"""Validate the PR #130 Mirae Asset FAQ Gold Answer dataset.

Structure-only validation is suitable for CI. Full validation additionally checks the
ignored local source corpus, final Docling bundles, and linked retrieval chunks.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

DATASET = "miraeasset_actual_86"
ANSWERABILITY = {"supported", "partial", "unsupported", "temporal_gap"}
STATUS_KO = {
    "supported": "직접 지원",
    "partial": "부분 지원",
    "unsupported": "미지원",
    "temporal_gap": "최신성 공백",
}
DOCLING_VARIANTS = {"delivery", "review_local_ocr"}
VARIANT_ROOTS = {
    "delivery": "processed/docling/formula_sources",
    "review_local_ocr": "processed/docling/knowledge_docs",
}
TABLE_CELL_FIELDS = ("start_row", "end_row", "start_col", "end_col")
RETRIEVAL_LINK_FIELDS = {
    "chunk_id",
    "canonical_doc_id",
    "content_hash",
    "page_start",
    "page_end",
    "match_method",
}
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
QUESTION_LINE = re.compile(r"^\|\s*(MA-(?:PP|RP|ISA)-\d{3})\s*\|")
ITEM_REF = re.compile(r"^#/(texts|tables|pictures|key_value_items|form_items)/(\d+)$")


class ValidationError(RuntimeError):
    """Raised when a Gold dataset invariant is violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        _require(isinstance(row, dict), f"{path}:{line_number}: row must be an object")
        rows.append(row)
    return rows


def _normalize_text(value: str) -> str:
    """Normalize layout whitespace without changing source characters."""

    return " ".join(value.split())


def _json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _markdown_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\r\n", "\n").replace("\n", "<br>")


def _table_cell_label(cell: dict[str, Any]) -> str:
    start = f"r{cell['start_row']}c{cell['start_col']}"
    end = f"r{cell['end_row'] - 1}c{cell['end_col'] - 1}"
    return start if start == end else f"{start}:{end}"


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _safe_relative_path(value: Any, field: str) -> PurePosixPath:
    _require(isinstance(value, str) and value, f"{field} must be a relative path")
    _require("\\" not in value, f"{field} must use POSIX separators")
    path = PurePosixPath(value)
    _require(not path.is_absolute(), f"{field} must be relative")
    _require(all(part not in ("", ".", "..") for part in path.parts), f"unsafe {field}")
    _require(str(path) == value, f"{field} must be canonical")
    return path


def _validate_retrieval_link(link: Any, evidence_id: str, index: int) -> None:
    context = f"{evidence_id}.retrieval_chunks[{index}]"
    _require(isinstance(link, dict), f"retrieval link must be an object: {context}")
    _require(set(link) == RETRIEVAL_LINK_FIELDS, f"retrieval link schema mismatch: {context}")
    for field in ("chunk_id", "canonical_doc_id"):
        _require(isinstance(link[field], str) and link[field], f"bad {context}.{field}")
    _require(
        isinstance(link["content_hash"], str) and SHA256_HEX.fullmatch(link["content_hash"]),
        f"bad {context}.content_hash",
    )
    _require(link["match_method"] == "quote_substring", f"bad {context}.match_method")
    page_start = link["page_start"]
    page_end = link["page_end"]
    if page_start is None or page_end is None:
        _require(
            page_start is None and page_end is None,
            f"retrieval page range must be both null or both integers: {context}",
        )
    else:
        _require(
            _is_int(page_start) and _is_int(page_end) and 0 < page_start <= page_end,
            f"bad retrieval page range: {context}",
        )


def _canonical_table_cells(value: Any, evidence_id: str) -> list[dict[str, Any]]:
    _require(isinstance(value, list), f"bad table cells: {evidence_id}")
    cells: list[dict[str, Any]] = []
    for index, cell in enumerate(value):
        _require(isinstance(cell, dict), f"bad table cell {index}: {evidence_id}")
        for field in TABLE_CELL_FIELDS:
            _require(_is_int(cell.get(field)), f"bad table cell {field}: {evidence_id}")
        _require(
            0 <= cell["start_row"] < cell["end_row"] and 0 <= cell["start_col"] < cell["end_col"],
            f"invalid table cell range: {evidence_id}",
        )
        _require(isinstance(cell.get("text"), str), f"bad table cell text: {evidence_id}")
        cells.append(
            {
                "start_row": cell["start_row"],
                "end_row": cell["end_row"],
                "start_col": cell["start_col"],
                "end_col": cell["end_col"],
                "text": cell["text"],
            }
        )
    cells.sort(
        key=lambda cell: (
            cell["start_row"],
            cell["start_col"],
            cell["end_row"],
            cell["end_col"],
        )
    )
    _require(
        value == cells, f"table cells must be canonical and contain no extra fields: {evidence_id}"
    )
    coordinates = [tuple(cell[field] for field in TABLE_CELL_FIELDS) for cell in cells]
    _require(len(coordinates) == len(set(coordinates)), f"duplicate table cells: {evidence_id}")
    return cells


def _expected_evidence_id(evidence: dict[str, Any]) -> str:
    source_key = evidence["source_key"]
    item_ref = evidence["item_ref"]
    variant = evidence["docling_variant"]
    match = ITEM_REF.fullmatch(item_ref)
    _require(match is not None, f"invalid item_ref: {item_ref}")
    collection, number = match.groups()
    kind = {"texts": "T", "tables": "TB", "pictures": "P"}.get(collection, collection[:2].upper())
    safe_source = re.sub(r"[^A-Za-z0-9]+", "-", source_key).strip("-").upper()
    key = _json_compact([source_key, variant, item_ref, evidence["quote"], evidence["table_cells"]])
    suffix = hashlib.sha256(key.encode()).hexdigest()[:16].upper()
    return f"E-{safe_source}-{kind}{number}-{suffix}"


def _questions(path: Path) -> list[tuple[str, str]]:
    questions: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not QUESTION_LINE.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        _require(len(cells) >= 3, f"malformed question row: {line[:120]}")
        questions.append((cells[0], html.unescape(cells[2])))
    _require(len(questions) == 86, f"expected 86 questions, found {len(questions)}")
    return questions


def _artifact_paths(repo_root: Path, manifest: dict[str, Any]) -> dict[str, Path]:
    artifacts = manifest.get("artifacts")
    _require(isinstance(artifacts, dict), "manifest.artifacts must be an object")
    paths: dict[str, Path] = {}
    for name in ("gold", "evidence", "sources", "table", "review"):
        record = artifacts.get(name)
        _require(isinstance(record, dict), f"manifest artifact missing: {name}")
        relative = record.get("path")
        _require(isinstance(relative, str) and relative, f"artifact {name} path is missing")
        path = repo_root / relative
        _require(path.is_file(), f"artifact does not exist: {relative}")
        expected_size = record.get("size_bytes")
        _require(_is_int(expected_size) and expected_size >= 0, f"bad artifact size: {relative}")
        _require(path.stat().st_size == expected_size, f"artifact size mismatch: {relative}")
        expected_hash = record.get("sha256")
        _require(expected_hash == _sha256(path), f"artifact hash mismatch: {relative}")
        paths[name] = path
    return paths


def _validate_delivery_metadata(manifest: dict[str, Any]) -> dict[str, Any]:
    corpus = manifest.get("corpus")
    _require(isinstance(corpus, dict), "manifest corpus metadata must be an object")
    delivery = corpus.get("docling_delivery")
    _require(isinstance(delivery, dict), "Docling delivery metadata must be an object")
    archive_name = delivery.get("archive_name")
    _require(isinstance(archive_name, str) and archive_name, "delivery archive name is missing")
    archive_relative_path = _safe_relative_path(
        delivery.get("archive_relative_path"),
        "docling_delivery.archive_relative_path",
    )
    _require(
        archive_relative_path.name == archive_name,
        "delivery archive name and relative path disagree",
    )
    _require(
        _is_int(delivery.get("size_bytes")) and delivery["size_bytes"] > 0,
        "bad delivery archive size",
    )
    _require(
        isinstance(delivery.get("sha256"), str) and SHA256_HEX.fullmatch(delivery["sha256"]),
        "bad delivery archive hash",
    )
    _require(
        delivery.get("successful_bundles") == delivery.get("bundle_count") == 158,
        "Docling delivery must contain 158 successful bundles",
    )
    return delivery


def _validate_questions(
    repo_root: Path,
    manifest: dict[str, Any],
    gold: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    question_meta = manifest.get("question_source", {})
    question_path_value = question_meta.get("path")
    _require(isinstance(question_path_value, str), "manifest question path is missing")
    question_path = repo_root / question_path_value
    _require(question_path.is_file(), f"question file does not exist: {question_path_value}")
    _require(question_meta.get("sha256") == _sha256(question_path), "question hash mismatch")
    canonical = _questions(question_path)
    _require(len(gold) == len(canonical), "Gold row count does not match the question set")
    for index, ((expected_id, expected_question), row) in enumerate(zip(canonical, gold)):
        _require(row.get("test_id") == expected_id, f"Gold ID/order mismatch at row {index + 1}")
        _require(
            row.get("question") == expected_question,
            f"Gold question mismatch for {expected_id}",
        )
    return canonical


def _validate_gold(
    gold: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> tuple[Counter[str], int, int, set[str]]:
    statuses: Counter[str] = Counter()
    claim_count = 0
    evidence_reference_count = 0
    used_evidence: set[str] = set()
    global_claim_ids: set[str] = set()

    for row in gold:
        test_id = row.get("test_id")
        _require(row.get("schema_version") == "miraeasset-gold-v1", f"bad schema: {test_id}")
        status = row.get("answerability")
        _require(status in ANSWERABILITY, f"invalid answerability for {test_id}: {status}")
        statuses[status] += 1
        answer = row.get("gold_answer")
        _require(isinstance(answer, str) and answer.strip(), f"empty Gold answer: {test_id}")
        for field in ("gaps", "forbidden_claims", "review_notes"):
            value = row.get(field)
            _require(isinstance(value, list), f"{test_id}.{field} must be a list")
            _require(all(isinstance(item, str) for item in value), f"bad {test_id}.{field}")

        claims = row.get("claims")
        _require(isinstance(claims, list), f"{test_id}.claims must be a list")
        if status == "supported":
            _require(claims, f"supported row must contain a claim: {test_id}")
        for claim in claims:
            _require(isinstance(claim, dict), f"invalid claim object: {test_id}")
            claim_id = claim.get("claim_id")
            _require(
                isinstance(claim_id, str) and claim_id.startswith(f"{test_id}-C"),
                f"invalid claim ID: {claim_id}",
            )
            _require(claim_id not in global_claim_ids, f"duplicate claim ID: {claim_id}")
            global_claim_ids.add(claim_id)
            _require(
                isinstance(claim.get("text"), str) and claim["text"].strip(),
                f"empty claim text: {claim_id}",
            )
            evidence_ids = claim.get("evidence_ids")
            _require(isinstance(evidence_ids, list) and evidence_ids, f"no evidence: {claim_id}")
            _require(len(evidence_ids) == len(set(evidence_ids)), f"duplicate evidence: {claim_id}")
            for evidence_id in evidence_ids:
                _require(evidence_id in evidence_by_id, f"unknown evidence: {evidence_id}")
                used_evidence.add(evidence_id)
            claim_count += 1
            evidence_reference_count += len(evidence_ids)

    _require(
        used_evidence == set(evidence_by_id),
        "evidence registry must contain exactly the evidence referenced by claims",
    )
    return statuses, claim_count, evidence_reference_count, used_evidence


def _validate_registries(
    evidence_root: dict[str, Any],
    sources_root: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], int]:
    _require(evidence_root.get("schema_version") == "docling-evidence-v1", "bad evidence schema")
    _require(sources_root.get("schema_version") == "docling-sources-v1", "bad sources schema")
    _require(evidence_root.get("dataset") == DATASET, "bad evidence dataset")
    _require(sources_root.get("dataset") == DATASET, "bad sources dataset")
    evidence_rows = evidence_root.get("evidence")
    source_rows = sources_root.get("sources")
    _require(isinstance(evidence_rows, list), "evidence registry must contain a list")
    _require(isinstance(source_rows, list), "source registry must contain a list")

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for row in evidence_rows:
        _require(isinstance(row, dict), "evidence row must be an object")
        evidence_id = row.get("evidence_id")
        _require(isinstance(evidence_id, str) and evidence_id, "evidence ID is missing")
        _require(evidence_id not in evidence_by_id, f"duplicate evidence ID: {evidence_id}")
        _require(
            isinstance(row.get("source_key"), str) and row["source_key"],
            f"missing source key: {evidence_id}",
        )
        variant = row.get("docling_variant")
        _require(variant in DOCLING_VARIANTS, f"invalid Docling variant: {evidence_id}")
        _require(ITEM_REF.fullmatch(str(row.get("item_ref"))), f"invalid item_ref: {evidence_id}")
        label = row.get("label")
        _require(isinstance(label, str) and label, f"missing label: {evidence_id}")
        _require(
            isinstance(row.get("quote"), str) and row["quote"].strip(),
            f"empty quote: {evidence_id}",
        )
        cells = _canonical_table_cells(row.get("table_cells"), evidence_id)
        if label == "table":
            _require(cells, f"table evidence requires exact cells: {evidence_id}")
        else:
            _require(not cells, f"non-table evidence cannot select table cells: {evidence_id}")

        page_no = row.get("page_no")
        bbox = row.get("bbox")
        charspan = row.get("charspan")
        if page_no is None:
            _require(bbox is None and charspan is None, f"incomplete provenance: {evidence_id}")
        else:
            _require(_is_int(page_no) and page_no > 0, f"bad page number: {evidence_id}")
            _require(isinstance(bbox, dict) and bbox, f"bad bbox: {evidence_id}")
            _require(
                isinstance(charspan, list)
                and len(charspan) == 2
                and all(_is_int(value) and value >= 0 for value in charspan)
                and charspan[0] <= charspan[1],
                f"bad charspan: {evidence_id}",
            )

        retrieval_chunks = row.get("retrieval_chunks")
        _require(isinstance(retrieval_chunks, list), f"bad retrieval: {evidence_id}")
        for index, link in enumerate(retrieval_chunks):
            _validate_retrieval_link(link, evidence_id, index)
        chunk_ids = [link["chunk_id"] for link in retrieval_chunks]
        _require(len(chunk_ids) == len(set(chunk_ids)), f"duplicate retrieval link: {evidence_id}")
        _require(
            evidence_id == _expected_evidence_id(row),
            f"evidence ID does not match canonical content: {evidence_id}",
        )
        evidence_by_id[evidence_id] = row

    sources_by_key: dict[str, dict[str, Any]] = {}
    for row in source_rows:
        _require(isinstance(row, dict), "source row must be an object")
        source_key = row.get("source_key")
        _require(isinstance(source_key, str) and source_key, "source key is missing")
        _require(source_key not in sources_by_key, f"duplicate source key: {source_key}")
        for field in ("filename", "source_sha256", "drive_id", "drive_url", "raw_relative_path"):
            _require(
                isinstance(row.get(field), str) and row[field], f"missing {source_key}.{field}"
            )
        _require(
            _is_int(row.get("size_bytes")) and row["size_bytes"] > 0, f"bad size: {source_key}"
        )
        _require(
            isinstance(row.get("collection"), str) and row["collection"],
            f"bad collection: {source_key}",
        )
        _require(
            isinstance(row.get("mime_type"), str) and row["mime_type"], f"bad MIME: {source_key}"
        )

        variants = row.get("docling_variants")
        _require(isinstance(variants, dict) and variants, f"missing Docling variants: {source_key}")
        _require(set(variants).issubset(DOCLING_VARIANTS), f"unknown Docling variant: {source_key}")
        for variant, docling in variants.items():
            _require(isinstance(docling, dict), f"bad {source_key}.{variant}")
            for field in (
                "bundle_dir",
                "bundle_id",
                "profile_id",
                "profile_digest",
                "json_filename",
                "json_sha256",
                "status",
                "relative_root",
            ):
                _require(
                    isinstance(docling.get(field), str) and docling[field],
                    f"missing {source_key}.{variant}.{field}",
                )
            _require(
                docling["relative_root"] == VARIANT_ROOTS[variant],
                f"wrong relative root: {source_key}.{variant}",
            )
            _require(docling["status"] == "success", f"variant failed: {source_key}.{variant}")
            _require(
                Path(docling["bundle_dir"]).name == docling["bundle_dir"],
                f"unsafe bundle directory: {source_key}.{variant}",
            )
            _require(
                Path(docling["json_filename"]).name == docling["json_filename"],
                f"unsafe JSON filename: {source_key}.{variant}",
            )
            if variant == "review_local_ocr":
                _require(
                    row["mime_type"] == "application/pdf", f"OCR review requires PDF: {source_key}"
                )
                _require(
                    isinstance(docling.get("purpose"), str) and docling["purpose"].strip(),
                    f"missing review purpose: {source_key}",
                )
                pages = docling.get("visually_verified_pages")
                _require(
                    isinstance(pages, list)
                    and pages
                    and all(_is_int(page) and page > 0 for page in pages),
                    f"bad visually verified pages: {source_key}",
                )
                _require(
                    pages == sorted(set(pages)),
                    f"visually verified pages must be sorted and unique: {source_key}",
                )
        if "review_local_ocr" in variants:
            _require(
                "delivery" in variants,
                f"OCR review source must retain its delivery variant: {source_key}",
            )
        sources_by_key[source_key] = row

    retrieval_links = 0
    referenced_sources: set[str] = set()
    for evidence_id, row in evidence_by_id.items():
        source_key = row.get("source_key")
        _require(source_key in sources_by_key, f"unknown source for {evidence_id}: {source_key}")
        variant = row["docling_variant"]
        source = sources_by_key[source_key]
        _require(
            variant in source["docling_variants"],
            f"source variant missing for {evidence_id}: {variant}",
        )
        if variant == "review_local_ocr":
            pages = source["docling_variants"][variant]["visually_verified_pages"]
            _require(
                row["page_no"] in pages,
                f"OCR evidence page was not visually verified: {evidence_id}",
            )
        referenced_sources.add(source_key)
        retrieval_links += len(row["retrieval_chunks"])
    _require(
        referenced_sources == set(sources_by_key),
        "source registry must contain exactly the sources used by evidence",
    )
    return evidence_by_id, sources_by_key, retrieval_links


def _validate_manifest_counts(
    manifest: dict[str, Any],
    gold: list[dict[str, Any]],
    statuses: Counter[str],
    claim_count: int,
    evidence_reference_count: int,
    evidence_count: int,
    source_count: int,
    retrieval_links: int,
    review_local_ocr_evidence: int,
    review_local_ocr_sources: int,
) -> None:
    counts = manifest.get("counts", {})
    expected = {
        "questions": len(gold),
        "claims": claim_count,
        "evidence": evidence_count,
        "evidence_references": evidence_reference_count,
        "sources": source_count,
        "retrieval_links": retrieval_links,
        "review_local_ocr_evidence": review_local_ocr_evidence,
        "review_local_ocr_sources": review_local_ocr_sources,
    }
    for name, value in expected.items():
        _require(counts.get(name) == value, f"manifest count mismatch: {name}")
    _require(
        counts.get("by_answerability") == dict(sorted(statuses.items())), "status count mismatch"
    )


def _row_evidence_ids(row: dict[str, Any]) -> list[str]:
    return list(
        dict.fromkeys(
            evidence_id for claim in row["claims"] for evidence_id in claim["evidence_ids"]
        )
    )


def _split_markdown_table_row(line: str, context: str) -> list[str]:
    _require(line.startswith("|") and line.endswith("|"), f"malformed Markdown row: {context}")
    body = line[1:-1]
    cells: list[str] = []
    start = 0
    for index, character in enumerate(body):
        if character != "|":
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and body[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            cells.append(body[start:index].strip())
            start = index + 1
    cells.append(body[start:].strip())
    _require(len(cells) == 7, f"Markdown row must contain exactly 7 columns: {context}")
    return cells


def _validate_claim_column(value: str, row: dict[str, Any]) -> None:
    test_id = row["test_id"]
    claims = row["claims"]
    if not claims:
        _require(value == "직접 확정할 필수 주장 없음", f"Gold table claims mismatch: {test_id}")
        return
    blocks = value.split("<br><br>")
    _require(len(blocks) == len(claims), f"Gold table claim block count mismatch: {test_id}")
    for index, (block, claim) in enumerate(zip(blocks, claims, strict=True), 1):
        heading, separator, evidence_text = block.partition("<br>근거: ")
        _require(separator, f"Gold table claim block is malformed: {test_id} block {index}")
        match = re.fullmatch(
            r"\*\*((?:MA-(?:PP|RP|ISA)-\d{3})-C\d+)\*\* (.*)",
            heading,
        )
        _require(match is not None, f"Gold table claim heading is malformed: {test_id}")
        actual_evidence_ids = evidence_text.split(", ")
        _require(match.group(1) == claim["claim_id"], f"Gold table claim ID mismatch: {test_id}")
        _require(
            match.group(2) == _markdown_text(claim["text"]),
            f"Gold table claim text mismatch: {claim['claim_id']}",
        )
        _require(
            actual_evidence_ids == claim["evidence_ids"],
            f"Gold table claim evidence mismatch: {claim['claim_id']}",
        )


def _expected_evidence_block(
    evidence: dict[str, Any],
    source: dict[str, Any],
) -> str:
    evidence_id = evidence["evidence_id"]
    variant = source["docling_variants"][evidence["docling_variant"]]
    result = (
        f"**{evidence_id}** — [{_markdown_text(source['filename'])}]({source['drive_url']})"
        f"<br>`{evidence['item_ref']}` · label `{evidence['label']}` · "
        f"variant `{evidence['docling_variant']}`"
    )
    if evidence["page_no"] is None:
        result += (
            "<br>페이지 provenance 없음; "
            f"source SHA-256 `{source['source_sha256']}` · "
            f"Docling JSON SHA-256 `{variant['json_sha256']}`"
        )
    else:
        charspan = evidence["charspan"]
        result += (
            f"<br>page/slide `{evidence['page_no']}`; "
            f"charspan `{charspan[0]}:{charspan[1]}`; "
            f"bbox `{_markdown_text(_json_compact(evidence['bbox']))}`"
        )
    if evidence["table_cells"]:
        labels = ", ".join(_table_cell_label(cell) for cell in evidence["table_cells"])
        result += f"<br>table cells `{labels}`"
    if evidence["retrieval_chunks"]:
        chunks = ", ".join(link["chunk_id"] for link in evidence["retrieval_chunks"])
        result += f"<br>retrieval `{chunks}`"
    return result + f"<br>인용: “{_markdown_text(evidence['quote'])}”"


def _validate_evidence_column(
    value: str,
    row: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
    sources_by_key: dict[str, dict[str, Any]],
) -> None:
    test_id = row["test_id"]
    expected_ids = _row_evidence_ids(row)
    if not expected_ids:
        _require(
            value == "직접 인용할 제공 문서 근거 없음",
            f"Gold table evidence mismatch: {test_id}",
        )
        return
    blocks = value.split("<br><br>")
    _require(
        len(blocks) == len(expected_ids),
        f"Gold table evidence block count mismatch: {test_id}",
    )
    actual_ids: list[str] = []
    for index, block in enumerate(blocks, 1):
        match = re.match(r"^\*\*(E-[A-Z0-9-]+)\*\* — ", block)
        _require(
            match is not None, f"Gold table evidence block is malformed: {test_id} block {index}"
        )
        actual_ids.append(match.group(1))
    _require(actual_ids == expected_ids, f"Gold table evidence order mismatch: {test_id}")
    for evidence_id, block in zip(expected_ids, blocks, strict=True):
        evidence = evidence_by_id[evidence_id]
        source = sources_by_key[evidence["source_key"]]
        _require(
            block == _expected_evidence_block(evidence, source),
            f"Gold table evidence block mismatch: {evidence_id}",
        )


def _expected_gap_column(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for field, heading in (
        ("gaps", "부족 근거"),
        ("forbidden_claims", "금지 주장"),
        ("review_notes", "검토 메모"),
    ):
        if row[field]:
            values = "<br>".join(f"• {_markdown_text(value)}" for value in row[field])
            parts.append(f"**{heading}**<br>{values}")
    return "<br><br>".join(parts) or "없음"


def _validate_table_markdown(
    path: Path,
    gold: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    sources_by_key: dict[str, dict[str, Any]],
) -> None:
    text = path.read_text(encoding="utf-8")
    _require(
        text.startswith("# PR #130 미래에셋 실제 FAQ 86문항 Gold Answer 표\n"),
        "Gold table title mismatch",
    )
    parsed_rows: list[list[str]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if line.startswith("|"):
            parsed_rows.append(_split_markdown_table_row(line, f"{path}:{line_number}"))
    header = [
        "ID",
        "질문",
        "근거충분도",
        "목표 답변",
        "필수 주장",
        "문서 내 정확한 근거 위치",
        "부족 근거·금지 주장",
    ]
    divider = ["---"] * 7
    _require(parsed_rows.count(header) == 3, "Gold table header count mismatch")
    _require(parsed_rows.count(divider) == 3, "Gold table divider count mismatch")
    _require(len(parsed_rows) == len(gold) + 6, "Gold table contains an unexpected row")
    rows = [cells for cells in parsed_rows if re.fullmatch(r"MA-(?:PP|RP|ISA)-\d{3}", cells[0])]
    _require(
        [cells[0] for cells in rows] == [row["test_id"] for row in gold],
        "Gold table ID/order mismatch",
    )

    for gold_row, cells in zip(gold, rows, strict=True):
        test_id = gold_row["test_id"]
        _require(cells[0] == test_id, f"Gold table ID mismatch: {test_id}")
        _require(
            cells[1] == _markdown_text(gold_row["question"]),
            f"Gold table question mismatch: {test_id}",
        )
        _require(
            cells[2] == STATUS_KO[gold_row["answerability"]],
            f"Gold table status mismatch: {test_id}",
        )
        _require(
            cells[3] == _markdown_text(gold_row["gold_answer"]),
            f"Gold table answer mismatch: {test_id}",
        )
        _validate_claim_column(cells[4], gold_row)
        _validate_evidence_column(cells[5], gold_row, evidence_by_id, sources_by_key)
        _require(
            cells[6] == _expected_gap_column(gold_row),
            f"Gold table gap/restriction mismatch: {test_id}",
        )


def _validate_review_markdown(
    path: Path,
    manifest: dict[str, Any],
    sources_by_key: dict[str, dict[str, Any]],
    statuses: Counter[str],
    claim_count: int,
    evidence_reference_count: int,
    evidence_count: int,
    source_count: int,
    retrieval_links: int,
) -> None:
    text = path.read_text(encoding="utf-8")
    _require(
        text.startswith("# PR #130 미래에셋 실제 FAQ 86문항 Gold Answer 구축 보고서\n"),
        "Gold review title mismatch",
    )
    for status in ("supported", "partial", "unsupported", "temporal_gap"):
        _require(
            f"| `{status}` | {statuses.get(status, 0)} |" in text,
            f"Gold review status mismatch: {status}",
        )
    _require(f"| 합계 | {sum(statuses.values())} |" in text, "Gold review total mismatch")
    for fragment in (
        f"필수 주장 {claim_count}개",
        f"고유 Docling 근거 {evidence_count}개",
        f"문항별 근거 참조 {evidence_reference_count}개",
        f"출처는 {source_count}개",
        f"retrieval chunk 연결은 {retrieval_links}개",
    ):
        _require(fragment in text, f"Gold review count mismatch: {fragment}")

    artifacts = manifest["artifacts"]
    for name in ("gold", "evidence", "sources", "table"):
        filename = Path(artifacts[name]["path"]).name
        _require(f"({filename})" in text, f"Gold review artifact link mismatch: {name}")

    delivery = manifest["corpus"]["docling_delivery"]
    retrieval = manifest["corpus"]["retrieval"]
    for fragment in (
        f"`{delivery['archive_name']}`",
        f"`{delivery['sha256']}`",
        f"{delivery['size_bytes']:,} bytes",
        f"{delivery['bundle_count']}개, 모두 `status=success`",
        f"`{retrieval['collection']}`, {retrieval['points']:,} points",
        f"`{retrieval['manifest_sha256']}`",
        f"`{retrieval['chunks_sha256']}`",
    ):
        _require(fragment in text, f"Gold review corpus metadata mismatch: {fragment}")

    review_sources = [
        source
        for source in sources_by_key.values()
        if "review_local_ocr" in source["docling_variants"]
    ]
    review_section = text.partition("## Parser drift와 원본 PDF 시각 대조")[2].partition("\n## ")[0]
    _require(review_section, "Gold review OCR section is missing")
    review_rows = [line for line in review_section.splitlines() if line.startswith("| `")]
    _require(len(review_rows) == len(review_sources), "Gold review OCR source count mismatch")
    for source in review_sources:
        variants = source["docling_variants"]
        delivery_variant = variants["delivery"]
        review_variant = variants["review_local_ocr"]
        pages = ", ".join(str(page) for page in review_variant["visually_verified_pages"])
        expected_row = (
            f"| `{source['filename']}` | `{delivery_variant['profile_id']}` | "
            f"`{review_variant['profile_id']}` | {pages} |"
        )
        _require(
            expected_row in review_section,
            f"Gold review OCR metadata mismatch: {source['source_key']}",
        )


def _validate_markdown_artifacts(
    paths: dict[str, Path],
    manifest: dict[str, Any],
    gold: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    sources_by_key: dict[str, dict[str, Any]],
    statuses: Counter[str],
    claim_count: int,
    evidence_reference_count: int,
    retrieval_links: int,
) -> None:
    _validate_table_markdown(paths["table"], gold, evidence_by_id, sources_by_key)
    _validate_review_markdown(
        paths["review"],
        manifest,
        sources_by_key,
        statuses,
        claim_count,
        evidence_reference_count,
        len(evidence_by_id),
        len(sources_by_key),
        retrieval_links,
    )


def _resolve_item(document: dict[str, Any], item_ref: str) -> dict[str, Any]:
    match = ITEM_REF.match(item_ref)
    _require(match is not None, f"invalid Docling item reference: {item_ref}")
    collection, index_text = match.groups()
    values = document.get(collection)
    _require(isinstance(values, list), f"Docling collection is missing: {collection}")
    index = int(index_text)
    _require(index < len(values), f"Docling item is out of range: {item_ref}")
    item = values[index]
    _require(isinstance(item, dict), f"Docling item must be an object: {item_ref}")
    _require(item.get("self_ref") == item_ref, f"Docling self_ref mismatch: {item_ref}")
    return item


def _matching_cell(table: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any] | None:
    cells = table.get("data", {}).get("table_cells", [])
    keys = (
        ("start_row", "start_row_offset_idx"),
        ("end_row", "end_row_offset_idx"),
        ("start_col", "start_col_offset_idx"),
        ("end_col", "end_col_offset_idx"),
    )
    matching = [
        cell for cell in cells if all(expected.get(short) == cell.get(long) for short, long in keys)
    ]
    _require(len(matching) <= 1, f"duplicate raw table cell coordinates: {expected}")
    return matching[0] if matching else None


def _item_text(item: dict[str, Any], table_cells: list[dict[str, Any]]) -> str:
    if item.get("label") != "table":
        _require(
            not table_cells, f"non-table item cannot select table cells: {item.get('self_ref')}"
        )
        return str(item.get("text", ""))
    _require(table_cells, f"table item requires exact cells: {item.get('self_ref')}")
    selected: list[str] = []
    for expected in table_cells:
        cell = _matching_cell(item, expected)
        _require(cell is not None, f"table cell not found: {expected}")
        _require(
            expected["text"] == cell.get("text", ""),
            f"table cell text mismatch: {expected}",
        )
        selected.append(str(cell.get("text", "")))
    return " ".join(selected)


def _validate_provenance(item: dict[str, Any], evidence: dict[str, Any]) -> None:
    page_no = evidence.get("page_no")
    bbox = evidence.get("bbox")
    charspan = evidence.get("charspan")
    candidates = item.get("prov", [])
    _require(isinstance(candidates, list), f"bad raw provenance: {evidence['evidence_id']}")
    if not candidates:
        _require(bbox is None and charspan is None, "bbox/charspan require page provenance")
        _require(page_no is None, f"page provenance absent in source: {evidence['evidence_id']}")
        return
    _require(
        page_no is not None and bbox is not None and charspan is not None,
        f"raw provenance must be retained: {evidence['evidence_id']}",
    )
    _require(
        any(
            prov.get("page_no") == page_no
            and prov.get("bbox") == bbox
            and prov.get("charspan") == charspan
            for prov in candidates
        ),
        f"page/bbox/charspan mismatch: {evidence['evidence_id']}",
    )


def _inventory_raw_path(drive: dict[str, Any]) -> str:
    collection = drive.get("collection")
    if collection == "docs":
        return f"raw/formula_sources/docs/docs_renamed/{drive['title']}"
    _require(collection == "investment_prospectus", f"unknown inventory collection: {collection}")
    return f"raw/formula_sources/investment_prospectus/{drive['parent_title']}/{drive['title']}"


def _validate_inventory(
    data_root: Path,
    delivery: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    inventory = _read_json(data_root / "raw" / "formula_source_inventory.json")
    _require(isinstance(inventory, dict), "source inventory must be an object")
    files = inventory.get("files")
    _require(isinstance(files, list), "source inventory files must be a list")
    _require(
        len(files) == delivery.get("bundle_count") == 158,
        "source inventory and delivery must contain exactly 158 files",
    )
    drive_by_id: dict[str, dict[str, Any]] = {}
    titles: set[str] = set()
    for row in files:
        _require(isinstance(row, dict), "source inventory row must be an object")
        drive_id = row.get("id")
        title = row.get("title")
        _require(isinstance(drive_id, str) and drive_id, "source inventory ID is missing")
        _require(drive_id not in drive_by_id, f"duplicate source inventory ID: {drive_id}")
        _require(isinstance(title, str) and title, f"source inventory title is missing: {drive_id}")
        _require(title not in titles, f"duplicate source inventory title: {title}")
        _require(_is_int(row.get("size")) and row["size"] > 0, f"bad source size: {title}")
        _require(isinstance(row.get("url"), str) and row["url"], f"bad source URL: {title}")
        _require(
            isinstance(row.get("mime_type"), str) and row["mime_type"],
            f"bad source MIME: {title}",
        )
        _inventory_raw_path(row)
        drive_by_id[drive_id] = row
        titles.add(title)
    return files, drive_by_id


def _validate_bundle(
    data_root: Path,
    source_key: str,
    source: dict[str, Any],
    variant: str,
    docling_meta: dict[str, Any],
) -> tuple[dict[str, Any], Path, Path]:
    bundle = data_root / docling_meta["relative_root"] / docling_meta["bundle_dir"]
    manifest_path = bundle / "manifest.json"
    document_path = bundle / docling_meta["json_filename"]
    _require(manifest_path.is_file(), f"bundle manifest is missing: {source_key}.{variant}")
    _require(document_path.is_file(), f"Docling JSON is missing: {source_key}.{variant}")
    bundle_manifest = _read_json(manifest_path)
    _require(bundle_manifest.get("status") == "success", f"bundle failed: {source_key}.{variant}")
    _require(
        bundle_manifest.get("status") == docling_meta["status"],
        f"bundle status mismatch: {source_key}.{variant}",
    )
    _require(
        bundle_manifest.get("bundle_id") == docling_meta["bundle_id"],
        f"bundle ID mismatch: {source_key}.{variant}",
    )
    bundle_source = bundle_manifest.get("source", {})
    _require(
        bundle_source.get("filename") == source["filename"],
        f"bundle filename mismatch: {source_key}.{variant}",
    )
    _require(
        bundle_source.get("size_bytes") == source["size_bytes"],
        f"bundle source size mismatch: {source_key}.{variant}",
    )
    _require(
        bundle_source.get("sha256") == source["source_sha256"],
        f"bundle source mismatch: {source_key}.{variant}",
    )
    profile = bundle_manifest.get("profile", {})
    _require(
        profile.get("id") == docling_meta["profile_id"],
        f"profile mismatch: {source_key}.{variant}",
    )
    _require(
        profile.get("digest") == docling_meta["profile_digest"],
        f"profile digest mismatch: {source_key}.{variant}",
    )
    artifacts = bundle_manifest.get("artifacts", {})
    _require(
        artifacts.get("docling_json") == docling_meta["json_filename"],
        f"bundle Docling filename mismatch: {source_key}.{variant}",
    )
    _require(
        artifacts.get("docling_json_sha256") == docling_meta["json_sha256"],
        f"bundle Docling hash mismatch: {source_key}.{variant}",
    )
    _require(
        _sha256(document_path) == docling_meta["json_sha256"],
        f"Docling hash mismatch: {source_key}.{variant}",
    )

    if variant == "review_local_ocr":
        total_pages = bundle_manifest.get("stats", {}).get("pages")
        _require(_is_int(total_pages) and total_pages > 0, f"bad PDF page count: {source_key}")
        pages = docling_meta["visually_verified_pages"]
        _require(max(pages) <= total_pages, f"visual review page is out of range: {source_key}")

    return _read_json(document_path), manifest_path, document_path


def _validate_delivery_archive(
    archive: Path,
    delivery: dict[str, Any],
    inventory_files: list[dict[str, Any]],
    loose_files: dict[str, Path],
) -> None:
    prefix = PurePosixPath("data") / VARIANT_ROOTS["delivery"]
    prefix_parts = prefix.parts
    required_members = set(loose_files)
    matched_required: set[str] = set()
    seen_members: set[str] = set()
    manifest_bundles: set[str] = set()
    document_bundles: set[str] = set()
    successful_bundles = 0
    archive_sources: set[tuple[str, int]] = set()

    try:
        with tarfile.open(archive, "r:gz") as handle:
            for member in handle:
                member_name = str(PurePosixPath(member.name))
                parts = PurePosixPath(member_name).parts
                is_bundle_file = (
                    len(parts) == len(prefix_parts) + 2
                    and parts[: len(prefix_parts)] == prefix_parts
                )
                if not is_bundle_file:
                    continue
                bundle_dir, filename = parts[-2:]
                is_manifest = filename == "manifest.json"
                is_document = filename == "document.docling.json"
                is_required = member_name in required_members
                if not (is_manifest or is_document or is_required):
                    continue
                _require(member.isfile(), f"archive member is not a file: {member_name}")
                _require(
                    member_name not in seen_members, f"duplicate archive member: {member_name}"
                )
                seen_members.add(member_name)
                if is_document:
                    _require(
                        bundle_dir not in document_bundles,
                        f"duplicate archived Docling JSON: {bundle_dir}",
                    )
                    document_bundles.add(bundle_dir)
                payload: bytes | None = None
                if is_manifest or is_required:
                    extracted = handle.extractfile(member)
                    _require(extracted is not None, f"cannot read archive member: {member_name}")
                    payload = extracted.read()
                if is_manifest:
                    _require(
                        bundle_dir not in manifest_bundles,
                        f"duplicate archive bundle: {bundle_dir}",
                    )
                    manifest_bundles.add(bundle_dir)
                    try:
                        assert payload is not None
                        archived_manifest = json.loads(payload)
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise ValidationError(f"invalid archived manifest: {bundle_dir}") from exc
                    successful_bundles += archived_manifest.get("status") == "success"
                    archived_source = archived_manifest.get("source", {})
                    filename_value = archived_source.get("filename")
                    size_value = archived_source.get("size_bytes")
                    _require(
                        isinstance(filename_value, str) and _is_int(size_value),
                        f"bad archived source metadata: {bundle_dir}",
                    )
                    archive_sources.add((filename_value, size_value))
                if is_required:
                    assert payload is not None
                    _require(
                        payload == loose_files[member_name].read_bytes(),
                        f"loose bundle differs from fixed archive: {member_name}",
                    )
                    matched_required.add(member_name)
    except (tarfile.TarError, OSError) as exc:
        raise ValidationError(f"cannot validate Docling delivery archive: {archive}") from exc

    expected_count = delivery["bundle_count"]
    _require(len(manifest_bundles) == expected_count, "archive bundle count mismatch")
    _require(document_bundles == manifest_bundles, "archive Docling JSON inventory mismatch")
    _require(
        successful_bundles == delivery["successful_bundles"],
        "archive successful bundle count mismatch",
    )
    inventory_sources = {(row["title"], row["size"]) for row in inventory_files}
    _require(archive_sources == inventory_sources, "archive and source inventory differ")
    _require(matched_required == required_members, "used delivery member is missing from archive")


def _validate_sources(
    data_root: Path,
    manifest: dict[str, Any],
    sources_by_key: dict[str, dict[str, Any]],
) -> tuple[
    dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]],
    int,
]:
    delivery = _validate_delivery_metadata(manifest)
    archive = data_root / delivery["archive_relative_path"]
    _require(archive.is_file(), f"Docling delivery archive is missing: {archive}")
    _require(archive.stat().st_size == delivery["size_bytes"], "archive size mismatch")
    _require(_sha256(archive) == delivery["sha256"], "archive hash mismatch")

    inventory_files, drive_by_id = _validate_inventory(data_root, delivery)
    documents: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]] = {}
    loose_delivery_files: dict[str, Path] = {}
    for source_key, source in sources_by_key.items():
        drive = drive_by_id.get(source["drive_id"])
        _require(drive is not None, f"Drive inventory entry missing: {source_key}")
        _require(drive["title"] == source["filename"], f"Drive filename mismatch: {source_key}")
        _require(drive["url"] == source["drive_url"], f"Drive URL mismatch: {source_key}")
        _require(drive["size"] == source["size_bytes"], f"Drive size mismatch: {source_key}")
        _require(
            drive["collection"] == source["collection"], f"Drive collection mismatch: {source_key}"
        )
        _require(drive["mime_type"] == source["mime_type"], f"Drive MIME mismatch: {source_key}")
        _require(
            source["raw_relative_path"] == _inventory_raw_path(drive),
            f"raw source path mismatch: {source_key}",
        )

        raw_path = data_root / source["raw_relative_path"]
        _require(raw_path.is_file(), f"original source is missing: {raw_path}")
        _require(
            raw_path.stat().st_size == source["size_bytes"], f"source size mismatch: {source_key}"
        )
        _require(
            _sha256(raw_path) == source["source_sha256"], f"source hash mismatch: {source_key}"
        )

        for variant, docling_meta in source["docling_variants"].items():
            document, manifest_path, document_path = _validate_bundle(
                data_root,
                source_key,
                source,
                variant,
                docling_meta,
            )
            documents[(source_key, variant)] = (source, document)
            if variant == "delivery":
                archive_base = PurePosixPath("data") / docling_meta["relative_root"]
                archive_base /= docling_meta["bundle_dir"]
                for filename, path in (
                    ("manifest.json", manifest_path),
                    (docling_meta["json_filename"], document_path),
                ):
                    member_name = str(archive_base / filename)
                    _require(
                        member_name not in loose_delivery_files,
                        f"duplicate delivery archive member: {member_name}",
                    )
                    loose_delivery_files[member_name] = path

    _validate_delivery_archive(
        archive,
        delivery,
        inventory_files,
        loose_delivery_files,
    )
    return documents, len(inventory_files)


def _validate_evidence_content(
    evidence_by_id: dict[str, dict[str, Any]],
    documents: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    for evidence in evidence_by_id.values():
        document_key = (evidence["source_key"], evidence["docling_variant"])
        _require(document_key in documents, f"Docling variant was not loaded: {document_key}")
        source, document = documents[document_key]
        item = _resolve_item(document, evidence["item_ref"])
        _require(
            item.get("label") == evidence.get("label"), f"label mismatch: {evidence['evidence_id']}"
        )
        _validate_provenance(item, evidence)
        searchable = _normalize_text(_item_text(item, evidence["table_cells"]))
        quote = _normalize_text(evidence["quote"])
        _require(quote in searchable, f"quote not found in Docling item: {evidence['evidence_id']}")
        _require(source["source_key"] == evidence["source_key"], "internal source mismatch")


def _validate_retrieval(
    data_root: Path,
    manifest: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
    inventory_count: int,
) -> None:
    retrieval_meta = manifest["corpus"]["retrieval"]
    manifest_path = data_root / retrieval_meta["manifest_relative_path"]
    chunks_path = data_root / retrieval_meta["chunks_relative_path"]
    _require(manifest_path.is_file(), f"retrieval manifest is missing: {manifest_path}")
    _require(chunks_path.is_file(), f"retrieval chunks are missing: {chunks_path}")
    _require(
        _sha256(manifest_path) == retrieval_meta["manifest_sha256"],
        "retrieval manifest hash mismatch",
    )
    _require(
        _sha256(chunks_path) == retrieval_meta["chunks_sha256"], "retrieval chunks hash mismatch"
    )
    retrieval_manifest = _read_json(manifest_path)
    _require(
        retrieval_manifest.get("collection_name") == retrieval_meta.get("collection"),
        "retrieval collection mismatch",
    )
    retrieval_counts = retrieval_manifest.get("counts", {})
    _require(
        retrieval_counts.get("points") == retrieval_meta.get("points"),
        "retrieval point count mismatch",
    )
    _require(
        retrieval_counts.get("sources") == inventory_count,
        "retrieval source count mismatch",
    )
    inputs = retrieval_manifest.get("inputs", {})
    _require(
        inputs.get("chunks", {}).get("sha256") == retrieval_meta["chunks_sha256"],
        "retrieval input chunk hash mismatch",
    )

    source_rows: list[dict[str, Any]] = []
    source_manifest_records = inputs.get("source_manifests")
    _require(isinstance(source_manifest_records, list), "retrieval source manifests are missing")
    source_manifest_names: set[str] = set()
    for record in source_manifest_records:
        _require(isinstance(record, dict), "bad retrieval source manifest record")
        original_path = record.get("path")
        expected_hash = record.get("sha256")
        _require(isinstance(original_path, str) and original_path, "bad retrieval source path")
        filename = Path(original_path).name
        _require(filename not in source_manifest_names, f"duplicate source manifest: {filename}")
        source_manifest_names.add(filename)
        source_path = chunks_path.parent / filename
        _require(source_path.is_file(), f"retrieval source manifest is missing: {filename}")
        _require(
            _sha256(source_path) == expected_hash, f"source manifest hash mismatch: {filename}"
        )
        source_rows.extend(_read_jsonl(source_path))
    source_ids = [row.get("source_id") for row in source_rows]
    _require(len(source_rows) == inventory_count, "retrieval source row count mismatch")
    _require(len(source_ids) == len(set(source_ids)), "duplicate retrieval source ID")

    chunk_rows = _read_jsonl(chunks_path)
    _require(len(chunk_rows) == retrieval_meta["points"], "retrieval chunk row count mismatch")
    canonical_documents = {row.get("canonical_doc_id") for row in chunk_rows}
    _require(
        len(canonical_documents) == retrieval_counts.get("canonical_documents"),
        "retrieval canonical document count mismatch",
    )
    chunks: dict[str, dict[str, Any]] = {}
    for row in chunk_rows:
        chunk_id = row.get("chunk_id")
        _require(isinstance(chunk_id, str) and chunk_id, "retrieval chunk ID is missing")
        _require(chunk_id not in chunks, f"duplicate retrieval chunk: {chunk_id}")
        chunk_text = row.get("text")
        content_hash = row.get("content_hash")
        _require(isinstance(chunk_text, str), f"retrieval chunk text is missing: {chunk_id}")
        _require(
            isinstance(content_hash, str) and SHA256_HEX.fullmatch(content_hash),
            f"bad retrieval chunk content hash: {chunk_id}",
        )
        expected_content_hash = hashlib.sha256(chunk_text.encode()).hexdigest()
        _require(
            content_hash == expected_content_hash,
            f"retrieval chunk content hash mismatch: {chunk_id}",
        )
        chunks[chunk_id] = row
    for evidence in evidence_by_id.values():
        for link in evidence["retrieval_chunks"]:
            chunk = chunks.get(link.get("chunk_id"))
            _require(chunk is not None, f"retrieval chunk missing: {link.get('chunk_id')}")
            for field in ("canonical_doc_id", "content_hash", "page_start", "page_end"):
                _require(chunk.get(field) == link.get(field), f"retrieval {field} mismatch")
            source_ids = chunk.get("metadata", {}).get("source_ids", [])
            _require(evidence["source_key"] in source_ids, "retrieval source mismatch")
            _require(
                link.get("match_method") == "quote_substring", "unknown retrieval match method"
            )
            _require(
                _normalize_text(evidence["quote"]) in _normalize_text(chunk["text"]),
                f"quote not found in retrieval chunk: {evidence['evidence_id']}",
            )


def validate_dataset(
    repo_root: Path,
    *,
    structure_only: bool = False,
    data_root: Path | None = None,
) -> dict[str, Any]:
    """Validate all committed artifacts and optionally the ignored source corpus."""

    manifest_path = repo_root / "evals" / "gold" / f"{DATASET}.manifest.json"
    manifest = _read_json(manifest_path)
    _require(manifest.get("schema_version") == "miraeasset-gold-manifest-v1", "bad manifest schema")
    _require(manifest.get("dataset") == DATASET, "bad manifest dataset")
    _validate_delivery_metadata(manifest)
    paths = _artifact_paths(repo_root, manifest)
    gold = _read_jsonl(paths["gold"])
    evidence_root = _read_json(paths["evidence"])
    sources_root = _read_json(paths["sources"])
    evidence_by_id, sources_by_key, retrieval_links = _validate_registries(
        evidence_root,
        sources_root,
    )
    _validate_questions(repo_root, manifest, gold)
    statuses, claims, evidence_references, _ = _validate_gold(gold, evidence_by_id)
    review_local_ocr_evidence = sum(
        row["docling_variant"] == "review_local_ocr" for row in evidence_by_id.values()
    )
    review_local_ocr_sources = sum(
        "review_local_ocr" in row["docling_variants"] for row in sources_by_key.values()
    )
    _validate_manifest_counts(
        manifest,
        gold,
        statuses,
        claims,
        evidence_references,
        len(evidence_by_id),
        len(sources_by_key),
        retrieval_links,
        review_local_ocr_evidence,
        review_local_ocr_sources,
    )
    _validate_markdown_artifacts(
        paths,
        manifest,
        gold,
        evidence_by_id,
        sources_by_key,
        statuses,
        claims,
        evidence_references,
        retrieval_links,
    )

    if not structure_only:
        _require(data_root is not None, "full validation requires --data-root")
        documents, inventory_count = _validate_sources(data_root, manifest, sources_by_key)
        _validate_evidence_content(evidence_by_id, documents)
        _validate_retrieval(data_root, manifest, evidence_by_id, inventory_count)

    return {
        "answerability": dict(sorted(statuses.items())),
        "claims": claims,
        "evidence": len(evidence_by_id),
        "evidence_references": evidence_references,
        "mode": "structure-only" if structure_only else "full",
        "questions": len(gold),
        "retrieval_links": retrieval_links,
        "review_local_ocr_evidence": review_local_ocr_evidence,
        "review_local_ocr_sources": review_local_ocr_sources,
        "sources": len(sources_by_key),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--structure-only", action="store_true")
    mode.add_argument("--data-root", type=Path)
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    summary = validate_dataset(
        repo_root,
        structure_only=args.structure_only or args.data_root is None,
        data_root=args.data_root,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
