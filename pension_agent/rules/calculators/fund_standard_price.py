"""집합투자기구의 1,000좌당 기준가격 계산 규칙."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pension_agent.rules.models import (
    CalculationPayload,
    CalculatorMetadata,
    RuleSource,
)
from pension_agent.rules.registry import CalculatorDefinition

_Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_Units = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]


class FundStandardPriceInput(BaseModel):
    """기준가격 산정에 필요한 전일 자산·부채·총좌수."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_assets_krw: _Money
    total_liabilities_krw: _Money
    total_units: _Units

    @model_validator(mode="after")
    def validate_net_assets(self) -> FundStandardPriceInput:
        """순자산총액이 음수가 되는 입력을 거부한다."""

        if self.total_liabilities_krw > self.total_assets_krw:
            raise ValueError("부채총액은 자산총액보다 클 수 없습니다.")
        return self


def calculate_fund_standard_price(value: FundStandardPriceInput) -> CalculationPayload:
    """순자산총액을 총좌수로 나눈 뒤 1,000좌 단위 가격을 반올림한다."""

    with localcontext() as context:
        context.prec = 28
        price = (
            (value.total_assets_krw - value.total_liabilities_krw)
            / value.total_units
            * Decimal(1000)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return CalculationPayload(
        outputs={"standard_price_per_1000_units": price},
        units={"standard_price_per_1000_units": "KRW/1,000 units"},
    )


FUND_STANDARD_PRICE = CalculatorDefinition(
    metadata=CalculatorMetadata(
        calculator_id="fund_standard_price",
        version="1.0.0",
        display_name="집합투자기구 기준가격",
        description="순자산총액을 총좌수로 나누어 1,000좌당 기준가격을 계산한다.",
        status="active",
        domain_tags=frozenset({"product", "fund_price"}),
        sources=(
            RuleSource(
                family_id="b90977046022dd5ed540",
                candidate_id="50557c65895c523004ab",
                source_file_name="R2_KR510902511M.pdf",
                source_sha256=("bfc65bedacc9ff64f73414e7c5cd9ac13c241c9838611a983bb23d1abc715491"),
                page=24,
                section="12. 기준가격 산정기준 및 집합투자재산의 평가",
                locator="#/tables/31",
                drive_file_id="1Qf3hwVJJynrq-B_kNYV1_RX49j1biIgA",
                extraction_source="docling_bundle",
                parser_profile="docling-no-ocr-formula-v1",
            ),
        ),
    ),
    input_model=FundStandardPriceInput,
    calculate=calculate_fund_standard_price,
)
