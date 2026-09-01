"""명시적으로 등록된 결정론적 계산 함수."""

from pension_agent.rules.calculators.fund_standard_price import FUND_STANDARD_PRICE
from pension_agent.rules.calculators.fund_var_risk import FUND_VAR_RISK
from pension_agent.rules.calculators.non_pension_withdrawal_tax import (
    NON_PENSION_WITHDRAWAL_TAX,
)
from pension_agent.rules.calculators.pension_income_tax import PENSION_INCOME_TAX
from pension_agent.rules.calculators.pension_tax_credit import PENSION_TAX_CREDIT
from pension_agent.rules.calculators.pension_withdrawal_limit import (
    PENSION_WITHDRAWAL_LIMIT,
)

CALCULATORS = {
    "fund_standard_price": FUND_STANDARD_PRICE,
    "fund_var_risk": FUND_VAR_RISK,
    "non_pension_withdrawal_tax": NON_PENSION_WITHDRAWAL_TAX,
    "pension_income_tax": PENSION_INCOME_TAX,
    "pension_tax_credit": PENSION_TAX_CREDIT,
    "pension_withdrawal_limit": PENSION_WITHDRAWAL_LIMIT,
}

__all__ = [
    "CALCULATORS",
    "FUND_STANDARD_PRICE",
    "FUND_VAR_RISK",
    "NON_PENSION_WITHDRAWAL_TAX",
    "PENSION_INCOME_TAX",
    "PENSION_TAX_CREDIT",
    "PENSION_WITHDRAWAL_LIMIT",
]
