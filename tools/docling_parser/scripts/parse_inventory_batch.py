"""고정 inventory의 문서를 분할 배치로 파싱한다."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from docling_team_parser.artifacts import parse_document
from docling_team_parser.docling_engine import DoclingEngine
from docling_team_parser.errors import ParserError
from docling_team_parser.profiles import OcrProvider, profile_for_provider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--collection")
    parser.add_argument(
        "--ocr",
        choices=tuple(provider.value for provider in OcrProvider),
        default=OcrProvider.NONE.value,
    )
    parser.add_argument("--partition-index", type=int, required=True)
    parser.add_argument("--partition-count", type=int, required=True)
    parser.add_argument("--skip-existing-source", action="store_true")
    args = parser.parse_args()

    if not 0 <= args.partition_index < args.partition_count:
        parser.error("partition-index는 0 이상 partition-count 미만이어야 합니다")

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))["files"]
    if args.collection:
        inventory = [item for item in inventory if item["collection"] == args.collection]
    selected = [
        item
        for index, item in enumerate(inventory)
        if index % args.partition_count == args.partition_index
    ]
    args.output_root.mkdir(parents=True, exist_ok=True)
    existing_sources: set[str] = set()
    if args.skip_existing_source:
        for manifest_path in args.output_root.glob("*/manifest.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            existing_sources.add(manifest["source"]["filename"])
    engine = DoclingEngine(profile_for_provider(args.ocr))
    results: list[dict[str, str]] = []
    started = time.monotonic()

    for index, item in enumerate(selected, start=1):
        source = args.raw_root / item["collection"] / item["parent_title"] / item["title"]
        if item["title"] in existing_sources:
            result = {
                "status": "skipped",
                "source": str(source),
                "error_code": "SOURCE_ALREADY_PARSED",
                "error_message": "다른 무OCR 프로필의 성공 bundle이 이미 있습니다.",
            }
            results.append(result)
            print(
                json.dumps(
                    {
                        "worker": args.partition_index,
                        "progress": f"{index}/{len(selected)}",
                        "elapsed_seconds": round(time.monotonic() - started, 1),
                        "last": result,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            continue
        try:
            bundle = parse_document(source, args.output_root, args.ocr, engine=engine)
            result = {
                "status": "success",
                "source": str(source),
                "bundle": str(bundle.output_dir),
            }
        except ParserError as exc:
            status = "skipped" if exc.code == "OUTPUT_EXISTS" else "failed"
            result = {
                "status": status,
                "source": str(source),
                "error_code": exc.code,
                "error_message": exc.message,
            }
        results.append(result)
        print(
            json.dumps(
                {
                    "worker": args.partition_index,
                    "progress": f"{index}/{len(selected)}",
                    "elapsed_seconds": round(time.monotonic() - started, 1),
                    "last": result,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    failed = [item for item in results if item["status"] == "failed"]
    print(
        json.dumps(
            {
                "worker_summary": {
                    "worker": args.partition_index,
                    "total": len(results),
                    "success": sum(item["status"] == "success" for item in results),
                    "skipped": sum(item["status"] == "skipped" for item in results),
                    "failed": failed,
                    "elapsed_seconds": round(time.monotonic() - started, 1),
                }
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
