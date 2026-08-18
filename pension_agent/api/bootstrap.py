"""FastAPI 프로세스에서 사용할 애플리케이션 객체 조립."""

from langchain_core.tools import BaseTool

from pension_agent.agent.model_factory import create_chat_clovax
from pension_agent.agent.orchestration import (
    AnswerService,
    create_domain_agent_tool,
    create_main_supervisor,
)
from pension_agent.agent.policy import POLICY_TOOL_DESCRIPTION, POLICY_TOOL_NAME, PolicyAgent
from pension_agent.agent.product import (
    PRODUCT_TOOL_DESCRIPTION,
    PRODUCT_TOOL_NAME,
    ProductAgent,
)
from pension_agent.agent.tax_payout import (
    TAX_PAYOUT_TOOL_DESCRIPTION,
    TAX_PAYOUT_TOOL_NAME,
    TaxPayoutAgent,
)
from pension_agent.config import MAIN_SUPERVISOR_HCX_CONFIG, ClovaStudioConnection


def create_domain_agent_tools() -> tuple[BaseTool, ...]:
    """도메인 Agent를 Main Supervisor Tool로 조립한다."""

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


def build_answer_service() -> AnswerService:
    """환경 설정으로 프로세스 공용 Answer Service를 조립한다."""

    connection = ClovaStudioConnection()
    model = create_chat_clovax(
        config=MAIN_SUPERVISOR_HCX_CONFIG,
        connection=connection,
    )
    supervisor = create_main_supervisor(model=model, tools=create_domain_agent_tools())
    return AnswerService(supervisor)
