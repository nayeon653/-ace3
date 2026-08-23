"""HCX 상품 후보 식별과 단일 문서 검색을 사용하는 Product Agent 조립."""

import json
from importlib import resources
from typing import Any

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Command

from pension_agent.agent.contracts import (
    DomainResult,
    ExecutionStatus,
    Permission,
    validate_domain_result,
)
from pension_agent.agent.domain_agent import DomainAgent, DomainAgentState, create_domain_agent
from pension_agent.agent.execution import ExecutionContext, ModelConcurrencyMiddleware
from pension_agent.agent.product.catalog_matcher import (
    HCXProductCatalogMatcher,
    ProductCatalogMatch,
    ProductCatalogMatcher,
    ProductCatalogMatchError,
)
from pension_agent.agent.search import SearchRunner
from pension_agent.config import DEFAULT_DOMAIN_AGENT_CONFIG, DomainAgentConfig
from pension_agent.retrieval import ProductCatalog, load_product_catalog

PRODUCT_TOOL_NAME = "analyze_product"
PRODUCT_TOOL_DESCRIPTION = "연금 상품의 특성, 비용, 위험과 유동성을 판단한다."
LOOKUP_PRODUCT_CODES_TOOL_NAME = "lookup_product_codes"
_PRODUCT_MAX_SEARCH_CALLS = 2


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
    search_service: SearchRunner,
    config: DomainAgentConfig = DEFAULT_DOMAIN_AGENT_CONFIG,
    model_concurrency: ModelConcurrencyMiddleware | None = None,
    catalog: ProductCatalog | None = None,
    catalog_matcher: ProductCatalogMatcher | None = None,
) -> DomainAgent:
    """HCX 후보 식별 후 단일 상품 문서를 검색하는 Product Agent를 만든다."""

    selected_catalog = catalog or load_product_catalog()
    selected_matcher = catalog_matcher or HCXProductCatalogMatcher(
        model=model,
        catalog=selected_catalog,
        model_concurrency=model_concurrency,
    )
    product_config = config.model_copy(update={"max_search_calls": _PRODUCT_MAX_SEARCH_CALLS})
    return create_domain_agent(
        domain="product",
        permission=Permission.PRODUCT,
        model=model,
        search_service=search_service,
        system_prompt=load_product_agent_prompt(),
        config=product_config,
        model_concurrency=model_concurrency,
        product_code_resolver=selected_catalog.resolve_source_file_name,
        product_lookup_tool=_create_product_code_lookup_tool(selected_matcher),
    )


def _create_product_code_lookup_tool(matcher: ProductCatalogMatcher) -> BaseTool:
    @tool(
        LOOKUP_PRODUCT_CODES_TOOL_NAME,
        description=(
            "사용자 질문 원문을 HCX 상품 카탈로그와 대조해 검증된 product_code를 "
            "식별한다. 상품 문서는 검색하지 않는다."
        ),
    )
    async def lookup_product_codes(
        runtime: ToolRuntime[ExecutionContext, DomainAgentState],
    ) -> Command:
        if runtime.tool_call_id is None:
            raise ValueError("상품 코드 식별 Tool 호출 ID가 없습니다.")
        try:
            match = await matcher.match(
                question=runtime.state.get("question", ""),
                objective=runtime.state.get("objective", ""),
                deadline=runtime.context.deadline,
            )
        except TimeoutError:
            result = _failed_product_result(
                "상품 후보 식별 시간이 초과됐습니다.", execution_status="timeout"
            )
            return _catalog_lookup_command(runtime.tool_call_id, result=result)
        except ProductCatalogMatchError:
            result = _failed_product_result("상품 후보를 식별하지 못했습니다.")
            return _catalog_lookup_command(runtime.tool_call_id, result=result)

        if match.status == "single":
            candidate = match.candidates[0]
            return _catalog_lookup_command(
                runtime.tool_call_id,
                match=match,
                candidate_codes=[candidate.product_code],
            )
        result = _terminal_product_match_result(match)
        return _catalog_lookup_command(runtime.tool_call_id, match=match, result=result)

    return lookup_product_codes


def _catalog_lookup_command(
    tool_call_id: str,
    *,
    match: ProductCatalogMatch | None = None,
    candidate_codes: list[str] | None = None,
    result: DomainResult | None = None,
) -> Command:
    payload: dict[str, Any]
    if match is None:
        payload = {"execution_status": result["execution_status"] if result else "failed"}
    else:
        payload = {
            "execution_status": "completed",
            "status": match.status,
            "candidates": [
                {
                    "product_code": candidate.product_code,
                    "official_name": candidate.official_name,
                    "provider": candidate.provider,
                }
                for candidate in match.candidates
            ],
        }
    update: dict[str, Any] = {
        "messages": [
            ToolMessage(
                content=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                tool_call_id=tool_call_id,
                name=LOOKUP_PRODUCT_CODES_TOOL_NAME,
            )
        ]
    }
    if candidate_codes is not None:
        update["product_candidate_codes"] = candidate_codes
    if result is not None:
        validate_domain_result(result)
        update["domain_result"] = result
    return Command(update=update)


def _terminal_product_match_result(match: ProductCatalogMatch) -> DomainResult:
    if match.status == "ambiguous":
        candidate_text = "; ".join(
            f"{candidate.official_name} ({candidate.provider}, {candidate.product_code})"
            for candidate in match.candidates
        )
        return {
            "domain": "product",
            "execution_status": "completed",
            "decision": {
                "status": "conditional",
                "conclusion": f"질문과 일치할 수 있는 상품 후보가 여러 개입니다: {candidate_text}",
                "missing_conditions": ["분석할 하나의 정확한 상품명 또는 product_code"],
            },
            "evidence": [],
            "calculations": [],
            "warnings": [
                "후보 식별 단계이며 상품 특성, 비용과 위험에 관한 문서는 검색하지 않았습니다."
            ],
        }
    return {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "undetermined",
            "conclusion": "질문에서 카탈로그에 등록된 상품을 식별하지 못했습니다.",
            "missing_conditions": ["카탈로그에 등록된 정확한 상품명 또는 product_code"],
        },
        "evidence": [],
        "calculations": [],
        "warnings": ["상품 후보를 식별하지 못해 상품 문서를 검색하지 않았습니다."],
    }


def _failed_product_result(
    error: str,
    *,
    execution_status: ExecutionStatus = "failed",
) -> DomainResult:
    return {
        "domain": "product",
        "execution_status": execution_status,
        "evidence": [],
        "calculations": [],
        "warnings": [],
        "error": error,
    }
