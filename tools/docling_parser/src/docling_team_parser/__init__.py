"""팀에서 사용하는 Docling 파서와 NAVER OCR 확장."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mirae-docling-cli-parser")
except PackageNotFoundError:  # pragma: no cover - 설치하지 않은 소스 체크아웃 환경
    __version__ = "0.1.0"

__all__ = ["__version__"]
