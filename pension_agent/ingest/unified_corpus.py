"""Prospectus + Knowledge Docs unified vector corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

PROSPECTUS_CHUNKS = REPO_ROOT / "data" / "indexes" / "prospectus" / "chunks.jsonl"
KNOWLEDGE_CHUNKS = REPO_ROOT / "data" / "indexes" / "knowledge_docs" / "chunks.jsonl"

OUTPUT_ROOT = REPO_ROOT / "data" / "indexes" / "unified"
OUTPUT_CHUNKS = OUTPUT_ROOT / "chunks.jsonl"

EXPECTED_SCHEMA = {
    "chunk_id",
    "canonical_doc_id",
    "doc_type",
    "text",
    "section_path",
    "page_start",
    "page_end",
    "metadata",
    "content_hash",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            row = json.loads(line)

            if set(row) != EXPECTED_SCHEMA:
                raise ValueError(f"{path}:{line_number}: schema mismatch got={sorted(row)}")

            rows.append(row)

    return rows


def write_jsonl(
    rows: list[dict[str, Any]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False))
            file.write("\n")


def main() -> None:
    prospectus_rows = read_jsonl(PROSPECTUS_CHUNKS)
    knowledge_rows = read_jsonl(KNOWLEDGE_CHUNKS)

    if len(prospectus_rows) != 18_995:
        raise ValueError(f"expected 18,995 prospectus chunks, got {len(prospectus_rows)}")

    if len(knowledge_rows) != 782:
        raise ValueError(f"expected 782 knowledge chunks, got {len(knowledge_rows)}")

    rows = prospectus_rows + knowledge_rows

    if len(rows) != 19_777:
        raise ValueError(f"expected 19,777 unified chunks, got {len(rows)}")

    chunk_ids = [row["chunk_id"] for row in rows]

    if len(set(chunk_ids)) != len(chunk_ids):
        raise ValueError("duplicate chunk_id across unified corpus")

    if any(not row["text"].strip() for row in rows):
        raise ValueError("empty chunk text found")

    prospectus_ids = {row["canonical_doc_id"] for row in prospectus_rows}

    knowledge_ids = {row["canonical_doc_id"] for row in knowledge_rows}

    if prospectus_ids & knowledge_ids:
        raise ValueError("canonical_doc_id collision between corpora")

    write_jsonl(rows, OUTPUT_CHUNKS)

    print(f"prospectus chunks: {len(prospectus_rows)}")
    print(f"knowledge chunks: {len(knowledge_rows)}")
    print(f"unified chunks: {len(rows)}")
    print(f"unique chunk_ids: {len(set(chunk_ids))}")
    print(f"output: {OUTPUT_CHUNKS}")


if __name__ == "__main__":
    main()
