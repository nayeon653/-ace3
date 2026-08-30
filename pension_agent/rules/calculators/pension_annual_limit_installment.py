"""남은 연간 연금수령한도의 회당 지급액 계산 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from pension_agent.rules.models import CalculationOutput, CalculatorDefinition

_Amount = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_Payments = Annotated[int, Field(ge=1)]


class PensionAnnualLimitInstallmentInput(BaseModel):
    """남은 연간 한도와 해당 연도의 남은 지급 횟수."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    remaining_annual_limit_krw: _Amount
    remaining_payments_in_year: _Payments


def calculate_pension_annual_limit_installment(
    value: PensionAnnualLimitInstallmentInput,
) -> CalculationOutput:
    """남은 연간 한도를 남은 지급 횟수로 나눈다."""

    with localcontext() as context:
        context.prec = 28
        installment = value.remaining_annual_limit_krw / Decimal(value.remaining_payments_in_year)
    return CalculationOutput(
        outputs={"installment_krw": installment},
        units={"installment_krw": "KRW"},
        warnings=("출처에는 원 단위 지급액의 반올림·절사 규칙이 명시되지 않았습니다.",),
    )


PENSION_ANNUAL_LIMIT_INSTALLMENT = CalculatorDefinition(
    input_model=PensionAnnualLimitInstallmentInput,
    calculate=calculate_pension_annual_limit_installment,
)
