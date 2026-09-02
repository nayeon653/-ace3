"""일간 수익률 2.5퍼센타일 손실률의 연환산 VaR와 위험등급 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from pension_agent.rules.models import CalculationOutput, CalculatorDefinition

_Percentage = Annotated[Decimal, Field(ge=-100, le=100, allow_inf_nan=False)]
_RISK_LABELS = {
    1: "매우 높은 위험",
    2: "높은 위험",
    3: "다소 높은 위험",
    4: "보통 위험",
    5: "낮은 위험",
    6: "매우 낮은 위험",
}


class FundVarRiskInput(BaseModel):
    """과거 3년 일간 수익률에서 산출한 2.5퍼센타일 손실률."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    daily_loss_percentile_percent: _Percentage


def classify_var_risk_grade(annualized_var_percent: Decimal) -> int:
    """문서의 상한치 표에 따라 97.5% VaR 위험등급을 반환한다."""

    if annualized_var_percent > 50:
        return 1
    if annualized_var_percent > 30:
        return 2
    if annualized_var_percent > 20:
        return 3
    if annualized_var_percent > 10:
        return 4
    if annualized_var_percent > 1:
        return 5
    return 6


def var_risk_label(grade: int) -> str:
    """검증된 VaR 위험등급의 표시명을 반환한다."""

    return _RISK_LABELS[grade]


def calculate_fund_var_risk(value: FundVarRiskInput) -> CalculationOutput:
    """손실률 절대값에 √250을 곱하고 같은 문서의 위험등급표를 적용한다."""

    with localcontext() as context:
        context.prec = 28
        annualized_var = abs(value.daily_loss_percentile_percent) * Decimal(250).sqrt()
    grade = classify_var_risk_grade(annualized_var)
    return CalculationOutput(
        outputs={
            "annualized_var_percent": annualized_var,
            "risk_grade": grade,
            "risk_label": var_risk_label(grade),
        },
        units={"annualized_var_percent": "%"},
        warnings=("출처에는 연환산 VaR의 표시 자릿수·반올림 규칙이 명시되지 않았습니다.",),
    )


FUND_VAR_RISK = CalculatorDefinition(
    input_model=FundVarRiskInput,
    calculate=calculate_fund_var_risk,
)
