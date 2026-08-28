"""Calculation Service를 계산기별 명시적 LangChain Tool로 노출한다."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Annotated, Any, Literal, cast

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool
from langgraph.types import Command
from pydantic import Field

from pension_agent.agent.calculation.input_sources import validated_input_sources
from pension_agent.agent.contracts import CalculationInputSource, CalculationResult
from pension_agent.agent.execution import ExecutionContext
from pension_agent.rules import CalculationError, CalculationRequest, calculate

CALCULATE_PENSION_WITHDRAWAL_LIMIT_TOOL_NAME = "calculate_pension_withdrawal_limit"
CALCULATE_PENSION_TAX_CREDIT_TOOL_NAME = "calculate_pension_tax_credit"
CALCULATE_FUND_STANDARD_PRICE_TOOL_NAME = "calculate_fund_standard_price"
CALCULATE_FUND_VAR_RISK_TOOL_NAME = "calculate_fund_var_risk"


def create_pension_withdrawal_limit_tool() -> BaseTool:
    """Tax/Payout Agent용 연금수령한도 계산 Tool을 만든다."""

    @tool(
        CALCULATE_PENSION_WITHDRAWAL_LIMIT_TOOL_NAME,
        description=(
            "연금계좌 평가액과 연금수령연차로 연금수령한도를 계산한다. "
            "사용자 질문 또는 검증된 검색 근거에 명시된 입력만 사용한다."
        ),
    )
    async def calculate_pension_withdrawal_limit(
        account_valuation_krw: Annotated[
            Decimal,
            Field(ge=0, description="연금계좌 평가액(원)"),
        ],
        pension_year: Annotated[
            int,
            Field(ge=1, le=10, description="1부터 10까지의 연금수령연차"),
        ],
        account_valuation_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="평가액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        pension_year_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="수령연차 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        return _execute_calculation(
            calculator_id="pension_withdrawal_limit",
            inputs={
                "account_valuation_krw": account_valuation_krw,
                "pension_year": pension_year,
            },
            input_sources={
                "account_valuation_krw": account_valuation_source,
                "pension_year": pension_year_source,
            },
            tool_name=CALCULATE_PENSION_WITHDRAWAL_LIMIT_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_pension_withdrawal_limit


def create_pension_tax_credit_tool() -> BaseTool:
    """Tax/Payout Agent용 연금계좌 세액공제 계산 Tool을 만든다."""

    @tool(
        CALCULATE_PENSION_TAX_CREDIT_TOOL_NAME,
        description=(
            "연금저축·퇴직연금 순납입액과 ISA 만기자금 전환, 소득 정보로 세액공제 "
            "대상액과 세액을 계산한다. 사용자 질문 또는 검증된 검색 근거에 명시된 "
            "입력만 사용하며, 선택 입력은 값과 출처를 함께 전달하거나 함께 생략한다."
        ),
    )
    async def calculate_pension_tax_credit(
        pension_savings_net_contribution_krw: Annotated[
            Decimal,
            Field(ge=0, description="연금저축 순납입액(원)"),
        ],
        retirement_pension_net_contribution_krw: Annotated[
            Decimal,
            Field(ge=0, description="퇴직연금 순납입액(원)"),
        ],
        pension_savings_net_contribution_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="연금저축 순납입액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        retirement_pension_net_contribution_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="퇴직연금 순납입액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
        pension_savings_isa_transfer_krw: Annotated[
            Decimal | None,
            Field(ge=0, description="연금저축 ISA 만기자금 전환액(원)"),
        ] = None,
        pension_savings_isa_transfer_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="연금저축 ISA 전환액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ] = None,
        retirement_pension_isa_transfer_krw: Annotated[
            Decimal | None,
            Field(ge=0, description="퇴직연금 ISA 만기자금 전환액(원)"),
        ] = None,
        retirement_pension_isa_transfer_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="퇴직연금 ISA 전환액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ] = None,
        prior_same_maturity_isa_extra_eligible_contribution_used_krw: Annotated[
            Decimal | None,
            Field(ge=0, le=3_000_000, description="같은 만기자금의 전년도 추가 공제대상액 사용분(원)"),
        ] = None,
        prior_same_maturity_isa_extra_eligible_contribution_used_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="전년도 추가 공제대상액 사용분 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ] = None,
        income_basis: Annotated[
            Literal["salary", "comprehensive_income"] | None,
            Field(description="소득 기준. 총급여 또는 종합소득금액"),
        ] = None,
        income_basis_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="소득 기준 명칭이 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ] = None,
        income_amount_krw: Annotated[
            Decimal | None,
            Field(ge=0, description="income_basis에 대응하는 소득금액(원)"),
        ] = None,
        income_amount_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="소득금액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ] = None,
        remaining_tax_before_pension_credit_krw: Annotated[
            Decimal | None,
            Field(ge=0, description="연금계좌 세액공제 적용 직전 잔여 산출세액(원)"),
        ] = None,
        remaining_tax_before_pension_credit_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="잔여 산출세액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ] = None,
    ) -> Command | str:
        optional_entries: tuple[tuple[str, Any, str | None], ...] = (
            (
                "pension_savings_isa_transfer_krw",
                pension_savings_isa_transfer_krw,
                pension_savings_isa_transfer_source,
            ),
            (
                "retirement_pension_isa_transfer_krw",
                retirement_pension_isa_transfer_krw,
                retirement_pension_isa_transfer_source,
            ),
            (
                "prior_same_maturity_isa_extra_eligible_contribution_used_krw",
                prior_same_maturity_isa_extra_eligible_contribution_used_krw,
                prior_same_maturity_isa_extra_eligible_contribution_used_source,
            ),
            ("income_basis", income_basis, income_basis_source),
            ("income_amount_krw", income_amount_krw, income_amount_source),
            (
                "remaining_tax_before_pension_credit_krw",
                remaining_tax_before_pension_credit_krw,
                remaining_tax_before_pension_credit_source,
            ),
        )
        inputs: dict[str, Any] = {
            "pension_savings_net_contribution_krw": pension_savings_net_contribution_krw,
            "retirement_pension_net_contribution_krw": retirement_pension_net_contribution_krw,
        }
        input_sources: dict[str, str] = {
            "pension_savings_net_contribution_krw": pension_savings_net_contribution_source,
            "retirement_pension_net_contribution_krw": retirement_pension_net_contribution_source,
        }
        for field, value, source in optional_entries:
            if (value is None) != (source is None):
                return json.dumps(
                    {"error": "선택 입력값과 출처는 함께 제공해야 합니다."},
                    ensure_ascii=False,
                )
            if value is not None:
                inputs[field] = value
                input_sources[field] = cast(str, source)

        return _execute_calculation(
            calculator_id="pension_tax_credit",
            inputs=inputs,
            input_sources=input_sources,
            tool_name=CALCULATE_PENSION_TAX_CREDIT_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_pension_tax_credit


def create_fund_standard_price_tool() -> BaseTool:
    """Product Agent용 펀드 기준가격 계산 Tool을 만든다."""

    @tool(
        CALCULATE_FUND_STANDARD_PRICE_TOOL_NAME,
        description=(
            "전일 자산총액, 부채총액과 총좌수로 1,000좌당 기준가격을 계산한다. "
            "사용자 질문 또는 검증된 검색 근거에 명시된 입력만 사용한다."
        ),
    )
    async def calculate_fund_standard_price(
        total_assets_krw: Annotated[
            Decimal,
            Field(ge=0, description="전일 자산총액(원)"),
        ],
        total_liabilities_krw: Annotated[
            Decimal,
            Field(ge=0, description="전일 부채총액(원)"),
        ],
        total_units: Annotated[
            Decimal,
            Field(gt=0, description="전일 총좌수"),
        ],
        total_assets_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="자산총액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        total_liabilities_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="부채총액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        total_units_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="총좌수 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        return _execute_calculation(
            calculator_id="fund_standard_price",
            inputs={
                "total_assets_krw": total_assets_krw,
                "total_liabilities_krw": total_liabilities_krw,
                "total_units": total_units,
            },
            input_sources={
                "total_assets_krw": total_assets_source,
                "total_liabilities_krw": total_liabilities_source,
                "total_units": total_units_source,
            },
            tool_name=CALCULATE_FUND_STANDARD_PRICE_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_fund_standard_price


def create_fund_var_risk_tool() -> BaseTool:
    """Product Agent용 VaR 위험등급 계산 Tool을 만든다."""

    @tool(
        CALCULATE_FUND_VAR_RISK_TOOL_NAME,
        description=(
            "과거 3년 일간 수익률의 2.5퍼센타일 손실률로 연환산 97.5% VaR와 "
            "위험등급을 계산한다. 사용자 질문 또는 검증된 검색 근거에 명시된 입력만 사용한다."
        ),
    )
    async def calculate_fund_var_risk(
        daily_loss_percentile_percent: Annotated[
            Decimal,
            Field(ge=-100, le=100, description="일간 2.5퍼센타일 손실률(%)"),
        ],
        daily_loss_percentile_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="손실률 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        return _execute_calculation(
            calculator_id="fund_var_risk",
            inputs={"daily_loss_percentile_percent": daily_loss_percentile_percent},
            input_sources={
                "daily_loss_percentile_percent": daily_loss_percentile_source,
            },
            tool_name=CALCULATE_FUND_VAR_RISK_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_fund_var_risk


def _execute_calculation(
    *,
    calculator_id: str,
    inputs: dict[str, Any],
    input_sources: dict[str, str],
    tool_name: str,
    runtime: ToolRuntime[ExecutionContext, Any],
) -> Command | str:
    """검색 이후 계산을 실행하고 검증된 결과만 Agent state에 누적한다."""

    search_result = runtime.state.get("search_result")
    if (
        search_result is None
        or search_result.execution_status != "completed"
        or not search_result.retrieved_chunks
    ):
        return json.dumps(
            {"error": "검증된 문서 근거를 먼저 검색해야 합니다."},
            ensure_ascii=False,
        )
    verified_sources = validated_input_sources(
        inputs=inputs,
        input_sources=input_sources,
        state=runtime.state,
    )
    if verified_sources is None:
        return json.dumps(
            {"error": "계산 입력의 질문·문서 출처를 확인할 수 없습니다."},
            ensure_ascii=False,
        )
    try:
        result = calculate(CalculationRequest(calculator_id=calculator_id, inputs=inputs))
    except CalculationError:
        return json.dumps(
            {"error": "계산 입력 또는 산술 조건이 올바르지 않습니다."},
            ensure_ascii=False,
        )
    if runtime.tool_call_id is None:
        raise ValueError("Calculation Tool 호출 ID가 없습니다.")
    calculation = _agent_calculation_result(
        result.model_dump(mode="json"),
        input_sources=verified_sources,
    )
    return Command(
        update={
            "calculations": [calculation],
            "messages": [
                ToolMessage(
                    content=result.model_dump_json(),
                    tool_call_id=runtime.tool_call_id,
                    name=tool_name,
                )
            ],
        }
    )


def _agent_calculation_result(
    value: dict[str, Any],
    *,
    input_sources: dict[str, CalculationInputSource],
) -> CalculationResult:
    """Rules 결과를 JSON 직렬화 가능한 Agent 계약으로 변환한다."""

    return {
        "calculator_id": value["calculator_id"],
        "inputs": value["inputs"],
        "input_sources": input_sources,
        "outputs": value["outputs"],
        "units": value["units"],
        "warnings": list(value["warnings"]),
    }
