"""HCX가 전체 상품 카탈로그를 근거로 구조화 조회 계획을 만든다."""

from __future__ import annotations

import asyncio
import json
from importlib import resources
from typing import Annotated, Any, Literal, Protocol

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain.tools import tool
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from pension_agent.agent.execution import ModelConcurrencyMiddleware
from pension_agent.retrieval import (
    CatalogReturnMode,
    ProductCatalog,
    ProductCatalogError,
)

PRODUCT_CATALOG_QUERY_TOOL_NAME = "return_product_catalog_query"
_PRODUCT_CATALOG_MARKER = "{{PRODUCT_CATALOG_JSON}}"
ProductResolutionStatus = Literal["single", "not_found", "ambiguous"]
ProviderResolutionStatus = Literal["registered", "not_found"]


class CatalogQueryPlanError(RuntimeError):
    """HCX의 카탈로그 조회 계획을 안전하게 사용할 수 없는 경우."""


class _CatalogQueryBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class ResolveProductQuery(_CatalogQueryBase):
    """특정 상품을 단일 코드로 식별하거나 안전한 미식별 상태로 정규화한 조회."""

    route: Literal["resolve_product"]
    resolution_status: ProductResolutionStatus
    provider: str | None = None
    product_code: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, to_upper=True),
        ]
        | None
    ) = None

    def model_post_init(self, context: object, /) -> None:
        """식별 상태와 상품 코드의 허용 조합을 제한한다."""

        del context
        if self.resolution_status == "single" and self.product_code is None:
            raise ValueError("single 상품 식별에는 상품 코드 하나가 필요합니다.")
        if self.resolution_status != "single" and self.product_code is not None:
            raise ValueError("미식별 상품 조회에는 상품 코드를 포함할 수 없습니다.")


class BrowseCatalogQuery(_CatalogQueryBase):
    """운용사 등록 상태와 상품 개수·목록 조회 계획."""

    route: Literal["browse_catalog"]
    provider_status: ProviderResolutionStatus
    provider: str | None = None
    return_mode: CatalogReturnMode

    def model_post_init(self, context: object, /) -> None:
        """미등록 운용사 상태에는 확인할 이름을 강제한다."""

        del context
        if self.provider_status == "not_found" and self.provider is None:
            raise ValueError("미등록 운용사 조회에는 운용사명이 필요합니다.")


CatalogQueryPlan = Annotated[
    ResolveProductQuery | BrowseCatalogQuery,
    Field(discriminator="route"),
]


class CatalogQueryEnvelope(_CatalogQueryBase):
    """단일 Tool의 discriminator 필드 아래에 Query union을 보관한다."""

    query: CatalogQueryPlan


@tool(PRODUCT_CATALOG_QUERY_TOOL_NAME, args_schema=CatalogQueryEnvelope)
def _return_product_catalog_query(query: dict[str, Any]) -> str:
    """상품 카탈로그 조회 계획을 구조화해 반환한다."""

    del query
    return ""


class ProductCatalogQueryPlanner(Protocol):
    """Product Agent의 카탈로그 Tool이 의존하는 계획 생성 계약."""

    async def plan(
        self,
        *,
        question: str,
        objective: str,
        deadline: float,
    ) -> CatalogQueryPlan: ...


def load_product_catalog_query_prompt(catalog: ProductCatalog) -> str:
    """전용 Planner 프롬프트에 검증된 전체 카탈로그를 삽입한다."""

    prompt = (
        resources.files("pension_agent.prompts")
        .joinpath("domain", "product-catalog-query-planner.md")
        .read_text(encoding="utf-8")
    )
    if prompt.count(_PRODUCT_CATALOG_MARKER) != 1:
        raise ValueError("상품 카탈로그 Query 프롬프트 marker가 올바르지 않습니다.")
    return prompt.replace(_PRODUCT_CATALOG_MARKER, catalog.to_prompt_json())


class HCXProductCatalogQueryPlanner:
    """HCX Query를 같은 카탈로그 스냅샷으로 재검증한다."""

    def __init__(
        self,
        *,
        model: BaseChatModel,
        catalog: ProductCatalog,
        model_concurrency: ModelConcurrencyMiddleware | None = None,
    ) -> None:
        self._catalog = catalog
        self._system_prompt = load_product_catalog_query_prompt(catalog)
        self._model: Runnable[Any, AIMessage] = model.bind_tools(
            (_return_product_catalog_query,),
            tool_choice=PRODUCT_CATALOG_QUERY_TOOL_NAME,
        )
        self._model_concurrency = model_concurrency

    async def plan(
        self,
        *,
        question: str,
        objective: str,
        deadline: float,
    ) -> CatalogQueryPlan:
        """질문 표현을 검증된 단일 카탈로그 Query로 변환한다."""

        if deadline <= asyncio.get_running_loop().time():
            raise TimeoutError
        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(
                content=json.dumps(
                    {"question": question, "objective": objective},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
        ]

        async def invoke() -> AIMessage:
            return await self._model.ainvoke(messages)

        try:
            async with asyncio.timeout_at(deadline):
                if self._model_concurrency is None:
                    response = await invoke()
                else:
                    response = await self._model_concurrency.arun(invoke)
            calls = [
                call
                for call in response.tool_calls
                if call["name"] == PRODUCT_CATALOG_QUERY_TOOL_NAME
            ]
            if len(calls) != 1 or len(response.tool_calls) != 1:
                raise CatalogQueryPlanError("HCX 카탈로그 Query 응답이 올바르지 않습니다.")
            query = CatalogQueryEnvelope.model_validate(calls[0]["args"]).query
            query = self._validate_query(query)
        except TimeoutError:
            raise
        except CatalogQueryPlanError:
            raise
        except (
            AttributeError,
            KeyError,
            OpenAIError,
            ProductCatalogError,
            RuntimeError,
            TypeError,
            ValidationError,
            ValueError,
        ):
            raise CatalogQueryPlanError("HCX 카탈로그 Query 응답이 올바르지 않습니다.") from None
        return query

    def _validate_query(self, query: CatalogQueryPlan) -> CatalogQueryPlan:
        if isinstance(query, BrowseCatalogQuery):
            if query.provider_status == "not_found":
                if query.provider is None:
                    raise ProductCatalogError("미등록 운용사명이 필요합니다.")
                if self._catalog.has_provider(query.provider):
                    raise ProductCatalogError("등록된 운용사를 미등록으로 처리할 수 없습니다.")
                return query
            result = self._catalog.query(
                provider=query.provider,
                return_mode=query.return_mode,
            )
            return query.model_copy(
                update={"provider_status": "registered", "provider": result.provider}
            )
        if query.resolution_status != "single":
            normalized_provider = None
            if query.provider is not None:
                normalized_provider = self._catalog.query(
                    provider=query.provider,
                    return_mode="count",
                ).provider
            return query.model_copy(update={"provider": normalized_provider})
        if query.product_code is None:
            raise ProductCatalogError("단일 상품 식별에는 상품 코드가 필요합니다.")
        product = self._catalog.select_products([query.product_code])[0]
        if query.provider is not None and query.provider != product.provider:
            raise ProductCatalogError("상품 코드와 운용사가 일치하지 않습니다.")
        return ResolveProductQuery(
            route="resolve_product",
            resolution_status="single",
            provider=product.provider,
            product_code=product.product_code,
        )
