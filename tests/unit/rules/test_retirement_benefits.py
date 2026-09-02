"""DB·DC 퇴직급여와 DB에서 DC로의 전환금액 계약을 검증한다."""

from decimal import Decimal

import pytest

from pension_agent.rules import CalculationRequest, InvalidCalculationInputError, calculate


def _calculate(calculator_id: str, inputs: dict[str, object]):
    return calculate(CalculationRequest(calculator_id=calculator_id, inputs=inputs))


def _db_inputs(**updates: object) -> dict[str, object]:
    inputs: dict[str, object] = {
        "wages_for_average_period_krw": "9000000",
        "included_days_for_average_wage": 90,
        "verified_service_years": "3.5",
    }
    inputs.update(updates)
    return inputs


def test_db_retirement_benefit_preserves_decimal_intermediate_values() -> None:
    result = _calculate("db_retirement_benefit", _db_inputs())

    assert result.outputs == {
        "average_daily_wage": Decimal(100_000),
        "average_wage_30_days": Decimal(3_000_000),
        "verified_service_years": Decimal("3.5"),
        "retirement_benefit": Decimal(10_500_000),
    }


def test_db_retirement_benefit_accepts_one_included_day() -> None:
    result = _calculate(
        "db_retirement_benefit",
        _db_inputs(wages_for_average_period_krw="1.25", included_days_for_average_wage=1),
    )

    assert result.outputs["average_daily_wage"] == Decimal("1.25")
    assert result.outputs["average_wage_30_days"] == Decimal("37.50")
    assert result.outputs["retirement_benefit"] == Decimal("131.250")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("included_days_for_average_wage", 0),
        ("included_days_for_average_wage", -1),
        ("wages_for_average_period_krw", -1),
        ("verified_service_years", -1),
        ("wages_for_average_period_krw", None),
        ("included_days_for_average_wage", None),
        ("verified_service_years", None),
    ],
)
def test_db_retirement_benefit_rejects_invalid_inputs(field: str, value: object) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate("db_retirement_benefit", _db_inputs(**{field: value}))


@pytest.mark.parametrize(
    "missing_field",
    [
        "wages_for_average_period_krw",
        "included_days_for_average_wage",
        "verified_service_years",
    ],
)
def test_db_retirement_benefit_rejects_missing_inputs(missing_field: str) -> None:
    inputs = _db_inputs()
    del inputs[missing_field]

    with pytest.raises(InvalidCalculationInputError):
        _calculate("db_retirement_benefit", inputs)


@pytest.mark.parametrize(
    ("updates", "expected_benefit"),
    [
        ({"wages_for_average_period_krw": 0}, Decimal(0)),
        ({"verified_service_years": 0}, Decimal(0)),
    ],
)
def test_db_retirement_benefit_preserves_explicit_zero(
    updates: dict[str, object], expected_benefit: Decimal
) -> None:
    result = _calculate("db_retirement_benefit", _db_inputs(**updates))

    assert result.outputs["retirement_benefit"] == expected_benefit
    for field, value in updates.items():
        assert result.inputs[field] == Decimal(value)


def test_db_retirement_benefit_does_not_round_repeating_decimal() -> None:
    result = _calculate(
        "db_retirement_benefit",
        _db_inputs(
            wages_for_average_period_krw="1.1",
            included_days_for_average_wage=3,
            verified_service_years="3.5",
        ),
    )

    average = result.outputs["average_daily_wage"]
    assert isinstance(average, Decimal)
    assert len(str(average).replace(".", "")) >= 27


def test_dc_minimum_contribution_divides_annual_wages_by_twelve() -> None:
    result = _calculate(
        "dc_minimum_employer_contribution",
        {"annual_total_wages_krw": "12000001"},
    )

    assert result.outputs["annual_total_wages"] == Decimal(12_000_001)
    contribution = result.outputs["minimum_employer_contribution"]
    assert isinstance(contribution, Decimal)
    assert contribution == Decimal(12_000_001) / Decimal(12)
    assert len(str(contribution).replace(".", "")) >= 27


def test_dc_minimum_contribution_preserves_zero() -> None:
    result = _calculate("dc_minimum_employer_contribution", {"annual_total_wages_krw": 0})

    assert result.inputs["annual_total_wages_krw"] == Decimal(0)
    assert result.outputs["minimum_employer_contribution"] == Decimal(0)


@pytest.mark.parametrize("value", [-1, None])
def test_dc_minimum_contribution_rejects_negative_or_null(value: object) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate("dc_minimum_employer_contribution", {"annual_total_wages_krw": value})


def test_dc_minimum_contribution_rejects_missing_wages() -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate("dc_minimum_employer_contribution", {})


@pytest.mark.parametrize(
    ("contributions", "gain_loss", "expected"),
    [
        ("100", "25", Decimal(125)),
        ("100", "0", Decimal(100)),
        ("100", "-25", Decimal(75)),
        ("100", "-100", Decimal(0)),
        ("100", "-125", Decimal(-25)),
        ("0", "10", Decimal(10)),
    ],
)
def test_dc_retirement_benefit_preserves_signed_gain_loss(
    contributions: str, gain_loss: str, expected: Decimal
) -> None:
    result = _calculate(
        "dc_retirement_benefit",
        {
            "accumulated_contributions_krw": contributions,
            "investment_gain_loss_krw": gain_loss,
        },
    )

    assert result.outputs["retirement_benefit"] == expected
    if expected < 0:
        assert "음수" in result.warnings[0]
    else:
        assert result.warnings == ()


@pytest.mark.parametrize(
    "inputs",
    [
        {"accumulated_contributions_krw": -1, "investment_gain_loss_krw": 0},
        {"accumulated_contributions_krw": None, "investment_gain_loss_krw": 0},
        {"accumulated_contributions_krw": 0, "investment_gain_loss_krw": None},
        {"investment_gain_loss_krw": 0},
        {"accumulated_contributions_krw": 0},
    ],
)
def test_dc_retirement_benefit_rejects_invalid_or_missing_inputs(
    inputs: dict[str, object],
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate("dc_retirement_benefit", inputs)


def _transfer_inputs(**updates: object) -> dict[str, object]:
    inputs: dict[str, object] = {
        "final_average_wage_30_days_krw": "300",
        "final_annual_total_wages_krw": "2400",
        "verified_service_years": "3.5",
    }
    inputs.update(updates)
    return inputs


@pytest.mark.parametrize(
    ("updates", "basis", "basis_type", "transfer"),
    [
        ({}, Decimal(300), "average_wage_30_days", Decimal(1050)),
        (
            {"final_annual_total_wages_krw": "4800"},
            Decimal(400),
            "annual_wage_monthly_basis",
            Decimal(1400),
        ),
        (
            {"final_annual_total_wages_krw": "3600"},
            Decimal(300),
            "equal",
            Decimal(1050),
        ),
    ],
)
def test_db_to_dc_transfer_selects_larger_or_equal_basis(
    updates: dict[str, object], basis: Decimal, basis_type: str, transfer: Decimal
) -> None:
    result = _calculate("db_to_dc_transfer_amount", _transfer_inputs(**updates))

    assert result.outputs["selected_basis"] == basis
    assert result.outputs["selected_basis_type"] == basis_type
    assert result.outputs["verified_service_years"] == Decimal("3.5")
    assert result.outputs["transfer_amount"] == transfer


def test_db_to_dc_transfer_preserves_explicit_zero() -> None:
    result = _calculate(
        "db_to_dc_transfer_amount",
        _transfer_inputs(
            final_average_wage_30_days_krw=0,
            final_annual_total_wages_krw=0,
            verified_service_years=0,
        ),
    )

    assert result.outputs["selected_basis"] == Decimal(0)
    assert result.outputs["selected_basis_type"] == "equal"
    assert result.outputs["transfer_amount"] == Decimal(0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("final_average_wage_30_days_krw", -1),
        ("final_annual_total_wages_krw", -1),
        ("verified_service_years", -1),
        ("final_average_wage_30_days_krw", None),
        ("final_annual_total_wages_krw", None),
        ("verified_service_years", None),
    ],
)
def test_db_to_dc_transfer_rejects_negative_or_null(field: str, value: object) -> None:
    with pytest.raises(InvalidCalculationInputError):
        _calculate("db_to_dc_transfer_amount", _transfer_inputs(**{field: value}))


@pytest.mark.parametrize(
    "missing_field",
    [
        "final_average_wage_30_days_krw",
        "final_annual_total_wages_krw",
        "verified_service_years",
    ],
)
def test_db_to_dc_transfer_rejects_missing_inputs(missing_field: str) -> None:
    inputs = _transfer_inputs()
    del inputs[missing_field]

    with pytest.raises(InvalidCalculationInputError):
        _calculate("db_to_dc_transfer_amount", inputs)
