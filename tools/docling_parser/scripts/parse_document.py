"""고정된 Docling 프로필로 문서 하나를 파싱한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from docling_team_parser.artifacts import parse_document
from docling_team_parser.errors import ParserError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Docling 문서 파싱 스크립트")
    parser.add_argument("source_path", type=Path, help="파싱할 PDF, DOCX, PPTX 또는 XLSX")
    parser.add_argument(
        "--ocr",
        choices=("none", "none-native", "local", "naver"),
        default="local",
        help=(
            "사용할 OCR 방식(기본값: local; none은 수식 보강, none-native는 native text/표만 수행)"
        ),
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="bundle 출력 폴더")
    parser.add_argument(
        "--confirm-external-transfer",
        action="store_true",
        help="문서 이미지의 NAVER Cloud 전송을 확인",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        bundle = parse_document(
            args.source_path,
            args.output_dir,
            args.ocr,
            confirm_external_transfer=args.confirm_external_transfer,
        )
    except ParserError as exc:
        json.dump(
            {"status": "failed", "error": {"code": exc.code, "message": exc.message}},
            sys.stderr,
            ensure_ascii=False,
        )
        sys.stderr.write("\n")
        return 1

    json.dump(
        {"status": "success", "bundle": bundle.to_dict()},
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
