"""연금소득세와 연금외수령 세액 계산 계약을 검증한다."""

from decimal import Decimal

import pytest

from pension_agent.rules import (
    CalculationRequest,
    InvalidCalculationInputError,
    calculate,
)


def _pension_income_inputs(**overrides: object) -> dict[str, object]:
    inputs: dict[str, object] = {
        "pension_treatment": "ordinary",
        "recipient_age": 55,
        "is_lifetime_annuity": False,
    }
    inputs.update(overrides)
    return inputs


@pytest.mark.parametrize(
    ("age", "expected_rate"),
    [
        (55, Decimal("5.5")),
        (69, Decimal("5.5")),
        (70, Decimal("4.4")),
        (79, Decimal("4.4")),
        (80, Decimal("3.3")),
    ],
)
def test_ordinary_age_rate_boundaries(age: int, expected_rate: Decimal) -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="pension_income_tax",
            inputs=_pension_income_inputs(recipient_age=age),
        )
    )

    assert result.outputs == {
        "base_rate_percent": expected_rate,
        "annual_threshold_status": "unknown",
    }


def test_ordinary_rejects_age_below_55() -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(
            CalculationRequest(
                calculator_id="pension_income_tax",
                inputs=_pension_income_inputs(recipient_age=54),
            )
        )


def test_ordinary_lifetime_annuity_uses_3_3_percent() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="pension_income_tax",
            inputs=_pension_income_inputs(
                recipient_age=55,
                is_lifetime_annuity=True,
            ),
        )
    )

    assert result.outputs["base_rate_percent"] == Decimal("3.3")


@pytest.mark.parametrize(
    ("age", "expected_rate"),
    [
        (54, Decimal("5.5")),
        (69, Decimal("5.5")),
        (70, Decimal("4.4")),
        (79, Decimal("4.4")),
        (80, Decimal("3.3")),
    ],
)
def test_unavoidable_age_rate_boundaries(age: int, expected_rate: Decimal) -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="pension_income_tax",
            inputs={
                "pension_treatment": "unavoidable",
                "recipient_age": age,
                "target_taxable_amount_krw": 1_000_000,
            },
        )
    )

    assert result.outputs == {
        "base_rate_percent": expected_rate,
        "tax_krw": Decimal(1_000_000) * expected_rate / Decimal(100),
        "after_tax_krw": Decimal(1_000_000) - Decimal(1_000_000) * expected_rate / Decimal(100),
    }


def test_ordinary_with_target_but_without_annual_total_does_not_create_tax() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="pension_income_tax",
            inputs=_pension_income_inputs(target_taxable_amount_krw=1_000_000),
        )
    )

    assert result.outputs == {
        "base_rate_percent": Decimal("5.5"),
        "annual_threshold_status": "unknown",
    }


@pytest.mark.parametrize("annual", [14_999_999, 15_000_000])
def test_ordinary_within_annual_threshold_calculates_target_tax(annual: int) -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="pension_income_tax",
            inputs=_pension_income_inputs(
                target_taxable_amount_krw=1_000_000,
                annual_private_pension_taxable_income_krw=annual,
            ),
        )
    )

    assert result.outputs == {
        "base_rate_percent": Decimal("5.5"),
        "annual_threshold_status": "within",
        "filing_choice_required": False,
        "tax_krw": Decimal(55_000),
        "after_tax_krw": Decimal(945_000),
    }


def test_ordinary_above_threshold_applies_16_5_percent_to_full_annual_total() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="pension_income_tax",
            inputs=_pension_income_inputs(
                target_taxable_amount_krw=1_000_000,
                annual_private_pension_taxable_income_krw=15_000_001,
            ),
        )
    )

    assert result.outputs == {
        "base_rate_percent": Decimal("5.5"),
        "annual_threshold_status": "exceeded",
        "filing_choice_required": True,
        "separate_tax_option_rate_percent": Decimal("16.5"),
        "separate_tax_option_tax_krw": Decimal("2475000.165"),
        "separate_tax_option_after_tax_krw": Decimal("12525000.835"),
    }
    assert "tax_krw" not in result.outputs


def test_rejects_target_greater_than_annual_total() -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(
            CalculationRequest(
                calculator_id="pension_income_tax",
                inputs=_pension_income_inputs(
                    target_taxable_amount_krw=2,
                    annual_private_pension_taxable_income_krw=1,
                ),
            )
        )


@pytest.mark.parametrize(
    "inputs",
    [
        {"pension_treatment": "ordinary", "recipient_age": 55},
        {
            "pension_treatment": "unavoidable",
            "recipient_age": 54,
            "is_lifetime_annuity": False,
        },
        {
            "pension_treatment": "unavoidable",
            "recipient_age": 54,
            "annual_private_pension_taxable_income_krw": 0,
        },
    ],
)
def test_pension_income_rejects_missing_or_mixed_treatment_fields(
    inputs: dict[str, object],
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(CalculationRequest(calculator_id="pension_income_tax", inputs=inputs))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_taxable_amount_krw", None),
        ("target_taxable_amount_krw", -1),
        ("annual_private_pension_taxable_income_krw", None),
        ("annual_private_pension_taxable_income_krw", -1),
    ],
)
def test_pension_income_rejects_null_or_negative_money(field: str, value: object) -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(
            CalculationRequest(
                calculator_id="pension_income_tax",
                inputs=_pension_income_inputs(**{field: value}),
            )
        )


def test_pension_income_preserves_explicit_zero_amounts() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="pension_income_tax",
            inputs=_pension_income_inputs(
                target_taxable_amount_krw=0,
                annual_private_pension_taxable_income_krw=0,
            ),
        )
    )

    assert result.inputs["target_taxable_amount_krw"] == Decimal(0)
    assert result.inputs["annual_private_pension_taxable_income_krw"] == Decimal(0)
    assert result.outputs["tax_krw"] == Decimal(0)
    assert result.outputs["after_tax_krw"] == Decimal(0)


def test_non_pension_without_amount_returns_rate_only() -> None:
    result = calculate(CalculationRequest(calculator_id="non_pension_withdrawal_tax", inputs={}))

    assert result.outputs == {"base_rate_percent": Decimal("16.5")}
    assert result.inputs == {}


def test_non_pension_calculates_amount_without_rounding() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="non_pension_withdrawal_tax",
            inputs={"taxable_amount_krw": 1},
        )
    )

    assert result.outputs == {
        "base_rate_percent": Decimal("16.5"),
        "tax_krw": Decimal("0.165"),
        "after_tax_krw": Decimal("0.835"),
    }


def test_non_pension_preserves_explicit_zero_amount() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="non_pension_withdrawal_tax",
            inputs={"taxable_amount_krw": 0},
        )
    )

    assert result.inputs == {"taxable_amount_krw": Decimal(0)}
    assert result.outputs["tax_krw"] == Decimal(0)
    assert result.outputs["after_tax_krw"] == Decimal(0)


@pytest.mark.parametrize("value", [None, -1])
def test_non_pension_rejects_null_or_negative_amount(value: object) -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(
            CalculationRequest(
                calculator_id="non_pension_withdrawal_tax",
                inputs={"taxable_amount_krw": value},
            )
        )


@pytest.mark.parametrize(
    ("calculator_id", "inputs"),
    [
        ("non_pension_withdrawal_tax", {"recipient_age": 55}),
        (
            "pension_income_tax",
            {
                "pension_treatment": "ordinary",
                "recipient_age": 55,
                "is_lifetime_annuity": False,
                "taxable_amount_krw": 1,
            },
        ),
    ],
)
def test_tax_calculators_reject_fields_from_the_other_contract(
    calculator_id: str,
    inputs: dict[str, object],
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(CalculationRequest(calculator_id=calculator_id, inputs=inputs))


@pytest.mark.parametrize(
    ("calculator_id", "inputs"),
    [
        (
            "pension_income_tax",
            _pension_income_inputs(
                target_taxable_amount_krw=1,
                annual_private_pension_taxable_income_krw=1,
            ),
        ),
        ("non_pension_withdrawal_tax", {"taxable_amount_krw": 1}),
    ],
)
def test_tax_results_serialize_decimals_as_strings(
    calculator_id: str,
    inputs: dict[str, object],
) -> None:
    payload = calculate(CalculationRequest(calculator_id=calculator_id, inputs=inputs)).model_dump(
        mode="json"
    )

    assert isinstance(next(iter(payload["outputs"].values())), str)
    amount_inputs = [value for value in payload["inputs"].values() if isinstance(value, str)]
    assert amount_inputs
