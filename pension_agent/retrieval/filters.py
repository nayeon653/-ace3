"""공용 검색 필터를 Qdrant payload 조건으로 변환한다."""

from qdrant_client import models

from pension_agent.core import NeighborRequest, SearchFilters


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

        if filters.document_type is not None:
            must.append(
                models.FieldCondition(
                    key="document_type",
                    match=models.MatchValue(value=filters.document_type.value),
                )
            )

        element_types = list(dict.fromkeys(value.value for value in filters.element_types))
        if element_types:
            must.append(
                models.FieldCondition(
                    key="element_types",
                    match=models.MatchAny(any=element_types),
                )
            )

        return models.Filter(must=must) if must else None

    @staticmethod
    def neighbors(request: NeighborRequest) -> models.Filter:
        """같은 파일에서 요청한 chunk_index 범위만 선택한다."""

        lower = max(0, request.chunk_index - request.before)
        upper = request.chunk_index + request.after
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="source_file_name",
                    match=models.MatchValue(value=request.source_file_name),
                ),
                models.FieldCondition(
                    key="chunk_index",
                    range=models.Range(gte=lower, lte=upper),
                ),
            ]
        )
