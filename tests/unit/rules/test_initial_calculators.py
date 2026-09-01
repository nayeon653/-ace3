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
        "executive_retirement_income_limit",
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


def test_executive_retirement_income_limit_sums_both_periods() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="executive_retirement_income_limit",
            inputs={
                "average_annualized_salary_2012_2019_krw": 100_000_000,
                "service_months_2012_2019": 96,
                "average_annualized_salary_2020_onward_krw": 120_000_000,
                "service_months_2020_onward": 60,
            },
        )
    )

    assert result.outputs == {
        "limit_2012_2019_krw": Decimal("240000000.0"),
        "limit_2020_onward_krw": Decimal("120000000.0"),
        "post_2011_total_limit_krw": Decimal("360000000.0"),
    }
    assert result.units == {
        "limit_2012_2019_krw": "KRW",
        "limit_2020_onward_krw": "KRW",
        "post_2011_total_limit_krw": "KRW",
    }


@pytest.mark.parametrize(
    ("period_inputs", "expected_present_zero_key"),
    [
        (
            {
                "average_annualized_salary_2012_2019_krw": 100_000_000,
                "service_months_2012_2019": 36,
            },
            "limit_2020_onward_krw",
        ),
        (
            {
                "average_annualized_salary_2020_onward_krw": 100_000_000,
                "service_months_2020_onward": 24,
            },
            "limit_2012_2019_krw",
        ),
    ],
)
def test_executive_retirement_income_limit_allows_single_period(
    period_inputs: dict[str, int], expected_present_zero_key: str
) -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="executive_retirement_income_limit",
            inputs=period_inputs,
        )
    )

    assert result.outputs[expected_present_zero_key] == Decimal(0)
    assert (
        result.outputs["post_2011_total_limit_krw"]
        == result.outputs["limit_2012_2019_krw"] + result.outputs["limit_2020_onward_krw"]
    )


def test_executive_retirement_income_limit_no_rounding_beyond_decimal_precision() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="executive_retirement_income_limit",
            inputs={
                "average_annualized_salary_2020_onward_krw": 100_000_000,
                "service_months_2020_onward": 5,
            },
        )
    )

    assert result.outputs["limit_2020_onward_krw"] == Decimal("8333333.333333333333333333334")


@pytest.mark.parametrize(
    "inputs",
    [
        {"average_annualized_salary_2012_2019_krw": 100_000_000},
        {"service_months_2012_2019": 12},
        {"average_annualized_salary_2020_onward_krw": 100_000_000},
        {"service_months_2020_onward": 12},
    ],
)
def test_executive_retirement_income_limit_requires_salary_and_months_together(
    inputs: dict[str, int],
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(
            CalculationRequest(
                calculator_id="executive_retirement_income_limit",
                inputs=inputs,
            )
        )


def test_executive_retirement_income_limit_requires_at_least_one_period() -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(
            CalculationRequest(
                calculator_id="executive_retirement_income_limit",
                inputs={"post_2011_limit_subject_payment_krw": 100_000_000},
            )
        )


@pytest.mark.parametrize(
    "inputs",
    [
        {"average_annualized_salary_2012_2019_krw": -1, "service_months_2012_2019": 12},
        {"average_annualized_salary_2012_2019_krw": 100, "service_months_2012_2019": -1},
        {
            "average_annualized_salary_2012_2019_krw": 100,
            "service_months_2012_2019": 12,
            "post_2011_limit_subject_payment_krw": -1,
        },
        {
            "average_annualized_salary_2012_2019_krw": None,
            "service_months_2012_2019": 12,
        },
    ],
)
def test_executive_retirement_income_limit_rejects_negative_and_null(
    inputs: dict[str, object],
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(
            CalculationRequest(
                calculator_id="executive_retirement_income_limit",
                inputs=inputs,
            )
        )


@pytest.mark.parametrize(
    ("payment", "expected_recognized", "expected_excess"),
    [
        (240_000_000, Decimal("240000000.0"), Decimal(0)),
        (100_000_000, Decimal("100000000.0"), Decimal(0)),
        (300_000_000, Decimal("240000000.0"), Decimal("60000000.0")),
    ],
)
def test_executive_retirement_income_limit_splits_payment_against_limit(
    payment: int, expected_recognized: Decimal, expected_excess: Decimal
) -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="executive_retirement_income_limit",
            inputs={
                "average_annualized_salary_2012_2019_krw": 100_000_000,
                "service_months_2012_2019": 96,
                "post_2011_limit_subject_payment_krw": payment,
            },
        )
    )

    assert result.outputs["retirement_income_amount_krw"] == expected_recognized
    assert result.outputs["wage_income_excess_krw"] == expected_excess


def test_executive_retirement_income_limit_omits_payment_outputs_without_payment() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="executive_retirement_income_limit",
            inputs={
                "average_annualized_salary_2012_2019_krw": 100_000_000,
                "service_months_2012_2019": 96,
            },
        )
    )

    assert "retirement_income_amount_krw" not in result.outputs
    assert "wage_income_excess_krw" not in result.outputs


def test_executive_retirement_income_limit_allows_zero_months() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="executive_retirement_income_limit",
            inputs={
                "average_annualized_salary_2012_2019_krw": 100_000_000,
                "service_months_2012_2019": 0,
            },
        )
    )

    assert result.outputs["limit_2012_2019_krw"] == Decimal(0)


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
