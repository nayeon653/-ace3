"""한투 30문항 Gold Answer와 Docling 근거 locator를 검증한다."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from evals.harness.docling_evidence import (
    item_text,
    normalize_text,
    resolve_item,
    select_table_cells,
    sha256_file,
)

_ANSWERABILITY = {"supported", "partial", "unsupported", "temporal_gap"}
_EXPECTED_IDS = {f"PROD-{index:03d}" for index in range(1, 16)} | {
    f"POLICY-{index:03d}" for index in range(1, 16)
}


@dataclass(frozen=True, slots=True)
class GoldValidationSummary:
    """검증된 정답셋의 주요 개수를 보관한다."""

    questions: int
    evidence: int
    retrieval_links: int
    answerability: dict[str, int]


def _split_markdown_row(line: str) -> list[str]:
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for character in line.strip()[1:-1]:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    cells.append("".join(current).strip())
    return cells


def _load_questions(path: Path) -> dict[str, str]:
    questions: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(("| PROD-", "| POLICY-")):
            continue
        cells = _split_markdown_row(line)
        if len(cells) != 13:
            raise ValueError(f"질문 표 열 개수가 13이 아닙니다: {cells[0]}")
        questions[cells[0]] = cells[3]
    return questions


def _load_gold_markdown_ids(path: Path) -> list[str]:
    return [
        _split_markdown_row(line)[0]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith(("| PROD-", "| POLICY-"))
    ]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}: JSONL 파싱 실패") from error
        if not isinstance(value, dict):
            raise TypeError(f"{path}:{line_number}: 객체가 아닙니다")
        rows.append(value)
    return rows


def _assert_equal(actual: Any, expected: Any, context: str) -> None:
    if actual != expected:
        raise ValueError(f"{context}: expected={expected!r}, actual={actual!r}")


def _validate_provenance(
    item: dict[str, Any],
    expected: dict[str, Any] | None,
    context: str,
) -> None:
    if expected is None:
        return
    index = expected["index"]
    provenance = item.get("prov", [])
    if index >= len(provenance):
        raise ValueError(f"{context}: provenance index가 범위를 벗어났습니다")
    actual = provenance[index]
    for field in ("page_no", "charspan", "bbox"):
        if field in expected:
            _assert_equal(actual.get(field), expected[field], f"{context}.{field}")


def _load_chunks(path: Path) -> dict[str, dict[str, Any]]:
    return {row["chunk_id"]: row for row in _load_jsonl(path)}


def _validate_retrieval(
    retrieval: dict[str, Any],
    quote: str,
    chunks: dict[str, dict[str, Any]],
    context: str,
) -> None:
    chunk_id = retrieval["chunk_id"]
    chunk = chunks.get(chunk_id)
    if chunk is None:
        raise ValueError(f"{context}: retrieval chunk가 없습니다: {chunk_id}")
    for field in ("canonical_doc_id", "content_hash", "page_start", "page_end"):
        if field in retrieval:
            _assert_equal(chunk.get(field), retrieval[field], f"{context}.retrieval.{field}")
    quote_text = normalize_text(str(retrieval.get("quote", quote)))
    chunk_text = normalize_text(str(chunk.get("text", "")))
    if quote_text not in chunk_text and chunk_text not in quote_text:
        raise ValueError(f"{context}: 인용문이 retrieval chunk와 연결되지 않습니다")


def _validate_evidence(
    evidence: dict[str, Any],
    source_entry: dict[str, Any],
    repo_root: Path,
    chunks: dict[str, dict[str, Any]],
    context: str,
) -> bool:
    bundle_path = repo_root / source_entry["bundle_path"]
    manifest_path = bundle_path / "manifest.json"
    document_path = bundle_path / "document.docling.json"
    if not manifest_path.is_file() or not document_path.is_file():
        raise ValueError(f"{context}: Docling bundle이 없습니다: {bundle_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    document = json.loads(document_path.read_text(encoding="utf-8"))
    source = manifest["source"]
    profile = manifest["profile"]
    artifacts = manifest["artifacts"]
    checks: dict[str, Any] = {
        "source_file": source["filename"],
        "source_sha256": source["sha256"],
        "bundle_id": manifest["bundle_id"],
        "profile_id": profile["id"],
        "profile_digest": profile["digest"],
        "docling_json_sha256": artifacts["docling_json_sha256"],
    }
    for field, actual in checks.items():
        _assert_equal(actual, source_entry[field], f"{context}.source.{field}")
    _assert_equal(
        sha256_file(document_path),
        source_entry["docling_json_sha256"],
        f"{context}.docling_json_sha256",
    )

    item = resolve_item(document, evidence["item_ref"])
    _assert_equal(item.get("label"), evidence["item_label"], f"{context}.item_label")
    selection = evidence.get("selection", {"kind": "item"})
    if selection["kind"] == "table_cells":
        selected_text = select_table_cells(item, selection["cells"])
    elif selection["kind"] == "item":
        selected_text = item_text(item)
    else:
        raise ValueError(f"{context}: 지원하지 않는 selection입니다")
    if normalize_text(evidence["quote"]) not in normalize_text(selected_text):
        raise ValueError(f"{context}: 인용문이 Docling 항목에 없습니다")
    _validate_provenance(item, evidence.get("provenance"), context)

    retrieval = evidence.get("retrieval")
    if retrieval is None:
        return False
    _validate_retrieval(retrieval, evidence["quote"], chunks, context)
    return True


def validate_gold_dataset(
    *,
    repo_root: Path,
    manifest_path: Path,
    dataset_path: Path,
    verify_corpus: bool = True,
) -> GoldValidationSummary:
    """정답셋 스키마, 질문 스냅샷, Docling 근거와 검색 청크를 모두 검증한다."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset_snapshot = manifest["gold_dataset"]
    expected_dataset_path = (repo_root / dataset_snapshot["path"]).resolve()
    _assert_equal(dataset_path.resolve(), expected_dataset_path, "gold_dataset.path")
    _assert_equal(
        sha256_file(dataset_path),
        dataset_snapshot["sha256"],
        "gold_dataset.sha256",
    )
    markdown_snapshot = manifest["markdown_table"]
    markdown_path = repo_root / markdown_snapshot["path"]
    _assert_equal(
        sha256_file(markdown_path),
        markdown_snapshot["sha256"],
        "markdown_table.sha256",
    )
    markdown_ids = _load_gold_markdown_ids(markdown_path)
    _assert_equal(
        len(markdown_ids),
        markdown_snapshot["row_count"],
        "markdown_table.row_count",
    )
    _assert_equal(set(markdown_ids), _EXPECTED_IDS, "markdown_table.test_id set")
    question_path = repo_root / manifest["question_source"]["path"]
    _assert_equal(
        sha256_file(question_path),
        manifest["question_source"]["sha256"],
        "question_source.sha256",
    )
    registry_path = repo_root / manifest["source_registry"]["path"]
    _assert_equal(
        sha256_file(registry_path),
        manifest["source_registry"]["sha256"],
        "source_registry.sha256",
    )
    source_registry = json.loads(registry_path.read_text(encoding="utf-8"))["sources"]
    evidence_registry_path = repo_root / manifest["evidence_registry"]["path"]
    _assert_equal(
        sha256_file(evidence_registry_path),
        manifest["evidence_registry"]["sha256"],
        "evidence_registry.sha256",
    )
    evidence_registry = json.loads(evidence_registry_path.read_text(encoding="utf-8"))["evidence"]

    chunks: dict[str, dict[str, Any]] = {}
    if verify_corpus:
        archive = repo_root / manifest["docling_corpus"]["local_archive_path"]
        _assert_equal(
            sha256_file(archive),
            manifest["docling_corpus"]["archive_sha256"],
            "docling_corpus.archive_sha256",
        )
        retrieval_manifest_path = repo_root / manifest["retrieval_corpus"]["manifest_path"]
        _assert_equal(
            sha256_file(retrieval_manifest_path),
            manifest["retrieval_corpus"]["manifest_sha256"],
            "retrieval_corpus.manifest_sha256",
        )
        chunks_path = repo_root / manifest["retrieval_corpus"]["chunks_path"]
        _assert_equal(
            sha256_file(chunks_path),
            manifest["retrieval_corpus"]["chunks_sha256"],
            "retrieval_corpus.chunks_sha256",
        )
        chunks = _load_chunks(chunks_path)

    questions = _load_questions(question_path)
    rows = _load_jsonl(dataset_path)
    _assert_equal(len(rows), dataset_snapshot["row_count"], "gold_dataset.row_count")
    ids = [row.get("test_id") for row in rows]
    _assert_equal(len(ids), len(set(ids)), "test_id uniqueness")
    _assert_equal(set(ids), _EXPECTED_IDS, "test_id set")
    _assert_equal(set(questions), _EXPECTED_IDS, "question source id set")

    evidence_count = 0
    retrieval_count = 0
    answerability: dict[str, int] = {value: 0 for value in sorted(_ANSWERABILITY)}
    for row in rows:
        test_id = row["test_id"]
        context = test_id
        _assert_equal(row["schema_version"], manifest["schema_version"], f"{context}.schema")
        _assert_equal(row["dataset_id"], manifest["dataset_id"], f"{context}.dataset_id")
        _assert_equal(row["question"], questions[test_id], f"{context}.question")
        if row["answerability"] not in _ANSWERABILITY:
            raise ValueError(f"{context}: answerability가 올바르지 않습니다")
        answerability[row["answerability"]] += 1
        if not row["gold_answer"].strip():
            raise ValueError(f"{context}: gold_answer가 비어 있습니다")

        claims = {claim["id"]: claim for claim in row["required_claims"]}
        row_evidence_ids = row["evidence_ids"]
        evidence = {
            evidence_id: evidence_registry[evidence_id]
            for evidence_id in row_evidence_ids
            if evidence_id in evidence_registry
        }
        if len(claims) != len(row["required_claims"]):
            raise ValueError(f"{context}: claim id가 중복됩니다")
        if len(row_evidence_ids) != len(set(row_evidence_ids)):
            raise ValueError(f"{context}: evidence id가 중복됩니다")
        unknown_evidence = set(row_evidence_ids) - set(evidence_registry)
        if unknown_evidence:
            raise ValueError(f"{context}: 등록되지 않은 evidence: {unknown_evidence}")
        if row["answerability"] == "supported" and (not claims or not evidence):
            raise ValueError(f"{context}: supported 문항에 주장 또는 근거가 없습니다")
        if row["answerability"] == "unsupported" and claims:
            raise ValueError(f"{context}: unsupported 문항에 필수 주장이 있습니다")
        if row["answerability"] != "supported" and not row.get("known_gaps"):
            raise ValueError(f"{context}: 불완전 문항에 known_gaps가 없습니다")
        if len(row.get("verification", [])) < 2:
            raise ValueError(f"{context}: 최소 2회 검증 기록이 필요합니다")

        for claim in claims.values():
            if not claim["evidence_ids"]:
                raise ValueError(f"{context}.{claim['id']}: evidence_ids가 비어 있습니다")
            for evidence_id in claim["evidence_ids"]:
                if evidence_id not in evidence:
                    raise ValueError(f"{context}.{claim['id']}: 근거가 없습니다: {evidence_id}")
        for evidence_id, item in evidence.items():
            source_key = item["source_key"]
            if source_key not in source_registry:
                raise ValueError(f"{context}.{evidence_id}: 출처 등록이 없습니다: {source_key}")
            evidence_count += 1
            if verify_corpus and _validate_evidence(
                item,
                source_registry[source_key],
                repo_root,
                chunks,
                f"{context}.{evidence_id}",
            ):
                retrieval_count += 1

    return GoldValidationSummary(
        questions=len(rows),
        evidence=evidence_count,
        retrieval_links=retrieval_count,
        answerability=answerability,
    )


def main() -> int:
    """저장소 기본 경로의 Gold Answer를 검증하고 요약을 출력한다."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--structure-only", action="store_true")
    args = parser.parse_args()
    manifest_path = args.manifest or args.repo_root / "evals/gold/hantoo_selected_30.manifest.json"
    dataset_path = args.dataset or args.repo_root / "evals/gold/hantoo_selected_30.jsonl"
    summary = validate_gold_dataset(
        repo_root=args.repo_root,
        manifest_path=manifest_path,
        dataset_path=dataset_path,
        verify_corpus=not args.structure_only,
    )
    print(json.dumps(asdict(summary), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
