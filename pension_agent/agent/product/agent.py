"""상품·운용 Domain Agent 조립."""

from importlib import resources

from langchain_core.language_models import BaseChatModel

from pension_agent.agent.contracts import Permission
from pension_agent.agent.domain_agent import DomainAgent, create_domain_agent
from pension_agent.agent.execution import ModelConcurrencyMiddleware
from pension_agent.agent.search import SearchRunner
from pension_agent.config import DEFAULT_DOMAIN_AGENT_CONFIG, DomainAgentConfig
from pension_agent.retrieval import ProductCatalog, load_product_catalog

PRODUCT_TOOL_NAME = "analyze_product"
PRODUCT_TOOL_DESCRIPTION = "연금 상품의 특성, 비용, 위험과 유동성을 판단한다."


def load_product_agent_prompt(catalog: ProductCatalog | None = None) -> str:
    """패키지 리소스에서 상품·운용 프롬프트를 읽는다."""

    selected_catalog = catalog or load_product_catalog()
    prompt = (
        resources.files("pension_agent.prompts")
        .joinpath("domain", "product-agent.md")
        .read_text(encoding="utf-8")
    )
    marker = "{{PRODUCT_CATALOG_JSON}}"
    if prompt.count(marker) != 1:
        raise ValueError("상품 Agent 프롬프트의 카탈로그 marker가 올바르지 않습니다.")
    return prompt.replace(marker, selected_catalog.to_prompt_json())


def create_product_agent(
    *,
    model: BaseChatModel,
    search_service: SearchRunner,
    config: DomainAgentConfig = DEFAULT_DOMAIN_AGENT_CONFIG,
    model_concurrency: ModelConcurrencyMiddleware | None = None,
    catalog: ProductCatalog | None = None,
) -> DomainAgent:
    """단일 Search Service Tool만 사용하는 상품·운용 Agent를 만든다."""

    selected_catalog = catalog or load_product_catalog()
    return create_domain_agent(
        domain="product",
        permission=Permission.PRODUCT,
        model=model,
        search_service=search_service,
        system_prompt=load_product_agent_prompt(selected_catalog),
        config=config,
        model_concurrency=model_concurrency,
        product_code_resolver=selected_catalog.resolve_source_file_name,
    )
