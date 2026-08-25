"""Docling bundle에서 계산식·계산 규칙 후보를 구조화해 추출한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_EXPLICIT_EQUATION_RE = re.compile(
    r"\b(?:MIN|MAX)\s*\(|(?<=[\w가-힣)%])\s*=\s*(?=[\w가-힣(])|"
    r"(?<=[\w가-힣)%])\s+(?:\+|-|\*|/)\s+(?=[\w가-힣(])",
    re.IGNORECASE,
)
_CALCULATION_KEYWORD_RE = re.compile(
    r"산식|계산식|계산\s*방법|산출\s*방법|산출식|산출액|계산(?:한|하여|되는|된|한다)|"
    r"곱(?:한|하여|한다)|나누(?:어|는)|차감|합산|공제|환산|적용률|수익률|비율|한도|"
    r"세율|과세표준|기준가격|평가금액|부담금"
)
_CONDITION_RE = re.compile(r"초과|이하|미만|이상|구간|경우|때에는|중\s*(?:작은|큰)\s*금액")
_RATE_ACTION_RE = re.compile(
    r"적용|과세|공제|수수료|보수|세액|세금|납부|환급|원천징수|감면|할인|가산"
)
_NUMERIC_TERM_RE = re.compile(
    r"(?<![\w.])\d[\d,]*(?:\.\d+)?\s*(?:%|퍼센트|원|만원|억원|조원|년|개월|월|일|세|회|배)?"
)
_OPERATOR_RE = re.compile(
    r"(?:<=|>=|==|(?<=[\w가-힣)%])\s*(?:=|×|÷|\*|\+|−|–|—|/)\s*(?=[\w가-힣(])|\bMIN\b|\bMAX\b)",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|(?=[①-⑳])")
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("−", "-").replace("–", "-").replace("—", "-")
    normalized = normalized.replace("÷", " / ").replace("×", " * ")
    return re.sub(r"\s+", " ", normalized).strip()


def _fingerprint(text: str) -> str:
    compact = re.sub(r"\s+", "", _normalize(text)).casefold()
    return hashlib.sha256(compact.encode("utf-8")).hexdigest()


def _signals(text: str, *, label: str) -> tuple[str | None, dict[str, list[str]]]:
    normalized = _normalize(text)
    signal_text = _URL_RE.sub("", normalized)
    keywords = sorted(set(_CALCULATION_KEYWORD_RE.findall(signal_text)))
    numeric_terms = _NUMERIC_TERM_RE.findall(signal_text)
    operators = sorted(set(_OPERATOR_RE.findall(signal_text)), key=str.casefold)
    meaningful_numeric = len(numeric_terms) >= 2 or any(
        re.search(r"%|퍼센트|원|년|개월|월|일|세|회|배", term) for term in numeric_terms
    )

    if label == "formula":
        kind = "docling_formula"
    elif _EXPLICIT_EQUATION_RE.search(signal_text):
        kind = "explicit_equation"
    elif "%" in signal_text and (
        _RATE_ACTION_RE.search(signal_text) or _CONDITION_RE.search(signal_text)
    ):
        kind = "rate_or_threshold_rule"
    elif _CALCULATION_KEYWORD_RE.search(signal_text) and (
        meaningful_numeric or operators or re.search(r"중\s*(?:작은|큰)\s*금액", signal_text)
    ):
        kind = "calculation_rule"
    else:
        kind = None
    return kind, {
        "keywords": keywords,
        "numeric_terms": numeric_terms,
        "operators": operators,
    }


def _segments(text: str) -> Iterable[str]:
    normalized = _normalize(text)
    if len(normalized) <= 280:
        yield normalized
        return
    parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(normalized) if part.strip()]
    yield from parts or [normalized]


def _location(item: dict[str, Any]) -> dict[str, Any]:
    prov = item.get("prov") or []
    first = prov[0] if prov else {}
    return {
        "self_ref": item.get("self_ref"),
        "label": item.get("label"),
        "page_no": first.get("page_no"),
        "bbox": first.get("bbox"),
    }


def _candidate(
    *,
    kind: str,
    evidence_text: str,
    context_text: str,
    signals: dict[str, list[str]],
    manifest: dict[str, Any],
    bundle_dir: Path,
    inventory_item: dict[str, Any] | None,
    location: dict[str, Any],
    section: str | None,
    table_row_index: int | None = None,
) -> dict[str, Any]:
    normalized = _normalize(evidence_text)
    source = manifest["source"]
    identity = "|".join(
        (
            source["sha256"],
            str(location.get("self_ref")),
            str(table_row_index),
            normalized,
        )
    )
    return {
        "schema_version": 1,
        "candidate_id": hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20],
        "fingerprint": _fingerprint(normalized),
        "kind": kind,
        "source": {
            "filename": source["filename"],
            "sha256": source["sha256"],
            "drive_file_id": inventory_item.get("id") if inventory_item else None,
            "collection": inventory_item.get("collection") if inventory_item else None,
            "parent_title": inventory_item.get("parent_title") if inventory_item else None,
            "bundle_dir": bundle_dir.name,
            "profile_id": manifest["profile"]["id"],
            "profile_digest": manifest["profile"]["digest"],
        },
        "location": {
            **location,
            "section": section,
            "table_row_index": table_row_index,
        },
        "evidence_text": evidence_text,
        "context_text": context_text,
        "normalized_text": normalized,
        "signals": signals,
        "requires_human_validation": True,
    }


def _extract_bundle(
    bundle_dir: Path,
    inventory_by_filename: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    document = json.loads((bundle_dir / "document.docling.json").read_text(encoding="utf-8"))
    filename = manifest["source"]["filename"]
    inventory_matches = inventory_by_filename.get(filename, [])
    inventory_item = inventory_matches[0] if len(inventory_matches) == 1 else None
    candidates: list[dict[str, Any]] = []
    section: str | None = None

    for item in document.get("texts", []):
        text = item.get("text") or ""
        label = item.get("label") or ""
        if label in {"section_header", "title"}:
            section = _normalize(text)
        for segment in _segments(text):
            kind, signals = _signals(segment, label=label)
            if kind is None:
                continue
            candidates.append(
                _candidate(
                    kind=kind,
                    evidence_text=segment,
                    context_text=text,
                    signals=signals,
                    manifest=manifest,
                    bundle_dir=bundle_dir,
                    inventory_item=inventory_item,
                    location=_location(item),
                    section=section,
                )
            )

    for table in document.get("tables", []):
        location = _location(table)
        for row_index, row in enumerate(table.get("data", {}).get("grid", [])):
            row_text = " | ".join(_normalize(cell.get("text") or "") for cell in row)
            kind, signals = _signals(row_text, label="table")
            if kind is None:
                continue
            candidates.append(
                _candidate(
                    kind=f"table_{kind}",
                    evidence_text=row_text,
                    context_text=row_text,
                    signals=signals,
                    manifest=manifest,
                    bundle_dir=bundle_dir,
                    inventory_item=inventory_item,
                    location=location,
                    section=section,
                    table_row_index=row_index,
                )
            )
    text_items = document.get("texts", [])
    tables = document.get("tables", [])
    native_text_chars = sum(len(item.get("text") or "") for item in text_items)
    table_text_chars = sum(
        len(cell.get("text") or "")
        for table in tables
        for row in table.get("data", {}).get("grid", [])
        for cell in row
    )
    extractable_text_chars = native_text_chars + table_text_chars
    coverage = {
        "schema_version": 1,
        "filename": filename,
        "sha256": manifest["source"]["sha256"],
        "profile_id": manifest["profile"]["id"],
        "ocr_provider": manifest.get("ocr_usage", {}).get("provider"),
        "pages": manifest.get("stats", {}).get("pages"),
        "text_items": len(text_items),
        "native_text_chars": native_text_chars,
        "table_text_chars": table_text_chars,
        "extractable_text_chars": extractable_text_chars,
        "tables": len(tables),
        "direct_formula_items": sum(item.get("label") == "formula" for item in text_items),
        "candidate_count": len(candidates),
        "coverage_status": (
            "no_usable_native_text"
            if extractable_text_chars < 20
            else "candidate_detected"
            if candidates
            else "no_candidate_detected"
        ),
        "warnings": manifest.get("warnings", []),
    }
    return candidates, coverage


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            output.write("\n")


def _markdown(families: list[dict[str, Any]], stats: dict[str, Any]) -> str:
    lines = [
        "# 계산식·계산 규칙 후보 카탈로그",
        "",
        "> Docling 무OCR 결과에서 자동 추출한 고재현율 후보입니다. Python 함수로 채택하기 전에 원문 조건과 단위를 사람이 검증해야 합니다.",
        "",
        f"- 처리 bundle: {stats['bundles']}개",
        f"- 후보 occurrence: {stats['candidates']}개",
        f"- 중복 제거 family: {stats['families']}개",
        f"- 후보가 없는 문서: {stats['documents_without_candidates']}개",
        "",
        "| Family | 유형 | 출현 | 대표 근거 | 문서 |",
        "|---|---:|---:|---|---|",
    ]
    for family in families:
        evidence = family["representative_text"].replace("|", "\\|").replace("\n", " ")
        sources = ", ".join(family["source_filenames"][:5])
        if len(family["source_filenames"]) > 5:
            sources += f" 외 {len(family['source_filenames']) - 5}개"
        lines.append(
            f"| `{family['family_id']}` | {family['kind']} | {family['occurrence_count']} | {evidence} | {sources} |"
        )
    lines.append("")
    return "\n".join(lines)


def _candidate_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "formula-candidate.schema.json",
        "title": "Formula candidate occurrence",
        "type": "object",
        "required": [
            "schema_version",
            "candidate_id",
            "fingerprint",
            "kind",
            "source",
            "location",
            "evidence_text",
            "normalized_text",
            "requires_human_validation",
        ],
        "properties": {
            "schema_version": {"const": 1},
            "candidate_id": {"type": "string"},
            "fingerprint": {"type": "string"},
            "kind": {
                "enum": [
                    "docling_formula",
                    "explicit_equation",
                    "calculation_rule",
                    "rate_or_threshold_rule",
                    "table_docling_formula",
                    "table_explicit_equation",
                    "table_calculation_rule",
                    "table_rate_or_threshold_rule",
                    "image_formula",
                ]
            },
            "source": {"type": "object"},
            "location": {"type": "object"},
            "evidence_text": {"type": "string"},
            "context_text": {"type": "string"},
            "normalized_text": {"type": "string"},
            "signals": {"type": "object"},
            "image_formula_extraction": {"type": "object"},
            "requires_human_validation": {"const": True},
        },
        "additionalProperties": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_root", type=Path)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--image-formulas", type=Path)
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))["files"]
    inventory_by_filename: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in inventory:
        inventory_by_filename[item["title"]].append(item)

    bundle_dirs = sorted(path.parent for path in args.bundle_root.glob("*/manifest.json"))
    candidates: list[dict[str, Any]] = []
    coverage_records: list[dict[str, Any]] = []
    candidate_documents: set[str] = set()
    for bundle_dir in bundle_dirs:
        extracted, coverage = _extract_bundle(bundle_dir, inventory_by_filename)
        candidates.extend(extracted)
        coverage_records.append(coverage)
        if extracted:
            candidate_documents.add(extracted[0]["source"]["sha256"])

    image_candidates: list[dict[str, Any]] = []
    if args.image_formulas:
        with args.image_formulas.open(encoding="utf-8") as input_file:
            image_candidates = [json.loads(line) for line in input_file if line.strip()]
        candidates.extend(image_candidates)
        candidate_documents.update(item["source"]["sha256"] for item in image_candidates)
        image_counts = Counter(item["source"]["sha256"] for item in image_candidates)
        for coverage in coverage_records:
            count = image_counts.get(coverage["sha256"], 0)
            coverage["image_formula_candidate_count"] = count
            if count and coverage["coverage_status"] != "candidate_detected":
                coverage["coverage_status"] = "candidate_detected"

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate["fingerprint"]].append(candidate)
    families: list[dict[str, Any]] = []
    for fingerprint, occurrences in grouped.items():
        kinds = Counter(item["kind"] for item in occurrences)
        families.append(
            {
                "schema_version": 1,
                "family_id": fingerprint[:20],
                "fingerprint": fingerprint,
                "kind": kinds.most_common(1)[0][0],
                "occurrence_count": len(occurrences),
                "representative_text": occurrences[0]["normalized_text"],
                "candidate_ids": [item["candidate_id"] for item in occurrences],
                "source_filenames": sorted({item["source"]["filename"] for item in occurrences}),
                "requires_human_validation": True,
            }
        )
    families.sort(key=lambda item: (-item["occurrence_count"], item["family_id"]))
    candidates.sort(
        key=lambda item: (
            item["source"]["filename"],
            item["location"].get("page_no") or 0,
            item["candidate_id"],
        )
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "formula_candidates.jsonl", candidates)
    _write_jsonl(args.output_dir / "formula_families.jsonl", families)
    _write_jsonl(args.output_dir / "document_coverage.jsonl", coverage_records)
    (args.output_dir / "formula_candidates.schema.json").write_text(
        json.dumps(_candidate_schema(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    stats = {
        "bundles": len(bundle_dirs),
        "candidates": len(candidates),
        "families": len(families),
        "documents_with_candidates": len(candidate_documents),
        "documents_without_candidates": len(bundle_dirs) - len(candidate_documents),
        "candidate_kinds": dict(Counter(item["kind"] for item in candidates)),
        "coverage_statuses": dict(Counter(item["coverage_status"] for item in coverage_records)),
        "image_formula_candidates": len(image_candidates),
    }
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "body_ocr_used": False,
        "image_formula_ocr_used": any(
            item.get("image_formula_extraction", {}).get("ocr_applied", False)
            for item in image_candidates
        ),
        "formula_candidates": "formula_candidates.jsonl",
        "formula_families": "formula_families.jsonl",
        "document_coverage": "document_coverage.jsonl",
        "candidate_schema": "formula_candidates.schema.json",
        "review_catalog": "formula_catalog.md",
        "stats": stats,
    }
    (args.output_dir / "extraction_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "formula_catalog.md").write_text(
        _markdown(families, stats), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
