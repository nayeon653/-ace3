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
CALCULATE_PENSION_ANNUAL_LIMIT_INSTALLMENT_TOOL_NAME = "calculate_pension_annual_limit_installment"
CALCULATE_PENSION_PERIOD_INSTALLMENT_TOOL_NAME = "calculate_pension_period_installment"
CALCULATE_PENSION_UNIT_INSTALLMENT_TOOL_NAME = "calculate_pension_unit_installment"
CALCULATE_PENSION_TAX_CREDIT_TOOL_NAME = "calculate_pension_tax_credit"
CALCULATE_PENSION_INCOME_TAX_TOOL_NAME = "calculate_pension_income_tax"
CALCULATE_NON_PENSION_WITHDRAWAL_TAX_TOOL_NAME = "calculate_non_pension_withdrawal_tax"
CALCULATE_DEFERRED_RETIREMENT_WITHDRAWAL_TAX_TOOL_NAME = (
    "calculate_deferred_retirement_withdrawal_tax"
)
CALCULATE_PENSION_WITHDRAWAL_ALLOCATION_TOOL_NAME = "calculate_pension_withdrawal_allocation"
CALCULATE_PENSION_WITHDRAWAL_TAX_BREAKDOWN_TOOL_NAME = "calculate_pension_withdrawal_tax_breakdown"
CALCULATE_DC_MEDICAL_WITHDRAWAL_THRESHOLD_TOOL_NAME = "calculate_dc_medical_withdrawal_threshold"
CALCULATE_DB_RETIREMENT_BENEFIT_TOOL_NAME = "calculate_db_retirement_benefit"
CALCULATE_DC_MINIMUM_EMPLOYER_CONTRIBUTION_TOOL_NAME = "calculate_dc_minimum_employer_contribution"
CALCULATE_DC_RETIREMENT_BENEFIT_TOOL_NAME = "calculate_dc_retirement_benefit"
CALCULATE_DB_TO_DC_TRANSFER_AMOUNT_TOOL_NAME = "calculate_db_to_dc_transfer_amount"
CALCULATE_MEDICAL_CARE_WITHDRAWAL_TAX_LIMIT_TOOL_NAME = (
    "calculate_medical_care_withdrawal_tax_limit"
)
CALCULATE_MEDICAL_CARE_WITHDRAWAL_TAX_BREAKDOWN_TOOL_NAME = (
    "calculate_medical_care_withdrawal_tax_breakdown"
)
CALCULATE_FUND_STANDARD_PRICE_TOOL_NAME = "calculate_fund_standard_price"
CALCULATE_FUND_REPORTED_VAR_RISK_TOOL_NAME = "calculate_fund_reported_var_risk"
CALCULATE_FUND_VAR_RISK_TOOL_NAME = "calculate_fund_var_risk"
CALCULATE_FUND_FRONTEND_SALES_FEE_TOOL_NAME = "calculate_fund_frontend_sales_fee"
CALCULATE_FUND_DEFERRED_SALES_FEE_TOOL_NAME = "calculate_fund_deferred_sales_fee"
CALCULATE_FUND_REDEMPTION_FEE_TOOL_NAME = "calculate_fund_redemption_fee"


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
        pension_year: Annotated[
            int,
            Field(ge=1, description="1 이상의 연금수령연차"),
        ],
        pension_year_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="연금수령연차 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
        account_valuation_krw: Annotated[
            Decimal | None,
            Field(ge=0, description="선택 연금계좌 평가액(원)"),
        ] = None,
        account_valuation_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="평가액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ] = None,
    ) -> Command | str:
        if (account_valuation_krw is None) != (account_valuation_source is None):
            return "계산 Tool 오류: 선택 입력은 값과 source를 함께 전달하거나 함께 생략해야 합니다."
        inputs: dict[str, Any] = {"pension_year": pension_year}
        input_sources = {"pension_year": pension_year_source}
        if account_valuation_krw is not None:
            inputs["account_valuation_krw"] = account_valuation_krw
            input_sources["account_valuation_krw"] = cast(str, account_valuation_source)
        return _execute_calculation(
            calculator_id="pension_withdrawal_limit",
            inputs=inputs,
            input_sources=input_sources,
            tool_name=CALCULATE_PENSION_WITHDRAWAL_LIMIT_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_pension_withdrawal_limit


def create_pension_annual_limit_installment_tool() -> BaseTool:
    """당해연도 남은 한도의 회당 지급액 계산 Tool을 만든다."""

    @tool(CALCULATE_PENSION_ANNUAL_LIMIT_INSTALLMENT_TOOL_NAME)
    async def calculate_pension_annual_limit_installment(
        remaining_annual_limit_krw: Annotated[Decimal, Field(ge=0)],
        remaining_payments_in_year: Annotated[int, Field(ge=1)],
        remaining_annual_limit_source: Annotated[str, Field(min_length=1, max_length=120)],
        remaining_payments_in_year_source: Annotated[str, Field(min_length=1, max_length=120)],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        """당해연도 남은 한도를 잔여 지급횟수로 나눈다."""

        return _execute_calculation(
            calculator_id="pension_annual_limit_installment",
            inputs={
                "remaining_annual_limit_krw": remaining_annual_limit_krw,
                "remaining_payments_in_year": remaining_payments_in_year,
            },
            input_sources={
                "remaining_annual_limit_krw": remaining_annual_limit_source,
                "remaining_payments_in_year": remaining_payments_in_year_source,
            },
            tool_name=CALCULATE_PENSION_ANNUAL_LIMIT_INSTALLMENT_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_pension_annual_limit_installment


def create_pension_period_installment_tool() -> BaseTool:
    """현재 평가액의 전체 잔여회차별 지급액 계산 Tool을 만든다."""

    @tool(CALCULATE_PENSION_PERIOD_INSTALLMENT_TOOL_NAME)
    async def calculate_pension_period_installment(
        current_valuation_krw: Annotated[Decimal, Field(ge=0)],
        remaining_payments: Annotated[int, Field(ge=1)],
        current_valuation_source: Annotated[str, Field(min_length=1, max_length=120)],
        remaining_payments_source: Annotated[str, Field(min_length=1, max_length=120)],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        """현재 평가액을 전체 기간 잔여 지급횟수로 나눈다."""

        return _execute_calculation(
            calculator_id="pension_period_installment",
            inputs={
                "current_valuation_krw": current_valuation_krw,
                "remaining_payments": remaining_payments,
            },
            input_sources={
                "current_valuation_krw": current_valuation_source,
                "remaining_payments": remaining_payments_source,
            },
            tool_name=CALCULATE_PENSION_PERIOD_INSTALLMENT_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_pension_period_installment


def create_pension_unit_installment_tool() -> BaseTool:
    """잔고좌수와 기준가격의 전체 잔여회차별 지급액 계산 Tool을 만든다."""

    @tool(CALCULATE_PENSION_UNIT_INSTALLMENT_TOOL_NAME)
    async def calculate_pension_unit_installment(
        remaining_units: Annotated[Decimal, Field(ge=0)],
        remaining_payments: Annotated[int, Field(ge=1)],
        standard_price_per_1000_units_krw: Annotated[Decimal, Field(ge=0)],
        remaining_units_source: Annotated[str, Field(min_length=1, max_length=120)],
        remaining_payments_source: Annotated[str, Field(min_length=1, max_length=120)],
        standard_price_per_1000_units_source: Annotated[str, Field(min_length=1, max_length=120)],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        """잔고좌수와 기준가격으로 전체 기간 회당 지급액을 계산한다."""

        return _execute_calculation(
            calculator_id="pension_unit_installment",
            inputs={
                "remaining_units": remaining_units,
                "remaining_payments": remaining_payments,
                "standard_price_per_1000_units_krw": standard_price_per_1000_units_krw,
            },
            input_sources={
                "remaining_units": remaining_units_source,
                "remaining_payments": remaining_payments_source,
                "standard_price_per_1000_units_krw": standard_price_per_1000_units_source,
            },
            tool_name=CALCULATE_PENSION_UNIT_INSTALLMENT_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_pension_unit_installment


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
        pension_savings_isa_transfer_krw: Annotated[
            Decimal,
            Field(ge=0, description="연금저축 ISA 만기자금 전환액(원)"),
        ],
        retirement_pension_isa_transfer_krw: Annotated[
            Decimal,
            Field(ge=0, description="퇴직연금 ISA 만기자금 전환액(원)"),
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
        pension_savings_isa_transfer_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="연금저축 ISA 전환액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        retirement_pension_isa_transfer_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="퇴직연금 ISA 전환액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
        prior_same_maturity_isa_extra_eligible_contribution_used_krw: Annotated[
            Decimal | None,
            Field(
                ge=0, le=3_000_000, description="같은 만기자금의 전년도 추가 공제대상액 사용분(원)"
            ),
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
            "pension_savings_isa_transfer_krw": pension_savings_isa_transfer_krw,
            "retirement_pension_isa_transfer_krw": retirement_pension_isa_transfer_krw,
        }
        input_sources: dict[str, str] = {
            "pension_savings_net_contribution_krw": pension_savings_net_contribution_source,
            "retirement_pension_net_contribution_krw": retirement_pension_net_contribution_source,
            "pension_savings_isa_transfer_krw": pension_savings_isa_transfer_source,
            "retirement_pension_isa_transfer_krw": retirement_pension_isa_transfer_source,
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


def create_pension_income_tax_tool() -> BaseTool:
    """Tax/Payout Agent용 연금소득세 계산 Tool을 만든다."""

    @tool(
        CALCULATE_PENSION_INCOME_TAX_TOOL_NAME,
        description=(
            "일반 연금수령 또는 부득이한 사유 인출의 기본세율과 확정 가능한 세액을 "
            "계산한다. 선택 입력은 값과 출처를 함께 전달하거나 함께 생략한다."
        ),
    )
    async def calculate_pension_income_tax(
        pension_treatment: Annotated[
            Literal["ordinary", "unavoidable"],
            Field(description="연금수령 과세 구분"),
        ],
        recipient_age: Annotated[int, Field(ge=0, description="수령자 나이")],
        pension_treatment_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="연금수령 또는 부득이한 사유 의미가 있는 원문 구절",
            ),
        ],
        recipient_age_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="나이 의미와 정확한 세 값이 있는 원문 구절",
            ),
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
        target_taxable_amount_krw: Annotated[
            Decimal | None,
            Field(ge=0, description="현재 연금수령 과세대상액(원)"),
        ] = None,
        target_taxable_amount_krw_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="연금수령 과세대상 재원과 금액이 있는 원문 구절",
            ),
        ] = None,
        is_lifetime_annuity: Annotated[
            bool | None,
            Field(description="종신연금 여부"),
        ] = None,
        is_lifetime_annuity_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="종신 또는 비종신 의미가 있는 원문 구절",
            ),
        ] = None,
        annual_private_pension_taxable_income_krw: Annotated[
            Decimal | None,
            Field(ge=0, description="연간 사적연금 과세대상 합계(원)"),
        ] = None,
        annual_private_pension_taxable_income_krw_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="연간 사적연금 과세대상 합계와 금액이 있는 원문 구절",
            ),
        ] = None,
    ) -> Command | str:
        optional_entries: tuple[tuple[str, Any, str | None], ...] = (
            (
                "target_taxable_amount_krw",
                target_taxable_amount_krw,
                target_taxable_amount_krw_source,
            ),
            (
                "is_lifetime_annuity",
                is_lifetime_annuity,
                is_lifetime_annuity_source,
            ),
            (
                "annual_private_pension_taxable_income_krw",
                annual_private_pension_taxable_income_krw,
                annual_private_pension_taxable_income_krw_source,
            ),
        )
        inputs: dict[str, Any] = {
            "pension_treatment": pension_treatment,
            "recipient_age": recipient_age,
        }
        input_sources = {
            "pension_treatment": pension_treatment_source,
            "recipient_age": recipient_age_source,
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
            calculator_id="pension_income_tax",
            inputs=inputs,
            input_sources=input_sources,
            tool_name=CALCULATE_PENSION_INCOME_TAX_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_pension_income_tax


def create_non_pension_withdrawal_tax_tool() -> BaseTool:
    """Tax/Payout Agent용 연금외수령 세액 계산 Tool을 만든다."""

    @tool(
        CALCULATE_NON_PENSION_WITHDRAWAL_TAX_TOOL_NAME,
        description=(
            "연금외수령의 16.5% 세율과 과세대상액이 있을 때 세액을 계산한다. "
            "과세대상액과 출처는 함께 전달하거나 함께 생략한다."
        ),
    )
    async def calculate_non_pension_withdrawal_tax(
        runtime: ToolRuntime[ExecutionContext, Any],
        taxable_amount_krw: Annotated[
            Decimal | None,
            Field(ge=0, description="연금외수령 과세대상액(원)"),
        ] = None,
        taxable_amount_krw_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="연금외수령 의미와 과세대상 재원·금액이 있는 원문 구절",
            ),
        ] = None,
    ) -> Command | str:
        inputs: dict[str, Any] = {}
        input_sources: dict[str, str] = {}
        if (taxable_amount_krw is None) != (taxable_amount_krw_source is None):
            return json.dumps(
                {"error": "선택 입력값과 출처는 함께 제공해야 합니다."},
                ensure_ascii=False,
            )
        if taxable_amount_krw is not None:
            inputs["taxable_amount_krw"] = taxable_amount_krw
            input_sources["taxable_amount_krw"] = cast(str, taxable_amount_krw_source)

        return _execute_calculation(
            calculator_id="non_pension_withdrawal_tax",
            inputs=inputs,
            input_sources=input_sources,
            tool_name=CALCULATE_NON_PENSION_WITHDRAWAL_TAX_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_non_pension_withdrawal_tax


def create_deferred_retirement_withdrawal_tax_tool() -> BaseTool:
    """Tax/Payout Agent용 이연퇴직소득세 납부·감면 계산 Tool을 만든다."""

    @tool(
        CALCULATE_DEFERRED_RETIREMENT_WITHDRAWAL_TAX_TOOL_NAME,
        description=(
            "연금·연금외수령 구분과 실제수령연차에 따라 해당 인출분에 배분된 "
            "이연퇴직소득세의 납부·감면 비율과 금액을 계산한다. 선택 입력은 값과 "
            "출처를 함께 전달하거나 함께 생략한다."
        ),
    )
    async def calculate_deferred_retirement_withdrawal_tax(
        receipt_type: Annotated[
            Literal["pension", "non_pension"],
            Field(description="이연퇴직소득의 연금 또는 연금외수령 구분"),
        ],
        receipt_type_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="연금수령 또는 연금외수령 의미가 있는 원문 구절",
            ),
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
        actual_pension_receipt_year: Annotated[
            int | None,
            Field(ge=1, description="실제로 연금을 수령한 누적 연차"),
        ] = None,
        actual_pension_receipt_year_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="실제수령연차와 정확한 년차 값이 있는 원문 구절",
            ),
        ] = None,
        allocated_deferred_retirement_tax_krw: Annotated[
            Decimal | None,
            Field(ge=0, description="해당 인출분에 배분된 이연퇴직소득세(원)"),
        ] = None,
        allocated_deferred_retirement_tax_krw_source: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=120,
                description="해당 인출분 배분 의미와 퇴직소득세 금액이 있는 원문 구절",
            ),
        ] = None,
    ) -> Command | str:
        optional_entries: tuple[tuple[str, Any, str | None], ...] = (
            (
                "actual_pension_receipt_year",
                actual_pension_receipt_year,
                actual_pension_receipt_year_source,
            ),
            (
                "allocated_deferred_retirement_tax_krw",
                allocated_deferred_retirement_tax_krw,
                allocated_deferred_retirement_tax_krw_source,
            ),
        )
        inputs: dict[str, Any] = {"receipt_type": receipt_type}
        input_sources = {"receipt_type": receipt_type_source}
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
            calculator_id="deferred_retirement_withdrawal_tax",
            inputs=inputs,
            input_sources=input_sources,
            tool_name=CALCULATE_DEFERRED_RETIREMENT_WITHDRAWAL_TAX_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_deferred_retirement_withdrawal_tax


def create_pension_withdrawal_allocation_tool() -> BaseTool:
    """현재 인출 요청액을 세법상 재원 순서대로 배분하는 Tool을 만든다."""

    @tool(CALCULATE_PENSION_WITHDRAWAL_ALLOCATION_TOOL_NAME)
    async def calculate_pension_withdrawal_allocation(
        requested_withdrawal_krw: Annotated[Decimal, Field(ge=0)],
        tax_free_source_balance_krw: Annotated[Decimal, Field(ge=0)],
        deferred_retirement_source_balance_krw: Annotated[Decimal, Field(ge=0)],
        credited_and_earnings_source_balance_krw: Annotated[Decimal, Field(ge=0)],
        requested_withdrawal_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        tax_free_source_balance_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        deferred_retirement_source_balance_krw_source: Annotated[
            str, Field(min_length=1, max_length=120)
        ],
        credited_and_earnings_source_balance_krw_source: Annotated[
            str, Field(min_length=1, max_length=120)
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        """현재 인출 요청액을 재원별로 배분한다."""

        return _execute_calculation(
            calculator_id="pension_withdrawal_allocation",
            inputs={
                "requested_withdrawal_krw": requested_withdrawal_krw,
                "tax_free_source_balance_krw": tax_free_source_balance_krw,
                "deferred_retirement_source_balance_krw": deferred_retirement_source_balance_krw,
                "credited_and_earnings_source_balance_krw": (
                    credited_and_earnings_source_balance_krw
                ),
            },
            input_sources={
                "requested_withdrawal_krw": requested_withdrawal_krw_source,
                "tax_free_source_balance_krw": tax_free_source_balance_krw_source,
                "deferred_retirement_source_balance_krw": (
                    deferred_retirement_source_balance_krw_source
                ),
                "credited_and_earnings_source_balance_krw": (
                    credited_and_earnings_source_balance_krw_source
                ),
            },
            tool_name=CALCULATE_PENSION_WITHDRAWAL_ALLOCATION_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_pension_withdrawal_allocation


def create_dc_medical_withdrawal_threshold_tool() -> BaseTool:
    """Policy Agent용 DC 의료비 12.5% 기준 계산 Tool을 만든다."""

    @tool(CALCULATE_DC_MEDICAL_WITHDRAWAL_THRESHOLD_TOOL_NAME)
    async def calculate_dc_medical_withdrawal_threshold(
        employment_duration_category: Literal["less_than_one_year", "at_least_one_year"],
        documented_medical_expenses_krw: Annotated[Decimal, Field(ge=0)],
        employment_duration_category_source: Annotated[str, Field(min_length=1, max_length=120)],
        documented_medical_expenses_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        runtime: ToolRuntime[ExecutionContext, Any],
        previous_year_annual_wages_krw: Annotated[Decimal | None, Field(ge=0)] = None,
        previous_year_annual_wages_krw_source: Annotated[
            str | None, Field(min_length=1, max_length=120)
        ] = None,
        preceding_12_month_wages_krw: Annotated[Decimal | None, Field(ge=0)] = None,
        preceding_12_month_wages_krw_source: Annotated[
            str | None, Field(min_length=1, max_length=120)
        ] = None,
        average_monthly_wage_during_employment_krw: Annotated[Decimal | None, Field(ge=0)] = None,
        average_monthly_wage_during_employment_krw_source: Annotated[
            str | None, Field(min_length=1, max_length=120)
        ] = None,
    ) -> Command | str:
        """검증된 임금과 의료비로 DC 12.5% 기준을 계산한다."""

        inputs: dict[str, Any] = {
            "employment_duration_category": employment_duration_category,
            "documented_medical_expenses_krw": documented_medical_expenses_krw,
        }
        input_sources = {
            "employment_duration_category": employment_duration_category_source,
            "documented_medical_expenses_krw": documented_medical_expenses_krw_source,
        }
        optional_entries: tuple[tuple[str, Any, str | None], ...] = (
            (
                "previous_year_annual_wages_krw",
                previous_year_annual_wages_krw,
                previous_year_annual_wages_krw_source,
            ),
            (
                "preceding_12_month_wages_krw",
                preceding_12_month_wages_krw,
                preceding_12_month_wages_krw_source,
            ),
            (
                "average_monthly_wage_during_employment_krw",
                average_monthly_wage_during_employment_krw,
                average_monthly_wage_during_employment_krw_source,
            ),
        )
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
            calculator_id="dc_medical_withdrawal_threshold",
            inputs=inputs,
            input_sources=input_sources,
            tool_name=CALCULATE_DC_MEDICAL_WITHDRAWAL_THRESHOLD_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_dc_medical_withdrawal_threshold


def create_db_retirement_benefit_tool() -> BaseTool:
    """검증된 평균임금 입력과 계속근로연수로 DB 퇴직급여를 계산하는 Tool을 만든다."""

    @tool(CALCULATE_DB_RETIREMENT_BENEFIT_TOOL_NAME)
    async def calculate_db_retirement_benefit(
        wages_for_average_period_krw: Annotated[Decimal, Field(ge=0)],
        included_days_for_average_wage: Annotated[int, Field(ge=1)],
        verified_service_years: Annotated[Decimal, Field(ge=0)],
        wages_for_average_period_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        included_days_for_average_wage_source: Annotated[str, Field(min_length=1, max_length=120)],
        verified_service_years_source: Annotated[str, Field(min_length=1, max_length=120)],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        """검증된 최근 3개월 임금·포함 일수·근속연수로 DB 급여를 계산한다."""

        return _execute_calculation(
            calculator_id="db_retirement_benefit",
            inputs={
                "wages_for_average_period_krw": wages_for_average_period_krw,
                "included_days_for_average_wage": included_days_for_average_wage,
                "verified_service_years": verified_service_years,
            },
            input_sources={
                "wages_for_average_period_krw": wages_for_average_period_krw_source,
                "included_days_for_average_wage": included_days_for_average_wage_source,
                "verified_service_years": verified_service_years_source,
            },
            tool_name=CALCULATE_DB_RETIREMENT_BENEFIT_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_db_retirement_benefit


def create_dc_minimum_employer_contribution_tool() -> BaseTool:
    """검증된 연간임금총액으로 DC 최소 사용자 부담금을 계산하는 Tool을 만든다."""

    @tool(CALCULATE_DC_MINIMUM_EMPLOYER_CONTRIBUTION_TOOL_NAME)
    async def calculate_dc_minimum_employer_contribution(
        annual_total_wages_krw: Annotated[Decimal, Field(ge=0)],
        annual_total_wages_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        """검증된 연간임금총액의 12분의 1을 계산한다."""

        return _execute_calculation(
            calculator_id="dc_minimum_employer_contribution",
            inputs={"annual_total_wages_krw": annual_total_wages_krw},
            input_sources={"annual_total_wages_krw": annual_total_wages_krw_source},
            tool_name=CALCULATE_DC_MINIMUM_EMPLOYER_CONTRIBUTION_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_dc_minimum_employer_contribution


def create_dc_retirement_benefit_tool() -> BaseTool:
    """검증된 누적 부담금과 운용손익으로 DC 퇴직급여를 계산하는 Tool을 만든다."""

    @tool(CALCULATE_DC_RETIREMENT_BENEFIT_TOOL_NAME)
    async def calculate_dc_retirement_benefit(
        accumulated_contributions_krw: Annotated[Decimal, Field(ge=0)],
        investment_gain_loss_krw: Decimal,
        accumulated_contributions_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        investment_gain_loss_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        """검증된 DC 누적 부담금과 부호 있는 누적 운용손익을 합산한다."""

        return _execute_calculation(
            calculator_id="dc_retirement_benefit",
            inputs={
                "accumulated_contributions_krw": accumulated_contributions_krw,
                "investment_gain_loss_krw": investment_gain_loss_krw,
            },
            input_sources={
                "accumulated_contributions_krw": accumulated_contributions_krw_source,
                "investment_gain_loss_krw": investment_gain_loss_krw_source,
            },
            tool_name=CALCULATE_DC_RETIREMENT_BENEFIT_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_dc_retirement_benefit


def create_db_to_dc_transfer_amount_tool() -> BaseTool:
    """검증된 두 임금 기준과 근속연수로 DB→DC 전환금액을 계산하는 Tool을 만든다."""

    @tool(CALCULATE_DB_TO_DC_TRANSFER_AMOUNT_TOOL_NAME)
    async def calculate_db_to_dc_transfer_amount(
        final_average_wage_30_days_krw: Annotated[Decimal, Field(ge=0)],
        final_annual_total_wages_krw: Annotated[Decimal, Field(ge=0)],
        verified_service_years: Annotated[Decimal, Field(ge=0)],
        final_average_wage_30_days_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        final_annual_total_wages_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        verified_service_years_source: Annotated[str, Field(min_length=1, max_length=120)],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        """전환 기준시점의 두 임금 기준 중 큰 값에 검증된 근속연수를 적용한다."""

        return _execute_calculation(
            calculator_id="db_to_dc_transfer_amount",
            inputs={
                "final_average_wage_30_days_krw": final_average_wage_30_days_krw,
                "final_annual_total_wages_krw": final_annual_total_wages_krw,
                "verified_service_years": verified_service_years,
            },
            input_sources={
                "final_average_wage_30_days_krw": final_average_wage_30_days_krw_source,
                "final_annual_total_wages_krw": final_annual_total_wages_krw_source,
                "verified_service_years": verified_service_years_source,
            },
            tool_name=CALCULATE_DB_TO_DC_TRANSFER_AMOUNT_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_db_to_dc_transfer_amount


def create_medical_care_withdrawal_tax_limit_tool() -> BaseTool:
    """Tax/Payout Agent용 의료·요양 저율과세 한도 Tool을 만든다."""

    @tool(CALCULATE_MEDICAL_CARE_WITHDRAWAL_TAX_LIMIT_TOOL_NAME)
    async def calculate_medical_care_withdrawal_tax_limit(
        requested_withdrawal_krw: Annotated[Decimal, Field(ge=0)],
        actual_medical_expenses_krw: Annotated[Decimal, Field(ge=0)],
        care_expenses_krw: Annotated[Decimal, Field(ge=0)],
        own_leave_months: Annotated[int, Field(ge=0)],
        requested_withdrawal_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        actual_medical_expenses_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        care_expenses_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        own_leave_months_source: Annotated[str, Field(min_length=1, max_length=120)],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        """검증된 의료·요양 입력으로 저율과세 한도를 계산한다."""

        return _execute_calculation(
            calculator_id="medical_care_withdrawal_tax_limit",
            inputs={
                "requested_withdrawal_krw": requested_withdrawal_krw,
                "actual_medical_expenses_krw": actual_medical_expenses_krw,
                "care_expenses_krw": care_expenses_krw,
                "own_leave_months": own_leave_months,
            },
            input_sources={
                "requested_withdrawal_krw": requested_withdrawal_krw_source,
                "actual_medical_expenses_krw": actual_medical_expenses_krw_source,
                "care_expenses_krw": care_expenses_krw_source,
                "own_leave_months": own_leave_months_source,
            },
            tool_name=CALCULATE_MEDICAL_CARE_WITHDRAWAL_TAX_LIMIT_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_medical_care_withdrawal_tax_limit


def create_medical_care_withdrawal_tax_breakdown_tool() -> BaseTool:
    """Tax/Payout Agent용 의료·요양 한도 내 세액 명세 Tool을 만든다."""

    @tool(CALCULATE_MEDICAL_CARE_WITHDRAWAL_TAX_BREAKDOWN_TOOL_NAME)
    async def calculate_medical_care_withdrawal_tax_breakdown(
        requested_withdrawal_krw: Annotated[Decimal, Field(ge=0)],
        actual_medical_expenses_krw: Annotated[Decimal, Field(ge=0)],
        care_expenses_krw: Annotated[Decimal, Field(ge=0)],
        own_leave_months: Annotated[int, Field(ge=0)],
        recipient_age: Annotated[int, Field(ge=0)],
        requested_withdrawal_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        actual_medical_expenses_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        care_expenses_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        own_leave_months_source: Annotated[str, Field(min_length=1, max_length=120)],
        recipient_age_source: Annotated[str, Field(min_length=1, max_length=120)],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        """검증된 의료·요양 입력과 나이로 한도 내 세액을 계산한다."""

        return _execute_calculation(
            calculator_id="medical_care_withdrawal_tax_breakdown",
            inputs={
                "requested_withdrawal_krw": requested_withdrawal_krw,
                "actual_medical_expenses_krw": actual_medical_expenses_krw,
                "care_expenses_krw": care_expenses_krw,
                "own_leave_months": own_leave_months,
                "recipient_age": recipient_age,
            },
            input_sources={
                "requested_withdrawal_krw": requested_withdrawal_krw_source,
                "actual_medical_expenses_krw": actual_medical_expenses_krw_source,
                "care_expenses_krw": care_expenses_krw_source,
                "own_leave_months": own_leave_months_source,
                "recipient_age": recipient_age_source,
            },
            tool_name=CALCULATE_MEDICAL_CARE_WITHDRAWAL_TAX_BREAKDOWN_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_medical_care_withdrawal_tax_breakdown


def create_pension_withdrawal_tax_breakdown_tool() -> BaseTool:
    """재원·수령구분별 현재 인출 세금 명세를 계산하는 Tool을 만든다."""

    @tool(CALCULATE_PENSION_WITHDRAWAL_TAX_BREAKDOWN_TOOL_NAME)
    async def calculate_pension_withdrawal_tax_breakdown(
        requested_withdrawal_krw: Annotated[Decimal, Field(ge=0)],
        tax_free_source_balance_krw: Annotated[Decimal, Field(ge=0)],
        deferred_retirement_source_balance_krw: Annotated[Decimal, Field(ge=0)],
        credited_and_earnings_source_balance_krw: Annotated[Decimal, Field(ge=0)],
        pension_treated_withdrawal_krw: Annotated[Decimal, Field(ge=0)],
        non_pension_treated_withdrawal_krw: Annotated[Decimal, Field(ge=0)],
        requested_withdrawal_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        tax_free_source_balance_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        deferred_retirement_source_balance_krw_source: Annotated[
            str, Field(min_length=1, max_length=120)
        ],
        credited_and_earnings_source_balance_krw_source: Annotated[
            str, Field(min_length=1, max_length=120)
        ],
        pension_treated_withdrawal_krw_source: Annotated[str, Field(min_length=1, max_length=120)],
        non_pension_treated_withdrawal_krw_source: Annotated[
            str, Field(min_length=1, max_length=120)
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
        actual_pension_receipt_year: Annotated[int | None, Field(ge=1)] = None,
        actual_pension_receipt_year_source: Annotated[
            str | None, Field(min_length=1, max_length=120)
        ] = None,
        recipient_age: Annotated[int | None, Field(ge=0)] = None,
        recipient_age_source: Annotated[str | None, Field(min_length=1, max_length=120)] = None,
        is_lifetime_annuity: bool | None = None,
        is_lifetime_annuity_source: Annotated[
            str | None, Field(min_length=1, max_length=120)
        ] = None,
        annual_private_pension_taxable_income_krw: Annotated[Decimal | None, Field(ge=0)] = None,
        annual_private_pension_taxable_income_krw_source: Annotated[
            str | None, Field(min_length=1, max_length=120)
        ] = None,
        pension_treated_allocated_deferred_retirement_tax_krw: Annotated[
            Decimal | None, Field(ge=0)
        ] = None,
        pension_treated_allocated_deferred_retirement_tax_krw_source: Annotated[
            str | None, Field(min_length=1, max_length=120)
        ] = None,
        non_pension_treated_allocated_deferred_retirement_tax_krw: Annotated[
            Decimal | None, Field(ge=0)
        ] = None,
        non_pension_treated_allocated_deferred_retirement_tax_krw_source: Annotated[
            str | None, Field(min_length=1, max_length=120)
        ] = None,
    ) -> Command | str:
        """현재 인출액의 재원·수령구분별 세금 명세를 계산한다."""

        inputs: dict[str, Any] = {
            "requested_withdrawal_krw": requested_withdrawal_krw,
            "tax_free_source_balance_krw": tax_free_source_balance_krw,
            "deferred_retirement_source_balance_krw": deferred_retirement_source_balance_krw,
            "credited_and_earnings_source_balance_krw": credited_and_earnings_source_balance_krw,
            "pension_treated_withdrawal_krw": pension_treated_withdrawal_krw,
            "non_pension_treated_withdrawal_krw": non_pension_treated_withdrawal_krw,
        }
        input_sources: dict[str, str] = {
            "requested_withdrawal_krw": requested_withdrawal_krw_source,
            "tax_free_source_balance_krw": tax_free_source_balance_krw_source,
            "deferred_retirement_source_balance_krw": deferred_retirement_source_balance_krw_source,
            "credited_and_earnings_source_balance_krw": (
                credited_and_earnings_source_balance_krw_source
            ),
            "pension_treated_withdrawal_krw": pension_treated_withdrawal_krw_source,
            "non_pension_treated_withdrawal_krw": non_pension_treated_withdrawal_krw_source,
        }
        optional_entries: tuple[tuple[str, Any, str | None], ...] = (
            (
                "actual_pension_receipt_year",
                actual_pension_receipt_year,
                actual_pension_receipt_year_source,
            ),
            ("recipient_age", recipient_age, recipient_age_source),
            ("is_lifetime_annuity", is_lifetime_annuity, is_lifetime_annuity_source),
            (
                "annual_private_pension_taxable_income_krw",
                annual_private_pension_taxable_income_krw,
                annual_private_pension_taxable_income_krw_source,
            ),
            (
                "pension_treated_allocated_deferred_retirement_tax_krw",
                pension_treated_allocated_deferred_retirement_tax_krw,
                pension_treated_allocated_deferred_retirement_tax_krw_source,
            ),
            (
                "non_pension_treated_allocated_deferred_retirement_tax_krw",
                non_pension_treated_allocated_deferred_retirement_tax_krw,
                non_pension_treated_allocated_deferred_retirement_tax_krw_source,
            ),
        )
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
            calculator_id="pension_withdrawal_tax_breakdown",
            inputs=inputs,
            input_sources=input_sources,
            tool_name=CALCULATE_PENSION_WITHDRAWAL_TAX_BREAKDOWN_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_pension_withdrawal_tax_breakdown


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


def create_fund_reported_var_risk_tool() -> BaseTool:
    """Product Agent용 공시 연환산 VaR 위험등급 계산 Tool을 만든다."""

    @tool(
        CALCULATE_FUND_REPORTED_VAR_RISK_TOOL_NAME,
        description=(
            "투자설명서에 결과값으로 공시된 연환산 97.5% VaR를 추가 변환 없이 "
            "위험등급으로 판정한다. 검증된 단일 상품 검색 근거의 정확한 공시값만 사용한다."
        ),
    )
    async def calculate_fund_reported_var_risk(
        annualized_var_percent: Annotated[
            Decimal,
            Field(ge=0, description="공시된 연환산 97.5% VaR(%)"),
        ],
        annualized_var_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=200,
                description=(
                    "공시·연환산·97.5% VaR 문맥과 결과값 하나를 포함하며 검색 원문에 "
                    "그대로 있는 구절"
                ),
            ),
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        return _execute_calculation(
            calculator_id="fund_reported_var_risk",
            inputs={"annualized_var_percent": annualized_var_percent},
            input_sources={"annualized_var_percent": annualized_var_source},
            tool_name=CALCULATE_FUND_REPORTED_VAR_RISK_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_fund_reported_var_risk


def create_fund_frontend_sales_fee_tool() -> BaseTool:
    """Product Agent용 선취판매수수료 계산 Tool을 만든다."""

    @tool(
        CALCULATE_FUND_FRONTEND_SALES_FEE_TOOL_NAME,
        description=(
            "가입 시 납입금액과 상품·클래스·가입기간에 맞게 검색으로 확정한 선취판매수수료율로 "
            "고정 수수료 또는 상한 수수료 금액을 계산한다. 사용자 질문 또는 검증된 검색 근거에 "
            "명시된 입력만 사용한다."
        ),
    )
    async def calculate_fund_frontend_sales_fee(
        subscription_amount_krw: Annotated[
            Decimal,
            Field(ge=0, description="가입 시 납입금액(원)"),
        ],
        selected_rate_percent: Annotated[
            Decimal,
            Field(ge=0, le=100, description="검색 근거로 확정한 선취판매수수료율(%)"),
        ],
        rate_kind: Annotated[
            Literal["fixed", "maximum"],
            Field(description="고정 요율인지 이내·상한 요율인지 구분"),
        ],
        subscription_amount_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="납입금액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        selected_rate_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="선취판매수수료율 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        rate_kind_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="고정 또는 이내·상한 의미가 있는 원문 구절",
            ),
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        return _execute_calculation(
            calculator_id="fund_frontend_sales_fee",
            inputs={
                "subscription_amount_krw": subscription_amount_krw,
                "selected_rate_percent": selected_rate_percent,
                "rate_kind": rate_kind,
            },
            input_sources={
                "subscription_amount_krw": subscription_amount_source,
                "selected_rate_percent": selected_rate_source,
                "rate_kind": rate_kind_source,
            },
            tool_name=CALCULATE_FUND_FRONTEND_SALES_FEE_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_fund_frontend_sales_fee


def create_fund_deferred_sales_fee_tool() -> BaseTool:
    """Product Agent용 후취판매수수료 계산 Tool을 만든다."""

    @tool(
        CALCULATE_FUND_DEFERRED_SALES_FEE_TOOL_NAME,
        description=(
            "환매 시 환매금액과 상품·클래스·보유기간에 맞게 검색으로 확정한 후취판매수수료율로 "
            "고정 수수료 또는 상한 수수료 금액을 계산한다. 사용자 질문 또는 검증된 검색 근거에 "
            "명시된 입력만 사용한다."
        ),
    )
    async def calculate_fund_deferred_sales_fee(
        redemption_amount_krw: Annotated[
            Decimal,
            Field(ge=0, description="환매 시 환매금액(원)"),
        ],
        selected_rate_percent: Annotated[
            Decimal,
            Field(ge=0, le=100, description="검색 근거로 확정한 후취판매수수료율(%)"),
        ],
        rate_kind: Annotated[
            Literal["fixed", "maximum"],
            Field(description="고정 요율인지 이내·상한 요율인지 구분"),
        ],
        redemption_amount_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="환매금액 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        selected_rate_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="후취판매수수료율 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        rate_kind_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="고정 또는 이내·상한 의미가 있는 원문 구절",
            ),
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        return _execute_calculation(
            calculator_id="fund_deferred_sales_fee",
            inputs={
                "redemption_amount_krw": redemption_amount_krw,
                "selected_rate_percent": selected_rate_percent,
                "rate_kind": rate_kind,
            },
            input_sources={
                "redemption_amount_krw": redemption_amount_source,
                "selected_rate_percent": selected_rate_source,
                "rate_kind": rate_kind_source,
            },
            tool_name=CALCULATE_FUND_DEFERRED_SALES_FEE_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_fund_deferred_sales_fee


def create_fund_redemption_fee_tool() -> BaseTool:
    """Product Agent용 환매수수료 계산 Tool을 만든다."""

    @tool(
        CALCULATE_FUND_REDEMPTION_FEE_TOOL_NAME,
        description=(
            "환매 시 이익금과 상품·클래스·보유기간에 맞게 검색으로 확정한 환매수수료율로 "
            "고정 수수료 또는 상한 수수료 금액을 계산한다. 사용자 질문 또는 검증된 검색 근거에 "
            "명시된 입력만 사용한다."
        ),
    )
    async def calculate_fund_redemption_fee(
        redemption_profit_krw: Annotated[
            Decimal,
            Field(ge=0, description="환매 시 이익금(원)"),
        ],
        selected_rate_percent: Annotated[
            Decimal,
            Field(ge=0, le=100, description="검색 근거로 확정한 환매수수료율(%)"),
        ],
        rate_kind: Annotated[
            Literal["fixed", "maximum"],
            Field(description="고정 요율인지 이내·상한 요율인지 구분"),
        ],
        redemption_profit_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="이익금 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        selected_rate_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="환매수수료율 하나만 포함하며 질문 또는 검색 원문에 그대로 있는 구절",
            ),
        ],
        rate_kind_source: Annotated[
            str,
            Field(
                min_length=1,
                max_length=120,
                description="고정 또는 이내·상한 의미가 있는 원문 구절",
            ),
        ],
        runtime: ToolRuntime[ExecutionContext, Any],
    ) -> Command | str:
        return _execute_calculation(
            calculator_id="fund_redemption_fee",
            inputs={
                "redemption_profit_krw": redemption_profit_krw,
                "selected_rate_percent": selected_rate_percent,
                "rate_kind": rate_kind,
            },
            input_sources={
                "redemption_profit_krw": redemption_profit_source,
                "selected_rate_percent": selected_rate_source,
                "rate_kind": rate_kind_source,
            },
            tool_name=CALCULATE_FUND_REDEMPTION_FEE_TOOL_NAME,
            runtime=runtime,
        )

    return calculate_fund_redemption_fee


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
        calculator_id=calculator_id,
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
