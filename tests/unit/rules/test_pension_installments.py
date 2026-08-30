"""연금수령한도 확장과 지급액 분할 계산기의 계약을 검증한다."""

from decimal import Decimal

import pytest

from pension_agent.rules import CalculationRequest, InvalidCalculationInputError, calculate


def _calculate(calculator_id: str, inputs: dict[str, object]):
    return calculate(CalculationRequest(calculator_id=calculator_id, inputs=inputs))


@pytest.mark.parametrize("pension_year", [11, 20])
def test_withdrawal_limit_does_not_apply_after_tenth_year(pension_year: int) -> None:
    result = _calculate("pension_withdrawal_limit", {"pension_year": pension_year})

    assert result.outputs == {"withdrawal_limit": None, "limit_applies": False}
    assert result.model_dump(mode="json")["outputs"]["withdrawal_limit"] is None
    assert result.warnings == ()


def test_withdrawal_limit_warns_when_unused_valuation_is_provided() -> None:
    result = _calculate(
        "pension_withdrawal_limit",
        {"pension_year": 11, "account_valuation_krw": 100_000_000},
    )

    assert result.outputs["withdrawal_limit"] is None
    assert "사용하지 않습니다" in result.warnings[0]


@pytest.mark.parametrize("pension_year", [1, 10])
def test_withdrawal_limit_requires_valuation_during_limit_years(
    pension_year: int,
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate("pension_withdrawal_limit", {"pension_year": pension_year})


@pytest.mark.parametrize("valuation", [None, -1])
def test_withdrawal_limit_rejects_null_or_negative_valuation(
    valuation: object,
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate(
            "pension_withdrawal_limit",
            {"pension_year": 11, "account_valuation_krw": valuation},
        )


@pytest.mark.parametrize(
    ("calculator_id", "inputs", "expected"),
    [
        (
            "pension_annual_limit_installment",
            {"remaining_annual_limit_krw": "1200000", "remaining_payments_in_year": 12},
            Decimal(100000),
        ),
        (
            "pension_period_installment",
            {"current_valuation_krw": "1200000", "remaining_payments": 12},
            Decimal(100000),
        ),
        (
            "pension_unit_installment",
            {
                "remaining_units": "12000",
                "remaining_payments": 12,
                "standard_price_per_1000_units_krw": "1500",
            },
            Decimal(1500),
        ),
    ],
)
def test_installment_formulas(
    calculator_id: str,
    inputs: dict[str, object],
    expected: Decimal,
) -> None:
    result = _calculate(calculator_id, inputs)

    assert result.outputs == {"installment_krw": expected}
    assert result.units == {"installment_krw": "KRW"}


@pytest.mark.parametrize(
    ("calculator_id", "inputs", "payment_field", "expected"),
    [
        (
            "pension_annual_limit_installment",
            {"remaining_annual_limit_krw": 1, "remaining_payments_in_year": 1},
            "remaining_payments_in_year",
            Decimal(1),
        ),
        (
            "pension_period_installment",
            {"current_valuation_krw": 1, "remaining_payments": 1},
            "remaining_payments",
            Decimal(1),
        ),
        (
            "pension_unit_installment",
            {
                "remaining_units": 1,
                "remaining_payments": 1,
                "standard_price_per_1000_units_krw": 1,
            },
            "remaining_payments",
            Decimal("0.001"),
        ),
    ],
)
def test_installment_payment_count_boundaries(
    calculator_id: str,
    inputs: dict[str, object],
    payment_field: str,
    expected: Decimal,
) -> None:
    assert _calculate(calculator_id, inputs).outputs["installment_krw"] == expected

    for invalid in (0, -1):
        invalid_inputs = {**inputs, payment_field: invalid}
        with pytest.raises(InvalidCalculationInputError):
            _calculate(calculator_id, invalid_inputs)


@pytest.mark.parametrize(
    ("calculator_id", "inputs"),
    [
        (
            "pension_annual_limit_installment",
            {"remaining_annual_limit_krw": 0, "remaining_payments_in_year": 3},
        ),
        (
            "pension_period_installment",
            {"current_valuation_krw": 0, "remaining_payments": 3},
        ),
        (
            "pension_unit_installment",
            {
                "remaining_units": 0,
                "remaining_payments": 3,
                "standard_price_per_1000_units_krw": 1000,
            },
        ),
        (
            "pension_unit_installment",
            {
                "remaining_units": 1000,
                "remaining_payments": 3,
                "standard_price_per_1000_units_krw": 0,
            },
        ),
    ],
)
def test_installment_zero_inputs_return_zero(
    calculator_id: str,
    inputs: dict[str, object],
) -> None:
    assert _calculate(calculator_id, inputs).outputs["installment_krw"] == Decimal(0)


@pytest.mark.parametrize(
    ("calculator_id", "inputs"),
    [
        (
            "pension_annual_limit_installment",
            {"remaining_annual_limit_krw": 1, "remaining_payments_in_year": 3},
        ),
        (
            "pension_period_installment",
            {"current_valuation_krw": 1, "remaining_payments": 3},
        ),
        (
            "pension_unit_installment",
            {
                "remaining_units": 1,
                "remaining_payments": 3,
                "standard_price_per_1000_units_krw": 1,
            },
        ),
    ],
)
def test_installment_repeating_decimal_is_not_rounded(
    calculator_id: str,
    inputs: dict[str, object],
) -> None:
    installment = _calculate(calculator_id, inputs).outputs["installment_krw"]

    assert isinstance(installment, Decimal)
    assert len(str(installment).replace(".", "")) >= 27


@pytest.mark.parametrize(
    ("calculator_id", "inputs"),
    [
        (
            "pension_annual_limit_installment",
            {"remaining_annual_limit_krw": -1, "remaining_payments_in_year": 1},
        ),
        (
            "pension_period_installment",
            {"current_valuation_krw": -1, "remaining_payments": 1},
        ),
        (
            "pension_unit_installment",
            {
                "remaining_units": -1,
                "remaining_payments": 1,
                "standard_price_per_1000_units_krw": 1,
            },
        ),
        (
            "pension_unit_installment",
            {
                "remaining_units": 1,
                "remaining_payments": 1,
                "standard_price_per_1000_units_krw": -1,
            },
        ),
    ],
)
def test_installment_rejects_negative_amounts(
    calculator_id: str,
    inputs: dict[str, object],
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate(calculator_id, inputs)


def test_installment_rejects_extra_input() -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate(
            "pension_period_installment",
            {"current_valuation_krw": 1, "remaining_payments": 1, "extra": 1},
        )


def test_existing_decimal_result_serialization_remains_unchanged() -> None:
    result = _calculate(
        "pension_withdrawal_limit",
        {"account_valuation_krw": "100000000", "pension_year": 1},
    )

    payload = result.model_dump(mode="json")
    assert payload["outputs"] == {
        "withdrawal_limit": "12000000.0",
        "limit_applies": True,
    }
