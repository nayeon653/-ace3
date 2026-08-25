"""계산식 카탈로그와 Docling bundle의 최종 전달 무결성을 검증한다."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docling_team_parser.io_utils import sha256_directory, sha256_file


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as input_file:
        return [json.loads(line) for line in input_file if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--catalog-dir", type=Path, required=True)
    parser.add_argument("--image-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))["files"]
    inventory_by_filename = {item["title"]: item for item in inventory}
    errors: list[str] = []
    manifests: list[dict[str, Any]] = []
    bundle_by_sha: dict[str, dict[str, Any]] = {}

    for manifest_path in sorted(args.bundle_root.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifests.append(manifest)
        source = manifest["source"]
        filename = source["filename"]
        item = inventory_by_filename.get(filename)
        if item is None:
            errors.append(f"inventory에 없는 bundle: {filename}")
            continue
        raw_path = args.raw_root / item["collection"] / item["parent_title"] / filename
        if not raw_path.is_file():
            errors.append(f"원본 없음: {filename}")
            continue
        if raw_path.stat().st_size != int(item["size"]):
            errors.append(f"Drive inventory 크기 불일치: {filename}")
        if sha256_file(raw_path) != source["sha256"]:
            errors.append(f"원본 sha256 불일치: {filename}")
        if source["sha256"] in bundle_by_sha:
            errors.append(f"중복 source bundle: {filename}")
        bundle_by_sha[source["sha256"]] = manifest
        if manifest.get("status") != "success":
            errors.append(f"성공 상태가 아닌 bundle: {filename}")
        if manifest.get("ocr_usage", {}).get("provider") not in {"none", "none-native"}:
            errors.append(f"본문 OCR 사용 bundle: {filename}")

        artifacts = manifest["artifacts"]
        bundle_dir = manifest_path.parent
        for name, hash_key in (
            ("markdown", "markdown_sha256"),
            ("html", "html_sha256"),
            ("docling_json", "docling_json_sha256"),
        ):
            artifact_path = bundle_dir / artifacts[name]
            if not artifact_path.is_file() or sha256_file(artifact_path) != artifacts[hash_key]:
                errors.append(f"artifact 무결성 오류: {filename}/{artifacts[name]}")
        assets_dir = bundle_dir / artifacts["assets"]
        if not assets_dir.is_dir() or sha256_directory(assets_dir) != artifacts["assets_sha256"]:
            errors.append(f"assets 무결성 오류: {filename}")

    bundled_filenames = {manifest["source"]["filename"] for manifest in manifests}
    missing = sorted(set(inventory_by_filename) - bundled_filenames)
    extra = sorted(bundled_filenames - set(inventory_by_filename))
    if missing:
        errors.append(f"누락 bundle {len(missing)}개: {', '.join(missing[:10])}")
    if extra:
        errors.append(f"초과 bundle {len(extra)}개: {', '.join(extra[:10])}")

    candidates = _read_jsonl(args.catalog_dir / "formula_candidates.jsonl")
    families = _read_jsonl(args.catalog_dir / "formula_families.jsonl")
    coverage = _read_jsonl(args.catalog_dir / "document_coverage.jsonl")
    catalog_manifest = json.loads(
        (args.catalog_dir / "extraction_manifest.json").read_text(encoding="utf-8")
    )
    image_manifest = json.loads(args.image_manifest.read_text(encoding="utf-8"))
    if len(coverage) != len(inventory):
        errors.append(f"coverage 문서 수 불일치: {len(coverage)} != {len(inventory)}")
    if len(candidates) != catalog_manifest["stats"]["candidates"]:
        errors.append("candidate 수와 extraction manifest 불일치")
    if len(families) != catalog_manifest["stats"]["families"]:
        errors.append("family 수와 extraction manifest 불일치")
    unknown_candidate_sources = sorted(
        {
            item["source"]["sha256"]
            for item in candidates
            if item["source"]["sha256"] not in bundle_by_sha
        }
    )
    if unknown_candidate_sources:
        errors.append(f"bundle이 없는 candidate source: {len(unknown_candidate_sources)}개")
    if image_manifest.get("errors"):
        errors.append(f"그림 수식 단계 오류: {len(image_manifest['errors'])}개")
    if image_manifest.get("policy", {}).get("body_ocr") is not False:
        errors.append("그림 수식 정책의 body_ocr가 false가 아님")

    stats = {
        "inventory_files": len(inventory),
        "bundles": len(manifests),
        "profile_counts": dict(Counter(item["profile"]["id"] for item in manifests)),
        "ocr_provider_counts": dict(Counter(item["ocr_usage"]["provider"] for item in manifests)),
        "formula_candidates": len(candidates),
        "formula_families": len(families),
        "coverage_statuses": dict(Counter(item["coverage_status"] for item in coverage)),
        "image_formula_candidate_occurrences": image_manifest.get("counts", {}).get(
            "candidate_occurrences", 0
        ),
        "image_ocr_calls": image_manifest.get("counts", {}).get(
            "images_ocrd_after_formula_gate", 0
        ),
    }
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": not errors,
        "stats": stats,
        "errors": errors,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "qa_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown = [
        "# 계산식 추출 QA 보고서",
        "",
        f"- 결과: {'PASS' if report['passed'] else 'FAIL'}",
        f"- 원본 / bundle: {stats['inventory_files']} / {stats['bundles']}",
        f"- 계산식 후보 occurrence / family: {stats['formula_candidates']} / {stats['formula_families']}",
        f"- 그림 수식 OCR 호출 / 후보: {stats['image_ocr_calls']} / {stats['image_formula_candidate_occurrences']}",
        "- 본문 OCR: 사용 안 함",
        "- 외부 전송: 사용 안 함",
        "",
        "## 오류",
        "",
    ]
    markdown.extend(f"- {error}" for error in errors)
    if not errors:
        markdown.append("- 없음")
    (args.output_dir / "qa_report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
