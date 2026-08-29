"""Domain Agent용 Calculation Tool 어댑터를 검증한다."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from langgraph.types import Command

from pension_agent.agent.calculation import (
    create_fund_standard_price_tool,
    create_fund_var_risk_tool,
    create_non_pension_withdrawal_tax_tool,
    create_pension_income_tax_tool,
    create_pension_tax_credit_tool,
    create_pension_withdrawal_limit_tool,
    format_calculation_summary,
)
from pension_agent.agent.calculation.input_sources import validated_input_sources
from pension_agent.agent.search import SearchResult


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
                "평가액 1천만원, 1년차, 자산총액 100만원, 부채총액 10만원, "
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
        pension_year_source="1년차",
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
        pension_year_source="1년차",
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
        pension_year_source="10년차",
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
        pension_year_source="수령연차 1년차",
        runtime=_runtime(
            question="연금수령한도를 계산해줘",
            chunk_content="평가액 1천만원, 수령연차 1년차에 대한 계산 규칙",
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
        pension_year_source="1년차",
        runtime=_runtime(),
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
        "연금수령 과세대상 금액 100만원; 연간 사적연금 과세대상 합계 1,000만원"
    )
    result = await create_pension_income_tax_tool().coroutine(
        pension_treatment="ordinary",
        recipient_age=55,
        pension_treatment_source="일반 연금수령",
        recipient_age_source="수령자 나이 55세",
        runtime=_runtime(question=question),
        target_taxable_amount_krw=Decimal(1_000_000),
        target_taxable_amount_krw_source="연금수령 과세대상 금액 100만원",
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
        "text": "연금수령 과세대상 금액 100만원",
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
            "연금수령 과세대상 금액 100만원",
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
