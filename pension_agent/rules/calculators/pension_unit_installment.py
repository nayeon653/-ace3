"""남은 좌수와 기준가격의 회당 지급액 계산 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from pension_agent.rules.models import CalculationOutput, CalculatorDefinition

_NonNegativeDecimal = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_Payments = Annotated[int, Field(ge=1)]


class PensionUnitInstallmentInput(BaseModel):
    """남은 좌수·지급 횟수와 1,000좌당 기준가격."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    remaining_units: _NonNegativeDecimal
    remaining_payments: _Payments
    standard_price_per_1000_units_krw: _NonNegativeDecimal


def calculate_pension_unit_installment(
    value: PensionUnitInstallmentInput,
) -> CalculationOutput:
    """회당 좌수에 1,000좌당 기준가격을 적용한다."""

    with localcontext() as context:
        context.prec = 28
        installment = (
            value.remaining_units
            / Decimal(value.remaining_payments)
            * value.standard_price_per_1000_units_krw
            / Decimal(1000)
        )
    return CalculationOutput(
        outputs={"installment_krw": installment},
        units={"installment_krw": "KRW"},
        warnings=("출처에는 좌수·원 단위 반올림·절사 규칙이 명시되지 않았습니다.",),
    )


PENSION_UNIT_INSTALLMENT = CalculatorDefinition(
    input_model=PensionUnitInstallmentInput,
    calculate=calculate_pension_unit_installment,
)
