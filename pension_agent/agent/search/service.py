"""Router와 결정론적 검색 전략을 실행하는 Search Service."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from dataclasses import dataclass, field
from math import isfinite
from time import monotonic
from typing import Protocol

from langsmith import traceable

from pension_agent.agent.contracts import (
    Permission,
    document_types_for_permission,
    validate_permission,
)
from pension_agent.agent.execution import effective_deadline
from pension_agent.agent.search.evidence_filter import EvidenceFilter
from pension_agent.agent.search.ports import ChunkRetriever, QueryEmbedder
from pension_agent.agent.search.router import SearchRouter
from pension_agent.agent.search.schemas import SearchPlan, SearchRequest, SearchResult
from pension_agent.config import DEFAULT_SEARCH_SERVICE_CONFIG, SearchServiceConfig
from pension_agent.core import (
    DocumentType,
    NeighborRequest,
    RetrievalError,
    RetrievedChunk,
    SearchFilters,
    SearchHit,
    SearchMode,
    SearchQuery,
)

logger = logging.getLogger(__name__)
_NO_RESULTS_LIMITATION = "제공 문서에서 관련 검색 결과를 확인하지 못했습니다."


class SearchRunner(Protocol):
    """Domain Agent가 의존하는 최소 검색 실행 계약."""

    def search(
        self,
        request: SearchRequest,
        *,
        permission: Permission,
        deadline: float | None = None,
    ) -> Awaitable[SearchResult]: ...


class SearchServiceError(RuntimeError):
    """외부 구현 세부사항을 제거한 Search Service 오류."""


@dataclass(slots=True)
class SearchService:
    """검색 요청 하나를 bounded 실행해 검증된 원문 청크를 반환한다."""

    embedder: QueryEmbedder
    retriever: ChunkRetriever
    config: SearchServiceConfig = DEFAULT_SEARCH_SERVICE_CONFIG
    router: SearchRouter | None = None
    evidence_filter: EvidenceFilter | None = None
    max_concurrency: int | None = None
    _capacity: asyncio.Semaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """기본 Router·EvidenceFilter와 요청 동시성 경계를 만든다."""

        concurrency = (
            self.config.max_concurrency if self.max_concurrency is None else self.max_concurrency
        )
        if concurrency < 1:
            raise ValueError("Search Service 동시 실행 상한은 1 이상이어야 합니다.")
        self.max_concurrency = concurrency
        self.router = self.router or SearchRouter(self.config)
        self.evidence_filter = self.evidence_filter or EvidenceFilter(self.config)
        self._capacity = asyncio.Semaphore(concurrency)

    @traceable(name="search_service", run_type="retriever")
    async def search(
        self,
        request: SearchRequest,
        *,
        permission: Permission,
        deadline: float | None = None,
    ) -> SearchResult:
        """Router를 한 번 실행하고 최초 검색과 선택적 문맥 확장을 제한한다."""

        started_at = monotonic()
        try:
            validated_permission = validate_permission(permission)
        except (TypeError, ValueError):
            result = _failed_result("검색 문서 접근 권한이 올바르지 않습니다.")
            _log_search_run(
                permission="invalid",
                route="not_started",
                result=result,
                elapsed_seconds=monotonic() - started_at,
            )
            return result

        search_deadline = effective_deadline(
            timeout_seconds=self.config.timeout_seconds,
            parent_deadline=deadline,
        )
        if search_deadline <= asyncio.get_running_loop().time():
            result = _timeout_result()
            _log_search_run(
                permission=validated_permission.value,
                route="not_started",
                result=result,
                elapsed_seconds=monotonic() - started_at,
            )
            return result

        route = "not_started"
        try:
            async with asyncio.timeout_at(search_deadline):
                async with self._capacity:
                    router = self.router
                    if router is None:
                        raise SearchServiceError("Search Router가 설정되지 않았습니다.")
                    authorized_document_types = document_types_for_permission(validated_permission)
                    plan = router.route(
                        request,
                        document_types=authorized_document_types,
                    )
                    if plan.document_types != authorized_document_types:
                        raise SearchServiceError("검색 계획이 문서 접근 권한을 위반했습니다.")
                    route = plan.route
                    chunks = await self._execute(plan)
                    result = SearchResult(
                        execution_status="completed",
                        retrieved_chunks=self._filter().to_payloads(chunks),
                        limitations=[] if chunks else [_NO_RESULTS_LIMITATION],
                    )
        except TimeoutError:
            result = _timeout_result()
        except SearchServiceError as exc:
            result = _failed_result(str(exc))
        except RetrievalError:
            result = _failed_result("검색 저장소 실행에 실패했습니다.")
        except Exception:  # noqa: BLE001
            result = _failed_result("Search Service 실행에 실패했습니다.")

        _log_search_run(
            permission=validated_permission.value,
            route=route,
            result=result,
            elapsed_seconds=monotonic() - started_at,
        )
        return result

    async def _execute(
        self,
        plan: SearchPlan,
    ) -> list[RetrievedChunk]:
        document_types = plan.document_types
        if plan.route == "chunk_lookup":
            chunks = await self._lookup_chunk(plan, document_types=document_types)
        else:
            hits = await self._search_hits(plan, document_types=document_types)
            _validate_authorized_hits(hits, document_types=document_types)
            _validate_finite_scores(hits)
            if plan.route == "within_document":
                _validate_source_hits(hits, source_file_name=plan.source_file_name)
            chunks = self._filter().filter_hits(hits)
        if not plan.expand_neighbors or not chunks:
            return chunks
        return await self._expand_neighbors(plan, chunks)

    async def _lookup_chunk(
        self,
        plan: SearchPlan,
        *,
        document_types: frozenset[DocumentType],
    ) -> list[RetrievedChunk]:
        if plan.chunk_id is None:
            raise SearchServiceError("청크 직접 조회 계획이 올바르지 않습니다.")
        chunk = await self.retriever.get_chunk(
            plan.chunk_id,
            document_types=document_types,
        )
        chunks = [chunk] if chunk is not None else []
        _validate_authorized_chunks(chunks, document_types=document_types)
        if chunk is not None and chunk.chunk_id != plan.chunk_id:
            raise SearchServiceError("청크 직접 조회 결과의 ID가 요청과 일치하지 않습니다.")
        return self._filter().filter_chunks(chunks)

    async def _search_hits(
        self,
        plan: SearchPlan,
        *,
        document_types: frozenset[DocumentType],
    ) -> list[SearchHit]:
        if plan.query is None or plan.mode is None:
            raise SearchServiceError("검색 계획에 검색문과 모드가 필요합니다.")
        query = await self._build_query(plan.query, mode=plan.mode)
        if plan.route == "global":
            return await self.retriever.search_chunks(
                query,
                filters=SearchFilters(document_types=document_types),
                limit=plan.candidate_limit,
            )
        if plan.source_file_name is None:
            raise SearchServiceError("문서 범위 검색 계획에 원본 파일명이 필요합니다.")
        return await self.retriever.search_within_document(
            query,
            source_file_name=plan.source_file_name,
            document_types=document_types,
            limit=plan.candidate_limit,
        )

    async def _build_query(self, text: str, *, mode: SearchMode) -> SearchQuery:
        if mode is SearchMode.SPARSE:
            return SearchQuery(text=text, mode=mode)
        try:
            dense = tuple(await self.embedder.aembed_query(text))
            return SearchQuery(text=text, dense=dense, mode=mode)
        except Exception:  # noqa: BLE001
            raise SearchServiceError("검색문 임베딩 생성에 실패했습니다.") from None

    async def _expand_neighbors(
        self,
        plan: SearchPlan,
        chunks: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        anchor = chunks[0]
        neighbors = await self.retriever.get_neighbor_chunks(
            NeighborRequest(
                source_file_name=anchor.source_file_name,
                chunk_index=anchor.chunk_index,
                before=plan.neighbor_before,
                after=plan.neighbor_after,
            ),
            document_types=plan.document_types,
        )
        _validate_authorized_chunks(neighbors, document_types=plan.document_types)
        _validate_neighbor_chunks(
            neighbors,
            anchor=anchor,
            before=plan.neighbor_before,
            after=plan.neighbor_after,
        )
        ordered_context = sorted(
            [
                *(chunk for chunk in neighbors if chunk.chunk_id != anchor.chunk_id),
                anchor,
            ],
            key=lambda chunk: chunk.chunk_index,
        )
        context = self._filter().filter_context(
            ordered_context,
            anchor_chunk_id=anchor.chunk_id,
        )
        remaining_slots = self.config.result_limit - len(context)
        if remaining_slots <= 0:
            return context
        context_ids = {chunk.chunk_id for chunk in context}
        remaining_hits = [chunk for chunk in chunks[1:] if chunk.chunk_id not in context_ids]
        return [*context, *self._filter().filter_chunks(remaining_hits)[:remaining_slots]]

    def _filter(self) -> EvidenceFilter:
        evidence_filter = self.evidence_filter
        if evidence_filter is None:
            raise SearchServiceError("EvidenceFilter가 설정되지 않았습니다.")
        return evidence_filter


def _validate_authorized_hits(
    hits: list[SearchHit],
    *,
    document_types: frozenset[DocumentType],
) -> None:
    _validate_authorized_chunks(
        [hit.chunk for hit in hits],
        document_types=document_types,
    )


def _validate_authorized_chunks(
    chunks: list[RetrievedChunk],
    *,
    document_types: frozenset[DocumentType],
) -> None:
    if any(chunk.document_type not in document_types for chunk in chunks):
        raise SearchServiceError("검색 결과가 문서 접근 권한을 위반했습니다.")


def _validate_finite_scores(hits: list[SearchHit]) -> None:
    if any(not isfinite(hit.score) for hit in hits):
        raise SearchServiceError("검색 결과 점수가 올바르지 않습니다.")


def _validate_source_hits(
    hits: list[SearchHit],
    *,
    source_file_name: str | None,
) -> None:
    if source_file_name is None or any(
        hit.chunk.source_file_name != source_file_name for hit in hits
    ):
        raise SearchServiceError("문서 범위 검색 결과가 요청한 원본을 벗어났습니다.")


def _validate_neighbor_chunks(
    chunks: list[RetrievedChunk],
    *,
    anchor: RetrievedChunk,
    before: int,
    after: int,
) -> None:
    minimum_index = max(0, anchor.chunk_index - before)
    maximum_index = anchor.chunk_index + after
    if any(
        chunk.source_file_name != anchor.source_file_name
        or not minimum_index <= chunk.chunk_index <= maximum_index
        for chunk in chunks
    ):
        raise SearchServiceError("인접 문맥 결과가 요청한 문서 범위를 벗어났습니다.")


def _failed_result(message: str) -> SearchResult:
    return SearchResult(execution_status="failed", error=message)


def _timeout_result() -> SearchResult:
    return SearchResult(
        execution_status="timeout",
        error="Search Service 실행 시간이 초과됐습니다.",
    )


def _log_search_run(
    *,
    permission: str,
    route: str,
    result: SearchResult,
    elapsed_seconds: float,
) -> None:
    logger.info(
        "Search Service 실행: permission=%s route=%s status=%s "
        "retrieved_chunk_ids=%s elapsed_ms=%d error=%s",
        permission,
        route,
        result.execution_status,
        [chunk.chunk_id for chunk in result.retrieved_chunks],
        round(elapsed_seconds * 1000),
        result.error,
    )
