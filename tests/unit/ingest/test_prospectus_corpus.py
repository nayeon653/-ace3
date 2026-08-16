"""raw source -> canonical corpus identity 계약을 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pension_agent.ingest import prospectus_corpus as pc

_RAW = {
    "body": {"children": [{"$ref": "#/texts/0"}, {"$ref": "#/texts/1"}]},
    "texts": [
        {"label": "section_header", "level": 1, "text": "섹션", "prov": [{"page_no": 1}]},
        {"label": "text", "text": "본문", "prov": [{"page_no": 1}]},
    ],
    "tables": [],
    "groups": [],
}


def _write_source(root: Path, product_code: str, content: bytes) -> Path:
    d = root / product_code
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"R2_{product_code}.pdf"
    p.write_bytes(content)
    return p


def _write_bundle(processed_root: Path, bundle_name: str, sha256: str) -> None:
    d = processed_root / "prospectus" / bundle_name
    d.mkdir(parents=True, exist_ok=True)
    manifest = {
        "status": "success",
        "profile": {"id": pc.PROFILE_ID},
        "source": {"filename": f"{bundle_name.split('--')[0]}.pdf", "sha256": sha256, "extension": ".pdf"},
        "stats": {"pages": 1},
    }
    (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (d / "document.docling.json").write_text(json.dumps(_RAW), encoding="utf-8")
    (d / "document.md").write_text("", encoding="utf-8")


def _build_fixture(tmp_path: Path) -> tuple[Path, Path, str, str]:
    """CODE_A와 CODE_B는 동일 content(dedup group), CODE_C는 다른 content.

    실제 corpus와 동일하게, dedup group에서는 "대표"(CODE_A)만 파싱되고
    bundle_name도 그 대표 파일 기준으로 만들어진다.
    """

    source_root = tmp_path / "raw" / "prospectus"
    processed_root = tmp_path / "processed" / "docling"
    content_x = b"content-x-bytes"
    content_y = b"content-y-bytes"
    _write_source(source_root, "CODE_A", content_x)
    _write_source(source_root, "CODE_B", content_x)
    _write_source(source_root, "CODE_C", content_y)

    sha_x = hashlib.sha256(content_x).hexdigest()
    sha_y = hashlib.sha256(content_y).hexdigest()
    _write_bundle(processed_root, f"R2_CODE_A--{sha_x[:12]}--{pc.PROFILE_ID}", sha_x)
    _write_bundle(processed_root, f"R2_CODE_C--{sha_y[:12]}--{pc.PROFILE_ID}", sha_y)

    return source_root, processed_root, sha_x, sha_y


def test_source_manifest_has_one_row_per_raw_source_and_shares_canonical_id_for_dup(tmp_path: Path) -> None:
    source_root, processed_root, sha_x, sha_y = _build_fixture(tmp_path)

    rows = pc.build_source_manifest(source_root, processed_root)

    assert len(rows) == 3
    assert {r["source_id"] for r in rows} == {"CODE_A", "CODE_B", "CODE_C"}
    by_id = {r["source_id"]: r for r in rows}

    assert by_id["CODE_A"]["source_sha256"] == by_id["CODE_B"]["source_sha256"] == sha_x
    assert by_id["CODE_A"]["canonical_doc_id"] == by_id["CODE_B"]["canonical_doc_id"] == pc.canonical_doc_id(sha_x)
    assert by_id["CODE_C"]["canonical_doc_id"] == pc.canonical_doc_id(sha_y)
    assert by_id["CODE_A"]["canonical_doc_id"] != by_id["CODE_C"]["canonical_doc_id"]

    assert len({r["source_id"] for r in rows}) == 3
    assert len({r["source_sha256"] for r in rows}) == 2
    assert len({r["canonical_doc_id"] for r in rows}) == 2
    assert all(r["processing_mode"] == "vector" for r in rows)
    assert all(r["parser_profile"] == pc.PROFILE_ID for r in rows)


def test_canonical_doc_id_independent_of_which_product_code_was_parsed(tmp_path: Path) -> None:
    """bundle의 대표 파일이 CODE_B였어도(=CODE_A가 아니라) canonical_doc_id는 동일해야 한다."""

    source_root = tmp_path / "raw" / "prospectus"
    processed_root = tmp_path / "processed" / "docling"
    content_x = b"content-x-bytes"
    _write_source(source_root, "CODE_A", content_x)
    _write_source(source_root, "CODE_B", content_x)
    sha_x = hashlib.sha256(content_x).hexdigest()
    _write_bundle(processed_root, f"R2_CODE_B--{sha_x[:12]}--{pc.PROFILE_ID}", sha_x)  # 대표가 B로 바뀜

    rows = pc.build_source_manifest(source_root, processed_root)
    by_id = {r["source_id"]: r for r in rows}

    assert by_id["CODE_A"]["canonical_doc_id"] == by_id["CODE_B"]["canonical_doc_id"] == pc.canonical_doc_id(sha_x)


def test_known_anomaly_note_attached_by_source_id(tmp_path: Path) -> None:
    source_root = tmp_path / "raw" / "prospectus"
    processed_root = tmp_path / "processed" / "docling"
    content = b"anomaly-doc-bytes"
    _write_source(source_root, "KR5127450117", content)
    sha = hashlib.sha256(content).hexdigest()
    _write_bundle(processed_root, f"R2_KR5127450117--{sha[:12]}--{pc.PROFILE_ID}", sha)

    rows = pc.build_source_manifest(source_root, processed_root)

    assert rows[0]["notes"] != ""


def test_canonical_export_chunks_unique_content_once_with_canonical_ids(tmp_path: Path) -> None:
    source_root, processed_root, sha_x, sha_y = _build_fixture(tmp_path)
    rows = pc.build_source_manifest(source_root, processed_root)

    chunk_rows = pc.export_canonical_chunks(rows, processed_root)

    canonical_ids = {r["canonical_doc_id"] for r in chunk_rows}
    assert canonical_ids == {pc.canonical_doc_id(sha_x), pc.canonical_doc_id(sha_y)}
    assert all(r["chunk_id"].startswith(r["canonical_doc_id"]) for r in chunk_rows)
    assert all("doc_id" not in r for r in chunk_rows)  # product_code를 chunk에 복제하지 않는다
    for r in chunk_rows:
        assert r["text"].strip()


def test_source_manifest_and_chunks_are_deterministic_across_runs(tmp_path: Path) -> None:
    source_root, processed_root, _sha_x, _sha_y = _build_fixture(tmp_path)

    rows_1 = pc.build_source_manifest(source_root, processed_root)
    rows_2 = pc.build_source_manifest(source_root, processed_root)
    assert rows_1 == rows_2

    chunks_1 = pc.export_canonical_chunks(rows_1, processed_root)
    chunks_2 = pc.export_canonical_chunks(rows_2, processed_root)
    assert chunks_1 == chunks_2


def test_write_jsonl_round_trip(tmp_path: Path) -> None:
    rows = [{"a": 1, "b": "한글"}, {"a": 2, "b": "text"}]
    path = tmp_path / "out" / "rows.jsonl"

    pc.write_jsonl(rows, path)

    loaded = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert loaded == rows
