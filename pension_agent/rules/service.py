"""등록된 계산 함수를 입력 검증 후 실행한다."""

from __future__ import annotations

from pydantic import ValidationError

from pension_agent.rules.calculators import CALCULATORS
from pension_agent.rules.errors import (
    CalculationExecutionError,
    CalculatorNotFoundError,
    InputIssue,
    InvalidCalculationInputError,
)
from pension_agent.rules.models import CalculationRequest, CalculationResult


def calculate(request: CalculationRequest) -> CalculationResult:
    """계산기 ID를 명시적 함수에 연결하고 정규화 결과를 반환한다."""

    definition = CALCULATORS.get(request.calculator_id)
    if definition is None:
        raise CalculatorNotFoundError("등록된 계산기를 찾을 수 없습니다.")

    try:
        inputs = definition.input_model.model_validate(request.inputs)
    except ValidationError as exc:
        issues = tuple(
            InputIssue(
                field=".".join(str(part) for part in error["loc"]),
                code=error["type"],
            )
            for error in exc.errors(
                include_url=False,
                include_context=False,
                include_input=False,
            )
        )
        raise InvalidCalculationInputError(issues) from None

    try:
        output = definition.calculate(inputs)
    except (ArithmeticError, ValueError):
        raise CalculationExecutionError(
            "계산 산술 조건을 만족하지 못했습니다."
        ) from None

    return CalculationResult(
        calculator_id=request.calculator_id,
        inputs=inputs.model_dump(
            mode="python",
            exclude_unset=True,
            exclude_none=True,
        ),
        outputs=output.outputs,
        units=output.units,
        warnings=output.warnings,
    )