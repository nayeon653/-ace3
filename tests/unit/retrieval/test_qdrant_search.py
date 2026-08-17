"""QdrantSearch가 만드는 SDK 요청과 반환 경계를 검증한다."""

from types import SimpleNamespace
from unittest.mock import create_autospec, patch
from uuid import UUID

import pytest
from qdrant_client import QdrantClient, models

from pension_agent.core import (
    DocumentType,
    ElementType,
    NeighborRequest,
    RetrievalDataError,
    SearchFilters,
    SearchMode,
    SearchQuery,
)
from pension_agent.retrieval.qdrant_search import QdrantSearch, make_locator, to_bm25_text

_CHUNK_ID = "550e8400-e29b-41d4-a716-446655440000"


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_file_name": "guide.pdf",
        "source_format": "pdf",
        "document_type": "pension_reference",
        "chunk_index": 7,
        "content": "퇴직연금의 근거 본문입니다.",
        "embedding_content": "퇴직연금\n퇴직연금의 근거 본문입니다.",
        "heading_path": ["제2장", "가입 절차"],
        "captions": [],
        "element_types": ["text", "table", "text"],
        "page_numbers": [13, 12, 13],
    }
    payload.update(overrides)
    return payload


def _scored_point(**payload_overrides: object) -> models.ScoredPoint:
    return models.ScoredPoint(
        id=_CHUNK_ID,
        version=1,
        score=0.8,
        payload=_payload(**payload_overrides),
    )


def _search() -> tuple[QdrantSearch, QdrantClient]:
    client = create_autospec(QdrantClient, instance=True)
    return QdrantSearch(client, collection_name="pension_documents"), client


def test_kiwi_query_preprocessor_keeps_content_tokens() -> None:
    assert to_bm25_text("퇴직연금은 원금 손실이 발생할 수 있습니다.") == (
        "퇴직 연금 원금 손실 발생 수 있"
    )


def test_hybrid_search_uses_same_filter_for_dense_and_sparse_prefetch() -> None:
    search, client = _search()
    client.query_points.return_value = SimpleNamespace(points=[_scored_point()])
    query = SearchQuery(text="퇴직연금 가입 절차", dense=(0.1, 0.2))
    filters = SearchFilters(
        document_type=DocumentType.PENSION_REFERENCE,
    )

    with patch(
        "pension_agent.retrieval.qdrant_search.to_bm25_text",
        return_value="퇴직 연금 가입 절차",
    ):
        hits = search.search_chunks(query, filters=filters, limit=5)

    kwargs = client.query_points.call_args.kwargs
    assert kwargs["collection_name"] == "pension_documents"
    assert kwargs["using"] is None
    assert kwargs["query_filter"] is None
    assert kwargs["limit"] == 5
    assert kwargs["query"] == models.FusionQuery(fusion=models.Fusion.RRF)
    sparse, dense = kwargs["prefetch"]
    assert sparse.using == "sparse"
    assert dense.using == "dense"
    assert sparse.filter == dense.filter
    assert sparse.limit == dense.limit == 30

    assert len(hits) == 1
    assert hits[0].score == 0.8
    assert hits[0].chunk.title == "가입 절차"
    assert hits[0].chunk.locator == "12–13페이지"
    assert hits[0].chunk.element_types == (ElementType.TEXT, ElementType.TABLE)


def test_dense_search_applies_filter_to_query() -> None:
    search, client = _search()
    client.query_points.return_value = SimpleNamespace(points=[])

    search.search_chunks(
        SearchQuery(text="위험", dense=(0.1,), mode=SearchMode.DENSE),
        filters=SearchFilters(source_file_name="fund.pdf"),
    )

    kwargs = client.query_points.call_args.kwargs
    assert kwargs["query"] == [0.1]
    assert kwargs["using"] == "dense"
    assert kwargs["prefetch"] is None
    assert kwargs["query_filter"] == models.Filter(
        must=[
            models.FieldCondition(
                key="source_file_name",
                match=models.MatchValue(value="fund.pdf"),
            )
        ]
    )


def test_hybrid_search_falls_back_to_dense_when_sparse_text_is_empty() -> None:
    search, client = _search()
    client.query_points.return_value = SimpleNamespace(points=[])

    search.search_chunks(SearchQuery(text="?!", dense=(0.1,), mode=SearchMode.HYBRID))

    kwargs = client.query_points.call_args.kwargs
    assert kwargs["using"] == "dense"
    assert kwargs["prefetch"] is None


def test_sparse_search_does_not_fallback_to_dense_without_content_tokens() -> None:
    search, client = _search()

    query = SearchQuery(text="?!", dense=(0.1,), mode=SearchMode.SPARSE)

    assert search.search_chunks(query) == []
    client.query_points.assert_not_called()


def test_search_within_document_adds_file_filter() -> None:
    search, client = _search()
    client.query_points.return_value = SimpleNamespace(points=[])

    search.search_within_document(
        SearchQuery(text="수수료", dense=(0.3,), mode=SearchMode.DENSE),
        source_file_name="fund.pdf",
    )

    query_filter = client.query_points.call_args.kwargs["query_filter"]
    assert query_filter.must == [
        models.FieldCondition(
            key="source_file_name",
            match=models.MatchValue(value="fund.pdf"),
        ),
    ]


def test_neighbor_chunks_are_returned_in_chunk_order() -> None:
    search, client = _search()
    client.scroll.return_value = (
        [
            models.Record(id=UUID(_CHUNK_ID), payload=_payload(chunk_index=8)),
            models.Record(id=UUID(_CHUNK_ID), payload=_payload(chunk_index=6)),
        ],
        None,
    )

    chunks = search.get_neighbor_chunks(
        NeighborRequest(source_file_name="guide.pdf", chunk_index=7)
    )

    assert [chunk.chunk_index for chunk in chunks] == [6, 8]
    kwargs = client.scroll.call_args.kwargs
    assert kwargs["limit"] == 3
    assert kwargs["order_by"] == "chunk_index"
    assert kwargs["with_vectors"] is False


def test_get_chunk_returns_none_when_point_is_missing() -> None:
    search, client = _search()
    client.retrieve.return_value = []

    assert search.get_chunk(_CHUNK_ID) is None


def test_get_chunk_rejects_invalid_uuid_before_request() -> None:
    search, client = _search()

    with pytest.raises(RetrievalDataError, match="UUID"):
        search.get_chunk("not-a-uuid")

    client.retrieve.assert_not_called()


def test_invalid_payload_raises_data_error() -> None:
    search, client = _search()
    client.query_points.return_value = SimpleNamespace(
        points=[_scored_point(content="")],
    )

    with pytest.raises(RetrievalDataError, match="저장 계약"):
        search.search_chunks(SearchQuery(text="위험", dense=(0.1,), mode=SearchMode.DENSE))


@pytest.mark.parametrize(
    ("pages", "headings", "chunk_index", "expected"),
    [
        ((3,), (), 0, "3페이지"),
        ((3, 5), (), 0, "3페이지, 5페이지"),
        ((), ("가입",), 0, "가입 절"),
        ((), (), 4, "문서 내 청크 5"),
    ],
)
def test_make_locator_fallbacks(
    pages: tuple[int, ...],
    headings: tuple[str, ...],
    chunk_index: int,
    expected: str,
) -> None:
    assert make_locator(pages, headings, chunk_index) == expected
