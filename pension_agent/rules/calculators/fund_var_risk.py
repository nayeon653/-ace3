"""일간 수익률 2.5퍼센타일 손실률의 연환산 VaR와 위험등급 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from pension_agent.rules.models import (
    CalculationPayload,
    CalculatorMetadata,
    RuleSource,
)
from pension_agent.rules.registry import CalculatorDefinition

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


def calculate_fund_var_risk(value: FundVarRiskInput) -> CalculationPayload:
    """손실률 절대값에 √250을 곱하고 같은 문서의 위험등급표를 적용한다."""

    with localcontext() as context:
        context.prec = 28
        annualized_var = abs(value.daily_loss_percentile_percent) * Decimal(250).sqrt()
    grade = classify_var_risk_grade(annualized_var)
    return CalculationPayload(
        outputs={
            "annualized_var_percent": annualized_var,
            "risk_grade": grade,
            "risk_label": _RISK_LABELS[grade],
        },
        units={"annualized_var_percent": "%"},
        warnings=("출처에는 연환산 VaR의 표시 자릿수·반올림 규칙이 명시되지 않았습니다.",),
    )


_SOURCE_SHA256 = "7a8af3143e72224b2cab1bbca2342a27f8c302511e99f0f6b45f7044fb551fa5"
_SOURCE_DRIVE_ID = "1EINmViwKqHCyhVHVfRGH2qgIokLtnYMn"
FUND_VAR_RISK = CalculatorDefinition(
    metadata=CalculatorMetadata(
        calculator_id="fund_var_risk",
        version="1.0.0",
        display_name="펀드 97.5% VaR 위험등급",
        description="일간 손실률을 연환산하고 위험등급 상한표를 적용한다.",
        status="active",
        domain_tags=frozenset({"product", "risk"}),
        sources=(
            RuleSource(
                family_id="702a66c07e5c2e2d94cd",
                candidate_id="8d16937a57c7782f7ea5",
                source_file_name="R2_KR5160420009.pdf",
                source_sha256=_SOURCE_SHA256,
                page=20,
                section="라. 투자위험에 적합한 투자자 유형",
                locator="#/texts/277",
                drive_file_id=_SOURCE_DRIVE_ID,
                extraction_source="docling_bundle",
                parser_profile="docling-no-ocr-native-v1",
            ),
            RuleSource(
                family_id="a3ab54a1fcb7fd5cbf6f",
                candidate_id="b194a43dd27eab1c1a08",
                source_file_name="R2_KR5160420009.pdf",
                source_sha256=_SOURCE_SHA256,
                page=20,
                section="위험등급 기준표 (수익률 변동성 기준)",
                locator="#/tables/26",
                drive_file_id=_SOURCE_DRIVE_ID,
                extraction_source="docling_bundle",
                parser_profile="docling-no-ocr-native-v1",
            ),
        ),
    ),
    input_model=FundVarRiskInput,
    calculate=calculate_fund_var_risk,
)
