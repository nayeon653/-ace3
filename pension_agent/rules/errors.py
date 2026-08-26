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
    """요청한 계산기 또는 버전을 Registry에서 찾을 수 없는 경우."""


class CalculatorNotActiveError(CalculationError):
    """등록된 계산기가 실행 가능한 active 상태가 아닌 경우."""


class CalculatorVersionRequiredError(CalculationError):
    """실행 가능한 버전이 여러 개라 요청에서 버전을 지정해야 하는 경우."""


class CalculatorConsumerNotAllowedError(CalculationError):
    """요청 소비자가 계산기의 허용 목록에 포함되지 않은 경우."""


class CalculatorRegistrationError(CalculationError):
    """중복되거나 계약을 위반한 계산기를 등록하려는 경우."""


class InvalidCalculationInputError(CalculationError):
    """계산 함수 호출 전에 입력 검증을 통과하지 못한 경우."""

    def __init__(self, issues: tuple[InputIssue, ...]) -> None:
        super().__init__("계산 입력이 올바르지 않습니다.")
        self.issues = issues


class CalculationExecutionError(CalculationError):
    """검증된 입력을 계산하는 동안 산술 조건을 만족하지 못한 경우."""
