"""Knowledge Docs 58개 canonical corpus export."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pension_agent.ingest.normalize import normalize_document
from pension_agent.retrieval.chunker import chunk_document

REPO_ROOT = Path(__file__).resolve().parents[2]

SOURCE_ROOT = REPO_ROOT / "data" / "raw" / "knowledge_docs"
PROCESSED_ROOT = REPO_ROOT / "data" / "processed" / "docling"

INDEX_ROOT = REPO_ROOT / "data" / "indexes" / "knowledge_docs"
SOURCE_MANIFEST_PATH = INDEX_ROOT / "source_manifest.jsonl"
CHUNKS_PATH = INDEX_ROOT / "chunks.jsonl"

CANONICAL_PREFIX = "knowledge"

NAVER_DOC_IDS = {
    "doc1",
    "doc2",
    "doc3",
    "doc4",
    "doc5",
    "doc8",
    "doc9",
    "doc21",
    "doc22",
    "doc27",
    "doc31",
    "doc32",
    "doc37",
    "doc54",
    "doc56",
    "doc58",
}

MANUAL_DOC_IDS = {
    "doc24",
    "doc28",
    "doc30",
}

DETERMINISTIC_DOC_IDS = {
    "doc34",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def canonical_doc_id(source_sha256: str) -> str:
    return f"{CANONICAL_PREFIX}-{source_sha256[:12]}"


def _raw_sources() -> dict[str, Path]:
    """doc1~doc58 raw source를 source_id 기준으로 찾는다."""

    sources: dict[str, Path] = {}

    for path in sorted(SOURCE_ROOT.rglob("*")):
        if not path.is_file():
            continue

        doc_id = path.stem

        if not doc_id.startswith("doc"):
            continue

        if doc_id in sources:
            raise ValueError(f"duplicate raw source_id: {doc_id}")

        sources[doc_id] = path

    return sources


def _find_bundle(doc_id: str) -> Path:
    """현재 확정된 정책대로 doc_id의 canonical 입력 bundle을 선택한다."""

    if doc_id in MANUAL_DOC_IDS:
        bundle = PROCESSED_ROOT / "knowledge_docs_manual" / doc_id

        if not (bundle / "manifest.json").exists():
            raise FileNotFoundError(f"manual bundle not found: {bundle}")

        return bundle

    candidates = [
        manifest.parent
        for manifest in PROCESSED_ROOT.rglob("manifest.json")
        if manifest.parent.name.startswith(f"{doc_id}--")
        and "prospectus" not in manifest.parts
        and "knowledge_docs_manual" not in manifest.parts
    ]

    if doc_id in NAVER_DOC_IDS:
        candidates = [path for path in candidates if "docling-naver-ocr-v1" in path.name]

    else:
        candidates = [path for path in candidates if "docling-local-ocr-v1" in path.name]

    if len(candidates) != 1:
        raise ValueError(f"{doc_id}: expected exactly one accepted bundle, got {candidates}")

    return candidates[0]


def _parser_profile(doc_id: str) -> str:
    if doc_id in MANUAL_DOC_IDS:
        return "manual"

    if doc_id in NAVER_DOC_IDS:
        return "docling-naver-ocr-v1"

    return "docling-local-ocr-v1"


def build_source_manifest() -> list[dict[str, Any]]:
    sources = _raw_sources()

    expected_ids = {f"doc{i}" for i in range(1, 59)}

    if set(sources) != expected_ids:
        missing = sorted(expected_ids - set(sources))
        extra = sorted(set(sources) - expected_ids)

        raise ValueError(f"raw source reconciliation failed: missing={missing}, extra={extra}")

    rows: list[dict[str, Any]] = []

    for doc_id in sorted(
        sources,
        key=lambda value: int(value.removeprefix("doc")),
    ):
        source_path = sources[doc_id]
        sha = sha256_file(source_path)

        try:
            relative_path = source_path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            relative_path = source_path.as_posix()

        processing_mode = "deterministic" if doc_id in DETERMINISTIC_DOC_IDS else "vector"

        notes = ""

        if doc_id == "doc7":
            notes = "local OCR bundle + doc7-specific noise normalization"
        elif doc_id in MANUAL_DOC_IDS:
            notes = "manual normalization after repeated NAVER OCR failure"

        rows.append(
            {
                "source_id": doc_id,
                "source_path": relative_path,
                "source_sha256": sha,
                "canonical_doc_id": canonical_doc_id(sha),
                "doc_type": source_path.suffix.lstrip(".").lower(),
                "parser_profile": _parser_profile(doc_id),
                "processing_mode": processing_mode,
                "notes": notes,
            }
        )

    return rows


def _canonical_chunk_row(
    chunk,
    cdoc_id: str,
    index: int,
) -> dict[str, Any]:
    return {
        "chunk_id": f"{cdoc_id}-{index:04d}",
        "canonical_doc_id": cdoc_id,
        "doc_type": chunk.doc_type,
        "text": chunk.text,
        "section_path": chunk.section_path,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "metadata": chunk.metadata,
        "content_hash": chunk.content_hash,
    }


def export_canonical_chunks(
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for source_row in source_rows:
        doc_id = source_row["source_id"]

        if source_row["processing_mode"] != "vector":
            continue

        bundle_dir = _find_bundle(doc_id)

        doc = normalize_document(bundle_dir)
        chunks = chunk_document(doc)

        if not chunks:
            raise ValueError(f"{doc_id}: vector document produced 0 chunks")

        cdoc_id = source_row["canonical_doc_id"]

        for index, chunk in enumerate(chunks):
            rows.append(
                _canonical_chunk_row(
                    chunk,
                    cdoc_id,
                    index,
                )
            )

    return rows


def write_jsonl(
    rows: list[dict[str, Any]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False))
            file.write("\n")


def main() -> None:
    source_rows = build_source_manifest()

    if len(source_rows) != 58:
        raise ValueError(f"expected 58 source rows, got {len(source_rows)}")

    if len({row["source_sha256"] for row in source_rows}) != 58:
        raise ValueError("unexpected duplicate source_sha256")

    write_jsonl(
        source_rows,
        SOURCE_MANIFEST_PATH,
    )

    chunk_rows = export_canonical_chunks(source_rows)

    if len(chunk_rows) != 782:
        raise ValueError(f"expected 782 chunks, got {len(chunk_rows)}")

    if len({row["chunk_id"] for row in chunk_rows}) != len(chunk_rows):
        raise ValueError("duplicate canonical chunk_id")

    if any(not row["text"].strip() for row in chunk_rows):
        raise ValueError("empty canonical chunk")

    write_jsonl(
        chunk_rows,
        CHUNKS_PATH,
    )

    vector_sources = sum(row["processing_mode"] == "vector" for row in source_rows)

    deterministic_sources = sum(row["processing_mode"] == "deterministic" for row in source_rows)

    print(f"sources: {len(source_rows)}")
    print(f"vector sources: {vector_sources}")
    print(f"deterministic sources: {deterministic_sources}")
    print(f"canonical chunks: {len(chunk_rows)}")
    print(f"source manifest: {SOURCE_MANIFEST_PATH}")
    print(f"chunks: {CHUNKS_PATH}")


if __name__ == "__main__":
    main()
