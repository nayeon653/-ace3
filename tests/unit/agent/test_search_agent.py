"""도메인 Agent용 Search Agent 계약을 검증한다."""

from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest

from pension_agent.agent import QueryEmbeddingError, SearchAgent
from pension_agent.core import (
    DocumentType,
    ElementType,
    NeighborRequest,
    RetrievedChunk,
    SearchFilters,
    SearchHit,
    SearchMode,
    SearchQuery,
)


@dataclass
class FakeEmbedder:
    vector: list[float] = field(default_factory=lambda: [0.1, 0.2])
    error: Exception | None = None
    calls: list[str] = field(default_factory=list)

    def embed_query(self, text: str) -> list[float]:
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return self.vector


class ExplodingVector(list[float]):
    def __iter__(self) -> Iterator[float]:
        raise RuntimeError("provider secret=LAZY")


@dataclass
class FakeSearchBackend:
    hits: list[SearchHit] = field(default_factory=list)
    chunks: list[RetrievedChunk] = field(default_factory=list)
    chunk: RetrievedChunk | None = None
    chunk_searches: list[tuple[SearchQuery, SearchFilters | None, int]] = field(
        default_factory=list
    )
    document_searches: list[tuple[SearchQuery, str, int]] = field(default_factory=list)
    neighbor_requests: list[NeighborRequest] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)

    def search_chunks(
        self,
        query: SearchQuery,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        self.chunk_searches.append((query, filters, limit))
        return self.hits

    def search_within_document(
        self,
        query: SearchQuery,
        *,
        source_file_name: str,
        limit: int = 10,
    ) -> list[SearchHit]:
        self.document_searches.append((query, source_file_name, limit))
        return self.hits

    def get_neighbor_chunks(self, request: NeighborRequest) -> list[RetrievedChunk]:
        self.neighbor_requests.append(request)
        return self.chunks

    def get_chunk(self, chunk_id: str) -> RetrievedChunk | None:
        self.chunk_ids.append(chunk_id)
        return self.chunk


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="550e8400-e29b-41d4-a716-446655440000",
        source_file_name="guide.pdf",
        source_format="pdf",
        document_type=DocumentType.PENSION_REFERENCE,
        chunk_index=2,
        content="연금계좌 이전 절차",
        heading_path=("계좌 이전",),
        captions=(),
        element_types=(ElementType.TEXT,),
        page_numbers=(3,),
        title="계좌 이전",
        locator="3페이지",
    )


@pytest.mark.parametrize("mode", [SearchMode.DENSE, SearchMode.HYBRID])
def test_search_chunks_embeds_query_and_preserves_search_contract(mode: SearchMode) -> None:
    embedder = FakeEmbedder()
    backend = FakeSearchBackend()
    filters = SearchFilters(document_type=DocumentType.PENSION_REFERENCE)
    agent = SearchAgent(embedder=embedder, backend=backend)

    result = agent.search_chunks("  IRP 이전 절차  ", filters=filters, mode=mode, limit=7)

    assert result == []
    assert embedder.calls == ["IRP 이전 절차"]
    query, received_filters, received_limit = backend.chunk_searches[0]
    assert query == SearchQuery(text="IRP 이전 절차", dense=(0.1, 0.2), mode=mode)
    assert received_filters is filters
    assert received_limit == 7


def test_sparse_search_skips_query_embedding() -> None:
    embedder = FakeEmbedder(error=RuntimeError("호출되면 안 됩니다."))
    backend = FakeSearchBackend()
    agent = SearchAgent(embedder=embedder, backend=backend)

    agent.search_chunks("IRP 이전 절차", mode=SearchMode.SPARSE)

    assert embedder.calls == []
    query, _filters, _limit = backend.chunk_searches[0]
    assert query == SearchQuery(text="IRP 이전 절차", mode=SearchMode.SPARSE)


def test_document_search_builds_query_and_preserves_document_scope() -> None:
    embedder = FakeEmbedder()
    backend = FakeSearchBackend()
    agent = SearchAgent(embedder=embedder, backend=backend)

    agent.search_within_document(
        "중도해지",
        source_file_name="guide.pdf",
        mode=SearchMode.DENSE,
        limit=4,
    )

    query, source_file_name, limit = backend.document_searches[0]
    assert query == SearchQuery(text="중도해지", dense=(0.1, 0.2), mode=SearchMode.DENSE)
    assert source_file_name == "guide.pdf"
    assert limit == 4


@pytest.mark.parametrize("limit", [0, 101, True])
def test_invalid_limit_fails_before_embedding(limit: int) -> None:
    embedder = FakeEmbedder(error=RuntimeError("호출되면 안 됩니다."))
    agent = SearchAgent(embedder=embedder, backend=FakeSearchBackend())

    with pytest.raises(ValueError, match="검색 결과 수"):
        agent.search_chunks("IRP 이전", limit=limit)

    assert embedder.calls == []


def test_empty_document_name_fails_before_embedding() -> None:
    embedder = FakeEmbedder(error=RuntimeError("호출되면 안 됩니다."))
    agent = SearchAgent(embedder=embedder, backend=FakeSearchBackend())

    with pytest.raises(ValueError, match="원본 파일명"):
        agent.search_within_document("IRP 이전", source_file_name="  ")

    assert embedder.calls == []


def test_lookup_functions_delegate_without_embedding() -> None:
    chunk = _chunk()
    request = NeighborRequest(source_file_name="guide.pdf", chunk_index=2)
    embedder = FakeEmbedder(error=RuntimeError("호출되면 안 됩니다."))
    backend = FakeSearchBackend(chunks=[chunk], chunk=chunk)
    agent = SearchAgent(embedder=embedder, backend=backend)

    assert agent.get_neighbor_chunks(request) == [chunk]
    assert agent.get_chunk(chunk.chunk_id) is chunk
    assert backend.neighbor_requests == [request]
    assert backend.chunk_ids == [chunk.chunk_id]
    assert embedder.calls == []


@pytest.mark.parametrize(
    ("embedder", "message"),
    [
        (FakeEmbedder(error=RuntimeError("provider secret")), "생성에 실패했습니다"),
        (FakeEmbedder(vector=[]), "결과가 올바르지 않습니다"),
        (FakeEmbedder(vector=[float("nan")]), "결과가 올바르지 않습니다"),
        (FakeEmbedder(vector=ExplodingVector()), "결과가 올바르지 않습니다"),
    ],
)
def test_embedding_failure_is_sanitized(embedder: FakeEmbedder, message: str) -> None:
    agent = SearchAgent(embedder=embedder, backend=FakeSearchBackend())

    with pytest.raises(QueryEmbeddingError, match=message) as exc_info:
        agent.search_chunks("IRP 이전")

    assert "secret" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_empty_query_fails_before_embedding() -> None:
    embedder = FakeEmbedder()
    agent = SearchAgent(embedder=embedder, backend=FakeSearchBackend())

    with pytest.raises(ValueError, match="검색문"):
        agent.search_chunks("  ")

    assert embedder.calls == []
