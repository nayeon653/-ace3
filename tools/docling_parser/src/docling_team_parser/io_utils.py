"""결정적이며 원자적으로 동작하는 소규모 I/O 도우미."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

_MARKDOWN_ASSET_LINK = re.compile(r"(\]\(<?)(assets\\[^)\n>]*)(>?\))")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_directory(path: Path) -> str:
    """상대 파일명과 바이트를 일정한 순서로 해시한다."""

    digest = hashlib.sha256()
    for file_path in sorted(
        (candidate for candidate in path.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(path).as_posix(),
    ):
        relative = file_path.relative_to(path).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        with file_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def safe_stem(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z가-힣._-]+", "-", value).strip("-._")
    return normalized[:80] or "document"


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        temp_path.replace(path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def normalize_markdown_file(path: Path) -> None:
    def normalize_asset_link(match: re.Match[str]) -> str:
        asset_path = match.group(2).replace("\\", "/")
        return f"{match.group(1)}{asset_path}{match.group(3)}"

    text = path.read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _MARKDOWN_ASSET_LINK.sub(normalize_asset_link, text)
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def normalize_docling_json_file(path: Path) -> None:
    """Windows에서 생성된 상대 이미지 URI만 POSIX 형식으로 바꾼다."""

    def normalize(value: Any) -> Any:
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            result = {key: normalize(item) for key, item in value.items()}
            uri = result.get("uri")
            if isinstance(uri, str) and uri.startswith("assets\\"):
                result["uri"] = uri.replace("\\", "/")
            return result
        return value

    payload = json.loads(path.read_text(encoding="utf-8"))
    write_json_atomic(path, normalize(payload))
