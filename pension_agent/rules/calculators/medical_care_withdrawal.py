"""DC 의료비 기준과 의료·요양 인출 저율과세 계산 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated, Any, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pension_agent.rules.calculators.pension_income_tax import (
    PensionIncomeTaxInput,
    calculate_pension_income_tax,
)
from pension_agent.rules.models import CalculationOutput, CalculationScalar, CalculatorDefinition

_Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_Age = Annotated[int, Field(ge=0)]
_LeaveMonths = Annotated[int, Field(ge=0)]
EmploymentDurationCategory = Literal["less_than_one_year", "at_least_one_year"]

_DC_THRESHOLD_RATE = Decimal("0.125")
_MONTHS_PER_YEAR = Decimal(12)
_BASE_TAX_LIMIT = Decimal(2_000_000)
_MONTHLY_LEAVE_LIMIT = Decimal(1_500_000)
_EXCESS_TAX_WARNING = (
    "초과액은 재원과 연금수령·연금외수령 구분이 없어 세액과 세후액을 확정할 수 없습니다."
)


class DcMedicalWithdrawalThresholdInput(BaseModel):
    """DC 의료비 기준 산출에 필요한 확인된 임금과 의료비."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    employment_duration_category: EmploymentDurationCategory
    documented_medical_expenses_krw: _Money
    previous_year_annual_wages_krw: _Money | None = None
    preceding_12_month_wages_krw: _Money | None = None
    average_monthly_wage_during_employment_krw: _Money | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("명시적인 null 입력은 허용하지 않습니다.")
        return value

    @model_validator(mode="after")
    def validate_wage_inputs(self) -> Self:
        if self.employment_duration_category == "at_least_one_year":
            if self.previous_year_annual_wages_krw is None:
                raise ValueError("재직 1년 이상은 직전연도 연간임금총액이 필요합니다.")
            if self.average_monthly_wage_during_employment_krw is not None:
                raise ValueError("재직 1년 이상에는 재직 중 월평균 급여를 입력할 수 없습니다.")
        else:
            if self.average_monthly_wage_during_employment_krw is None:
                raise ValueError("재직 1년 미만은 재직 중 월평균 급여가 필요합니다.")
            if self.previous_year_annual_wages_krw is not None:
                raise ValueError("재직 1년 미만에는 직전연도 연간임금을 입력할 수 없습니다.")
            if self.preceding_12_month_wages_krw is not None:
                raise ValueError("재직 1년 미만에는 직전 12개월 임금을 입력할 수 없습니다.")
        return self


def calculate_dc_medical_withdrawal_threshold(
    value: DcMedicalWithdrawalThresholdInput,
) -> CalculationOutput:
    """적용 임금과 12.5% 기준 및 증빙 의료비의 엄격한 초과 여부를 반환한다."""

    if value.employment_duration_category == "at_least_one_year":
        previous_year_wages = value.previous_year_annual_wages_krw
        if previous_year_wages is None:
            raise ValueError("직전연도 연간임금총액이 필요합니다.")
        preceding_wages = value.preceding_12_month_wages_krw
        if preceding_wages is not None and preceding_wages < previous_year_wages:
            applicable_wages = preceding_wages
            wage_basis = "preceding_12_month_wages"
        else:
            applicable_wages = previous_year_wages
            wage_basis = "previous_year_annual_wages"
    else:
        average_monthly_wage = value.average_monthly_wage_during_employment_krw
        if average_monthly_wage is None:
            raise ValueError("재직 중 월평균 급여가 필요합니다.")
        applicable_wages = average_monthly_wage * _MONTHS_PER_YEAR
        wage_basis = "annualized_average_monthly_wage"

    threshold = applicable_wages * _DC_THRESHOLD_RATE
    return CalculationOutput(
        outputs={
            "applicable_wages_krw": applicable_wages,
            "wage_basis": wage_basis,
            "medical_expense_threshold_krw": threshold,
            "threshold_met": value.documented_medical_expenses_krw > threshold,
        },
        units={
            "applicable_wages_krw": "KRW",
            "medical_expense_threshold_krw": "KRW",
        },
    )


class MedicalCareWithdrawalTaxLimitInput(BaseModel):
    """의료·요양 사유의 총 요청액과 저율과세 한도 구성요소."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_withdrawal_krw: _Money
    actual_medical_expenses_krw: _Money
    care_expenses_krw: _Money
    own_leave_months: _LeaveMonths

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("명시적인 null 입력은 허용하지 않습니다.")
        return value


def calculate_medical_care_withdrawal_tax_limit(
    value: MedicalCareWithdrawalTaxLimitInput,
) -> CalculationOutput:
    """저율과세 한도와 총 요청액의 한도 내·초과 금액을 반환한다."""

    with localcontext() as context:
        context.prec = 28
        tax_limit = (
            _BASE_TAX_LIMIT
            + value.actual_medical_expenses_krw
            + value.care_expenses_krw
            + Decimal(value.own_leave_months) * _MONTHLY_LEAVE_LIMIT
        )
        amount_within_limit = min(value.requested_withdrawal_krw, tax_limit)
        excess_amount = value.requested_withdrawal_krw - amount_within_limit

    outputs: dict[str, CalculationScalar] = {
        "tax_limit_krw": tax_limit,
        "amount_within_limit_krw": amount_within_limit,
        "excess_amount_krw": excess_amount,
    }
    return CalculationOutput(outputs=outputs, units={key: "KRW" for key in outputs})


class MedicalCareWithdrawalTaxBreakdownInput(MedicalCareWithdrawalTaxLimitInput):
    """의료·요양 한도 원 입력과 정확한 수령자 나이."""

    recipient_age: _Age


def calculate_medical_care_withdrawal_tax_breakdown(
    value: MedicalCareWithdrawalTaxBreakdownInput,
) -> CalculationOutput:
    """한도 내 금액에 #113 부득이한 사유 세율을 적용한다."""

    limit_result = calculate_medical_care_withdrawal_tax_limit(
        MedicalCareWithdrawalTaxLimitInput(
            requested_withdrawal_krw=value.requested_withdrawal_krw,
            actual_medical_expenses_krw=value.actual_medical_expenses_krw,
            care_expenses_krw=value.care_expenses_krw,
            own_leave_months=value.own_leave_months,
        )
    )
    tax_limit = cast(Decimal, limit_result.outputs["tax_limit_krw"])
    amount_within_limit = cast(Decimal, limit_result.outputs["amount_within_limit_krw"])
    excess_amount = cast(Decimal, limit_result.outputs["excess_amount_krw"])

    within_limit_result = calculate_pension_income_tax(
        PensionIncomeTaxInput(
            pension_treatment="unavoidable",
            recipient_age=value.recipient_age,
            target_taxable_amount_krw=amount_within_limit,
        )
    )
    rate = cast(Decimal, within_limit_result.outputs["base_rate_percent"])
    tax = cast(Decimal, within_limit_result.outputs["tax_krw"])
    after_tax = cast(Decimal, within_limit_result.outputs["after_tax_krw"])

    current_tax: Decimal | None = tax if excess_amount == 0 else None
    current_after_tax: Decimal | None = after_tax if excess_amount == 0 else None
    outputs: dict[str, CalculationScalar] = {
        "tax_limit_krw": tax_limit,
        "amount_within_limit_krw": amount_within_limit,
        "within_limit_tax_rate_percent": rate,
        "within_limit_tax_krw": tax,
        "within_limit_after_tax_krw": after_tax,
        "excess_amount_krw": excess_amount,
        "current_withdrawal_tax_krw": current_tax,
        "current_withdrawal_after_tax_krw": current_after_tax,
    }
    warnings = within_limit_result.warnings
    if excess_amount > 0:
        warnings = (*warnings, _EXCESS_TAX_WARNING)
    return CalculationOutput(
        outputs=outputs,
        units={key: "%" if key == "within_limit_tax_rate_percent" else "KRW" for key in outputs},
        warnings=warnings,
    )


DC_MEDICAL_WITHDRAWAL_THRESHOLD = CalculatorDefinition(
    input_model=DcMedicalWithdrawalThresholdInput,
    calculate=calculate_dc_medical_withdrawal_threshold,
)
MEDICAL_CARE_WITHDRAWAL_TAX_LIMIT = CalculatorDefinition(
    input_model=MedicalCareWithdrawalTaxLimitInput,
    calculate=calculate_medical_care_withdrawal_tax_limit,
)
MEDICAL_CARE_WITHDRAWAL_TAX_BREAKDOWN = CalculatorDefinition(
    input_model=MedicalCareWithdrawalTaxBreakdownInput,
    calculate=calculate_medical_care_withdrawal_tax_breakdown,
)
