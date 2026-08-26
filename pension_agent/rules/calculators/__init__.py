"""원문 검증을 거쳐 active로 등록된 초기 계산 함수."""

from pension_agent.rules.calculators.fund_standard_price import FUND_STANDARD_PRICE
from pension_agent.rules.calculators.fund_var_risk import FUND_VAR_RISK
from pension_agent.rules.calculators.pension_withdrawal_limit import (
    PENSION_WITHDRAWAL_LIMIT,
)

INITIAL_CALCULATORS = (
    FUND_STANDARD_PRICE,
    FUND_VAR_RISK,
    PENSION_WITHDRAWAL_LIMIT,
)

__all__ = [
    "FUND_STANDARD_PRICE",
    "FUND_VAR_RISK",
    "INITIAL_CALCULATORS",
    "PENSION_WITHDRAWAL_LIMIT",
]
