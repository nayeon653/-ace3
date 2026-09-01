"""Domain Agent가 사용하는 결정론적 계산 Tool 어댑터."""

from pension_agent.agent.calculation.input_sources import calculation_evidence_chunk_ids
from pension_agent.agent.calculation.presentation import format_calculation_summary
from pension_agent.agent.calculation.tools import (
    CALCULATE_FUND_STANDARD_PRICE_TOOL_NAME,
    CALCULATE_FUND_VAR_RISK_TOOL_NAME,
    CALCULATE_NON_PENSION_WITHDRAWAL_TAX_TOOL_NAME,
    CALCULATE_PENSION_INCOME_TAX_TOOL_NAME,
    CALCULATE_PENSION_TAX_CREDIT_TOOL_NAME,
    CALCULATE_PENSION_WITHDRAWAL_LIMIT_TOOL_NAME,
    create_fund_standard_price_tool,
    create_fund_var_risk_tool,
    create_non_pension_withdrawal_tax_tool,
    create_pension_income_tax_tool,
    create_pension_tax_credit_tool,
    create_pension_withdrawal_limit_tool,
)

__all__ = [
    "CALCULATE_FUND_STANDARD_PRICE_TOOL_NAME",
    "CALCULATE_FUND_VAR_RISK_TOOL_NAME",
    "CALCULATE_NON_PENSION_WITHDRAWAL_TAX_TOOL_NAME",
    "CALCULATE_PENSION_INCOME_TAX_TOOL_NAME",
    "CALCULATE_PENSION_TAX_CREDIT_TOOL_NAME",
    "CALCULATE_PENSION_WITHDRAWAL_LIMIT_TOOL_NAME",
    "calculation_evidence_chunk_ids",
    "create_fund_standard_price_tool",
    "create_fund_var_risk_tool",
    "create_non_pension_withdrawal_tax_tool",
    "create_pension_income_tax_tool",
    "create_pension_tax_credit_tool",
    "create_pension_withdrawal_limit_tool",
    "format_calculation_summary",
]
