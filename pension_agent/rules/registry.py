"""명시적으로 등록된 계산 함수와 버전을 조회한다."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel

from pension_agent.rules.errors import (
    CalculatorConsumerNotAllowedError,
    CalculatorNotActiveError,
    CalculatorNotFoundError,
    CalculatorRegistrationError,
    CalculatorVersionRequiredError,
)
from pension_agent.rules.models import CalculationPayload, CalculatorMetadata

CalculatorCallable = Callable[[Any], CalculationPayload]


@dataclass(frozen=True, slots=True)
class CalculatorDefinition:
    """계산 함수 하나와 그 입력·메타데이터 계약."""

    metadata: CalculatorMetadata
    input_model: type[BaseModel]
    calculate: CalculatorCallable


class CalculationRegistry:
    """문자열 수식 실행 없이 등록된 Python 함수만 해석한다."""

    def __init__(self) -> None:
        self._definitions: dict[tuple[str, str], CalculatorDefinition] = {}

    def register(self, definition: CalculatorDefinition) -> None:
        """계산기 ID와 버전의 중복 없이 함수를 등록한다."""

        metadata = definition.metadata
        key = (metadata.calculator_id, metadata.version)
        if key in self._definitions:
            raise CalculatorRegistrationError("동일한 계산기 버전이 이미 등록되어 있습니다.")
        self._definitions[key] = definition

    def resolve(
        self,
        calculator_id: str,
        *,
        version: str | None = None,
        effective_on: date | None = None,
        consumer: str | None = None,
    ) -> CalculatorDefinition:
        """상태·적용일·소비 권한을 만족하는 계산기 하나를 반환한다."""

        all_versions = [
            definition
            for (registered_id, _), definition in self._definitions.items()
            if registered_id == calculator_id
        ]
        if not all_versions:
            raise CalculatorNotFoundError("등록된 계산기를 찾을 수 없습니다.")

        if version is not None:
            definitions = [
                definition for definition in all_versions if definition.metadata.version == version
            ]
            if not definitions:
                raise CalculatorNotFoundError("등록된 계산기 버전을 찾을 수 없습니다.")
        else:
            definitions = all_versions

        active = [
            definition
            for definition in definitions
            if definition.metadata.status == "active"
            and (effective_on is None or definition.metadata.applies_on(effective_on))
        ]
        if not active:
            raise CalculatorNotActiveError("실행 가능한 계산기 규칙이 없습니다.")
        if len(active) != 1:
            raise CalculatorVersionRequiredError("계산기 버전 또는 적용일을 지정해야 합니다.")

        definition = active[0]
        allowed = definition.metadata.allowed_consumers
        if consumer is not None and allowed is not None and consumer not in allowed:
            raise CalculatorConsumerNotAllowedError("이 소비자는 계산기를 사용할 수 없습니다.")
        return definition

    def definitions(self) -> tuple[CalculatorDefinition, ...]:
        """등록 순서와 무관하게 정렬된 읽기 전용 스냅샷을 반환한다."""

        return tuple(
            sorted(
                self._definitions.values(),
                key=lambda item: (item.metadata.calculator_id, item.metadata.version),
            )
        )
