"""검증된 카탈로그 조회와 단일 상품 문서 검색을 사용하는 Product Agent 조립."""

import json
from importlib import resources
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Command

from pension_agent.agent.contracts import (
    CatalogItem,
    CatalogResult,
    DomainResult,
    ExecutionStatus,
    Permission,
    validate_domain_result,
)
from pension_agent.agent.domain_agent import DomainAgent, DomainAgentState, create_domain_agent
from pension_agent.agent.execution import ExecutionContext, ModelConcurrencyMiddleware
from pension_agent.agent.product.catalog_matcher import (
    ProductCatalogMatch,
    ProductCatalogMatcher,
    ProductCatalogMatchError,
)
from pension_agent.agent.product.catalog_query import (
    BrowseCatalogQuery,
    CatalogQueryPlanError,
    HCXProductCatalogQueryPlanner,
    ProductCatalogQueryPlanner,
    SingleProductQuery,
    UnresolvedProductQuery,
)
from pension_agent.agent.search import SearchRunner
from pension_agent.config import DEFAULT_DOMAIN_AGENT_CONFIG, DomainAgentConfig
from pension_agent.retrieval import (
    ProductCatalog,
    ProductCatalogResult,
    load_product_catalog,
)

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
    catalog_query_planner: ProductCatalogQueryPlanner | None = None,
) -> DomainAgent:
    """HCX 조회 계획을 검증한 뒤 카탈로그 또는 상품 문서를 조회한다."""

    selected_catalog = catalog or load_product_catalog()
    if catalog_matcher is not None and catalog_query_planner is not None:
        raise ValueError("상품 matcher와 카탈로그 Query Planner를 함께 지정할 수 없습니다.")
    if catalog_matcher is not None:
        catalog_tool = _create_legacy_product_code_lookup_tool(catalog_matcher)
    else:
        selected_planner = catalog_query_planner or HCXProductCatalogQueryPlanner(
            model=model,
            catalog=selected_catalog,
            model_concurrency=model_concurrency,
        )
        catalog_tool = _create_product_catalog_query_tool(
            selected_planner,
            selected_catalog,
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
        product_lookup_tool=catalog_tool,
    )


def _create_product_catalog_query_tool(
    planner: ProductCatalogQueryPlanner,
    catalog: ProductCatalog,
) -> BaseTool:
    @tool(
        LOOKUP_PRODUCT_CODES_TOOL_NAME,
        description=(
            "사용자 질문을 전체 상품 카탈로그와 대조해 검증된 단일 상품 코드를 "
            "식별하거나, 운용사별 상품 개수와 목록을 정확히 조회한다."
        ),
    )
    async def query_product_catalog(
        runtime: ToolRuntime[ExecutionContext, DomainAgentState],
    ) -> Command:
        if runtime.tool_call_id is None:
            raise ValueError("상품 카탈로그 조회 Tool 호출 ID가 없습니다.")
        try:
            query = await planner.plan(
                question=runtime.state.get("question", ""),
                objective=runtime.state.get("objective", ""),
                deadline=runtime.context.deadline,
            )
        except TimeoutError:
            result = _failed_product_result(
                "상품 카탈로그 조회 계획 시간이 초과됐습니다.",
                execution_status="timeout",
            )
            return _catalog_lookup_command(runtime.tool_call_id, result=result)
        except CatalogQueryPlanError:
            result = _failed_product_result("상품 카탈로그 조회 계획을 확정하지 못했습니다.")
            return _catalog_lookup_command(runtime.tool_call_id, result=result)

        if isinstance(query, BrowseCatalogQuery):
            if query.provider_status == "not_found":
                result = _terminal_unregistered_provider_result(query)
                return _catalog_lookup_command(
                    runtime.tool_call_id,
                    payload={"query": query.model_dump()},
                    result=result,
                )
            catalog_result = catalog.query(
                provider=query.provider,
                return_mode=query.return_mode,
            )
            result = _catalog_domain_result(catalog_result)
            return _catalog_lookup_command(
                runtime.tool_call_id,
                payload={"query": query.model_dump(), "catalog_result": result["catalog_result"]},
                pending_catalog_result=result,
            )
        if not isinstance(query, SingleProductQuery):
            result = _terminal_product_resolution_result(query)
            return _catalog_lookup_command(
                runtime.tool_call_id,
                payload={"query": query.model_dump()},
                result=result,
            )
        return _catalog_lookup_command(
            runtime.tool_call_id,
            payload={"query": query.model_dump()},
            candidate_codes=[query.product_code],
        )

    return query_product_catalog


def _create_legacy_product_code_lookup_tool(matcher: ProductCatalogMatcher) -> BaseTool:
    """기존 주입형 matcher 테스트와 호환되는 단일 상품 식별 Tool."""

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
    payload: dict[str, Any] | None = None,
    candidate_codes: list[str] | None = None,
    result: DomainResult | None = None,
    pending_catalog_result: DomainResult | None = None,
) -> Command:
    if payload is not None:
        message_payload = payload
    elif match is None:
        message_payload = {"execution_status": result["execution_status"] if result else "failed"}
    else:
        message_payload = {
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
                content=json.dumps(
                    message_payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
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
    if pending_catalog_result is not None:
        validate_domain_result(pending_catalog_result)
        update["product_catalog_result"] = pending_catalog_result
    return Command(update=update)


def _catalog_domain_result(result: ProductCatalogResult) -> DomainResult:
    """결정론적 조회 결과를 Main/API 공통 DomainResult로 변환한다."""

    items: list[CatalogItem] = [
        {
            "product_code": item.product_code,
            "official_name": item.official_name,
            "provider": item.provider,
        }
        for item in result.items
    ]
    catalog_result: CatalogResult = {
        "route": "browse_catalog",
        "provider": result.provider,
        "return_mode": result.return_mode,
        "total_count": result.total_count,
        "items": items,
        "catalog_version": result.catalog_version,
    }
    subject = result.provider or "전체"
    evidence_content = json.dumps(
        catalog_result,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    domain_result: DomainResult = {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": f"{subject} 상품 카탈로그에서 {result.total_count}개를 조회했습니다.",
            "missing_conditions": [],
        },
        "evidence": [
            {
                "chunk_id": str(
                    uuid5(
                        NAMESPACE_URL,
                        f"product-catalog:{result.catalog_version}:{evidence_content}",
                    )
                ),
                "source_file_name": "product_catalog.json",
                "title": "검증된 상품 카탈로그 조회 결과",
                "locator": (
                    f"provider={result.provider or 'all'};catalog_version={result.catalog_version}"
                ),
                "content": evidence_content,
            }
        ],
        "calculations": [],
        "warnings": [],
        "catalog_result": catalog_result,
    }
    validate_domain_result(domain_result)
    return domain_result


def _terminal_product_resolution_result(query: UnresolvedProductQuery) -> DomainResult:
    """단일 상품을 확정하지 못한 Query를 문서 검색 없이 종료한다."""

    if query.resolution_status == "ambiguous":
        return {
            "domain": "product",
            "execution_status": "completed",
            "decision": {
                "status": "conditional",
                "conclusion": "질문에서 분석할 상품을 하나로 식별할 수 없습니다.",
                "missing_conditions": ["분석할 하나의 정확한 상품명 또는 product_code"],
            },
            "evidence": [],
            "calculations": [],
            "warnings": ["상품이 모호해 상품 문서를 검색하지 않았습니다."],
        }
    return {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "undetermined",
            "conclusion": "질문의 상품은 검증된 상품 카탈로그에 등록되어 있지 않습니다.",
            "missing_conditions": ["카탈로그에 등록된 정확한 상품명 또는 product_code"],
        },
        "evidence": [],
        "calculations": [],
        "warnings": ["미등록 상품이므로 상품 문서를 검색하지 않았습니다."],
    }


def _terminal_unregistered_provider_result(query: BrowseCatalogQuery) -> DomainResult:
    """미등록 운용사 조회를 문서 검색 없이 종료한다."""

    if query.provider is None:
        raise ValueError("미등록 운용사명이 없습니다.")
    return {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "undetermined",
            "conclusion": f"'{query.provider}' 운용사는 검증된 상품 카탈로그에 등록되어 있지 않습니다.",
            "missing_conditions": ["카탈로그에 등록된 정확한 운용사명 또는 product_code"],
        },
        "evidence": [],
        "calculations": [],
        "warnings": ["미등록 운용사이므로 상품 문서를 검색하지 않았습니다."],
    }


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
