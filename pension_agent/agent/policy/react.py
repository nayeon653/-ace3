"""Policy 도메인의 ReAct 구현."""

from __future__ import annotations

import json
import operator
import re
from collections.abc import Mapping
from dataclasses import dataclass
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
from pension_agent.agent.search import SearchRequest, SearchResult, SearchRunner
from pension_agent.config import DomainAgentConfig

SEARCH_DOCUMENTS_TOOL_NAME = "search_documents"
SUBMIT_DOMAIN_RESULT_TOOL_NAME = "submit_domain_result"
_NOT_APPLICABLE_CONCLUSION = "이 질문에는 해당 도메인 판단이 적용되지 않습니다."
_NO_EVIDENCE_CONCLUSION = "제공 문서에서 관련 근거를 확인하지 못해 판단할 수 없습니다."
_DC_ELIGIBILITY_MISSING_CONDITION = (
    "DC 의료비 중도인출의 6개월 이상 요양·가족관계·서류 요건 확인 필요"
)
_RETIREMENT_SCHEME_MISSING_CONDITION = "DB 또는 DC 제도 유형 확인 필요"
_SERVICE_RECOGNITION_MISSING_CONDITION = "계속근로·근속 인정 여부 확인 필요"
_DB_TO_DC_ELIGIBILITY_MISSING_CONDITION = "DB→DC 전환 가능 조건 확인 필요"
_ISA_MATURITY_DATE_MISSING_CONDITION = "ISA 만기일 확인 필요"
_ISA_TRANSFER_COMPLETION_DATE_MISSING_CONDITION = "입금확인·전환완료 처리일 확인 필요"
_ISA_TRANSFER_REMAINING_REFERENCE_DATE_MISSING_CONDITION = "남은 일수 기준일 확인 필요"
_ISA_TRANSFER_ELIGIBILITY_MISSING_CONDITION = "ISA 연금전환의 나머지 적용 요건 확인 필요"


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
                "DC 의료비 중도인출의 임금 12.5% 기준 또는 ISA 연금전환 60일 기한 "
                "계산이면 의미에 맞는 Calculation Tool을 호출하고, "
                "그 외에는 최종 도메인 판단 결과 제출 Tool로 결과를 제출하세요."
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


class SinglePolicySubmitPerModelCall(AgentMiddleware[Any, Any, Any]):
    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        last_message = state.get("messages", [])[-1]
        if not isinstance(last_message, AIMessage):
            return None
        kept_submit = False
        tool_calls: list[ToolCall] = []
        for call in last_message.tool_calls:
            if call["name"] != SUBMIT_DOMAIN_RESULT_TOOL_NAME:
                tool_calls.append(call)
            elif not kept_submit:
                tool_calls.append(call)
                kept_submit = True
        if tool_calls == last_message.tool_calls:
            return None
        return {"messages": [last_message.model_copy(update={"tool_calls": tool_calls})]}

    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


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
        allowed_calls = [
            call
            for call in last_message.tool_calls
            if call["name"] in allowed and _policy_tool_call_is_allowed(call, state)
        ]
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
            *((model_concurrency,) if model_concurrency is not None else ()),
            CompletePolicyResult(),
            RequirePolicyTool(),
            SinglePolicySubmitPerModelCall(),
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
            "연금 참고자료에서 판단 목표의 근거를 검색한다. 문서 타입 필터는 시스템이 적용한다. "
            "일반 질문은 objective만 전달하고 파일명·청크 ID는 생략한다."
        ),
    )
    async def search_documents(
        objective: Annotated[
            str, Field(min_length=1, description="하나의 구체적인 근거 검색 목표")
        ],
        runtime: ToolRuntime[ExecutionContext, PolicyAgentState],
        source_file_name: Annotated[
            str | None,
            Field(
                description=(
                    "기본 생략 또는 null. 사용자 질문에서 조회 대상으로 명시한 확장자 포함 "
                    "원본 파일명만 그대로 전달한다. 주제·분류명·문서 타입·질문 전체는 금지한다. "
                    "chunk_id와 동시에 지정하지 않는다."
                )
            ),
        ] = None,
        chunk_id: Annotated[
            str | None,
            Field(
                description=(
                    "기본 생략 또는 null. 사용자 질문에서 조회 대상으로 명시한 유효한 UUID만 "
                    "그대로 전달한다. source_file_name과 동시에 지정하지 않는다."
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
                objective=objective,
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
        runtime: ToolRuntime[ExecutionContext, PolicyAgentState],
        dc_medical_eligibility_conditions_confirmed: Annotated[
            bool,
            Field(
                description=(
                    "DC 의료비 중도인출의 6개월 요양·가족관계·서류 요건이 모두 확인됐는지 여부"
                )
            ),
        ] = False,
    ) -> Command | str:
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
                question=runtime.state.get("question", ""),
                status=status,
                conclusion=conclusion,
                missing_conditions=missing_conditions,
                warnings=warnings,
                evidence_chunk_ids=evidence_chunk_ids,
                dc_medical_eligibility_conditions_confirmed=(
                    dc_medical_eligibility_conditions_confirmed
                ),
            )
            validate_domain_result(result)
        except (KeyError, TypeError, ValueError):
            return json.dumps(
                {"error": "최종 업무·제도 판단 결과가 공통 계약을 위반했습니다."},
                ensure_ascii=False,
            )
        if runtime.tool_call_id is None:
            raise ValueError("최종 Policy Agent 결과 제출 Tool 호출 ID가 없습니다.")
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


def _build_policy_result(
    *,
    search_result: SearchResult,
    calculations: list[CalculationResult],
    question: str = "",
    status: DecisionStatus,
    conclusion: str,
    missing_conditions: list[str],
    warnings: list[str],
    evidence_chunk_ids: list[str],
    dc_medical_eligibility_conditions_confirmed: bool = False,
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
        has_dc_threshold = any(
            calculation["calculator_id"] == "dc_medical_withdrawal_threshold"
            for calculation in calculations
        )
        if has_dc_threshold and not dc_medical_eligibility_conditions_confirmed:
            if status == "determined":
                status = "conditional"
            if _DC_ELIGIBILITY_MISSING_CONDITION not in normalized_missing:
                normalized_missing.append(_DC_ELIGIBILITY_MISSING_CONDITION)
    if _is_isa_transfer_question(question):
        isa_calculations = [
            calculation
            for calculation in calculations
            if calculation["calculator_id"] == "isa_transfer_deadline"
        ]
        if not isa_calculations:
            status = _conditional_unless_stronger(status)
            normalized_missing.append(_ISA_MATURITY_DATE_MISSING_CONDITION)
        else:
            isa_inputs = isa_calculations[0]["inputs"]
            if (
                _asks_isa_completion_status(question)
                and "transfer_completion_date" not in isa_inputs
            ):
                status = _conditional_unless_stronger(status)
                normalized_missing.append(_ISA_TRANSFER_COMPLETION_DATE_MISSING_CONDITION)
            if _asks_today_remaining_days(question):
                status = _conditional_unless_stronger(status)
                normalized_missing.append(_ISA_TRANSFER_REMAINING_REFERENCE_DATE_MISSING_CONDITION)
            if _asks_overall_isa_transfer_eligibility(question):
                status = _conditional_unless_stronger(status)
                normalized_missing.append(_ISA_TRANSFER_ELIGIBILITY_MISSING_CONDITION)
        normalized_missing = list(dict.fromkeys(normalized_missing))
    if not selected_chunks and status != "not_applicable":
        status = "undetermined"
        normalized_conclusion = _NO_EVIDENCE_CONCLUSION
        normalized_missing = ["제공 문서의 관련 근거"]
        normalized_warnings.append("검색된 원문 청크 중 결론에 사용한 근거가 제출되지 않았습니다.")
    elif status in {"conditional", "undetermined"}:
        normalized_missing = list(
            dict.fromkeys(
                [
                    *normalized_missing,
                    *_retirement_policy_missing_conditions(question),
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


def _retirement_policy_missing_conditions(question: str) -> list[str]:
    """미확정 #118 제도 판단에 필요한 표준 확인 조건을 반환한다."""

    conditions: list[str] = []
    if "퇴직급여" in question and "DB" not in question and "DC" not in question:
        conditions.append(_RETIREMENT_SCHEME_MISSING_CONDITION)
    if any(label in question for label in ("계속근로", "근속")) and any(
        label in question for label in ("인정", "포함")
    ):
        conditions.append(_SERVICE_RECOGNITION_MISSING_CONDITION)
    if ("DB→DC" in question or "DB에서 DC" in question) and "가능" in question:
        conditions.append(_DB_TO_DC_ELIGIBILITY_MISSING_CONDITION)
    return conditions


def _policy_tool_call_is_allowed(call: ToolCall, state: Mapping[str, Any]) -> bool:
    question = state.get("question", "")
    isa_question = isinstance(question, str) and _is_isa_transfer_question(question)
    if call["name"] == CALCULATE_ISA_TRANSFER_DEADLINE_TOOL_NAME:
        return isa_question
    if call["name"] == CALCULATE_DC_MEDICAL_WITHDRAWAL_THRESHOLD_TOOL_NAME:
        return not isa_question
    return True


def _is_isa_transfer_question(question: str) -> bool:
    if re.search(r"ISA", question, re.IGNORECASE) is None:
        return False
    if any(label in question for label in ("마감", "기한", "60일")):
        return True
    return "만기" in question and any(
        label in question for label in ("연금전환", "연금 전환", "연금계좌 전환")
    )


def _asks_isa_completion_status(question: str) -> bool:
    has_action_date = any(
        label in question
        for label in (
            "입금확인",
            "전환완료",
            "전환 완료",
            "신청일",
            "신청했",
            "입금일",
            "입금했",
            "처리했",
            "처리일",
        )
    )
    asks_status = any(label in question for label in ("기한 안", "기한 내", "늦", "충족", "가능"))
    return has_action_date and asks_status


def _asks_today_remaining_days(question: str) -> bool:
    return "오늘" in question and any(label in question for label in ("며칠", "남았", "남은"))


def _asks_overall_isa_transfer_eligibility(question: str) -> bool:
    return (
        any(label in question for label in ("연금전환 가능", "연금 전환 가능", "전환 가능 여부"))
        and "기한" not in question
        and "60일" not in question
    )


def _conditional_unless_stronger(status: DecisionStatus) -> DecisionStatus:
    return "conditional" if status == "determined" else status


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
