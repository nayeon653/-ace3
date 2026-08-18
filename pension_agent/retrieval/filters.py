"""공용 검색 필터를 Qdrant payload 조건으로 변환한다."""

from qdrant_client import models

from pension_agent.core import DocumentType, NeighborRequest, SearchFilters


class QdrantFilterBuilder:
    """허용된 payload 필드만 Qdrant 조건으로 만드는 Filter Builder."""

    @staticmethod
    def build(filters: SearchFilters) -> models.Filter | None:
        """Agent 검색 필터를 AND 조건으로 결합한다."""

        must: list[models.Condition] = []

        if filters.source_file_name is not None:
            must.append(
                models.FieldCondition(
                    key="source_file_name",
                    match=models.MatchValue(value=filters.source_file_name),
                )
            )

        if filters.document_types is not None:
            must.append(_document_type_condition(filters.document_types))

        return models.Filter(must=must) if must else None

    @staticmethod
    def neighbors(
        request: NeighborRequest,
        *,
        document_types: frozenset[DocumentType] | None = None,
    ) -> models.Filter:
        """같은 파일에서 요청한 chunk_index 범위만 선택한다."""

        lower = max(0, request.chunk_index - request.before)
        upper = request.chunk_index + request.after
        must: list[models.Condition] = [
            models.FieldCondition(
                key="source_file_name",
                match=models.MatchValue(value=request.source_file_name),
            ),
            models.FieldCondition(
                key="chunk_index",
                range=models.Range(gte=lower, lte=upper),
            ),
        ]
        if document_types is not None:
            must.append(_document_type_condition(document_types))
        return models.Filter(must=must)


def _document_type_condition(
    document_types: frozenset[DocumentType],
) -> models.FieldCondition:
    if not document_types:
        raise ValueError("문서 유형 필터는 최소 하나가 필요합니다.")
    values = sorted(item.value for item in document_types)
    match: models.Match = (
        models.MatchValue(value=values[0]) if len(values) == 1 else models.MatchAny(any=values)
    )
    return models.FieldCondition(key="document_type", match=match)
