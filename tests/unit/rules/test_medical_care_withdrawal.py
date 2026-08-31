"""DC 의료비 기준과 의료·요양 인출 저율과세 계약을 검증한다."""

from decimal import Decimal

import pytest

from pension_agent.rules import CalculationRequest, InvalidCalculationInputError, calculate
from pension_agent.rules.calculators.pension_income_tax import (
    PensionIncomeTaxInput,
    calculate_pension_income_tax,
)


def _calculate(calculator_id: str, inputs: dict[str, object]):
    return calculate(CalculationRequest(calculator_id=calculator_id, inputs=inputs))


def _dc_inputs(**updates: object) -> dict[str, object]:
    inputs: dict[str, object] = {
        "employment_duration_category": "at_least_one_year",
        "documented_medical_expenses_krw": 12_500_001,
        "previous_year_annual_wages_krw": 100_000_000,
    }
    inputs.update(updates)
    return inputs


@pytest.mark.parametrize(
    ("updates", "expected_wages", "expected_basis"),
    [
        ({}, Decimal(100_000_000), "previous_year_annual_wages"),
        (
            {"preceding_12_month_wages_krw": 80_000_000},
            Decimal(80_000_000),
            "preceding_12_month_wages",
        ),
        (
            {"preceding_12_month_wages_krw": 120_000_000},
            Decimal(100_000_000),
            "previous_year_annual_wages",
        ),
        (
            {"preceding_12_month_wages_krw": 100_000_000},
            Decimal(100_000_000),
            "previous_year_annual_wages",
        ),
    ],
)
def test_dc_threshold_selects_wage_basis(
    updates: dict[str, object], expected_wages: Decimal, expected_basis: str
) -> None:
    result = _calculate("dc_medical_withdrawal_threshold", _dc_inputs(**updates))

    assert result.outputs["applicable_wages_krw"] == expected_wages
    assert result.outputs["wage_basis"] == expected_basis


def test_dc_threshold_annualizes_average_monthly_wage_under_one_year() -> None:
    result = _calculate(
        "dc_medical_withdrawal_threshold",
        {
            "employment_duration_category": "less_than_one_year",
            "documented_medical_expenses_krw": 3_000_001,
            "average_monthly_wage_during_employment_krw": 2_000_000,
        },
    )

    assert result.outputs["applicable_wages_krw"] == Decimal(24_000_000)
    assert result.outputs["medical_expense_threshold_krw"] == Decimal(3_000_000)
    assert result.outputs["wage_basis"] == "annualized_average_monthly_wage"


@pytest.mark.parametrize(
    ("medical_expenses", "expected"),
    [(Decimal("12.5"), False), (Decimal("12.500000000000000000000000001"), True)],
)
def test_dc_threshold_uses_strict_decimal_comparison(
    medical_expenses: Decimal, expected: bool
) -> None:
    result = _calculate(
        "dc_medical_withdrawal_threshold",
        _dc_inputs(
            previous_year_annual_wages_krw=100,
            documented_medical_expenses_krw=medical_expenses,
        ),
    )

    assert result.outputs["medical_expense_threshold_krw"] == Decimal("12.5")
    assert result.outputs["threshold_met"] is expected


def test_dc_threshold_preserves_explicit_zero() -> None:
    result = _calculate(
        "dc_medical_withdrawal_threshold",
        _dc_inputs(previous_year_annual_wages_krw=0, documented_medical_expenses_krw=0),
    )

    assert result.inputs["previous_year_annual_wages_krw"] == Decimal(0)
    assert result.inputs["documented_medical_expenses_krw"] == Decimal(0)
    assert result.outputs["medical_expense_threshold_krw"] == Decimal(0)
    assert result.outputs["threshold_met"] is False


@pytest.mark.parametrize(
    "inputs",
    [
        {},
        _dc_inputs(documented_medical_expenses_krw=None),
        _dc_inputs(previous_year_annual_wages_krw=None),
        _dc_inputs(documented_medical_expenses_krw=-1),
        _dc_inputs(previous_year_annual_wages_krw=-1),
        {
            "employment_duration_category": "at_least_one_year",
            "documented_medical_expenses_krw": 1,
        },
        {
            "employment_duration_category": "less_than_one_year",
            "documented_medical_expenses_krw": 1,
        },
        _dc_inputs(employment_duration_category="invalid"),
        _dc_inputs(average_monthly_wage_during_employment_krw=1),
        {
            "employment_duration_category": "less_than_one_year",
            "documented_medical_expenses_krw": 1,
            "average_monthly_wage_during_employment_krw": 1,
            "preceding_12_month_wages_krw": 1,
        },
    ],
)
def test_dc_threshold_rejects_missing_null_negative_or_mismatched_inputs(
    inputs: dict[str, object],
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate("dc_medical_withdrawal_threshold", inputs)


def _limit_inputs(**updates: object) -> dict[str, object]:
    inputs: dict[str, object] = {
        "requested_withdrawal_krw": 3_000_000,
        "actual_medical_expenses_krw": 0,
        "care_expenses_krw": 0,
        "own_leave_months": 0,
    }
    inputs.update(updates)
    return inputs


def test_tax_limit_has_base_amount_when_components_are_zero() -> None:
    result = _calculate("medical_care_withdrawal_tax_limit", _limit_inputs())

    assert result.outputs == {
        "tax_limit_krw": Decimal(2_000_000),
        "amount_within_limit_krw": Decimal(2_000_000),
        "excess_amount_krw": Decimal(1_000_000),
    }
    assert result.inputs["own_leave_months"] == 0


def test_tax_limit_adds_each_component() -> None:
    result = _calculate(
        "medical_care_withdrawal_tax_limit",
        _limit_inputs(
            requested_withdrawal_krw=10_000_000,
            actual_medical_expenses_krw=1_000_000,
            care_expenses_krw=2_000_000,
            own_leave_months=2,
        ),
    )

    assert result.outputs["tax_limit_krw"] == Decimal(8_000_000)
    assert result.outputs["amount_within_limit_krw"] == Decimal(8_000_000)
    assert result.outputs["excess_amount_krw"] == Decimal(2_000_000)


@pytest.mark.parametrize(
    ("requested", "within", "excess"),
    [
        (Decimal(0), Decimal(0), Decimal(0)),
        (Decimal(1_000_000), Decimal(1_000_000), Decimal(0)),
        (Decimal(2_000_000), Decimal(2_000_000), Decimal(0)),
        (Decimal(2_000_001), Decimal(2_000_000), Decimal(1)),
    ],
)
def test_tax_limit_splits_request_at_boundaries(
    requested: Decimal, within: Decimal, excess: Decimal
) -> None:
    result = _calculate(
        "medical_care_withdrawal_tax_limit",
        _limit_inputs(requested_withdrawal_krw=requested),
    )

    assert result.outputs["amount_within_limit_krw"] == within
    assert result.outputs["excess_amount_krw"] == excess


def test_tax_limit_preserves_fractional_decimals_without_rounding() -> None:
    result = _calculate(
        "medical_care_withdrawal_tax_limit",
        _limit_inputs(
            requested_withdrawal_krw=Decimal("2000000.3"),
            actual_medical_expenses_krw=Decimal("0.1"),
            care_expenses_krw=Decimal("0.2"),
        ),
    )

    assert result.outputs["tax_limit_krw"] == Decimal("2000000.3")
    assert result.outputs["amount_within_limit_krw"] == Decimal("2000000.3")
    assert result.outputs["excess_amount_krw"] == Decimal(0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requested_withdrawal_krw", None),
        ("requested_withdrawal_krw", -1),
        ("actual_medical_expenses_krw", None),
        ("actual_medical_expenses_krw", -1),
        ("care_expenses_krw", None),
        ("care_expenses_krw", -1),
        ("own_leave_months", None),
        ("own_leave_months", -1),
        ("own_leave_months", Decimal("0.5")),
    ],
)
def test_tax_limit_rejects_null_negative_or_fractional_inputs(field: str, value: object) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate("medical_care_withdrawal_tax_limit", _limit_inputs(**{field: value}))


def test_tax_limit_rejects_missing_required_input() -> None:
    inputs = _limit_inputs()
    del inputs["care_expenses_krw"]

    with pytest.raises(InvalidCalculationInputError):
        _calculate("medical_care_withdrawal_tax_limit", inputs)


def _breakdown_inputs(**updates: object) -> dict[str, object]:
    inputs = _limit_inputs(requested_withdrawal_krw=2_000_000)
    inputs["recipient_age"] = 69
    inputs.update(updates)
    return inputs


def test_breakdown_determines_current_totals_without_excess() -> None:
    result = _calculate("medical_care_withdrawal_tax_breakdown", _breakdown_inputs())

    assert result.outputs["within_limit_tax_krw"] == Decimal(110_000)
    assert result.outputs["within_limit_after_tax_krw"] == Decimal(1_890_000)
    assert result.outputs["current_withdrawal_tax_krw"] == Decimal(110_000)
    assert result.outputs["current_withdrawal_after_tax_krw"] == Decimal(1_890_000)


def test_breakdown_leaves_current_totals_null_when_excess_exists() -> None:
    result = _calculate(
        "medical_care_withdrawal_tax_breakdown",
        _breakdown_inputs(requested_withdrawal_krw=3_000_000),
    )

    assert result.outputs["excess_amount_krw"] == Decimal(1_000_000)
    assert result.outputs["current_withdrawal_tax_krw"] is None
    assert result.outputs["current_withdrawal_after_tax_krw"] is None
    assert "초과액" in " ".join(result.warnings)


@pytest.mark.parametrize(
    ("age", "expected_rate"),
    [(69, Decimal("5.5")), (70, Decimal("4.4")), (79, Decimal("4.4")), (80, Decimal("3.3"))],
)
def test_breakdown_reuses_unavoidable_age_boundaries(age: int, expected_rate: Decimal) -> None:
    result = _calculate(
        "medical_care_withdrawal_tax_breakdown",
        _breakdown_inputs(recipient_age=age),
    )
    direct = calculate_pension_income_tax(
        PensionIncomeTaxInput(
            pension_treatment="unavoidable",
            recipient_age=age,
            target_taxable_amount_krw=Decimal(2_000_000),
        )
    )

    assert result.outputs["within_limit_tax_rate_percent"] == expected_rate
    assert result.outputs["within_limit_tax_krw"] == direct.outputs["tax_krw"]
    assert result.outputs["within_limit_after_tax_krw"] == direct.outputs["after_tax_krw"]


def test_breakdown_preserves_fractional_tax_without_rounding() -> None:
    result = _calculate(
        "medical_care_withdrawal_tax_breakdown",
        _breakdown_inputs(requested_withdrawal_krw=Decimal("1.1")),
    )

    assert result.outputs["within_limit_tax_krw"] == Decimal("0.0605")
    assert result.outputs["within_limit_after_tax_krw"] == Decimal("1.0395")


@pytest.mark.parametrize("age", [None, -1])
def test_breakdown_rejects_null_or_negative_age(age: object) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate(
            "medical_care_withdrawal_tax_breakdown",
            _breakdown_inputs(recipient_age=age),
        )


def test_breakdown_rejects_missing_age() -> None:
    inputs = _breakdown_inputs()
    del inputs["recipient_age"]

    with pytest.raises(InvalidCalculationInputError):
        _calculate("medical_care_withdrawal_tax_breakdown", inputs)
