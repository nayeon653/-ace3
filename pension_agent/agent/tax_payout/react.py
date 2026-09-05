"""TaxPayout 도메인의 ReAct 구현."""

from __future__ import annotations

import json
import operator
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, NotRequired, Protocol, cast
from uuid import UUID

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
from pydantic import Field, ValidationError

from pension_agent.agent.calculation import (
    CALCULATE_DB_RETIREMENT_BENEFIT_TOOL_NAME,
    CALCULATE_DB_TO_DC_TRANSFER_AMOUNT_TOOL_NAME,
    CALCULATE_DC_MINIMUM_EMPLOYER_CONTRIBUTION_TOOL_NAME,
    CALCULATE_DC_RETIREMENT_BENEFIT_TOOL_NAME,
    CALCULATE_DEFERRED_RETIREMENT_WITHDRAWAL_TAX_TOOL_NAME,
    CALCULATE_EXECUTIVE_RETIREMENT_INCOME_LIMIT_TOOL_NAME,
    CALCULATE_MEDICAL_CARE_WITHDRAWAL_TAX_BREAKDOWN_TOOL_NAME,
    CALCULATE_MEDICAL_CARE_WITHDRAWAL_TAX_LIMIT_TOOL_NAME,
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
    create_db_retirement_benefit_tool,
    create_db_to_dc_transfer_amount_tool,
    create_dc_minimum_employer_contribution_tool,
    create_dc_retirement_benefit_tool,
    create_deferred_retirement_withdrawal_tax_tool,
    create_executive_retirement_income_limit_tool,
    create_medical_care_withdrawal_tax_breakdown_tool,
    create_medical_care_withdrawal_tax_limit_tool,
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
from pension_agent.agent.search import (
    SearchRequest,
    SearchResult,
    SearchRunner,
    combine_search_objective,
)
from pension_agent.agent.tax_payout.statutory_facts import (
    candidate_fact_hints,
    resolve_statutory_facts,
)
from pension_agent.config import DomainAgentConfig

SEARCH_DOCUMENTS_TOOL_NAME = "search_documents"
SUBMIT_DOMAIN_RESULT_TOOL_NAME = "submit_domain_result"
_NOT_APPLICABLE_CONCLUSION = "이 질문에는 해당 도메인 판단이 적용되지 않습니다."
_NO_EVIDENCE_CONCLUSION = "제공 문서에서 관련 근거를 확인하지 못해 판단할 수 없습니다."
_INCOME_BASIS_MISSING_CONDITION = "총급여 또는 종합소득금액 확인 필요"
_ANNUAL_PRIVATE_PENSION_INCOME_MISSING_CONDITION = "해당 연도 사적연금 과세대상 합계 확인 필요"
_PENSION_TAX_FILING_CHOICE_MISSING_CONDITION = "과세 방식 선택 필요"
_PENSION_INCOME_TAX_CALCULATOR_ID = "pension_income_tax"
_PENSION_WITHDRAWAL_TAX_BREAKDOWN_CALCULATOR_ID = "pension_withdrawal_tax_breakdown"
_MEDICAL_CARE_TAX_BREAKDOWN_CALCULATOR_ID = "medical_care_withdrawal_tax_breakdown"
_MEDICAL_CARE_EXCESS_MISSING_CONDITION = "초과액의 재원 및 연금수령·연금외수령 구분 확인 필요"
_CALL_BUDGET_EXHAUSTED_CONCLUSION = "모델 호출 한도 내에 최종 결론을 확정하지 못했습니다."
_CALL_BUDGET_MISSING_CONDITION = "모델 호출 한도 내 최종 결론 확정"
_CALL_BUDGET_EXHAUSTED_WARNING = (
    "모델 호출 한도 내에 최종 판단을 제출하지 못해 안전한 결과로 종료했습니다."
)

_CALCULATION_TOOL_NAMES = (
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
    CALCULATE_MEDICAL_CARE_WITHDRAWAL_TAX_LIMIT_TOOL_NAME,
    CALCULATE_MEDICAL_CARE_WITHDRAWAL_TAX_BREAKDOWN_TOOL_NAME,
    CALCULATE_DB_RETIREMENT_BENEFIT_TOOL_NAME,
    CALCULATE_DC_MINIMUM_EMPLOYER_CONTRIBUTION_TOOL_NAME,
    CALCULATE_DC_RETIREMENT_BENEFIT_TOOL_NAME,
    CALCULATE_DB_TO_DC_TRANSFER_AMOUNT_TOOL_NAME,
    CALCULATE_EXECUTIVE_RETIREMENT_INCOME_LIMIT_TOOL_NAME,
)


class TaxPayoutAgentState(AgentState):
    """TaxPayout ReAct의 검색·결과 상태."""

    question: NotRequired[str]
    objective: NotRequired[str]
    search_result: NotRequired[SearchResult]
    calculations: NotRequired[Annotated[list[CalculationResult], operator.add]]
    domain_result: NotRequired[DomainResult]


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
        if state.get("search_result") is not None:
            instruction = (
                "추가 산출이 필요하면 적합한 Calculation Tool 하나를 호출하고, "
                "그렇지 않으면 근거 기반 판단을 submit_domain_result Tool로 제출하세요."
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


class EnforceTaxPayoutToolSequence(AgentMiddleware[Any, Any, Any]):
    """질문 문구를 해석하지 않고 검색·계산·제출 단계와 남은 호출 예산만으로 다음 Tool을 제한한다."""

    def __init__(self, *, max_model_calls: int) -> None:
        super().__init__()
        self._max_model_calls = max_model_calls

    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        last_message = state.get("messages", [])[-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return None
        allowed_tools: tuple[str, ...]
        if state.get("search_result") is None:
            allowed_tools = (SEARCH_DOCUMENTS_TOOL_NAME, SUBMIT_DOMAIN_RESULT_TOOL_NAME)
        elif state.get("run_model_call_count", 0) >= self._max_model_calls - 1:
            # 마지막으로 허용된 모델 호출이다. 추가 계산 시도로 예산을 낭비하지 않고
            # 반드시 submit_domain_result로 수렴하도록 좁힌다.
            allowed_tools = (SUBMIT_DOMAIN_RESULT_TOOL_NAME,)
        else:
            allowed_tools = (*_CALCULATION_TOOL_NAMES, SUBMIT_DOMAIN_RESULT_TOOL_NAME)
        allowed_calls = [call for call in last_message.tool_calls if call["name"] in allowed_tools]
        calculation_calls = [
            call for call in allowed_calls if call["name"] != SUBMIT_DOMAIN_RESULT_TOOL_NAME
        ]
        kept_calls = calculation_calls[:1] if calculation_calls else allowed_calls[:1]
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
            "domain_result": _safe_terminal_tax_payout_result(state),
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
    medical_care_limit_tool = create_medical_care_withdrawal_tax_limit_tool()
    medical_care_breakdown_tool = create_medical_care_withdrawal_tax_breakdown_tool()
    db_retirement_benefit_tool = create_db_retirement_benefit_tool()
    dc_minimum_contribution_tool = create_dc_minimum_employer_contribution_tool()
    dc_retirement_benefit_tool = create_dc_retirement_benefit_tool()
    db_to_dc_transfer_tool = create_db_to_dc_transfer_amount_tool()
    executive_retirement_limit_tool = create_executive_retirement_income_limit_tool()
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
            medical_care_limit_tool,
            medical_care_breakdown_tool,
            db_retirement_benefit_tool,
            dc_minimum_contribution_tool,
            dc_retirement_benefit_tool,
            db_to_dc_transfer_tool,
            executive_retirement_limit_tool,
            _create_tax_payout_result_tool(),
        ),
        system_prompt=system_prompt,
        state_schema=TaxPayoutAgentState,
        context_schema=ExecutionContext,
        middleware=(
            *((model_concurrency,) if model_concurrency is not None else ()),
            CompleteTaxPayoutResult(),
            RequireTaxPayoutTool(),
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
                tool_name=medical_care_limit_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=medical_care_breakdown_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=db_retirement_benefit_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=dc_minimum_contribution_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=dc_retirement_benefit_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=db_to_dc_transfer_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=executive_retirement_limit_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                run_limit=config.max_submit_calls,
                exit_behavior="continue",
            ),
            EnforceTaxPayoutToolSequence(max_model_calls=config.max_model_calls),
        ),
        name="tax_payout_agent",
    )
    return TaxPayoutReactAgent(graph=cast(TaxPayoutGraph, graph))


def _create_tax_payout_search_tool(search_service: SearchRunner) -> Any:
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
        runtime: ToolRuntime[ExecutionContext, TaxPayoutAgentState],
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
                permission=Permission.TAX_PAYOUT,
                deadline=runtime.context.deadline,
            )
        update: dict[str, Any] = {
            "search_result": result,
            "messages": [
                ToolMessage(
                    content=_search_result_message_content(result),
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


def _search_result_message_content(result: SearchResult) -> str:
    """검색 결과 JSON 뒤에, 검색된 청크와 같은 출처의 법정 수치 fact_id 후보를 덧붙인다.

    fact_id와 원문 발췌만 보여준다 — value·role·scope·canonical 문장은 절대
    포함하지 않는다. registry 전체가 아니라 이번 검색으로 실제로 찾은 청크와
    연결된 fact만 후보로 좁힌다.
    """

    payload = result.model_dump_json()
    candidates = candidate_fact_hints(result.retrieved_chunks)
    if not candidates:
        return payload
    candidate_lines = "\n".join(
        f'- fact_id={candidate["fact_id"]}\n  원문 발췌: "{candidate["source_excerpt"]}"'
        for candidate in candidates
    )
    return f"{payload}\n\n[검색된 근거와 연결된 법정 수치 fact_id 후보]\n{candidate_lines}"


def _create_tax_payout_result_tool() -> Any:
    @tool(
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
        description=(
            "최종 세제·수령 판단 결과 제출 Tool. 검증된 검색 근거에서 도출한 "
            "판단, 누락 조건과 경고만 제출한다. 질문에 직접 답하고 실제 사용한 "
            "근거 청크만 연결한다."
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
                    "검색 근거와 계산 결과의 적용 대상·조건을 보존해 질문에 직접 답하는 "
                    "스스로 완결된 결론"
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
        selected_fact_ids: Annotated[
            list[str],
            Field(
                default_factory=list,
                description=(
                    "결론에 인용한 법정 수치가 있으면, search_documents 결과에 제시된 "
                    "fact_id candidate 중 실제로 필요한 것만 선택한다. 값·단위·세율· "
                    "한도 숫자는 여기에도 conclusion에도 직접 쓰지 않는다 — fact_id만 "
                    "고르면 실제 문장은 시스템이 채운다. 후보에 없는 fact_id는 만들지 "
                    "않는다. 법정 수치를 인용하지 않으면 빈 목록으로 둔다."
                ),
            ),
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
        try:
            result = _build_tax_payout_result(
                search_result=search_result,
                calculations=list(runtime.state.get("calculations", [])),
                question=runtime.state.get("question", ""),
                objective=runtime.state.get("objective", ""),
                status=status,
                conclusion=conclusion,
                missing_conditions=missing_conditions,
                warnings=warnings,
                evidence_chunk_ids=evidence_chunk_ids,
                selected_fact_ids=selected_fact_ids,
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
    question: str = "",
    objective: str = "",
    status: DecisionStatus,
    conclusion: str,
    missing_conditions: list[str],
    warnings: list[str],
    evidence_chunk_ids: list[str],
    selected_fact_ids: list[str] | None = None,
) -> DomainResult:
    del question, objective
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
    verified_numeric_statements = resolve_statutory_facts(selected_fact_ids or [], selected_chunks)
    normalized_missing = [value.strip() for value in missing_conditions if value.strip()]
    normalized_warnings = [value.strip() for value in warnings if value.strip()]
    normalized_warnings.extend(search_result.limitations)
    normalized_conclusion = conclusion.strip()
    if calculations:
        normalized_conclusion = (
            "검증된 Python 계산 결과:\n"
            + format_calculation_summary(calculations)
            + "\n근거 기반 설명:\n"
            + normalized_conclusion
        )
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
        if _has_unresolved_medical_care_excess(calculations):
            if status == "determined":
                status = "conditional"
            if _MEDICAL_CARE_EXCESS_MISSING_CONDITION not in normalized_missing:
                normalized_missing.append(_MEDICAL_CARE_EXCESS_MISSING_CONDITION)
    if not selected_chunks and status != "not_applicable":
        status = "undetermined"
        normalized_conclusion = _NO_EVIDENCE_CONCLUSION
        normalized_missing = ["제공 문서의 관련 근거"]
        normalized_warnings.append("검색된 원문 청크 중 결론에 사용한 근거가 제출되지 않았습니다.")
        calculations = []
        verified_numeric_statements = []
    if status == "not_applicable":
        normalized_conclusion = _NOT_APPLICABLE_CONCLUSION
        normalized_missing = []
        normalized_warnings = []
        selected_chunks = []
        calculations = []
        verified_numeric_statements = []
    result: DomainResult = {
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
    if verified_numeric_statements:
        result["verified_numeric_statements"] = verified_numeric_statements
    return result


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


def _has_unresolved_medical_care_excess(calculations: list[CalculationResult]) -> bool:
    for calculation in calculations:
        if calculation["calculator_id"] != _MEDICAL_CARE_TAX_BREAKDOWN_CALCULATOR_ID:
            continue
        try:
            excess = Decimal(str(calculation["outputs"].get("excess_amount_krw")))
        except InvalidOperation:
            continue
        if excess > 0 and (
            calculation["outputs"].get("current_withdrawal_tax_krw") is None
            or calculation["outputs"].get("current_withdrawal_after_tax_krw") is None
        ):
            return True
    return False


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


def _safe_terminal_tax_payout_result(state: Any) -> DomainResult:
    """모델 호출 한도 도달 시 현재 state만으로 안전한 terminal DomainResult를 만든다.

    모델이 스스로 conclusion을 완결하지 못했으므로 새 서술이나 수치를 만들지 않고,
    이미 검증된 search_result·calculations만 그대로 보존해 conditional/undetermined로
    제출한다. `verified_numeric_statements`는 여기서 새로 만들지 않는다 —
    submit_domain_result가 성공해야만 fact가 검증되므로, 이 경로에 도달했다는
    것은 그런 성공한 제출이 없었다는 뜻이다(있었다면 CompleteTaxPayoutResult가
    이미 종료했다).
    """

    search_result = state.get("search_result")
    if search_result is None:
        return failed_domain_result(
            "tax_payout", "TaxPayout Agent가 모델 호출 한도 내에 검색을 완료하지 못했습니다."
        )
    no_evidence_result = _terminal_result_from_search(search_result)
    if no_evidence_result is not None:
        return no_evidence_result
    calculations = list(state.get("calculations", []))
    try:
        selected_chunks = _select_evidence(
            search_result, calculation_evidence_chunk_ids(calculations)
        )
    except ValueError:
        selected_chunks = []
        calculations = []
    warnings = [*search_result.limitations, _CALL_BUDGET_EXHAUSTED_WARNING]
    status: DecisionStatus
    if calculations:
        conclusion = "검증된 Python 계산 결과:\n" + format_calculation_summary(calculations)
        warnings.extend(
            warning for calculation in calculations for warning in calculation["warnings"]
        )
        status = "conditional"
    else:
        conclusion = _CALL_BUDGET_EXHAUSTED_CONCLUSION
        status = "undetermined"
    return {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": status,
            "conclusion": conclusion,
            "missing_conditions": [_CALL_BUDGET_MISSING_CONDITION],
        },
        "evidence": [_evidence_from_chunk(chunk) for chunk in selected_chunks],
        "calculations": calculations,
        "warnings": list(dict.fromkeys(warnings)),
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
