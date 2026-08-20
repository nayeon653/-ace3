"""SearchService의 bounded 검색 실행과 안전한 실패 계약을 검증한다."""

import asyncio
from dataclasses import dataclass, field
from typing import Any, cast
from uuid import UUID

import pytest

from pension_agent.agent.contracts import Permission
from pension_agent.agent.search import (
    SearchPlan,
    SearchRequest,
    SearchRouter,
    SearchService,
)
from pension_agent.config import SearchServiceConfig
from pension_agent.core import (
    DocumentType,
    ElementType,
    NeighborRequest,
    RetrievalError,
    RetrievedChunk,
    SearchFilters,
    SearchHit,
    SearchMode,
    SearchQuery,
)

_PENSION_TYPES = frozenset({DocumentType.PENSION_REFERENCE})
_FUND_TYPES = frozenset({DocumentType.FUND_PROSPECTUS})


@dataclass
class FakeEmbedder:
    vector: list[float] = field(default_factory=lambda: [0.1, 0.2])
    error: Exception | None = None
    calls: list[str] = field(default_factory=list)

    async def aembed_query(self, text: str) -> list[float]:
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return self.vector


@dataclass
class FakeRetriever:
    hits: list[SearchHit] = field(default_factory=list)
    neighbors: list[RetrievedChunk] = field(default_factory=list)
    chunk: RetrievedChunk | None = None
    search_error: Exception | None = None
    delay: float = 0
    chunk_searches: list[tuple[SearchQuery, SearchFilters | None, int]] = field(
        default_factory=list
    )
    document_searches: list[tuple[SearchQuery, str, frozenset[DocumentType] | None, int]] = field(
        default_factory=list
    )
    neighbor_requests: list[tuple[NeighborRequest, frozenset[DocumentType] | None]] = field(
        default_factory=list
    )
    chunk_ids: list[tuple[str, frozenset[DocumentType] | None]] = field(default_factory=list)

    async def search_chunks(
        self,
        query: SearchQuery,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        self.chunk_searches.append((query, filters, limit))
        await self._before_result()
        return self.hits

    async def search_within_document(
        self,
        query: SearchQuery,
        *,
        source_file_name: str,
        document_types: frozenset[DocumentType] | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        self.document_searches.append((query, source_file_name, document_types, limit))
        await self._before_result()
        return self.hits

    async def get_neighbor_chunks(
        self,
        request: NeighborRequest,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> list[RetrievedChunk]:
        self.neighbor_requests.append((request, document_types))
        await self._before_result()
        return self.neighbors

    async def get_chunk(
        self,
        chunk_id: str,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> RetrievedChunk | None:
        self.chunk_ids.append((chunk_id, document_types))
        await self._before_result()
        return self.chunk

    async def _before_result(self) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.search_error is not None:
            raise self.search_error


@dataclass
class RecordingRouter:
    inner: SearchRouter
    calls: list[tuple[SearchRequest, frozenset[DocumentType]]] = field(default_factory=list)

    def route(
        self,
        request: SearchRequest,
        *,
        document_types: frozenset[DocumentType],
    ) -> SearchPlan:
        self.calls.append((request, document_types))
        return self.inner.route(request, document_types=document_types)


def _chunk(
    chunk_index: int,
    *,
    document_type: DocumentType = DocumentType.PENSION_REFERENCE,
    source_file_name: str = "guide.pdf",
    content: str | None = None,
    chunk_id: str | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id or str(UUID(int=chunk_index + 1)),
        source_file_name=source_file_name,
        source_format="pdf",
        document_type=document_type,
        chunk_index=chunk_index,
        content=content or f"{chunk_index}번 청크의 연금 근거",
        heading_path=("연금",),
        captions=(),
        element_types=(ElementType.TEXT,),
        page_numbers=(chunk_index + 1,),
        title=f"연금 근거 {chunk_index}",
        locator=f"{chunk_index + 1}페이지",
    )


def _config(**overrides: Any) -> SearchServiceConfig:
    values: dict[str, Any] = {
        "max_concurrency": 2,
        "timeout_seconds": 1,
        "default_search_mode": SearchMode.HYBRID,
        "candidate_limit": 6,
        "result_limit": 3,
        "neighbor_before": 1,
        "neighbor_after": 1,
    }
    values.update(overrides)
    return SearchServiceConfig.model_validate(values)


def _service(
    retriever: Any,
    *,
    embedder: FakeEmbedder | None = None,
    config: SearchServiceConfig | None = None,
    router: Any = None,
) -> tuple[SearchService, FakeEmbedder]:
    resolved_embedder = embedder or FakeEmbedder()
    service = SearchService(
        embedder=resolved_embedder,
        retriever=retriever,
        config=config or _config(),
        router=router,
    )
    return service, resolved_embedder


def test_global_route_executes_once_with_plan_provenance_and_returns_ranked_raw_chunks() -> None:
    first = _chunk(1)
    second = _chunk(2)
    retriever = FakeRetriever(
        hits=[SearchHit(chunk=first, score=0.6), SearchHit(chunk=second, score=0.9)]
    )
    config = _config(candidate_limit=4, result_limit=2)
    router = RecordingRouter(SearchRouter(config))
    service, embedder = _service(retriever, config=config, router=router)
    request = SearchRequest(objective="IRP 이전 근거")

    result = asyncio.run(service.search(request, permission=Permission.POLICY))

    assert result.execution_status == "completed"
    assert [chunk.chunk_id for chunk in result.retrieved_chunks] == [
        second.chunk_id,
        first.chunk_id,
    ]
    assert embedder.calls == ["IRP 이전 근거"]
    assert router.calls == [(request, _PENSION_TYPES)]
    assert retriever.chunk_searches == [
        (
            SearchQuery(text="IRP 이전 근거", dense=(0.1, 0.2), mode=SearchMode.HYBRID),
            SearchFilters(document_types=_PENSION_TYPES),
            4,
        )
    ]
    assert retriever.document_searches == []
    assert retriever.neighbor_requests == []


def test_service_executes_route_strategy_from_self_contained_plan() -> None:
    anchor = _chunk(5)
    retriever = FakeRetriever(
        hits=[SearchHit(chunk=anchor, score=0.9)],
        neighbors=[_chunk(6), _chunk(7)],
    )
    plan = SearchPlan(
        route="global",
        query="Router가 확정한 검색문",
        mode=SearchMode.SPARSE,
        document_types=_PENSION_TYPES,
        candidate_limit=2,
        expand_neighbors=True,
        neighbor_before=0,
        neighbor_after=2,
    )

    class ScriptedRouter:
        def route(
            self,
            request: SearchRequest,
            *,
            document_types: frozenset[DocumentType],
        ) -> SearchPlan:
            del request
            assert document_types == _PENSION_TYPES
            return plan

    service, embedder = _service(retriever, router=ScriptedRouter())

    result = asyncio.run(
        service.search(SearchRequest(objective="원 요청"), permission=Permission.POLICY)
    )

    assert result.execution_status == "completed"
    assert embedder.calls == []
    assert retriever.chunk_searches[0] == (
        SearchQuery(text="Router가 확정한 검색문", mode=SearchMode.SPARSE),
        SearchFilters(document_types=_PENSION_TYPES),
        2,
    )
    assert retriever.neighbor_requests == [
        (
            NeighborRequest(
                source_file_name="guide.pdf",
                chunk_index=5,
                before=0,
                after=2,
            ),
            _PENSION_TYPES,
        )
    ]


def test_document_route_preserves_explicit_source_scope() -> None:
    retriever = FakeRetriever(hits=[SearchHit(chunk=_chunk(1), score=0.8)])
    service, _embedder = _service(retriever)

    result = asyncio.run(
        service.search(
            SearchRequest(objective="중도 해지", source_file_name="guide.pdf"),
            permission=Permission.POLICY,
        )
    )

    assert result.execution_status == "completed"
    assert len(retriever.document_searches) == 1
    query, source_file_name, document_types, limit = retriever.document_searches[0]
    assert query.text == "중도 해지"
    assert source_file_name == "guide.pdf"
    assert document_types == _PENSION_TYPES
    assert limit == 6
    assert retriever.chunk_searches == []


def test_chunk_route_skips_embedding_and_search() -> None:
    chunk = _chunk(2)
    retriever = FakeRetriever(chunk=chunk)
    embedder = FakeEmbedder(error=RuntimeError("호출되면 안 됩니다."))
    service, _embedder = _service(retriever, embedder=embedder)

    result = asyncio.run(
        service.search(
            SearchRequest(objective="청크 확인", chunk_id=chunk.chunk_id),
            permission=Permission.POLICY,
        )
    )

    assert result.execution_status == "completed"
    assert result.retrieved_chunks[0].chunk_id == chunk.chunk_id
    assert embedder.calls == []
    assert retriever.chunk_ids == [(chunk.chunk_id, _PENSION_TYPES)]
    assert retriever.chunk_searches == []


def test_sparse_plan_skips_embedding() -> None:
    retriever = FakeRetriever()
    embedder = FakeEmbedder(error=RuntimeError("호출되면 안 됩니다."))
    service, _embedder = _service(
        retriever,
        embedder=embedder,
        config=_config(default_search_mode=SearchMode.SPARSE),
    )

    result = asyncio.run(
        service.search(SearchRequest(objective="IRP 이전"), permission=Permission.POLICY)
    )

    assert result.execution_status == "completed"
    assert embedder.calls == []
    assert retriever.chunk_searches[0][0] == SearchQuery(
        text="IRP 이전",
        mode=SearchMode.SPARSE,
    )


def test_empty_search_returns_completed_result_with_limitation() -> None:
    service, _embedder = _service(FakeRetriever())

    result = asyncio.run(
        service.search(SearchRequest(objective="없는 근거"), permission=Permission.POLICY)
    )

    assert result.execution_status == "completed"
    assert result.retrieved_chunks == []
    assert result.limitations == ["제공 문서에서 관련 검색 결과를 확인하지 못했습니다."]


def test_neighbor_expansion_runs_at_most_once_and_preserves_anchor() -> None:
    anchor = _chunk(5)
    other_hit = _chunk(20)
    before = _chunk(4)
    after = _chunk(6)
    retriever = FakeRetriever(
        hits=[SearchHit(chunk=anchor, score=0.9), SearchHit(chunk=other_hit, score=0.8)],
        neighbors=[after, before],
    )
    service, _embedder = _service(
        retriever,
        config=_config(result_limit=2, neighbor_before=1, neighbor_after=1),
    )

    result = asyncio.run(
        service.search(
            SearchRequest(objective="이전 문맥", expand_neighbors=True),
            permission=Permission.POLICY,
        )
    )

    assert result.execution_status == "completed"
    assert [chunk.chunk_index for chunk in result.retrieved_chunks] == [4, 5]
    assert any(chunk.chunk_id == anchor.chunk_id for chunk in result.retrieved_chunks)
    assert len(retriever.chunk_searches) == 1
    assert retriever.neighbor_requests == [
        (
            NeighborRequest(
                source_file_name="guide.pdf",
                chunk_index=5,
                before=1,
                after=1,
            ),
            _PENSION_TYPES,
        )
    ]


def test_neighbor_expansion_fails_closed_when_retriever_leaves_requested_window() -> None:
    anchor = _chunk(5)
    retriever = FakeRetriever(
        hits=[SearchHit(chunk=anchor, score=0.9)],
        neighbors=[_chunk(8)],
    )
    service, _embedder = _service(retriever)

    result = asyncio.run(
        service.search(
            SearchRequest(objective="이전 문맥", expand_neighbors=True),
            permission=Permission.POLICY,
        )
    )

    assert result.execution_status == "failed"
    assert result.retrieved_chunks == []
    assert result.error == "인접 문맥 결과가 요청한 문서 범위를 벗어났습니다."


def test_neighbor_expansion_fails_closed_for_another_source() -> None:
    anchor = _chunk(5)
    retriever = FakeRetriever(
        hits=[SearchHit(chunk=anchor, score=0.9)],
        neighbors=[_chunk(4, source_file_name="other.pdf")],
    )
    service, _embedder = _service(retriever)

    result = asyncio.run(
        service.search(
            SearchRequest(objective="이전 문맥", expand_neighbors=True),
            permission=Permission.POLICY,
        )
    )

    assert result.execution_status == "failed"
    assert result.error == "인접 문맥 결과가 요청한 문서 범위를 벗어났습니다."


def test_invalid_permission_fails_before_router_embedding_or_retrieval() -> None:
    config = _config()
    router = RecordingRouter(SearchRouter(config))
    retriever = FakeRetriever()
    service, embedder = _service(retriever, config=config, router=router)

    result = asyncio.run(
        service.search(
            SearchRequest(objective="연금 근거"),
            permission=cast(Permission, "admin"),
        )
    )

    assert result.execution_status == "failed"
    assert result.error == "검색 문서 접근 권한이 올바르지 않습니다."
    assert router.calls == []
    assert embedder.calls == []
    assert retriever.chunk_searches == []


def test_service_rejects_router_plan_outside_authorized_document_types() -> None:
    retriever = FakeRetriever()
    unauthorized_plan = SearchPlan(
        route="global",
        query="상품 문서",
        mode=SearchMode.SPARSE,
        document_types=_FUND_TYPES,
        candidate_limit=3,
        neighbor_before=1,
        neighbor_after=1,
    )

    class UnauthorizedRouter:
        def route(
            self,
            request: SearchRequest,
            *,
            document_types: frozenset[DocumentType],
        ) -> SearchPlan:
            del request
            assert document_types == _PENSION_TYPES
            return unauthorized_plan

    service, embedder = _service(retriever, router=UnauthorizedRouter())

    result = asyncio.run(
        service.search(SearchRequest(objective="연금 근거"), permission=Permission.POLICY)
    )

    assert result.execution_status == "failed"
    assert result.error == "검색 계획이 문서 접근 권한을 위반했습니다."
    assert embedder.calls == []
    assert retriever.chunk_searches == []


def test_result_outside_permission_fails_without_exposing_chunk_content() -> None:
    forbidden = _chunk(
        1,
        document_type=DocumentType.FUND_PROSPECTUS,
        content="노출되면 안 되는 상품 문서",
    )
    retriever = FakeRetriever(hits=[SearchHit(chunk=forbidden, score=0.9)])
    service, _embedder = _service(retriever)

    result = asyncio.run(
        service.search(SearchRequest(objective="연금 근거"), permission=Permission.POLICY)
    )

    assert result.execution_status == "failed"
    assert result.error == "검색 결과가 문서 접근 권한을 위반했습니다."
    assert forbidden.content not in result.error
    assert result.retrieved_chunks == []


def test_document_route_rejects_result_from_another_source() -> None:
    retriever = FakeRetriever(
        hits=[SearchHit(chunk=_chunk(1, source_file_name="other.pdf"), score=0.9)]
    )
    service, _embedder = _service(retriever)

    result = asyncio.run(
        service.search(
            SearchRequest(objective="이전 근거", source_file_name="guide.pdf"),
            permission=Permission.POLICY,
        )
    )

    assert result.execution_status == "failed"
    assert result.error == "문서 범위 검색 결과가 요청한 원본을 벗어났습니다."


def test_chunk_route_rejects_retriever_result_with_another_id() -> None:
    requested = str(UUID(int=10))
    retriever = FakeRetriever(chunk=_chunk(1))
    service, embedder = _service(retriever)

    result = asyncio.run(
        service.search(
            SearchRequest(objective="청크 확인", chunk_id=requested),
            permission=Permission.POLICY,
        )
    )

    assert result.execution_status == "failed"
    assert result.error == "청크 직접 조회 결과의 ID가 요청과 일치하지 않습니다."
    assert embedder.calls == []
    assert retriever.chunk_ids == [(requested, _PENSION_TYPES)]


def test_product_permission_routes_only_to_fund_documents() -> None:
    product_chunk = _chunk(1, document_type=DocumentType.FUND_PROSPECTUS)
    retriever = FakeRetriever(hits=[SearchHit(chunk=product_chunk, score=0.9)])
    service, _embedder = _service(retriever)

    result = asyncio.run(
        service.search(SearchRequest(objective="상품 수수료"), permission=Permission.PRODUCT)
    )

    assert result.execution_status == "completed"
    assert retriever.chunk_searches[0][1] == SearchFilters(document_types=_FUND_TYPES)


def test_expired_parent_deadline_does_not_start_router_or_providers() -> None:
    config = _config()
    router = RecordingRouter(SearchRouter(config))
    retriever = FakeRetriever()
    service, embedder = _service(retriever, config=config, router=router)

    async def scenario() -> Any:
        return await service.search(
            SearchRequest(objective="연금 근거"),
            permission=Permission.POLICY,
            deadline=asyncio.get_running_loop().time() - 1,
        )

    result = asyncio.run(scenario())

    assert result.execution_status == "timeout"
    assert router.calls == []
    assert embedder.calls == []
    assert retriever.chunk_searches == []


def test_local_timeout_cancels_slow_retrieval() -> None:
    retriever = FakeRetriever(delay=0.05)
    service, _embedder = _service(retriever, config=_config(timeout_seconds=0.01))

    result = asyncio.run(
        service.search(SearchRequest(objective="느린 검색"), permission=Permission.POLICY)
    )

    assert result.execution_status == "timeout"
    assert result.error == "Search Service 실행 시간이 초과됐습니다."


class SequencedRetriever(FakeRetriever):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def _before_result(self) -> None:
        if len(self.chunk_searches) == 1:
            self.started.set()
            await self.release.wait()


def test_capacity_wait_uses_same_absolute_parent_deadline() -> None:
    async def scenario() -> tuple[Any, Any, int]:
        retriever = SequencedRetriever()
        service, _embedder = _service(
            retriever,
            config=_config(max_concurrency=1),
        )
        first_task = asyncio.create_task(
            service.search(SearchRequest(objective="첫 검색"), permission=Permission.POLICY)
        )
        await retriever.started.wait()
        second = await service.search(
            SearchRequest(objective="대기 검색"),
            permission=Permission.POLICY,
            deadline=asyncio.get_running_loop().time() + 0.01,
        )
        retriever.release.set()
        return await first_task, second, len(retriever.chunk_searches)

    first, second, call_count = asyncio.run(scenario())

    assert first.execution_status == "completed"
    assert second.execution_status == "timeout"
    assert call_count == 1


def test_cancellation_releases_capacity_without_converting_cancelled_error() -> None:
    async def scenario() -> tuple[Any, int]:
        retriever = SequencedRetriever()
        service, _embedder = _service(
            retriever,
            config=_config(max_concurrency=1),
        )
        first_task = asyncio.create_task(
            service.search(SearchRequest(objective="취소 검색"), permission=Permission.POLICY)
        )
        await retriever.started.wait()
        first_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first_task
        result = await service.search(
            SearchRequest(objective="후속 검색"),
            permission=Permission.POLICY,
        )
        return result, len(retriever.chunk_searches)

    result, call_count = asyncio.run(scenario())

    assert result.execution_status == "completed"
    assert call_count == 2


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (RetrievalError("provider secret=QDRANT"), "검색 저장소 실행에 실패했습니다."),
        (RuntimeError("provider secret=RUNTIME"), "Search Service 실행에 실패했습니다."),
    ],
)
def test_retrieval_failures_are_sanitized(
    error: Exception,
    expected_error: str,
) -> None:
    retriever = FakeRetriever(search_error=error)
    service, _embedder = _service(retriever)

    result = asyncio.run(
        service.search(SearchRequest(objective="검색 오류"), permission=Permission.POLICY)
    )

    assert result.execution_status == "failed"
    assert result.error == expected_error
    assert "secret" not in result.error


@pytest.mark.parametrize("vector", [[], [float("nan")]])
def test_invalid_embedding_is_sanitized_before_retrieval(vector: list[float]) -> None:
    embedder = FakeEmbedder(vector=vector)
    retriever = FakeRetriever()
    service, _embedder = _service(retriever, embedder=embedder)

    result = asyncio.run(
        service.search(SearchRequest(objective="임베딩 오류"), permission=Permission.POLICY)
    )

    assert result.execution_status == "failed"
    assert result.error == "검색문 임베딩 생성에 실패했습니다."
    assert retriever.chunk_searches == []


def test_non_finite_retrieval_score_fails_closed() -> None:
    retriever = FakeRetriever(hits=[SearchHit(chunk=_chunk(1), score=float("inf"))])
    service, _embedder = _service(retriever)

    result = asyncio.run(
        service.search(SearchRequest(objective="점수 오류"), permission=Permission.POLICY)
    )

    assert result.execution_status == "failed"
    assert result.error == "검색 결과 점수가 올바르지 않습니다."
