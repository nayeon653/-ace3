"""이연퇴직소득세의 수령 유형·실제수령연차별 납부 비율 계산 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pension_agent.rules.models import (
    CalculationOutput,
    CalculationScalar,
    CalculatorDefinition,
)

_Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_ReceiptYear = Annotated[int, Field(ge=1)]
ReceiptType = Literal["pension", "non_pension"]

_NO_ROUNDING_WARNING = "출처에는 원 단위 세액의 반올림·절사 규칙이 명시되지 않았습니다."


class DeferredRetirementWithdrawalTaxInput(BaseModel):
    """수령 유형과 해당 인출분에 이미 배분된 이연퇴직소득세."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    receipt_type: ReceiptType
    actual_pension_receipt_year: _ReceiptYear | None = None
    allocated_deferred_retirement_tax_krw: _Money | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        """선택 필드 생략은 허용하되 명시적인 null은 거부한다."""

        if value is None:
            raise ValueError("명시적인 null 입력은 허용하지 않습니다.")
        return value

    @model_validator(mode="after")
    def validate_receipt_fields(self) -> Self:
        """수령 유형에 따른 실제수령연차 입력 조건을 검증한다."""

        if self.receipt_type == "pension":
            if self.actual_pension_receipt_year is None:
                raise ValueError("연금수령에는 실제수령연차가 필요합니다.")
        elif self.actual_pension_receipt_year is not None:
            raise ValueError("연금외수령에는 실제수령연차를 입력할 수 없습니다.")
        return self


def _payable_ratio(value: DeferredRetirementWithdrawalTaxInput) -> Decimal:
    if value.receipt_type == "non_pension":
        return Decimal(1)
    receipt_year = value.actual_pension_receipt_year
    if receipt_year is None:
        raise ValueError("연금수령 실제수령연차가 없습니다.")
    if receipt_year <= 10:
        return Decimal("0.70")
    if receipt_year <= 20:
        return Decimal("0.60")
    return Decimal("0.50")


def calculate_deferred_retirement_withdrawal_tax(
    value: DeferredRetirementWithdrawalTaxInput,
) -> CalculationOutput:
    """배분된 이연퇴직소득세에 납부·감면 비율을 적용한다."""

    payable_ratio = _payable_ratio(value)
    reduction_ratio = Decimal(1) - payable_ratio
    outputs: dict[str, CalculationScalar] = {
        "payable_ratio_percent": payable_ratio * Decimal(100),
        "reduction_ratio_percent": reduction_ratio * Decimal(100),
    }
    units = {
        "payable_ratio_percent": "%",
        "reduction_ratio_percent": "%",
    }

    allocated_tax = value.allocated_deferred_retirement_tax_krw
    if allocated_tax is not None:
        with localcontext() as context:
            context.prec = 28
            tax_payable = allocated_tax * payable_ratio
            outputs.update(
                {
                    "tax_payable_krw": tax_payable,
                    "tax_reduction_krw": allocated_tax - tax_payable,
                }
            )
            units.update(
                {
                    "tax_payable_krw": "KRW",
                    "tax_reduction_krw": "KRW",
                }
            )

    return CalculationOutput(
        outputs=outputs,
        units=units,
        warnings=(_NO_ROUNDING_WARNING,),
    )


DEFERRED_RETIREMENT_WITHDRAWAL_TAX = CalculatorDefinition(
    input_model=DeferredRetirementWithdrawalTaxInput,
    calculate=calculate_deferred_retirement_withdrawal_tax,
)
