"""납입금액·환매금액·이익금 기준 펀드 판매·환매수수료 계산 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from pension_agent.rules.models import CalculationOutput, CalculatorDefinition

_Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_RatePercent = Annotated[Decimal, Field(ge=0, le=100, allow_inf_nan=False)]
RateKind = Literal["fixed", "maximum"]


def _fee_output(amount: Decimal, rate_kind: RateKind) -> CalculationOutput:
    """고정 요율은 fee_amount_krw, 상한 요율은 maximum_fee_amount_krw로만 반환한다."""

    key = "fee_amount_krw" if rate_kind == "fixed" else "maximum_fee_amount_krw"
    return CalculationOutput(outputs={key: amount}, units={key: "KRW"})


class FundFrontendSalesFeeInput(BaseModel):
    """가입 시 납입금액에 적용하는 선취판매수수료율."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subscription_amount_krw: _Money
    selected_rate_percent: _RatePercent
    rate_kind: RateKind


def calculate_fund_frontend_sales_fee(value: FundFrontendSalesFeeInput) -> CalculationOutput:
    """납입금액에 검증된 선택 요율을 곱해 선취판매수수료를 계산한다."""

    with localcontext() as context:
        context.prec = 28
        amount = value.subscription_amount_krw * value.selected_rate_percent / 100
    return _fee_output(amount, value.rate_kind)


class FundDeferredSalesFeeInput(BaseModel):
    """환매 시 환매금액에 적용하는 후취판매수수료율."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    redemption_amount_krw: _Money
    selected_rate_percent: _RatePercent
    rate_kind: RateKind


def calculate_fund_deferred_sales_fee(value: FundDeferredSalesFeeInput) -> CalculationOutput:
    """환매금액에 검증된 선택 요율을 곱해 후취판매수수료를 계산한다."""

    with localcontext() as context:
        context.prec = 28
        amount = value.redemption_amount_krw * value.selected_rate_percent / 100
    return _fee_output(amount, value.rate_kind)


class FundRedemptionFeeInput(BaseModel):
    """환매 시 이익금에 적용하는 환매수수료율."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    redemption_profit_krw: _Money
    selected_rate_percent: _RatePercent
    rate_kind: RateKind


def calculate_fund_redemption_fee(value: FundRedemptionFeeInput) -> CalculationOutput:
    """이익금에 검증된 선택 요율을 곱해 환매수수료를 계산한다."""

    with localcontext() as context:
        context.prec = 28
        amount = value.redemption_profit_krw * value.selected_rate_percent / 100
    return _fee_output(amount, value.rate_kind)


FUND_FRONTEND_SALES_FEE = CalculatorDefinition(
    input_model=FundFrontendSalesFeeInput,
    calculate=calculate_fund_frontend_sales_fee,
)
FUND_DEFERRED_SALES_FEE = CalculatorDefinition(
    input_model=FundDeferredSalesFeeInput,
    calculate=calculate_fund_deferred_sales_fee,
)
FUND_REDEMPTION_FEE = CalculatorDefinition(
    input_model=FundRedemptionFeeInput,
    calculate=calculate_fund_redemption_fee,
)
