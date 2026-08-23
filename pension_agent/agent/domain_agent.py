"""Search Service만 검색 Tool로 사용하는 공통 Domain Agent."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Annotated, Any, NotRequired, Protocol, cast
from uuid import UUID

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    hook_config,
)
from langchain.messages import AIMessage, HumanMessage, ToolCall, ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Command
from pydantic import Field, TypeAdapter, ValidationError

from pension_agent.agent.contracts import (
    DecisionStatus,
    DomainName,
    DomainRequest,
    DomainResult,
    EvidenceChunk,
    Permission,
    validate_domain_result,
)
from pension_agent.agent.execution import (
    ExecutionContext,
    ModelConcurrencyMiddleware,
    effective_deadline,
)
from pension_agent.agent.search import SearchRequest, SearchResult, SearchRunner
from pension_agent.config import DEFAULT_DOMAIN_AGENT_CONFIG, DomainAgentConfig

SEARCH_DOCUMENTS_TOOL_NAME = "search_documents"
SUBMIT_DOMAIN_RESULT_TOOL_NAME = "submit_domain_result"
_DOMAIN_RESULT_ADAPTER = TypeAdapter(DomainResult)
_NUMERIC_CLAIM_PATTERN = re.compile(
    r"(?:\d|%|퍼센트|프로|만\s*원|억\s*원|세율|공제율|공제액|금액|한도)"
)
_CALCULATOR_REQUIRED_CONCLUSION = "확정 수치 판단에는 결정론적 계산 Tool 결과가 필요합니다."
_CALCULATOR_REQUIRED_CONDITION = "결정론적 계산 Tool 결과"
_NUMERIC_CLAIM_WARNING = "계산 Tool 없이 세금·금액·세율·한도를 확정하지 않았습니다."
_NOT_APPLICABLE_CONCLUSION = "이 질문에는 해당 도메인 판단이 적용되지 않습니다."
_NO_EVIDENCE_CONCLUSION = "제공 문서에서 관련 근거를 확인하지 못해 판단할 수 없습니다."
ProductCodeResolver = Callable[[str], str]


class DomainAgentState(AgentState):
    """Domain Agent의 검증된 검색·결과 상태."""

    question: NotRequired[str]
    objective: NotRequired[str]
    product_candidate_codes: NotRequired[list[str]]
    product_scoped_search_completed: NotRequired[bool]
    search_result: NotRequired[SearchResult]
    domain_result: NotRequired[DomainResult]


class DomainGraph(Protocol):
    """Domain Agent 실행기가 사용하는 최소 Graph 계약."""

    async def ainvoke(
        self,
        input: dict[str, Any],
        /,
        *,
        context: ExecutionContext,
    ) -> Mapping[str, Any]:
        """초기 상태로 Domain Agent를 실행한다."""


class CompleteDomainResult(AgentMiddleware[Any, Any, Any]):
    """검증된 DomainResult 제출 후 추가 모델 호출 없이 종료한다."""

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("domain_result") is None:
            return None
        return {"jump_to": "end"}

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


class RequireDomainTool(AgentMiddleware[Any, Any, Any]):
    """DomainResult가 제출될 때까지 Function calling을 강제한다."""

    def __init__(self, *, domain: DomainName, max_search_calls: int) -> None:
        self._domain = domain
        self._max_search_calls = max_search_calls

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("domain_result") is not None:
            return None
        last_message = state.get("messages", [])[-1]
        if isinstance(last_message, AIMessage) and not last_message.tool_calls:
            search_result = state.get("search_result")
            if self._domain == "product":
                instruction = _product_next_tool_instruction(
                    state,
                    max_search_calls=self._max_search_calls,
                )
            elif search_result is not None:
                instruction = "최종 도메인 판단 결과 제출 Tool로 결과를 제출하세요."
            else:
                instruction = "search_documents Tool로 제공 문서 근거를 검색하세요."
            return {
                "jump_to": "model",
                "messages": [
                    HumanMessage(content=f"자유 형식 답변은 사용하지 않습니다. {instruction}")
                ],
            }
        return None

    @hook_config(can_jump_to=["model"])
    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


class SingleDomainSubmitPerModelCall(AgentMiddleware[Any, Any, Any]):
    """한 모델 응답의 병렬 DomainResult 제출을 하나로 제한한다."""

    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        last_message = state.get("messages", [])[-1]
        if not isinstance(last_message, AIMessage):
            return None
        submit_calls = [
            call
            for call in last_message.tool_calls
            if call["name"] == SUBMIT_DOMAIN_RESULT_TOOL_NAME
        ]
        if len(submit_calls) <= 1:
            return None
        kept_submit = False
        tool_calls: list[ToolCall] = []
        for call in last_message.tool_calls:
            if call["name"] != SUBMIT_DOMAIN_RESULT_TOOL_NAME:
                tool_calls.append(call)
                continue
            if not kept_submit:
                tool_calls.append(call)
                kept_submit = True
        return {
            "messages": [last_message.model_copy(update={"tool_calls": tool_calls})],
        }

    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


class EnforceProductToolSequence(AgentMiddleware[Any, Any, Any]):
    """Product Agent의 검색 우선·코드 식별·결과 제출 단계를 안전하게 제한한다."""

    def __init__(self, *, lookup_tool_name: str, max_search_calls: int) -> None:
        self._lookup_tool_name = lookup_tool_name
        self._max_search_calls = max_search_calls

    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        last_message = state.get("messages", [])[-1]
        if not isinstance(last_message, AIMessage) or state.get("domain_result") is not None:
            return None
        if not last_message.tool_calls:
            return None
        allowed_tools = _allowed_product_tools(
            state,
            lookup_tool_name=self._lookup_tool_name,
            max_search_calls=self._max_search_calls,
        )
        allowed_calls = [
            call
            for call in last_message.tool_calls
            if _product_tool_call_is_allowed(call, state=state, allowed_tools=allowed_tools)
        ]
        if not allowed_calls:
            return {
                "messages": [last_message.model_copy(update={"tool_calls": []})],
            }
        kept_call = allowed_calls[0]
        if last_message.tool_calls == [kept_call]:
            return None
        return {
            "messages": [last_message.model_copy(update={"tool_calls": [kept_call]})],
        }

    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


class DomainModelCallLimit(ModelCallLimitMiddleware):
    """모델 호출 상한에서 자유 형식 결과 생성 없이 종료한다."""

    def __init__(self, *, max_model_calls: int) -> None:
        super().__init__(run_limit=max_model_calls, exit_behavior="end")
        self._max_model_calls = max_model_calls

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("run_model_call_count", 0) < self._max_model_calls:
            return None
        return {
            "jump_to": "end",
            "messages": [AIMessage(content="Domain Agent 호출 한도에 도달했습니다.")],
        }

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


@dataclass(slots=True)
class DomainAgent:
    """Compiled create_agent를 DomainRequest -> DomainResult 계약으로 감싼다."""

    domain: DomainName
    graph: DomainGraph
    config: DomainAgentConfig = DEFAULT_DOMAIN_AGENT_CONFIG
    max_concurrency: int | None = None
    _capacity: asyncio.Semaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_concurrency is None:
            self.max_concurrency = self.config.max_concurrency
        if self.max_concurrency < 1:
            raise ValueError("Domain Agent 동시 실행 상한은 1 이상이어야 합니다.")
        self._capacity = asyncio.Semaphore(self.max_concurrency)

    async def __call__(
        self,
        request: DomainRequest,
        *,
        deadline: float | None = None,
    ) -> DomainResult:
        """질문 원문과 하나의 판단 목표를 Domain Agent에 전달한다."""

        question = request["question"].strip()
        objective = request["objective"].strip()
        if not question or not objective:
            return _failed_domain_result(self.domain, "도메인 판단 요청이 올바르지 않습니다.")

        run_deadline = effective_deadline(
            timeout_seconds=self.config.timeout_seconds,
            parent_deadline=deadline,
        )
        if run_deadline <= asyncio.get_running_loop().time():
            return _failed_domain_result(
                self.domain,
                "Domain Agent 실행 시간이 초과됐습니다.",
                execution_status="timeout",
            )
        try:
            async with asyncio.timeout_at(run_deadline):
                await self._capacity.acquire()
                try:
                    state = await self.graph.ainvoke(
                        {
                            "question": question,
                            "objective": objective,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": _domain_request_text(question, objective),
                                }
                            ],
                        },
                        context=ExecutionContext(deadline=run_deadline),
                    )
                finally:
                    self._capacity.release()
        except TimeoutError:
            return _failed_domain_result(
                self.domain,
                "Domain Agent 실행 시간이 초과됐습니다.",
                execution_status="timeout",
            )
        except Exception:  # noqa: BLE001
            return _failed_domain_result(self.domain, "Domain Agent 실행에 실패했습니다.")

        try:
            result = _DOMAIN_RESULT_ADAPTER.validate_python(state.get("domain_result"))
            validate_domain_result(result)
        except (AttributeError, KeyError, TypeError, ValueError, ValidationError):
            return _failed_domain_result(
                self.domain,
                "Domain Agent가 최종 판단 결과를 제출하지 못했습니다.",
            )
        if result["domain"] != self.domain:
            return _failed_domain_result(
                self.domain, "Domain Agent 결과 도메인이 일치하지 않습니다."
            )
        return result


def create_domain_agent(
    *,
    domain: DomainName,
    permission: Permission,
    model: BaseChatModel,
    search_service: SearchRunner,
    system_prompt: str,
    config: DomainAgentConfig = DEFAULT_DOMAIN_AGENT_CONFIG,
    model_concurrency: ModelConcurrencyMiddleware | None = None,
    product_code_resolver: ProductCodeResolver | None = None,
    product_lookup_tool: BaseTool | None = None,
) -> DomainAgent:
    """도메인별 검색 Tool과 최종 결과 제출 Tool을 가진 Domain Agent를 만든다."""

    if domain == "product":
        if product_code_resolver is None or product_lookup_tool is None:
            raise ValueError("Product Agent에는 상품 코드 식별 Tool과 코드 resolver가 필요합니다.")
        search_tool = _create_product_search_tool(
            search_service=search_service,
            permission=permission,
            product_code_resolver=product_code_resolver,
            max_search_calls=config.max_search_calls,
        )
    else:
        search_tool = _create_search_tool(
            domain=domain,
            search_service=search_service,
            permission=permission,
        )
    result_tool = _create_domain_result_tool(domain=domain)
    tools = (
        (product_lookup_tool, search_tool, result_tool)
        if product_lookup_tool is not None
        else (search_tool, result_tool)
    )
    graph = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        state_schema=DomainAgentState,
        context_schema=ExecutionContext,
        middleware=(
            *((model_concurrency,) if model_concurrency is not None else ()),
            CompleteDomainResult(),
            RequireDomainTool(domain=domain, max_search_calls=config.max_search_calls),
            SingleDomainSubmitPerModelCall(),
            DomainModelCallLimit(max_model_calls=config.max_model_calls),
            ToolCallLimitMiddleware(
                tool_name=SEARCH_DOCUMENTS_TOOL_NAME,
                run_limit=config.max_search_calls,
                exit_behavior="continue",
            ),
            *(
                (
                    ToolCallLimitMiddleware(
                        tool_name=product_lookup_tool.name,
                        run_limit=1,
                        exit_behavior="continue",
                    ),
                )
                if product_lookup_tool is not None
                else ()
            ),
            ToolCallLimitMiddleware(
                tool_name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                run_limit=config.max_submit_calls,
                exit_behavior="continue",
            ),
            # after_model hook은 역순 실행되므로 병렬 호출을 Tool 상한 집계보다 먼저 정제한다.
            *(
                (
                    EnforceProductToolSequence(
                        lookup_tool_name=product_lookup_tool.name,
                        max_search_calls=config.max_search_calls,
                    ),
                )
                if product_lookup_tool is not None
                else ()
            ),
        ),
        name=f"{domain}_agent",
    )
    return DomainAgent(domain=domain, graph=cast(DomainGraph, graph), config=config)


def _create_search_tool(
    *,
    domain: DomainName,
    search_service: SearchRunner,
    permission: Permission,
) -> Any:
    @tool(
        SEARCH_DOCUMENTS_TOOL_NAME,
        description="하나의 구체적인 판단 목표에 필요한 제공 문서 근거를 검색한다.",
    )
    async def search_documents(
        objective: Annotated[
            str,
            Field(min_length=1, description="하나의 구체적인 근거 검색 목표"),
        ],
        runtime: ToolRuntime[ExecutionContext, DomainAgentState],
        source_file_name: Annotated[
            str | None,
            Field(description="사용자가 명시했거나 이미 검증된 원본 파일명"),
        ] = None,
        chunk_id: Annotated[
            str | None,
            Field(description="이미 검증된 원문 청크 UUID"),
        ] = None,
        expand_neighbors: Annotated[
            bool,
            Field(description="기준 청크의 앞뒤 문맥이 필요한지 여부"),
        ] = False,
    ) -> Command:
        if runtime.tool_call_id is None:
            raise ValueError("Search Service Tool 호출 ID가 없습니다.")
        hints_are_trusted = all(
            _hint_is_present_in_question(runtime.state, hint)
            for hint in (source_file_name, chunk_id)
            if hint is not None
        )
        try:
            if not hints_are_trusted:
                raise ValueError("검색 힌트 출처를 확인할 수 없습니다.")
            request = SearchRequest(
                objective=objective,
                source_file_name=source_file_name,
                chunk_id=chunk_id,
                expand_neighbors=expand_neighbors,
            )
        except (TypeError, ValueError, ValidationError):
            result = SearchResult(
                execution_status="failed",
                error="검색 요청이 올바르지 않습니다.",
            )
        else:
            result = await search_service.search(
                request,
                permission=permission,
                deadline=runtime.context.deadline,
            )
        terminal_result = _terminal_domain_result_from_search(
            domain=domain,
            search_result=result,
        )
        update: dict[str, Any] = {
            "search_result": result,
            "messages": [
                ToolMessage(
                    content=result.model_dump_json(),
                    tool_call_id=runtime.tool_call_id,
                    name=SEARCH_DOCUMENTS_TOOL_NAME,
                )
            ],
        }
        if terminal_result is not None:
            update["domain_result"] = terminal_result
        return Command(update=update)

    return search_documents


def _create_product_search_tool(
    *,
    search_service: SearchRunner,
    permission: Permission,
    product_code_resolver: ProductCodeResolver,
    max_search_calls: int,
) -> Any:
    @tool(
        SEARCH_DOCUMENTS_TOOL_NAME,
        description="상품 문서 전체 또는 검증된 단일 상품에서 제공 문서 근거를 검색한다.",
    )
    async def search_documents(
        objective: Annotated[
            str,
            Field(min_length=1, description="하나의 구체적인 근거 검색 목표"),
        ],
        runtime: ToolRuntime[ExecutionContext, DomainAgentState],
        product_code: Annotated[
            str | None,
            Field(
                description=(
                    "lookup_product_codes가 반환한 단일 상품 코드. "
                    "상품 식별 전 전체 검색에서는 생략"
                )
            ),
        ] = None,
        expand_neighbors: Annotated[
            bool,
            Field(description="기준 청크의 앞뒤 문맥이 필요한지 여부"),
        ] = False,
    ) -> Command:
        if runtime.tool_call_id is None:
            raise ValueError("Search Service Tool 호출 ID가 없습니다.")
        candidate_codes = runtime.state.get("product_candidate_codes", [])
        scoped_search = bool(candidate_codes)
        try:
            source_file_name = None
            if scoped_search:
                if product_code is None:
                    raise ValueError("검증된 상품 코드가 필요합니다.")
                normalized_code = product_code.strip().upper()
                if normalized_code not in candidate_codes:
                    raise ValueError("상품 코드 식별 결과에 없는 코드입니다.")
                source_file_name = product_code_resolver(normalized_code)
            elif product_code is not None:
                raise ValueError("상품 식별 전에는 상품 코드를 검색 조건으로 사용할 수 없습니다.")
            request = SearchRequest(
                objective=objective,
                source_file_name=source_file_name,
                expand_neighbors=expand_neighbors,
            )
        except (TypeError, ValueError, ValidationError):
            result = SearchResult(
                execution_status="failed",
                error="검색 요청이 올바르지 않습니다.",
            )
        else:
            result = await search_service.search(
                request,
                permission=permission,
                deadline=runtime.context.deadline,
            )
        search_call_count = _search_call_count(runtime.state) + 1
        previous_result = None
        if scoped_search and runtime.state.get("product_scoped_search_completed"):
            previous_result = runtime.state.get("search_result")
        accumulated_result = _merge_completed_search_results(
            previous_result,
            result,
        )
        terminal_result = None
        if result.execution_status != "completed" or search_call_count >= max_search_calls:
            terminal_result = _terminal_domain_result_from_search(
                domain="product",
                search_result=accumulated_result,
            )
        update: dict[str, Any] = {
            "search_result": accumulated_result,
            "product_scoped_search_completed": scoped_search,
            "messages": [
                ToolMessage(
                    content=result.model_dump_json(),
                    tool_call_id=runtime.tool_call_id,
                    name=SEARCH_DOCUMENTS_TOOL_NAME,
                )
            ],
        }
        if terminal_result is not None:
            update["domain_result"] = terminal_result
        return Command(update=update)

    return search_documents


def _search_call_count(state: Mapping[str, Any]) -> int:
    """현재 실행에서 완료된 문서 검색 Tool 호출 수를 센다."""

    return sum(
        isinstance(message, ToolMessage) and message.name == SEARCH_DOCUMENTS_TOOL_NAME
        for message in state.get("messages", [])
    )


def _allowed_product_tools(
    state: Mapping[str, Any],
    *,
    lookup_tool_name: str,
    max_search_calls: int,
) -> tuple[str, ...]:
    """현재 Product Agent 상태에서 실행 가능한 다음 Tool 이름을 반환한다."""

    search_call_count = _search_call_count(state)
    if not state.get("product_candidate_codes"):
        if search_call_count == 0:
            return (lookup_tool_name, SEARCH_DOCUMENTS_TOOL_NAME)
        return (lookup_tool_name,)
    if not state.get("product_scoped_search_completed"):
        return (SEARCH_DOCUMENTS_TOOL_NAME,)
    if search_call_count >= max_search_calls:
        return (SUBMIT_DOMAIN_RESULT_TOOL_NAME,)
    search_result = state.get("search_result")
    if search_result is not None and not search_result.retrieved_chunks:
        return (SEARCH_DOCUMENTS_TOOL_NAME,)
    return (SUBMIT_DOMAIN_RESULT_TOOL_NAME, SEARCH_DOCUMENTS_TOOL_NAME)


def _product_tool_call_is_allowed(
    call: ToolCall,
    *,
    state: Mapping[str, Any],
    allowed_tools: tuple[str, ...],
) -> bool:
    """상품 식별 전 검색에는 모델이 만든 product_code가 섞이지 않게 한다."""

    if call["name"] not in allowed_tools:
        return False
    if call["name"] != SEARCH_DOCUMENTS_TOOL_NAME or state.get("product_candidate_codes"):
        return True
    return call["args"].get("product_code") is None


def _product_next_tool_instruction(
    state: Mapping[str, Any],
    *,
    max_search_calls: int,
) -> str:
    """Product Agent의 현재 단계에 맞는 다음 Tool 안내를 만든다."""

    search_call_count = _search_call_count(state)
    if not state.get("product_candidate_codes"):
        if search_call_count == 0:
            return (
                "lookup_product_codes Tool로 상품을 식별하거나 product_code 없이 "
                "search_documents Tool로 상품 문서를 먼저 검색하세요."
            )
        return "lookup_product_codes Tool로 검색 대상 상품 코드를 식별하세요."
    if not state.get("product_scoped_search_completed"):
        return "검증된 product_code로 search_documents Tool을 호출하세요."
    search_result = state.get("search_result")
    if (
        search_result is not None
        and not search_result.retrieved_chunks
        and search_call_count < max_search_calls
    ):
        return "검색 목표를 다르게 재작성해 search_documents Tool을 호출하세요."
    return "최종 도메인 판단 결과 제출 Tool로 결과를 제출하세요."


def _merge_completed_search_results(
    previous: SearchResult | None,
    current: SearchResult,
) -> SearchResult:
    """완료된 검색 근거를 청크 ID 기준으로 누적하고 중복을 제거한다."""

    if (
        previous is None
        or previous.execution_status != "completed"
        or current.execution_status != "completed"
    ):
        return current
    chunks_by_id = {
        chunk.chunk_id: chunk for chunk in (*previous.retrieved_chunks, *current.retrieved_chunks)
    }
    limitations = []
    if not chunks_by_id:
        limitations = list(dict.fromkeys((*previous.limitations, *current.limitations)))
    return SearchResult(
        execution_status="completed",
        retrieved_chunks=list(chunks_by_id.values()),
        limitations=limitations,
    )


def _create_domain_result_tool(*, domain: DomainName) -> Any:
    @tool(
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
        description=(
            "최종 도메인 판단 결과 제출 Tool. 검증된 검색 근거에서 도출한 "
            "판단, 누락 조건과 경고만 제출한다."
        ),
    )
    async def submit_domain_result(
        status: Annotated[
            DecisionStatus,
            Field(description="determined, conditional, undetermined, not_applicable 중 하나"),
        ],
        conclusion: Annotated[str, Field(min_length=1, description="근거에서 도출한 결론")],
        missing_conditions: Annotated[
            list[str],
            Field(description="조건부 또는 미확정 판단에 필요한 누락 조건"),
        ],
        warnings: Annotated[list[str], Field(description="이용자가 알아야 할 제한과 주의사항")],
        evidence_chunk_ids: Annotated[
            list[str],
            Field(description="결론에 실제 사용한 SearchResult 청크 UUID 목록"),
        ],
        runtime: ToolRuntime[ExecutionContext, DomainAgentState],
    ) -> Command | str:
        search_result = runtime.state.get("search_result")
        if search_result is None:
            return json.dumps(
                {"error": "search_documents Tool을 먼저 호출해야 합니다."},
                ensure_ascii=False,
            )
        if domain == "product" and not runtime.state.get("product_scoped_search_completed"):
            return json.dumps(
                {"error": "검증된 product_code로 search_documents Tool을 호출해야 합니다."},
                ensure_ascii=False,
            )
        try:
            result = _build_domain_result(
                domain=domain,
                search_result=search_result,
                status=status,
                conclusion=conclusion,
                missing_conditions=missing_conditions,
                warnings=warnings,
                evidence_chunk_ids=evidence_chunk_ids,
            )
            validate_domain_result(result)
        except (KeyError, TypeError, ValueError):
            return json.dumps(
                {"error": "최종 도메인 판단 결과가 공통 계약을 위반했습니다."},
                ensure_ascii=False,
            )
        if runtime.tool_call_id is None:
            raise ValueError("최종 Domain Agent 결과 제출 Tool 호출 ID가 없습니다.")
        return Command(
            update={
                "domain_result": result,
                "messages": [
                    ToolMessage(
                        content=json.dumps({"status": "accepted"}, ensure_ascii=False),
                        tool_call_id=runtime.tool_call_id,
                        name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                    )
                ],
            }
        )

    return submit_domain_result


def _build_domain_result(
    *,
    domain: DomainName,
    search_result: SearchResult,
    status: DecisionStatus,
    conclusion: str,
    missing_conditions: list[str],
    warnings: list[str],
    evidence_chunk_ids: list[str],
) -> DomainResult:
    if search_result.execution_status != "completed":
        return _failed_domain_result(
            domain,
            search_result.error or "검색을 완료하지 못했습니다.",
            execution_status=search_result.execution_status,
        )

    selected_chunks = _select_evidence_chunks(
        search_result=search_result,
        evidence_chunk_ids=evidence_chunk_ids,
    )
    normalized_missing = [value.strip() for value in missing_conditions if value.strip()]
    normalized_warnings = [value.strip() for value in warnings if value.strip()]
    normalized_limitations = list(search_result.limitations)
    normalized_conclusion = conclusion.strip()
    untrusted_text = (
        normalized_conclusion,
        *normalized_missing,
        *normalized_warnings,
        *normalized_limitations,
    )
    if domain == "tax_payout" and any(
        _NUMERIC_CLAIM_PATTERN.search(value) for value in untrusted_text
    ):
        status = "conditional"
        normalized_conclusion = _CALCULATOR_REQUIRED_CONCLUSION
        normalized_missing = [_CALCULATOR_REQUIRED_CONDITION]
        normalized_warnings = [
            value for value in normalized_warnings if not _NUMERIC_CLAIM_PATTERN.search(value)
        ]
        normalized_limitations = [
            value for value in normalized_limitations if not _NUMERIC_CLAIM_PATTERN.search(value)
        ]
        normalized_warnings.append(_NUMERIC_CLAIM_WARNING)
    if not selected_chunks and status != "not_applicable":
        status = "undetermined"
        normalized_conclusion = _NO_EVIDENCE_CONCLUSION
        normalized_missing = ["제공 문서의 관련 근거"]
        normalized_warnings.append("검색된 원문 청크 중 결론에 사용한 근거가 제출되지 않았습니다.")

    if status == "not_applicable":
        normalized_conclusion = _NOT_APPLICABLE_CONCLUSION
        normalized_missing = []
        normalized_warnings = []
        normalized_limitations = []

    normalized_warnings.extend(normalized_limitations)
    evidence = [_evidence_from_chunk(chunk) for chunk in selected_chunks]
    if status == "not_applicable":
        evidence = []
    return {
        "domain": domain,
        "execution_status": "completed",
        "decision": {
            "status": status,
            "conclusion": normalized_conclusion,
            "missing_conditions": normalized_missing,
        },
        "evidence": evidence,
        "calculations": [],
        "warnings": list(dict.fromkeys(normalized_warnings)),
    }


def _select_evidence_chunks(
    *,
    search_result: SearchResult,
    evidence_chunk_ids: list[str],
) -> list[Any]:
    """Domain 모델이 명시한 검증된 SearchResult 부분집합만 반환한다."""

    try:
        normalized_ids = [str(UUID(value.strip())) for value in evidence_chunk_ids]
    except (AttributeError, TypeError, ValueError):
        raise ValueError("근거 청크 ID는 UUID 형식이어야 합니다.") from None
    if len(normalized_ids) != len(set(normalized_ids)):
        raise ValueError("근거 청크 ID는 중복될 수 없습니다.")
    chunks_by_id = {chunk.chunk_id: chunk for chunk in search_result.retrieved_chunks}
    if any(chunk_id not in chunks_by_id for chunk_id in normalized_ids):
        raise ValueError("SearchResult에 없는 청크를 근거로 제출할 수 없습니다.")
    return [chunks_by_id[chunk_id] for chunk_id in normalized_ids]


def _terminal_domain_result_from_search(
    *,
    domain: DomainName,
    search_result: SearchResult,
) -> DomainResult | None:
    """검색 실패나 빈 결과는 모델 재호출 없이 안전하게 종료한다."""

    if search_result.execution_status != "completed":
        return _failed_domain_result(
            domain,
            search_result.error or "검색을 완료하지 못했습니다.",
            execution_status=search_result.execution_status,
        )
    if search_result.retrieved_chunks:
        return None
    return {
        "domain": domain,
        "execution_status": "completed",
        "decision": {
            "status": "undetermined",
            "conclusion": _NO_EVIDENCE_CONCLUSION,
            "missing_conditions": ["제공 문서의 관련 근거"],
        },
        "evidence": [],
        "calculations": [],
        "warnings": list(
            dict.fromkeys(
                [
                    *search_result.limitations,
                    "제공 문서에서 관련 근거를 확인하지 못했습니다.",
                ]
            )
        ),
    }


def _hint_is_present_in_question(state: DomainAgentState, hint: str) -> bool:
    """모델이 생성한 힌트 대신 사용자 원문에 있는 힌트만 허용한다."""

    question = state.get("question", "")
    return hint.strip() in question


def _evidence_from_chunk(chunk: Any) -> EvidenceChunk:
    return {
        "chunk_id": chunk.chunk_id,
        "source_file_name": chunk.source_file_name,
        "title": chunk.title,
        "locator": chunk.locator,
        "content": chunk.content,
    }


def _failed_domain_result(
    domain: DomainName,
    error: str,
    *,
    execution_status: str = "failed",
) -> DomainResult:
    return cast(
        DomainResult,
        {
            "domain": domain,
            "execution_status": execution_status,
            "evidence": [],
            "calculations": [],
            "warnings": [],
            "error": error,
        },
    )


def _domain_request_text(question: str, objective: str) -> str:
    return f"질문 원문: {question}\n판단 목표: {objective}"
