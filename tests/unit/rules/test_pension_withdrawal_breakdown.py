"""연금 인출 순서 배분과 재원·수령구분별 세액 합성 계약을 검증한다."""

from decimal import Decimal

import pytest

from pension_agent.rules import CalculationRequest, InvalidCalculationInputError, calculate
from pension_agent.rules.calculators.deferred_retirement_withdrawal_tax import (
    DeferredRetirementWithdrawalTaxInput,
    calculate_deferred_retirement_withdrawal_tax,
)
from pension_agent.rules.calculators.non_pension_withdrawal_tax import (
    NonPensionWithdrawalTaxInput,
    calculate_non_pension_withdrawal_tax,
)
from pension_agent.rules.calculators.pension_income_tax import (
    PensionIncomeTaxInput,
    calculate_pension_income_tax,
)


def _calculate(calculator_id: str, inputs: dict[str, object]):
    return calculate(CalculationRequest(calculator_id=calculator_id, inputs=inputs))


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (Decimal(50), (Decimal(50), Decimal(0), Decimal(0))),
        (Decimal(100), (Decimal(100), Decimal(0), Decimal(0))),
        (Decimal(250), (Decimal(100), Decimal(150), Decimal(0))),
        (Decimal(600), (Decimal(100), Decimal(200), Decimal(300))),
        (Decimal(0), (Decimal(0), Decimal(0), Decimal(0))),
    ],
)
def test_allocation_partial_boundaries_and_full_withdrawal(
    requested: Decimal,
    expected: tuple[Decimal, Decimal, Decimal],
) -> None:
    result = _calculate(
        "pension_withdrawal_allocation",
        {
            "requested_withdrawal_krw": requested,
            "tax_free_source_balance_krw": 100,
            "deferred_retirement_source_balance_krw": 200,
            "credited_and_earnings_source_balance_krw": 300,
        },
    )

    assert (
        result.outputs["tax_free_withdrawal_krw"],
        result.outputs["deferred_retirement_withdrawal_krw"],
        result.outputs["credited_and_earnings_withdrawal_krw"],
    ) == expected
    assert result.outputs["tax_free_remaining_balance_krw"] == Decimal(100) - expected[0]
    assert result.outputs["deferred_retirement_remaining_balance_krw"] == (
        Decimal(200) - expected[1]
    )
    assert result.outputs["credited_and_earnings_remaining_balance_krw"] == (
        Decimal(300) - expected[2]
    )
    assert set(result.units.values()) == {"KRW"}


@pytest.mark.parametrize(
    "inputs",
    [
        {
            "requested_withdrawal_krw": 601,
            "tax_free_source_balance_krw": 100,
            "deferred_retirement_source_balance_krw": 200,
            "credited_and_earnings_source_balance_krw": 300,
        },
        {
            "requested_withdrawal_krw": None,
            "tax_free_source_balance_krw": 0,
            "deferred_retirement_source_balance_krw": 0,
            "credited_and_earnings_source_balance_krw": 0,
        },
        {
            "requested_withdrawal_krw": 0,
            "tax_free_source_balance_krw": -1,
            "deferred_retirement_source_balance_krw": 0,
            "credited_and_earnings_source_balance_krw": 0,
        },
    ],
)
def test_allocation_rejects_excess_null_and_negative(inputs: dict[str, object]) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate("pension_withdrawal_allocation", inputs)


def _breakdown_inputs(**updates: object) -> dict[str, object]:
    inputs: dict[str, object] = {
        "requested_withdrawal_krw": 500,
        "tax_free_source_balance_krw": 100,
        "deferred_retirement_source_balance_krw": 200,
        "credited_and_earnings_source_balance_krw": 300,
        "pension_treated_withdrawal_krw": 250,
        "non_pension_treated_withdrawal_krw": 250,
        "actual_pension_receipt_year": 1,
        "pension_treated_allocated_deferred_retirement_tax_krw": 30,
        "non_pension_treated_allocated_deferred_retirement_tax_krw": 10,
    }
    inputs.update(updates)
    return inputs


def test_breakdown_allocates_front_pension_segment_across_source_boundaries() -> None:
    result = _calculate("pension_withdrawal_tax_breakdown", _breakdown_inputs())

    expected_withdrawals = {
        "tax_free_pension_withdrawal_krw": Decimal(100),
        "tax_free_non_pension_withdrawal_krw": Decimal(0),
        "deferred_retirement_pension_withdrawal_krw": Decimal(150),
        "deferred_retirement_non_pension_withdrawal_krw": Decimal(50),
        "credited_and_earnings_pension_withdrawal_krw": Decimal(0),
        "credited_and_earnings_non_pension_withdrawal_krw": Decimal(200),
    }
    for key, expected in expected_withdrawals.items():
        assert result.outputs[key] == expected
    assert sum(expected_withdrawals.values()) == Decimal(500)
    assert result.outputs["tax_free_pension_tax_krw"] == Decimal(0)
    assert result.outputs["tax_free_non_pension_tax_krw"] == Decimal(0)
    assert "비과세 재원 인출액도 연금수령한도를 소진" in " ".join(result.warnings)


def test_breakdown_reuses_deferred_and_non_pension_tax_functions() -> None:
    result = _calculate("pension_withdrawal_tax_breakdown", _breakdown_inputs())
    pension_tax = calculate_deferred_retirement_withdrawal_tax(
        DeferredRetirementWithdrawalTaxInput(
            receipt_type="pension",
            actual_pension_receipt_year=1,
            allocated_deferred_retirement_tax_krw=30,
        )
    ).outputs["tax_payable_krw"]
    non_pension_deferred_tax = calculate_deferred_retirement_withdrawal_tax(
        DeferredRetirementWithdrawalTaxInput(
            receipt_type="non_pension",
            allocated_deferred_retirement_tax_krw=10,
        )
    ).outputs["tax_payable_krw"]
    credited_tax = calculate_non_pension_withdrawal_tax(
        NonPensionWithdrawalTaxInput(taxable_amount_krw=200)
    ).outputs["tax_krw"]

    assert result.outputs["deferred_retirement_pension_tax_krw"] == pension_tax
    assert result.outputs["deferred_retirement_non_pension_tax_krw"] == (non_pension_deferred_tax)
    assert result.outputs["credited_and_earnings_non_pension_tax_krw"] == credited_tax
    assert result.outputs["current_withdrawal_tax_krw"] == (
        pension_tax + non_pension_deferred_tax + credited_tax
    )
    assert result.outputs["current_withdrawal_after_tax_krw"] == (
        Decimal(500) - result.outputs["current_withdrawal_tax_krw"]
    )


def test_breakdown_preserves_explicit_zero_allocated_deferred_taxes() -> None:
    result = _calculate(
        "pension_withdrawal_tax_breakdown",
        _breakdown_inputs(
            pension_treated_allocated_deferred_retirement_tax_krw=0,
            non_pension_treated_allocated_deferred_retirement_tax_krw=0,
        ),
    )

    assert result.inputs["pension_treated_allocated_deferred_retirement_tax_krw"] == Decimal(0)
    assert result.inputs["non_pension_treated_allocated_deferred_retirement_tax_krw"] == Decimal(0)
    assert result.outputs["deferred_retirement_pension_tax_krw"] == Decimal(0)
    assert result.outputs["deferred_retirement_non_pension_tax_krw"] == Decimal(0)


def _credited_pension_inputs(**updates: object) -> dict[str, object]:
    inputs: dict[str, object] = {
        "requested_withdrawal_krw": 100,
        "tax_free_source_balance_krw": 0,
        "deferred_retirement_source_balance_krw": 0,
        "credited_and_earnings_source_balance_krw": 100,
        "pension_treated_withdrawal_krw": 100,
        "non_pension_treated_withdrawal_krw": 0,
        "recipient_age": 55,
        "is_lifetime_annuity": False,
    }
    inputs.update(updates)
    return inputs


def test_breakdown_reuses_ordinary_pension_income_tax() -> None:
    result = _calculate(
        "pension_withdrawal_tax_breakdown",
        _credited_pension_inputs(annual_private_pension_taxable_income_krw=1000),
    )
    direct = calculate_pension_income_tax(
        PensionIncomeTaxInput(
            pension_treatment="ordinary",
            recipient_age=55,
            target_taxable_amount_krw=100,
            is_lifetime_annuity=False,
            annual_private_pension_taxable_income_krw=1000,
        )
    )

    assert result.outputs["credited_and_earnings_pension_tax_krw"] == direct.outputs["tax_krw"]
    assert (
        result.outputs["credited_and_earnings_pension_after_tax_krw"]
        == (direct.outputs["after_tax_krw"])
    )


@pytest.mark.parametrize("annual", [None, Decimal(15_000_001)])
def test_breakdown_propagates_null_for_unresolved_credited_pension_tax(
    annual: Decimal | None,
) -> None:
    inputs = _credited_pension_inputs()
    if annual is not None:
        inputs["annual_private_pension_taxable_income_krw"] = annual
    result = _calculate("pension_withdrawal_tax_breakdown", inputs)

    assert result.outputs["credited_and_earnings_pension_tax_krw"] is None
    assert result.outputs["credited_and_earnings_pension_after_tax_krw"] is None
    assert result.outputs["current_withdrawal_tax_krw"] is None
    assert result.outputs["current_withdrawal_after_tax_krw"] is None


def test_annual_separate_tax_option_is_not_added_to_current_total() -> None:
    result = _calculate(
        "pension_withdrawal_tax_breakdown",
        _credited_pension_inputs(annual_private_pension_taxable_income_krw=20_000_000),
    )

    assert result.outputs["annual_private_pension_separate_tax_option_tax_krw"] == Decimal(
        3_300_000
    )
    assert result.outputs["current_withdrawal_tax_krw"] is None
    assert "현재 인출 세액 합계와 다른 단위" in " ".join(result.warnings)


@pytest.mark.parametrize(
    "updates",
    [
        {"non_pension_treated_withdrawal_krw": 249},
        {"actual_pension_receipt_year": None},
        {"actual_pension_receipt_year": 0},
        {"pension_treated_allocated_deferred_retirement_tax_krw": None},
        {"pension_treated_allocated_deferred_retirement_tax_krw": -1},
        {"non_pension_treated_allocated_deferred_retirement_tax_krw": None},
        {"non_pension_treated_allocated_deferred_retirement_tax_krw": -1},
    ],
)
def test_breakdown_rejects_mismatched_or_invalid_conditional_inputs(
    updates: dict[str, object],
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate("pension_withdrawal_tax_breakdown", _breakdown_inputs(**updates))


@pytest.mark.parametrize(
    "updates",
    [
        {"recipient_age": None},
        {"recipient_age": -1},
        {"is_lifetime_annuity": None},
        {"annual_private_pension_taxable_income_krw": None},
        {"annual_private_pension_taxable_income_krw": -1},
    ],
)
def test_credited_pension_rejects_null_or_negative_conditional_inputs(
    updates: dict[str, object],
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate(
            "pension_withdrawal_tax_breakdown",
            _credited_pension_inputs(**updates),
        )


def test_conditional_inputs_are_forbidden_when_corresponding_path_is_absent() -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate(
            "pension_withdrawal_tax_breakdown",
            {
                "requested_withdrawal_krw": 0,
                "tax_free_source_balance_krw": 0,
                "deferred_retirement_source_balance_krw": 0,
                "credited_and_earnings_source_balance_krw": 0,
                "pension_treated_withdrawal_krw": 0,
                "non_pension_treated_withdrawal_krw": 0,
                "recipient_age": 0,
            },
        )


def test_tax_free_warning_only_when_tax_free_is_actually_withdrawn() -> None:
    without_tax_free = _calculate(
        "pension_withdrawal_tax_breakdown",
        {
            "requested_withdrawal_krw": 100,
            "tax_free_source_balance_krw": 0,
            "deferred_retirement_source_balance_krw": 0,
            "credited_and_earnings_source_balance_krw": 100,
            "pension_treated_withdrawal_krw": 0,
            "non_pension_treated_withdrawal_krw": 100,
        },
    )
    assert not any("비과세 재원" in warning for warning in without_tax_free.warnings)


def test_breakdown_invariants_and_decimal_json_serialization() -> None:
    result = _calculate("pension_withdrawal_tax_breakdown", _breakdown_inputs())
    payload = result.model_dump(mode="json")
    path_names = (
        "tax_free_pension",
        "tax_free_non_pension",
        "deferred_retirement_pension",
        "deferred_retirement_non_pension",
        "credited_and_earnings_pension",
        "credited_and_earnings_non_pension",
    )

    assert sum(result.outputs[f"{path}_withdrawal_krw"] for path in path_names) == Decimal(500)
    for path in path_names:
        assert (
            result.outputs[f"{path}_tax_krw"] + result.outputs[f"{path}_after_tax_krw"]
            == (result.outputs[f"{path}_withdrawal_krw"])
        )
    assert isinstance(payload["outputs"]["current_withdrawal_tax_krw"], str)
