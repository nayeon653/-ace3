"""검증·함수 실행·출처 직렬화를 하나의 결정론적 경계로 제공한다."""

from __future__ import annotations

from pydantic import ValidationError

from pension_agent.core import Permission
from pension_agent.rules.errors import (
    CalculationExecutionError,
    InputIssue,
    InvalidCalculationInputError,
)
from pension_agent.rules.models import CalculationRequest, CalculationResult
from pension_agent.rules.registry import CalculationRegistry


class CalculationService:
    """Registry의 active Python 계산기만 입력 검증 후 실행한다."""

    def __init__(self, registry: CalculationRegistry) -> None:
        self._registry = registry

    def calculate(
        self,
        request: CalculationRequest,
        *,
        permission: Permission | None = None,
    ) -> CalculationResult:
        """요청을 검증된 입력 모델로 변환하고 provenance를 포함해 반환한다."""

        definition = self._registry.resolve(
            request.calculator_id,
            version=request.version,
            effective_on=request.effective_on,
            permission=permission,
        )
        try:
            inputs = definition.input_model.model_validate(request.inputs)
        except ValidationError as exc:
            issues = tuple(
                InputIssue(
                    field=".".join(str(part) for part in error["loc"]),
                    code=error["type"],
                )
                for error in exc.errors(
                    include_url=False, include_context=False, include_input=False
                )
            )
            raise InvalidCalculationInputError(issues) from None

        try:
            payload = definition.calculate(inputs)
        except (ArithmeticError, ValueError):
            raise CalculationExecutionError("계산 산술 조건을 만족하지 못했습니다.") from None

        metadata = definition.metadata
        return CalculationResult(
            calculator_id=metadata.calculator_id,
            calculator_version=metadata.version,
            display_name=metadata.display_name,
            inputs=inputs.model_dump(mode="python"),
            outputs=payload.outputs,
            units=payload.units,
            domain_tags=metadata.domain_tags,
            source_rule_ids=tuple(source.family_id for source in metadata.sources),
            sources=metadata.sources,
            warnings=payload.warnings,
        )
