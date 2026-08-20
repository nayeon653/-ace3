"""Search Agent가 외부 제공자와 검색 구현에 요구하는 Port."""

from dataclasses import dataclass
from typing import Protocol

from pension_agent.agent.execution import AsyncConcurrencyLimiter
from pension_agent.core import (
    DocumentType,
    NeighborRequest,
    RetrievedChunk,
    SearchFilters,
    SearchHit,
    SearchQuery,
)


class QueryEmbedder(Protocol):
    """검색문 하나를 dense vector로 변환하는 제공자 경계."""

    async def aembed_query(self, text: str) -> list[float]:
        """검색문에 대응하는 dense vector를 반환한다."""


class ChunkRetriever(Protocol):
    """Search Tool이 의존하는 도메인 중립 청크 조회 기능."""

    async def search_chunks(
        self,
        query: SearchQuery,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        """전체 corpus를 검색한다."""

    async def search_within_document(
        self,
        query: SearchQuery,
        *,
        source_file_name: str,
        document_types: frozenset[DocumentType] | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        """원본 문서 하나에서 검색한다."""

    async def get_neighbor_chunks(
        self,
        request: NeighborRequest,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> list[RetrievedChunk]:
        """기준 청크 주변의 문맥을 조회한다."""

    async def get_chunk(
        self,
        chunk_id: str,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> RetrievedChunk | None:
        """청크 ID로 근거 하나를 조회한다."""


@dataclass(frozen=True, slots=True)
class LimitedQueryEmbedder:
    """여러 요청이 공유하는 embedding 제공자 동시 실행 상한."""

    inner: QueryEmbedder
    limiter: AsyncConcurrencyLimiter

    async def aembed_query(self, text: str) -> list[float]:
        """공유 슬롯 안에서 검색문 embedding을 생성한다."""

        async with self.limiter.slot():
            return await self.inner.aembed_query(text)


@dataclass(frozen=True, slots=True)
class LimitedChunkRetriever:
    """여러 요청이 공유하는 Qdrant 조회 동시 실행 상한."""

    inner: ChunkRetriever
    limiter: AsyncConcurrencyLimiter

    async def search_chunks(
        self,
        query: SearchQuery,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        async with self.limiter.slot():
            return await self.inner.search_chunks(query, filters=filters, limit=limit)

    async def search_within_document(
        self,
        query: SearchQuery,
        *,
        source_file_name: str,
        document_types: frozenset[DocumentType] | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        async with self.limiter.slot():
            return await self.inner.search_within_document(
                query,
                source_file_name=source_file_name,
                document_types=document_types,
                limit=limit,
            )

    async def get_neighbor_chunks(
        self,
        request: NeighborRequest,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> list[RetrievedChunk]:
        async with self.limiter.slot():
            return await self.inner.get_neighbor_chunks(
                request,
                document_types=document_types,
            )

    async def get_chunk(
        self,
        chunk_id: str,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> RetrievedChunk | None:
        async with self.limiter.slot():
            return await self.inner.get_chunk(
                chunk_id,
                document_types=document_types,
            )
