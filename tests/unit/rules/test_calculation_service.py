"""공용 Calculation Service의 등록·해석·검증 계약을 확인한다."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel, ConfigDict, Field

from pension_agent.rules import (
    CalculationPayload,
    CalculationRegistry,
    CalculationRequest,
    CalculationService,
    CalculatorConsumerNotAllowedError,
    CalculatorDefinition,
    CalculatorMetadata,
    CalculatorNotActiveError,
    CalculatorNotFoundError,
    CalculatorRegistrationError,
    CalculatorVersionRequiredError,
    InvalidCalculationInputError,
    RuleSource,
)


class _Input(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: Decimal = Field(ge=0)


def _source() -> RuleSource:
    return RuleSource(
        family_id="a" * 20,
        candidate_id="b" * 20,
        source_file_name="source.pdf",
        source_sha256="c" * 64,
        page=3,
        section="산정방법",
        locator="#/texts/1",
    )


def _definition(
    *,
    version: str = "1.0.0",
    status: str = "active",
    effective_from: date | None = None,
    effective_to: date | None = None,
    allowed_consumers: frozenset[str] | None = None,
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
        allowed_consumers=allowed_consumers,
        sources=(_source(),),
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


def test_service_returns_normalized_result_with_provenance() -> None:
    result = _service().calculate(
        CalculationRequest(calculator_id="double_amount", inputs={"amount": "10.25"})
    )

    assert result.calculator_version == "1.0.0"
    assert result.inputs == {"amount": Decimal("10.25")}
    assert result.outputs == {"doubled": Decimal("20.50")}
    assert result.units == {"doubled": "KRW"}
    assert result.source_rule_ids == ("a" * 20,)
    assert result.sources == (_source(),)


def test_service_rejects_unknown_calculator() -> None:
    with pytest.raises(CalculatorNotFoundError):
        _service().calculate(CalculationRequest(calculator_id="missing", inputs={}))


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


def test_registry_enforces_consumer_allowlist_only_when_consumer_is_supplied() -> None:
    service = _service(_definition(allowed_consumers=frozenset({"tax_payout"})))

    standalone = service.calculate(
        CalculationRequest(calculator_id="double_amount", inputs={"amount": 1})
    )
    assert standalone.outputs == {"doubled": Decimal(2)}

    with pytest.raises(CalculatorConsumerNotAllowedError):
        service.calculate(
            CalculationRequest(
                calculator_id="double_amount",
                inputs={"amount": 1},
                consumer="product",
            )
        )


def test_same_request_returns_same_result() -> None:
    service = _service()
    request = CalculationRequest(calculator_id="double_amount", inputs={"amount": "1.1"})

    assert service.calculate(request) == service.calculate(request)


def test_active_metadata_requires_source() -> None:
    with pytest.raises(ValueError, match="검증된 출처"):
        CalculatorMetadata(
            calculator_id="empty_source",
            version="1.0.0",
            display_name="출처 없는 계산기",
            description="등록되면 안 되는 계산기",
            status="active",
            domain_tags=frozenset({"test"}),
        )
