"""원문 검증을 거쳐 등록한 초기 계산 함수의 산식과 경계값을 확인한다."""

from decimal import Decimal

import pytest

from pension_agent.rules import (
    CalculationRequest,
    InvalidCalculationInputError,
    calculate,
)
from pension_agent.rules.calculators import CALCULATORS
from pension_agent.rules.calculators.fund_var_risk import classify_var_risk_grade


def test_calculator_map_contains_registered_set() -> None:
    assert CALCULATORS.keys() == {
        "db_retirement_benefit",
        "db_to_dc_transfer_amount",
        "deferred_retirement_withdrawal_tax",
        "dc_medical_withdrawal_threshold",
        "dc_minimum_employer_contribution",
        "dc_retirement_benefit",
        "fund_reported_var_risk",
        "fund_standard_price",
        "fund_var_risk",
        "medical_care_withdrawal_tax_breakdown",
        "medical_care_withdrawal_tax_limit",
        "non_pension_withdrawal_tax",
        "pension_annual_limit_installment",
        "pension_income_tax",
        "pension_period_installment",
        "pension_tax_credit",
        "pension_unit_installment",
        "pension_withdrawal_limit",
        "pension_withdrawal_allocation",
        "pension_withdrawal_tax_breakdown",
    }


@pytest.mark.parametrize(
    ("pension_year", "expected"),
    [(1, Decimal(12_000_000)), (6, Decimal(24_000_000)), (10, Decimal(120_000_000))],
)
def test_pension_withdrawal_limit_formula(pension_year: int, expected: Decimal) -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="pension_withdrawal_limit",
            inputs={"account_valuation_krw": 100_000_000, "pension_year": pension_year},
        )
    )

    assert result.outputs == {"withdrawal_limit": expected, "limit_applies": True}
    assert result.units == {"withdrawal_limit": "KRW"}


def test_pension_withdrawal_limit_rejects_zero_year() -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(
            CalculationRequest(
                calculator_id="pension_withdrawal_limit",
                inputs={"account_valuation_krw": 100_000_000, "pension_year": 0},
            )
        )


def test_fund_standard_price_formula_and_rounding() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="fund_standard_price",
            inputs={
                "total_assets_krw": "1.235",
                "total_liabilities_krw": 0,
                "total_units": 1000,
            },
        )
    )

    assert result.outputs == {"standard_price_per_1000_units": Decimal("1.24")}
    assert result.units == {"standard_price_per_1000_units": "KRW/1,000 units"}


@pytest.mark.parametrize(
    "inputs",
    [
        {"total_assets_krw": 1, "total_liabilities_krw": 2, "total_units": 1},
        {"total_assets_krw": 1, "total_liabilities_krw": 0, "total_units": 0},
    ],
)
def test_fund_standard_price_rejects_invalid_balance_or_units(
    inputs: dict[str, int],
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(CalculationRequest(calculator_id="fund_standard_price", inputs=inputs))


@pytest.mark.parametrize(
    ("annualized_var", "grade"),
    [
        (Decimal("50.0001"), 1),
        (Decimal(50), 2),
        (Decimal(30), 3),
        (Decimal(20), 4),
        (Decimal(10), 5),
        (Decimal(1), 6),
        (Decimal(0), 6),
    ],
)
def test_var_risk_grade_boundaries(annualized_var: Decimal, grade: int) -> None:
    assert classify_var_risk_grade(annualized_var) == grade


def test_fund_var_uses_absolute_loss_and_returns_grade() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="fund_var_risk",
            inputs={"daily_loss_percentile_percent": "-1"},
        )
    )

    assert result.outputs["annualized_var_percent"] == Decimal(250).sqrt()
    assert result.outputs["risk_grade"] == 4
    assert result.outputs["risk_label"] == "보통 위험"


def test_initial_calculators_are_json_serializable_without_binary_float() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="pension_withdrawal_limit",
            inputs={"account_valuation_krw": "100000000", "pension_year": 1},
        )
    )

    payload = result.model_dump(mode="json")
    assert payload["inputs"]["account_valuation_krw"] == "100000000"
    assert payload["outputs"]["withdrawal_limit"] == "12000000.0"
