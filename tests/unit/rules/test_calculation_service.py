"""공용 Calculation Service의 등록·해석·검증 계약을 확인한다."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pension_agent.core import Permission
from pension_agent.rules import (
    CalculationPayload,
    CalculationRegistry,
    CalculationRequest,
    CalculationService,
    CalculatorDefinition,
    CalculatorMetadata,
    CalculatorNotActiveError,
    CalculatorNotFoundError,
    CalculatorPermissionDeniedError,
    CalculatorRegistrationError,
    CalculatorVersionRequiredError,
    InvalidCalculationInputError,
)


class _Input(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: Decimal = Field(ge=0)


def _definition(
    *,
    version: str = "1.0.0",
    status: str = "active",
    effective_from: date | None = None,
    effective_to: date | None = None,
    allowed_permissions: frozenset[Permission] | None = None,
) -> CalculatorDefinition:
    metadata = CalculatorMetadata(
        calculator_id="double_amount",
        version=version,
        display_name="금액 두 배",
        description="테스트 금액을 두 배로 계산한다.",
        status=status,
        domain_tags=frozenset({"test"}),
        effective_from=effective_from,
        effective_to=effective_to,
        allowed_permissions=allowed_permissions,
    )

    def calculate(value: _Input) -> CalculationPayload:
        return CalculationPayload(
            outputs={"doubled": value.amount * 2},
            units={"doubled": "KRW"},
        )

    return CalculatorDefinition(metadata=metadata, input_model=_Input, calculate=calculate)


def _service(definition: CalculatorDefinition | None = None) -> CalculationService:
    registry = CalculationRegistry()
    registry.register(definition or _definition())
    return CalculationService(registry)


def test_service_returns_normalized_result() -> None:
    result = _service().calculate(
        CalculationRequest(calculator_id="double_amount", inputs={"amount": "10.25"})
    )

    assert result.calculator_version == "1.0.0"
    assert result.inputs == {"amount": Decimal("10.25")}
    assert result.outputs == {"doubled": Decimal("20.50")}
    assert result.units == {"doubled": "KRW"}


def test_service_rejects_unknown_calculator() -> None:
    with pytest.raises(CalculatorNotFoundError):
        _service().calculate(CalculationRequest(calculator_id="missing", inputs={}))


def test_calculation_request_rejects_permission_from_payload() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CalculationRequest.model_validate(
            {
                "calculator_id": "double_amount",
                "inputs": {"amount": 1},
                "permission": "tax_payout",
            }
        )


def test_service_rejects_inactive_calculator() -> None:
    with pytest.raises(CalculatorNotActiveError):
        _service(_definition(status="reviewed")).calculate(
            CalculationRequest(calculator_id="double_amount", inputs={"amount": 1})
        )


def test_service_exposes_field_codes_without_raw_input() -> None:
    with pytest.raises(InvalidCalculationInputError) as captured:
        _service().calculate(
            CalculationRequest(calculator_id="double_amount", inputs={"amount": -1})
        )

    assert captured.value.issues[0].field == "amount"
    assert captured.value.issues[0].code == "greater_than_equal"
    assert "-1" not in str(captured.value)


def test_registry_rejects_duplicate_id_and_version() -> None:
    registry = CalculationRegistry()
    registry.register(_definition())

    with pytest.raises(CalculatorRegistrationError):
        registry.register(_definition())


def test_registry_requires_version_when_multiple_active_versions_match() -> None:
    registry = CalculationRegistry()
    registry.register(_definition(version="1.0.0"))
    registry.register(_definition(version="2.0.0"))

    with pytest.raises(CalculatorVersionRequiredError):
        CalculationService(registry).calculate(
            CalculationRequest(calculator_id="double_amount", inputs={"amount": 1})
        )


def test_registry_selects_version_by_effective_date() -> None:
    registry = CalculationRegistry()
    registry.register(
        _definition(
            version="1.0.0",
            effective_from=date(2025, 1, 1),
            effective_to=date(2025, 12, 31),
        )
    )
    registry.register(_definition(version="2.0.0", effective_from=date(2026, 1, 1)))

    result = CalculationService(registry).calculate(
        CalculationRequest(
            calculator_id="double_amount",
            inputs={"amount": 1},
            effective_on=date(2026, 8, 26),
        )
    )

    assert result.calculator_version == "2.0.0"


def test_registry_requires_allowed_permission_when_allowlist_is_configured() -> None:
    service = _service(_definition(allowed_permissions=frozenset({Permission.TAX_PAYOUT})))

    with pytest.raises(CalculatorPermissionDeniedError):
        service.calculate(CalculationRequest(calculator_id="double_amount", inputs={"amount": 1}))

    allowed = service.calculate(
        CalculationRequest(
            calculator_id="double_amount",
            inputs={"amount": 1},
        ),
        permission=Permission.TAX_PAYOUT,
    )
    assert allowed.outputs == {"doubled": Decimal(2)}

    with pytest.raises(CalculatorPermissionDeniedError):
        service.calculate(
            CalculationRequest(
                calculator_id="double_amount",
                inputs={"amount": 1},
            ),
            permission=Permission.PRODUCT,
        )


def test_same_request_returns_same_result() -> None:
    service = _service()
    request = CalculationRequest(calculator_id="double_amount", inputs={"amount": "1.1"})

    assert service.calculate(request) == service.calculate(request)


def test_metadata_rejects_effective_end_before_start() -> None:
    with pytest.raises(ValueError, match="종료일"):
        CalculatorMetadata(
            calculator_id="invalid_period",
            version="1.0.0",
            display_name="적용 기간 오류 계산기",
            description="적용 종료일이 시작일보다 빠른 계산기",
            status="active",
            domain_tags=frozenset({"test"}),
            effective_from=date(2026, 1, 2),
            effective_to=date(2026, 1, 1),
        )
