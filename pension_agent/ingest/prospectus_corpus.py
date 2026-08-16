"""투자설명서 원본 100개 -> 92 unique canonical corpus export.

이미 검증된 normalize_document/chunk_document(둘 다 수정하지 않는다)를 그대로
쓰고, canonical identity는 이 모듈(export 경계)에서만 주입한다.

identity 계약:
- source_id = product_code(원본 폴더명, data/raw/prospectus/<product_code>/).
- source_sha256 = 원본 PDF의 SHA-256(dedup 키). Chunk.content_hash(청크 텍스트
  자체의 해시)와 의미가 달라서 이름을 분리했다 — 혼동 금지.
- canonical_doc_id = f"prospectus-{source_sha256[:12]}". 어떤 product_code가
  먼저 파싱돼 bundle의 대표 파일이 됐는지와 무관하게 source_sha256만으로
  정해지는 deterministic id다 — 대표 파일이 바뀌어도 안 변한다.
- 동일 source_sha256를 가진 여러 product_code(예: KR5113420013≡KR5113420015)는
  같은 canonical_doc_id를 공유한다. canonical chunk는 92개 unique content
  기준으로 한 번만 만든다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pension_agent.ingest.normalize import normalize_document
from pension_agent.retrieval.chunker import chunk_document

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "data" / "raw" / "prospectus"
PROCESSED_ROOT = REPO_ROOT / "data" / "processed" / "docling"
INDEX_ROOT = REPO_ROOT / "data" / "indexes" / "prospectus"
SOURCE_MANIFEST_PATH = INDEX_ROOT / "source_manifest.jsonl"
CHUNKS_PATH = INDEX_ROOT / "chunks.jsonl"

PROFILE_ID = "docling-local-ocr-v1"
CANONICAL_PREFIX = "prospectus"

# 이미 확인된 raw JSON/hierarchy anomaly — 자동 FAIL 대상 아님, 기록만.
KNOWN_ANOMALY_NOTES = {
    "KR5127450117": "raw JSON에 제3부 본문 heading occurrence 결측(echo만 존재)",
    "KR514X450008": "raw JSON에 제3부 본문 heading occurrence 결측(echo만 존재)",
    "KR5156450026": "subitem 1건 보수적 미승격('나 . 투자제한'이 '3)' 각주 안에 파묻힘) — text로 보존",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_doc_id(source_sha256: str) -> str:
    return f"{CANONICAL_PREFIX}-{source_sha256[:12]}"


def _find_success_bundles(processed_root: Path) -> dict[str, Path]:
    """source_sha256 -> bundle_dir. status=success + profile 일치하는 것만."""

    bundles: dict[str, Path] = {}
    for manifest_path in sorted(processed_root.glob("*/*/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if manifest.get("status") == "success" and manifest.get("profile", {}).get("id") == PROFILE_ID:
            sha = manifest.get("source", {}).get("sha256")
            if sha:
                bundles.setdefault(sha, manifest_path.parent)
    return bundles


def build_source_manifest(source_root: Path = SOURCE_ROOT, processed_root: Path = PROCESSED_ROOT) -> list[dict[str, Any]]:
    """원본 100개 각각 1 row. rows 순서는 경로 정렬로 고정(재실행 시 동일)."""

    bundles_by_hash = _find_success_bundles(processed_root)
    rows: list[dict[str, Any]] = []
    for pdf_path in sorted(source_root.glob("*/*.pdf")):
        source_id = pdf_path.parent.name
        sha = sha256_file(pdf_path)
        bundle_dir = bundles_by_hash.get(sha)
        if bundle_dir is not None:
            profile_id: str | None = PROFILE_ID
            processing_mode = "vector"
        else:
            profile_id = None
            processing_mode = "failed"
        try:
            source_path = pdf_path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            source_path = pdf_path.as_posix()
        rows.append(
            {
                "source_id": source_id,
                "source_path": source_path,
                "source_sha256": sha,
                "canonical_doc_id": canonical_doc_id(sha),
                "doc_type": pdf_path.suffix.lstrip(".").lower(),
                "parser_profile": profile_id,
                "processing_mode": processing_mode,
                "notes": KNOWN_ANOMALY_NOTES.get(source_id, ""),
            }
        )
    return rows


def _canonical_chunk_row(chunk, cdoc_id: str, index: int) -> dict[str, Any]:
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


def export_canonical_chunks(source_rows: list[dict[str, Any]], processed_root: Path = PROCESSED_ROOT) -> list[dict[str, Any]]:
    """source manifest rows에서 unique source_sha256(92개)만 뽑아 1회씩 chunk한다.

    canonical_doc_id 오름차순으로 순회한다 — 원본 디렉터리 나열 순서가 아니라
    content hash 자체로만 export 순서가 정해지므로 재실행/환경이 달라져도 동일하다.
    """

    bundles_by_hash = _find_success_bundles(processed_root)

    unique_sources: dict[str, str] = {}  # source_sha256 -> canonical_doc_id
    for row in source_rows:
        unique_sources.setdefault(row["source_sha256"], row["canonical_doc_id"])

    rows: list[dict[str, Any]] = []
    for sha, cdoc_id in sorted(unique_sources.items(), key=lambda item: item[1]):
        bundle_dir = bundles_by_hash.get(sha)
        if bundle_dir is None:
            continue
        doc = normalize_document(bundle_dir)
        chunks = chunk_document(doc)
        for i, chunk in enumerate(chunks):
            rows.append(_canonical_chunk_row(chunk, cdoc_id, i))
    return rows


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def main() -> None:
    source_rows = build_source_manifest()
    write_jsonl(source_rows, SOURCE_MANIFEST_PATH)

    chunk_rows = export_canonical_chunks(source_rows)
    write_jsonl(chunk_rows, CHUNKS_PATH)

    print(f"source manifest: {len(source_rows)} rows -> {SOURCE_MANIFEST_PATH}")
    print(f"canonical chunks: {len(chunk_rows)} rows -> {CHUNKS_PATH}")


if __name__ == "__main__":
    main()
