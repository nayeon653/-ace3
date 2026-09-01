"""Domain Agent용 Calculation Tool 어댑터를 검증한다."""

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from langgraph.types import Command

from pension_agent.agent.calculation import (
    create_db_retirement_benefit_tool,
    create_db_to_dc_transfer_amount_tool,
    create_dc_medical_withdrawal_threshold_tool,
    create_dc_minimum_employer_contribution_tool,
    create_dc_retirement_benefit_tool,
    create_deferred_retirement_withdrawal_tax_tool,
    create_executive_retirement_income_limit_tool,
    create_fund_standard_price_tool,
    create_fund_var_risk_tool,
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
from pension_agent.agent.calculation.input_sources import validated_input_sources
from pension_agent.agent.search import SearchResult

_DC_DURATION_SOURCE = "재직 1년 이상"
_DC_MEDICAL_SOURCE = "근로자 부담 증빙 의료비 1,300만원"
_DC_PREVIOUS_WAGES_SOURCE = "직전연도 연간임금총액 1억원"
_DC_PRECEDING_WAGES_SOURCE = "신청일 기준 직전 12개월 임금 8천만원"
_MEDICAL_CARE_REQUEST_SOURCE = "의료·요양 총 인출 요청액 300만원"
_ACTUAL_MEDICAL_SOURCE = "과세한도 산식 실제 의료비 50만원"
_CARE_EXPENSE_SOURCE = "간병비 25만원"
_OWN_LEAVE_SOURCE = "본인 휴직 0개월"
_DB_WAGES_SOURCE = "최근 3개월 임금 합계는 9,000,000원"
_DB_DAYS_SOURCE = "제외기간 반영 후 평균임금 산정일수 90일"
_SERVICE_YEARS_SOURCE = "검증된 근속연수 3.5년"
_DC_ANNUAL_WAGES_SOURCE = "연간임금총액은 48,000,000원"
_DC_CONTRIBUTIONS_SOURCE = "DC 실제 누적 부담금 10,000,000원"
_DC_GAIN_SOURCE = "누적 운용수익 1,000,000원"
_FINAL_AVERAGE_WAGE_SOURCE = "DB→DC 전환 기준 최종 30일 평균임금 4,000,000원"
_FINAL_ANNUAL_WAGES_SOURCE = "DB→DC 전환 기준 최종 연간임금총액 60,000,000원"


def _medical_care_runtime(*sources: str, chunk: bool = False) -> SimpleNamespace:
    content = "; ".join(sources)
    return _runtime(
        question="의료·요양 인출을 계산해줘" if chunk else content,
        chunk_content=content,
    )


def _retirement_runtime(*sources: str, chunk: bool = False) -> SimpleNamespace:
    content = "; ".join(sources)
    return _runtime(
        question="DB·DC 퇴직급여를 계산해줘" if chunk else content,
        chunk_content=content,
    )


def _runtime(
    *,
    with_evidence: bool = True,
    question: str | None = None,
    chunk_content: str = "검증된 계산 규칙",
) -> SimpleNamespace:
    chunks = (
        [
            {
                "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_file_name": "rules.pdf",
                "document_type": "pension_reference",
                "chunk_index": 0,
                "title": "계산 규칙",
                "locator": "1쪽",
                "content": chunk_content,
            }
        ]
        if with_evidence
        else []
    )
    return SimpleNamespace(
        state={
            "question": question
            or (
                "평가액 1천만원, 연금수령연차 1년차, 자산총액 100만원, 부채총액 10만원, "
                "총좌수 10만좌, 손실률 -2%"
            ),
            "search_result": SearchResult(
                execution_status="completed",
                retrieved_chunks=chunks,
            ),
        },
        tool_call_id="call-1",
    )


@pytest.mark.anyio
async def test_pension_tool_records_rules_result_in_state() -> None:
    result = await create_pension_withdrawal_limit_tool().coroutine(
        account_valuation_krw=Decimal(10000000),
        pension_year=1,
        account_valuation_source="평가액 1천만원",
        pension_year_source="연금수령연차 1년차",
        runtime=_runtime(),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == "pension_withdrawal_limit"
    assert calculation["outputs"]["withdrawal_limit"] == "1200000.0"


@pytest.mark.anyio
async def test_product_tools_record_only_their_calculator_results() -> None:
    standard_price = await create_fund_standard_price_tool().coroutine(
        total_assets_krw=Decimal(1000000),
        total_liabilities_krw=Decimal(100000),
        total_units=Decimal(100000),
        total_assets_source="자산총액 100만원",
        total_liabilities_source="부채총액 10만원",
        total_units_source="총좌수 10만좌",
        runtime=_runtime(),
    )
    var_risk = await create_fund_var_risk_tool().coroutine(
        daily_loss_percentile_percent=Decimal(-2),
        daily_loss_percentile_source="손실률 -2%",
        runtime=_runtime(),
    )

    assert isinstance(standard_price, Command)
    assert isinstance(var_risk, Command)
    assert standard_price.update["calculations"][0]["calculator_id"] == "fund_standard_price"
    assert var_risk.update["calculations"][0]["calculator_id"] == "fund_var_risk"


@pytest.mark.anyio
async def test_calculation_tool_requires_completed_search_evidence() -> None:
    result = await create_pension_withdrawal_limit_tool().coroutine(
        account_valuation_krw=Decimal(10000000),
        pension_year=1,
        account_valuation_source="평가액 1천만원",
        pension_year_source="연금수령연차 1년차",
        runtime=_runtime(with_evidence=False),
    )

    assert isinstance(result, str)
    assert "문서 근거" in result


@pytest.mark.anyio
async def test_calculation_tool_rejects_input_without_trusted_source() -> None:
    result = await create_pension_withdrawal_limit_tool().coroutine(
        account_valuation_krw=Decimal(999999999),
        pension_year=10,
        account_valuation_source="평가액 999,999,999원",
        pension_year_source="연금수령연차 10년차",
        runtime=_runtime(),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_calculation_tool_rejects_money_from_another_field() -> None:
    result = await create_fund_standard_price_tool().coroutine(
        total_assets_krw=Decimal(500000),
        total_liabilities_krw=Decimal(100000),
        total_units=Decimal(100000),
        total_assets_source="가입금액 50만원",
        total_liabilities_source="부채총액 10만원",
        total_units_source="총좌수 10만좌",
        runtime=_runtime(
            question="가입금액 50만원, 자산총액 100만원, 부채총액 10만원, 총좌수 10만좌"
        ),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_calculation_tool_records_evidence_source_chunk() -> None:
    result = await create_pension_withdrawal_limit_tool().coroutine(
        account_valuation_krw=Decimal(10000000),
        pension_year=1,
        account_valuation_source="평가액 1천만원",
        pension_year_source="연금수령연차 1년차",
        runtime=_runtime(
            question="연금수령한도를 계산해줘",
            chunk_content="평가액 1천만원, 연금수령연차 1년차에 대한 계산 규칙",
        ),
    )

    assert isinstance(result, Command)
    sources = result.update["calculations"][0]["input_sources"]
    assert sources["account_valuation_krw"] == {
        "origin": "evidence",
        "text": "평가액 1천만원",
        "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("account_value", "account_source"),
    [
        (Decimal(1), "1년차"),
        (Decimal(10000000), "평가액 1천만원, 1년차"),
    ],
)
async def test_calculation_tool_rejects_wrong_field_or_multi_value_source(
    account_value: Decimal,
    account_source: str,
) -> None:
    result = await create_pension_withdrawal_limit_tool().coroutine(
        account_valuation_krw=account_value,
        pension_year=1,
        account_valuation_source=account_source,
        pension_year_source="연금수령연차 1년차",
        runtime=_runtime(),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_withdrawal_limit_tool_allows_omitted_valuation_after_tenth_year() -> None:
    result = await create_pension_withdrawal_limit_tool().coroutine(
        pension_year=11,
        pension_year_source="연금수령연차 11년차",
        runtime=_runtime(question="연금수령연차 11년차"),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["inputs"] == {"pension_year": 11}
    assert calculation["outputs"] == {"withdrawal_limit": None, "limit_applies": False}
    assert calculation["input_sources"].keys() == {"pension_year"}


@pytest.mark.anyio
async def test_withdrawal_limit_tool_returns_rules_error_without_required_valuation() -> None:
    result = await create_pension_withdrawal_limit_tool().coroutine(
        pension_year=10,
        pension_year_source="연금수령연차 10년차",
        runtime=_runtime(question="연금수령연차 10년차"),
    )

    assert isinstance(result, str)
    assert "계산 입력" in result


@pytest.mark.anyio
async def test_withdrawal_limit_tool_rejects_mismatched_optional_pair() -> None:
    result = await create_pension_withdrawal_limit_tool().coroutine(
        pension_year=11,
        pension_year_source="연금수령연차 11년차",
        account_valuation_krw=Decimal(1_000_000),
        runtime=_runtime(question="연금수령연차 11년차, 평가액 100만원"),
    )

    assert isinstance(result, str)
    assert "함께" in result


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool_factory", "kwargs", "calculator_id", "expected"),
    [
        (
            create_pension_annual_limit_installment_tool,
            {
                "remaining_annual_limit_krw": Decimal(1_200_000),
                "remaining_payments_in_year": 12,
                "remaining_annual_limit_source": "올해 남은 연금수령한도 120만원",
                "remaining_payments_in_year_source": "올해 잔여 지급횟수 12회",
            },
            "pension_annual_limit_installment",
            "100000",
        ),
        (
            create_pension_period_installment_tool,
            {
                "current_valuation_krw": Decimal(1_200_000),
                "remaining_payments": 12,
                "current_valuation_source": "현재 계좌 평가액 120만원",
                "remaining_payments_source": "전체 기간 잔여회차 12회",
            },
            "pension_period_installment",
            "100000",
        ),
        (
            create_pension_unit_installment_tool,
            {
                "remaining_units": Decimal(12_000),
                "remaining_payments": 12,
                "standard_price_per_1000_units_krw": Decimal(1_500),
                "remaining_units_source": "잔고좌수 12,000좌",
                "remaining_payments_source": "전체 기간 잔여 지급횟수 12회",
                "standard_price_per_1000_units_source": "1,000좌당 기준가격 1,500원",
            },
            "pension_unit_installment",
            "1500",
        ),
    ],
)
async def test_pension_installment_tools_calculate_and_preserve_sources(
    tool_factory: Any,
    kwargs: dict[str, Any],
    calculator_id: str,
    expected: str,
) -> None:
    question = "; ".join(str(value) for key, value in kwargs.items() if key.endswith("source"))
    result = await tool_factory().coroutine(**kwargs, runtime=_runtime(question=question))

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == calculator_id
    assert calculation["outputs"]["installment_krw"] == expected
    expected_sources = {str(value) for key, value in kwargs.items() if key.endswith("source")}
    assert {source["text"] for source in calculation["input_sources"].values()} == (
        expected_sources
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("source", "value"),
    [
        ("실제수령연차 11년차", 11),
        ("연금수령연차 10년차", 11),
        ("연금수령연차; 11년차", 11),
    ],
)
async def test_withdrawal_limit_tool_rejects_invalid_year_provenance(
    source: str, value: int
) -> None:
    result = await create_pension_withdrawal_limit_tool().coroutine(
        pension_year=value,
        pension_year_source=source,
        runtime=_runtime(question=source),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool_factory", "kwargs", "question"),
    [
        (
            create_pension_annual_limit_installment_tool,
            {
                "remaining_annual_limit_krw": Decimal(1_200_000),
                "remaining_payments_in_year": 12,
                "remaining_annual_limit_source": "올해 남은 연금수령한도; 120만원",
                "remaining_payments_in_year_source": "전체 기간 잔여회차 12회",
            },
            "올해 남은 연금수령한도; 120만원; 전체 기간 잔여회차 12회",
        ),
        (
            create_pension_period_installment_tool,
            {
                "current_valuation_krw": Decimal(1_200_000),
                "remaining_payments": 12,
                "current_valuation_source": "현재 계좌 평가액 120만원",
                "remaining_payments_source": "올해 잔여 지급횟수 12회",
            },
            "현재 계좌 평가액 120만원; 올해 잔여 지급횟수 12회",
        ),
        (
            create_pension_unit_installment_tool,
            {
                "remaining_units": Decimal(1_500),
                "remaining_payments": 12,
                "standard_price_per_1000_units_krw": Decimal(1_500),
                "remaining_units_source": "잔고좌수 1,500원",
                "remaining_payments_source": "전체 기간 잔여회차 12회",
                "standard_price_per_1000_units_source": "1,000좌당 기준가격 1,500원",
            },
            "잔고좌수 1,500원; 전체 기간 잔여회차 12회; 1,000좌당 기준가격 1,500원",
        ),
    ],
)
async def test_pension_installment_tools_reject_semantic_or_phrase_mismatch(
    tool_factory: Any,
    kwargs: dict[str, Any],
    question: str,
) -> None:
    result = await tool_factory().coroutine(**kwargs, runtime=_runtime(question=question))

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_pension_installment_tool_rejects_reused_source() -> None:
    source = "전체 현재 계좌 평가액과 잔여회차 12회 120만원"
    result = await create_pension_period_installment_tool().coroutine(
        current_valuation_krw=Decimal(1_200_000),
        remaining_payments=12,
        current_valuation_source=source,
        remaining_payments_source=source,
        runtime=_runtime(question=source),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_pension_tax_credit_tool_calculates_regular_contribution_with_salary() -> None:
    result = await create_pension_tax_credit_tool().coroutine(
        pension_savings_net_contribution_krw=Decimal(6_000_000),
        retirement_pension_net_contribution_krw=Decimal(3_000_000),
        pension_savings_isa_transfer_krw=Decimal(0),
        retirement_pension_isa_transfer_krw=Decimal(0),
        pension_savings_net_contribution_source="연금저축 순납입액 600만원",
        retirement_pension_net_contribution_source="퇴직연금 순납입액 300만원",
        pension_savings_isa_transfer_source="연금저축 ISA 전환액 0원",
        retirement_pension_isa_transfer_source="퇴직연금 ISA 전환액 0원",
        runtime=_runtime(
            question=(
                "연금저축 순납입액 600만원, 퇴직연금 순납입액 300만원 납입, "
                "연금저축 ISA 전환액 0원, 퇴직연금 ISA 전환액 0원, 총급여 5천만원"
            )
        ),
        income_basis="salary",
        income_basis_source="총급여",
        income_amount_krw=Decimal(50_000_000),
        income_amount_source="총급여 5천만원",
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == "pension_tax_credit"
    assert calculation["inputs"].keys() == {
        "pension_savings_net_contribution_krw",
        "retirement_pension_net_contribution_krw",
        "pension_savings_isa_transfer_krw",
        "retirement_pension_isa_transfer_krw",
        "income_basis",
        "income_amount_krw",
    }
    assert Decimal(calculation["outputs"]["eligible_contribution_krw"]) == Decimal(9_000_000)
    assert Decimal(calculation["outputs"]["credit_rate_percent"]) == Decimal("16.5")
    assert Decimal(calculation["outputs"]["theoretical_credit_krw"]) == Decimal(1_485_000)


@pytest.mark.anyio
async def test_pension_tax_credit_tool_returns_two_rate_scenarios_without_income() -> None:
    result = await create_pension_tax_credit_tool().coroutine(
        pension_savings_net_contribution_krw=Decimal(6_000_000),
        retirement_pension_net_contribution_krw=Decimal(3_000_000),
        pension_savings_isa_transfer_krw=Decimal(0),
        retirement_pension_isa_transfer_krw=Decimal(0),
        pension_savings_net_contribution_source="연금저축 순납입액 600만원",
        retirement_pension_net_contribution_source="퇴직연금 순납입액 300만원",
        pension_savings_isa_transfer_source="연금저축 ISA 전환액 0원",
        retirement_pension_isa_transfer_source="퇴직연금 ISA 전환액 0원",
        runtime=_runtime(
            question=(
                "연금저축 순납입액 600만원, 퇴직연금 순납입액 300만원 납입, "
                "연금저축 ISA 전환액 0원, 퇴직연금 ISA 전환액 0원"
            )
        ),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["inputs"].keys() == {
        "pension_savings_net_contribution_krw",
        "retirement_pension_net_contribution_krw",
        "pension_savings_isa_transfer_krw",
        "retirement_pension_isa_transfer_krw",
    }
    assert Decimal(calculation["outputs"]["lower_income_rate_percent"]) == Decimal("16.5")
    assert Decimal(calculation["outputs"]["other_income_rate_percent"]) == Decimal("13.2")


@pytest.mark.anyio
async def test_pension_tax_credit_tool_calculates_isa_transfer_and_preserves_sources() -> None:
    result = await create_pension_tax_credit_tool().coroutine(
        pension_savings_net_contribution_krw=Decimal(36_000_000),
        retirement_pension_net_contribution_krw=Decimal(3_000_000),
        pension_savings_net_contribution_source="연금저축 순납입액 3,600만원",
        retirement_pension_net_contribution_source="퇴직연금 순납입액 300만원",
        runtime=_runtime(
            question=(
                "연금저축 순납입액 3,600만원, 퇴직연금 순납입액 300만원 납입, "
                "연금저축 ISA 만기자금 3,000만원 전환, 퇴직연금 ISA 전환액 0원, 전년도 ISA 사용액 0원"
            )
        ),
        pension_savings_isa_transfer_krw=Decimal(30_000_000),
        pension_savings_isa_transfer_source="연금저축 ISA 만기자금 3,000만원",
        retirement_pension_isa_transfer_krw=Decimal(0),
        retirement_pension_isa_transfer_source="퇴직연금 ISA 전환액 0원",
        prior_same_maturity_isa_extra_eligible_contribution_used_krw=Decimal(0),
        prior_same_maturity_isa_extra_eligible_contribution_used_source="전년도 ISA 사용액 0원",
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert Decimal(calculation["outputs"]["eligible_contribution_krw"]) == Decimal(12_000_000)
    assert calculation["input_sources"]["pension_savings_isa_transfer_krw"] == {
        "origin": "question",
        "text": "연금저축 ISA 만기자금 3,000만원",
        "chunk_id": None,
    }
    assert calculation["input_sources"]["retirement_pension_isa_transfer_krw"] == {
        "origin": "question",
        "text": "퇴직연금 ISA 전환액 0원",
        "chunk_id": None,
    }


@pytest.mark.anyio
async def test_pension_tax_credit_tool_rejects_isa_transfer_without_prior_used_amount() -> None:
    result = await create_pension_tax_credit_tool().coroutine(
        pension_savings_net_contribution_krw=Decimal(36_000_000),
        retirement_pension_net_contribution_krw=Decimal(3_000_000),
        pension_savings_net_contribution_source="연금저축 순납입액 3,600만원",
        retirement_pension_net_contribution_source="퇴직연금 순납입액 300만원",
        runtime=_runtime(
            question=(
                "연금저축 순납입액 3,600만원, 퇴직연금 순납입액 300만원 납입, "
                "연금저축 ISA 만기자금 3,000만원 전환, 퇴직연금 ISA 전환액 0원"
            )
        ),
        pension_savings_isa_transfer_krw=Decimal(30_000_000),
        pension_savings_isa_transfer_source="연금저축 ISA 만기자금 3,000만원",
        retirement_pension_isa_transfer_krw=Decimal(0),
        retirement_pension_isa_transfer_source="퇴직연금 ISA 전환액 0원",
    )

    assert isinstance(result, str)


@pytest.mark.anyio
async def test_pension_tax_credit_tool_rejects_mismatched_optional_value_and_source() -> None:
    result = await create_pension_tax_credit_tool().coroutine(
        pension_savings_net_contribution_krw=Decimal(6_000_000),
        retirement_pension_net_contribution_krw=Decimal(3_000_000),
        pension_savings_isa_transfer_krw=Decimal(0),
        retirement_pension_isa_transfer_krw=Decimal(0),
        pension_savings_net_contribution_source="연금저축 순납입액 600만원",
        retirement_pension_net_contribution_source="퇴직연금 순납입액 300만원",
        pension_savings_isa_transfer_source="연금저축 ISA 0원",
        retirement_pension_isa_transfer_source="퇴직연금 ISA 0원",
        runtime=_runtime(),
        income_amount_krw=Decimal(50_000_000),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_pension_tax_credit_tool_rejects_income_basis_source_mismatch() -> None:
    result = await create_pension_tax_credit_tool().coroutine(
        pension_savings_net_contribution_krw=Decimal(6_000_000),
        retirement_pension_net_contribution_krw=Decimal(3_000_000),
        pension_savings_isa_transfer_krw=Decimal(0),
        retirement_pension_isa_transfer_krw=Decimal(0),
        pension_savings_net_contribution_source="연금저축 순납입액 600만원",
        retirement_pension_net_contribution_source="퇴직연금 순납입액 300만원",
        pension_savings_isa_transfer_source="연금저축 ISA 전환액 0원",
        retirement_pension_isa_transfer_source="퇴직연금 ISA 전환액 0원",
        runtime=_runtime(
            question=(
                "연금저축 순납입액 600만원, 퇴직연금 순납입액 300만원 납입, "
                "연금저축 ISA 전환액 0원, 퇴직연금 ISA 전환액 0원, 종합소득금액 5천만원"
            )
        ),
        income_basis="salary",
        income_basis_source="종합소득금액",
        income_amount_krw=Decimal(50_000_000),
        income_amount_source="종합소득금액 5천만원",
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_pension_income_tax_tool_calculates_ordinary_with_all_inputs() -> None:
    question = (
        "일반 연금수령; 수령자 나이 55세; 비종신 연금; "
        "현재 연금수령 과세대상 금액 100만원; 연간 사적연금 과세대상 합계 1,000만원"
    )
    result = await create_pension_income_tax_tool().coroutine(
        pension_treatment="ordinary",
        recipient_age=55,
        pension_treatment_source="일반 연금수령",
        recipient_age_source="수령자 나이 55세",
        runtime=_runtime(question=question),
        target_taxable_amount_krw=Decimal(1_000_000),
        target_taxable_amount_krw_source="현재 연금수령 과세대상 금액 100만원",
        is_lifetime_annuity=False,
        is_lifetime_annuity_source="비종신 연금",
        annual_private_pension_taxable_income_krw=Decimal(10_000_000),
        annual_private_pension_taxable_income_krw_source=("연간 사적연금 과세대상 합계 1,000만원"),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == "pension_income_tax"
    assert calculation["outputs"]["base_rate_percent"] == "5.500"
    assert calculation["outputs"]["tax_krw"] == "55000.000"
    assert calculation["input_sources"]["target_taxable_amount_krw"] == {
        "origin": "question",
        "text": "현재 연금수령 과세대상 금액 100만원",
        "chunk_id": None,
    }


@pytest.mark.anyio
async def test_pension_income_tax_tool_keeps_unknown_threshold_when_annual_omitted() -> None:
    result = await create_pension_income_tax_tool().coroutine(
        pension_treatment="ordinary",
        recipient_age=55,
        pension_treatment_source="일반 연금수령",
        recipient_age_source="수령자 나이 55세",
        runtime=_runtime(question="일반 연금수령, 수령자 나이 55세, 확정기간 연금"),
        is_lifetime_annuity=False,
        is_lifetime_annuity_source="확정기간 연금",
    )

    assert isinstance(result, Command)
    assert result.update["calculations"][0]["outputs"] == {
        "base_rate_percent": "5.500",
        "annual_threshold_status": "unknown",
    }


@pytest.mark.anyio
async def test_pension_income_tax_tool_allows_unavoidable_below_age_55() -> None:
    result = await create_pension_income_tax_tool().coroutine(
        pension_treatment="unavoidable",
        recipient_age=54,
        pension_treatment_source="부득이한 사유 연금수령",
        recipient_age_source="수령자 연령 54세",
        runtime=_runtime(question="부득이한 사유 연금수령, 수령자 연령 54세"),
    )

    assert isinstance(result, Command)
    assert result.update["calculations"][0]["outputs"]["base_rate_percent"] == "5.500"


@pytest.mark.anyio
async def test_non_pension_withdrawal_tax_tool_calculates_taxable_amount() -> None:
    result = await create_non_pension_withdrawal_tax_tool().coroutine(
        runtime=_runtime(question="중도해지 운용수익 과세대상 금액 100만원"),
        taxable_amount_krw=Decimal(1_000_000),
        taxable_amount_krw_source="중도해지 운용수익 과세대상 금액 100만원",
    )

    assert isinstance(result, Command)
    outputs = result.update["calculations"][0]["outputs"]
    assert outputs["base_rate_percent"] == "16.5"
    assert outputs["tax_krw"] == "165000.000"


@pytest.mark.anyio
async def test_non_pension_withdrawal_tax_tool_returns_rate_without_amount() -> None:
    result = await create_non_pension_withdrawal_tax_tool().coroutine(
        runtime=_runtime(question="연금외수령 세율은 얼마인가요?"),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["inputs"] == {}
    assert calculation["input_sources"] == {}
    assert calculation["outputs"] == {"base_rate_percent": "16.5"}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("value", "source"),
    [(Decimal(1_000_000), None), (None, "중도해지 과세대상 금액 100만원")],
)
async def test_non_pension_tool_rejects_mismatched_optional_value_and_source(
    value: Decimal | None, source: str | None
) -> None:
    result = await create_non_pension_withdrawal_tax_tool().coroutine(
        runtime=_runtime(question="중도해지 과세대상 금액 100만원"),
        taxable_amount_krw=value,
        taxable_amount_krw_source=source,
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_pension_income_tool_rejects_mismatched_optional_value_and_source() -> None:
    result = await create_pension_income_tax_tool().coroutine(
        pension_treatment="ordinary",
        recipient_age=55,
        pension_treatment_source="일반 연금수령",
        recipient_age_source="수령자 나이 55세",
        runtime=_runtime(question="일반 연금수령, 수령자 나이 55세"),
        target_taxable_amount_krw=Decimal(1_000_000),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_pension_income_tool_rejects_treatment_source_mismatch() -> None:
    result = await create_pension_income_tax_tool().coroutine(
        pension_treatment="ordinary",
        recipient_age=55,
        pension_treatment_source="부득이한 사유 연금수령",
        recipient_age_source="수령자 나이 55세",
        runtime=_runtime(question="부득이한 사유 연금수령, 수령자 나이 55세"),
        is_lifetime_annuity=False,
        is_lifetime_annuity_source="비종신 연금",
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_pension_income_tool_rejects_wrong_age_value_in_source() -> None:
    result = await create_pension_income_tax_tool().coroutine(
        pension_treatment="ordinary",
        recipient_age=55,
        pension_treatment_source="일반 연금수령",
        recipient_age_source="수령자 나이 54세",
        runtime=_runtime(question="일반 연금수령, 수령자 나이 54세, 비종신 연금"),
        is_lifetime_annuity=False,
        is_lifetime_annuity_source="비종신 연금",
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_pension_income_tool_rejects_lifetime_source_mismatch() -> None:
    result = await create_pension_income_tax_tool().coroutine(
        pension_treatment="ordinary",
        recipient_age=55,
        pension_treatment_source="일반 연금수령",
        recipient_age_source="수령자 나이 55세",
        runtime=_runtime(question="일반 연금수령, 수령자 나이 55세, 확정기간 연금"),
        is_lifetime_annuity=True,
        is_lifetime_annuity_source="확정기간 연금",
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.parametrize(
    ("field", "source", "value"),
    [
        (
            "target_taxable_amount_krw",
            "연간 사적연금 과세대상 합계 1,000만원",
            Decimal(10_000_000),
        ),
        (
            "annual_private_pension_taxable_income_krw",
            "현재 연금수령 과세대상 금액 100만원",
            Decimal(1_000_000),
        ),
    ],
)
def test_pension_income_provenance_rejects_misassigned_money_meaning(
    field: str, source: str, value: Decimal
) -> None:
    result = validated_input_sources(
        inputs={field: value},
        input_sources={field: source},
        state={"question": source},
    )

    assert result is None


def test_pension_income_provenance_rejects_annual_source_reused_for_target() -> None:
    source = "연간 사적연금 과세대상 합계 1,000만원"
    result = validated_input_sources(
        inputs={
            "target_taxable_amount_krw": Decimal(10_000_000),
            "annual_private_pension_taxable_income_krw": Decimal(10_000_000),
        },
        input_sources={
            "target_taxable_amount_krw": source,
            "annual_private_pension_taxable_income_krw": source,
        },
        state={"question": source},
    )

    assert result is None


@pytest.mark.parametrize(
    ("treatment", "source"),
    [
        ("ordinary", "현재 연금수령 세액공제 받은 원금의 과세대상 금액 100만원"),
        ("unavoidable", "부득이한 사유로 인출한 세액공제 받은 원금의 과세대상 금액 100만원"),
    ],
)
def test_pension_income_target_provenance_accepts_current_amount_meaning(
    treatment: str, source: str
) -> None:
    treatment_source = "일반 연금수령" if treatment == "ordinary" else "부득이한 사유 인출"
    question = f"{treatment_source}; {source}"
    result = validated_input_sources(
        inputs={"pension_treatment": treatment, "target_taxable_amount_krw": Decimal(1_000_000)},
        input_sources={
            "pension_treatment": treatment_source,
            "target_taxable_amount_krw": source,
        },
        state={"question": question},
    )

    assert result is not None


@pytest.mark.parametrize(
    ("field", "value", "source"),
    [
        ("pension_treatment", "ordinary", "일반 연금수령이 아님"),
        ("pension_treatment", "unavoidable", "부득이한 사유가 아닌 인출"),
        ("is_lifetime_annuity", True, "종신연금에 해당하지 않음"),
    ],
)
def test_pension_income_provenance_rejects_negated_positive_meaning(
    field: str, value: object, source: str
) -> None:
    result = validated_input_sources(
        inputs={field: value},
        input_sources={field: source},
        state={"question": source},
    )

    assert result is None


def test_non_lifetime_provenance_accepts_explicit_negation() -> None:
    source = "종신연금에 해당하지 않음"
    result = validated_input_sources(
        inputs={"is_lifetime_annuity": False},
        input_sources={"is_lifetime_annuity": source},
        state={"question": source},
    )

    assert result is not None


@pytest.mark.parametrize(
    ("value", "source"),
    [
        (55, "수령자 나이 55세 미만"),
        (70, "수령자 연령 70세 이상"),
        (80, "수령자 연령 80세 미만"),
        (69, "수령자 나이 55~69세"),
        (55, "수령자 나이 55세부터 69세"),
        (70, "수령자 나이 70세 전후"),
    ],
)
def test_recipient_age_provenance_rejects_ranges_and_approximations(
    value: int, source: str
) -> None:
    result = validated_input_sources(
        inputs={"recipient_age": value},
        input_sources={"recipient_age": source},
        state={"question": source},
    )

    assert result is None


@pytest.mark.parametrize("source", ["나이 65세", "연령 65세", "만 65세"])
def test_recipient_age_provenance_accepts_exact_age(source: str) -> None:
    result = validated_input_sources(
        inputs={"recipient_age": 65},
        input_sources={"recipient_age": source},
        state={"question": source},
    )

    assert result is not None


@pytest.mark.anyio
async def test_non_pension_tool_rejects_general_contribution_as_taxable_source() -> None:
    result = await create_non_pension_withdrawal_tax_tool().coroutine(
        runtime=_runtime(question="연금저축 일반 납입액 100만원"),
        taxable_amount_krw=Decimal(1_000_000),
        taxable_amount_krw_source="연금저축 일반 납입액 100만원",
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_pension_income_tool_returns_rules_cross_validation_error() -> None:
    result = await create_pension_income_tax_tool().coroutine(
        pension_treatment="ordinary",
        recipient_age=55,
        pension_treatment_source="일반 연금수령",
        recipient_age_source="수령자 나이 55세",
        runtime=_runtime(question="일반 연금수령, 수령자 나이 55세"),
    )

    assert isinstance(result, str)
    assert "계산 입력" in result


def test_pension_tax_credit_rejects_source_reused_from_wrong_field() -> None:
    result = validated_input_sources(
        inputs={"pension_savings_isa_transfer_krw": Decimal(10_000_000)},
        input_sources={"pension_savings_isa_transfer_krw": "연금저축 순납입액 1,000만원"},
        state={"question": "연금저축 순납입액 1,000만원"},
    )

    assert result is None


@pytest.mark.parametrize(
    "field",
    ["pension_savings_isa_transfer_krw", "retirement_pension_isa_transfer_krw"],
)
def test_pension_tax_credit_rejects_isa_source_without_account_type(field: str) -> None:
    result = validated_input_sources(
        inputs={field: Decimal(10_000_000)},
        input_sources={field: "ISA 만기자금 1,000만원"},
        state={"question": "ISA 만기자금 1,000만원"},
    )

    assert result is None


def test_pension_tax_credit_accepts_account_qualified_isa_sources() -> None:
    question = "연금저축 ISA 만기자금 전환액 600만원, IRP ISA 만기자금 전환액 400만원"

    savings_result = validated_input_sources(
        inputs={"pension_savings_isa_transfer_krw": Decimal(6_000_000)},
        input_sources={"pension_savings_isa_transfer_krw": "연금저축 ISA 만기자금 전환액 600만원"},
        state={"question": question},
    )
    retirement_result = validated_input_sources(
        inputs={"retirement_pension_isa_transfer_krw": Decimal(4_000_000)},
        input_sources={"retirement_pension_isa_transfer_krw": "IRP ISA 만기자금 전환액 400만원"},
        state={"question": question},
    )

    assert savings_result is not None
    assert retirement_result is not None


def test_pension_tax_credit_rejects_cross_phrase_token_reuse() -> None:
    source = "연금저축 ISA 만기자금 전환액 600만원, IRP 순납입액 400만원"

    result = validated_input_sources(
        inputs={"retirement_pension_isa_transfer_krw": Decimal(4_000_000)},
        input_sources={"retirement_pension_isa_transfer_krw": source},
        state={"question": source},
    )

    assert result is None


def test_pension_tax_credit_matches_isa_transfer_within_shared_source_phrase() -> None:
    source = "연금저축 ISA 만기자금 전환액 600만원, IRP ISA 만기자금 전환액 400만원"

    savings_result = validated_input_sources(
        inputs={"pension_savings_isa_transfer_krw": Decimal(6_000_000)},
        input_sources={"pension_savings_isa_transfer_krw": source},
        state={"question": source},
    )
    retirement_result = validated_input_sources(
        inputs={"retirement_pension_isa_transfer_krw": Decimal(4_000_000)},
        input_sources={"retirement_pension_isa_transfer_krw": source},
        state={"question": source},
    )

    assert savings_result is not None
    assert retirement_result is not None


@pytest.mark.parametrize(
    ("field", "source", "value"),
    [
        (
            "prior_same_maturity_isa_extra_eligible_contribution_used_krw",
            "전년도 300만원",
            Decimal(3_000_000),
        ),
        (
            "prior_same_maturity_isa_extra_eligible_contribution_used_krw",
            "ISA 300만원",
            Decimal(3_000_000),
        ),
        (
            "remaining_tax_before_pension_credit_krw",
            "잔여 100만원",
            Decimal(1_000_000),
        ),
        (
            "remaining_tax_before_pension_credit_krw",
            "산출세액 100만원",
            Decimal(1_000_000),
        ),
    ],
)
def test_pension_tax_credit_rejects_partially_matching_source(
    field: str, source: str, value: Decimal
) -> None:
    result = validated_input_sources(
        inputs={field: value},
        input_sources={field: source},
        state={"question": source},
    )

    assert result is None


@pytest.mark.anyio
async def test_deferred_retirement_tax_tool_calculates_pension_and_preserves_sources() -> None:
    question = (
        "이연퇴직소득을 연금으로 수령; 실제수령연차 10년차; "
        "해당 인출분에 배분된 이연퇴직소득세 100만원"
    )
    result = await create_deferred_retirement_withdrawal_tax_tool().coroutine(
        receipt_type="pension",
        receipt_type_source="이연퇴직소득을 연금으로 수령",
        runtime=_runtime(question=question),
        actual_pension_receipt_year=10,
        actual_pension_receipt_year_source="실제수령연차 10년차",
        allocated_deferred_retirement_tax_krw=Decimal(1_000_000),
        allocated_deferred_retirement_tax_krw_source=(
            "해당 인출분에 배분된 이연퇴직소득세 100만원"
        ),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == "deferred_retirement_withdrawal_tax"
    assert calculation["outputs"] == {
        "payable_ratio_percent": "70.00",
        "reduction_ratio_percent": "30.00",
        "tax_payable_krw": "700000.00",
        "tax_reduction_krw": "300000.00",
    }
    assert calculation["input_sources"]["allocated_deferred_retirement_tax_krw"] == {
        "origin": "question",
        "text": "해당 인출분에 배분된 이연퇴직소득세 100만원",
        "chunk_id": None,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("receipt_year", "payable_ratio"),
    [(11, "60.00"), (21, "50.00")],
)
async def test_deferred_retirement_tax_tool_uses_pension_year_ratio(
    receipt_year: int, payable_ratio: str
) -> None:
    source = f"실제수령연차 {receipt_year}년차"
    result = await create_deferred_retirement_withdrawal_tax_tool().coroutine(
        receipt_type="pension",
        receipt_type_source="연금수령",
        runtime=_runtime(question=f"연금수령, {source}"),
        actual_pension_receipt_year=receipt_year,
        actual_pension_receipt_year_source=source,
    )

    assert isinstance(result, Command)
    assert result.update["calculations"][0]["outputs"]["payable_ratio_percent"] == payable_ratio


@pytest.mark.anyio
async def test_deferred_retirement_tax_tool_returns_ratios_without_allocated_tax() -> None:
    result = await create_deferred_retirement_withdrawal_tax_tool().coroutine(
        receipt_type="pension",
        receipt_type_source="연금수령",
        runtime=_runtime(question="연금수령, 실제수령연차 10년차"),
        actual_pension_receipt_year=10,
        actual_pension_receipt_year_source="실제수령연차 10년차",
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["inputs"].keys() == {"receipt_type", "actual_pension_receipt_year"}
    assert calculation["outputs"] == {
        "payable_ratio_percent": "70.00",
        "reduction_ratio_percent": "30.00",
    }


@pytest.mark.anyio
async def test_deferred_retirement_tax_tool_preserves_explicit_zero_tax() -> None:
    question = "연금수령, 실제수령연차 10년차, 해당 인출분에 배분된 이연퇴직소득세 0원"
    result = await create_deferred_retirement_withdrawal_tax_tool().coroutine(
        receipt_type="pension",
        receipt_type_source="연금수령",
        runtime=_runtime(question=question),
        actual_pension_receipt_year=10,
        actual_pension_receipt_year_source="실제수령연차 10년차",
        allocated_deferred_retirement_tax_krw=Decimal(0),
        allocated_deferred_retirement_tax_krw_source=("해당 인출분에 배분된 이연퇴직소득세 0원"),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["inputs"]["allocated_deferred_retirement_tax_krw"] == "0"
    assert calculation["outputs"]["tax_payable_krw"] == "0.00"
    assert calculation["outputs"]["tax_reduction_krw"] == "0.00"


@pytest.mark.anyio
async def test_deferred_retirement_tax_tool_calculates_non_pension_ratio() -> None:
    result = await create_deferred_retirement_withdrawal_tax_tool().coroutine(
        receipt_type="non_pension",
        receipt_type_source="이연퇴직소득 연금외수령",
        runtime=_runtime(question="이연퇴직소득 연금외수령"),
    )

    assert isinstance(result, Command)
    assert result.update["calculations"][0]["outputs"] == {
        "payable_ratio_percent": "100",
        "reduction_ratio_percent": "0",
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("year", "year_source", "tax", "tax_source"),
    [
        (10, None, None, None),
        (None, "실제수령연차 10년차", None, None),
        (10, "실제수령연차 10년차", Decimal(1_000_000), None),
        (10, "실제수령연차 10년차", None, "해당 인출분 퇴직소득세 100만원"),
    ],
)
async def test_deferred_retirement_tax_tool_rejects_mismatched_optional_pairs(
    year: int | None,
    year_source: str | None,
    tax: Decimal | None,
    tax_source: str | None,
) -> None:
    result = await create_deferred_retirement_withdrawal_tax_tool().coroutine(
        receipt_type="pension",
        receipt_type_source="연금수령",
        runtime=_runtime(
            question=("연금수령, 실제수령연차 10년차, 해당 인출분 퇴직소득세 100만원")
        ),
        actual_pension_receipt_year=year,
        actual_pension_receipt_year_source=year_source,
        allocated_deferred_retirement_tax_krw=tax,
        allocated_deferred_retirement_tax_krw_source=tax_source,
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_deferred_retirement_tax_tool_returns_rules_error_without_pension_year() -> None:
    result = await create_deferred_retirement_withdrawal_tax_tool().coroutine(
        receipt_type="pension",
        receipt_type_source="연금수령",
        runtime=_runtime(question="연금수령"),
    )

    assert isinstance(result, str)
    assert "계산 입력" in result


@pytest.mark.anyio
async def test_deferred_retirement_tax_tool_returns_rules_error_for_non_pension_year() -> None:
    result = await create_deferred_retirement_withdrawal_tax_tool().coroutine(
        receipt_type="non_pension",
        receipt_type_source="연금외수령",
        runtime=_runtime(question="연금외수령, 실제수령연차 10년차"),
        actual_pension_receipt_year=10,
        actual_pension_receipt_year_source="실제수령연차 10년차",
    )

    assert isinstance(result, str)
    assert "계산 입력" in result


@pytest.mark.anyio
async def test_deferred_retirement_tax_tool_rejects_withdrawal_limit_year_source() -> None:
    result = await create_deferred_retirement_withdrawal_tax_tool().coroutine(
        receipt_type="pension",
        receipt_type_source="연금수령",
        runtime=_runtime(question="연금수령, 연금수령연차 10년차"),
        actual_pension_receipt_year=10,
        actual_pension_receipt_year_source="연금수령연차 10년차",
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_deferred_retirement_tax_tool_rejects_wrong_actual_year_value() -> None:
    result = await create_deferred_retirement_withdrawal_tax_tool().coroutine(
        receipt_type="pension",
        receipt_type_source="연금수령",
        runtime=_runtime(question="연금수령, 실제수령연차 11년차"),
        actual_pension_receipt_year=10,
        actual_pension_receipt_year_source="실제수령연차 11년차",
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_deferred_retirement_tax_tool_rejects_whole_account_tax_source() -> None:
    result = await create_deferred_retirement_withdrawal_tax_tool().coroutine(
        receipt_type="pension",
        receipt_type_source="연금수령",
        runtime=_runtime(question="연금수령, 실제수령연차 10년차, 계좌 전체 퇴직소득세 100만원"),
        actual_pension_receipt_year=10,
        actual_pension_receipt_year_source="실제수령연차 10년차",
        allocated_deferred_retirement_tax_krw=Decimal(1_000_000),
        allocated_deferred_retirement_tax_krw_source="계좌 전체 퇴직소득세 100만원",
    )

    assert isinstance(result, str)
    assert "출처" in result


def test_deferred_retirement_tax_accepts_allocated_withdrawal_tax_provenance() -> None:
    source = "해당 인출분에 배분된 이연퇴직소득세 100만원"
    result = validated_input_sources(
        inputs={"allocated_deferred_retirement_tax_krw": Decimal(1_000_000)},
        input_sources={"allocated_deferred_retirement_tax_krw": source},
        state={"question": source},
    )

    assert result is not None


@pytest.mark.anyio
async def test_deferred_retirement_tax_tool_rejects_receipt_type_source_mismatch() -> None:
    result = await create_deferred_retirement_withdrawal_tax_tool().coroutine(
        receipt_type="pension",
        receipt_type_source="연금외수령",
        runtime=_runtime(question="연금외수령, 실제수령연차 10년차"),
        actual_pension_receipt_year=10,
        actual_pension_receipt_year_source="실제수령연차 10년차",
    )

    assert isinstance(result, str)
    assert "출처" in result


def test_calculation_summary_preserves_verified_values() -> None:
    summary = format_calculation_summary(
        [
            {
                "calculator_id": "fund_var_risk",
                "inputs": {"daily_loss_percentile_percent": "-2"},
                "input_sources": {
                    "daily_loss_percentile_percent": {
                        "origin": "question",
                        "text": "손실률 -2%",
                        "chunk_id": None,
                    }
                },
                "outputs": {
                    "annualized_var_percent": "31.62277660168379331998893544",
                    "risk_grade": 2,
                    "risk_label": "높은 위험",
                },
                "units": {"annualized_var_percent": "%"},
                "warnings": [],
            }
        ]
    )

    assert "31.62277660168379331998893544 %" in summary
    assert "2등급 (높은 위험)" in summary


_WITHDRAWAL_VALUES = {
    "requested_withdrawal_krw": Decimal(6_000_000),
    "tax_free_source_balance_krw": Decimal(1_000_000),
    "deferred_retirement_source_balance_krw": Decimal(2_000_000),
    "credited_and_earnings_source_balance_krw": Decimal(5_000_000),
}
_WITHDRAWAL_SOURCES = {
    "requested_withdrawal_krw_source": "현재 인출 요청액 600만원",
    "tax_free_source_balance_krw_source": "세액공제 미적용 원금 비과세 재원의 현재 잔액 100만원",
    "deferred_retirement_source_balance_krw_source": "이연퇴직소득 퇴직금 재원의 현재 잔액 200만원",
    "credited_and_earnings_source_balance_krw_source": (
        "세액공제 받은 원금·운용수익 재원의 현재 잔액 500만원"
    ),
}
_BREAKDOWN_VALUES = {
    **_WITHDRAWAL_VALUES,
    "pension_treated_withdrawal_krw": Decimal(4_000_000),
    "non_pension_treated_withdrawal_krw": Decimal(2_000_000),
}
_BREAKDOWN_SOURCES = {
    **_WITHDRAWAL_SOURCES,
    "pension_treated_withdrawal_krw_source": "현재 요청 중 연금수령으로 처리되는 금액 400만원",
    "non_pension_treated_withdrawal_krw_source": (
        "현재 요청 중 연금외수령으로 처리되는 금액 200만원"
    ),
}


def _withdrawal_runtime(*sources: str) -> SimpleNamespace:
    content = "; ".join(sources)
    return _runtime(question=content, chunk_content=content)


def _breakdown_optional(annual: Decimal | None = Decimal(10_000_000)) -> dict[str, Any]:
    optional: dict[str, Any] = {
        "actual_pension_receipt_year": 10,
        "actual_pension_receipt_year_source": "실제수령연차 10년차",
        "recipient_age": 65,
        "recipient_age_source": "만 65세",
        "is_lifetime_annuity": False,
        "is_lifetime_annuity_source": "종신연금에 해당하지 않음",
        "pension_treated_allocated_deferred_retirement_tax_krw": Decimal(1_000_000),
        "pension_treated_allocated_deferred_retirement_tax_krw_source": (
            "해당 인출분에 배분된 연금수령 처리 이연퇴직소득세 100만원"
        ),
    }
    if annual is not None:
        optional["annual_private_pension_taxable_income_krw"] = annual
        optional["annual_private_pension_taxable_income_krw_source"] = (
            f"해당 연도 연간 사적연금 과세대상 합계 {annual}원"
        )
    return optional


def _optional_sources(optional: dict[str, Any]) -> list[str]:
    return [str(value) for key, value in optional.items() if key.endswith("_source")]


@pytest.mark.anyio
async def test_withdrawal_allocation_tool_calculates_and_preserves_sources() -> None:
    result = await create_pension_withdrawal_allocation_tool().coroutine(
        **_WITHDRAWAL_VALUES,
        **_WITHDRAWAL_SOURCES,
        runtime=_withdrawal_runtime(*_WITHDRAWAL_SOURCES.values()),
    )
    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == "pension_withdrawal_allocation"
    assert calculation["outputs"]["tax_free_withdrawal_krw"] == "1000000"
    assert calculation["outputs"]["credited_and_earnings_withdrawal_krw"] == "3000000"
    assert set(calculation["input_sources"]) == set(_WITHDRAWAL_VALUES)


@pytest.mark.anyio
async def test_withdrawal_allocation_tool_preserves_zero_request() -> None:
    values = {**_WITHDRAWAL_VALUES, "requested_withdrawal_krw": Decimal(0)}
    sources = {**_WITHDRAWAL_SOURCES, "requested_withdrawal_krw_source": "현재 인출 요청액 0원"}
    result = await create_pension_withdrawal_allocation_tool().coroutine(
        **values,
        **sources,
        runtime=_withdrawal_runtime(*sources.values()),
    )
    assert isinstance(result, Command)
    assert result.update["calculations"][0]["outputs"]["tax_free_withdrawal_krw"] == "0"


@pytest.mark.anyio
async def test_withdrawal_allocation_tool_returns_rules_error_above_balance() -> None:
    values = {**_WITHDRAWAL_VALUES, "requested_withdrawal_krw": Decimal(9_000_000)}
    sources = {**_WITHDRAWAL_SOURCES, "requested_withdrawal_krw_source": "현재 인출 요청액 900만원"}
    result = await create_pension_withdrawal_allocation_tool().coroutine(
        **values,
        **sources,
        runtime=_withdrawal_runtime(*sources.values()),
    )
    assert isinstance(result, str)
    assert "error" in result


@pytest.mark.anyio
async def test_dc_medical_threshold_tool_calculates_and_preserves_sources() -> None:
    sources = (_DC_DURATION_SOURCE, _DC_MEDICAL_SOURCE, _DC_PREVIOUS_WAGES_SOURCE)
    result = await create_dc_medical_withdrawal_threshold_tool().coroutine(
        employment_duration_category="at_least_one_year",
        documented_medical_expenses_krw=Decimal(13_000_000),
        employment_duration_category_source=_DC_DURATION_SOURCE,
        documented_medical_expenses_krw_source=_DC_MEDICAL_SOURCE,
        previous_year_annual_wages_krw=Decimal(100_000_000),
        previous_year_annual_wages_krw_source=_DC_PREVIOUS_WAGES_SOURCE,
        runtime=_medical_care_runtime(*sources, chunk=True),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == "dc_medical_withdrawal_threshold"
    assert calculation["outputs"]["threshold_met"] is True
    assert set(calculation["inputs"]) == set(calculation["input_sources"])
    assert {source["origin"] for source in calculation["input_sources"].values()} == {"evidence"}


@pytest.mark.anyio
async def test_dc_medical_threshold_tool_selects_lower_preceding_wages() -> None:
    sources = (
        _DC_DURATION_SOURCE,
        _DC_MEDICAL_SOURCE,
        _DC_PREVIOUS_WAGES_SOURCE,
        _DC_PRECEDING_WAGES_SOURCE,
    )
    result = await create_dc_medical_withdrawal_threshold_tool().coroutine(
        employment_duration_category="at_least_one_year",
        documented_medical_expenses_krw=Decimal(13_000_000),
        employment_duration_category_source=_DC_DURATION_SOURCE,
        documented_medical_expenses_krw_source=_DC_MEDICAL_SOURCE,
        previous_year_annual_wages_krw=Decimal(100_000_000),
        previous_year_annual_wages_krw_source=_DC_PREVIOUS_WAGES_SOURCE,
        preceding_12_month_wages_krw=Decimal(80_000_000),
        preceding_12_month_wages_krw_source=_DC_PRECEDING_WAGES_SOURCE,
        runtime=_medical_care_runtime(*sources),
    )

    assert isinstance(result, Command)
    outputs = result.update["calculations"][0]["outputs"]
    assert outputs["applicable_wages_krw"] == "80000000"
    assert outputs["wage_basis"] == "preceding_12_month_wages"


@pytest.mark.anyio
async def test_dc_medical_threshold_accepts_exact_month_duration_and_zero_values() -> None:
    sources = ("재직 11개월", "근로자 부담 증빙 의료비 0원", "재직 중 월평균 급여 0원")
    result = await create_dc_medical_withdrawal_threshold_tool().coroutine(
        employment_duration_category="less_than_one_year",
        documented_medical_expenses_krw=Decimal(0),
        employment_duration_category_source=sources[0],
        documented_medical_expenses_krw_source=sources[1],
        average_monthly_wage_during_employment_krw=Decimal(0),
        average_monthly_wage_during_employment_krw_source=sources[2],
        runtime=_medical_care_runtime(*sources),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["inputs"]["documented_medical_expenses_krw"] == "0"
    assert calculation["inputs"]["average_monthly_wage_during_employment_krw"] == "0"
    assert calculation["outputs"]["threshold_met"] is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "bad_source"),
    [
        ("previous_year_annual_wages_krw_source", _DC_PRECEDING_WAGES_SOURCE),
        ("previous_year_annual_wages_krw_source", "재직 중 월평균 급여 1억원"),
        ("previous_year_annual_wages_krw_source", "배우자 직전연도 연간임금총액 1억원"),
        ("documented_medical_expenses_krw_source", "의료 목적 인출 요청액 1,300만원"),
        ("documented_medical_expenses_krw_source", "금액 1,300만원"),
        ("documented_medical_expenses_krw_source", "근로자 부담 증빙 의료비가 아님 1,300만원"),
        ("employment_duration_category_source", "재직 약 1년"),
        ("employment_duration_category_source", "재직 11개월"),
    ],
)
async def test_dc_medical_threshold_rejects_provenance_mismatch(
    field: str, bad_source: str
) -> None:
    values: dict[str, object] = {
        "employment_duration_category": "at_least_one_year",
        "documented_medical_expenses_krw": Decimal(13_000_000),
        "employment_duration_category_source": _DC_DURATION_SOURCE,
        "documented_medical_expenses_krw_source": _DC_MEDICAL_SOURCE,
        "previous_year_annual_wages_krw": Decimal(100_000_000),
        "previous_year_annual_wages_krw_source": _DC_PREVIOUS_WAGES_SOURCE,
    }
    values[field] = bad_source
    sources = [str(value) for key, value in values.items() if key.endswith("_source")]
    result = await create_dc_medical_withdrawal_threshold_tool().coroutine(
        **values,
        runtime=_medical_care_runtime(*sources),
    )

    assert isinstance(result, str)
    assert "출처" in result


def _medical_limit_tool_inputs(**updates: object) -> dict[str, object]:
    inputs: dict[str, object] = {
        "requested_withdrawal_krw": Decimal(3_000_000),
        "actual_medical_expenses_krw": Decimal(500_000),
        "care_expenses_krw": Decimal(250_000),
        "own_leave_months": 0,
        "requested_withdrawal_krw_source": _MEDICAL_CARE_REQUEST_SOURCE,
        "actual_medical_expenses_krw_source": _ACTUAL_MEDICAL_SOURCE,
        "care_expenses_krw_source": _CARE_EXPENSE_SOURCE,
        "own_leave_months_source": _OWN_LEAVE_SOURCE,
    }
    inputs.update(updates)
    return inputs


def _source_values(inputs: dict[str, object]) -> list[str]:
    return [str(value) for key, value in inputs.items() if key.endswith("_source")]


@pytest.mark.anyio
async def test_db_retirement_benefit_tool_preserves_results_sources_and_evidence() -> None:
    sources = (_DB_WAGES_SOURCE, _DB_DAYS_SOURCE, _SERVICE_YEARS_SOURCE)
    result = await create_db_retirement_benefit_tool().coroutine(
        wages_for_average_period_krw=Decimal(9_000_000),
        included_days_for_average_wage=90,
        verified_service_years=Decimal("3.5"),
        wages_for_average_period_krw_source=sources[0],
        included_days_for_average_wage_source=sources[1],
        verified_service_years_source=sources[2],
        runtime=_retirement_runtime(*sources, chunk=True),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == "db_retirement_benefit"
    assert calculation["outputs"] == {
        "average_daily_wage": "100000",
        "average_wage_30_days": "3000000",
        "verified_service_years": "3.5",
        "retirement_benefit": "10500000.0",
    }
    assert set(calculation["inputs"]) == set(calculation["input_sources"])
    assert {source["origin"] for source in calculation["input_sources"].values()} == {"evidence"}


@pytest.mark.anyio
async def test_db_retirement_benefit_tool_allows_zero_and_shared_source() -> None:
    shared = "최근 3개월 임금 합계는 0원, 평균임금 산정 포함 일수는 90일, 검증된 근속연수는 0년이다"
    result = await create_db_retirement_benefit_tool().coroutine(
        wages_for_average_period_krw=Decimal(0),
        included_days_for_average_wage=90,
        verified_service_years=Decimal(0),
        wages_for_average_period_krw_source=shared,
        included_days_for_average_wage_source=shared,
        verified_service_years_source=shared,
        runtime=_retirement_runtime(shared),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["inputs"]["wages_for_average_period_krw"] == "0"
    assert calculation["inputs"]["verified_service_years"] == "0"
    assert calculation["outputs"]["retirement_benefit"] == "0"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "source"),
    [
        ("wages_for_average_period_krw_source", "연간임금총액 9,000,000원"),
        ("wages_for_average_period_krw_source", "최근 3개월 계좌입금액 9,000,000원"),
        ("included_days_for_average_wage_source", "휴직 90일"),
        ("included_days_for_average_wage_source", "최근 3개월은 약 90일"),
        ("verified_service_years_source", "근속연수 3.5년 이상"),
        ("verified_service_years_source", "근속연수 약 3.5년"),
        ("verified_service_years_source", "근속연수 3.5년이 아니다"),
        ("verified_service_years_source", "배우자 근속연수 3.5년"),
    ],
)
async def test_db_retirement_benefit_tool_rejects_semantic_or_non_exact_sources(
    field: str, source: str
) -> None:
    inputs: dict[str, object] = {
        "wages_for_average_period_krw": Decimal(9_000_000),
        "included_days_for_average_wage": 90,
        "verified_service_years": Decimal("3.5"),
        "wages_for_average_period_krw_source": _DB_WAGES_SOURCE,
        "included_days_for_average_wage_source": _DB_DAYS_SOURCE,
        "verified_service_years_source": _SERVICE_YEARS_SOURCE,
    }
    inputs[field] = source
    result = await create_db_retirement_benefit_tool().coroutine(
        **inputs,
        runtime=_retirement_runtime(*_source_values(inputs)),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("wages", "source", "expected"),
    [
        (Decimal(48_000_000), _DC_ANNUAL_WAGES_SOURCE, "4000000"),
        (Decimal(0), "연간임금총액은 0원", "0"),
    ],
)
async def test_dc_minimum_contribution_tool_preserves_rules_result(
    wages: Decimal, source: str, expected: str
) -> None:
    result = await create_dc_minimum_employer_contribution_tool().coroutine(
        annual_total_wages_krw=wages,
        annual_total_wages_krw_source=source,
        runtime=_retirement_runtime(source, chunk=True),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["outputs"]["minimum_employer_contribution"] == expected
    assert calculation["input_sources"]["annual_total_wages_krw"]["origin"] == "evidence"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "source",
    [
        "최근 3개월 임금 합계 48,000,000원",
        "월급 48,000,000원",
        "직전연도 연간임금총액 48,000,000원",
        "DC 누적 부담금 48,000,000원",
        "연간임금총액 약 48,000,000원",
        "연간임금총액 48,000,000원 이상",
        "연간임금총액 48,000,000원이 아니다",
    ],
)
async def test_dc_minimum_contribution_tool_rejects_wrong_wage_meaning(source: str) -> None:
    result = await create_dc_minimum_employer_contribution_tool().coroutine(
        annual_total_wages_krw=Decimal(48_000_000),
        annual_total_wages_krw_source=source,
        runtime=_retirement_runtime(source),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("gain_loss", "gain_source", "expected"),
    [
        (Decimal(1_000_000), _DC_GAIN_SOURCE, "11000000"),
        (Decimal(0), "누적 운용손익 0원", "10000000"),
        (Decimal(-1_000_000), "누적 운용손실 1,000,000원", "9000000"),
        (Decimal(-11_000_000), "누적 운용손익 -11,000,000원", "-1000000"),
    ],
)
async def test_dc_retirement_benefit_tool_preserves_signed_rules_result(
    gain_loss: Decimal, gain_source: str, expected: str
) -> None:
    sources = (_DC_CONTRIBUTIONS_SOURCE, gain_source)
    result = await create_dc_retirement_benefit_tool().coroutine(
        accumulated_contributions_krw=Decimal(10_000_000),
        investment_gain_loss_krw=gain_loss,
        accumulated_contributions_krw_source=sources[0],
        investment_gain_loss_krw_source=sources[1],
        runtime=_retirement_runtime(*sources, chunk=True),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["outputs"]["retirement_benefit"] == expected
    assert set(calculation["inputs"]) == set(calculation["input_sources"])


@pytest.mark.anyio
async def test_dc_retirement_benefit_tool_allows_explicit_zero_and_shared_source() -> None:
    shared = "DC 실제 누적 부담금 0원, 누적 운용손익 0원"
    result = await create_dc_retirement_benefit_tool().coroutine(
        accumulated_contributions_krw=Decimal(0),
        investment_gain_loss_krw=Decimal(0),
        accumulated_contributions_krw_source=shared,
        investment_gain_loss_krw_source=shared,
        runtime=_retirement_runtime(shared),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["inputs"]["accumulated_contributions_krw"] == "0"
    assert calculation["inputs"]["investment_gain_loss_krw"] == "0"
    assert calculation["outputs"]["retirement_benefit"] == "0"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "source"),
    [
        ("accumulated_contributions_krw_source", "DC 현재 계좌잔액 10,000,000원"),
        ("accumulated_contributions_krw_source", "DC 최소 사용자 부담금 10,000,000원"),
        ("investment_gain_loss_krw_source", "운용수익률 -5%"),
        ("investment_gain_loss_krw_source", "예상 운용손실 1,000,000원"),
        ("investment_gain_loss_krw_source", "운용손실이 없다"),
        ("investment_gain_loss_krw_source", "금액 -1,000,000원"),
    ],
)
async def test_dc_retirement_benefit_tool_rejects_wrong_meaning(field: str, source: str) -> None:
    inputs: dict[str, object] = {
        "accumulated_contributions_krw": Decimal(10_000_000),
        "investment_gain_loss_krw": Decimal(-1_000_000),
        "accumulated_contributions_krw_source": _DC_CONTRIBUTIONS_SOURCE,
        "investment_gain_loss_krw_source": "누적 운용손실 1,000,000원",
    }
    inputs[field] = source
    result = await create_dc_retirement_benefit_tool().coroutine(
        **inputs,
        runtime=_retirement_runtime(*_source_values(inputs)),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_dc_retirement_benefit_rejects_one_unqualified_shared_number() -> None:
    shared = "DC 퇴직급여 관련 금액 10,000,000원"
    result = await create_dc_retirement_benefit_tool().coroutine(
        accumulated_contributions_krw=Decimal(10_000_000),
        investment_gain_loss_krw=Decimal(10_000_000),
        accumulated_contributions_krw_source=shared,
        investment_gain_loss_krw_source=shared,
        runtime=_retirement_runtime(shared),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("annual_wages", "expected_basis", "basis_type", "transfer"),
    [
        (Decimal(36_000_000), "4000000", "average_wage_30_days", "14000000.0"),
        (Decimal(60_000_000), "5000000", "annual_wage_monthly_basis", "17500000.0"),
        (Decimal(48_000_000), "4000000", "equal", "14000000.0"),
    ],
)
async def test_db_to_dc_transfer_tool_preserves_basis_selection(
    annual_wages: Decimal, expected_basis: str, basis_type: str, transfer: str
) -> None:
    annual_source = f"DB→DC 전환 기준 최종 연간임금총액 {annual_wages}원"
    sources = (_FINAL_AVERAGE_WAGE_SOURCE, annual_source, _SERVICE_YEARS_SOURCE)
    result = await create_db_to_dc_transfer_amount_tool().coroutine(
        final_average_wage_30_days_krw=Decimal(4_000_000),
        final_annual_total_wages_krw=annual_wages,
        verified_service_years=Decimal("3.5"),
        final_average_wage_30_days_krw_source=sources[0],
        final_annual_total_wages_krw_source=sources[1],
        verified_service_years_source=sources[2],
        runtime=_retirement_runtime(*sources, chunk=True),
    )

    assert isinstance(result, Command)
    outputs = result.update["calculations"][0]["outputs"]
    assert outputs["selected_basis"] == expected_basis
    assert outputs["selected_basis_type"] == basis_type
    assert outputs["transfer_amount"] == transfer


@pytest.mark.anyio
async def test_db_to_dc_transfer_tool_allows_fully_qualified_shared_source() -> None:
    shared = (
        "DB→DC 전환 기준 최종 30일 평균임금 4,000,000원, "
        "DB→DC 전환 기준 최종 연간임금총액 48,000,000원, 검증된 근속연수 3.5년"
    )
    result = await create_db_to_dc_transfer_amount_tool().coroutine(
        final_average_wage_30_days_krw=Decimal(4_000_000),
        final_annual_total_wages_krw=Decimal(48_000_000),
        verified_service_years=Decimal("3.5"),
        final_average_wage_30_days_krw_source=shared,
        final_annual_total_wages_krw_source=shared,
        verified_service_years_source=shared,
        runtime=_retirement_runtime(shared),
    )

    assert isinstance(result, Command)
    assert result.update["calculations"][0]["outputs"]["selected_basis_type"] == "equal"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "source"),
    [
        ("final_average_wage_30_days_krw_source", "일반 월급 4,000,000원"),
        ("final_average_wage_30_days_krw_source", "전환 기준 평균일급 4,000,000원"),
        ("final_average_wage_30_days_krw_source", "과거 최종 30일 평균임금 4,000,000원"),
        ("final_annual_total_wages_krw_source", "최근 3개월 임금 60,000,000원"),
        ("final_annual_total_wages_krw_source", "최종 연간임금총액 60,000,000원"),
        ("verified_service_years_source", "근속연수 3~4년"),
        ("verified_service_years_source", "근속연수 3.5년 이상"),
    ],
)
async def test_db_to_dc_transfer_tool_rejects_wrong_or_non_exact_sources(
    field: str, source: str
) -> None:
    inputs: dict[str, object] = {
        "final_average_wage_30_days_krw": Decimal(4_000_000),
        "final_annual_total_wages_krw": Decimal(60_000_000),
        "verified_service_years": Decimal("3.5"),
        "final_average_wage_30_days_krw_source": _FINAL_AVERAGE_WAGE_SOURCE,
        "final_annual_total_wages_krw_source": _FINAL_ANNUAL_WAGES_SOURCE,
        "verified_service_years_source": _SERVICE_YEARS_SOURCE,
    }
    inputs[field] = source
    result = await create_db_to_dc_transfer_amount_tool().coroutine(
        **inputs,
        runtime=_retirement_runtime(*_source_values(inputs)),
    )

    assert isinstance(result, str)
    assert "출처" in result


_EXEC_SALARY_2012_2019_SOURCE = "2012년부터 2019년까지 총급여 연평균 환산액 100,000,000원"
_EXEC_MONTHS_2012_2019_SOURCE = "2012년부터 2019년까지 근무월수 96개월"
_EXEC_SALARY_2020_ONWARD_SOURCE = "2020년 이후 총급여 연평균 환산액 120,000,000원"
_EXEC_MONTHS_2020_ONWARD_SOURCE = "2020년 이후 근무월수 60개월"
_EXEC_PAYMENT_SOURCE = "2012년 이후 한도 적용대상 지급액 400,000,000원"


@pytest.mark.anyio
async def test_executive_retirement_income_limit_tool_sums_both_periods_and_splits_payment() -> (
    None
):
    sources = (
        _EXEC_SALARY_2012_2019_SOURCE,
        _EXEC_MONTHS_2012_2019_SOURCE,
        _EXEC_SALARY_2020_ONWARD_SOURCE,
        _EXEC_MONTHS_2020_ONWARD_SOURCE,
        _EXEC_PAYMENT_SOURCE,
    )
    result = await create_executive_retirement_income_limit_tool().coroutine(
        average_annualized_salary_2012_2019_krw=Decimal(100_000_000),
        average_annualized_salary_2012_2019_source=_EXEC_SALARY_2012_2019_SOURCE,
        service_months_2012_2019=96,
        service_months_2012_2019_source=_EXEC_MONTHS_2012_2019_SOURCE,
        average_annualized_salary_2020_onward_krw=Decimal(120_000_000),
        average_annualized_salary_2020_onward_source=_EXEC_SALARY_2020_ONWARD_SOURCE,
        service_months_2020_onward=60,
        service_months_2020_onward_source=_EXEC_MONTHS_2020_ONWARD_SOURCE,
        post_2011_limit_subject_payment_krw=Decimal(400_000_000),
        post_2011_limit_subject_payment_source=_EXEC_PAYMENT_SOURCE,
        runtime=_retirement_runtime(*sources, chunk=True),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == "executive_retirement_income_limit"
    assert calculation["outputs"] == {
        "limit_2012_2019_krw": "240000000.0",
        "limit_2020_onward_krw": "120000000.0",
        "post_2011_total_limit_krw": "360000000.0",
        "retirement_income_amount_krw": "360000000.0",
        "wage_income_excess_krw": "40000000.0",
    }
    assert calculation["input_sources"]["post_2011_limit_subject_payment_krw"] == {
        "origin": "evidence",
        "text": _EXEC_PAYMENT_SOURCE,
        "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
    }


@pytest.mark.anyio
async def test_executive_retirement_income_limit_tool_allows_single_period() -> None:
    result = await create_executive_retirement_income_limit_tool().coroutine(
        average_annualized_salary_2020_onward_krw=Decimal(120_000_000),
        average_annualized_salary_2020_onward_source=_EXEC_SALARY_2020_ONWARD_SOURCE,
        service_months_2020_onward=60,
        service_months_2020_onward_source=_EXEC_MONTHS_2020_ONWARD_SOURCE,
        runtime=_retirement_runtime(
            _EXEC_SALARY_2020_ONWARD_SOURCE, _EXEC_MONTHS_2020_ONWARD_SOURCE, chunk=True
        ),
    )

    assert isinstance(result, Command)
    outputs = result.update["calculations"][0]["outputs"]
    assert outputs["limit_2012_2019_krw"] == "0"
    assert outputs["limit_2020_onward_krw"] == "120000000.0"
    assert "retirement_income_amount_krw" not in outputs
    assert "wage_income_excess_krw" not in outputs


@pytest.mark.anyio
async def test_executive_retirement_income_limit_tool_requires_value_and_source_together() -> None:
    result = await create_executive_retirement_income_limit_tool().coroutine(
        average_annualized_salary_2012_2019_krw=Decimal(100_000_000),
        average_annualized_salary_2012_2019_source=None,
        service_months_2012_2019=96,
        service_months_2012_2019_source=_EXEC_MONTHS_2012_2019_SOURCE,
        runtime=_retirement_runtime(_EXEC_MONTHS_2012_2019_SOURCE),
    )

    assert isinstance(result, str)
    assert "함께" in result


@pytest.mark.anyio
async def test_executive_retirement_income_limit_tool_surfaces_rules_period_pairing_error() -> None:
    """급여만 있고 근무월수 전체가 생략되면 Rules의 기간 쌍 검증 오류가 그대로 전달된다."""

    result = await create_executive_retirement_income_limit_tool().coroutine(
        average_annualized_salary_2012_2019_krw=Decimal(100_000_000),
        average_annualized_salary_2012_2019_source=_EXEC_SALARY_2012_2019_SOURCE,
        runtime=_retirement_runtime(_EXEC_SALARY_2012_2019_SOURCE),
    )

    assert isinstance(result, str)
    assert "error" in result


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "source"),
    [
        (
            "average_annualized_salary_2012_2019_source",
            "2020년 이후 총급여 연평균 환산액 100,000,000원",
        ),
        (
            "average_annualized_salary_2012_2019_source",
            "2012년부터 2019년까지 월급 100,000,000원",
        ),
        (
            "average_annualized_salary_2012_2019_source",
            "2012년부터 2019년까지 퇴직급여 연평균 환산액 100,000,000원",
        ),
        (
            "service_months_2012_2019_source",
            "2012년부터 2019년까지 근무기간 8년",
        ),
        (
            "service_months_2012_2019_source",
            "2012년부터 2019년까지 근무월수 약 96개월",
        ),
        (
            "service_months_2012_2019_source",
            "2020년 이후 근무월수 96개월",
        ),
        (
            "post_2011_limit_subject_payment_source",
            "퇴직금 400,000,000원",
        ),
        (
            "post_2011_limit_subject_payment_source",
            "2012년 이후 한도 적용대상 지급액 최대 400,000,000원",
        ),
    ],
)
async def test_executive_retirement_income_limit_tool_rejects_wrong_or_non_exact_sources(
    field: str, source: str
) -> None:
    inputs: dict[str, object] = {
        "average_annualized_salary_2012_2019_krw": Decimal(100_000_000),
        "average_annualized_salary_2012_2019_source": _EXEC_SALARY_2012_2019_SOURCE,
        "service_months_2012_2019": 96,
        "service_months_2012_2019_source": _EXEC_MONTHS_2012_2019_SOURCE,
        "post_2011_limit_subject_payment_krw": Decimal(400_000_000),
        "post_2011_limit_subject_payment_source": _EXEC_PAYMENT_SOURCE,
    }
    inputs[field] = source
    result = await create_executive_retirement_income_limit_tool().coroutine(
        **inputs,
        runtime=_retirement_runtime(*_source_values(inputs)),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
async def test_medical_care_limit_tool_calculates_and_preserves_sources() -> None:
    inputs = _medical_limit_tool_inputs()
    result = await create_medical_care_withdrawal_tax_limit_tool().coroutine(
        **inputs,
        runtime=_medical_care_runtime(*_source_values(inputs)),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == "medical_care_withdrawal_tax_limit"
    assert calculation["outputs"] == {
        "tax_limit_krw": "2750000",
        "amount_within_limit_krw": "2750000",
        "excess_amount_krw": "250000",
    }
    assert set(calculation["inputs"]) == set(calculation["input_sources"])


@pytest.mark.anyio
async def test_medical_care_limit_allows_shared_source_with_each_meaning_and_value() -> None:
    shared = "의료·요양 총 인출 요청액 300만원, 실제 의료비 50만원, 간병비 25만원, 본인 휴직 2개월"
    result = await create_medical_care_withdrawal_tax_limit_tool().coroutine(
        requested_withdrawal_krw=Decimal(3_000_000),
        actual_medical_expenses_krw=Decimal(500_000),
        care_expenses_krw=Decimal(250_000),
        own_leave_months=2,
        requested_withdrawal_krw_source=shared,
        actual_medical_expenses_krw_source=shared,
        care_expenses_krw_source=shared,
        own_leave_months_source=shared,
        runtime=_medical_care_runtime(shared),
    )

    assert isinstance(result, Command)
    assert result.update["calculations"][0]["outputs"]["tax_limit_krw"] == "5750000"


@pytest.mark.anyio
async def test_medical_care_limit_preserves_explicit_zero_sources() -> None:
    inputs = _medical_limit_tool_inputs(
        actual_medical_expenses_krw=Decimal(0),
        care_expenses_krw=Decimal(0),
        actual_medical_expenses_krw_source="실제 의료비 없음",
        care_expenses_krw_source="간병비 0원",
        own_leave_months_source="본인 휴직 없음",
    )
    result = await create_medical_care_withdrawal_tax_limit_tool().coroutine(
        **inputs,
        runtime=_medical_care_runtime(*_source_values(inputs)),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["inputs"]["actual_medical_expenses_krw"] == "0"
    assert calculation["inputs"]["care_expenses_krw"] == "0"
    assert calculation["inputs"]["own_leave_months"] == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "source"),
    [
        ("requested_withdrawal_krw_source", "계좌 전체 잔액 300만원"),
        ("requested_withdrawal_krw_source", "실제 의료비 300만원"),
        ("actual_medical_expenses_krw_source", "의료·요양 총 인출 요청액 50만원"),
        ("actual_medical_expenses_krw_source", "간병비 50만원"),
        ("care_expenses_krw_source", "실제 의료비 25만원"),
        ("own_leave_months_source", "가족 휴직 0개월"),
        ("own_leave_months_source", "본인 요양기간 0개월"),
        ("own_leave_months_source", "본인 휴직이 아님 0개월"),
    ],
)
async def test_medical_care_limit_rejects_provenance_mismatch(field: str, source: str) -> None:
    inputs = _medical_limit_tool_inputs(**{field: source})
    result = await create_medical_care_withdrawal_tax_limit_tool().coroutine(
        **inputs,
        runtime=_medical_care_runtime(*_source_values(inputs)),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("requested", "age", "expected_tax", "expect_null"),
    [
        (Decimal(2_750_000), 69, "151250.000", False),
        (Decimal(3_000_000), 70, "121000.000", True),
    ],
)
async def test_medical_care_breakdown_preserves_rules_results_and_warnings(
    requested: Decimal, age: int, expected_tax: str, expect_null: bool
) -> None:
    inputs = _medical_limit_tool_inputs(
        requested_withdrawal_krw=requested,
        requested_withdrawal_krw_source=f"의료·요양 총 인출 요청액 {requested}원",
    )
    result = await create_medical_care_withdrawal_tax_breakdown_tool().coroutine(
        **inputs,
        recipient_age=age,
        recipient_age_source=f"수령자 나이 {age}세",
        runtime=_medical_care_runtime(*_source_values(inputs), f"수령자 나이 {age}세", chunk=True),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == "medical_care_withdrawal_tax_breakdown"
    assert calculation["outputs"]["within_limit_tax_krw"] == expected_tax
    assert (calculation["outputs"]["current_withdrawal_tax_krw"] is None) is expect_null
    assert (calculation["outputs"]["current_withdrawal_after_tax_krw"] is None) is expect_null
    assert set(calculation["inputs"]) == set(calculation["input_sources"])
    if expect_null:
        assert "초과액" in " ".join(calculation["warnings"])


@pytest.mark.anyio
@pytest.mark.parametrize(
    "age_source",
    ["수령자 나이 70대", "수령자 나이 약 70세", "수령자 나이 70세 이상", "배우자 나이 70세"],
)
async def test_medical_care_breakdown_rejects_non_exact_or_other_person_age(
    age_source: str,
) -> None:
    inputs = _medical_limit_tool_inputs()
    result = await create_medical_care_withdrawal_tax_breakdown_tool().coroutine(
        **inputs,
        recipient_age=70,
        recipient_age_source=age_source,
        runtime=_medical_care_runtime(*_source_values(inputs), age_source),
    )

    assert isinstance(result, str)
    assert "출처" in result


@pytest.mark.parametrize(
    ("field", "bad_source"),
    [
        ("requested_withdrawal_krw_source", "현재 비과세 재원 잔액 600만원"),
        ("tax_free_source_balance_krw_source", "현재 인출 요청액 100만원"),
        ("deferred_retirement_source_balance_krw_source", "비과세 재원의 현재 잔액 200만원"),
        ("credited_and_earnings_source_balance_krw_source", "이연퇴직소득 현재 잔액 500만원"),
    ],
)
@pytest.mark.anyio
async def test_withdrawal_allocation_tool_rejects_misassigned_meaning(
    field: str, bad_source: str
) -> None:
    sources = {**_WITHDRAWAL_SOURCES, field: bad_source}
    result = await create_pension_withdrawal_allocation_tool().coroutine(
        **_WITHDRAWAL_VALUES,
        **sources,
        runtime=_withdrawal_runtime(*sources.values()),
    )
    assert isinstance(result, str)
    assert "error" in result


@pytest.mark.anyio
async def test_withdrawal_allocation_tool_rejects_reused_or_multi_value_source() -> None:
    reused = {
        **_WITHDRAWAL_SOURCES,
        "deferred_retirement_source_balance_krw_source": (
            _WITHDRAWAL_SOURCES["tax_free_source_balance_krw_source"]
        ),
    }
    result = await create_pension_withdrawal_allocation_tool().coroutine(
        **_WITHDRAWAL_VALUES,
        **reused,
        runtime=_withdrawal_runtime(*reused.values()),
    )
    assert isinstance(result, str)

    combined = {
        **_WITHDRAWAL_SOURCES,
        "tax_free_source_balance_krw_source": (
            "세액공제 미적용 원금 비과세 재원의 현재 잔액 100만원과 200만원"
        ),
    }
    result = await create_pension_withdrawal_allocation_tool().coroutine(
        **_WITHDRAWAL_VALUES,
        **combined,
        runtime=_withdrawal_runtime(*combined.values()),
    )
    assert isinstance(result, str)


@pytest.mark.anyio
async def test_withdrawal_tax_breakdown_tool_calculates_all_paths() -> None:
    optional = _breakdown_optional()
    result = await create_pension_withdrawal_tax_breakdown_tool().coroutine(
        **_BREAKDOWN_VALUES,
        **_BREAKDOWN_SOURCES,
        **optional,
        runtime=_withdrawal_runtime(*_BREAKDOWN_SOURCES.values(), *_optional_sources(optional)),
    )
    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == "pension_withdrawal_tax_breakdown"
    assert calculation["outputs"]["tax_free_pension_tax_krw"] == "0"
    assert calculation["outputs"]["current_withdrawal_tax_krw"] == "1085000.000"
    assert set(calculation["input_sources"]) == set(calculation["inputs"])


@pytest.mark.anyio
async def test_withdrawal_tax_breakdown_preserves_unknown_annual_nulls() -> None:
    optional = _breakdown_optional(annual=None)
    result = await create_pension_withdrawal_tax_breakdown_tool().coroutine(
        **_BREAKDOWN_VALUES,
        **_BREAKDOWN_SOURCES,
        **optional,
        runtime=_withdrawal_runtime(*_BREAKDOWN_SOURCES.values(), *_optional_sources(optional)),
    )
    assert isinstance(result, Command)
    outputs = result.update["calculations"][0]["outputs"]
    assert outputs["credited_and_earnings_pension_tax_krw"] is None
    assert outputs["current_withdrawal_tax_krw"] is None


@pytest.mark.anyio
async def test_withdrawal_tax_breakdown_preserves_separate_tax_option() -> None:
    optional = _breakdown_optional(Decimal(15_000_001))
    result = await create_pension_withdrawal_tax_breakdown_tool().coroutine(
        **_BREAKDOWN_VALUES,
        **_BREAKDOWN_SOURCES,
        **optional,
        runtime=_withdrawal_runtime(*_BREAKDOWN_SOURCES.values(), *_optional_sources(optional)),
    )
    assert isinstance(result, Command)
    outputs = result.update["calculations"][0]["outputs"]
    assert outputs["current_withdrawal_tax_krw"] is None
    assert outputs["annual_private_pension_separate_tax_option_tax_krw"] == "2475000.165"


@pytest.mark.anyio
async def test_withdrawal_tax_breakdown_rejects_optional_half_pair_and_rules_omission() -> None:
    half_pair = await create_pension_withdrawal_tax_breakdown_tool().coroutine(
        **_BREAKDOWN_VALUES,
        **_BREAKDOWN_SOURCES,
        recipient_age=65,
        runtime=_withdrawal_runtime(*_BREAKDOWN_SOURCES.values()),
    )
    assert isinstance(half_pair, str)

    missing = await create_pension_withdrawal_tax_breakdown_tool().coroutine(
        **_BREAKDOWN_VALUES,
        **_BREAKDOWN_SOURCES,
        runtime=_withdrawal_runtime(*_BREAKDOWN_SOURCES.values()),
    )
    assert isinstance(missing, str)
    assert "error" in missing


@pytest.mark.parametrize(
    ("field", "value", "source"),
    [
        ("actual_pension_receipt_year", 10, "연금수령연차 10년차"),
        ("recipient_age", 55, "수령자 나이 55세 미만"),
        ("is_lifetime_annuity", True, "종신연금에 해당하지 않음"),
    ],
)
@pytest.mark.anyio
async def test_withdrawal_tax_breakdown_reuses_strict_existing_provenance(
    field: str, value: Any, source: str
) -> None:
    optional = _breakdown_optional()
    optional[field] = value
    optional[f"{field}_source"] = source
    result = await create_pension_withdrawal_tax_breakdown_tool().coroutine(
        **_BREAKDOWN_VALUES,
        **_BREAKDOWN_SOURCES,
        **optional,
        runtime=_withdrawal_runtime(*_BREAKDOWN_SOURCES.values(), *_optional_sources(optional)),
    )
    assert isinstance(result, str)
    assert "error" in result


@pytest.mark.anyio
async def test_withdrawal_tax_breakdown_rejects_treatment_mixup_and_annual_reuse() -> None:
    mixed = {
        **_BREAKDOWN_SOURCES,
        "pension_treated_withdrawal_krw_source": (
            _BREAKDOWN_SOURCES["non_pension_treated_withdrawal_krw_source"]
        ),
    }
    result = await create_pension_withdrawal_tax_breakdown_tool().coroutine(
        **_BREAKDOWN_VALUES,
        **mixed,
        runtime=_withdrawal_runtime(*mixed.values()),
    )
    assert isinstance(result, str)

    optional = _breakdown_optional()
    optional["annual_private_pension_taxable_income_krw"] = Decimal(4_000_000)
    optional["annual_private_pension_taxable_income_krw_source"] = _BREAKDOWN_SOURCES[
        "pension_treated_withdrawal_krw_source"
    ]
    result = await create_pension_withdrawal_tax_breakdown_tool().coroutine(
        **_BREAKDOWN_VALUES,
        **_BREAKDOWN_SOURCES,
        **optional,
        runtime=_withdrawal_runtime(*_BREAKDOWN_SOURCES.values(), *_optional_sources(optional)),
    )
    assert isinstance(result, str)


@pytest.mark.anyio
async def test_withdrawal_tax_breakdown_rejects_whole_account_allocated_tax() -> None:
    optional = _breakdown_optional()
    optional["pension_treated_allocated_deferred_retirement_tax_krw_source"] = (
        "계좌 전체 연금수령 처리 이연퇴직소득세 100만원"
    )
    result = await create_pension_withdrawal_tax_breakdown_tool().coroutine(
        **_BREAKDOWN_VALUES,
        **_BREAKDOWN_SOURCES,
        **optional,
        runtime=_withdrawal_runtime(*_BREAKDOWN_SOURCES.values(), *_optional_sources(optional)),
    )
    assert isinstance(result, str)
    assert "error" in result


@pytest.mark.anyio
async def test_withdrawal_tax_breakdown_returns_rules_error_for_treatment_sum() -> None:
    optional = _breakdown_optional()
    values = {
        **_BREAKDOWN_VALUES,
        "non_pension_treated_withdrawal_krw": Decimal(1_000_000),
    }
    sources = {
        **_BREAKDOWN_SOURCES,
        "non_pension_treated_withdrawal_krw_source": (
            "현재 요청 중 연금외수령으로 처리되는 금액 100만원"
        ),
    }
    result = await create_pension_withdrawal_tax_breakdown_tool().coroutine(
        **values,
        **sources,
        **optional,
        runtime=_withdrawal_runtime(*sources.values(), *_optional_sources(optional)),
    )
    assert isinstance(result, str)
    assert "error" in result


@pytest.mark.anyio
async def test_withdrawal_tax_breakdown_separates_two_allocated_tax_sources() -> None:
    values = {
        **_BREAKDOWN_VALUES,
        "requested_withdrawal_krw": Decimal(4_000_000),
        "pension_treated_withdrawal_krw": Decimal(2_000_000),
        "non_pension_treated_withdrawal_krw": Decimal(2_000_000),
    }
    sources = {
        **_BREAKDOWN_SOURCES,
        "requested_withdrawal_krw_source": "현재 인출 요청액 400만원",
        "pension_treated_withdrawal_krw_source": (
            "현재 요청 중 연금수령으로 처리되는 금액 200만원"
        ),
    }
    optional: dict[str, Any] = {
        "actual_pension_receipt_year": 10,
        "actual_pension_receipt_year_source": "실제수령연차 10년차",
        "pension_treated_allocated_deferred_retirement_tax_krw": Decimal(500_000),
        "pension_treated_allocated_deferred_retirement_tax_krw_source": (
            "해당 인출분에 배분된 연금수령 처리 이연퇴직소득세 50만원"
        ),
        "non_pension_treated_allocated_deferred_retirement_tax_krw": Decimal(600_000),
        "non_pension_treated_allocated_deferred_retirement_tax_krw_source": (
            "해당 인출분에 배분된 연금외수령 처리 이연퇴직소득세 60만원"
        ),
    }
    result = await create_pension_withdrawal_tax_breakdown_tool().coroutine(
        **values,
        **sources,
        **optional,
        runtime=_withdrawal_runtime(*sources.values(), *_optional_sources(optional)),
    )
    assert isinstance(result, Command)

    duplicated = dict(optional)
    duplicated["non_pension_treated_allocated_deferred_retirement_tax_krw"] = Decimal(500_000)
    duplicated["non_pension_treated_allocated_deferred_retirement_tax_krw_source"] = optional[
        "pension_treated_allocated_deferred_retirement_tax_krw_source"
    ]
    result = await create_pension_withdrawal_tax_breakdown_tool().coroutine(
        **values,
        **sources,
        **duplicated,
        runtime=_withdrawal_runtime(*sources.values(), *_optional_sources(duplicated)),
    )
    assert isinstance(result, str)
    assert "error" in result
