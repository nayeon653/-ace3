"""도메인 Agent가 사용하는 검색 오케스트레이터."""

from __future__ import annotations

from typing import Protocol

from pension_agent.core import (
    NeighborRequest,
    RetrievedChunk,
    SearchFilters,
    SearchHit,
    SearchMode,
    SearchQuery,
)

_MAX_RESULT_LIMIT = 100


class QueryEmbedder(Protocol):
    """검색문 하나를 dense vector로 변환하는 제공자 경계."""

    def embed_query(self, text: str) -> list[float]:
        """검색문에 대응하는 dense vector를 반환한다."""


class SearchBackend(Protocol):
    """Agent가 의존하는 도메인 중립 검색 기능."""

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
        limit: int = 10,
    ) -> list[SearchHit]:
        """원본 문서 하나에서 검색한다."""

    def get_neighbor_chunks(self, request: NeighborRequest) -> list[RetrievedChunk]:
        """기준 청크 주변의 문맥을 조회한다."""

    def get_chunk(self, chunk_id: str) -> RetrievedChunk | None:
        """청크 ID로 근거 하나를 조회한다."""


class QueryEmbeddingError(RuntimeError):
    """검색문 dense embedding을 안전하게 생성하지 못한 경우."""


class SearchAgent:
    """검색문 준비와 검색 Backend 호출을 캡슐화한다."""

    def __init__(self, *, embedder: QueryEmbedder, backend: SearchBackend) -> None:
        self._embedder = embedder
        self._backend = backend

    def search_chunks(
        self,
        text: str,
        *,
        filters: SearchFilters | None = None,
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 10,
    ) -> list[SearchHit]:
        """원문 검색어만 받아 전체 corpus 검색을 실행한다."""

        _validate_limit(limit)
        return self._backend.search_chunks(
            self._build_query(text, mode=mode),
            filters=filters,
            limit=limit,
        )

    def search_within_document(
        self,
        text: str,
        *,
        source_file_name: str,
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 10,
    ) -> list[SearchHit]:
        """원문 검색어만 받아 문서 범위 검색을 실행한다."""

        _validate_limit(limit)
        source_file_name = source_file_name.strip()
        if not source_file_name:
            raise ValueError("원본 파일명 필터는 비어 있을 수 없습니다.")

        return self._backend.search_within_document(
            self._build_query(text, mode=mode),
            source_file_name=source_file_name,
            limit=limit,
        )

    def get_neighbor_chunks(self, request: NeighborRequest) -> list[RetrievedChunk]:
        """인접 청크 조회를 검색 Backend에 위임한다."""

        return self._backend.get_neighbor_chunks(request)

    def get_chunk(self, chunk_id: str) -> RetrievedChunk | None:
        """단건 청크 조회를 검색 Backend에 위임한다."""

        return self._backend.get_chunk(chunk_id)

    def _build_query(self, text: str, *, mode: SearchMode) -> SearchQuery:
        if mode is SearchMode.SPARSE:
            return SearchQuery(text=text, mode=mode)

        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("검색문은 비어 있을 수 없습니다.")

        provider_failed = False
        try:
            raw_dense = self._embedder.embed_query(normalized_text)
        # 외부 임베딩 구현마다 예외 계층이 달라 Provider 경계에서 한 번에 정제한다.
        except Exception:  # noqa: BLE001
            provider_failed = True

        if provider_failed:
            raise QueryEmbeddingError("검색문 임베딩 생성에 실패했습니다.")

        invalid_result = False
        try:
            query = SearchQuery(text=normalized_text, dense=tuple(raw_dense), mode=mode)
        except (TypeError, ValueError):
            invalid_result = True

        if invalid_result:
            raise QueryEmbeddingError("검색문 임베딩 결과가 올바르지 않습니다.")
        return query


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not 1 <= limit <= _MAX_RESULT_LIMIT:
        raise ValueError(f"검색 결과 수는 1~{_MAX_RESULT_LIMIT} 사이여야 합니다.")
