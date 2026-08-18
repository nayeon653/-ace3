"""NormalizedDocument -> Chunk. 문서유형별 정책은 여기 한 곳에 모은다.

정책:
- faq block(예: doc29 FAQ 시트): 행 하나 = chunk 하나("1 Q&A = 1 chunk").
  문서에 faq block이 하나라도 있으면 그 문서의 vector chunk는 faq 행만 생성한다.
  같은 문서의 text/table block(예: doc29의 README/Sources 시트)은 FAQ 답변의
  중복이거나 부가 설명이라 별도 vector chunk로 만들지 않는다.
  각 FAQ 행의 "근거ID" 컬럼 값을 Sources류 표(첫 컬럼이 SourceID인 표)에서 찾아
  그 행이 인용하는 source만 metadata["sources"]에 담는다.
  README/Sources 전체를 모든 chunk에 복제하지 않는다.

- 그 외 문서: heading 경계로 섹션을 나누고, 섹션이 너무 길 때만 block 경계에서
  하위 분할한다.
  block(=원본 문단/list_item 하나) 내부는 절대 자르지 않는다.
  숫자·조건·예외 나열이 한 block 안에 있으면 그 block은 항상 통째로 하나의
  chunk에 들어간다.

- table block(faq 아닌 일반 표): section_path를 text 앞에 붙인 독립 chunk로 만든다.

- heading의 계층(level)은 NormalizedBlock.level을 그대로 신뢰한다.
  투자설명서의 "제N부 → N. 항목 → 가/나/다" 3단 계층 복원,
  표지/목차 재인용 배제, marker/orig 기반 숨은 heading 복원,
  합쳐진 노드 분리 등은 pension_agent.ingest.normalize 단계에서 끝낸다.
  chunker는 Docling label/marker/orig를 알지 않고 text를 다시 정규식으로
  재해석하지 않는다.

- doc55는 page 정보가 없을 수 있으므로 section_path가 위치 식별자 역할을 한다.

- doc34는 deterministic lookup 대상이므로 vector chunk를 생성하지 않는다.

- doc7은 normalize 단계에서 전용 noise filtering을 거친 뒤 일반 chunking 경로를 사용한다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pension_agent.core.documents import NormalizedBlock, NormalizedDocument

_MAX_SECTION_CHARS = 800
_EXCLUDED_DOC_IDS = {"doc34"}
_SOURCE_ID_COLUMN = "근거ID"
_SOURCE_TABLE_FIRST_COLUMN = "SourceID"


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    doc_type: str
    text: str
    section_path: list[str]
    page_start: int | None
    page_end: int | None
    metadata: dict
    content_hash: str


def chunk_document(doc: NormalizedDocument) -> list[Chunk]:
    if doc.doc_id in _EXCLUDED_DOC_IDS:
        return []

    has_faq = any(block.type == "faq" for block in doc.blocks)
    faq_only = doc.doc_id == "doc29"
    source_lookup = _build_source_lookup(doc.blocks) if has_faq else {}

    chunks: list[Chunk] = []
    heading_stack: list[tuple[int, str]] = []
    buffer: list[NormalizedBlock] = []

    def section_path() -> list[str]:
        return [text for _level, text in heading_stack]

    def flush_buffer() -> None:
        if not buffer:
            return

        path = section_path()

        for piece in _split_by_block_boundary(buffer, _MAX_SECTION_CHARS):
            _emit_text_chunk(chunks, doc, path, piece)

        buffer.clear()

    for block in doc.blocks:
        if block.type == "heading":
            text = (block.text or "").strip()

            if not text:
                continue

            level = block.level or 1

            flush_buffer()

            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()

            heading_stack.append((level, text))

        elif block.type == "text":
            if faq_only:
                continue

            text = (block.text or "").strip()

            if not text:
                continue

            buffer.append(block)

        elif block.type == "faq":
            flush_buffer()
            _emit_faq_chunks(
                chunks,
                doc,
                section_path(),
                block,
                source_lookup,
            )

        elif block.type == "table":
            if faq_only:
                continue

            flush_buffer()
            _emit_table_chunk(
                chunks,
                doc,
                section_path(),
                block,
            )

    flush_buffer()

    return chunks


def _split_by_block_boundary(
    blocks: list[NormalizedBlock],
    max_chars: int,
) -> list[list[NormalizedBlock]]:
    """block 경계에서만 나눈다. block 텍스트 내부는 자르지 않는다."""

    pieces: list[list[NormalizedBlock]] = []
    current: list[NormalizedBlock] = []
    current_len = 0

    for block in blocks:
        text_len = len(block.text or "")

        if current and current_len + text_len > max_chars:
            pieces.append(current)
            current = []
            current_len = 0

        current.append(block)
        current_len += text_len

    if current:
        pieces.append(current)

    return pieces


def _build_chunk(
    doc: NormalizedDocument,
    index: int,
    path: list[str],
    text: str,
    pages: list[int],
    block_type: str,
    extra_metadata: dict | None = None,
) -> Chunk:
    metadata = {
        "block_type": block_type,
        "ocr_profile": doc.metadata.get("ocr_profile"),
    }

    if extra_metadata:
        metadata.update(extra_metadata)

    return Chunk(
        chunk_id=f"{doc.doc_id}-{index:04d}",
        doc_id=doc.doc_id,
        doc_type=doc.doc_type,
        text=text,
        section_path=path,
        page_start=min(pages) if pages else None,
        page_end=max(pages) if pages else None,
        metadata=metadata,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _emit_text_chunk(
    chunks: list[Chunk],
    doc: NormalizedDocument,
    path: list[str],
    blocks: list[NormalizedBlock],
) -> None:
    text = "\n".join((block.text or "").strip() for block in blocks).strip()

    if not text:
        return

    pages = [block.page for block in blocks if block.page is not None]

    chunks.append(
        _build_chunk(
            doc,
            len(chunks),
            path,
            text,
            pages,
            block_type="text",
        )
    )


def _render_table(
    path: list[str],
    rows: list[list[str]],
) -> str:
    lines = [" > ".join(path)] if path else []

    lines.extend(" | ".join(cell for cell in row) for row in rows)

    return "\n".join(lines).strip()


def _emit_table_chunk(
    chunks: list[Chunk],
    doc: NormalizedDocument,
    path: list[str],
    block: NormalizedBlock,
) -> None:
    rows = block.table_data or []

    if not rows:
        return

    text = _render_table(path, rows)

    if not text:
        return

    pages = [block.page] if block.page is not None else []

    chunks.append(
        _build_chunk(
            doc,
            len(chunks),
            path,
            text,
            pages,
            block_type="table",
        )
    )


def _build_source_lookup(
    blocks: list[NormalizedBlock],
) -> dict[str, dict[str, str]]:
    """근거ID(SourceID) -> {컬럼명: 값} 매핑을 만든다."""

    for block in blocks:
        if block.type != "table" or not block.table_data:
            continue

        header, *rows = block.table_data

        if not header or header[0] != _SOURCE_TABLE_FIRST_COLUMN:
            continue

        return {row[0]: dict(zip(header[1:], row[1:])) for row in rows if row}

    return {}


def _emit_faq_chunks(
    chunks: list[Chunk],
    doc: NormalizedDocument,
    path: list[str],
    block: NormalizedBlock,
    source_lookup: dict[str, dict[str, str]],
) -> None:
    rows = block.table_data or []

    if len(rows) < 2:
        return

    headers = rows[0]
    entries = rows[1:]

    pages = [block.page] if block.page is not None else []

    source_col = headers.index(_SOURCE_ID_COLUMN) if _SOURCE_ID_COLUMN in headers else None

    for row in entries:
        fields = [f"{header}: {value}" for header, value in zip(headers, row) if value.strip()]

        if not fields:
            continue

        text_parts = [" > ".join(path)] if path else []
        text_parts.extend(fields)

        text = "\n".join(text_parts).strip()

        if not text:
            continue

        extra_metadata = None

        if source_col is not None and source_col < len(row):
            ids = [
                source_id.strip() for source_id in row[source_col].split(",") if source_id.strip()
            ]

            sources = {
                source_id: source_lookup[source_id]
                for source_id in ids
                if source_id in source_lookup
            }

            if sources:
                extra_metadata = {"sources": sources}

        chunks.append(
            _build_chunk(
                doc,
                len(chunks),
                path,
                text,
                pages,
                block_type="faq",
                extra_metadata=extra_metadata,
            )
        )
