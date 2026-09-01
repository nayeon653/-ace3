"""ISA 만기자금 연금계좌 전환 마감일 계산 규칙."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic_core import PydanticCustomError

from pension_agent.rules.models import CalculationOutput, CalculationScalar, CalculatorDefinition

_ISO_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_TRANSFER_PERIOD_DAYS = 60


class IsaTransferDeadlineInput(BaseModel):
    """검증된 ISA 만기일과 선택적인 전환완료 처리일."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    isa_maturity_date: date
    transfer_completion_date: date | None = None

    @field_validator("*", mode="before")
    @classmethod
    def validate_exact_date(cls, value: Any) -> Any:
        """date 객체와 정확한 ISO 날짜만 허용하고 명시적 null을 거부한다."""
        if value is None:
            raise ValueError("명시적인 null 입력은 허용하지 않습니다.")
        if isinstance(value, datetime):
            raise PydanticCustomError("date_type", "시간이 포함된 날짜는 허용하지 않습니다.")
        if isinstance(value, date):
            return value
        if isinstance(value, str) and _ISO_DATE_PATTERN.fullmatch(value):
            return value
        raise ValueError("날짜는 YYYY-MM-DD 형식이어야 합니다.")

    @model_validator(mode="after")
    def validate_date_order(self) -> Self:
        """전환완료 처리일은 ISA 만기일보다 앞설 수 없다."""
        if (
            self.transfer_completion_date is not None
            and self.transfer_completion_date < self.isa_maturity_date
        ):
            raise ValueError("전환완료 처리일은 ISA 만기일보다 앞설 수 없습니다.")
        return self


def calculate_isa_transfer_deadline(
    value: IsaTransferDeadlineInput,
) -> CalculationOutput:
    """초일불산입 60 calendar days 마감일과 선택적인 적기 여부를 반환한다."""
    deadline = value.isa_maturity_date + timedelta(days=_TRANSFER_PERIOD_DAYS)
    outputs: dict[str, CalculationScalar] = {"transfer_deadline_date": deadline.isoformat()}
    if value.transfer_completion_date is not None:
        outputs["within_deadline"] = value.transfer_completion_date <= deadline
    return CalculationOutput(outputs=outputs)


ISA_TRANSFER_DEADLINE = CalculatorDefinition(
    input_model=IsaTransferDeadlineInput,
    calculate=calculate_isa_transfer_deadline,
)
