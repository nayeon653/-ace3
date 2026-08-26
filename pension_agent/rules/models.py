"""Calculation Service의 입력·결과 계약."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CalculationScalar = Decimal | int | str | bool | None
_Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[a-z][a-z0-9_]*$"),
]


class CalculationRequest(BaseModel):
    """특정 계산기 실행 요청."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    calculator_id: _Identifier
    inputs: dict[str, Any]


class CalculationOutput(BaseModel):
    """개별 Python 계산 함수의 정규화 출력."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outputs: dict[str, CalculationScalar]
    units: dict[str, str] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_output_contract(self) -> CalculationOutput:
        """출력은 비어 있지 않고 단위 키는 실제 출력 키의 부분집합이어야 한다."""

        if not self.outputs:
            raise ValueError("계산 결과에는 하나 이상의 출력이 필요합니다.")
        unknown_units = self.units.keys() - self.outputs.keys()
        if unknown_units:
            raise ValueError("단위가 실제 계산 출력과 일치하지 않습니다.")
        return self


CalculatorCallable = Callable[[Any], CalculationOutput]


@dataclass(frozen=True, slots=True)
class CalculatorDefinition:
    """계산 함수와 해당 입력 모델을 묶는 최소 등록 단위."""

    input_model: type[BaseModel]
    calculate: CalculatorCallable


class CalculationResult(BaseModel):
    """계산기 ID와 정규화 입출력을 포함한 결정론적 계산 기록."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calculator_id: _Identifier
    inputs: dict[str, Any]
    outputs: dict[str, CalculationScalar]
    units: dict[str, str]
    warnings: tuple[str, ...]
