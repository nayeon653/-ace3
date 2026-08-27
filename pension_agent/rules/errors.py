"""Calculation Service가 외부에 노출하는 정제된 오류."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InputIssue:
    """계산 입력의 한 필드에서 확인한 검증 오류."""

    field: str
    code: str


class CalculationError(RuntimeError):
    """Calculation Service의 예측 가능한 실행 실패."""


class CalculatorNotFoundError(CalculationError):
    """요청한 계산기를 찾을 수 없는 경우."""


class InvalidCalculationInputError(CalculationError):
    """계산 함수 호출 전에 입력 검증을 통과하지 못한 경우."""

    def __init__(self, issues: tuple[InputIssue, ...]) -> None:
        super().__init__("계산 입력이 올바르지 않습니다.")
        self.issues = issues


class CalculationExecutionError(CalculationError):
    """검증된 입력을 계산하는 동안 산술 조건을 만족하지 못한 경우."""
