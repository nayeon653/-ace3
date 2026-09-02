"""현재 평가액의 남은 기간 회당 지급액 계산 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from pension_agent.rules.models import CalculationOutput, CalculatorDefinition

_Amount = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_Payments = Annotated[int, Field(ge=1)]


class PensionPeriodInstallmentInput(BaseModel):
    """현재 평가액과 남은 전체 지급 횟수."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    current_valuation_krw: _Amount
    remaining_payments: _Payments


def calculate_pension_period_installment(
    value: PensionPeriodInstallmentInput,
) -> CalculationOutput:
    """현재 평가액을 남은 지급 횟수로 나눈다."""

    with localcontext() as context:
        context.prec = 28
        installment = value.current_valuation_krw / Decimal(value.remaining_payments)
    return CalculationOutput(
        outputs={"installment_krw": installment},
        units={"installment_krw": "KRW"},
        warnings=("출처에는 원 단위 지급액의 반올림·절사 규칙이 명시되지 않았습니다.",),
    )


PENSION_PERIOD_INSTALLMENT = CalculatorDefinition(
    input_model=PensionPeriodInstallmentInput,
    calculate=calculate_pension_period_installment,
)
