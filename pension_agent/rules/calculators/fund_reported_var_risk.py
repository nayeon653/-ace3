"""공시된 연환산 VaR의 위험등급 판정 규칙."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from pension_agent.rules.calculators.fund_var_risk import (
    classify_var_risk_grade,
    var_risk_label,
)
from pension_agent.rules.models import CalculationOutput, CalculatorDefinition

_AnnualizedVar = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class FundReportedVarRiskInput(BaseModel):
    """투자설명서에 결과값으로 공시된 연환산 97.5% VaR."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    annualized_var_percent: _AnnualizedVar


def calculate_fund_reported_var_risk(
    value: FundReportedVarRiskInput,
) -> CalculationOutput:
    """공시 연환산 VaR를 추가 변환 없이 위험등급표에 적용한다."""

    grade = classify_var_risk_grade(value.annualized_var_percent)
    return CalculationOutput(
        outputs={
            "annualized_var_percent": value.annualized_var_percent,
            "risk_grade": grade,
            "risk_label": var_risk_label(grade),
        },
        units={"annualized_var_percent": "%"},
    )


FUND_REPORTED_VAR_RISK = CalculatorDefinition(
    input_model=FundReportedVarRiskInput,
    calculate=calculate_fund_reported_var_risk,
)
