from decimal import Decimal

import pytest
from pydantic import ValidationError

from pension_agent.rules import CalculationRequest, calculate
from pension_agent.rules.calculators import CALCULATORS
from pension_agent.rules.calculators.pension_tax_credit import (
    PensionTaxCreditInput,
    calculate_pension_tax_credit,
)

_BASE_INPUTS: dict[str, object] = {
    "pension_savings_net_contribution_krw": 6_000_000,
    "retirement_pension_net_contribution_krw": 3_000_000,
}


def _create_input(
    extra_inputs: dict[str, object] | None = None,
) -> PensionTaxCreditInput:
    return PensionTaxCreditInput.model_validate({**_BASE_INPUTS, **(extra_inputs or {})})


def test_accepts_regular_contributions_without_optional_inputs() -> None:
    value = _create_input()

    assert value.pension_savings_net_contribution_krw == Decimal(6_000_000)
    assert value.retirement_pension_net_contribution_krw == Decimal(3_000_000)
    assert value.income_basis is None


def test_accepts_isa_transfer_with_prior_used_amount() -> None:
    value = PensionTaxCreditInput.model_validate(
        {
            "pension_savings_net_contribution_krw": 36_000_000,
            "retirement_pension_net_contribution_krw": 3_000_000,
            "pension_savings_isa_transfer_krw": 30_000_000,
            "prior_same_maturity_isa_extra_eligible_contribution_used_krw": 0,
        }
    )

    assert value.pension_savings_isa_transfer_krw == Decimal(30_000_000)


@pytest.mark.parametrize(
    "extra_inputs",
    [
        {"income_basis": None},
        {
            "pension_savings_isa_transfer_krw": 7_000_000,
            "prior_same_maturity_isa_extra_eligible_contribution_used_krw": 0,
        },
        {
            "retirement_pension_isa_transfer_krw": 4_000_000,
            "prior_same_maturity_isa_extra_eligible_contribution_used_krw": 0,
        },
        {"pension_savings_isa_transfer_krw": 1_000_000},
        {
            "prior_same_maturity_isa_extra_eligible_contribution_used_krw": 0,
        },
        {"income_basis": "salary"},
        {"income_amount_krw": 50_000_000},
        {"remaining_tax_before_pension_credit_krw": 1_000_000},
    ],
)
def test_rejects_invalid_related_inputs(
    extra_inputs: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _create_input(extra_inputs)


@pytest.mark.parametrize("prior_used", [-1, 3_000_001])
def test_rejects_prior_isa_used_outside_limit(prior_used: int) -> None:
    with pytest.raises(ValidationError):
        PensionTaxCreditInput.model_validate(
            {
                "pension_savings_net_contribution_krw": 31_000_000,
                "retirement_pension_net_contribution_krw": 0,
                "pension_savings_isa_transfer_krw": 30_000_000,
                "prior_same_maturity_isa_extra_eligible_contribution_used_krw": (prior_used),
            }
        )


def test_accepts_income_pair_and_remaining_tax() -> None:
    value = _create_input(
        {
            "income_basis": "salary",
            "income_amount_krw": 50_000_000,
            "remaining_tax_before_pension_credit_krw": 1_000_000,
        }
    )

    assert value.income_basis == "salary"
    assert value.income_amount_krw == Decimal(50_000_000)
    assert value.remaining_tax_before_pension_credit_krw == Decimal(1_000_000)


def test_calculates_regular_eligible_contribution() -> None:
    result = calculate_pension_tax_credit(
        _create_input(
            {
                "income_basis": "salary",
                "income_amount_krw": 50_000_000,
            }
        )
    )

    assert result.outputs["regular_eligible_contribution_krw"] == Decimal(9_000_000)
    assert result.outputs["eligible_contribution_krw"] == Decimal(9_000_000)
    assert result.outputs["credit_rate_percent"] == Decimal("16.5")
    assert result.outputs["theoretical_credit_krw"] == Decimal(1_485_000)


def test_returns_both_rate_scenarios_when_income_is_missing() -> None:
    result = calculate_pension_tax_credit(_create_input())

    assert result.outputs["lower_income_rate_percent"] == Decimal("16.5")
    assert result.outputs["lower_income_theoretical_credit_krw"] == Decimal(1_485_000)
    assert result.outputs["other_income_rate_percent"] == Decimal("13.2")
    assert result.outputs["other_income_theoretical_credit_krw"] == Decimal(1_188_000)


def test_calculates_full_isa_extra_limit() -> None:
    value = PensionTaxCreditInput.model_validate(
        {
            "pension_savings_net_contribution_krw": 36_000_000,
            "retirement_pension_net_contribution_krw": 3_000_000,
            "pension_savings_isa_transfer_krw": 30_000_000,
            "prior_same_maturity_isa_extra_eligible_contribution_used_krw": 0,
            "income_basis": "salary",
            "income_amount_krw": 50_000_000,
        }
    )

    result = calculate_pension_tax_credit(value)

    assert result.outputs["regular_eligible_contribution_krw"] == Decimal(9_000_000)
    assert result.outputs["isa_extra_remaining_cap_krw"] == Decimal(3_000_000)
    assert result.outputs["isa_extra_limit_krw"] == Decimal(3_000_000)
    assert result.outputs["isa_extra_eligible_contribution_krw"] == Decimal(3_000_000)
    assert result.outputs["eligible_contribution_krw"] == Decimal(12_000_000)
    assert result.outputs["theoretical_credit_krw"] == Decimal(1_980_000)


def test_subtracts_prior_isa_extra_eligible_amount() -> None:
    value = PensionTaxCreditInput.model_validate(
        {
            "pension_savings_net_contribution_krw": 36_000_000,
            "retirement_pension_net_contribution_krw": 3_000_000,
            "pension_savings_isa_transfer_krw": 30_000_000,
            "prior_same_maturity_isa_extra_eligible_contribution_used_krw": (2_000_000),
            "income_basis": "salary",
            "income_amount_krw": 50_000_000,
        }
    )

    result = calculate_pension_tax_credit(value)

    assert result.outputs["isa_extra_remaining_cap_krw"] == Decimal(1_000_000)
    assert result.outputs["isa_extra_limit_krw"] == Decimal(1_000_000)
    assert result.outputs["eligible_contribution_krw"] == Decimal(10_000_000)


def test_does_not_exceed_total_net_contribution() -> None:
    value = PensionTaxCreditInput.model_validate(
        {
            "pension_savings_net_contribution_krw": 3_000_000,
            "retirement_pension_net_contribution_krw": 0,
            "pension_savings_isa_transfer_krw": 3_000_000,
            "prior_same_maturity_isa_extra_eligible_contribution_used_krw": 0,
        }
    )

    result = calculate_pension_tax_credit(value)

    assert result.outputs["isa_extra_limit_krw"] == Decimal(300_000)
    assert result.outputs["eligible_contribution_krw"] == Decimal(3_000_000)
    assert result.outputs["isa_extra_eligible_contribution_krw"] == Decimal(0)


@pytest.mark.parametrize(
    ("income_basis", "income_amount", "expected_rate"),
    [
        ("salary", 55_000_000, Decimal("16.5")),
        ("salary", 55_000_001, Decimal("13.2")),
        ("comprehensive_income", 45_000_000, Decimal("16.5")),
        ("comprehensive_income", 45_000_001, Decimal("13.2")),
    ],
)
def test_applies_income_rate_boundaries(
    income_basis: str,
    income_amount: int,
    expected_rate: Decimal,
) -> None:
    result = calculate_pension_tax_credit(
        _create_input(
            {
                "income_basis": income_basis,
                "income_amount_krw": income_amount,
            }
        )
    )

    assert result.outputs["credit_rate_percent"] == expected_rate


def test_limits_usable_credit_to_remaining_tax() -> None:
    result = calculate_pension_tax_credit(
        _create_input(
            {
                "income_basis": "salary",
                "income_amount_krw": 50_000_000,
                "remaining_tax_before_pension_credit_krw": 1_000_000,
            }
        )
    )

    assert result.outputs["theoretical_credit_krw"] == Decimal(1_485_000)
    assert result.outputs["usable_credit_krw"] == Decimal(1_000_000)


def test_does_not_round_fractional_tax_amount() -> None:
    value = PensionTaxCreditInput.model_validate(
        {
            "pension_savings_net_contribution_krw": 1,
            "retirement_pension_net_contribution_krw": 0,
            "income_basis": "salary",
            "income_amount_krw": 50_000_000,
        }
    )

    result = calculate_pension_tax_credit(value)

    assert result.outputs["theoretical_credit_krw"] == Decimal("0.165")
    assert result.units["theoretical_credit_krw"] == "KRW"
    assert result.warnings


def test_pension_tax_credit_is_registered() -> None:
    assert "pension_tax_credit" in CALCULATORS


def test_calculation_request_omits_unset_optional_inputs() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="pension_tax_credit",
            inputs=dict(_BASE_INPUTS),
        )
    )

    assert result.inputs.keys() == _BASE_INPUTS.keys()
    assert result.outputs["eligible_contribution_krw"] == Decimal(9_000_000)


def test_calculation_result_serializes_decimal_as_json_string() -> None:
    result = calculate(
        CalculationRequest(
            calculator_id="pension_tax_credit",
            inputs=dict(_BASE_INPUTS),
        )
    )

    payload = result.model_dump(mode="json")

    contribution_payload = payload["inputs"]["pension_savings_net_contribution_krw"]
    eligible_payload = payload["outputs"]["eligible_contribution_krw"]
    assert isinstance(contribution_payload, str)
    assert isinstance(eligible_payload, str)
    assert Decimal(contribution_payload) == Decimal(6_000_000)
    assert Decimal(eligible_payload) == Decimal(9_000_000)
