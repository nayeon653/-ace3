"""HCX 상품 카탈로그 Query Planner의 구조와 재검증을 확인한다."""

import asyncio
from collections.abc import Sequence
from typing import Any, ClassVar

import pytest
from langchain.messages import AIMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import Runnable

from pension_agent.agent.product import (
    PRODUCT_CATALOG_QUERY_TOOL_NAME,
    BrowseCatalogQuery,
    CatalogQueryPlanError,
    HCXProductCatalogQueryPlanner,
    ResolveProductQuery,
    load_product_catalog_query_prompt,
)
from pension_agent.retrieval import load_product_catalog


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class BindingFakeModel(FakeMessagesListChatModel):
    """구조화 Tool binding을 기록하는 Query Planner용 Fake 모델."""

    bindings: ClassVar[list[dict[str, Any]]] = []

    def bind_tools(
        self,
        tools: Sequence[Any],
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        del tools
        self.bindings.append(kwargs)
        return self


def _query_response(query: dict[str, Any]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": PRODUCT_CATALOG_QUERY_TOOL_NAME,
                "args": {"query": query},
                "id": "query-call",
                "type": "tool_call",
            }
        ],
    )


def test_query_planner_forces_one_structured_tool() -> None:
    model = BindingFakeModel(responses=[])
    model.bindings.clear()

    HCXProductCatalogQueryPlanner(model=model, catalog=load_product_catalog())

    assert model.bindings == [{"tool_choice": PRODUCT_CATALOG_QUERY_TOOL_NAME}]


@pytest.mark.anyio
async def test_query_planner_normalizes_provider_for_catalog_browse() -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(
            responses=[
                _query_response(
                    {
                        "route": "browse_catalog",
                        "provider_status": "registered",
                        "provider": "미래에셋",
                        "return_mode": "count_and_items",
                    }
                )
            ]
        ),
        catalog=load_product_catalog(),
    )

    query = await planner.plan(
        question="미레에셋 상품은 몇 개고 어떤 것들이 있어?",
        objective="운용사 상품 개수와 목록 조회",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert query == BrowseCatalogQuery(
        route="browse_catalog",
        provider_status="registered",
        provider="미래에셋",
        return_mode="count_and_items",
    )


@pytest.mark.anyio
async def test_query_planner_resolves_one_catalog_product() -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(
            responses=[
                _query_response(
                    {
                        "route": "resolve_product",
                        "resolution_status": "single",
                        "provider": "미래에셋",
                        "product_code": "kr510902511m",
                    }
                )
            ]
        ),
        catalog=load_product_catalog(),
    )

    query = await planner.plan(
        question="미레에셋 장기성장 포커스 위험은?",
        objective="특정 상품 위험 판단",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert query == ResolveProductQuery(
        route="resolve_product",
        resolution_status="single",
        provider="미래에셋",
        product_code="KR510902511M",
    )


@pytest.mark.anyio
@pytest.mark.parametrize("resolution_status", ["not_found", "ambiguous"])
async def test_query_planner_preserves_safe_unresolved_status(
    resolution_status: str,
) -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(
            responses=[
                _query_response(
                    {
                        "route": "resolve_product",
                        "resolution_status": resolution_status,
                        "provider": "미래에셋",
                    }
                )
            ]
        ),
        catalog=load_product_catalog(),
    )

    query = await planner.plan(
        question="상품을 식별하기 어려운 질문",
        objective="특정 상품 식별",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert query == ResolveProductQuery(
        route="resolve_product",
        resolution_status=resolution_status,
        provider="미래에셋",
    )


@pytest.mark.anyio
async def test_query_planner_verifies_unregistered_provider_status() -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(
            responses=[
                _query_response(
                    {
                        "route": "browse_catalog",
                        "provider_status": "not_found",
                        "provider": "메리츠",
                        "return_mode": "count",
                    }
                )
            ]
        ),
        catalog=load_product_catalog(),
    )

    query = await planner.plan(
        question="메리츠 상품은 몇 개가 등록돼 있어?",
        objective="운용사 상품 개수 조회",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert query == BrowseCatalogQuery(
        route="browse_catalog",
        provider_status="not_found",
        provider="메리츠",
        return_mode="count",
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "query",
    [
        {
            "route": "browse_catalog",
            "provider_status": "registered",
            "provider": "없는운용사",
            "return_mode": "count",
        },
        {
            "route": "browse_catalog",
            "provider_status": "not_found",
            "provider": "미래에셋",
            "return_mode": "count",
        },
        {
            "route": "resolve_product",
            "resolution_status": "single",
            "provider": "미래에셋",
            "product_code": "KR9999999999",
        },
        {
            "route": "resolve_product",
            "resolution_status": "single",
            "provider": "하나",
            "product_code": "KR510902511M",
        },
        {
            "route": "resolve_product",
            "resolution_status": "single",
            "provider": "미래에셋",
        },
        {
            "route": "resolve_product",
            "resolution_status": "not_found",
            "product_code": "KR510902511M",
        },
        {
            "route": "resolve_product",
            "resolution_status": "ambiguous",
            "product_code": "KR510902511M",
        },
        {
            "route": "browse_catalog",
            "provider_status": "registered",
            "provider": "미래에셋",
            "return_mode": "count",
            "product_codes": ["KR510902511M"],
        },
    ],
)
async def test_query_planner_rejects_unverified_or_invalid_queries(
    query: dict[str, Any],
) -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(responses=[_query_response(query)]),
        catalog=load_product_catalog(),
    )

    with pytest.raises(CatalogQueryPlanError):
        await planner.plan(
            question="상품 조회",
            objective="상품 조회",
            deadline=asyncio.get_running_loop().time() + 5,
        )


@pytest.mark.anyio
async def test_query_planner_does_not_start_after_deadline() -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(responses=[]),
        catalog=load_product_catalog(),
    )

    with pytest.raises(TimeoutError):
        await planner.plan(
            question="상품 조회",
            objective="상품 조회",
            deadline=asyncio.get_running_loop().time(),
        )


def test_query_planner_prompt_contains_the_full_catalog_only_once() -> None:
    prompt = load_product_catalog_query_prompt(load_product_catalog())

    assert prompt.count('"product_code":"KR510902511M"') == 1
    assert '"product_code":"KR518102001M"' in prompt
    assert "{{PRODUCT_CATALOG_JSON}}" not in prompt
    assert "상품 목록, 상품 개수" in prompt
    assert "resolution_status=not_found" in prompt
    assert "resolution_status=ambiguous" in prompt
    assert "provider_status=not_found" in prompt
