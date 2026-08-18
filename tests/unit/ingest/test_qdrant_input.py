"""통합 JSONL에서 Qdrant payload로 가는 입력 계약을 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from pension_agent.ingest.qdrant_input import IndexInputError, load_corpus


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _source(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "source_id": "guide-source",
        "source_path": "knowledge/연금 가이드.pdf",
        "source_sha256": "a" * 64,
        "canonical_doc_id": "knowledge-abc",
        "doc_type": "pdf",
        "parser_profile": "easyocr-v1",
        "processing_mode": "vector",
        "notes": "",
    }
    row.update(overrides)
    return row


def _chunk(text: str = "퇴직연금의 근거 본문입니다.", **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "chunk_id": "knowledge-abc-0000",
        "canonical_doc_id": "knowledge-abc",
        "doc_type": "pdf",
        "text": text,
        "section_path": ["제2장", "가입 절차"],
        "page_start": 2,
        "page_end": 3,
        "metadata": {
            "block_type": "text",
            "ocr_profile": "easyocr-v1",
            "source_ids": ["guide-source"],
        },
        "content_hash": hashlib.sha256(text.encode()).hexdigest(),
    }
    row.update(overrides)
    return row


def _load(tmp_path: Path, chunks: list[dict[str, object]], sources: list[dict[str, object]]):
    chunks_path = tmp_path / "chunks.jsonl"
    sources_path = tmp_path / "sources.jsonl"
    _write_jsonl(chunks_path, chunks)
    _write_jsonl(sources_path, sources)
    return load_corpus(chunks_path, [sources_path])


def test_load_corpus_builds_stable_point_and_retrieval_payload(tmp_path: Path) -> None:
    corpus = _load(tmp_path, [_chunk()], [_source()])

    assert corpus.source_count == 1
    assert corpus.canonical_document_count == 1
    prepared = corpus.chunks[0]
    assert prepared.point_id == str(uuid5(NAMESPACE_URL, "urn:ace3:chunk:knowledge-abc-0000"))
    assert prepared.embedding_content == "제2장\n가입 절차\n퇴직연금의 근거 본문입니다."
    assert prepared.payload == {
        "source_file_name": "연금 가이드.pdf",
        "source_format": "pdf",
        "document_type": "pension_reference",
        "chunk_index": 0,
        "content": "퇴직연금의 근거 본문입니다.",
        "embedding_content": "제2장\n가입 절차\n퇴직연금의 근거 본문입니다.",
        "heading_path": ["제2장", "가입 절차"],
        "captions": [],
        "element_types": ["text"],
        "page_numbers": [2, 3],
    }


def test_load_corpus_rejects_tampered_content(tmp_path: Path) -> None:
    row = _chunk()
    row["content_hash"] = "0" * 64

    with pytest.raises(IndexInputError, match="content_hash"):
        _load(tmp_path, [row], [_source()])


def test_load_corpus_rejects_missing_source_reference(tmp_path: Path) -> None:
    row = _chunk()
    row["metadata"] = {
        "block_type": "text",
        "ocr_profile": "easyocr-v1",
        "source_ids": ["missing-source"],
    }

    with pytest.raises(IndexInputError, match="manifest 참조"):
        _load(tmp_path, [row], [_source()])


def test_load_corpus_requires_contiguous_chunk_indexes(tmp_path: Path) -> None:
    row = _chunk(chunk_id="knowledge-abc-0001")

    with pytest.raises(IndexInputError, match="0부터 연속"):
        _load(tmp_path, [row], [_source()])
