"""계산 함수의 최소 dispatch와 입력 검증 계약을 확인한다."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from pension_agent.rules import (
    CalculationOutput,
    CalculationRequest,
    CalculatorNotFoundError,
    InvalidCalculationInputError,
    calculate,
)


def test_calculate_returns_normalized_result() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="pension_withdrawal_limit",
            inputs={"account_valuation_krw": "100000000", "pension_year": 1},
        )
    )

    assert result.calculator_id == "pension_withdrawal_limit"
    assert result.inputs == {
        "account_valuation_krw": Decimal(100000000),
        "pension_year": 1,
    }
    assert result.outputs == {
        "withdrawal_limit": Decimal("12000000.0"),
        "limit_applies": True,
    }
    assert result.units == {"withdrawal_limit": "KRW"}


def test_calculate_rejects_unknown_calculator() -> None:
    with pytest.raises(CalculatorNotFoundError):
        calculate(CalculationRequest(calculator_id="missing", inputs={}))


def test_calculation_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CalculationRequest.model_validate(
            {
                "calculator_id": "pension_withdrawal_limit",
                "inputs": {},
                "permission": "tax_payout",
            }
        )


def test_calculate_exposes_field_codes_without_raw_input() -> None:
    with pytest.raises(InvalidCalculationInputError) as captured:
        calculate(
            CalculationRequest(
                calculator_id="pension_withdrawal_limit",
                inputs={"account_valuation_krw": -1, "pension_year": 1},
            )
        )

    assert captured.value.issues[0].field == "account_valuation_krw"
    assert captured.value.issues[0].code == "greater_than_equal"
    assert "-1" not in str(captured.value)


def test_calculation_output_rejects_unknown_unit_key() -> None:
    with pytest.raises(ValidationError, match="단위가 실제 계산 출력과 일치하지 않습니다"):
        CalculationOutput(outputs={"amount": Decimal(1)}, units={"missing": "KRW"})


def test_same_request_returns_same_result() -> None:
    request = CalculationRequest(
        calculator_id="pension_withdrawal_limit",
        inputs={"account_valuation_krw": "100000000", "pension_year": 1},
    )

    assert calculate(request) == calculate(request)
