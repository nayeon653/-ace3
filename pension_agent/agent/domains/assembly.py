"""도메인 Agent 구현을 Main Supervisor Tool로 조립한다."""

from langchain_core.tools import BaseTool

from pension_agent.agent.domains.policy import (
    POLICY_TOOL_DESCRIPTION,
    POLICY_TOOL_NAME,
    TbdPolicyAgent,
)
from pension_agent.agent.domains.product import (
    PRODUCT_TOOL_DESCRIPTION,
    PRODUCT_TOOL_NAME,
    TbdProductAgent,
)
from pension_agent.agent.domains.tax_payout import (
    TAX_PAYOUT_TOOL_DESCRIPTION,
    TAX_PAYOUT_TOOL_NAME,
    TbdTaxPayoutAgent,
)
from pension_agent.agent.tools import create_domain_agent_tool


def create_tbd_domain_agent_tools() -> tuple[BaseTool, ...]:
    """TBD Agent 3개를 Main Supervisor의 공식 Tool로 등록한다."""

    return (
        create_domain_agent_tool(
            name=POLICY_TOOL_NAME,
            description=POLICY_TOOL_DESCRIPTION,
            domain="policy",
            runner=TbdPolicyAgent(),
        ),
        create_domain_agent_tool(
            name=TAX_PAYOUT_TOOL_NAME,
            description=TAX_PAYOUT_TOOL_DESCRIPTION,
            domain="tax_payout",
            runner=TbdTaxPayoutAgent(),
        ),
        create_domain_agent_tool(
            name=PRODUCT_TOOL_NAME,
            description=PRODUCT_TOOL_DESCRIPTION,
            domain="product",
            runner=TbdProductAgent(),
        ),
    )
