"""Agent와 retrieval 구현이 공유하는 검색 계약."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from numbers import Real


class DocumentType(StrEnum):
    """Qdrant에 저장하는 제공 문서 분류."""

    FUND_PROSPECTUS = "fund_prospectus"
    PENSION_REFERENCE = "pension_reference"


class ElementType(StrEnum):
    """청크를 구성한 원문 요소 분류."""

    TITLE = "title"
    SECTION_HEADER = "section_header"
    TEXT = "text"
    LIST_ITEM = "list_item"
    TABLE = "table"
    PICTURE = "picture"
    CAPTION = "caption"
    FORMULA = "formula"
    CODE = "code"
    UNKNOWN = "unknown"


class SearchMode(StrEnum):
    """Qdrant named vector를 사용하는 후보 검색 방식."""

    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class SearchQuery:
    """검색문과 이미 계산된 dense embedding을 함께 전달하는 Query Object."""

    text: str
    dense: tuple[float, ...] | None = None
    mode: SearchMode = SearchMode.HYBRID

    def __post_init__(self) -> None:
        text = self.text.strip()
        if not text:
            raise ValueError("검색문은 비어 있을 수 없습니다.")
        object.__setattr__(self, "text", text)

        if self.mode in {SearchMode.DENSE, SearchMode.HYBRID} and not self.dense:
            raise ValueError(f"{self.mode.value} 검색에는 dense vector가 필요합니다.")
        if self.dense is not None:
            if any(isinstance(value, bool) or not isinstance(value, Real) for value in self.dense):
                raise TypeError("dense vector에는 숫자만 포함할 수 있습니다.")
            dense = tuple(float(value) for value in self.dense)
            if not all(isfinite(value) for value in dense):
                raise ValueError("dense vector에는 유한한 숫자만 포함할 수 있습니다.")
            object.__setattr__(self, "dense", dense)


@dataclass(frozen=True)
class SearchFilters:
    """현재 payload index로 지원하는 메타데이터 필터."""

    source_file_name: str | None = None
    document_type: DocumentType | None = None

    def __post_init__(self) -> None:
        if self.source_file_name is None:
            return
        source_file_name = self.source_file_name.strip()
        if not source_file_name:
            raise ValueError("원본 파일명 필터는 비어 있을 수 없습니다.")
        object.__setattr__(self, "source_file_name", source_file_name)


@dataclass(frozen=True)
class RetrievedChunk:
    """Qdrant SDK 타입을 제거한 검증된 청크."""

    chunk_id: str
    source_file_name: str
    source_format: str
    document_type: DocumentType
    chunk_index: int
    content: str
    heading_path: tuple[str, ...]
    captions: tuple[str, ...]
    element_types: tuple[ElementType, ...]
    page_numbers: tuple[int, ...]
    title: str
    locator: str


@dataclass(frozen=True)
class SearchHit:
    """검색 점수와 검증된 청크의 조합."""

    chunk: RetrievedChunk
    score: float


@dataclass(frozen=True)
class NeighborRequest:
    """같은 문서에서 기준 청크의 앞뒤 문맥을 요청한다."""

    source_file_name: str
    chunk_index: int
    before: int = 1
    after: int = 1

    def __post_init__(self) -> None:
        source_file_name = self.source_file_name.strip()
        if not source_file_name:
            raise ValueError("원본 파일명은 비어 있을 수 없습니다.")
        if self.chunk_index < 0:
            raise ValueError("chunk_index는 0 이상이어야 합니다.")
        if self.before < 0 or self.after < 0:
            raise ValueError("인접 청크 범위는 0 이상이어야 합니다.")
        object.__setattr__(self, "source_file_name", source_file_name)


class RetrievalError(RuntimeError):
    """검색 경계에서 발생한 정제된 오류."""


class RetrievalDataError(RetrievalError):
    """Qdrant point나 payload가 저장 계약을 위반한 경우."""


class RetrievalBackendError(RetrievalError):
    """Qdrant 요청 자체가 실패한 경우."""
