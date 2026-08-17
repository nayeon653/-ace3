"""공용 필터에서 Qdrant payload 조건으로의 변환을 검증한다."""

from qdrant_client import models

from pension_agent.core import (
    DocumentType,
    ElementType,
    NeighborRequest,
    SearchFilters,
)
from pension_agent.retrieval.filters import QdrantFilterBuilder


def test_empty_search_filter_does_not_create_qdrant_filter() -> None:
    assert QdrantFilterBuilder.build(SearchFilters()) is None


def test_filter_builder_combines_supported_metadata_fields() -> None:
    result = QdrantFilterBuilder.build(
        SearchFilters(
            source_file_name="guide.pdf",
            document_type=DocumentType.PENSION_REFERENCE,
            element_types=(ElementType.TABLE, ElementType.TEXT, ElementType.TABLE),
        )
    )

    assert result == models.Filter(
        must=[
            models.FieldCondition(
                key="source_file_name",
                match=models.MatchValue(value="guide.pdf"),
            ),
            models.FieldCondition(
                key="document_type",
                match=models.MatchValue(value="pension_reference"),
            ),
            models.FieldCondition(
                key="element_types",
                match=models.MatchAny(any=["table", "text"]),
            ),
        ]
    )


def test_neighbor_filter_stays_within_file_and_chunk_range() -> None:
    result = QdrantFilterBuilder.neighbors(
        NeighborRequest(
            source_file_name="guide.pdf",
            chunk_index=1,
            before=3,
            after=2,
        )
    )

    assert result == models.Filter(
        must=[
            models.FieldCondition(
                key="source_file_name",
                match=models.MatchValue(value="guide.pdf"),
            ),
            models.FieldCondition(
                key="chunk_index",
                range=models.Range(gte=0, lte=3),
            ),
        ]
    )
