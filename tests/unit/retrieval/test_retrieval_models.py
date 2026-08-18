"""Qdrant와 독립적인 검색 Query Object 계약을 검증한다."""

import pytest

from pension_agent.core import DocumentType, NeighborRequest, SearchFilters, SearchMode, SearchQuery


def test_hybrid_query_requires_dense_vector() -> None:
    with pytest.raises(ValueError, match="dense vector"):
        SearchQuery(text="퇴직연금", mode=SearchMode.HYBRID)


def test_sparse_query_does_not_require_dense_vector() -> None:
    query = SearchQuery(text="  퇴직연금  ", mode=SearchMode.SPARSE)

    assert query.text == "퇴직연금"
    assert query.dense is None


def test_query_normalizes_dense_values_and_rejects_non_finite_number() -> None:
    query = SearchQuery(text="퇴직연금", dense=(1, 0.5), mode=SearchMode.DENSE)

    assert query.dense == (1.0, 0.5)

    with pytest.raises(ValueError, match="유한한 숫자"):
        SearchQuery(text="퇴직연금", dense=(float("nan"),), mode=SearchMode.DENSE)


def test_source_file_filter_rejects_blank_value() -> None:
    with pytest.raises(ValueError, match="파일명 필터"):
        SearchFilters(source_file_name="   ")


def test_document_type_filter_rejects_empty_set() -> None:
    with pytest.raises(ValueError, match="최소 하나"):
        SearchFilters(document_types=frozenset())

    assert SearchFilters(
        document_types=frozenset({DocumentType.PENSION_REFERENCE})
    ).document_types == frozenset({DocumentType.PENSION_REFERENCE})


def test_neighbor_request_rejects_negative_range() -> None:
    with pytest.raises(ValueError, match="0 이상"):
        NeighborRequest(source_file_name="guide.pdf", chunk_index=3, before=-1)


def test_neighbor_request_rejects_combined_range_over_limit() -> None:
    with pytest.raises(ValueError, match="100개 이하"):
        NeighborRequest(
            source_file_name="guide.pdf",
            chunk_index=2,
            before=99,
            after=99,
        )
