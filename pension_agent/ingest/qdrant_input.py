"""통합 청크 JSONL을 Qdrant 저장 계약으로 변환한다."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from pension_agent.core import DocumentType, ElementType

_NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
_SourceFormat = Literal["pdf", "docx", "pptx", "xlsx"]


class IndexInputError(ValueError):
    """청크나 source manifest가 적재 입력 계약을 위반한 경우."""


class SourceManifestRow(BaseModel):
    """원본 하나와 canonical 문서의 대응."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_id: _NonEmptyString
    source_path: _NonEmptyString
    source_sha256: _Sha256
    canonical_doc_id: _NonEmptyString
    doc_type: _SourceFormat
    parser_profile: str | None
    processing_mode: Literal["vector", "deterministic"]
    notes: str


class UnifiedChunkMetadata(BaseModel):
    """통합 청크 생성기가 보존한 최소 metadata."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    block_type: Literal["text", "table", "faq"]
    ocr_profile: _NonEmptyString
    source_ids: list[_NonEmptyString] = Field(min_length=1)
    sources: dict[str, dict[str, str]] | None = None


class UnifiedChunkRow(BaseModel):
    """Drive의 chunks33.jsonl 한 행."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chunk_id: _NonEmptyString
    canonical_doc_id: _NonEmptyString
    doc_type: _SourceFormat
    text: _NonEmptyString
    section_path: list[_NonEmptyString]
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    metadata: UnifiedChunkMetadata
    content_hash: _Sha256


@dataclass(frozen=True)
class PreparedChunk:
    """임베딩과 Qdrant upsert에 필요한 검증 완료 청크."""

    source_chunk_id: str
    point_id: str
    canonical_doc_id: str
    embedding_content: str
    embedding_content_hash: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class CorpusInput:
    """전체 입력 검증 결과."""

    chunks: tuple[PreparedChunk, ...]
    source_count: int
    canonical_document_count: int


def load_corpus(
    chunks_path: Path,
    source_manifest_paths: list[Path],
) -> CorpusInput:
    """manifest와 청크 전체의 참조·해시·순서 계약을 검증한다."""

    sources = _load_sources(source_manifest_paths)
    prepared: list[PreparedChunk] = []
    seen_chunk_ids: set[str] = set()
    indexes_by_document: dict[str, list[int]] = defaultdict(list)

    for line_number, chunk in _read_models(chunks_path, UnifiedChunkRow):
        if chunk.chunk_id in seen_chunk_ids:
            raise IndexInputError(f"{chunks_path}:{line_number}: chunk_id가 중복되었습니다.")
        seen_chunk_ids.add(chunk.chunk_id)

        content_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
        if content_hash != chunk.content_hash:
            raise IndexInputError(
                f"{chunks_path}:{line_number}: content_hash가 본문과 일치하지 않습니다."
            )

        chunk_index = _chunk_index(chunk, chunks_path, line_number)
        indexes_by_document[chunk.canonical_doc_id].append(chunk_index)
        prepared.append(
            _prepare_chunk(
                chunk,
                chunk_index=chunk_index,
                sources=sources,
                path=chunks_path,
                line_number=line_number,
            )
        )

    if not prepared:
        raise IndexInputError(f"{chunks_path}: 적재할 청크가 없습니다.")

    for canonical_doc_id, indexes in indexes_by_document.items():
        if sorted(indexes) != list(range(len(indexes))):
            raise IndexInputError(f"{canonical_doc_id}: chunk_index가 0부터 연속적이지 않습니다.")

    expected_documents = {
        source.canonical_doc_id for source in sources.values() if source.processing_mode == "vector"
    }
    actual_documents = set(indexes_by_document)
    if actual_documents != expected_documents:
        raise IndexInputError(
            "vector source manifest와 청크의 canonical 문서 집합이 일치하지 않습니다."
        )

    return CorpusInput(
        chunks=tuple(prepared),
        source_count=len(sources),
        canonical_document_count=len(actual_documents),
    )


def _load_sources(paths: list[Path]) -> dict[str, SourceManifestRow]:
    if not paths:
        raise IndexInputError("source manifest 경로가 필요합니다.")

    sources: dict[str, SourceManifestRow] = {}
    for path in paths:
        for line_number, source in _read_models(path, SourceManifestRow):
            if source.source_id in sources:
                raise IndexInputError(f"{path}:{line_number}: source_id가 중복되었습니다.")
            sources[source.source_id] = source
    return sources


def _read_models[ModelT: BaseModel](
    path: Path,
    model_type: type[ModelT],
) -> list[tuple[int, ModelT]]:
    if not path.is_file():
        raise IndexInputError(f"입력 파일을 찾을 수 없습니다: {path}")

    rows: list[tuple[int, ModelT]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                raw = json.loads(line)
                rows.append((line_number, model_type.model_validate(raw)))
            except (json.JSONDecodeError, ValidationError):
                raise IndexInputError(
                    f"{path}:{line_number}: JSONL 행이 입력 계약을 위반했습니다."
                ) from None
    return rows


def _chunk_index(chunk: UnifiedChunkRow, path: Path, line_number: int) -> int:
    prefix = f"{chunk.canonical_doc_id}-"
    if not chunk.chunk_id.startswith(prefix):
        raise IndexInputError(
            f"{path}:{line_number}: chunk_id와 canonical_doc_id가 일치하지 않습니다."
        )
    suffix = chunk.chunk_id.removeprefix(prefix)
    if len(suffix) != 4 or not suffix.isdigit():
        raise IndexInputError(f"{path}:{line_number}: chunk_id 순번이 4자리 숫자가 아닙니다.")
    return int(suffix)


def _prepare_chunk(
    chunk: UnifiedChunkRow,
    *,
    chunk_index: int,
    sources: dict[str, SourceManifestRow],
    path: Path,
    line_number: int,
) -> PreparedChunk:
    resolved_sources: list[SourceManifestRow] = []
    for source_id in chunk.metadata.source_ids:
        source = sources.get(source_id)
        if source is None or source.processing_mode != "vector":
            raise IndexInputError(
                f"{path}:{line_number}: vector source manifest 참조가 올바르지 않습니다."
            )
        if source.canonical_doc_id != chunk.canonical_doc_id:
            raise IndexInputError(
                f"{path}:{line_number}: source와 canonical 문서가 일치하지 않습니다."
            )
        if source.doc_type != chunk.doc_type:
            raise IndexInputError(
                f"{path}:{line_number}: source와 청크의 파일 형식이 일치하지 않습니다."
            )
        resolved_sources.append(source)

    primary_source = resolved_sources[0]
    source_file_name = PurePosixPath(primary_source.source_path).name
    if not source_file_name:
        raise IndexInputError(f"{path}:{line_number}: source_file_name을 만들 수 없습니다.")

    document_type = _document_type(chunk.canonical_doc_id, path, line_number)
    page_numbers = _page_numbers(chunk, path, line_number)
    embedding_content = _embedding_content(chunk.section_path, chunk.text)
    point_id = str(uuid5(NAMESPACE_URL, f"urn:ace3:chunk:{chunk.chunk_id}"))

    payload: dict[str, Any] = {
        "source_file_name": source_file_name,
        "source_format": chunk.doc_type,
        "document_type": document_type.value,
        "chunk_index": chunk_index,
        "content": chunk.text,
        "embedding_content": embedding_content,
        "heading_path": chunk.section_path,
        "captions": [],
        "element_types": [_element_type(chunk.metadata.block_type).value],
        "page_numbers": page_numbers,
    }
    return PreparedChunk(
        source_chunk_id=chunk.chunk_id,
        point_id=point_id,
        canonical_doc_id=chunk.canonical_doc_id,
        embedding_content=embedding_content,
        embedding_content_hash=hashlib.sha256(embedding_content.encode("utf-8")).hexdigest(),
        payload=payload,
    )


def _document_type(
    canonical_doc_id: str,
    path: Path,
    line_number: int,
) -> DocumentType:
    if canonical_doc_id.startswith("prospectus-"):
        return DocumentType.FUND_PROSPECTUS
    if canonical_doc_id.startswith("knowledge-"):
        return DocumentType.PENSION_REFERENCE
    raise IndexInputError(f"{path}:{line_number}: canonical 문서 분류를 결정할 수 없습니다.")


def _page_numbers(chunk: UnifiedChunkRow, path: Path, line_number: int) -> list[int]:
    if chunk.page_start is None and chunk.page_end is None:
        return []
    if chunk.page_start is None or chunk.page_end is None:
        raise IndexInputError(f"{path}:{line_number}: page_start와 page_end는 함께 있어야 합니다.")
    if chunk.page_start > chunk.page_end:
        raise IndexInputError(f"{path}:{line_number}: 페이지 범위가 역순입니다.")
    return list(range(chunk.page_start, chunk.page_end + 1))


def _embedding_content(section_path: list[str], text: str) -> str:
    if not section_path:
        return text
    newline_prefix = "\n".join(section_path)
    breadcrumb_prefix = " > ".join(section_path)
    if text.startswith((newline_prefix, breadcrumb_prefix)):
        return text
    return f"{newline_prefix}\n{text}"


def _element_type(block_type: str) -> ElementType:
    if block_type == "text":
        return ElementType.TEXT
    if block_type in {"table", "faq"}:
        return ElementType.TABLE
    return ElementType.UNKNOWN
