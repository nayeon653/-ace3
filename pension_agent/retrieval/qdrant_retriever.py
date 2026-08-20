"""Search Agent의 ChunkRetriever Port를 구현하는 Qdrant Adapter."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from kiwipiepy import Kiwi  # type: ignore[import-untyped]
from langsmith.utils import ContextThreadPoolExecutor
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from qdrant_client import AsyncQdrantClient, QdrantClient, models
from qdrant_client.http.exceptions import ApiException

from pension_agent.core import (
    DocumentType,
    ElementType,
    NeighborRequest,
    RetrievalBackendError,
    RetrievalDataError,
    RetrievedChunk,
    SearchFilters,
    SearchHit,
    SearchMode,
    SearchQuery,
)
from pension_agent.retrieval.filters import QdrantFilterBuilder

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
SPARSE_MODEL_NAME = "qdrant/bm25"

_CONTENT_TAG_PREFIXES = ("N", "V", "M")
_CONTENT_TAGS = frozenset({"SL", "SH", "SN", "XR"})
_MAX_RESULT_LIMIT = 100
_KIWI_EXECUTOR = ContextThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="kiwi-tokenizer",
)

BM25_OPTIONS = models.Bm25Config(
    k=1.2,
    b=0.75,
    avg_len=256,
    tokenizer=models.TokenizerType.WHITESPACE,
    lowercase=True,
    stemmer=models.DisabledStemmerParams(type=models.NoStemmer.NONE),
    stopwords=models.StopwordsSet(),
)

_NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]
_NonNegativeInt = Annotated[int, Field(ge=0, strict=True)]
_PageNumber = Annotated[int, Field(ge=1, strict=True)]


class _ChunkPayload(BaseModel):
    """Qdrant payload 저장 계약을 조회 경계에서 검증한다."""

    model_config = ConfigDict(extra="ignore")

    source_file_name: _NonEmptyString
    source_format: Literal["pdf", "docx", "pptx", "xlsx"]
    document_type: DocumentType
    chunk_index: _NonNegativeInt
    content: _NonEmptyString
    embedding_content: _NonEmptyString
    heading_path: list[_NonEmptyString]
    captions: list[_NonEmptyString]
    element_types: list[ElementType]
    page_numbers: list[_PageNumber]


@dataclass(frozen=True)
class _QueryPlan:
    query: list[float] | models.Document | models.FusionQuery
    using: str | None
    prefetch: list[models.Prefetch] | None
    query_filter: models.Filter | None
    limit: int


@lru_cache(maxsize=1)
def _kiwi() -> Kiwi:
    return Kiwi()


def to_bm25_text(text: str) -> str:
    """적재 계약과 동일하게 검색문에서 내용 형태소만 남긴다."""

    return " ".join(
        token.form
        for token in _kiwi().tokenize(text)
        if token.tag.startswith(_CONTENT_TAG_PREFIXES) or token.tag in _CONTENT_TAGS
    )


async def async_to_bm25_text(text: str) -> str:
    """Kiwi CPU 작업을 이벤트 루프 밖의 단일 전용 worker에서 실행한다."""

    future = _KIWI_EXECUTOR.submit(to_bm25_text, text)
    return await asyncio.wrap_future(future)


async def prewarm_kiwi() -> None:
    """요청 수신 전에 Kiwi lazy 초기화를 완료한다."""

    await async_to_bm25_text("형태소 분석 준비")


def make_locator(
    page_numbers: tuple[int, ...],
    heading_path: tuple[str, ...],
    chunk_index: int,
) -> str:
    """저장된 provenance에서 공개 API용 위치를 파생한다."""

    pages = sorted(set(page_numbers))
    if len(pages) == 1:
        return f"{pages[0]}페이지"
    if pages and pages == list(range(pages[0], pages[-1] + 1)):
        return f"{pages[0]}–{pages[-1]}페이지"
    if pages:
        return ", ".join(f"{page}페이지" for page in pages)
    if heading_path:
        return f"{heading_path[-1]} 절"
    return f"문서 내 청크 {chunk_index + 1}"


class QdrantChunkRetriever:
    """검색 방식과 조회 기능을 하나의 안정된 Agent 접근점으로 제공한다."""

    def __init__(
        self,
        client: QdrantClient,
        *,
        collection_name: str,
        prefetch_limit: int = 30,
    ) -> None:
        collection_name = collection_name.strip()
        if not collection_name:
            raise ValueError("Qdrant collection 이름은 비어 있을 수 없습니다.")
        _validate_limit(prefetch_limit)
        self._client = client
        self._collection_name = collection_name
        self._prefetch_limit = prefetch_limit

    def search_chunks(
        self,
        query: SearchQuery,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        """전체 corpus를 dense, sparse 또는 hybrid 방식으로 검색한다."""

        _validate_limit(limit)
        query_filter = QdrantFilterBuilder.build(filters or SearchFilters())
        sparse_text = to_bm25_text(query.text)

        if query.mode is SearchMode.SPARSE and not sparse_text:
            return []

        plan = self._build_query_plan(
            query=query,
            sparse_text=sparse_text,
            query_filter=query_filter,
            limit=limit,
        )
        try:
            response = self._client.query_points(
                collection_name=self._collection_name,
                query=plan.query,
                using=plan.using,
                prefetch=plan.prefetch,
                query_filter=plan.query_filter,
                limit=plan.limit,
                with_payload=True,
                with_vectors=False,
            )
        except ApiException as exc:
            raise RetrievalBackendError("Qdrant 검색 요청에 실패했습니다.") from exc

        return [
            SearchHit(chunk=_to_chunk(point), score=float(point.score)) for point in response.points
        ]

    def search_within_document(
        self,
        query: SearchQuery,
        *,
        source_file_name: str,
        document_types: frozenset[DocumentType] | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        """원본 파일 하나로 검색 범위를 제한한다."""

        return self.search_chunks(
            query,
            filters=SearchFilters(
                source_file_name=source_file_name,
                document_types=document_types,
            ),
            limit=limit,
        )

    def get_neighbor_chunks(
        self,
        request: NeighborRequest,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> list[RetrievedChunk]:
        """같은 문서의 인접 청크를 문서 순서대로 조회한다."""

        limit = request.before + request.after + 1
        _validate_limit(limit)
        try:
            records, _next_offset = self._client.scroll(
                collection_name=self._collection_name,
                scroll_filter=QdrantFilterBuilder.neighbors(
                    request,
                    document_types=document_types,
                ),
                limit=limit,
                order_by="chunk_index",
                with_payload=True,
                with_vectors=False,
            )
        except ApiException as exc:
            raise RetrievalBackendError("Qdrant 인접 청크 조회에 실패했습니다.") from exc

        chunks = [_to_chunk(record) for record in records]
        return sorted(chunks, key=lambda chunk: chunk.chunk_index)

    def get_chunk(
        self,
        chunk_id: str,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> RetrievedChunk | None:
        """UUID chunk ID로 근거 하나를 다시 조회한다."""

        try:
            point_id = str(UUID(chunk_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise RetrievalDataError("chunk_id가 올바른 UUID가 아닙니다.") from exc

        try:
            records = self._client.retrieve(
                collection_name=self._collection_name,
                ids=[point_id],
                with_payload=True,
                with_vectors=False,
            )
        except ApiException as exc:
            raise RetrievalBackendError("Qdrant 청크 조회에 실패했습니다.") from exc

        if not records:
            return None
        if len(records) != 1:
            raise RetrievalDataError("단건 chunk ID 조회가 여러 point를 반환했습니다.")
        chunk = _to_chunk(records[0])
        if document_types is not None and chunk.document_type not in document_types:
            return None
        return chunk

    def _build_query_plan(
        self,
        *,
        query: SearchQuery,
        sparse_text: str,
        query_filter: models.Filter | None,
        limit: int,
    ) -> _QueryPlan:
        return _build_query_plan(
            query=query,
            sparse_text=sparse_text,
            query_filter=query_filter,
            limit=limit,
            prefetch_limit=self._prefetch_limit,
        )


class AsyncQdrantChunkRetriever:
    """온라인 Agent가 사용하는 native async Qdrant 조회 Adapter."""

    def __init__(
        self,
        client: AsyncQdrantClient,
        *,
        collection_name: str,
        prefetch_limit: int = 30,
    ) -> None:
        collection_name = collection_name.strip()
        if not collection_name:
            raise ValueError("Qdrant collection 이름은 비어 있을 수 없습니다.")
        _validate_limit(prefetch_limit)
        self._client = client
        self._collection_name = collection_name
        self._prefetch_limit = prefetch_limit

    async def search_chunks(
        self,
        query: SearchQuery,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        """전체 corpus를 이벤트 루프를 막지 않고 검색한다."""

        _validate_limit(limit)
        query_filter = QdrantFilterBuilder.build(filters or SearchFilters())
        sparse_text = await async_to_bm25_text(query.text)
        if query.mode is SearchMode.SPARSE and not sparse_text:
            return []

        plan = _build_query_plan(
            query=query,
            sparse_text=sparse_text,
            query_filter=query_filter,
            limit=limit,
            prefetch_limit=self._prefetch_limit,
        )
        try:
            response = await self._client.query_points(
                collection_name=self._collection_name,
                query=plan.query,
                using=plan.using,
                prefetch=plan.prefetch,
                query_filter=plan.query_filter,
                limit=plan.limit,
                with_payload=True,
                with_vectors=False,
            )
        except ApiException as exc:
            raise RetrievalBackendError("Qdrant 검색 요청에 실패했습니다.") from exc

        return [
            SearchHit(chunk=_to_chunk(point), score=float(point.score)) for point in response.points
        ]

    async def search_within_document(
        self,
        query: SearchQuery,
        *,
        source_file_name: str,
        document_types: frozenset[DocumentType] | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        """원본 파일 하나로 검색 범위를 제한한다."""

        return await self.search_chunks(
            query,
            filters=SearchFilters(
                source_file_name=source_file_name,
                document_types=document_types,
            ),
            limit=limit,
        )

    async def get_neighbor_chunks(
        self,
        request: NeighborRequest,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> list[RetrievedChunk]:
        """같은 문서의 인접 청크를 문서 순서대로 조회한다."""

        limit = request.before + request.after + 1
        _validate_limit(limit)
        try:
            records, _next_offset = await self._client.scroll(
                collection_name=self._collection_name,
                scroll_filter=QdrantFilterBuilder.neighbors(
                    request,
                    document_types=document_types,
                ),
                limit=limit,
                order_by="chunk_index",
                with_payload=True,
                with_vectors=False,
            )
        except ApiException as exc:
            raise RetrievalBackendError("Qdrant 인접 청크 조회에 실패했습니다.") from exc

        chunks = [_to_chunk(record) for record in records]
        return sorted(chunks, key=lambda chunk: chunk.chunk_index)

    async def get_chunk(
        self,
        chunk_id: str,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> RetrievedChunk | None:
        """UUID chunk ID로 근거 하나를 다시 조회한다."""

        try:
            point_id = str(UUID(chunk_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise RetrievalDataError("chunk_id가 올바른 UUID가 아닙니다.") from exc

        try:
            records = await self._client.retrieve(
                collection_name=self._collection_name,
                ids=[point_id],
                with_payload=True,
                with_vectors=False,
            )
        except ApiException as exc:
            raise RetrievalBackendError("Qdrant 청크 조회에 실패했습니다.") from exc

        if not records:
            return None
        if len(records) != 1:
            raise RetrievalDataError("단건 chunk ID 조회가 여러 point를 반환했습니다.")
        chunk = _to_chunk(records[0])
        if document_types is not None and chunk.document_type not in document_types:
            return None
        return chunk


def _build_query_plan(
    *,
    query: SearchQuery,
    sparse_text: str,
    query_filter: models.Filter | None,
    limit: int,
    prefetch_limit: int,
) -> _QueryPlan:
    if query.mode is SearchMode.SPARSE:
        return _QueryPlan(
            query=_sparse_document(sparse_text),
            using=SPARSE_VECTOR_NAME,
            prefetch=None,
            query_filter=query_filter,
            limit=limit,
        )

    dense = list(query.dense or ())
    if query.mode is SearchMode.DENSE or not sparse_text:
        return _QueryPlan(
            query=dense,
            using=DENSE_VECTOR_NAME,
            prefetch=None,
            query_filter=query_filter,
            limit=limit,
        )

    resolved_prefetch_limit = max(prefetch_limit, limit)
    return _QueryPlan(
        prefetch=[
            models.Prefetch(
                query=_sparse_document(sparse_text),
                using=SPARSE_VECTOR_NAME,
                limit=resolved_prefetch_limit,
                filter=query_filter,
            ),
            models.Prefetch(
                query=dense,
                using=DENSE_VECTOR_NAME,
                limit=resolved_prefetch_limit,
                filter=query_filter,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        using=None,
        query_filter=None,
        limit=limit,
    )


def _sparse_document(text: str) -> models.Document:
    return models.Document(
        text=text,
        model=SPARSE_MODEL_NAME,
        options=BM25_OPTIONS,
    )


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not 1 <= limit <= _MAX_RESULT_LIMIT:
        raise ValueError(f"검색 결과 수는 1~{_MAX_RESULT_LIMIT} 사이여야 합니다.")


def _to_chunk(point: models.ScoredPoint | models.Record) -> RetrievedChunk:
    try:
        chunk_id = str(UUID(str(point.id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise RetrievalDataError("Qdrant point ID가 올바른 UUID가 아닙니다.") from exc

    try:
        payload = _ChunkPayload.model_validate(point.payload)
    except ValidationError as exc:
        raise RetrievalDataError("Qdrant payload가 retrieval 저장 계약을 위반했습니다.") from exc

    heading_path = tuple(payload.heading_path)
    page_numbers = tuple(sorted(set(payload.page_numbers)))
    return RetrievedChunk(
        chunk_id=chunk_id,
        source_file_name=payload.source_file_name,
        source_format=payload.source_format,
        document_type=payload.document_type,
        chunk_index=payload.chunk_index,
        content=payload.content,
        heading_path=heading_path,
        captions=tuple(payload.captions),
        element_types=tuple(dict.fromkeys(payload.element_types)),
        page_numbers=page_numbers,
        title=heading_path[-1] if heading_path else Path(payload.source_file_name).stem,
        locator=make_locator(page_numbers, heading_path, payload.chunk_index),
    )
