"""Search Agent의 Tool 응답, 근거 선택과 최종 결과 계약."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from pension_agent.agent.contracts import ExecutionStatus
from pension_agent.core import DocumentType

SearchCoverage = Literal["sufficient", "partial", "none"]

_NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]
_MAX_SELECTED_CHUNKS = 100


class _SearchSchema(BaseModel):
    """Search Agent 내부 경계에서 사용하는 공통 검증 설정."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class SearchChunkPayload(_SearchSchema):
    """검색 Tool이 HCX에 공개하는 검증된 청크."""

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


class SearchHitPayload(_SearchSchema):
    """검색 점수와 해당 청크를 함께 전달하는 Tool 응답 항목."""

    score: float
    chunk: SearchChunkPayload


class SearchHitsPayload(_SearchSchema):
    """전체 또는 문서 범위 검색 Tool의 성공 응답."""

    hits: list[SearchHitPayload]


class NeighborChunksPayload(_SearchSchema):
    """인접 청크 조회 Tool의 성공 응답."""

    chunks: list[SearchChunkPayload]


class GetChunkPayload(_SearchSchema):
    """청크 ID 단건 조회 Tool의 성공 응답."""

    chunk: SearchChunkPayload | None


class SearchToolErrorPayload(_SearchSchema):
    """검색 Tool이 HCX에 공개하는 정제된 오류 응답."""

    error: _NonEmptyString


class SearchSelection(_SearchSchema):
    """HCX가 terminal Tool로 제출하는 검색 근거 선택."""

    coverage: SearchCoverage
    selected_chunk_ids: list[_NonEmptyString] = Field(max_length=_MAX_SELECTED_CHUNKS)
    limitations: list[_NonEmptyString] = Field(default_factory=list)

    @field_validator("selected_chunk_ids")
    @classmethod
    def validate_selected_chunk_ids(cls, values: list[str]) -> list[str]:
        """선택한 청크 ID를 UUID로 정규화하고 중복을 금지한다."""

        normalized: list[str] = []
        for value in values:
            try:
                normalized.append(str(UUID(value)))
            except ValueError:
                raise ValueError("선택한 chunk_id는 UUID 형식이어야 합니다.") from None
        if len(normalized) != len(set(normalized)):
            raise ValueError("선택한 chunk_id는 중복될 수 없습니다.")
        return normalized

    def model_post_init(self, context: object, /) -> None:
        """근거 충족도와 선택 ID의 조합을 검증한다."""

        del context
        if self.coverage == "none" and self.selected_chunk_ids:
            raise ValueError("근거가 없으면 chunk_id를 선택할 수 없습니다.")
        if self.coverage != "none" and not self.selected_chunk_ids:
            raise ValueError("근거가 있으면 최소 하나의 chunk_id가 필요합니다.")


class SearchResult(_SearchSchema):
    """Python이 검증한 뒤 Domain Agent에 전달하는 검색 결과."""

    execution_status: ExecutionStatus
    coverage: SearchCoverage | None = None
    selected_chunks: list[SearchChunkPayload] = Field(default_factory=list)
    limitations: list[_NonEmptyString] = Field(default_factory=list)
    error: _NonEmptyString | None = None

    def model_post_init(self, context: object, /) -> None:
        """실행 상태, 근거 충족도와 선택 청크의 조합을 검증한다."""

        del context
        if len(self.selected_chunks) != len({chunk.chunk_id for chunk in self.selected_chunks}):
            raise ValueError("선택한 청크는 중복될 수 없습니다.")

        if self.execution_status == "completed":
            self._validate_completed()
            return
        if self.coverage is not None:
            raise ValueError("실패하거나 시간 초과된 검색에는 coverage를 포함할 수 없습니다.")
        if self.selected_chunks:
            raise ValueError("실패하거나 시간 초과된 검색에는 청크를 포함할 수 없습니다.")
        if self.error is None:
            raise ValueError("실패하거나 시간 초과된 검색에는 정제된 error가 필요합니다.")

    def _validate_completed(self) -> Self:
        if self.coverage is None:
            raise ValueError("완료된 검색에는 coverage가 필요합니다.")
        if self.error is not None:
            raise ValueError("완료된 검색에는 error를 포함할 수 없습니다.")
        if self.coverage == "none" and self.selected_chunks:
            raise ValueError("근거가 없는 검색에는 선택 청크를 포함할 수 없습니다.")
        if self.coverage != "none" and not self.selected_chunks:
            raise ValueError("근거가 있는 검색에는 최소 하나의 선택 청크가 필요합니다.")
        return self
