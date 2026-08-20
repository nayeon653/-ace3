"""상품·운용 Domain Agent 조립."""

from importlib import resources

from langchain_core.language_models import BaseChatModel

from pension_agent.agent.contracts import Permission
from pension_agent.agent.domain_agent import DomainAgent, create_domain_agent
from pension_agent.agent.execution import ModelConcurrencyMiddleware
from pension_agent.agent.search import SearchAgentAdapter
from pension_agent.config import DEFAULT_DOMAIN_AGENT_CONFIG, DomainAgentConfig

PRODUCT_TOOL_NAME = "analyze_product"
PRODUCT_TOOL_DESCRIPTION = "연금 상품의 특성, 비용, 위험과 유동성을 판단한다."


def load_product_agent_prompt() -> str:
    """패키지 리소스에서 상품·운용 프롬프트를 읽는다."""

    return (
        resources.files("pension_agent.prompts")
        .joinpath("domain", "product-agent.md")
        .read_text(encoding="utf-8")
    )


def create_product_agent(
    *,
    model: BaseChatModel,
    search_adapter: SearchAgentAdapter,
    config: DomainAgentConfig = DEFAULT_DOMAIN_AGENT_CONFIG,
    model_concurrency: ModelConcurrencyMiddleware | None = None,
) -> DomainAgent:
    """Search Agent Tool만 사용하는 상품·운용 Agent를 만든다."""

    return create_domain_agent(
        domain="product",
        permission=Permission.PRODUCT,
        model=model,
        search_adapter=search_adapter,
        system_prompt=load_product_agent_prompt(),
        config=config,
        model_concurrency=model_concurrency,
    )
