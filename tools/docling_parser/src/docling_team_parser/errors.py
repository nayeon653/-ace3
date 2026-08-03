"""CLI 어댑터가 노출하는 안정적인 파서 오류 타입."""

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
    """NAVER OCR 요청 또는 응답이 유효하지 않을 때 발생한다."""
