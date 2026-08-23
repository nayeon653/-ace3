"""HCX로 사용자 표현을 카탈로그의 검증된 상품 후보에 연결한다."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from importlib import resources
from typing import Annotated, Any, Literal, Protocol

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain.tools import tool
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from pension_agent.agent.execution import ModelConcurrencyMiddleware
from pension_agent.retrieval import ProductCatalog, ProductCatalogEntry, ProductCatalogError

PRODUCT_CATALOG_SELECTION_TOOL_NAME = "return_product_catalog_selection"
_PRODUCT_CATALOG_MARKER = "{{PRODUCT_CATALOG_JSON}}"
_MAX_CANDIDATES_MARKER = "{{MAX_PRODUCT_CANDIDATES}}"
_MAX_PRODUCT_CANDIDATES = 12
_CandidateCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ProductMatchStatus = Literal["single", "ambiguous", "not_found"]


class ProductCatalogMatchError(RuntimeError):
    """HCX 상품 후보 식별 결과를 안전하게 사용할 수 없는 경우."""


class ProductCatalogSelection(BaseModel):
    """HCX가 카탈로그에서 고른 코드와 식별 상태."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ProductMatchStatus
    product_codes: list[_CandidateCode] = Field(max_length=_MAX_PRODUCT_CANDIDATES)

    def model_post_init(self, context: object, /) -> None:
        """식별 상태와 후보 개수의 조합을 제한한다."""

        del context
        count = len(self.product_codes)
        if self.status == "single" and count != 1:
            raise ValueError("single 상품 식별에는 코드 하나가 필요합니다.")
        if self.status == "ambiguous" and count < 2:
            raise ValueError("ambiguous 상품 식별에는 코드 두 개 이상이 필요합니다.")
        if self.status == "not_found" and count != 0:
            raise ValueError("not_found 상품 식별에는 코드를 포함할 수 없습니다.")


@tool(PRODUCT_CATALOG_SELECTION_TOOL_NAME, args_schema=ProductCatalogSelection)
def _return_product_catalog_selection(status: str, product_codes: list[str]) -> str:
    """상품 카탈로그 후보 선택을 구조화해 반환한다."""

    del status, product_codes
    return ""


@dataclass(frozen=True, slots=True)
class ProductCatalogMatch:
    """애플리케이션 카탈로그로 다시 검증된 HCX 상품 식별 결과."""

    status: ProductMatchStatus
    candidates: tuple[ProductCatalogEntry, ...]


class ProductCatalogMatcher(Protocol):
    """Product Agent의 상품 코드 식별 Tool이 의존하는 최소 계약."""

    async def match(
        self,
        *,
        question: str,
        objective: str,
        deadline: float,
    ) -> ProductCatalogMatch: ...


def load_product_catalog_matcher_prompt(catalog: ProductCatalog) -> str:
    """HCX 상품 후보 식별 프롬프트에 카탈로그를 한 번 삽입한다."""

    prompt = (
        resources.files("pension_agent.prompts")
        .joinpath("domain", "product-catalog-matcher.md")
        .read_text(encoding="utf-8")
    )
    if prompt.count(_PRODUCT_CATALOG_MARKER) != 1 or prompt.count(_MAX_CANDIDATES_MARKER) != 1:
        raise ValueError("상품 카탈로그 식별 프롬프트의 marker가 올바르지 않습니다.")
    return prompt.replace(_PRODUCT_CATALOG_MARKER, catalog.to_prompt_json()).replace(
        _MAX_CANDIDATES_MARKER,
        str(_MAX_PRODUCT_CANDIDATES),
    )


class HCXProductCatalogMatcher:
    """HCX가 제안한 후보 코드를 애플리케이션 카탈로그로 검증한다."""

    def __init__(
        self,
        *,
        model: BaseChatModel,
        catalog: ProductCatalog,
        model_concurrency: ModelConcurrencyMiddleware | None = None,
    ) -> None:
        self._catalog = catalog
        self._system_prompt = load_product_catalog_matcher_prompt(catalog)
        self._model: Runnable[Any, AIMessage] = model.bind_tools(
            (_return_product_catalog_selection,),
            tool_choice=PRODUCT_CATALOG_SELECTION_TOOL_NAME,
        )
        self._model_concurrency = model_concurrency

    async def match(
        self,
        *,
        question: str,
        objective: str,
        deadline: float,
    ) -> ProductCatalogMatch:
        """사용자 원문을 HCX에 전달하고 검증된 후보만 반환한다."""

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
                if call["name"] == PRODUCT_CATALOG_SELECTION_TOOL_NAME
            ]
            if len(calls) != 1 or len(response.tool_calls) != 1:
                raise ProductCatalogMatchError("HCX 상품 후보 응답이 올바르지 않습니다.")
            selection = ProductCatalogSelection.model_validate(calls[0]["args"])
            selected_candidates = self._catalog.select_products(selection.product_codes)
            candidates = _deduplicate_document_candidates(self._catalog, selected_candidates)
        except TimeoutError:
            raise
        except ProductCatalogMatchError:
            raise
        except (
            AttributeError,
            KeyError,
            OpenAIError,
            ProductCatalogError,
            RuntimeError,
            TypeError,
            ValueError,
        ):
            raise ProductCatalogMatchError("HCX 상품 후보 응답이 올바르지 않습니다.") from None
        status = selection.status
        if status != "not_found":
            status = "single" if len(candidates) == 1 else "ambiguous"
        return ProductCatalogMatch(status=status, candidates=candidates)


def _deduplicate_document_candidates(
    catalog: ProductCatalog,
    candidates: tuple[ProductCatalogEntry, ...],
) -> tuple[ProductCatalogEntry, ...]:
    """동일한 색인 문서를 공유하는 상품 코드는 첫 후보 하나로 합친다."""

    selected: list[ProductCatalogEntry] = []
    seen_documents: set[str] = set()
    for candidate in candidates:
        source_file_name = catalog.resolve_source_file_name(candidate.product_code)
        if source_file_name in seen_documents:
            continue
        seen_documents.add(source_file_name)
        selected.append(candidate)
    return tuple(selected)
