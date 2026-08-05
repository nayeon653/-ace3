"""Docling 결과를 문서별 bundle로 저장한다."""

from __future__ import annotations

import os
import platform
import shutil
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from . import __version__
from .docling_engine import DoclingEngine
from .errors import NaverOcrError, ParserError
from .io_utils import (
    normalize_docling_json_file,
    normalize_markdown_file,
    safe_stem,
    sha256_directory,
    sha256_file,
    write_json_atomic,
)
from .profiles import OcrProvider, profile_for_provider

SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx", ".pptx", ".xlsx"})
_RUNTIME_PACKAGES = (
    "docling",
    "docling-core",
    "easyocr",
    "httpx",
    "torch",
    "torchvision",
    "transformers",
)


def _unresolved_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _has_path_redirection(path: Path) -> bool:
    """경로 자체나 기존 상위 경로에 symlink 또는 Windows junction이 있는지 확인한다."""

    current = _unresolved_absolute(path)
    while True:
        if current.is_symlink():
            return True
        is_junction = getattr(current, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        if current.parent == current:
            return False
        current = current.parent


@dataclass(frozen=True, slots=True)
class ArtifactBundle:
    bundle_id: str
    output_dir: Path
    manifest_path: Path
    markdown_path: Path
    docling_json_path: Path
    assets_dir: Path
    source_sha256: str
    profile_id: str
    profile_digest: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "output_dir",
            "manifest_path",
            "markdown_path",
            "docling_json_path",
            "assets_dir",
        ):
            payload[key] = str(payload[key])
        payload["warnings"] = list(self.warnings)
        return payload


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for package in _RUNTIME_PACKAGES:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return versions


def parse_document(
    source_path: Path,
    output_dir: Path,
    ocr_provider: str | OcrProvider,
    *,
    confirm_external_transfer: bool = False,
) -> ArtifactBundle:
    """문서 하나를 파싱하고 완성된 bundle을 원자적으로 게시한다."""

    provider = OcrProvider(ocr_provider)
    if provider is OcrProvider.NAVER and not confirm_external_transfer:
        raise ParserError(
            "EXTERNAL_TRANSFER_NOT_CONFIRMED",
            "NAVER OCR을 사용하려면 외부 전송을 명시적으로 확인해야 합니다.",
        )

    try:
        if _has_path_redirection(source_path):
            raise ParserError(
                "SOURCE_PATH_REDIRECTED",
                f"원본 경로에 symlink 또는 junction을 사용할 수 없습니다: {source_path}",
            )
        source = source_path.expanduser().resolve(strict=True)
    except ParserError:
        raise
    except (OSError, RuntimeError) as exc:
        raise ParserError(
            "SOURCE_NOT_FOUND", f"원본 파일을 찾을 수 없습니다: {source_path}"
        ) from exc
    if not source.is_file():
        raise ParserError("SOURCE_NOT_FILE", f"원본 경로가 파일이 아닙니다: {source}")
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ParserError(
            "UNSUPPORTED_FORMAT",
            f"지원하지 않는 확장자입니다: {source.suffix.lower()}",
        )

    profile = profile_for_provider(provider)
    try:
        source_sha256 = sha256_file(source)
        source_size = source.stat().st_size
    except OSError as exc:
        raise ParserError("SOURCE_UNAVAILABLE", f"원본 파일을 읽을 수 없습니다: {source}") from exc
    try:
        if _has_path_redirection(output_dir):
            raise ParserError(
                "OUTPUT_PATH_REDIRECTED",
                f"출력 경로에 symlink 또는 junction을 사용할 수 없습니다: {output_dir}",
            )
        root = output_dir.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
    except ParserError:
        raise
    except (OSError, RuntimeError) as exc:
        raise ParserError(
            "OUTPUT_DIR_UNAVAILABLE", f"출력 폴더를 사용할 수 없습니다: {output_dir}"
        ) from exc
    target = root / f"{safe_stem(source.stem)}--{source_sha256[:12]}--{profile.id}"
    if target.exists() or target.is_symlink():
        raise ParserError("OUTPUT_EXISTS", f"기존 결과를 덮어쓰지 않습니다: {target}")

    try:
        stage = Path(tempfile.mkdtemp(prefix=".docling-parser-", dir=root))
    except OSError as exc:
        raise ParserError(
            "OUTPUT_STAGE_FAILED", f"출력 임시 폴더를 만들 수 없습니다: {root}"
        ) from exc
    try:
        from docling_core.types.doc import ImageRefMode

        bundle_id = str(uuid.uuid4())
        result = DoclingEngine(profile).convert(source)
        if sha256_file(source) != source_sha256:
            raise ParserError(
                "SOURCE_CHANGED_DURING_PARSE",
                "파싱 도중 원본 파일 내용이 변경되었습니다.",
            )

        assets_dir = stage / "assets"
        markdown_path = stage / "document.md"
        docling_json_path = stage / "document.docling.json"
        assets_dir.mkdir()

        result.document.save_as_markdown(
            markdown_path,
            artifacts_dir=Path("assets"),
            image_mode=ImageRefMode.REFERENCED,
            traverse_pictures=profile.traverse_pictures,
            compact_tables=False,
        )
        normalize_markdown_file(markdown_path)
        result.document.save_as_json(
            docling_json_path,
            artifacts_dir=Path("assets"),
            image_mode=ImageRefMode.REFERENCED,
            indent=2,
        )
        normalize_docling_json_file(docling_json_path)

        manifest = {
            "schema_version": 4,
            "status": "success",
            "bundle_id": bundle_id,
            "source": {
                "filename": source.name,
                "sha256": source_sha256,
                "size_bytes": source_size,
                "extension": source.suffix.lower(),
            },
            "profile": {
                "id": profile.id,
                "digest": profile.digest,
                "options": profile.to_dict(),
            },
            "runtime": {
                "parser_version": __version__,
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "packages": _package_versions(),
                "docling_conversion": result.conversion_version,
            },
            "artifacts": {
                "markdown": "document.md",
                "markdown_sha256": sha256_file(markdown_path),
                "docling_json": "document.docling.json",
                "docling_json_sha256": sha256_file(docling_json_path),
                "assets": "assets",
                "assets_sha256": sha256_directory(assets_dir),
            },
            "stats": {
                "pages": result.pages,
                "pictures_found": result.pictures_found,
                "pictures_retained": result.pictures_retained,
                "office_pictures_ocrd": result.office_pictures_ocrd,
                "repeated_decorative_pictures_removed": (
                    result.quality.repeated_decorative_pictures_removed
                ),
                "embedded_pictures_requiring_visual_review": (
                    result.quality.embedded_pictures_requiring_visual_review
                ),
                "picture_ocr_text_nodes_isolated": (
                    result.quality.picture_ocr_text_nodes_isolated
                ),
                "repeated_text_nodes_normalized": (
                    result.quality.repeated_text_nodes_normalized
                ),
                "possible_cross_page_table_continuations": len(
                    result.quality.possible_cross_page_table_pairs
                ),
            },
            "quality_signals": {
                "possible_cross_page_table_pairs": [
                    [first, second]
                    for first, second in result.quality.possible_cross_page_table_pairs
                ],
            },
            "warnings": result.warnings,
            "created_at": datetime.now(UTC).isoformat(),
        }
        write_json_atomic(stage / "manifest.json", manifest)

        try:
            stage.replace(target)
        except OSError as exc:
            raise ParserError(
                "OUTPUT_PUBLISH_FAILED", f"결과를 게시할 수 없습니다: {target}"
            ) from exc

        return ArtifactBundle(
            bundle_id=bundle_id,
            output_dir=target,
            manifest_path=target / "manifest.json",
            markdown_path=target / "document.md",
            docling_json_path=target / "document.docling.json",
            assets_dir=target / "assets",
            source_sha256=source_sha256,
            profile_id=profile.id,
            profile_digest=profile.digest,
            warnings=tuple(result.warnings),
        )
    except ParserError:
        raise
    except NaverOcrError as exc:
        raise ParserError("NAVER_OCR_FAILED", str(exc)) from exc
    except Exception as exc:
        raise ParserError("PARSE_FAILED", str(exc) or exc.__class__.__name__) from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
