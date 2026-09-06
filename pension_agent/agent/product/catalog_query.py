"""HCX가 전체 상품 카탈로그를 근거로 구조화 조회 계획을 만든다."""

from __future__ import annotations

import asyncio
import json
from importlib import resources
from typing import Annotated, Any, Literal, Protocol, Self

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain.tools import tool
from langchain_core.language_models import BaseChatModel
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
from pension_agent.agent.product.catalog_selection import (
    CatalogSelectionMode,
    CatalogSelectionSnapshot,
)
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

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        submitted_query: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.submitted_query = submitted_query


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
                "모델이 식별한 비교 대상의 상품 표현. "
                "공통 이름과 수식어는 별도 원소로 나눌 수 있다."
            ),
        ),
    ]
    resolution_status: ProductResolutionStatus
    product_code: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, to_upper=True),
        ]
        | None
    ) = Field(
        default=None,
        description="카탈로그에서 선택한 product_code. single에서만 포함",
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


class _SelectedRowProductQuery(SingleProductQuery):
    """카탈로그의 단일 상품 행 ID로 식별한 조회."""

    product_code: Annotated[str, StringConstraints(min_length=1)] = Field(alias="selected_row_id")


class _SelectedRowComparisonTarget(ComparisonProductTarget):
    """원문 표현과 확정 여부를 함께 보존하는 비교 대상."""

    product_code: Annotated[str, StringConstraints(min_length=1)] | None = Field(
        default=None,
        alias="selected_row_id",
        description="카탈로그에서 선택한 row_id. single에서만 포함",
    )


class _SelectedRowsProductsQuery(_CatalogQueryBase):
    """하나의 계획 안에 명시적인 복수 비교 대상을 보존한다."""

    route: Literal["resolve_products"]
    targets: Annotated[list[_SelectedRowComparisonTarget], Field(min_length=2, max_length=5)]


class _SelectedRowQueryEnvelope(_CatalogQueryBase):
    """단일 Tool의 discriminator 필드 아래에 Query union을 보관한다."""

    query: Annotated[
        _SelectedRowProductQuery
        | NotFoundProductQuery
        | AmbiguousProductQuery
        | _SelectedRowsProductsQuery
        | BrowseAllCatalogQuery
        | BrowseProviderCatalogQuery
        | UnregisteredProviderQuery,
        Field(discriminator="route"),
    ]


@tool(PRODUCT_CATALOG_QUERY_TOOL_NAME, args_schema=CatalogQueryEnvelope)
def _return_product_catalog_query(query: CatalogQueryPlan) -> str:
    """상품 카탈로그 조회 계획을 구조화해 반환한다."""

    del query
    return ""


@tool(PRODUCT_CATALOG_QUERY_TOOL_NAME, args_schema=_SelectedRowQueryEnvelope)
def _return_product_catalog_row_query(query: Any) -> str:
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
        retry_hint: str | None = None,
    ) -> CatalogQueryPlan: ...


def load_product_catalog_query_prompt(
    catalog: ProductCatalog,
    *,
    selection_mode: CatalogSelectionMode = "compact_codes",
) -> str:
    """전용 Planner 프롬프트에 검증된 전체 카탈로그를 삽입한다."""

    return _load_snapshot_prompt(
        CatalogSelectionSnapshot.from_catalog(catalog, mode=selection_mode)
    )


def _load_snapshot_prompt(snapshot: CatalogSelectionSnapshot) -> str:
    prompt_root = resources.files("pension_agent.prompts").joinpath("domain")
    prompt = prompt_root.joinpath("product-catalog-query-planner.md").read_text(encoding="utf-8")
    policies = json.loads(
        prompt_root.joinpath("product-catalog-selection.json").read_text(encoding="utf-8")
    )
    policy = policies["row_ids" if snapshot.mode == "row_ids" else "codes"]
    for name, value in policy.items():
        marker = "{{" + name + "}}"
        if prompt.count(marker) != 1:
            raise ValueError("상품 카탈로그 선택 프롬프트 marker가 올바르지 않습니다.")
        prompt = prompt.replace(marker, value)
    if prompt.count(_PRODUCT_CATALOG_MARKER) != 1:
        raise ValueError("상품 카탈로그 Query 프롬프트 marker가 올바르지 않습니다.")
    return prompt.replace(_PRODUCT_CATALOG_MARKER, snapshot.catalog_text)


class HCXProductCatalogQueryPlanner:
    """HCX 조회 계획의 형식과 카탈로그 연결 가능 여부를 확인한다."""

    def __init__(
        self,
        *,
        model: BaseChatModel,
        catalog: ProductCatalog,
        model_concurrency: ModelConcurrencyMiddleware | None = None,
        selection_mode: CatalogSelectionMode = "compact_codes",
    ) -> None:
        self._catalog = catalog
        self._selection = CatalogSelectionSnapshot.from_catalog(catalog, mode=selection_mode)
        self._system_prompt = _load_snapshot_prompt(self._selection)
        query_tool = (
            _return_product_catalog_row_query
            if selection_mode == "row_ids"
            else _return_product_catalog_query
        )
        self._model: Runnable[Any, AIMessage] = model.bind_tools(
            (query_tool,),
            tool_choice=PRODUCT_CATALOG_QUERY_TOOL_NAME,
        )
        self._model_concurrency = model_concurrency

    async def plan(
        self,
        *,
        question: str,
        objective: str,
        deadline: float,
        retry_hint: str | None = None,
    ) -> CatalogQueryPlan:
        """조회 계획을 한 번 생성하며 모델의 상품 선택을 다시 판정하지 않는다."""

        if deadline <= asyncio.get_running_loop().time():
            raise TimeoutError
        payload = {"question": question, "objective": objective}
        if retry_hint is not None:
            payload["retry_hint"] = retry_hint
        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(
                content=json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
        ]

        async def invoke_model() -> AIMessage:
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
        except TimeoutError:
            raise
        except (
            AttributeError,
            KeyError,
            OpenAIError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            raise CatalogQueryPlanError("HCX 카탈로그 모델 호출에 실패했습니다.") from exc

        try:
            submitted = self._parse_response(response)
        except (AttributeError, KeyError, TypeError, ValidationError, ValueError) as exc:
            raise CatalogQueryPlanError(
                "HCX 카탈로그 조회 계획의 응답 형식이 올바르지 않습니다."
            ) from exc
        try:
            query = self._resolve_selection(submitted)
            return self._validate_query(query)
        except ProductCatalogError as exc:
            raise CatalogQueryPlanError(
                "HCX 카탈로그 조회 계획의 상품 선택 또는 운용사 정보가 카탈로그와 일치하지 않습니다.",
                retryable=True,
                submitted_query=submitted.model_dump(exclude_none=True, by_alias=True),
            ) from exc

    def _parse_response(
        self,
        response: AIMessage,
    ) -> CatalogQueryPlan | _SelectedRowsProductsQuery:
        calls = [
            call for call in response.tool_calls if call["name"] == PRODUCT_CATALOG_QUERY_TOOL_NAME
        ]
        if len(calls) != 1 or len(response.tool_calls) != 1:
            raise ValueError("카탈로그 조회 계획은 지정된 Tool 호출 하나로 반환해야 합니다.")
        if self._selection.mode == "row_ids":
            return _SelectedRowQueryEnvelope.model_validate(calls[0]["args"]).query
        return CatalogQueryEnvelope.model_validate(calls[0]["args"]).query

    def _resolve_selection(
        self,
        query: CatalogQueryPlan | _SelectedRowsProductsQuery,
    ) -> CatalogQueryPlan:
        if isinstance(query, _SelectedRowProductQuery):
            return SingleProductQuery.model_validate(
                {
                    **query.model_dump(exclude_none=True),
                    "product_code": self._selection.resolve_row_id(query.product_code),
                }
            )
        if isinstance(query, _SelectedRowsProductsQuery):
            targets = []
            for target in query.targets:
                payload = target.model_dump(exclude_none=True)
                if target.product_code is not None:
                    payload["product_code"] = self._selection.resolve_row_id(target.product_code)
                targets.append(payload)
            return MultipleProductsQuery.model_validate({"route": query.route, "targets": targets})
        return query

    def _validate_query(self, query: CatalogQueryPlan) -> CatalogQueryPlan:
        if isinstance(query, MultipleProductsQuery):
            for target in query.targets:
                if target.product_code is not None:
                    self._catalog.select_products([target.product_code])
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
