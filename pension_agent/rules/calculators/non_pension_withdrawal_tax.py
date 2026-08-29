"""연금외수령 과세대상액의 세액 계산 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pension_agent.rules.models import (
    CalculationOutput,
    CalculationScalar,
    CalculatorDefinition,
)

_Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_NON_PENSION_WITHDRAWAL_RATE = Decimal("0.165")
_NO_ROUNDING_WARNING = "출처에는 원 단위 세액의 반올림·절사 규칙이 명시되지 않았습니다."


class NonPensionWithdrawalTaxInput(BaseModel):
    """연금외수령의 확인된 과세대상액."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    taxable_amount_krw: _Money | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        """금액 생략은 허용하되 명시적인 null은 거부한다."""

        if value is None:
            raise ValueError("명시적인 null 입력은 허용하지 않습니다.")
        return value


def calculate_non_pension_withdrawal_tax(
    value: NonPensionWithdrawalTaxInput,
) -> CalculationOutput:
    """연금외수령에 16.5%를 적용해 확정 가능한 세액을 계산한다."""

    outputs: dict[str, CalculationScalar] = {
        "base_rate_percent": Decimal("16.5"),
    }
    units = {"base_rate_percent": "%"}

    if value.taxable_amount_krw is not None:
        with localcontext() as context:
            context.prec = 28
            tax = value.taxable_amount_krw * _NON_PENSION_WITHDRAWAL_RATE
            outputs.update(
                {
                    "tax_krw": tax,
                    "after_tax_krw": value.taxable_amount_krw - tax,
                }
            )
            units.update({"tax_krw": "KRW", "after_tax_krw": "KRW"})

    return CalculationOutput(
        outputs=outputs,
        units=units,
        warnings=(_NO_ROUNDING_WARNING,),
    )


NON_PENSION_WITHDRAWAL_TAX = CalculatorDefinition(
    input_model=NonPensionWithdrawalTaxInput,
    calculate=calculate_non_pension_withdrawal_tax,
)
