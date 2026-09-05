"""HCX가 전체 상품 카탈로그를 근거로 구조화 조회 계획을 만든다."""

from __future__ import annotations

import asyncio
import json
from importlib import resources
from typing import Annotated, Any, Literal, Protocol, Self

from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from openai import OpenAIError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from pension_agent.agent.execution import ModelConcurrencyMiddleware
from pension_agent.agent.product.product_identity import resolve_mention_candidates
from pension_agent.retrieval import (
    CatalogReturnMode,
    ProductCatalog,
    ProductCatalogError,
)

PRODUCT_CATALOG_QUERY_TOOL_NAME = "return_product_catalog_query"
_PRODUCT_CATALOG_MARKER = "{{PRODUCT_CATALOG_JSON}}"
ProductResolutionStatus = Literal["single", "not_found", "ambiguous"]


class CatalogQueryPlanError(RuntimeError):
    """HCX의 카탈로그 조회 계획을 안전하게 사용할 수 없는 경우."""


class _CatalogQueryBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class SingleProductQuery(_CatalogQueryBase):
    """카탈로그의 단일 상품 코드로 식별한 조회."""

    route: Literal["resolve_product"]
    resolution_status: Literal["single"]
    provider: str | None = None
    product_code: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, to_upper=True),
    ]


class NotFoundProductQuery(_CatalogQueryBase):
    """카탈로그에 없는 특정 상품을 코드 없이 종료하는 조회."""

    route: Literal["product_not_found"]
    resolution_status: Literal["not_found"]
    provider: str | None = None


class AmbiguousProductQuery(_CatalogQueryBase):
    """후보가 여러 개인 특정 상품을 코드 없이 종료하는 조회."""

    route: Literal["product_ambiguous"]
    resolution_status: Literal["ambiguous"]
    provider: str | None = None


UnresolvedProductQuery = NotFoundProductQuery | AmbiguousProductQuery
ResolveProductQuery = SingleProductQuery | UnresolvedProductQuery


class ComparisonProductTarget(_CatalogQueryBase):
    """원문 표현과 확정 여부를 함께 보존하는 비교 대상."""

    mention_parts: Annotated[
        list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]],
        Field(
            min_length=1,
            description=(
                "각 원소는 question의 연속된 원문 그대로. 떨어진 공통 이름과 수식어는 "
                "별도 원소로 분리하고 원문에 없는 결합 표현은 금지한다."
            ),
        ),
    ]
    resolution_status: ProductResolutionStatus
    product_code: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, pattern=r"^KR[A-Z0-9]{10}$", to_upper=True),
        ]
        | None
    ) = Field(
        default=None,
        description="카탈로그 product_code의 KR로 시작하는 12자리 코드. 공식명이나 alias는 금지. single에서만 포함",
    )

    @model_validator(mode="after")
    def validate_resolution(self) -> Self:
        if self.resolution_status == "single":
            if self.product_code is None:
                raise ValueError("확정된 비교 대상에는 상품 코드가 필요합니다.")
        elif "product_code" in self.model_fields_set:
            raise ValueError("미식별 비교 대상에는 상품 코드를 넣을 수 없습니다.")
        return self


class MultipleProductsQuery(_CatalogQueryBase):
    """하나의 계획 안에 명시적인 복수 비교 대상을 보존한다."""

    route: Literal["resolve_products"]
    targets: Annotated[list[ComparisonProductTarget], Field(min_length=2, max_length=5)]


class _ComparisonCodeMismatch(ProductCatalogError):
    """원문 후보는 하나지만 HCX가 다른 코드를 선택해 한 번 교정할 수 있는 오류."""

    def __init__(self, query: MultipleProductsQuery, mismatches: list[dict[str, Any]]) -> None:
        super().__init__("상품 식별 표현과 확정 코드가 일치하지 않습니다.")
        self.query = query
        self.mismatches = mismatches


class BrowseAllCatalogQuery(_CatalogQueryBase):
    """운용사 조건 없이 전체 상품 개수·목록을 조회하는 계획."""

    route: Literal["browse_all_catalog"]
    return_mode: CatalogReturnMode


class BrowseProviderCatalogQuery(_CatalogQueryBase):
    """등록된 공식 운용사의 상품 개수·목록을 조회하는 계획."""

    route: Literal["browse_provider_catalog"]
    provider: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    return_mode: CatalogReturnMode


class UnregisteredProviderQuery(_CatalogQueryBase):
    """카탈로그에 없는 운용사 조회를 검색 없이 종료하는 계획."""

    route: Literal["provider_not_found"]
    provider: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    return_mode: CatalogReturnMode


BrowseCatalogQuery = BrowseAllCatalogQuery | BrowseProviderCatalogQuery | UnregisteredProviderQuery


CatalogQueryPlan = Annotated[
    SingleProductQuery
    | NotFoundProductQuery
    | AmbiguousProductQuery
    | MultipleProductsQuery
    | BrowseAllCatalogQuery
    | BrowseProviderCatalogQuery
    | UnregisteredProviderQuery,
    Field(discriminator="route"),
]


class CatalogQueryEnvelope(_CatalogQueryBase):
    """단일 Tool의 discriminator 필드 아래에 Query union을 보관한다."""

    query: CatalogQueryPlan


@tool(PRODUCT_CATALOG_QUERY_TOOL_NAME, args_schema=CatalogQueryEnvelope)
def _return_product_catalog_query(query: CatalogQueryPlan) -> str:
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
        self._repair_feedback = json.loads(
            resources.files("pension_agent.prompts")
            .joinpath("domain", "product-catalog-query-repair.json")
            .read_text(encoding="utf-8")
        )
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
        messages: list[BaseMessage] = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(
                content=json.dumps(
                    {"question": question, "objective": objective},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
        ]

        model_call_count = 0

        async def invoke_model() -> AIMessage:
            nonlocal model_call_count
            if model_call_count >= 2:
                raise CatalogQueryPlanError("상품 카탈로그 계획의 모델 호출 상한에 도달했습니다.")
            model_call_count += 1
            return await self._model.ainvoke(messages)

        async def invoke() -> AIMessage:
            if self._model_concurrency is None:
                return await invoke_model()
            return await self._model_concurrency.arun(
                invoke_model,
                deadline=deadline,
            )

        try:
            async with asyncio.timeout_at(deadline):
                response = await invoke()
                try:
                    query = self._parse_and_validate_response(response, question=question)
                except _ComparisonCodeMismatch as mismatch:
                    messages.extend(
                        [
                            response,
                            ToolMessage(
                                name=PRODUCT_CATALOG_QUERY_TOOL_NAME,
                                tool_call_id=response.tool_calls[0]["id"],
                                content=json.dumps(
                                    {**self._repair_feedback, "mismatches": mismatch.mismatches},
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                ),
                            ),
                        ]
                    )
                    if deadline <= asyncio.get_running_loop().time():
                        raise TimeoutError
                    response = await invoke()
                    query = self._parse_and_validate_response(response, question=question)
                    if not isinstance(query, MultipleProductsQuery) or [
                        (target.mention_parts, target.resolution_status) for target in query.targets
                    ] != [
                        (target.mention_parts, target.resolution_status)
                        for target in mismatch.query.targets
                    ]:
                        raise ProductCatalogError("코드 교정 중 원래 비교 대상을 바꿀 수 없습니다.")
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

    def _parse_and_validate_response(
        self,
        response: AIMessage,
        *,
        question: str | None = None,
    ) -> CatalogQueryPlan:
        calls = [
            call for call in response.tool_calls if call["name"] == PRODUCT_CATALOG_QUERY_TOOL_NAME
        ]
        if len(calls) != 1 or len(response.tool_calls) != 1:
            raise CatalogQueryPlanError("HCX 카탈로그 Query 응답이 올바르지 않습니다.")
        query = CatalogQueryEnvelope.model_validate(calls[0]["args"]).query
        return self._validate_query(query, question=question)

    def _validate_query(
        self,
        query: CatalogQueryPlan,
        *,
        question: str | None = None,
    ) -> CatalogQueryPlan:
        if isinstance(query, MultipleProductsQuery):
            if question is None:
                raise ProductCatalogError("복수 상품 식별에는 질문 원문이 필요합니다.")
            mismatches: list[dict[str, Any]] = []
            for index, target in enumerate(query.targets):
                candidates = resolve_mention_candidates(
                    catalog=self._catalog,
                    mention_parts=target.mention_parts,
                    question=question,
                )
                if target.resolution_status != "single":
                    continue
                if len(candidates) != 1:
                    raise ProductCatalogError("상품 식별 표현과 확정 코드가 일치하지 않습니다.")
                if candidates[0].product_code != target.product_code:
                    mismatches.append(
                        {
                            "target_index": index + 1,
                            "mention_parts": list(target.mention_parts),
                            "selected_product_code": target.product_code,
                            "candidate": candidates[0].to_dict(),
                        }
                    )
            if mismatches:
                raise _ComparisonCodeMismatch(query, mismatches)
            return query
        if isinstance(query, UnregisteredProviderQuery):
            if self._catalog.has_provider(query.provider):
                raise ProductCatalogError("등록된 운용사를 미등록으로 처리할 수 없습니다.")
            return query
        if isinstance(query, BrowseAllCatalogQuery):
            self._catalog.query(provider=None, return_mode=query.return_mode)
            return query
        if isinstance(query, BrowseProviderCatalogQuery):
            try:
                result = self._catalog.query(
                    provider=query.provider,
                    return_mode=query.return_mode,
                )
            except ProductCatalogError:
                return UnregisteredProviderQuery(
                    route="provider_not_found",
                    provider=query.provider,
                    return_mode=query.return_mode,
                )
            if result.provider is None:
                raise ProductCatalogError("등록 운용사 조회에 운용사명이 없습니다.")
            return query.model_copy(update={"provider": result.provider})
        if isinstance(query, (NotFoundProductQuery, AmbiguousProductQuery)):
            normalized_provider = None
            if query.provider is not None:
                normalized_provider = self._catalog.query(
                    provider=query.provider,
                    return_mode="count",
                ).provider
            return query.model_copy(update={"provider": normalized_provider})
        product = self._catalog.select_products([query.product_code])[0]
        if query.provider is not None and query.provider != product.provider:
            raise ProductCatalogError("상품 코드와 운용사가 일치하지 않습니다.")
        return SingleProductQuery(
            route="resolve_product",
            resolution_status="single",
            provider=product.provider,
            product_code=product.product_code,
        )
