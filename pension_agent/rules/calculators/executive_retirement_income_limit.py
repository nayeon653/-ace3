"""임원 퇴직소득 한도와 한도초과 근로소득 계산 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pension_agent.rules.models import CalculationOutput, CalculationScalar, CalculatorDefinition

_Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_Months = Annotated[int, Field(ge=0)]

_PRE_2020_MULTIPLIER = Decimal(3)
_POST_2020_MULTIPLIER = Decimal(2)
_TENTH = Decimal("0.1")
_MONTHS_PER_YEAR = Decimal(12)


class ExecutiveRetirementIncomeLimitInput(BaseModel):
    """법정 산정이 끝난 기간별 평균 연환산 급여·근무월수와 선택 지급액."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    average_annualized_salary_2012_2019_krw: _Money | None = None
    service_months_2012_2019: _Months | None = None
    average_annualized_salary_2020_onward_krw: _Money | None = None
    service_months_2020_onward: _Months | None = None
    post_2011_limit_subject_payment_krw: _Money | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("명시적인 null 입력은 허용하지 않습니다.")
        return value

    @model_validator(mode="after")
    def validate_period_pairs(self) -> Self:
        """각 기간은 급여와 근무월수를 함께 받고, 최소 한 기간이 있어야 한다."""

        has_2012_2019 = self.average_annualized_salary_2012_2019_krw is not None
        if has_2012_2019 != (self.service_months_2012_2019 is not None):
            raise ValueError("2012~2019년 구간은 급여와 근무월수를 함께 입력해야 합니다.")
        has_2020_onward = self.average_annualized_salary_2020_onward_krw is not None
        if has_2020_onward != (self.service_months_2020_onward is not None):
            raise ValueError("2020년 이후 구간은 급여와 근무월수를 함께 입력해야 합니다.")
        if not has_2012_2019 and not has_2020_onward:
            raise ValueError("2012~2019년 또는 2020년 이후 구간 중 최소 하나는 입력해야 합니다.")
        return self


def calculate_executive_retirement_income_limit(
    value: ExecutiveRetirementIncomeLimitInput,
) -> CalculationOutput:
    """두 기간별 구성액을 합산해 한도를 계산하고, 지급액이 있으면 인정액·초과액을 나눈다."""

    with localcontext() as context:
        context.prec = 28
        limit_2012_2019 = Decimal(0)
        if value.average_annualized_salary_2012_2019_krw is not None:
            months = value.service_months_2012_2019
            assert months is not None
            limit_2012_2019 = (
                value.average_annualized_salary_2012_2019_krw
                * _TENTH
                * Decimal(months)
                / _MONTHS_PER_YEAR
                * _PRE_2020_MULTIPLIER
            )
        limit_2020_onward = Decimal(0)
        if value.average_annualized_salary_2020_onward_krw is not None:
            months = value.service_months_2020_onward
            assert months is not None
            limit_2020_onward = (
                value.average_annualized_salary_2020_onward_krw
                * _TENTH
                * Decimal(months)
                / _MONTHS_PER_YEAR
                * _POST_2020_MULTIPLIER
            )
        total_limit = limit_2012_2019 + limit_2020_onward

    outputs: dict[str, CalculationScalar] = {
        "limit_2012_2019_krw": limit_2012_2019,
        "limit_2020_onward_krw": limit_2020_onward,
        "post_2011_total_limit_krw": total_limit,
    }
    units = {key: "KRW" for key in outputs}

    payment = value.post_2011_limit_subject_payment_krw
    if payment is not None:
        with localcontext() as context:
            context.prec = 28
            recognized = min(payment, total_limit)
            excess = max(payment - total_limit, Decimal(0))
        outputs["retirement_income_amount_krw"] = recognized
        outputs["wage_income_excess_krw"] = excess
        units["retirement_income_amount_krw"] = "KRW"
        units["wage_income_excess_krw"] = "KRW"

    return CalculationOutput(outputs=outputs, units=units)


EXECUTIVE_RETIREMENT_INCOME_LIMIT = CalculatorDefinition(
    input_model=ExecutiveRetirementIncomeLimitInput,
    calculate=calculate_executive_retirement_income_limit,
)
