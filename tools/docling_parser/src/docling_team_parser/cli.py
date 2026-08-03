"""고정된 로컬 및 NAVER 워크플로만 노출하는 CLI 우선 어댑터."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO

from . import __version__
from .errors import ParserError
from .models import BatchRequest, ConflictPolicy, FailurePolicy, ParseRequest
from .profiles import LOCAL_PROFILE_ID, NAVER_PROFILE_ID
from .service import ParserService


def _add_common_parse_arguments(
    parser: argparse.ArgumentParser,
    *,
    require_external_transfer_confirmation: bool,
) -> None:
    parser.add_argument(
        "source_path",
        type=Path,
        metavar="SOURCE_PATH",
        help="PDF, DOCX, PPTX, or XLSX path",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        metavar="PATH",
        required=True,
        help="artifact output root",
    )
    parser.add_argument(
        "--conflict-policy",
        choices=tuple(policy.value for policy in ConflictPolicy),
        default=ConflictPolicy.ERROR.value,
        help=f"existing-output behavior (default: {ConflictPolicy.ERROR.value})",
    )
    if require_external_transfer_confirmation:
        parser.add_argument(
            "--confirm-external-transfer",
            action="store_true",
            required=True,
            help="confirm that document images may be sent to NAVER Cloud OCR",
        )


def _add_common_batch_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_failure_policy: FailurePolicy,
    require_external_transfer_confirmation: bool,
) -> None:
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument(
        "--source-path",
        dest="source_paths",
        action="append",
        type=Path,
        metavar="PATH",
        help="document path; repeat this option to parse multiple documents",
    )
    sources.add_argument(
        "--source-dir",
        type=Path,
        metavar="PATH",
        help="directory containing documents",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="search below --source-dir recursively",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        metavar="PATH",
        required=True,
        help="artifact output root",
    )
    parser.add_argument(
        "--conflict-policy",
        choices=tuple(policy.value for policy in ConflictPolicy),
        default=ConflictPolicy.ERROR.value,
        help=f"existing-output behavior (default: {ConflictPolicy.ERROR.value})",
    )
    parser.add_argument(
        "--failure-policy",
        choices=tuple(policy.value for policy in FailurePolicy),
        default=default_failure_policy.value,
        help=f"batch failure behavior (default: {default_failure_policy.value})",
    )
    if require_external_transfer_confirmation:
        parser.add_argument(
            "--confirm-external-transfer",
            action="store_true",
            required=True,
            help="confirm that document images may be sent to NAVER Cloud OCR",
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docling-parser",
        description=(
            "Parse documents with fixed local or NAVER OCR workflows and emit JSON."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("profiles", help="list fixed parser profiles")
    subparsers.add_parser("doctor", help="check dependencies and configuration")

    parse_local = subparsers.add_parser(
        "parse-local",
        help="parse one document with the fixed local OCR profile",
    )
    _add_common_parse_arguments(
        parse_local,
        require_external_transfer_confirmation=False,
    )

    parse_naver = subparsers.add_parser(
        "parse-naver",
        help="parse one document with the fixed NAVER Cloud OCR profile",
    )
    _add_common_parse_arguments(
        parse_naver,
        require_external_transfer_confirmation=True,
    )

    batch_local = subparsers.add_parser(
        "batch-local",
        help="parse documents with the fixed local OCR profile",
    )
    _add_common_batch_arguments(
        batch_local,
        default_failure_policy=FailurePolicy.CONTINUE,
        require_external_transfer_confirmation=False,
    )

    batch_naver = subparsers.add_parser(
        "batch-naver",
        help="parse documents with the fixed NAVER Cloud OCR profile",
    )
    _add_common_batch_arguments(
        batch_naver,
        default_failure_policy=FailurePolicy.STOP,
        require_external_transfer_confirmation=True,
    )
    return parser


def _payload(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not isinstance(value, dict):
        raise TypeError("service result must serialize to a JSON object")
    return value


def _write_json(value: dict[str, Any], stream: TextIO | None = None) -> None:
    target = stream or sys.stdout
    json.dump(value, target, ensure_ascii=False, indent=2, sort_keys=True)
    target.write("\n")


def _error_payload(exc: ParserError) -> dict[str, Any]:
    return {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "failure_manifest_path": (
                str(exc.failure_manifest_path) if exc.failure_manifest_path else None
            ),
        }
    }


def _parse_request(args: argparse.Namespace) -> ParseRequest:
    is_naver = args.command == "parse-naver"
    return ParseRequest(
        source_path=args.source_path,
        profile_id=NAVER_PROFILE_ID if is_naver else LOCAL_PROFILE_ID,
        output_dir=args.output_dir,
        conflict_policy=ConflictPolicy(args.conflict_policy),
        confirm_external_transfer=is_naver,
    )


def _batch_request(args: argparse.Namespace) -> BatchRequest:
    is_naver = args.command == "batch-naver"
    return BatchRequest(
        profile_id=NAVER_PROFILE_ID if is_naver else LOCAL_PROFILE_ID,
        source_paths=tuple(args.source_paths or ()),
        source_dir=args.source_dir,
        recursive=args.recursive,
        output_dir=args.output_dir,
        failure_policy=FailurePolicy(args.failure_policy),
        conflict_policy=ConflictPolicy(args.conflict_policy),
        confirm_external_transfer=is_naver,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    service_factory: Callable[[], ParserService] = ParserService,
) -> int:
    """CLI 명령을 실행하고 프로세스 종료 코드를 반환한다."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2

    try:
        service = service_factory()
        if args.command == "profiles":
            result = service.list_profiles()
        elif args.command == "doctor":
            result = service.doctor()
        elif args.command in {"parse-local", "parse-naver"}:
            result = service.parse(_parse_request(args))
        else:
            result = service.parse_batch(_batch_request(args))
        payload = _payload(result)
        _write_json(payload)
        if args.command == "doctor" and payload.get("ok") is False:
            return 1
        if args.command in {"batch-local", "batch-naver"} and payload.get("status") in {
            "failed",
            "partial_success",
        }:
            return 1
        return 0
    except ParserError as exc:
        _write_json(_error_payload(exc), stream=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - CLI 경계는 항상 JSON만 출력해야 한다.
        _write_json(
            {"error": {"code": "INTERNAL_ERROR", "message": str(exc)}},
            stream=sys.stderr,
        )
        return 1


if __name__ == "__main__":  # pragma: no cover - 콘솔 진입점
    raise SystemExit(main())
