"""Application service used by the Docling CLI adapter."""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from . import __version__
from .errors import NaverOcrError, ParserError
from .io_utils import (
    normalize_markdown_file,
    safe_stem,
    sha256_directory,
    sha256_file,
    write_json_atomic,
)
from .models import (
    SUPPORTED_EXTENSIONS,
    BatchItemResult,
    BatchRequest,
    BatchResult,
    ConflictPolicy,
    FailurePolicy,
    OcrProvider,
    ParseRequest,
    ParseResult,
    ParseStats,
    RunManifest,
)
from .profiles import get_profile, iter_profiles, profile_availability
from .settings import RuntimeSettings

_RUNTIME_PACKAGES = (
    "mirae-docling-cli-parser",
    "docling",
    "docling-core",
    "easyocr",
    "httpx",
    "torch",
    "torchvision",
    "transformers",
)


class ParserService:
    def __init__(self, settings: RuntimeSettings | None = None):
        self.settings = settings or RuntimeSettings.from_env()

    def list_profiles(self) -> dict[str, Any]:
        profiles = []
        for profile in iter_profiles():
            available, reason = profile_availability(profile)
            profiles.append(
                {
                    **profile.model_dump(mode="json"),
                    "digest": profile.digest,
                    "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
                    "available": available,
                    "unavailable_reason": reason,
                }
            )
        return {"profiles": profiles}

    def doctor(self) -> dict[str, Any]:
        package_versions = self._runtime_package_versions()
        output_configuration_error: dict[str, str] | None = None
        try:
            authorized_output = self.settings.authorize_output_dir(None)
        except ParserError as exc:
            authorized_output = self.settings.default_output_root
            output_configuration_error = {"code": exc.code, "message": exc.message}
        output_parent = self._nearest_existing_parent(authorized_output)
        profiles = self.list_profiles()["profiles"]
        naver_enabled = os.environ.get(
            "DOCLING_PARSER_ENABLE_NAVER_OCR", ""
        ).strip().lower() in {"1", "true", "yes"}
        easyocr_importable = importlib.util.find_spec("easyocr") is not None
        torch_importable = importlib.util.find_spec("torch") is not None
        transformers_torch_available = False
        if torch_importable and importlib.util.find_spec("transformers") is not None:
            try:
                from transformers.utils import is_torch_available

                transformers_torch_available = is_torch_available()
            except (ImportError, RuntimeError, AttributeError):
                transformers_torch_available = False
        output_parent_is_directory = output_parent.is_dir()
        if not output_parent_is_directory and output_configuration_error is None:
            output_configuration_error = {
                "code": "OUTPUT_NOT_DIRECTORY",
                "message": f"nearest existing output parent is not a directory: {output_parent}",
            }
        output_parent_writable = output_parent_is_directory and os.access(
            output_parent, os.W_OK
        )
        output_configuration_valid = output_configuration_error is None
        return {
            "ok": all(
                profile["available"]
                for profile in profiles
                if profile["ocr_provider"] == OcrProvider.LOCAL.value or naver_enabled
            )
            and easyocr_importable
            and torch_importable
            and transformers_torch_available
            and output_configuration_valid
            and output_parent_writable,
            "parser_version": __version__,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "packages": package_versions,
            "easyocr_importable": easyocr_importable,
            "torch_importable": torch_importable,
            "transformers_torch_available": transformers_torch_available,
            "allowed_roots": [str(path) for path in self.settings.allowed_roots],
            "default_output_root": str(self.settings.default_output_root),
            "output_configuration_valid": output_configuration_valid,
            "output_configuration_error": output_configuration_error,
            "output_parent_is_directory": output_parent_is_directory,
            "output_parent_writable": output_parent_writable,
            "naver_environment": {
                "enabled": naver_enabled,
                "invoke_url_present": bool(os.environ.get("NAVER_OCR_INVOKE_URL")),
                "secret_present": bool(os.environ.get("NAVER_OCR_SECRET")),
            },
            "profiles": profiles,
        }

    def parse(self, request: ParseRequest) -> ParseResult:
        started_at = datetime.now(UTC)
        started_clock = time.perf_counter()
        run_id = uuid.uuid4().hex
        profile = get_profile(request.profile_id)
        self._require_profile_available(profile)
        if profile.external_data_transfer and not request.confirm_external_transfer:
            raise ParserError(
                "EXTERNAL_TRANSFER_NOT_CONFIRMED",
                "NAVER OCR requires explicit external transfer confirmation",
            )

        source = self.settings.authorize_existing_file(request.source_path)
        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ParserError(
                "UNSUPPORTED_FORMAT",
                f"supported extensions are: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            )
        output_root = self.settings.authorize_output_dir(request.output_dir)
        try:
            output_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ParserError(
                "OUTPUT_UNAVAILABLE",
                f"output directory cannot be created: {output_root}",
            ) from exc
        self._require_safe_output_directory(
            output_root,
            output_root,
            label="output root",
        )
        try:
            source_sha = sha256_file(source)
            source_size = source.stat().st_size
        except OSError as exc:
            raise ParserError(
                "SOURCE_UNAVAILABLE", f"source could not be read: {source}"
            ) from exc
        target = output_root / (
            f"{safe_stem(source.stem)}--{source_sha[:12]}--{profile.id}"
        )

        if target.is_symlink():
            raise ParserError(
                "OUTPUT_CONFLICT", f"output target cannot be a symlink: {target}"
            )
        if target.exists():
            try:
                if not self._path_is_unredirected_within(target, target):
                    raise ParserError(
                        "OUTPUT_CONFLICT",
                        f"output target cannot be a link or junction: {target}",
                    )
            except (OSError, RuntimeError) as exc:
                raise ParserError(
                    "OUTPUT_CONFLICT", f"output target could not be verified: {target}"
                ) from exc
            if request.conflict_policy is ConflictPolicy.REUSE_IDENTICAL:
                return self._reuse_result(target, source, source_sha, profile.digest)
            raise ParserError("OUTPUT_CONFLICT", f"output already exists: {target}")

        try:
            stage = Path(tempfile.mkdtemp(prefix=".docling-parser-", dir=output_root))
        except OSError as exc:
            raise ParserError(
                "OUTPUT_UNAVAILABLE",
                f"temporary output cannot be created under: {output_root}",
            ) from exc
        try:
            from docling_core.types.doc import ImageRefMode

            from .docling_engine import DoclingEngine

            engine_result = DoclingEngine(profile).convert(source)
            try:
                source_sha_after_parse = sha256_file(source)
            except OSError as exc:
                raise ParserError(
                    "SOURCE_CHANGED_DURING_PARSE",
                    "source became unavailable while Docling was parsing it",
                ) from exc
            if source_sha_after_parse != source_sha:
                raise ParserError(
                    "SOURCE_CHANGED_DURING_PARSE",
                    "source content changed while Docling was parsing it",
                )
            assets_dir = stage / "assets"
            markdown_path = stage / "document.md"
            docling_json_path = stage / "document.docling.json"
            assets_dir.mkdir(parents=True, exist_ok=True)

            engine_result.document.save_as_markdown(
                markdown_path,
                # A relative directory makes Docling emit portable references such
                # as assets/image_....png instead of the atomic staging path.
                artifacts_dir=Path("assets"),
                image_mode=ImageRefMode.REFERENCED,
                traverse_pictures=profile.traverse_pictures,
                compact_tables=False,
            )
            normalize_markdown_file(markdown_path)
            engine_result.document.save_as_json(
                docling_json_path,
                artifacts_dir=Path("assets"),
                image_mode=ImageRefMode.REFERENCED,
                indent=2,
            )

            elapsed_ms = round((time.perf_counter() - started_clock) * 1000)
            stats = ParseStats(
                pages=engine_result.pages,
                pictures_found=engine_result.pictures_found,
                office_pictures_ocrd=engine_result.office_pictures_ocrd,
                elapsed_ms=elapsed_ms,
            )
            markdown_sha = sha256_file(markdown_path)
            docling_json_sha = sha256_file(docling_json_path)
            assets_sha = sha256_directory(assets_dir)
            manifest = RunManifest(
                status="success",
                run_id=run_id,
                source={
                    "path": str(source),
                    "sha256": source_sha,
                    "size_bytes": source_size,
                    "extension": source.suffix.lower(),
                },
                profile={
                    "id": profile.id,
                    "digest": profile.digest,
                    "effective_options": profile.model_dump(mode="json"),
                },
                runtime={
                    "parser_version": __version__,
                    "python": sys.version.split()[0],
                    "platform": platform.platform(),
                    "packages": self._runtime_package_versions(),
                    "docling_conversion": engine_result.conversion_version,
                },
                artifacts={
                    "markdown": "document.md",
                    "markdown_sha256": markdown_sha,
                    "docling_json": "document.docling.json",
                    "docling_json_sha256": docling_json_sha,
                    "assets": "assets",
                    "assets_sha256": assets_sha,
                },
                stats=stats.model_dump(mode="json"),
                warnings=engine_result.warnings,
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )
            write_json_atomic(stage / "manifest.json", manifest.model_dump(mode="json"))
            try:
                stage.replace(target)
            except OSError as exc:
                if not target.exists():
                    raise ParserError(
                        "OUTPUT_UNAVAILABLE",
                        f"completed output could not be published: {target}",
                    ) from exc
                shutil.rmtree(stage, ignore_errors=True)
                if request.conflict_policy is ConflictPolicy.REUSE_IDENTICAL:
                    return self._reuse_result(
                        target, source, source_sha, profile.digest
                    )
                raise ParserError(
                    "OUTPUT_CONFLICT",
                    f"another parse published the output concurrently: {target}",
                ) from exc
            return ParseResult(
                status="success",
                run_id=run_id,
                source_path=source,
                source_sha256=source_sha,
                profile_id=profile.id,
                profile_digest=profile.digest,
                output_dir=target,
                markdown_path=target / "document.md",
                docling_json_path=target / "document.docling.json",
                manifest_path=target / "manifest.json",
                assets_dir=target / "assets",
                markdown_sha256=markdown_sha,
                docling_json_sha256=docling_json_sha,
                assets_sha256=assets_sha,
                warnings=tuple(engine_result.warnings),
                stats=stats,
            )
        except Exception as exc:
            shutil.rmtree(stage, ignore_errors=True)
            parser_error = self._as_parser_error(exc)
            try:
                failure_path = self._write_failure_manifest(
                    output_root=output_root,
                    run_id=run_id,
                    source=source,
                    source_sha=source_sha,
                    profile=profile,
                    started_at=started_at,
                    started_clock=started_clock,
                    error=parser_error,
                )
            except Exception:  # noqa: BLE001 - diagnostics must not mask parse errors
                # A diagnostic artifact is best effort and must never replace the
                # original parse failure (for example on a full output volume).
                failure_path = None
            parser_error.failure_manifest_path = failure_path
            raise parser_error from exc

    def parse_batch(self, request: BatchRequest) -> BatchResult:
        batch_id = uuid.uuid4().hex
        profile = get_profile(request.profile_id)
        self._require_profile_available(profile)
        if profile.external_data_transfer and not request.confirm_external_transfer:
            raise ParserError(
                "EXTERNAL_TRANSFER_NOT_CONFIRMED",
                "NAVER OCR requires explicit external transfer confirmation",
            )

        source_paths = self._resolve_batch_sources(request)
        output_root = self.settings.authorize_output_dir(request.output_dir)
        try:
            output_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ParserError(
                "OUTPUT_UNAVAILABLE",
                f"output directory cannot be created: {output_root}",
            ) from exc
        self._require_safe_output_directory(
            output_root,
            output_root,
            label="output root",
        )
        items: list[BatchItemResult] = []

        for index, source_path in enumerate(source_paths):
            try:
                result = self.parse(
                    ParseRequest(
                        source_path=source_path,
                        profile_id=profile.id,
                        output_dir=output_root,
                        conflict_policy=request.conflict_policy,
                        confirm_external_transfer=request.confirm_external_transfer,
                    )
                )
                items.append(
                    BatchItemResult(
                        source_path=source_path,
                        status=result.status,
                        result=result,
                    )
                )
            except ParserError as exc:
                items.append(
                    BatchItemResult(
                        source_path=source_path,
                        status="failed",
                        error_code=exc.code,
                        error_message=exc.message,
                        failure_manifest_path=exc.failure_manifest_path,
                    )
                )
                if request.failure_policy is FailurePolicy.STOP:
                    items.extend(
                        BatchItemResult(source_path=remaining_source, status="skipped")
                        for remaining_source in source_paths[index + 1 :]
                    )
                    break

        succeeded = sum(item.status == "success" for item in items)
        reused = sum(item.status == "reused" for item in items)
        failed = sum(item.status == "failed" for item in items)
        skipped = sum(item.status == "skipped" for item in items)
        status = (
            "failed"
            if failed and not (succeeded or reused)
            else "partial_success"
            if failed
            else "success"
        )
        batch_dir = self._prepare_output_subdirectory(output_root, "batches")
        batch_manifest_path = batch_dir / f"{batch_id}.json"
        result = BatchResult(
            status=status,
            batch_id=batch_id,
            profile_id=profile.id,
            profile_digest=profile.digest,
            total=len(source_paths),
            succeeded=succeeded,
            reused=reused,
            failed=failed,
            skipped=skipped,
            items=tuple(items),
            batch_manifest_path=batch_manifest_path,
        )
        try:
            write_json_atomic(batch_manifest_path, result.model_dump(mode="json"))
        except OSError as exc:
            raise ParserError(
                "OUTPUT_UNAVAILABLE",
                f"batch manifest could not be written: {batch_manifest_path}",
            ) from exc
        return result

    def _resolve_batch_sources(self, request: BatchRequest) -> list[Path]:
        if request.source_dir:
            source_dir = self.settings.authorize_existing_dir(request.source_dir)
            pattern = "**/*" if request.recursive else "*"
            candidates = (
                path
                for path in source_dir.glob(pattern)
                if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
            )
        else:
            # Individual authorization happens inside parse(), allowing CONTINUE
            # batches to report one bad explicit path without losing all results.
            candidates = (path.expanduser() for path in request.source_paths)
        try:
            paths = sorted(
                set(candidates),
                key=lambda path: (str(path).casefold(), str(path)),
            )
        except (OSError, RuntimeError) as exc:
            raise ParserError(
                "SOURCE_ENUMERATION_FAILED", "source paths could not be enumerated"
            ) from exc
        if not paths:
            raise ParserError("NO_SUPPORTED_DOCUMENTS", "no supported documents found")
        return paths

    def _reuse_result(
        self,
        target: Path,
        source: Path,
        source_sha: str,
        profile_digest: str,
    ) -> ParseResult:
        manifest_path = target / "manifest.json"
        try:
            if not self._path_is_unredirected_within(target, target):
                raise ParserError(
                    "OUTPUT_CONFLICT", "existing output is a link or junction"
                )
            if not self._path_is_unredirected_within(manifest_path, target):
                raise ParserError(
                    "OUTPUT_CONFLICT", "existing manifest redirects outside the output"
                )
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = RunManifest.model_validate(payload)
            source_payload = manifest.source
            profile_payload = manifest.profile
            artifacts_payload = manifest.artifacts
        except ParserError:
            raise
        except (
            OSError,
            RuntimeError,
            json.JSONDecodeError,
            ValidationError,
            TypeError,
        ) as exc:
            raise ParserError(
                "OUTPUT_CONFLICT", f"existing output has no valid manifest: {target}"
            ) from exc
        if (
            manifest.status != "success"
            or source_payload.get("sha256") != source_sha
            or profile_payload.get("digest") != profile_digest
        ):
            raise ParserError(
                "OUTPUT_CONFLICT", "existing output does not match source and profile"
            )
        markdown_path = target / "document.md"
        docling_json_path = target / "document.docling.json"
        assets_dir = target / "assets"
        expected_markdown_sha = artifacts_payload.get("markdown_sha256")
        expected_json_sha = artifacts_payload.get("docling_json_sha256")
        expected_assets_sha = artifacts_payload.get("assets_sha256")
        try:
            artifact_paths_safe = all(
                self._path_is_unredirected_within(path, target)
                for path in (markdown_path, docling_json_path, assets_dir)
            )
            assets_tree_safe = artifact_paths_safe and all(
                self._path_is_unredirected_within(path, target)
                for path in assets_dir.rglob("*")
            )
            artifacts_match = (
                artifact_paths_safe
                and assets_tree_safe
                and markdown_path.is_file()
                and docling_json_path.is_file()
                and assets_dir.is_dir()
                and bool(expected_markdown_sha)
                and bool(expected_json_sha)
                and bool(expected_assets_sha)
                and sha256_file(markdown_path) == expected_markdown_sha
                and sha256_file(docling_json_path) == expected_json_sha
                and sha256_directory(assets_dir) == expected_assets_sha
            )
        except (OSError, RuntimeError) as exc:
            raise ParserError(
                "OUTPUT_CONFLICT", "existing output artifacts could not be verified"
            ) from exc
        if not artifacts_match:
            raise ParserError(
                "OUTPUT_CONFLICT",
                "existing output artifacts are missing or do not match the manifest",
            )
        try:
            stats = ParseStats.model_validate(manifest.stats)
            return ParseResult(
                status="reused",
                run_id=manifest.run_id,
                source_path=source,
                source_sha256=source_sha,
                profile_id=str(profile_payload["id"]),
                profile_digest=profile_digest,
                output_dir=target,
                markdown_path=markdown_path,
                docling_json_path=docling_json_path,
                manifest_path=manifest_path,
                assets_dir=assets_dir,
                markdown_sha256=str(expected_markdown_sha),
                docling_json_sha256=str(expected_json_sha),
                assets_sha256=str(expected_assets_sha),
                warnings=tuple(manifest.warnings),
                stats=stats,
            )
        except (KeyError, TypeError, ValidationError) as exc:
            raise ParserError(
                "OUTPUT_CONFLICT", "existing output manifest is incomplete"
            ) from exc

    def _write_failure_manifest(
        self,
        *,
        output_root: Path,
        run_id: str,
        source: Path,
        source_sha: str,
        profile: Any,
        started_at: datetime,
        started_clock: float,
        error: ParserError,
    ) -> Path:
        failure_dir = self._prepare_output_subdirectory(output_root, "failures")
        failure_path = failure_dir / f"{run_id}.manifest.json"
        manifest = RunManifest(
            status="failed",
            run_id=run_id,
            source={"path": str(source), "sha256": source_sha},
            profile={
                "id": profile.id,
                "digest": profile.digest,
                "effective_options": profile.model_dump(mode="json"),
            },
            runtime={
                "parser_version": __version__,
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "packages": self._runtime_package_versions(),
            },
            artifacts={},
            stats={"elapsed_ms": round((time.perf_counter() - started_clock) * 1000)},
            warnings=[],
            error={"code": error.code, "message": error.message},
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
        write_json_atomic(failure_path, manifest.model_dump(mode="json"))
        return failure_path

    @staticmethod
    def _as_parser_error(exc: BaseException) -> ParserError:
        if isinstance(exc, ParserError):
            return exc
        if isinstance(exc, NaverOcrError):
            return ParserError("NAVER_OCR_FAILED", str(exc))
        return ParserError("PARSE_FAILED", str(exc) or exc.__class__.__name__)

    @staticmethod
    def _require_profile_available(profile: Any) -> None:
        available, reason = profile_availability(profile)
        if not available:
            raise ParserError("PROFILE_UNAVAILABLE", reason or "profile unavailable")

    @staticmethod
    def _package_version(name: str) -> str | None:
        try:
            return version(name)
        except PackageNotFoundError:
            return None

    @classmethod
    def _runtime_package_versions(cls) -> dict[str, str | None]:
        return {name: cls._package_version(name) for name in _RUNTIME_PACKAGES}

    @staticmethod
    def _nearest_existing_parent(path: Path) -> Path:
        candidate = path
        while not candidate.exists() and candidate != candidate.parent:
            candidate = candidate.parent
        return candidate

    @classmethod
    def _prepare_output_subdirectory(cls, output_root: Path, name: str) -> Path:
        directory = output_root / name
        try:
            directory.mkdir(exist_ok=True)
        except OSError as exc:
            raise ParserError(
                "OUTPUT_UNAVAILABLE",
                f"output subdirectory cannot be created: {directory}",
            ) from exc
        cls._require_safe_output_directory(
            directory,
            output_root,
            label="output subdirectory",
        )
        return directory

    @classmethod
    def _require_safe_output_directory(
        cls,
        directory: Path,
        output_root: Path,
        *,
        label: str,
    ) -> None:
        try:
            is_safe = directory.is_dir() and cls._path_is_unredirected_within(
                directory,
                output_root,
            )
        except (OSError, RuntimeError) as exc:
            raise ParserError(
                "OUTPUT_CONFLICT",
                f"{label} could not be verified: {directory}",
            ) from exc
        if not is_safe:
            raise ParserError(
                "OUTPUT_CONFLICT",
                f"{label} cannot be a link or junction: {directory}",
            )

    @staticmethod
    def _path_is_unredirected_within(path: Path, root: Path) -> bool:
        """Reject symlinks and Windows junctions, including nested artifact links."""

        resolved_path = path.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
        return path == resolved_path and (
            resolved_path == resolved_root
            or resolved_path.is_relative_to(resolved_root)
        )
