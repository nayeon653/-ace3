"""이연퇴직소득세 수령 유형별 납부·감면 계산 계약을 검증한다."""

from decimal import Decimal

import pytest

from pension_agent.rules import (
    CalculationRequest,
    InvalidCalculationInputError,
    calculate,
)


def _calculate(inputs: dict[str, object]) -> object:
    return calculate(
        CalculationRequest(
            calculator_id="deferred_retirement_withdrawal_tax",
            inputs=inputs,
        )
    )


@pytest.mark.parametrize(
    ("receipt_year", "payable", "reduction"),
    [
        (1, Decimal(70), Decimal(30)),
        (10, Decimal(70), Decimal(30)),
        (11, Decimal(60), Decimal(40)),
        (20, Decimal(60), Decimal(40)),
        (21, Decimal(50), Decimal(50)),
        (10_000, Decimal(50), Decimal(50)),
    ],
)
def test_pension_receipt_year_boundaries(
    receipt_year: int, payable: Decimal, reduction: Decimal
) -> None:
    result = _calculate(
        {
            "receipt_type": "pension",
            "actual_pension_receipt_year": receipt_year,
        }
    )

    assert result.outputs == {
        "payable_ratio_percent": payable,
        "reduction_ratio_percent": reduction,
    }


def test_non_pension_uses_full_payable_ratio() -> None:
    result = _calculate({"receipt_type": "non_pension"})

    assert result.outputs == {
        "payable_ratio_percent": Decimal(100),
        "reduction_ratio_percent": Decimal(0),
    }


def test_omitted_allocated_tax_returns_ratios_only() -> None:
    result = _calculate({"receipt_type": "pension", "actual_pension_receipt_year": 1})

    assert result.inputs.keys() == {"receipt_type", "actual_pension_receipt_year"}
    assert "tax_payable_krw" not in result.outputs
    assert "tax_reduction_krw" not in result.outputs


def test_explicit_zero_allocated_tax_returns_zero_amounts() -> None:
    result = _calculate(
        {
            "receipt_type": "pension",
            "actual_pension_receipt_year": 1,
            "allocated_deferred_retirement_tax_krw": 0,
        }
    )

    assert result.inputs["allocated_deferred_retirement_tax_krw"] == Decimal(0)
    assert result.outputs["tax_payable_krw"] == Decimal(0)
    assert result.outputs["tax_reduction_krw"] == Decimal(0)


@pytest.mark.parametrize("value", [None, -1])
def test_rejects_null_or_negative_allocated_tax(value: object) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate(
            {
                "receipt_type": "pension",
                "actual_pension_receipt_year": 1,
                "allocated_deferred_retirement_tax_krw": value,
            }
        )


@pytest.mark.parametrize(
    "inputs",
    [
        {"receipt_type": "pension"},
        {"receipt_type": "pension", "actual_pension_receipt_year": 0},
    ],
)
def test_pension_rejects_missing_or_zero_actual_receipt_year(
    inputs: dict[str, object],
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate(inputs)


def test_non_pension_rejects_actual_receipt_year() -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate(
            {
                "receipt_type": "non_pension",
                "actual_pension_receipt_year": 1,
            }
        )


def test_rejects_withdrawal_limit_pension_year_field() -> None:
    with pytest.raises(InvalidCalculationInputError) as captured:
        _calculate(
            {
                "receipt_type": "pension",
                "actual_pension_receipt_year": 1,
                "pension_year": 1,
            }
        )

    assert any(issue.field == "pension_year" for issue in captured.value.issues)
    assert any(issue.code == "extra_forbidden" for issue in captured.value.issues)


@pytest.mark.parametrize(
    ("receipt_type", "receipt_year", "allocated_tax"),
    [
        ("pension", 1, Decimal("1.01")),
        ("pension", 11, Decimal("1.01")),
        ("pension", 21, Decimal("1.01")),
        ("non_pension", None, Decimal("1.01")),
    ],
)
def test_tax_payable_and_reduction_preserve_allocated_tax(
    receipt_type: str,
    receipt_year: int | None,
    allocated_tax: Decimal,
) -> None:
    inputs: dict[str, object] = {
        "receipt_type": receipt_type,
        "allocated_deferred_retirement_tax_krw": allocated_tax,
    }
    if receipt_year is not None:
        inputs["actual_pension_receipt_year"] = receipt_year

    result = _calculate(inputs)

    assert result.outputs["tax_payable_krw"] + result.outputs["tax_reduction_krw"] == allocated_tax


def test_result_serializes_decimals_as_strings() -> None:
    payload = _calculate(
        {
            "receipt_type": "pension",
            "actual_pension_receipt_year": 21,
            "allocated_deferred_retirement_tax_krw": Decimal("1.01"),
        }
    ).model_dump(mode="json")

    assert payload["inputs"]["allocated_deferred_retirement_tax_krw"] == "1.01"
    assert payload["outputs"]["payable_ratio_percent"] == "50.00"
    assert payload["outputs"]["tax_payable_krw"] == "0.5050"
