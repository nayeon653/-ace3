"""명시적으로 등록된 결정론적 계산 함수."""

from pension_agent.rules.calculators.deferred_retirement_withdrawal_tax import (
    DEFERRED_RETIREMENT_WITHDRAWAL_TAX,
)
from pension_agent.rules.calculators.fund_standard_price import FUND_STANDARD_PRICE
from pension_agent.rules.calculators.fund_var_risk import FUND_VAR_RISK
from pension_agent.rules.calculators.non_pension_withdrawal_tax import (
    NON_PENSION_WITHDRAWAL_TAX,
)
from pension_agent.rules.calculators.pension_annual_limit_installment import (
    PENSION_ANNUAL_LIMIT_INSTALLMENT,
)
from pension_agent.rules.calculators.pension_income_tax import PENSION_INCOME_TAX
from pension_agent.rules.calculators.pension_period_installment import (
    PENSION_PERIOD_INSTALLMENT,
)
from pension_agent.rules.calculators.pension_tax_credit import PENSION_TAX_CREDIT
from pension_agent.rules.calculators.pension_unit_installment import (
    PENSION_UNIT_INSTALLMENT,
)
from pension_agent.rules.calculators.pension_withdrawal_limit import (
    PENSION_WITHDRAWAL_LIMIT,
)

CALCULATORS = {
    "deferred_retirement_withdrawal_tax": DEFERRED_RETIREMENT_WITHDRAWAL_TAX,
    "fund_standard_price": FUND_STANDARD_PRICE,
    "fund_var_risk": FUND_VAR_RISK,
    "non_pension_withdrawal_tax": NON_PENSION_WITHDRAWAL_TAX,
    "pension_income_tax": PENSION_INCOME_TAX,
    "pension_annual_limit_installment": PENSION_ANNUAL_LIMIT_INSTALLMENT,
    "pension_period_installment": PENSION_PERIOD_INSTALLMENT,
    "pension_tax_credit": PENSION_TAX_CREDIT,
    "pension_unit_installment": PENSION_UNIT_INSTALLMENT,
    "pension_withdrawal_limit": PENSION_WITHDRAWAL_LIMIT,
}

__all__ = [
    "CALCULATORS",
    "DEFERRED_RETIREMENT_WITHDRAWAL_TAX",
    "FUND_STANDARD_PRICE",
    "FUND_VAR_RISK",
    "NON_PENSION_WITHDRAWAL_TAX",
    "PENSION_ANNUAL_LIMIT_INSTALLMENT",
    "PENSION_INCOME_TAX",
    "PENSION_PERIOD_INSTALLMENT",
    "PENSION_TAX_CREDIT",
    "PENSION_UNIT_INSTALLMENT",
    "PENSION_WITHDRAWAL_LIMIT",
]
