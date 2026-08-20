"""Router 기반 검색 요청, 실행 계획과 결과 계약."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from pension_agent.agent.contracts import ExecutionStatus
from pension_agent.core import DocumentType, SearchMode

SearchRoute = Literal["global", "within_document", "chunk_lookup"]

_NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]


class _SearchSchema(BaseModel):
    """검색 경계에서 사용하는 공통 검증 설정."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class SearchRequest(_SearchSchema):
    """Domain Agent가 검색 구현 세부사항 없이 전달하는 의미 요청."""

    objective: _NonEmptyString
    source_file_name: _NonEmptyString | None = None
    chunk_id: _NonEmptyString | None = None
    expand_neighbors: bool = Field(default=False, strict=True)

    @field_validator("chunk_id")
    @classmethod
    def validate_chunk_id(cls, value: str | None) -> str | None:
        """선택적 청크 ID를 정규화된 UUID로 제한한다."""

        if value is None:
            return None
        try:
            return str(UUID(value))
        except ValueError:
            raise ValueError("chunk_id는 UUID 형식이어야 합니다.") from None

    def model_post_init(self, context: object, /) -> None:
        """서로 다른 최초 검색 경로 힌트의 중복을 금지한다."""

        del context
        if self.source_file_name is not None and self.chunk_id is not None:
            raise ValueError("원본 파일명과 chunk_id를 동시에 지정할 수 없습니다.")


class SearchPlan(_SearchSchema):
    """Search Router가 한 번 결정하는 bounded 최초 검색 계획."""

    route: SearchRoute
    query: _NonEmptyString | None = None
    mode: SearchMode | None = None
    source_file_name: _NonEmptyString | None = None
    chunk_id: _NonEmptyString | None = None
    document_types: frozenset[DocumentType] = Field(min_length=1)
    candidate_limit: int = Field(ge=1, le=100, strict=True)
    expand_neighbors: bool = Field(default=False, strict=True)
    neighbor_before: int = Field(ge=0, le=99, strict=True)
    neighbor_after: int = Field(ge=0, le=99, strict=True)

    @field_validator("chunk_id")
    @classmethod
    def validate_chunk_id(cls, value: str | None) -> str | None:
        """계획의 청크 ID도 정규화된 UUID로 제한한다."""

        if value is None:
            return None
        try:
            return str(UUID(value))
        except ValueError:
            raise ValueError("chunk_id는 UUID 형식이어야 합니다.") from None

    def model_post_init(self, context: object, /) -> None:
        """Route별로 필요한 필드와 금지 필드를 검증한다."""

        del context
        if self.neighbor_before + self.neighbor_after + 1 > 100:
            raise ValueError("인접 청크 조회 수는 기준 청크를 포함해 100개 이하여야 합니다.")
        if self.route == "global":
            if self.query is None or self.mode is None:
                raise ValueError("전체 문서 검색에는 query와 mode가 필요합니다.")
            if self.source_file_name is not None or self.chunk_id is not None:
                raise ValueError("전체 문서 검색에는 문서명이나 chunk_id를 지정할 수 없습니다.")
            return
        if self.route == "within_document":
            if self.query is None or self.mode is None or self.source_file_name is None:
                raise ValueError("문서 범위 검색에는 query, mode와 원본 파일명이 필요합니다.")
            if self.chunk_id is not None:
                raise ValueError("문서 범위 검색에는 chunk_id를 지정할 수 없습니다.")
            return
        if self.chunk_id is None:
            raise ValueError("청크 직접 조회에는 chunk_id가 필요합니다.")
        if self.query is not None or self.mode is not None or self.source_file_name is not None:
            raise ValueError("청크 직접 조회에는 검색문, 모드와 문서명을 지정할 수 없습니다.")


class SearchChunkPayload(_SearchSchema):
    """Python이 검증해 Domain Agent에 전달하는 원문 청크."""

    chunk_id: _NonEmptyString
    source_file_name: _NonEmptyString
    document_type: DocumentType
    chunk_index: int = Field(ge=0, strict=True)
    title: _NonEmptyString
    locator: _NonEmptyString
    content: _NonEmptyString

    @field_validator("chunk_id")
    @classmethod
    def validate_chunk_id(cls, value: str) -> str:
        """청크 ID를 정규화된 UUID 문자열로 제한한다."""

        try:
            return str(UUID(value))
        except ValueError:
            raise ValueError("chunk_id는 UUID 형식이어야 합니다.") from None


class SearchResult(_SearchSchema):
    """Search Service가 Domain Agent에 전달하는 검증된 원문 검색 결과."""

    execution_status: ExecutionStatus
    retrieved_chunks: list[SearchChunkPayload] = Field(default_factory=list)
    limitations: list[_NonEmptyString] = Field(default_factory=list)
    error: _NonEmptyString | None = None

    def model_post_init(self, context: object, /) -> None:
        """실행 상태, 원문 청크와 정제 오류의 조합을 검증한다."""

        del context
        chunk_ids = [chunk.chunk_id for chunk in self.retrieved_chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("검색 결과 청크는 중복될 수 없습니다.")
        if self.execution_status == "completed":
            if self.error is not None:
                raise ValueError("완료된 검색에는 error를 포함할 수 없습니다.")
            return
        if self.retrieved_chunks:
            raise ValueError("실패하거나 시간 초과된 검색에는 청크를 포함할 수 없습니다.")
        if self.error is None:
            raise ValueError("실패하거나 시간 초과된 검색에는 정제된 error가 필요합니다.")
