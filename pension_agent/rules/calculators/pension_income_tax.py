"""일반 연금수령과 부득이한 사유 인출의 연금소득세 계산 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pension_agent.rules.models import (
    CalculationOutput,
    CalculationScalar,
    CalculatorDefinition,
)

_Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_Age = Annotated[int, Field(ge=0)]
PensionTreatment = Literal["ordinary", "unavoidable"]

_ANNUAL_PRIVATE_PENSION_THRESHOLD = Decimal(15_000_000)
_RATE_55_TO_69 = Decimal("0.055")
_RATE_70_TO_79 = Decimal("0.044")
_RATE_80_OR_LIFETIME = Decimal("0.033")
_SEPARATE_TAX_OPTION_RATE = Decimal("0.165")
_NO_ROUNDING_WARNING = "출처에는 원 단위 세액의 반올림·절사 규칙이 명시되지 않았습니다."


class PensionIncomeTaxInput(BaseModel):
    """연금수령 유형과 확인된 과세대상 금액 조건."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pension_treatment: PensionTreatment
    recipient_age: _Age
    target_taxable_amount_krw: _Money | None = None
    is_lifetime_annuity: bool | None = None
    annual_private_pension_taxable_income_krw: _Money | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        """선택 필드 생략은 허용하되 명시적인 null은 거부한다."""

        if value is None:
            raise ValueError("명시적인 null 입력은 허용하지 않습니다.")
        return value

    @model_validator(mode="after")
    def validate_treatment_fields(self) -> Self:
        """일반 수령과 부득이한 사유의 입력 조건을 분리한다."""

        if self.pension_treatment == "ordinary":
            if self.recipient_age < 55:
                raise ValueError("일반 연금수령은 55세 이상이어야 합니다.")
            if self.is_lifetime_annuity is None:
                raise ValueError("일반 연금수령은 종신연금 여부가 필요합니다.")
        else:
            if self.is_lifetime_annuity is not None:
                raise ValueError("부득이한 사유 인출에는 종신연금 여부를 입력할 수 없습니다.")
            if self.annual_private_pension_taxable_income_krw is not None:
                raise ValueError(
                    "부득이한 사유 인출에는 연간 사적연금소득 합계를 입력할 수 없습니다."
                )

        target = self.target_taxable_amount_krw
        annual = self.annual_private_pension_taxable_income_krw
        if target is not None and annual is not None and target > annual:
            raise ValueError(
                "현재 과세대상액은 연간 과세대상 사적연금소득 합계를 초과할 수 없습니다."
            )

        return self


def _age_based_rate(age: int) -> Decimal:
    if age < 70:
        return _RATE_55_TO_69
    if age < 80:
        return _RATE_70_TO_79
    return _RATE_80_OR_LIFETIME


def calculate_pension_income_tax(value: PensionIncomeTaxInput) -> CalculationOutput:
    """수령 유형별 기본세율과 확정 가능한 세액만 계산한다."""

    if value.pension_treatment == "ordinary" and value.is_lifetime_annuity:
        base_rate = _RATE_80_OR_LIFETIME
    else:
        base_rate = _age_based_rate(value.recipient_age)

    outputs: dict[str, CalculationScalar] = {
        "base_rate_percent": base_rate * Decimal(100),
    }
    units = {"base_rate_percent": "%"}

    with localcontext() as context:
        context.prec = 28

        target = value.target_taxable_amount_krw
        annual = value.annual_private_pension_taxable_income_krw

        if value.pension_treatment == "unavoidable":
            if target is not None:
                tax = target * base_rate
                outputs.update(
                    {
                        "tax_krw": tax,
                        "after_tax_krw": target - tax,
                    }
                )
                units.update({"tax_krw": "KRW", "after_tax_krw": "KRW"})
        elif annual is None:
            outputs["annual_threshold_status"] = "unknown"
        elif annual <= _ANNUAL_PRIVATE_PENSION_THRESHOLD:
            outputs.update(
                {
                    "annual_threshold_status": "within",
                    "filing_choice_required": False,
                }
            )
            if target is not None:
                tax = target * base_rate
                outputs.update(
                    {
                        "tax_krw": tax,
                        "after_tax_krw": target - tax,
                    }
                )
                units.update({"tax_krw": "KRW", "after_tax_krw": "KRW"})
        else:
            separate_tax = annual * _SEPARATE_TAX_OPTION_RATE
            outputs.update(
                {
                    "annual_threshold_status": "exceeded",
                    "filing_choice_required": True,
                    "separate_tax_option_rate_percent": Decimal("16.5"),
                    "separate_tax_option_tax_krw": separate_tax,
                    "separate_tax_option_after_tax_krw": annual - separate_tax,
                }
            )
            units.update(
                {
                    "separate_tax_option_rate_percent": "%",
                    "separate_tax_option_tax_krw": "KRW",
                    "separate_tax_option_after_tax_krw": "KRW",
                }
            )

    return CalculationOutput(
        outputs=outputs,
        units=units,
        warnings=(_NO_ROUNDING_WARNING,),
    )


PENSION_INCOME_TAX = CalculatorDefinition(
    input_model=PensionIncomeTaxInput,
    calculate=calculate_pension_income_tax,
)
