"""Gold answer 근거를 Docling 원본 항목과 검색 청크에 연결한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class DoclingItem:
    """Docling 문서 안에서 직접 인용할 수 있는 항목이다."""

    bundle_path: Path
    manifest: dict[str, Any]
    document: dict[str, Any]
    item_ref: str
    item: dict[str, Any]
    text: str


def sha256_file(path: Path) -> str:
    """파일의 SHA-256을 계산한다."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_text(value: str) -> str:
    """공백 차이를 무시하는 근거 대조용 문자열을 만든다."""

    return " ".join(value.split())


def table_text(item: dict[str, Any]) -> str:
    """병합 셀 중복 없이 표 셀 텍스트를 읽기 순서로 직렬화한다."""

    cells = item.get("data", {}).get("table_cells", [])
    ordered = sorted(
        cells,
        key=lambda cell: (
            cell.get("start_row_offset_idx", -1),
            cell.get("start_col_offset_idx", -1),
        ),
    )
    return "\n".join(str(cell.get("text", "")) for cell in ordered if cell.get("text"))


def item_text(item: dict[str, Any]) -> str:
    """텍스트·표 항목에서 인용 가능한 문자열을 꺼낸다."""

    if item.get("label") == "table":
        return table_text(item)
    return str(item.get("text") or item.get("orig") or "")


def iter_document_items(document: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """근거로 사용할 수 있는 Docling 텍스트·표 항목을 순회한다."""

    for collection_name in ("texts", "tables", "pictures", "key_value_items", "form_items"):
        for index, item in enumerate(document.get(collection_name, [])):
            item_ref = str(item.get("self_ref") or f"#/{collection_name}/{index}")
            yield item_ref, item


def iter_bundles(docling_root: Path) -> Iterator[tuple[Path, dict[str, Any], dict[str, Any]]]:
    """완성된 Docling bundle과 manifest를 순회한다."""

    for bundle_path in sorted(path for path in docling_root.iterdir() if path.is_dir()):
        manifest_path = bundle_path / "manifest.json"
        document_path = bundle_path / "document.docling.json"
        if not manifest_path.is_file() or not document_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        document = json.loads(document_path.read_text(encoding="utf-8"))
        yield bundle_path, manifest, document


def find_items(
    docling_root: Path,
    pattern: re.Pattern[str],
    *,
    source_id: str | None = None,
) -> Iterator[DoclingItem]:
    """정규식과 선택적 source ID로 Docling 항목을 검색한다."""

    for bundle_path, manifest, document in iter_bundles(docling_root):
        filename = str(manifest.get("source", {}).get("filename", ""))
        if source_id and Path(filename).stem.casefold() != source_id.casefold():
            continue
        for item_ref, item in iter_document_items(document):
            text = item_text(item)
            if pattern.search(text):
                yield DoclingItem(bundle_path, manifest, document, item_ref, item, text)


def resolve_item(document: dict[str, Any], item_ref: str) -> dict[str, Any]:
    """지원하는 Docling self_ref를 실제 항목으로 해석한다."""

    match = re.fullmatch(r"#/([^/]+)/(\d+)", item_ref)
    if match is None:
        raise ValueError(f"지원하지 않는 Docling item_ref입니다: {item_ref}")
    collection_name, raw_index = match.groups()
    collection = document.get(collection_name)
    if not isinstance(collection, list):
        raise TypeError(f"Docling collection이 없습니다: {collection_name}")
    return collection[int(raw_index)]


def select_table_cells(
    item: dict[str, Any],
    selections: list[dict[str, int]],
) -> str:
    """지정된 행·열 시작 좌표의 표 셀 텍스트를 반환한다."""

    cells = item.get("data", {}).get("table_cells", [])
    selected: list[str] = []
    for selection in selections:
        row = selection["row"]
        column = selection["column"]
        matches = [
            cell
            for cell in cells
            if cell.get("start_row_offset_idx") == row
            and cell.get("start_col_offset_idx") == column
        ]
        if len(matches) != 1:
            raise ValueError(f"표 셀을 하나로 해석할 수 없습니다: row={row}, column={column}")
        selected.append(str(matches[0].get("text", "")))
    return "\n".join(selected)


def _search_command(args: argparse.Namespace) -> int:
    pattern = re.compile(args.pattern, re.IGNORECASE)
    matches = find_items(args.docling_root, pattern, source_id=args.source_id)
    for match in matches:
        manifest = match.manifest
        source = manifest["source"]
        preview = normalize_text(match.text)[: args.preview_chars]
        payload = {
            "source_file": source["filename"],
            "source_sha256": source["sha256"],
            "bundle_id": manifest["bundle_id"],
            "bundle_path": str(match.bundle_path),
            "profile_id": manifest["profile"]["id"],
            "profile_digest": manifest["profile"]["digest"],
            "docling_json_sha256": manifest["artifacts"]["docling_json_sha256"],
            "item_ref": match.item_ref,
            "item_label": match.item.get("label"),
            "provenance": match.item.get("prov", []),
            "preview": preview,
        }
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    """Docling 근거 항목 검색 CLI를 실행한다."""

    parser = argparse.ArgumentParser()
    parser.add_argument("pattern")
    parser.add_argument("--docling-root", type=Path, required=True)
    parser.add_argument("--source-id")
    parser.add_argument("--preview-chars", type=int, default=500)
    return _search_command(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
