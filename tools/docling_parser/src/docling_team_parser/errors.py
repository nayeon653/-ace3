"""Stable parser error types exposed by the CLI adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ParserError(Exception):
    code: str
    message: str
    failure_manifest_path: Path | None = None

    def __str__(self) -> str:
        suffix = (
            f" Failure manifest: {self.failure_manifest_path}"
            if self.failure_manifest_path
            else ""
        )
        return f"{self.code}: {self.message}{suffix}"


class NaverOcrError(RuntimeError):
    """Raised when a NAVER OCR request or response is invalid."""
