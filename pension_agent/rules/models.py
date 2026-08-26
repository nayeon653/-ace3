"""Calculation Service의 입력·결과 계약."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from pension_agent.core import Permission

RuleStatus = Literal["candidate", "draft", "reviewed", "active", "retired", "blocked"]
CalculationScalar = Decimal | int | str | bool | None
_Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[a-z][a-z0-9_]*$"),
]
_Version = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$"),
]


class CalculatorMetadata(BaseModel):
    """등록된 계산 함수의 버전·상태·적용 범위."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    calculator_id: _Identifier
    version: _Version
    display_name: Annotated[str, StringConstraints(min_length=1)]
    description: Annotated[str, StringConstraints(min_length=1)]
    status: RuleStatus
    domain_tags: frozenset[_Identifier] = Field(min_length=1)
    effective_from: date | None = None
    effective_to: date | None = None
    allowed_permissions: frozenset[Permission] | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> CalculatorMetadata:
        """적용 종료일이 시작일보다 빠르지 않은지 검증한다."""

        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("규칙 적용 종료일은 시작일보다 빠를 수 없습니다.")
        return self

    def applies_on(self, target: date) -> bool:
        """요청 기준일이 이 규칙의 적용 기간에 포함되는지 반환한다."""

        if self.effective_from is not None and target < self.effective_from:
            return False
        return self.effective_to is None or target <= self.effective_to


class CalculationRequest(BaseModel):
    """특정 계산기 실행 요청."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    calculator_id: _Identifier
    inputs: dict[str, Any]
    version: _Version | None = None
    effective_on: date | None = None


class CalculationPayload(BaseModel):
    """개별 Python 함수가 Service에 반환하는 정규화 결과."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outputs: dict[str, CalculationScalar]
    units: dict[str, str] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_output_contract(self) -> CalculationPayload:
        """출력은 비어 있지 않고 단위 키는 실제 출력 키의 부분집합이어야 한다."""

        if not self.outputs:
            raise ValueError("계산 결과에는 하나 이상의 출력이 필요합니다.")
        unknown_units = self.units.keys() - self.outputs.keys()
        if unknown_units:
            raise ValueError("단위가 실제 계산 출력과 일치하지 않습니다.")
        return self


class CalculationResult(BaseModel):
    """함수 버전과 정규화 입출력을 포함한 결정론적 계산 기록."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calculator_id: _Identifier
    calculator_version: _Version
    display_name: str
    inputs: dict[str, Any]
    outputs: dict[str, CalculationScalar]
    units: dict[str, str]
    domain_tags: frozenset[str]
    warnings: tuple[str, ...]
