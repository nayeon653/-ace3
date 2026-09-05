"""Policy 도메인의 ReAct 구현."""

from __future__ import annotations

import json
import operator
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any, NotRequired, Protocol, cast
from uuid import UUID

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelCallResult,
    ModelRequest,
    ModelResponse,
    ToolCallLimitMiddleware,
    hook_config,
)
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel
from langgraph.types import Command
from pydantic import Field, ValidationError

from pension_agent.agent.calculation import (
    CALCULATE_DC_MEDICAL_WITHDRAWAL_THRESHOLD_TOOL_NAME,
    CALCULATE_ISA_TRANSFER_DEADLINE_TOOL_NAME,
    calculation_evidence_chunk_ids,
    create_dc_medical_withdrawal_threshold_tool,
    create_isa_transfer_deadline_tool,
    format_calculation_summary,
)
from pension_agent.agent.contracts import (
    CalculationResult,
    DecisionStatus,
    DomainRequest,
    DomainResult,
    EvidenceChunk,
    Permission,
    validate_domain_result,
)
from pension_agent.agent.domain_runner import failed_domain_result
from pension_agent.agent.execution import ExecutionContext, ModelConcurrencyMiddleware
from pension_agent.agent.prompt_injection import PromptInjectionMiddleware
from pension_agent.agent.search import (
    SearchRequest,
    SearchResult,
    SearchRunner,
    combine_search_objective,
)
from pension_agent.config import DomainAgentConfig

SEARCH_DOCUMENTS_TOOL_NAME = "search_documents"
SUBMIT_DOMAIN_RESULT_TOOL_NAME = "submit_domain_result"
_NOT_APPLICABLE_CONCLUSION = "이 질문에는 해당 도메인 판단이 적용되지 않습니다."
_NO_EVIDENCE_CONCLUSION = "제공 문서에서 관련 근거를 확인하지 못해 판단할 수 없습니다."


def _policy_model_request_tool_name(model_tool: Any) -> str | None:
    """ModelRequest의 LangChain·provider Tool 표현에서 이름을 읽는다."""

    name = getattr(model_tool, "name", None)
    if isinstance(name, str):
        return name
    if not isinstance(model_tool, Mapping):
        return None
    name = model_tool.get("name")
    if isinstance(name, str):
        return name
    function = model_tool.get("function")
    if not isinstance(function, Mapping):
        return None
    function_name = function.get("name")
    return function_name if isinstance(function_name, str) else None


def _policy_historical_tool_names(messages: list[Any]) -> set[str]:
    """provider 대화 이력이 참조하는 과거 Tool 이름을 수집한다."""

    names: set[str] = set()
    for message in messages:
        if isinstance(message, AIMessage):
            names.update(
                call["name"] for call in message.tool_calls if isinstance(call.get("name"), str)
            )
        elif isinstance(message, ToolMessage) and isinstance(message.name, str):
            names.add(message.name)
    return names


class PolicyAgentState(AgentState):
    """Policy ReAct의 검색·결과 상태."""

    question: NotRequired[str]
    objective: NotRequired[str]
    search_result: NotRequired[SearchResult]
    calculations: NotRequired[Annotated[list[CalculationResult], operator.add]]
    domain_result: NotRequired[DomainResult]


class PolicyGraph(Protocol):
    async def ainvoke(
        self,
        input: dict[str, Any],
        /,
        *,
        context: ExecutionContext,
    ) -> Mapping[str, Any]: ...


@dataclass(slots=True)
class PolicyReactAgent:
    """Policy CompiledStateGraph를 공통 Domain 계약으로 노출한다."""

    graph: PolicyGraph

    async def __call__(
        self,
        request: DomainRequest,
        *,
        deadline: float | None = None,
    ) -> DomainResult:
        if deadline is None:
            raise ValueError("Policy Agent 실행 deadline이 없습니다.")
        state = await self.graph.ainvoke(
            {
                "question": request["question"],
                "objective": request["objective"],
                "calculations": [],
                "messages": [{"role": "user", "content": _request_text(request)}],
            },
            context=ExecutionContext(deadline=deadline),
        )
        return cast(DomainResult, state.get("domain_result"))


class CompletePolicyResult(AgentMiddleware[Any, Any, Any]):
    @hook_config(can_jump_to=["end"])
    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        return {"jump_to": "end"} if state.get("domain_result") is not None else None

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


class RequirePolicyTool(AgentMiddleware[Any, Any, Any]):
    @hook_config(can_jump_to=["model"])
    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("domain_result") is not None:
            return None
        last_message = state.get("messages", [])[-1]
        if not isinstance(last_message, AIMessage) or last_message.tool_calls:
            return None
        if state.get("calculations"):
            instruction = "최종 도메인 판단 결과 제출 Tool로 결과를 제출하세요."
        elif state.get("search_result") is not None:
            instruction = (
                "사용자 조건으로 새 기준값·날짜를 산출해야 할 때만 시스템 지침의 "
                "Calculation Tool 하나를 호출하세요. 그렇지 않으면 방금 판단에서 "
                "objective의 확인 항목과 근거의 조건·예외를 삭제하거나 축약하지 말고, "
                "스스로 완결된 conclusion과 실제 사용한 근거 UUID를 "
                "submit_domain_result Tool로 제출하세요. 설명문 대신 Tool만 호출하세요."
            )
        else:
            instruction = "search_documents Tool로 제공 문서 근거를 검색하세요."
        return {
            "jump_to": "model",
            "messages": [
                HumanMessage(content=f"자유 형식 답변은 사용하지 않습니다. {instruction}")
            ],
        }

    @hook_config(can_jump_to=["model"])
    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


class PolicyToolAvailabilityMiddleware(AgentMiddleware[Any, Any, Any]):
    """Policy 실행 단계에 필요한 Tool schema만 auto 선택으로 노출한다."""

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelCallResult[Any]:
        state = request.state
        state = state or {}
        required_tool_names = set(_policy_historical_tool_names(request.messages))
        required_tool_names.add(SUBMIT_DOMAIN_RESULT_TOOL_NAME)
        optional_tool_names: set[str] = set()
        if state.get("search_result") is None:
            required_tool_names.add(SEARCH_DOCUMENTS_TOOL_NAME)
        elif not state.get("calculations"):
            optional_tool_names.update(
                {
                    CALCULATE_DC_MEDICAL_WITHDRAWAL_THRESHOLD_TOOL_NAME,
                    CALCULATE_ISA_TRANSFER_DEADLINE_TOOL_NAME,
                }
            )

        available_tools = list(request.tools or [])
        available_tool_names = [
            _policy_model_request_tool_name(model_tool) for model_tool in available_tools
        ]
        selected_name_set = required_tool_names | (
            optional_tool_names & {name for name in available_tool_names if name is not None}
        )
        selected_tools = [
            model_tool
            for model_tool, name in zip(available_tools, available_tool_names, strict=True)
            if name in selected_name_set
        ]
        selected_tool_names = [name for name in available_tool_names if name in selected_name_set]
        if (
            any(name is None for name in available_tool_names)
            or any(selected_tool_names.count(name) != 1 for name in selected_name_set)
            or not required_tool_names <= set(selected_tool_names)
        ):
            raise RuntimeError("Policy 상태별 Tool 구성이 올바르지 않습니다.")
        return await handler(request.override(tools=selected_tools, tool_choice=None))


class EnforcePolicyToolSequence(AgentMiddleware[Any, Any, Any]):
    """검색·Policy 계산·결과 제출 순서에서 허용된 Tool 호출만 남긴다."""

    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        last_message = state.get("messages", [])[-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return None
        allowed: tuple[str, ...]
        if state.get("search_result") is None:
            allowed = (SEARCH_DOCUMENTS_TOOL_NAME, SUBMIT_DOMAIN_RESULT_TOOL_NAME)
        elif state.get("calculations"):
            allowed = (SUBMIT_DOMAIN_RESULT_TOOL_NAME,)
        else:
            allowed = (
                CALCULATE_DC_MEDICAL_WITHDRAWAL_THRESHOLD_TOOL_NAME,
                CALCULATE_ISA_TRANSFER_DEADLINE_TOOL_NAME,
                SUBMIT_DOMAIN_RESULT_TOOL_NAME,
            )
        allowed_calls = [call for call in last_message.tool_calls if call["name"] in allowed]
        calculation_calls = [
            call for call in allowed_calls if call["name"] != SUBMIT_DOMAIN_RESULT_TOOL_NAME
        ]
        kept_calls = calculation_calls[:1] if calculation_calls else allowed_calls[:1]
        if kept_calls == last_message.tool_calls:
            return None
        return {"messages": [last_message.model_copy(update={"tool_calls": kept_calls})]}

    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


class PolicyModelCallLimit(ModelCallLimitMiddleware):
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
            "messages": [AIMessage(content="Policy Agent 호출 한도에 도달했습니다.")],
        }

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


def create_policy_react_agent(
    *,
    model: BaseChatModel,
    search_service: SearchRunner,
    system_prompt: str,
    config: DomainAgentConfig,
    model_concurrency: ModelConcurrencyMiddleware | None,
) -> PolicyReactAgent:
    """Policy 패키지가 소유하는 ReAct graph를 만든다."""

    threshold_tool = create_dc_medical_withdrawal_threshold_tool()
    isa_transfer_deadline_tool = create_isa_transfer_deadline_tool()
    graph = create_agent(
        model=model,
        tools=(
            _create_policy_search_tool(search_service),
            threshold_tool,
            isa_transfer_deadline_tool,
            _create_policy_result_tool(),
        ),
        system_prompt=system_prompt,
        state_schema=PolicyAgentState,
        context_schema=ExecutionContext,
        middleware=(
            PromptInjectionMiddleware(),
            *((model_concurrency,) if model_concurrency is not None else ()),
            CompletePolicyResult(),
            RequirePolicyTool(),
            PolicyToolAvailabilityMiddleware(),
            PolicyModelCallLimit(max_model_calls=config.max_model_calls),
            ToolCallLimitMiddleware(
                tool_name=SEARCH_DOCUMENTS_TOOL_NAME,
                run_limit=config.max_search_calls,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=threshold_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=isa_transfer_deadline_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                run_limit=config.max_submit_calls,
                exit_behavior="continue",
            ),
            EnforcePolicyToolSequence(),
        ),
        name="policy_agent",
    )
    return PolicyReactAgent(graph=cast(PolicyGraph, graph))


def _create_policy_search_tool(search_service: SearchRunner) -> Any:
    @tool(
        SEARCH_DOCUMENTS_TOOL_NAME,
        description=(
            "연금 참고자료에서 판단 목표의 근거를 검색한다. objective에는 원래 판단 목표에 "
            "덧붙일 구체적인 검색 초점을 쓰고 "
            "source_file_name과 chunk_id는 둘 다 null로 시작한다. "
            "사용자가 조회 식별자를 명시한 경우에만 하나를 바꾼다. 문서 타입은 시스템이 제한한다."
        ),
    )
    async def search_documents(
        objective: Annotated[
            str,
            Field(min_length=1, description="원래 판단 목표에 덧붙일 구체적인 검색 초점"),
        ],
        runtime: ToolRuntime[ExecutionContext, PolicyAgentState],
        source_file_name: Annotated[
            str | None,
            Field(
                description=(
                    "기본값은 JSON null. 사용자 질문에 조회 대상으로 명시된 확장자 포함 "
                    "원본 파일명이 있을 때만 그 식별자 그대로 바꾼다. "
                    "[개인연금] 같은 범주 접두사·주제·문서 타입은 null을 유지한다. "
                    "chunk_id가 있으면 이 필드는 null이다."
                )
            ),
        ] = None,
        chunk_id: Annotated[
            str | None,
            Field(
                description=(
                    "기본값은 JSON null. 사용자 질문에 조회 대상으로 명시된 유효한 UUID가 "
                    "있을 때만 그 UUID로 바꾼다. 이때 source_file_name은 null을 유지한다."
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
        try:
            if not all(
                _hint_is_present_in_question(runtime.state, hint)
                for hint in (source_file_name, chunk_id)
                if hint is not None
            ):
                raise ValueError("검색 힌트 출처를 확인할 수 없습니다.")
            request = SearchRequest(
                objective=combine_search_objective(
                    domain_objective=runtime.state.get("objective", ""),
                    model_focus=objective,
                ),
                source_file_name=source_file_name,
                chunk_id=chunk_id,
                expand_neighbors=expand_neighbors,
            )
        except (TypeError, ValueError, ValidationError):
            result = SearchResult(execution_status="failed", error="검색 요청이 올바르지 않습니다.")
        else:
            result = await search_service.search(
                request,
                permission=Permission.POLICY,
                deadline=runtime.context.deadline,
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
        terminal_result = _terminal_result_from_search(result)
        if terminal_result is not None:
            update["domain_result"] = terminal_result
        return Command(update=update)

    return search_documents


def _create_policy_result_tool() -> Any:
    @tool(
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
        description=(
            "최종 업무·제도 판단 결과 제출 Tool. 검증된 검색 근거에서 도출한 "
            "판단, 누락 조건과 경고만 제출한다. objective의 각 확인 항목은 "
            "근거가 있으면 conclusion에, 없으면 missing_conditions에 남겨야 한다."
        ),
    )
    async def submit_domain_result(
        status: Annotated[
            DecisionStatus,
            Field(description="determined, conditional, undetermined, not_applicable 중 하나"),
        ],
        conclusion: Annotated[
            str,
            Field(
                min_length=1,
                description=(
                    "질문에 직접 답하고 objective에서 근거로 확인한 대상·절차·"
                    "조건·예외를 누락하지 않은 스스로 완결된 결론"
                ),
            ),
        ],
        missing_conditions: Annotated[
            list[str],
            Field(description="objective 항목 중 근거·사용자 조건이 부족해 확정하지 못한 내용"),
        ],
        warnings: Annotated[list[str], Field(description="이용자가 알아야 할 제한과 주의사항")],
        evidence_chunk_ids: Annotated[
            list[str],
            Field(description="결론에 실제 사용한 SearchResult 청크 UUID 목록"),
        ],
        runtime: ToolRuntime[ExecutionContext, PolicyAgentState],
    ) -> Command | str:
        tool_call_id = runtime.tool_call_id
        if tool_call_id is None:
            raise ValueError("최종 Policy Agent 결과 제출 Tool 호출 ID가 없습니다.")
        if status == "not_applicable":
            return Command(
                update={
                    "domain_result": _not_applicable_policy_result(),
                    "messages": [
                        ToolMessage(
                            content=json.dumps({"status": "accepted"}, ensure_ascii=False),
                            tool_call_id=tool_call_id,
                            name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                        )
                    ],
                }
            )
        search_result = runtime.state.get("search_result")
        if search_result is None:
            return json.dumps(
                {"error": "search_documents Tool을 먼저 호출해야 합니다."},
                ensure_ascii=False,
            )
        try:
            result = _build_policy_result(
                search_result=search_result,
                calculations=list(runtime.state.get("calculations", [])),
                status=status,
                conclusion=conclusion,
                missing_conditions=missing_conditions,
                warnings=warnings,
                evidence_chunk_ids=evidence_chunk_ids,
            )
            validate_domain_result(result)
        except (KeyError, TypeError, ValueError):
            return json.dumps(
                {"error": "최종 업무·제도 판단 결과가 공통 계약을 위반했습니다."},
                ensure_ascii=False,
            )
        return Command(
            update={
                "domain_result": result,
                "messages": [
                    ToolMessage(
                        content=json.dumps({"status": "accepted"}, ensure_ascii=False),
                        tool_call_id=tool_call_id,
                        name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                    )
                ],
            }
        )

    return submit_domain_result


def _not_applicable_policy_result() -> DomainResult:
    return {
        "domain": "policy",
        "execution_status": "completed",
        "decision": {
            "status": "not_applicable",
            "conclusion": _NOT_APPLICABLE_CONCLUSION,
            "missing_conditions": [],
        },
        "evidence": [],
        "calculations": [],
        "warnings": [],
    }


def _build_policy_result(
    *,
    search_result: SearchResult,
    calculations: list[CalculationResult],
    status: DecisionStatus,
    conclusion: str,
    missing_conditions: list[str],
    warnings: list[str],
    evidence_chunk_ids: list[str],
) -> DomainResult:
    if search_result.execution_status != "completed":
        return failed_domain_result(
            "policy",
            search_result.error or "검색을 완료하지 못했습니다.",
            execution_status=search_result.execution_status,
        )
    required_evidence_ids = calculation_evidence_chunk_ids(calculations)
    selected_chunks = _select_evidence(
        search_result,
        list(dict.fromkeys([*evidence_chunk_ids, *required_evidence_ids])),
    )
    normalized_missing = [value.strip() for value in missing_conditions if value.strip()]
    normalized_warnings = [value.strip() for value in warnings if value.strip()]
    normalized_warnings.extend(search_result.limitations)
    normalized_conclusion = conclusion.strip()
    if calculations:
        normalized_conclusion = (
            "검증된 Python 계산 결과:\n"
            + format_calculation_summary(calculations)
            + "\n제도 판단:\n"
            + normalized_conclusion
        )
        normalized_warnings.extend(
            warning for calculation in calculations for warning in calculation["warnings"]
        )
    if not selected_chunks and status != "not_applicable":
        status = "undetermined"
        normalized_conclusion = _NO_EVIDENCE_CONCLUSION
        normalized_missing = list(dict.fromkeys(normalized_missing or ["제공 문서의 관련 근거"]))
        normalized_warnings = list(
            dict.fromkeys(
                [
                    *search_result.limitations,
                    "검색된 원문 청크 중 결론에 사용한 근거가 제출되지 않았습니다.",
                ]
            )
        )
    if status == "not_applicable":
        normalized_conclusion = _NOT_APPLICABLE_CONCLUSION
        normalized_missing = []
        normalized_warnings = []
        selected_chunks = []
        calculations = []
    return {
        "domain": "policy",
        "execution_status": "completed",
        "decision": {
            "status": status,
            "conclusion": normalized_conclusion,
            "missing_conditions": normalized_missing,
        },
        "evidence": [_evidence_from_chunk(chunk) for chunk in selected_chunks],
        "calculations": calculations,
        "warnings": list(dict.fromkeys(normalized_warnings)),
    }


def _select_evidence(search_result: SearchResult, evidence_chunk_ids: list[str]) -> list[Any]:
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


def _terminal_result_from_search(search_result: SearchResult) -> DomainResult | None:
    if search_result.execution_status != "completed":
        return failed_domain_result(
            "policy",
            search_result.error or "검색을 완료하지 못했습니다.",
            execution_status=search_result.execution_status,
        )
    if search_result.retrieved_chunks:
        return None
    return {
        "domain": "policy",
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
                [*search_result.limitations, "제공 문서에서 관련 근거를 확인하지 못했습니다."]
            )
        ),
    }


def _hint_is_present_in_question(state: PolicyAgentState, hint: str) -> bool:
    return hint.strip() in state.get("question", "")


def _evidence_from_chunk(chunk: Any) -> EvidenceChunk:
    return {
        "chunk_id": chunk.chunk_id,
        "source_file_name": chunk.source_file_name,
        "title": chunk.title,
        "locator": chunk.locator,
        "content": chunk.content,
    }


def _request_text(request: DomainRequest) -> str:
    return f"질문 원문: {request['question']}\n판단 목표: {request['objective']}"
