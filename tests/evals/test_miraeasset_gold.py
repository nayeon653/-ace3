from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import sys
import tarfile
from pathlib import Path
from typing import Any

import pytest

from evals.harness import validate_miraeasset_gold as validator
from evals.harness.validate_miraeasset_gold import (
    DATASET,
    ValidationError,
    _artifact_paths,
    _expected_evidence_id,
    _item_text,
    _normalize_text,
    _split_markdown_table_row,
    _validate_delivery_archive,
    _validate_provenance,
    _validate_registries,
    _validate_retrieval,
    validate_dataset,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _copy_dataset(tmp_path: Path) -> Path:
    source_repo = Path(__file__).resolve().parents[2]
    repo_root = tmp_path / "repo"
    shutil.copytree(source_repo / "evals" / "gold", repo_root / "evals" / "gold")
    (repo_root / "evals" / "questions").mkdir(parents=True)
    shutil.copy2(
        source_repo / "evals" / "questions" / f"{DATASET}.md",
        repo_root / "evals" / "questions" / f"{DATASET}.md",
    )
    return repo_root


def _rehash_artifact(repo_root: Path, artifact: str) -> None:
    gold_root = repo_root / "evals" / "gold"
    manifest_path = gold_root / f"{DATASET}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_path = repo_root / manifest["artifacts"][artifact]["path"]
    manifest["artifacts"][artifact].update(
        {"sha256": _sha256(artifact_path), "size_bytes": artifact_path.stat().st_size}
    )
    _write_json(manifest_path, manifest)


def _retrieval_link() -> dict[str, Any]:
    return {
        "chunk_id": "knowledge-doc-0001",
        "canonical_doc_id": "knowledge-doc",
        "content_hash": "d" * 64,
        "page_start": None,
        "page_end": None,
        "match_method": "quote_substring",
    }


def _delivery_meta() -> dict[str, Any]:
    return {
        "bundle_dir": "doc--abc123--delivery",
        "bundle_id": "bundle-delivery",
        "profile_id": "docling-no-ocr-formula-v1",
        "profile_digest": "sha256:delivery",
        "json_filename": "document.docling.json",
        "json_sha256": "a" * 64,
        "status": "success",
        "relative_root": "processed/docling/formula_sources",
    }


def _review_meta() -> dict[str, Any]:
    return {
        "bundle_dir": "doc--abc123--review",
        "bundle_id": "bundle-review",
        "profile_id": "docling-local-ocr-v1",
        "profile_digest": "sha256:review",
        "json_filename": "document.docling.json",
        "json_sha256": "b" * 64,
        "status": "success",
        "relative_root": "processed/docling/knowledge_docs",
        "purpose": "원본 PDF 시각 대조",
        "visually_verified_pages": [2],
    }


def _source(*, include_review: bool = False) -> dict[str, Any]:
    variants = {"delivery": _delivery_meta()}
    if include_review:
        variants["review_local_ocr"] = _review_meta()
    return {
        "source_key": "doc",
        "filename": "doc.pdf",
        "collection": "docs",
        "mime_type": "application/pdf",
        "size_bytes": 10,
        "source_sha256": "c" * 64,
        "drive_id": "drive-doc",
        "drive_url": "https://example.test/doc",
        "raw_relative_path": "raw/formula_sources/docs/docs_renamed/doc.pdf",
        "docling_variants": variants,
    }


def _evidence(
    *,
    variant: str = "delivery",
    label: str = "text",
    item_ref: str = "#/texts/0",
    table_cells: list[dict[str, Any]] | None = None,
    page_no: int | None = None,
) -> dict[str, Any]:
    row = {
        "evidence_id": "pending",
        "source_key": "doc",
        "docling_variant": variant,
        "item_ref": item_ref,
        "label": label,
        "quote": "근거 문장",
        "page_no": page_no,
        "bbox": {"l": 1, "t": 2, "r": 3, "b": 0, "coord_origin": "BOTTOMLEFT"}
        if page_no is not None
        else None,
        "charspan": [0, 4] if page_no is not None else None,
        "table_cells": table_cells or [],
        "retrieval_chunks": [],
    }
    row["evidence_id"] = _expected_evidence_id(row)
    return row


def _registry_roots(
    evidence: dict[str, Any], source: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {
            "schema_version": "docling-evidence-v1",
            "dataset": DATASET,
            "evidence": [evidence],
        },
        {
            "schema_version": "docling-sources-v1",
            "dataset": DATASET,
            "sources": [source],
        },
    )


def test_miraeasset_gold_structure() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    summary = validate_dataset(repo_root, structure_only=True)

    assert summary["questions"] == 86
    assert sum(summary["answerability"].values()) == 86
    assert summary["claims"] > 0
    assert summary["evidence"] > 0
    assert summary["sources"] > 0


def test_normalize_text_does_not_decode_html_entities() -> None:
    assert _normalize_text("연금  &amp;\nISA") == "연금 &amp; ISA"
    assert _normalize_text("연금 &amp; ISA") != _normalize_text("연금 & ISA")


def test_markdown_row_parser_preserves_escaped_pipe_inside_seven_columns() -> None:
    row = "| ID | 질문의 \\| 기호 | 상태 | 답변 | 주장 | 근거 | 공백 |"

    assert _split_markdown_table_row(row, "test") == [
        "ID",
        "질문의 \\| 기호",
        "상태",
        "답변",
        "주장",
        "근거",
        "공백",
    ]


def test_evidence_id_has_16_hex_suffix_and_includes_variant() -> None:
    delivery = _evidence()
    review = _evidence(variant="review_local_ocr")

    assert len(delivery["evidence_id"].rsplit("-", 1)[1]) == 16
    assert delivery["evidence_id"] != review["evidence_id"]
    assert delivery["evidence_id"] == _expected_evidence_id(delivery)


def test_registry_rejects_evidence_content_changed_without_new_id() -> None:
    evidence = _evidence()
    evidence["quote"] = "ID 생성 뒤 바꾼 근거 문장"
    evidence_root, sources_root = _registry_roots(evidence, _source())

    with pytest.raises(ValidationError, match="canonical content"):
        _validate_registries(evidence_root, sources_root)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("extra_field", "schema mismatch"),
        ("bad_method", "match_method"),
        ("bad_chunk_id", "chunk_id"),
        ("bad_hash", "content_hash"),
        ("half_null_page", "both null or both integers"),
        ("reversed_page", "bad retrieval page range"),
    ],
)
def test_registry_rejects_invalid_retrieval_link(mutation: str, message: str) -> None:
    evidence = _evidence()
    link = _retrieval_link()
    if mutation == "extra_field":
        link["unexpected"] = True
    elif mutation == "bad_method":
        link["match_method"] = "fuzzy"
    elif mutation == "bad_chunk_id":
        link["chunk_id"] = 123
    elif mutation == "bad_hash":
        link["content_hash"] = "not-a-sha256"
    elif mutation == "half_null_page":
        link["page_start"] = 1
    elif mutation == "reversed_page":
        link["page_start"] = 3
        link["page_end"] = 2
    evidence["retrieval_chunks"] = [link]
    evidence_root, sources_root = _registry_roots(evidence, _source())

    with pytest.raises(ValidationError, match=message):
        _validate_registries(evidence_root, sources_root)


def test_registry_rejects_table_evidence_without_cells() -> None:
    evidence = _evidence(label="table", item_ref="#/tables/0")
    evidence_root, sources_root = _registry_roots(evidence, _source())

    with pytest.raises(ValidationError, match="requires exact cells"):
        _validate_registries(evidence_root, sources_root)


def test_registry_rejects_unverified_review_page() -> None:
    evidence = _evidence(variant="review_local_ocr", page_no=3)
    evidence_root, sources_root = _registry_roots(evidence, _source(include_review=True))

    with pytest.raises(ValidationError, match="was not visually verified"):
        _validate_registries(evidence_root, sources_root)


def test_provenance_cannot_be_dropped_when_raw_item_has_it() -> None:
    provenance = {
        "page_no": 1,
        "bbox": {"l": 1, "t": 2, "r": 3, "b": 0, "coord_origin": "BOTTOMLEFT"},
        "charspan": [0, 4],
    }
    item = {"prov": [provenance]}
    evidence = {"evidence_id": "E-TEST", "page_no": None, "bbox": None, "charspan": None}

    with pytest.raises(ValidationError, match="must be retained"):
        _validate_provenance(item, evidence)


def test_table_cell_text_must_equal_raw_docling_text() -> None:
    item = {
        "self_ref": "#/tables/0",
        "label": "table",
        "data": {
            "table_cells": [
                {
                    "start_row_offset_idx": 0,
                    "end_row_offset_idx": 1,
                    "start_col_offset_idx": 0,
                    "end_col_offset_idx": 1,
                    "text": "원문",
                }
            ]
        },
    }
    selected = [
        {
            "start_row": 0,
            "end_row": 1,
            "start_col": 0,
            "end_col": 1,
            "text": "변조",
        }
    ]

    with pytest.raises(ValidationError, match="text mismatch"):
        _item_text(item, selected)


def test_artifact_size_is_verified(tmp_path: Path) -> None:
    artifacts: dict[str, dict[str, Any]] = {}
    for name in ("gold", "evidence", "sources", "table", "review"):
        path = tmp_path / f"{name}.txt"
        path.write_text(name, encoding="utf-8")
        artifacts[name] = {
            "path": path.name,
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
    artifacts["table"]["size_bytes"] += 1

    with pytest.raises(ValidationError, match="artifact size mismatch"):
        _artifact_paths(tmp_path, {"artifacts": artifacts})


@pytest.mark.parametrize("mutated_filename", ["manifest.json", "document.docling.json"])
def test_delivery_archive_rejects_loose_bundle_mutation(
    tmp_path: Path, mutated_filename: str
) -> None:
    prefix = "data/processed/docling/formula_sources/bundle"
    archived_manifest = {
        "status": "success",
        "source": {"filename": "doc.pdf", "size_bytes": 10},
    }
    manifest_bytes = json.dumps(archived_manifest).encode()
    archived_document = b'{"texts": []}'
    archive = tmp_path / "delivery.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        for name, payload in (
            (f"{prefix}/manifest.json", manifest_bytes),
            (f"{prefix}/document.docling.json", archived_document),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            handle.addfile(info, io.BytesIO(payload))

    loose_manifest = tmp_path / "manifest.json"
    loose_document = tmp_path / "document.docling.json"
    loose_manifest.write_bytes(manifest_bytes)
    loose_document.write_bytes(archived_document)
    mutated_path = loose_manifest if mutated_filename == "manifest.json" else loose_document
    mutated_path.write_bytes(mutated_path.read_bytes() + b"\nmutated")
    loose_files = {
        f"{prefix}/manifest.json": loose_manifest,
        f"{prefix}/document.docling.json": loose_document,
    }
    delivery = {"bundle_count": 1, "successful_bundles": 1}
    inventory = [{"title": "doc.pdf", "size": 10}]

    with pytest.raises(ValidationError, match="differs from fixed archive"):
        _validate_delivery_archive(archive, delivery, inventory, loose_files)


def test_retrieval_manifest_source_count_is_verified(tmp_path: Path) -> None:
    chunks_path = tmp_path / "input" / "chunks.jsonl"
    chunks_path.parent.mkdir(parents=True)
    chunks_path.write_text("", encoding="utf-8")
    retrieval_manifest = {
        "collection_name": "test",
        "counts": {"points": 0, "sources": 2, "canonical_documents": 0},
        "inputs": {"chunks": {"sha256": _sha256(chunks_path)}, "source_manifests": []},
    }
    manifest_path = tmp_path / "manifest.json"
    _write_json(manifest_path, retrieval_manifest)
    manifest = {
        "corpus": {
            "retrieval": {
                "collection": "test",
                "points": 0,
                "manifest_relative_path": "manifest.json",
                "manifest_sha256": _sha256(manifest_path),
                "chunks_relative_path": "input/chunks.jsonl",
                "chunks_sha256": _sha256(chunks_path),
            }
        }
    }

    with pytest.raises(ValidationError, match="source count mismatch"):
        _validate_retrieval(tmp_path, manifest, {}, inventory_count=1)


def test_full_retrieval_recomputes_chunk_content_hash(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    source_path = input_root / "sources.jsonl"
    source_path.write_text(json.dumps({"source_id": "doc"}) + "\n", encoding="utf-8")
    chunks_path = input_root / "chunks.jsonl"
    chunk = {
        "chunk_id": "chunk-1",
        "canonical_doc_id": "document-1",
        "content_hash": "0" * 64,
        "page_start": None,
        "page_end": None,
        "text": "실제 청크 원문",
        "metadata": {"source_ids": ["doc"]},
    }
    chunks_path.write_text(json.dumps(chunk, ensure_ascii=False) + "\n", encoding="utf-8")
    retrieval_manifest = {
        "collection_name": "test",
        "counts": {"points": 1, "sources": 1, "canonical_documents": 1},
        "inputs": {
            "chunks": {"sha256": _sha256(chunks_path)},
            "source_manifests": [{"path": str(source_path), "sha256": _sha256(source_path)}],
        },
    }
    manifest_path = tmp_path / "manifest.json"
    _write_json(manifest_path, retrieval_manifest)
    manifest = {
        "corpus": {
            "retrieval": {
                "collection": "test",
                "points": 1,
                "manifest_relative_path": "manifest.json",
                "manifest_sha256": _sha256(manifest_path),
                "chunks_relative_path": "input/chunks.jsonl",
                "chunks_sha256": _sha256(chunks_path),
            }
        }
    }

    with pytest.raises(ValidationError, match="chunk content hash mismatch"):
        _validate_retrieval(tmp_path, manifest, {}, inventory_count=1)


@pytest.mark.parametrize(
    ("artifact", "message"),
    [
        ("table", "Gold table title mismatch"),
        ("review", "Gold review title mismatch"),
    ],
)
def test_structure_validation_rejects_semantically_corrupted_markdown(
    tmp_path: Path, artifact: str, message: str
) -> None:
    repo_root = _copy_dataset(tmp_path)
    artifact_path = repo_root / "evals" / "gold" / f"{DATASET}.{artifact}.md"
    artifact_path.write_text("# CORRUPTED BUT HASHED\n", encoding="utf-8")
    _rehash_artifact(repo_root, artifact)

    with pytest.raises(ValidationError, match=message):
        validate_dataset(repo_root, structure_only=True)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("claim_evidence_swap", "claim evidence mismatch"),
        ("evidence_content_swap", "evidence block mismatch"),
        ("extra_column", "exactly 7 columns"),
    ],
)
def test_structure_validation_rejects_markdown_id_swaps_and_extra_columns(
    tmp_path: Path, mutation: str, message: str
) -> None:
    repo_root = _copy_dataset(tmp_path)
    table_path = repo_root / "evals" / "gold" / f"{DATASET}.table.md"
    lines = table_path.read_text(encoding="utf-8").splitlines()
    row_index = next(index for index, line in enumerate(lines) if line.startswith("| MA-PP-003 "))
    cells = _split_markdown_table_row(lines[row_index], "mutation test")

    if mutation == "claim_evidence_swap":
        blocks = cells[4].split("<br><br>")
        first_heading, separator, first_evidence = blocks[0].partition("<br>근거: ")
        second_heading, _, second_evidence = blocks[1].partition("<br>근거: ")
        blocks[0] = first_heading + separator + second_evidence
        blocks[1] = second_heading + separator + first_evidence
        cells[4] = "<br><br>".join(blocks)
    elif mutation == "evidence_content_swap":
        blocks = cells[5].split("<br><br>")
        first = re.fullmatch(r"(\*\*E-[A-Z0-9-]+\*\* — )(.*)", blocks[0])
        second = re.fullmatch(r"(\*\*E-[A-Z0-9-]+\*\* — )(.*)", blocks[1])
        assert first is not None and second is not None
        blocks[0] = first.group(1) + second.group(2)
        blocks[1] = second.group(1) + first.group(2)
        cells[5] = "<br><br>".join(blocks)
    else:
        cells.insert(3, "삽입된 열")

    lines[row_index] = "| " + " | ".join(cells) + " |"
    table_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _rehash_artifact(repo_root, "table")

    with pytest.raises(ValidationError, match=message):
        validate_dataset(repo_root, structure_only=True)


def test_structure_validation_rejects_unsafe_archive_relative_path(tmp_path: Path) -> None:
    repo_root = _copy_dataset(tmp_path)
    manifest_path = repo_root / "evals" / "gold" / f"{DATASET}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["corpus"]["docling_delivery"]["archive_relative_path"] = "../../archive.tar.gz"
    _write_json(manifest_path, manifest)

    with pytest.raises(ValidationError, match="unsafe docling_delivery.archive_relative_path"):
        validate_dataset(repo_root, structure_only=True)


def test_cli_defaults_to_structure_only_without_data_root(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: dict[str, Any] = {}

    def fake_validate_dataset(
        repo_root: Path,
        *,
        structure_only: bool = False,
        data_root: Path | None = None,
    ) -> dict[str, Any]:
        captured.update(
            repo_root=repo_root,
            structure_only=structure_only,
            data_root=data_root,
        )
        return {"mode": "structure-only"}

    monkeypatch.setattr(sys, "argv", ["validate_miraeasset_gold"])
    monkeypatch.setattr(validator, "validate_dataset", fake_validate_dataset)

    validator.main()

    assert captured["structure_only"] is True
    assert captured["data_root"] is None
    assert json.loads(capsys.readouterr().out) == {"mode": "structure-only"}
