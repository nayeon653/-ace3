"""Search Agent만 비즈니스 Tool로 사용하는 공통 Domain Agent."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from threading import BoundedSemaphore
from typing import Annotated, Any, NotRequired, Protocol, cast

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    hook_config,
)
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel
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
from pension_agent.agent.search import SearchAgentAdapter, SearchResult
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


class DomainAgentState(AgentState):
    """Domain Agent의 검증된 검색·결과 상태."""

    search_result: NotRequired[SearchResult]
    domain_result: NotRequired[DomainResult]


class DomainGraph(Protocol):
    """Domain Agent 실행기가 사용하는 최소 Graph 계약."""

    def invoke(self, input: dict[str, Any], /) -> Mapping[str, Any]:
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

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("domain_result") is not None:
            return None
        last_message = state.get("messages", [])[-1]
        if isinstance(last_message, AIMessage) and not last_message.tool_calls:
            return {
                "jump_to": "model",
                "messages": [
                    HumanMessage(
                        content=(
                            "자유 형식 답변은 사용하지 않습니다. Search Agent Tool을 호출하고 "
                            "최종 도메인 판단 결과 제출 Tool로 결과를 제출하세요."
                        )
                    )
                ],
            }
        return None

    @hook_config(can_jump_to=["model"])
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
    max_workers: int = 2
    _executor: ThreadPoolExecutor = field(init=False, repr=False)
    _capacity: BoundedSemaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("Domain Agent worker 수는 1 이상이어야 합니다.")
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix=f"{self.domain}-agent",
        )
        self._capacity = BoundedSemaphore(self.max_workers)

    def __call__(self, request: DomainRequest) -> DomainResult:
        """질문 원문과 하나의 판단 목표를 Domain Agent에 전달한다."""

        question = request["question"].strip()
        objective = request["objective"].strip()
        if not question or not objective:
            return _failed_domain_result(self.domain, "도메인 판단 요청이 올바르지 않습니다.")

        if not self._capacity.acquire(blocking=False):
            return _failed_domain_result(
                self.domain,
                "Domain Agent가 현재 처리 가능한 요청 수를 초과했습니다.",
            )
        try:
            future: Future[Mapping[str, Any]] = self._executor.submit(
                self.graph.invoke,
                {
                    "messages": [
                        {"role": "user", "content": _domain_request_text(question, objective)}
                    ]
                },
            )
        except RuntimeError:
            self._capacity.release()
            return _failed_domain_result(self.domain, "Domain Agent 실행기를 사용할 수 없습니다.")
        future.add_done_callback(lambda completed: self._capacity.release())
        try:
            state = future.result(timeout=self.config.timeout_seconds)
        except TimeoutError:
            future.cancel()
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

    def close(self) -> None:
        """프로세스 종료 시 실행 worker를 정리한다."""

        self._executor.shutdown(wait=False, cancel_futures=True)


def create_domain_agent(
    *,
    domain: DomainName,
    permission: Permission,
    model: BaseChatModel,
    search_adapter: SearchAgentAdapter,
    system_prompt: str,
    config: DomainAgentConfig = DEFAULT_DOMAIN_AGENT_CONFIG,
) -> DomainAgent:
    """Search Agent Tool과 최종 결과 제출 Tool만 가진 Domain Agent를 만든다."""

    search_tool = _create_search_tool(search_adapter=search_adapter, permission=permission)
    result_tool = _create_domain_result_tool(domain=domain)
    graph = create_agent(
        model=model,
        tools=(search_tool, result_tool),
        system_prompt=system_prompt,
        state_schema=DomainAgentState,
        middleware=(
            CompleteDomainResult(),
            RequireDomainTool(),
            DomainModelCallLimit(max_model_calls=config.max_model_calls),
            ToolCallLimitMiddleware(
                tool_name=SEARCH_DOCUMENTS_TOOL_NAME,
                run_limit=config.max_search_calls,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                run_limit=config.max_submit_calls,
                exit_behavior="continue",
            ),
        ),
        name=f"{domain}_agent",
    )
    return DomainAgent(domain=domain, graph=cast(DomainGraph, graph), config=config)


def _create_search_tool(
    *,
    search_adapter: SearchAgentAdapter,
    permission: Permission,
) -> Any:
    @tool(
        SEARCH_DOCUMENTS_TOOL_NAME,
        description="하나의 구체적인 판단 목표에 필요한 제공 문서 근거를 검색한다.",
    )
    def search_documents(
        objective: Annotated[
            str,
            Field(min_length=1, description="하나의 구체적인 근거 검색 목표"),
        ],
        runtime: ToolRuntime[None, DomainAgentState],
    ) -> Command:
        result = search_adapter.search(objective, permission=permission)
        if runtime.tool_call_id is None:
            raise ValueError("Search Agent Tool 호출 ID가 없습니다.")
        return Command(
            update={
                "search_result": result,
                "messages": [
                    ToolMessage(
                        content=result.model_dump_json(),
                        tool_call_id=runtime.tool_call_id,
                        name=SEARCH_DOCUMENTS_TOOL_NAME,
                    )
                ],
            }
        )

    return search_documents


def _create_domain_result_tool(*, domain: DomainName) -> Any:
    @tool(
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
        description=(
            "최종 도메인 판단 결과 제출 Tool. 검증된 검색 근거에서 도출한 "
            "판단, 누락 조건과 경고만 제출한다."
        ),
    )
    def submit_domain_result(
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
        runtime: ToolRuntime[None, DomainAgentState],
    ) -> Command | str:
        search_result = runtime.state.get("search_result")
        if search_result is None:
            return json.dumps(
                {"error": "Search Agent Tool을 먼저 호출해야 합니다."},
                ensure_ascii=False,
            )
        result = _build_domain_result(
            domain=domain,
            search_result=search_result,
            status=status,
            conclusion=conclusion,
            missing_conditions=missing_conditions,
            warnings=warnings,
        )
        try:
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
) -> DomainResult:
    if search_result.execution_status != "completed":
        return _failed_domain_result(
            domain,
            search_result.error or "검색을 완료하지 못했습니다.",
            execution_status=search_result.execution_status,
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
    if search_result.coverage == "none":
        status = "undetermined"
        normalized_missing = normalized_missing or ["제공 문서의 관련 근거"]
        normalized_warnings.append("제공 문서에서 관련 근거를 확인하지 못했습니다.")
    elif search_result.coverage == "partial" and status in {"determined", "not_applicable"}:
        status = "conditional"
        normalized_missing = normalized_missing or ["판단을 완결할 추가 문서 근거"]

    if status == "not_applicable":
        normalized_conclusion = _NOT_APPLICABLE_CONCLUSION
        normalized_missing = []
        normalized_warnings = []
        normalized_limitations = []

    normalized_warnings.extend(normalized_limitations)
    evidence = [_evidence_from_chunk(chunk) for chunk in search_result.selected_chunks]
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
