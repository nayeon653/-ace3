"""명시적으로 등록된 결정론적 계산 함수."""

from pension_agent.rules.calculators.deferred_retirement_withdrawal_tax import (
    DEFERRED_RETIREMENT_WITHDRAWAL_TAX,
)
from pension_agent.rules.calculators.fund_standard_price import FUND_STANDARD_PRICE
from pension_agent.rules.calculators.fund_var_risk import FUND_VAR_RISK
from pension_agent.rules.calculators.isa_transfer_deadline import ISA_TRANSFER_DEADLINE
from pension_agent.rules.calculators.medical_care_withdrawal import (
    DC_MEDICAL_WITHDRAWAL_THRESHOLD,
    MEDICAL_CARE_WITHDRAWAL_TAX_BREAKDOWN,
    MEDICAL_CARE_WITHDRAWAL_TAX_LIMIT,
)
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
from pension_agent.rules.calculators.pension_withdrawal_breakdown import (
    PENSION_WITHDRAWAL_ALLOCATION,
    PENSION_WITHDRAWAL_TAX_BREAKDOWN,
)
from pension_agent.rules.calculators.pension_withdrawal_limit import (
    PENSION_WITHDRAWAL_LIMIT,
)
from pension_agent.rules.calculators.retirement_benefits import (
    DB_RETIREMENT_BENEFIT,
    DB_TO_DC_TRANSFER_AMOUNT,
    DC_MINIMUM_EMPLOYER_CONTRIBUTION,
    DC_RETIREMENT_BENEFIT,
)

CALCULATORS = {
    "db_retirement_benefit": DB_RETIREMENT_BENEFIT,
    "db_to_dc_transfer_amount": DB_TO_DC_TRANSFER_AMOUNT,
    "dc_minimum_employer_contribution": DC_MINIMUM_EMPLOYER_CONTRIBUTION,
    "dc_retirement_benefit": DC_RETIREMENT_BENEFIT,
    "deferred_retirement_withdrawal_tax": DEFERRED_RETIREMENT_WITHDRAWAL_TAX,
    "dc_medical_withdrawal_threshold": DC_MEDICAL_WITHDRAWAL_THRESHOLD,
    "fund_standard_price": FUND_STANDARD_PRICE,
    "fund_var_risk": FUND_VAR_RISK,
    "isa_transfer_deadline": ISA_TRANSFER_DEADLINE,
    "medical_care_withdrawal_tax_breakdown": MEDICAL_CARE_WITHDRAWAL_TAX_BREAKDOWN,
    "medical_care_withdrawal_tax_limit": MEDICAL_CARE_WITHDRAWAL_TAX_LIMIT,
    "non_pension_withdrawal_tax": NON_PENSION_WITHDRAWAL_TAX,
    "pension_income_tax": PENSION_INCOME_TAX,
    "pension_annual_limit_installment": PENSION_ANNUAL_LIMIT_INSTALLMENT,
    "pension_period_installment": PENSION_PERIOD_INSTALLMENT,
    "pension_tax_credit": PENSION_TAX_CREDIT,
    "pension_unit_installment": PENSION_UNIT_INSTALLMENT,
    "pension_withdrawal_limit": PENSION_WITHDRAWAL_LIMIT,
    "pension_withdrawal_allocation": PENSION_WITHDRAWAL_ALLOCATION,
    "pension_withdrawal_tax_breakdown": PENSION_WITHDRAWAL_TAX_BREAKDOWN,
}

__all__ = [
    "CALCULATORS",
    "DB_RETIREMENT_BENEFIT",
    "DB_TO_DC_TRANSFER_AMOUNT",
    "DC_MEDICAL_WITHDRAWAL_THRESHOLD",
    "DC_MINIMUM_EMPLOYER_CONTRIBUTION",
    "DC_RETIREMENT_BENEFIT",
    "DEFERRED_RETIREMENT_WITHDRAWAL_TAX",
    "FUND_STANDARD_PRICE",
    "FUND_VAR_RISK",
    "ISA_TRANSFER_DEADLINE",
    "MEDICAL_CARE_WITHDRAWAL_TAX_BREAKDOWN",
    "MEDICAL_CARE_WITHDRAWAL_TAX_LIMIT",
    "NON_PENSION_WITHDRAWAL_TAX",
    "PENSION_ANNUAL_LIMIT_INSTALLMENT",
    "PENSION_INCOME_TAX",
    "PENSION_PERIOD_INSTALLMENT",
    "PENSION_TAX_CREDIT",
    "PENSION_UNIT_INSTALLMENT",
    "PENSION_WITHDRAWAL_ALLOCATION",
    "PENSION_WITHDRAWAL_LIMIT",
    "PENSION_WITHDRAWAL_TAX_BREAKDOWN",
]
