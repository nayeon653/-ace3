"""연금계좌 평가액과 연금수령연차에 따른 연금수령한도 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from pension_agent.rules.models import CalculationPayload, CalculatorMetadata
from pension_agent.rules.registry import CalculatorDefinition

_Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class PensionWithdrawalLimitInput(BaseModel):
    """연금수령한도의 평가액과 수령연차."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    account_valuation_krw: _Money
    pension_year: int = Field(ge=1, le=10)


def calculate_pension_withdrawal_limit(
    value: PensionWithdrawalLimitInput,
) -> CalculationPayload:
    """평가액 ÷ (11 - 수령연차) × 120% 공식을 적용한다."""

    with localcontext() as context:
        context.prec = 28
        limit = value.account_valuation_krw / Decimal(11 - value.pension_year) * Decimal("1.2")
    return CalculationPayload(
        outputs={"withdrawal_limit": limit},
        units={"withdrawal_limit": "KRW"},
        warnings=("출처에는 최종 지급 단위의 반올림·절사 규칙이 명시되지 않았습니다.",),
    )


PENSION_WITHDRAWAL_LIMIT = CalculatorDefinition(
    metadata=CalculatorMetadata(
        calculator_id="pension_withdrawal_limit",
        version="1.0.0",
        display_name="연금수령한도",
        description="연금계좌 평가액과 연금수령연차로 연금수령한도를 계산한다.",
        status="active",
        domain_tags=frozenset({"pension", "withdrawal_limit"}),
    ),
    input_model=PensionWithdrawalLimitInput,
    calculate=calculate_pension_withdrawal_limit,
)
