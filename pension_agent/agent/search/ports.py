"""Search Agent가 외부 제공자와 검색 구현에 요구하는 Port."""

from typing import Protocol

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

    def embed_query(self, text: str) -> list[float]:
        """검색문에 대응하는 dense vector를 반환한다."""


class ChunkRetriever(Protocol):
    """Search Tool이 의존하는 도메인 중립 청크 조회 기능."""

    def search_chunks(
        self,
        query: SearchQuery,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        """전체 corpus를 검색한다."""

    def search_within_document(
        self,
        query: SearchQuery,
        *,
        source_file_name: str,
        document_types: frozenset[DocumentType] | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        """원본 문서 하나에서 검색한다."""

    def get_neighbor_chunks(
        self,
        request: NeighborRequest,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> list[RetrievedChunk]:
        """기준 청크 주변의 문맥을 조회한다."""

    def get_chunk(
        self,
        chunk_id: str,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> RetrievedChunk | None:
        """청크 ID로 근거 하나를 조회한다."""
