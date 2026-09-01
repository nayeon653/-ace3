"""ISA 만기자금 연금전환 60일 마감일 계산기 회귀 테스트."""

from datetime import date

import pytest

from pension_agent.rules import (
    CalculationRequest,
    CalculationResult,
    InvalidCalculationInputError,
    calculate,
)


def _calculate(maturity: object, completion: object = ...) -> CalculationResult:
    inputs = {"isa_maturity_date": maturity}
    if completion is not ...:
        inputs["transfer_completion_date"] = completion
    return calculate(CalculationRequest(calculator_id="isa_transfer_deadline", inputs=inputs))


@pytest.mark.parametrize(
    ("maturity", "deadline"),
    [
        ("2026-04-15", "2026-06-14"),
        ("2026-01-31", "2026-04-01"),
        ("2026-02-01", "2026-04-02"),
        ("2024-02-01", "2024-04-01"),
        ("2026-12-31", "2027-03-01"),
    ],
)
def test_deadline_uses_sixty_calendar_days_excluding_maturity_date(
    maturity: str,
    deadline: str,
) -> None:
    result = _calculate(maturity)

    assert result.outputs == {"transfer_deadline_date": deadline}
    assert result.units == {}


@pytest.mark.parametrize(
    ("completion", "within_deadline"),
    [
        ("2026-06-13", True),
        ("2026-06-14", True),
        ("2026-06-15", False),
    ],
)
def test_completion_date_includes_exact_deadline(
    completion: str,
    within_deadline: bool,
) -> None:
    result = _calculate("2026-04-15", completion)

    assert result.outputs == {
        "transfer_deadline_date": "2026-06-14",
        "within_deadline": within_deadline,
    }


def test_calculator_accepts_date_objects() -> None:
    result = _calculate(date(2026, 4, 15), date(2026, 6, 14))

    assert result.inputs == {
        "isa_maturity_date": date(2026, 4, 15),
        "transfer_completion_date": date(2026, 6, 14),
    }
    assert result.outputs["within_deadline"] is True


@pytest.mark.parametrize(
    "inputs",
    [
        {},
        {"isa_maturity_date": None},
        {"isa_maturity_date": "2026-02-30"},
        {"isa_maturity_date": "2026/04/15"},
        {"isa_maturity_date": "2026-04"},
        {"isa_maturity_date": "2026-04-15T00:00:00"},
        {"isa_maturity_date": "2026-04-15", "transfer_completion_date": None},
        {
            "isa_maturity_date": "2026-04-15",
            "transfer_completion_date": "2026-04-14",
        },
    ],
)
def test_calculator_rejects_missing_null_malformed_and_reversed_dates(
    inputs: dict[str, object],
) -> None:
    with pytest.raises(InvalidCalculationInputError):
        calculate(CalculationRequest(calculator_id="isa_transfer_deadline", inputs=inputs))


def test_same_request_is_deterministic() -> None:
    first = _calculate("2026-12-31", "2027-03-01")
    second = _calculate("2026-12-31", "2027-03-01")

    assert first == second
