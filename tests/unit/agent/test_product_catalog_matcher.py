"""HCX 상품 후보 식별 응답의 구조와 카탈로그 검증을 확인한다."""

import asyncio
from collections.abc import Sequence
from typing import Any, ClassVar

import pytest
from langchain.messages import AIMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import Runnable

from pension_agent.agent.product import (
    HCXProductCatalogMatcher,
    ProductCatalogMatchError,
    load_product_agent_prompt,
    load_product_catalog_matcher_prompt,
)
from pension_agent.agent.product.catalog_matcher import PRODUCT_CATALOG_SELECTION_TOOL_NAME
from pension_agent.retrieval import load_product_catalog


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class BindingFakeModel(FakeMessagesListChatModel):
    """구조화 Tool binding만 지원하는 후보 식별용 Fake 모델."""

    bindings: ClassVar[list[dict[str, Any]]] = []

    def bind_tools(
        self,
        tools: Sequence[Any],
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        del tools
        self.bindings.append(kwargs)
        return self


def _selection_response(status: str, product_codes: list[str]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": PRODUCT_CATALOG_SELECTION_TOOL_NAME,
                "args": {"status": status, "product_codes": product_codes},
                "id": "selection-call",
                "type": "tool_call",
            }
        ],
    )


def test_hcx_catalog_matcher_does_not_disable_parallel_tool_calls() -> None:
    model = BindingFakeModel(responses=[])
    model.bindings.clear()

    HCXProductCatalogMatcher(model=model, catalog=load_product_catalog())

    assert model.bindings == [{"tool_choice": PRODUCT_CATALOG_SELECTION_TOOL_NAME}]


@pytest.mark.anyio
async def test_hcx_catalog_matcher_returns_only_catalog_backed_entries() -> None:
    catalog = load_product_catalog()
    matcher = HCXProductCatalogMatcher(
        model=BindingFakeModel(responses=[_selection_response("single", [" kr510902511m "])]),
        catalog=catalog,
    )

    result = await matcher.match(
        question="미리에셋 장기성장 상품",
        objective="상품 식별",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert result.status == "single"
    assert [candidate.product_code for candidate in result.candidates] == ["KR510902511M"]
    assert result.candidates[0].official_name


@pytest.mark.anyio
async def test_hcx_catalog_matcher_rejects_generated_unknown_code() -> None:
    matcher = HCXProductCatalogMatcher(
        model=BindingFakeModel(responses=[_selection_response("single", ["KR9999999999"])]),
        catalog=load_product_catalog(),
    )

    with pytest.raises(ProductCatalogMatchError):
        await matcher.match(
            question="없는 상품",
            objective="상품 식별",
            deadline=asyncio.get_running_loop().time() + 5,
        )


@pytest.mark.anyio
async def test_hcx_catalog_matcher_collapses_codes_that_share_one_indexed_document() -> None:
    matcher = HCXProductCatalogMatcher(
        model=BindingFakeModel(
            responses=[_selection_response("ambiguous", ["KR5113420013", "KR5113420015"])]
        ),
        catalog=load_product_catalog(),
    )

    result = await matcher.match(
        question="한국투자 골드플랜 연금 채권",
        objective="상품 식별",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert result.status == "single"
    assert len(result.candidates) == 1


@pytest.mark.parametrize(
    ("status", "product_codes"),
    [
        ("single", []),
        ("ambiguous", ["KR510902511M"]),
        ("not_found", ["KR510902511M"]),
    ],
)
@pytest.mark.anyio
async def test_hcx_catalog_matcher_rejects_inconsistent_status_and_candidates(
    status: str,
    product_codes: list[str],
) -> None:
    matcher = HCXProductCatalogMatcher(
        model=BindingFakeModel(responses=[_selection_response(status, product_codes)]),
        catalog=load_product_catalog(),
    )

    with pytest.raises(ProductCatalogMatchError):
        await matcher.match(
            question="상품",
            objective="상품 식별",
            deadline=asyncio.get_running_loop().time() + 5,
        )


def test_catalog_is_injected_only_into_hcx_matcher_prompt() -> None:
    product_prompt = load_product_agent_prompt()
    matcher_prompt = load_product_catalog_matcher_prompt(load_product_catalog())

    assert '"product_code":"KR510902511M"' not in product_prompt
    assert '"product_code":"KR510902511M"' in matcher_prompt
    assert "{{PRODUCT_CATALOG_JSON}}" not in matcher_prompt
    assert "{{MAX_PRODUCT_CANDIDATES}}" not in matcher_prompt
