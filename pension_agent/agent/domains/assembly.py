"""도메인 Agent 구현을 Main Supervisor Tool로 조립한다."""

from langchain_core.tools import BaseTool

from pension_agent.agent.domains.policy import (
    POLICY_TOOL_DESCRIPTION,
    POLICY_TOOL_NAME,
    PolicyAgent,
)
from pension_agent.agent.domains.product import (
    PRODUCT_TOOL_DESCRIPTION,
    PRODUCT_TOOL_NAME,
    ProductAgent,
)
from pension_agent.agent.domains.tax_payout import (
    TAX_PAYOUT_TOOL_DESCRIPTION,
    TAX_PAYOUT_TOOL_NAME,
    TaxPayoutAgent,
)
from pension_agent.agent.tools import create_domain_agent_tool


def create_domain_agent_tools() -> tuple[BaseTool, ...]:
    """기본 도메인 Agent 3개를 Main Supervisor의 공식 Tool로 등록한다."""

    return (
        create_domain_agent_tool(
            name=POLICY_TOOL_NAME,
            description=POLICY_TOOL_DESCRIPTION,
            domain="policy",
            runner=PolicyAgent(),
        ),
        create_domain_agent_tool(
            name=TAX_PAYOUT_TOOL_NAME,
            description=TAX_PAYOUT_TOOL_DESCRIPTION,
            domain="tax_payout",
            runner=TaxPayoutAgent(),
        ),
        create_domain_agent_tool(
            name=PRODUCT_TOOL_NAME,
            description=PRODUCT_TOOL_DESCRIPTION,
            domain="product",
            runner=ProductAgent(),
        ),
    )
