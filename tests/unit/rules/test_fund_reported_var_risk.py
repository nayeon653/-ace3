"""공시 연환산 VaR 위험등급 계산기 회귀 테스트."""

from decimal import Decimal

import pytest

from pension_agent.rules import (
    CalculationRequest,
    InvalidCalculationInputError,
    calculate,
)


def _calculate(value: object):
    return calculate(
        CalculationRequest(
            calculator_id="fund_reported_var_risk",
            inputs={"annualized_var_percent": value},
        )
    )


@pytest.mark.parametrize(
    ("annualized_var", "grade"),
    [
        ("0", 6),
        ("1", 6),
        ("1.0001", 5),
        ("10", 5),
        ("10.0001", 4),
        ("20", 4),
        ("20.0001", 3),
        ("30", 3),
        ("30.0001", 2),
        ("50", 2),
        ("50.0001", 1),
    ],
)
def test_reported_var_risk_grade_boundaries(annualized_var: str, grade: int) -> None:
    result = _calculate(annualized_var)

    assert result.inputs == {"annualized_var_percent": Decimal(annualized_var)}
    assert result.outputs["annualized_var_percent"] == Decimal(annualized_var)
    assert result.outputs["risk_grade"] == grade


def test_reported_var_is_not_annualized_again() -> None:
    result = _calculate("12.3456789")

    assert result.outputs == {
        "annualized_var_percent": Decimal("12.3456789"),
        "risk_grade": 4,
        "risk_label": "보통 위험",
    }
    assert result.warnings == ()


@pytest.mark.parametrize("value", [None, "-0.0001", "NaN", "Infinity", "not-a-number"])
def test_reported_var_rejects_null_negative_or_invalid_values(value: object) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate(value)


def test_reported_var_requires_input() -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(
            CalculationRequest(
                calculator_id="fund_reported_var_risk",
                inputs={},
            )
        )


def test_daily_var_calculator_remains_separate() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="fund_var_risk",
            inputs={"daily_loss_percentile_percent": "-1"},
        )
    )

    assert result.outputs["annualized_var_percent"] == Decimal(250).sqrt()
