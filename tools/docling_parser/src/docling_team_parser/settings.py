"""Runtime settings and path authorization."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import ParserError


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    allowed_roots: tuple[Path, ...]
    default_output_root: Path

    @classmethod
    def from_env(cls) -> RuntimeSettings:
        raw_roots = os.environ.get("DOCLING_PARSER_ALLOWED_ROOTS")
        try:
            if raw_roots:
                roots = tuple(
                    Path(value.strip()).expanduser().resolve()
                    for value in raw_roots.split(os.pathsep)
                    if value.strip()
                )
            else:
                project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
                roots = (
                    Path(project_dir.strip()).resolve()
                    if project_dir and project_dir.strip()
                    else Path.cwd().resolve(),
                )
        except (OSError, RuntimeError) as exc:
            raise ParserError(
                "CONFIG_INVALID", "allowed roots could not be resolved"
            ) from exc

        if not roots:
            raise ParserError("CONFIG_INVALID", "no allowed roots are configured")

        raw_output = os.environ.get("DOCLING_PARSER_OUTPUT_ROOT")
        try:
            output_root = (
                Path(raw_output.strip()).expanduser().resolve()
                if raw_output and raw_output.strip()
                else roots[0] / ".docling-parser" / "outputs"
            )
        except (OSError, RuntimeError) as exc:
            raise ParserError(
                "CONFIG_INVALID", "default output root could not be resolved"
            ) from exc
        return cls(allowed_roots=roots, default_output_root=output_root)

    def authorize_existing_file(self, path: Path) -> Path:
        try:
            resolved = path.expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ParserError(
                "SOURCE_NOT_FOUND", f"source is unavailable: {path}"
            ) from exc
        if not resolved.is_file():
            raise ParserError("SOURCE_NOT_FILE", f"source is not a file: {resolved}")
        self._require_in_allowed_root(resolved)
        return resolved

    def authorize_existing_dir(self, path: Path) -> Path:
        try:
            resolved = path.expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ParserError(
                "SOURCE_DIRECTORY_NOT_FOUND", f"source directory is unavailable: {path}"
            ) from exc
        if not resolved.is_dir():
            raise ParserError(
                "SOURCE_NOT_DIRECTORY", f"source is not a directory: {resolved}"
            )
        self._require_in_allowed_root(resolved)
        return resolved

    def authorize_output_dir(self, path: Path | None) -> Path:
        try:
            resolved = (path or self.default_output_root).expanduser().resolve()
        except (OSError, RuntimeError) as exc:
            raise ParserError(
                "OUTPUT_UNAVAILABLE", f"output path is unavailable: {path}"
            ) from exc
        self._require_in_allowed_root(resolved)
        if resolved.exists() and not resolved.is_dir():
            raise ParserError(
                "OUTPUT_NOT_DIRECTORY", f"output path is not a directory: {resolved}"
            )
        return resolved

    def _require_in_allowed_root(self, path: Path) -> None:
        if not any(
            path == root or path.is_relative_to(root) for root in self.allowed_roots
        ):
            raise ParserError(
                "PATH_OUTSIDE_ALLOWED_ROOT",
                f"path is outside configured roots: {path}",
            )
