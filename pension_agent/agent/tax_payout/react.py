"""TaxPayout 도메인의 ReAct 구현."""

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
    CALCULATE_DEFERRED_RETIREMENT_WITHDRAWAL_TAX_TOOL_NAME,
    CALCULATE_NON_PENSION_WITHDRAWAL_TAX_TOOL_NAME,
    CALCULATE_PENSION_ANNUAL_LIMIT_INSTALLMENT_TOOL_NAME,
    CALCULATE_PENSION_INCOME_TAX_TOOL_NAME,
    CALCULATE_PENSION_PERIOD_INSTALLMENT_TOOL_NAME,
    CALCULATE_PENSION_TAX_CREDIT_TOOL_NAME,
    CALCULATE_PENSION_UNIT_INSTALLMENT_TOOL_NAME,
    CALCULATE_PENSION_WITHDRAWAL_ALLOCATION_TOOL_NAME,
    CALCULATE_PENSION_WITHDRAWAL_LIMIT_TOOL_NAME,
    CALCULATE_PENSION_WITHDRAWAL_TAX_BREAKDOWN_TOOL_NAME,
    calculation_evidence_chunk_ids,
    create_deferred_retirement_withdrawal_tax_tool,
    create_non_pension_withdrawal_tax_tool,
    create_pension_annual_limit_installment_tool,
    create_pension_income_tax_tool,
    create_pension_period_installment_tool,
    create_pension_tax_credit_tool,
    create_pension_unit_installment_tool,
    create_pension_withdrawal_allocation_tool,
    create_pension_withdrawal_limit_tool,
    create_pension_withdrawal_tax_breakdown_tool,
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
# 실제 확정 수치(숫자·%·퍼센트·금액 단위)만 매칭한다. "세율"·"한도"·"금액"·"공제액" 같은
# 화제어만으로는 매칭하지 않는다 — 조건·정성적 비교 설명까지 계산 필요로 오인하지 않기 위함.
_NUMERIC_CLAIM_PATTERN = re.compile(r"(?:\d|%|퍼센트|프로|만\s*원|억\s*원)")
_CALCULATOR_REQUIRED_CONCLUSION = "확정 수치 판단에는 결정론적 계산 Tool 결과가 필요합니다."
_CALCULATOR_REQUIRED_CONDITION = "결정론적 계산 Tool 결과"
_NUMERIC_CLAIM_UNDETERMINED_CONCLUSION = (
    "제공 근거만으로는 확정 수치를 포함한 결론을 판단할 수 없습니다."
)
_UNDETERMINED_MISSING_FALLBACK = "제공 문서의 관련 근거 또는 필수 조건"
_CONDITIONAL_MISSING_FALLBACK = "판단에 필요한 사용자 조건"
_INCOME_BASIS_MISSING_CONDITION = "총급여 또는 종합소득금액 확인 필요"
_ANNUAL_PRIVATE_PENSION_INCOME_MISSING_CONDITION = "해당 연도 사적연금 과세대상 합계 확인 필요"
_PENSION_TAX_FILING_CHOICE_MISSING_CONDITION = "종합과세 또는 16.5% 분리과세 선택 필요"
_PENSION_INCOME_TAX_CALCULATOR_ID = "pension_income_tax"
_NON_PENSION_WITHDRAWAL_TAX_CALCULATOR_ID = "non_pension_withdrawal_tax"
_PENSION_WITHDRAWAL_TAX_BREAKDOWN_CALCULATOR_ID = "pension_withdrawal_tax_breakdown"
_PENSION_TAX_COMPARISON_TOOL_NAMES = frozenset(
    {
        CALCULATE_PENSION_INCOME_TAX_TOOL_NAME,
        CALCULATE_NON_PENSION_WITHDRAWAL_TAX_TOOL_NAME,
    }
)
_NUMERIC_CLAIM_WARNING = "계산 Tool 없이 세금·금액·세율·한도를 확정하지 않았습니다."
_NUMERIC_CLAIM_REMOVED_WARNING = "근거 없이 제출된 확정 수치는 결과에서 제거했습니다."
_NUMERIC_CLAIM_RESUBMIT_INSTRUCTION = (
    "conclusion에 근거 없는 확정 수치가 있습니다. 조건·정성적 비교 질문이면 숫자 없이 다시 "
    "제출하고, 정확한 계산이 필요한 질문이면 status를 conditional로 하고 missing_conditions에 "
    "결정론적 계산 Tool 결과를 남겨 다시 제출하세요."
)


class TaxPayoutAgentState(AgentState):
    """TaxPayout ReAct의 검색·결과 상태."""

    question: NotRequired[str]
    objective: NotRequired[str]
    search_result: NotRequired[SearchResult]
    calculations: NotRequired[Annotated[list[CalculationResult], operator.add]]
    domain_result: NotRequired[DomainResult]
    numeric_resubmit_used: NotRequired[bool]


class TaxPayoutGraph(Protocol):
    async def ainvoke(
        self,
        input: dict[str, Any],
        /,
        *,
        context: ExecutionContext,
    ) -> Mapping[str, Any]: ...


@dataclass(slots=True)
class TaxPayoutReactAgent:
    """TaxPayout CompiledStateGraph를 공통 Domain 계약으로 노출한다."""

    graph: TaxPayoutGraph

    async def __call__(
        self,
        request: DomainRequest,
        *,
        deadline: float | None = None,
    ) -> DomainResult:
        if deadline is None:
            raise ValueError("TaxPayout Agent 실행 deadline이 없습니다.")
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


class CompleteTaxPayoutResult(AgentMiddleware[Any, Any, Any]):
    @hook_config(can_jump_to=["end"])
    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        return {"jump_to": "end"} if state.get("domain_result") is not None else None

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


class RequireTaxPayoutTool(AgentMiddleware[Any, Any, Any]):
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
                "연금수령한도 계산이면 calculate_pension_withdrawal_limit Tool을, "
                "올해 남은 한도의 회당 지급액이면 "
                "calculate_pension_annual_limit_installment Tool을, 현재 평가액의 전체 "
                "잔여회차별 지급액이면 calculate_pension_period_installment Tool을, "
                "잔고좌수와 기준가격의 회당 지급액이면 "
                "calculate_pension_unit_installment Tool을, "
                "연금계좌 세액공제 계산이면 calculate_pension_tax_credit Tool을 호출하고, "
                "세액공제 원금·운용수익의 연금수령 세금이면 "
                "calculate_pension_income_tax Tool을, 같은 재원의 연금외수령 세금이면 "
                "calculate_non_pension_withdrawal_tax Tool을 호출하세요. 이연퇴직소득 재원의 "
                "연금·연금외수령 세금이면 calculate_deferred_retirement_withdrawal_tax Tool을 "
                "호출하고 두 재원을 혼용하지 마세요. 재원별 인출 배분만 필요하거나 세금 "
                "조건이 부족하면 calculate_pension_withdrawal_allocation Tool을, 재원별 세금과 "
                "세후액 조건이 모두 확인되면 calculate_pension_withdrawal_tax_breakdown Tool을 "
                "둘 중 하나만 호출하세요. "
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


class SingleTaxPayoutSubmitPerModelCall(AgentMiddleware[Any, Any, Any]):
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


class EnforceTaxPayoutToolSequence(AgentMiddleware[Any, Any, Any]):
    """검색·계산·결과 제출 순서에서 현재 허용된 Tool 호출만 남긴다."""

    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        last_message = state.get("messages", [])[-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return None
        allowed_tools: tuple[str, ...]
        if state.get("search_result") is None:
            # not_applicable 제출은 search_documents 없이도 허용해야 한다 — 도메인
            # 외 질문에는 검색을 강제하지 않는다. status 검증(search_result 필수)은
            # submit_domain_result 안에서 계속 수행한다.
            allowed_tools = (SEARCH_DOCUMENTS_TOOL_NAME, SUBMIT_DOMAIN_RESULT_TOOL_NAME)
        elif state.get("calculations"):
            completed_ids = {calculation["calculator_id"] for calculation in state["calculations"]}
            completed_comparison_ids = completed_ids & {
                _PENSION_INCOME_TAX_CALCULATOR_ID,
                _NON_PENSION_WITHDRAWAL_TAX_CALCULATOR_ID,
            }
            if completed_comparison_ids == {_PENSION_INCOME_TAX_CALCULATOR_ID}:
                allowed_tools = (
                    CALCULATE_NON_PENSION_WITHDRAWAL_TAX_TOOL_NAME,
                    SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                )
            elif completed_comparison_ids == {_NON_PENSION_WITHDRAWAL_TAX_CALCULATOR_ID}:
                allowed_tools = (
                    CALCULATE_PENSION_INCOME_TAX_TOOL_NAME,
                    SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                )
            else:
                allowed_tools = (SUBMIT_DOMAIN_RESULT_TOOL_NAME,)
        else:
            allowed_tools = (
                CALCULATE_PENSION_WITHDRAWAL_LIMIT_TOOL_NAME,
                CALCULATE_PENSION_ANNUAL_LIMIT_INSTALLMENT_TOOL_NAME,
                CALCULATE_PENSION_PERIOD_INSTALLMENT_TOOL_NAME,
                CALCULATE_PENSION_UNIT_INSTALLMENT_TOOL_NAME,
                CALCULATE_PENSION_TAX_CREDIT_TOOL_NAME,
                CALCULATE_PENSION_INCOME_TAX_TOOL_NAME,
                CALCULATE_NON_PENSION_WITHDRAWAL_TAX_TOOL_NAME,
                CALCULATE_DEFERRED_RETIREMENT_WITHDRAWAL_TAX_TOOL_NAME,
                CALCULATE_PENSION_WITHDRAWAL_ALLOCATION_TOOL_NAME,
                CALCULATE_PENSION_WITHDRAWAL_TAX_BREAKDOWN_TOOL_NAME,
                SUBMIT_DOMAIN_RESULT_TOOL_NAME,
            )
        allowed_calls = [call for call in last_message.tool_calls if call["name"] in allowed_tools]
        calculation_calls = [
            call for call in allowed_calls if call["name"] != SUBMIT_DOMAIN_RESULT_TOOL_NAME
        ]
        if {call["name"] for call in calculation_calls} == _PENSION_TAX_COMPARISON_TOOL_NAMES:
            kept_calls = calculation_calls
        elif calculation_calls:
            kept_calls = calculation_calls[:1]
        else:
            kept_calls = allowed_calls[:1]
        if kept_calls == last_message.tool_calls:
            return None
        return {"messages": [last_message.model_copy(update={"tool_calls": kept_calls})]}

    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


class TaxPayoutModelCallLimit(ModelCallLimitMiddleware):
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
            "messages": [AIMessage(content="TaxPayout Agent 호출 한도에 도달했습니다.")],
        }

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


def create_tax_payout_react_agent(
    *,
    model: BaseChatModel,
    search_service: SearchRunner,
    system_prompt: str,
    config: DomainAgentConfig,
    model_concurrency: ModelConcurrencyMiddleware | None,
) -> TaxPayoutReactAgent:
    """TaxPayout 패키지가 소유하는 ReAct graph를 만든다."""

    calculation_tool = create_pension_withdrawal_limit_tool()
    annual_limit_installment_tool = create_pension_annual_limit_installment_tool()
    period_installment_tool = create_pension_period_installment_tool()
    unit_installment_tool = create_pension_unit_installment_tool()
    tax_credit_tool = create_pension_tax_credit_tool()
    pension_income_tax_tool = create_pension_income_tax_tool()
    non_pension_withdrawal_tax_tool = create_non_pension_withdrawal_tax_tool()
    deferred_retirement_tax_tool = create_deferred_retirement_withdrawal_tax_tool()
    withdrawal_allocation_tool = create_pension_withdrawal_allocation_tool()
    withdrawal_tax_breakdown_tool = create_pension_withdrawal_tax_breakdown_tool()
    graph = create_agent(
        model=model,
        tools=(
            _create_tax_payout_search_tool(search_service),
            calculation_tool,
            annual_limit_installment_tool,
            period_installment_tool,
            unit_installment_tool,
            tax_credit_tool,
            pension_income_tax_tool,
            non_pension_withdrawal_tax_tool,
            deferred_retirement_tax_tool,
            withdrawal_allocation_tool,
            withdrawal_tax_breakdown_tool,
            _create_tax_payout_result_tool(),
        ),
        system_prompt=system_prompt,
        state_schema=TaxPayoutAgentState,
        context_schema=ExecutionContext,
        middleware=(
            *((model_concurrency,) if model_concurrency is not None else ()),
            CompleteTaxPayoutResult(),
            RequireTaxPayoutTool(),
            SingleTaxPayoutSubmitPerModelCall(),
            TaxPayoutModelCallLimit(max_model_calls=config.max_model_calls),
            ToolCallLimitMiddleware(
                tool_name=SEARCH_DOCUMENTS_TOOL_NAME,
                run_limit=config.max_search_calls,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=calculation_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=annual_limit_installment_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=period_installment_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=unit_installment_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=tax_credit_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=pension_income_tax_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=non_pension_withdrawal_tax_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=deferred_retirement_tax_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=withdrawal_allocation_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=withdrawal_tax_breakdown_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                run_limit=config.max_submit_calls,
                exit_behavior="continue",
            ),
            EnforceTaxPayoutToolSequence(),
        ),
        name="tax_payout_agent",
    )
    return TaxPayoutReactAgent(graph=cast(TaxPayoutGraph, graph))


def _create_tax_payout_search_tool(search_service: SearchRunner) -> Any:
    @tool(
        SEARCH_DOCUMENTS_TOOL_NAME,
        description="하나의 구체적인 판단 목표에 필요한 제공 문서 근거를 검색한다.",
    )
    async def search_documents(
        objective: Annotated[
            str, Field(min_length=1, description="하나의 구체적인 근거 검색 목표")
        ],
        runtime: ToolRuntime[ExecutionContext, TaxPayoutAgentState],
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
                permission=Permission.TAX_PAYOUT,
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


def _create_tax_payout_result_tool() -> Any:
    @tool(
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
        description=(
            "최종 세제·수령 판단 결과 제출 Tool. 검증된 검색 근거에서 도출한 "
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
        runtime: ToolRuntime[ExecutionContext, TaxPayoutAgentState],
    ) -> Command | str:
        if runtime.tool_call_id is None:
            raise ValueError("최종 TaxPayout Agent 결과 제출 Tool 호출 ID가 없습니다.")
        if status == "not_applicable":
            return Command(
                update={
                    "domain_result": _not_applicable_tax_payout_result(),
                    "messages": [
                        ToolMessage(
                            content=json.dumps({"status": "accepted"}, ensure_ascii=False),
                            tool_call_id=runtime.tool_call_id,
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
        # calculations가 있으면 conclusion은 곧 검증된 Python 요약으로 교체되므로
        # 재제출 요청은 계산 Tool 없이 숫자를 직접 제출한 경우에만 의미가 있다.
        if (
            not runtime.state.get("calculations")
            and _NUMERIC_CLAIM_PATTERN.search(conclusion.strip())
            and not runtime.state.get("numeric_resubmit_used", False)
        ):
            return Command(
                update={
                    "numeric_resubmit_used": True,
                    "messages": [
                        ToolMessage(
                            content=json.dumps(
                                {"error": _NUMERIC_CLAIM_RESUBMIT_INSTRUCTION},
                                ensure_ascii=False,
                            ),
                            tool_call_id=runtime.tool_call_id,
                            name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                        )
                    ],
                }
            )
        try:
            result = _build_tax_payout_result(
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
                {"error": "최종 세제·수령 판단 결과가 공통 계약을 위반했습니다."},
                ensure_ascii=False,
            )
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


def _not_applicable_tax_payout_result() -> DomainResult:
    return {
        "domain": "tax_payout",
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


def _build_tax_payout_result(
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
            "tax_payout",
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
        normalized_conclusion = "검증된 Python 계산 결과:\n" + format_calculation_summary(
            calculations
        )
        normalized_warnings = [
            value for value in normalized_warnings if not _NUMERIC_CLAIM_PATTERN.search(value)
        ]
        normalized_warnings.extend(
            warning for calculation in calculations for warning in calculation["warnings"]
        )
        if _has_unconditioned_pension_tax_credit_rate_scenarios(calculations):
            status = "conditional"
            if _INCOME_BASIS_MISSING_CONDITION not in normalized_missing:
                normalized_missing = [*normalized_missing, _INCOME_BASIS_MISSING_CONDITION]
        if _has_unknown_ordinary_pension_income_threshold(calculations):
            status = "conditional"
            if _ANNUAL_PRIVATE_PENSION_INCOME_MISSING_CONDITION not in normalized_missing:
                normalized_missing = [
                    *normalized_missing,
                    _ANNUAL_PRIVATE_PENSION_INCOME_MISSING_CONDITION,
                ]
        if _requires_pension_tax_filing_choice(calculations):
            status = "conditional"
            if _PENSION_TAX_FILING_CHOICE_MISSING_CONDITION not in normalized_missing:
                normalized_missing = [
                    *normalized_missing,
                    _PENSION_TAX_FILING_CHOICE_MISSING_CONDITION,
                ]
        if _has_unresolved_withdrawal_breakdown_tax(calculations):
            status = "conditional"
            if _ANNUAL_PRIVATE_PENSION_INCOME_MISSING_CONDITION not in normalized_missing:
                normalized_missing = [
                    *normalized_missing,
                    _ANNUAL_PRIVATE_PENSION_INCOME_MISSING_CONDITION,
                ]
        if _has_withdrawal_breakdown_separate_tax_option(calculations):
            status = "conditional"
            if _PENSION_TAX_FILING_CHOICE_MISSING_CONDITION not in normalized_missing:
                normalized_missing = [
                    *normalized_missing,
                    _PENSION_TAX_FILING_CHOICE_MISSING_CONDITION,
                ]
    elif status != "not_applicable":
        status, normalized_conclusion, normalized_missing, normalized_warnings = (
            _apply_numeric_claim_guard(
                status=status,
                conclusion=normalized_conclusion,
                missing_conditions=normalized_missing,
                warnings=normalized_warnings,
            )
        )
    if not selected_chunks and status != "not_applicable":
        status = "undetermined"
        normalized_conclusion = _NO_EVIDENCE_CONCLUSION
        normalized_missing = ["제공 문서의 관련 근거"]
        normalized_warnings.append("검색된 원문 청크 중 결론에 사용한 근거가 제출되지 않았습니다.")
        calculations = []
    if status == "not_applicable":
        normalized_conclusion = _NOT_APPLICABLE_CONCLUSION
        normalized_missing = []
        normalized_warnings = []
        selected_chunks = []
        calculations = []
    return {
        "domain": "tax_payout",
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


def _has_unconditioned_pension_tax_credit_rate_scenarios(
    calculations: list[CalculationResult],
) -> bool:
    """소득 기준 없이 두 세율 시나리오만 반환된 세액공제 계산이 있는지 확인한다."""

    return any(
        calculation["calculator_id"] == "pension_tax_credit"
        and "income_basis" not in calculation["inputs"]
        and "income_amount_krw" not in calculation["inputs"]
        and "lower_income_rate_percent" in calculation["outputs"]
        and "other_income_rate_percent" in calculation["outputs"]
        for calculation in calculations
    )


def _has_unknown_ordinary_pension_income_threshold(
    calculations: list[CalculationResult],
) -> bool:
    return any(
        calculation["calculator_id"] == _PENSION_INCOME_TAX_CALCULATOR_ID
        and calculation["inputs"].get("pension_treatment") == "ordinary"
        and "annual_private_pension_taxable_income_krw" not in calculation["inputs"]
        and calculation["outputs"].get("annual_threshold_status") == "unknown"
        for calculation in calculations
    )


def _requires_pension_tax_filing_choice(
    calculations: list[CalculationResult],
) -> bool:
    return any(
        calculation["calculator_id"] == _PENSION_INCOME_TAX_CALCULATOR_ID
        and calculation["outputs"].get("filing_choice_required") is True
        for calculation in calculations
    )


def _has_unresolved_withdrawal_breakdown_tax(
    calculations: list[CalculationResult],
) -> bool:
    return any(
        calculation["calculator_id"] == _PENSION_WITHDRAWAL_TAX_BREAKDOWN_CALCULATOR_ID
        and "annual_private_pension_taxable_income_krw" not in calculation["inputs"]
        and (
            calculation["outputs"].get("current_withdrawal_tax_krw") is None
            or calculation["outputs"].get("current_withdrawal_after_tax_krw") is None
        )
        for calculation in calculations
    )


def _has_withdrawal_breakdown_separate_tax_option(
    calculations: list[CalculationResult],
) -> bool:
    return any(
        calculation["calculator_id"] == _PENSION_WITHDRAWAL_TAX_BREAKDOWN_CALCULATOR_ID
        and "annual_private_pension_separate_tax_option_tax_krw" in calculation["outputs"]
        for calculation in calculations
    )


def _apply_numeric_claim_guard(
    *,
    status: DecisionStatus,
    conclusion: str,
    missing_conditions: list[str],
    warnings: list[str],
) -> tuple[DecisionStatus, str, list[str], list[str]]:
    """근거 없는 확정 수치를 필드별로 검사해 제거한다.

    conclusion·missing_conditions·warnings를 각각 검사하고, 숫자가 없는 필드는
    그대로 보존한다 — warning이나 missing_conditions에만 숫자가 있다는 이유로
    정상 conclusion과 status까지 바꾸지 않는다. `undetermined`(근거 부족)는
    어떤 경우에도 `conditional`(계산 필요)로 승격하지 않는다 — "근거가
    부족하다"와 "계산만 하면 된다"는 의미가 다르다.
    """

    conclusion_has_claim = bool(_NUMERIC_CLAIM_PATTERN.search(conclusion))
    kept_missing = [
        value for value in missing_conditions if not _NUMERIC_CLAIM_PATTERN.search(value)
    ]
    kept_warnings = [value for value in warnings if not _NUMERIC_CLAIM_PATTERN.search(value)]
    if not (
        conclusion_has_claim
        or len(kept_missing) != len(missing_conditions)
        or len(kept_warnings) != len(warnings)
    ):
        return status, conclusion, missing_conditions, warnings

    if status == "undetermined":
        return (
            status,
            _NUMERIC_CLAIM_UNDETERMINED_CONCLUSION if conclusion_has_claim else conclusion,
            kept_missing or [_UNDETERMINED_MISSING_FALLBACK],
            [*kept_warnings, _NUMERIC_CLAIM_REMOVED_WARNING],
        )

    if conclusion_has_claim:
        return (
            "conditional",
            _CALCULATOR_REQUIRED_CONCLUSION,
            [_CALCULATOR_REQUIRED_CONDITION],
            [*kept_warnings, _NUMERIC_CLAIM_WARNING],
        )

    result_missing = kept_missing
    if status == "conditional" and not result_missing:
        result_missing = [_CONDITIONAL_MISSING_FALLBACK]
    return status, conclusion, result_missing, [*kept_warnings, _NUMERIC_CLAIM_REMOVED_WARNING]


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
            "tax_payout",
            search_result.error or "검색을 완료하지 못했습니다.",
            execution_status=search_result.execution_status,
        )
    if search_result.retrieved_chunks:
        return None
    return {
        "domain": "tax_payout",
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


def _hint_is_present_in_question(state: TaxPayoutAgentState, hint: str) -> bool:
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
