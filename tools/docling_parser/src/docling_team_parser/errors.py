"""파싱 스크립트가 사용하는 오류 타입."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ParserError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class NaverOcrError(RuntimeError):
    """NAVER OCR 요청 또는 응답이 유효하지 않을 때 발생한다."""
