"""DB·DC 퇴직급여와 DB에서 DC로의 전환금액 계산 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from pension_agent.rules.models import CalculationOutput, CalculatorDefinition

_NonNegativeDecimal = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_SignedDecimal = Annotated[Decimal, Field(allow_inf_nan=False)]
_PositiveDays = Annotated[int, Field(ge=1)]

_NO_ROUNDING_WARNING = "출처에는 원 단위 금액의 반올림·절사 규칙이 명시되지 않았습니다."
_NEGATIVE_DC_BENEFIT_WARNING = "운용손실이 누적 부담금을 초과해 DC 퇴직급여 계산 결과가 음수입니다."


class DbRetirementBenefitInput(BaseModel):
    """검증된 평균임금 입력과 계속근로연수."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    wages_for_average_period_krw: _NonNegativeDecimal
    included_days_for_average_wage: _PositiveDays
    verified_service_years: _NonNegativeDecimal


def calculate_db_retirement_benefit(
    value: DbRetirementBenefitInput,
) -> CalculationOutput:
    """평균일급과 30일 평균임금을 거쳐 DB 퇴직급여를 계산한다."""

    with localcontext() as context:
        context.prec = 28
        average_daily_wage = value.wages_for_average_period_krw / Decimal(
            value.included_days_for_average_wage
        )
        average_wage_30_days = average_daily_wage * Decimal(30)
        retirement_benefit = average_wage_30_days * value.verified_service_years

    return CalculationOutput(
        outputs={
            "average_daily_wage": average_daily_wage,
            "average_wage_30_days": average_wage_30_days,
            "verified_service_years": value.verified_service_years,
            "retirement_benefit": retirement_benefit,
        },
        units={
            "average_daily_wage": "KRW/day",
            "average_wage_30_days": "KRW",
            "verified_service_years": "years",
            "retirement_benefit": "KRW",
        },
        warnings=(_NO_ROUNDING_WARNING,),
    )


class DcMinimumEmployerContributionInput(BaseModel):
    """DC 최소 사용자 부담금 산출에 쓰는 연간임금총액."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    annual_total_wages_krw: _NonNegativeDecimal


def calculate_dc_minimum_employer_contribution(
    value: DcMinimumEmployerContributionInput,
) -> CalculationOutput:
    """연간임금총액의 12분의 1을 DC 최소 사용자 부담금으로 계산한다."""

    with localcontext() as context:
        context.prec = 28
        minimum_contribution = value.annual_total_wages_krw / Decimal(12)

    return CalculationOutput(
        outputs={
            "annual_total_wages": value.annual_total_wages_krw,
            "minimum_employer_contribution": minimum_contribution,
        },
        units={
            "annual_total_wages": "KRW",
            "minimum_employer_contribution": "KRW",
        },
        warnings=(_NO_ROUNDING_WARNING,),
    )


class DcRetirementBenefitInput(BaseModel):
    """DC 퇴직급여 산출에 쓰는 누적 부담금과 운용손익."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    accumulated_contributions_krw: _NonNegativeDecimal
    investment_gain_loss_krw: _SignedDecimal


def calculate_dc_retirement_benefit(
    value: DcRetirementBenefitInput,
) -> CalculationOutput:
    """누적 부담금과 부호가 있는 운용손익을 합산한다."""

    retirement_benefit = value.accumulated_contributions_krw + value.investment_gain_loss_krw
    warnings = (_NEGATIVE_DC_BENEFIT_WARNING,) if retirement_benefit < 0 else ()
    return CalculationOutput(
        outputs={
            "accumulated_contributions": value.accumulated_contributions_krw,
            "investment_gain_loss": value.investment_gain_loss_krw,
            "retirement_benefit": retirement_benefit,
        },
        units={
            "accumulated_contributions": "KRW",
            "investment_gain_loss": "KRW",
            "retirement_benefit": "KRW",
        },
        warnings=warnings,
    )


class DbToDcTransferAmountInput(BaseModel):
    """DB에서 DC로 전환할 때 비교하는 두 임금 기준과 근속연수."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    final_average_wage_30_days_krw: _NonNegativeDecimal
    final_annual_total_wages_krw: _NonNegativeDecimal
    verified_service_years: _NonNegativeDecimal


def calculate_db_to_dc_transfer_amount(
    value: DbToDcTransferAmountInput,
) -> CalculationOutput:
    """두 월 기준금액 중 큰 값에 검증된 근속연수를 곱한다."""

    with localcontext() as context:
        context.prec = 28
        annual_wage_monthly_basis = value.final_annual_total_wages_krw / Decimal(12)
        if value.final_average_wage_30_days_krw > annual_wage_monthly_basis:
            selected_basis = value.final_average_wage_30_days_krw
            selected_basis_type = "average_wage_30_days"
        elif value.final_average_wage_30_days_krw < annual_wage_monthly_basis:
            selected_basis = annual_wage_monthly_basis
            selected_basis_type = "annual_wage_monthly_basis"
        else:
            selected_basis = value.final_average_wage_30_days_krw
            selected_basis_type = "equal"
        transfer_amount = selected_basis * value.verified_service_years

    return CalculationOutput(
        outputs={
            "final_average_wage_30_days": value.final_average_wage_30_days_krw,
            "annual_wage_monthly_basis": annual_wage_monthly_basis,
            "selected_basis": selected_basis,
            "selected_basis_type": selected_basis_type,
            "verified_service_years": value.verified_service_years,
            "transfer_amount": transfer_amount,
        },
        units={
            "final_average_wage_30_days": "KRW",
            "annual_wage_monthly_basis": "KRW",
            "selected_basis": "KRW",
            "verified_service_years": "years",
            "transfer_amount": "KRW",
        },
        warnings=(_NO_ROUNDING_WARNING,),
    )


DB_RETIREMENT_BENEFIT = CalculatorDefinition(
    input_model=DbRetirementBenefitInput,
    calculate=calculate_db_retirement_benefit,
)
DC_MINIMUM_EMPLOYER_CONTRIBUTION = CalculatorDefinition(
    input_model=DcMinimumEmployerContributionInput,
    calculate=calculate_dc_minimum_employer_contribution,
)
DC_RETIREMENT_BENEFIT = CalculatorDefinition(
    input_model=DcRetirementBenefitInput,
    calculate=calculate_dc_retirement_benefit,
)
DB_TO_DC_TRANSFER_AMOUNT = CalculatorDefinition(
    input_model=DbToDcTransferAmountInput,
    calculate=calculate_db_to_dc_transfer_amount,
)
