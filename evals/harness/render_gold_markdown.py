"""한투 30문항 Gold Answer를 사람이 읽는 Markdown 표로 렌더링한다."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MANIFEST = _PROJECT_ROOT / "evals/gold/hantoo_selected_30.manifest.json"
_DEFAULT_DATASET = _PROJECT_ROOT / "evals/gold/hantoo_selected_30.jsonl"
_DEFAULT_OUTPUT = _PROJECT_ROOT / "evals/gold/hantoo_selected_30.table.md"
_ANSWERABILITY_LABELS = {
    "supported": "직접 지원",
    "partial": "부분 지원",
    "unsupported": "미지원",
    "temporal_gap": "최신성 공백",
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path}: JSON 최상위 값이 객체가 아닙니다")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise TypeError(f"{path}:{line_number}: JSONL 값이 객체가 아닙니다")
        rows.append(value)
    return rows


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")


def _source_link(source: dict[str, Any]) -> str:
    drive = source.get("drive", {})
    if not isinstance(drive, dict):
        return str(source["source_file"])
    url = drive.get("url")
    if not isinstance(url, str):
        folder_id = drive.get("folder_id")
        url = (
            f"https://drive.google.com/drive/folders/{folder_id}"
            if isinstance(folder_id, str)
            else None
        )
    source_file = str(source["source_file"])
    return f"[{source_file}]({url})" if url else source_file


def _format_provenance(evidence: dict[str, Any]) -> str:
    provenance = evidence.get("provenance")
    if not isinstance(provenance, dict):
        return "페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정"

    parts = [f"page/slide `{provenance['page_no']}`"]
    charspan = provenance.get("charspan")
    if isinstance(charspan, list) and len(charspan) == 2:
        parts.append(f"charspan `{charspan[0]}:{charspan[1]}`")
    bbox = provenance.get("bbox")
    if isinstance(bbox, dict):
        serialized = json.dumps(bbox, ensure_ascii=False, separators=(",", ":"))
        parts.append(f"bbox `{serialized}`")
    return "; ".join(parts)


def _format_selection(evidence: dict[str, Any]) -> str | None:
    selection = evidence.get("selection")
    if not isinstance(selection, dict) or selection.get("kind") != "table_cells":
        return None
    cells = selection.get("cells", [])
    if not isinstance(cells, list):
        return None
    formatted = [
        f"r{cell['row']}c{cell['column']}"
        for cell in cells
        if isinstance(cell, dict) and "row" in cell and "column" in cell
    ]
    return "table cells `" + ", ".join(formatted) + "`" if formatted else None


def _format_evidence(
    evidence_id: str,
    evidence: dict[str, Any],
    sources: dict[str, Any],
) -> str:
    source_key = evidence["source_key"]
    source = sources[source_key]
    location = [
        f"**{evidence_id}** — {_source_link(source)}",
        f"`{evidence['item_ref']}` · label `{evidence['item_label']}`",
        _format_provenance(evidence),
    ]
    drive = source.get("drive")
    if isinstance(drive, dict) and drive.get("kind") == "archive_member":
        location.append(f"Drive archive `{drive['archive']}` · member `{drive['member']}`")
    if not isinstance(evidence.get("provenance"), dict):
        location.append(
            f"source SHA-256 `{source['source_sha256']}` · "
            f"Docling JSON SHA-256 `{source['docling_json_sha256']}`"
        )
    selection = _format_selection(evidence)
    if selection:
        location.append(selection)
    retrieval = evidence.get("retrieval")
    if isinstance(retrieval, dict):
        location.append(f"retrieval `{retrieval['chunk_id']}`")
    location.append(f"인용: “{evidence['quote']}”")
    return "<br>".join(location)


def _format_claims(row: dict[str, Any]) -> str:
    claims = row.get("required_claims", [])
    if not claims:
        return "직접 확정할 필수 주장 없음"
    return "<br>".join(
        f"**{claim['id']}** {claim['text']}<br>근거: {', '.join(claim['evidence_ids'])}"
        for claim in claims
    )


def _format_constraints(row: dict[str, Any]) -> str:
    parts: list[str] = []
    gaps = row.get("known_gaps", [])
    if gaps:
        parts.append("**부족 근거**<br>" + "<br>".join(f"• {gap}" for gap in gaps))
    prohibited = row.get("must_not_claim", [])
    if prohibited:
        parts.append("**금지 주장**<br>" + "<br>".join(f"• {claim}" for claim in prohibited))
    return "<br><br>".join(parts) if parts else "없음"


def _render_table(
    rows: list[dict[str, Any]],
    evidence_registry: dict[str, Any],
    sources: dict[str, Any],
) -> str:
    lines = [
        "| ID | 질문 | 근거충분도 | 목표 답변 | 필수 주장 | 문서 내 정확한 근거 위치 | 부족 근거·금지 주장 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        evidence_items = [
            _format_evidence(evidence_id, evidence_registry[evidence_id], sources)
            for evidence_id in row["evidence_ids"]
        ]
        cells = [
            str(row["test_id"]),
            str(row["question"]),
            _ANSWERABILITY_LABELS[str(row["answerability"])],
            str(row["gold_answer"]),
            _format_claims(row),
            "<br><br>".join(evidence_items) if evidence_items else "직접 근거 없음",
            _format_constraints(row),
        ]
        lines.append("| " + " | ".join(_escape_cell(cell) for cell in cells) + " |")
    return "\n".join(lines)


def render_gold_markdown(
    *,
    repo_root: Path,
    manifest_path: Path,
    dataset_path: Path,
) -> str:
    """고정된 Gold Answer와 evidence registry를 Markdown 표로 렌더링한다."""

    manifest = _load_json(manifest_path)
    rows = _load_jsonl(dataset_path)
    evidence_path = repo_root / manifest["evidence_registry"]["path"]
    source_path = repo_root / manifest["source_registry"]["path"]
    evidence_registry = _load_json(evidence_path)["evidence"]
    sources = _load_json(source_path)["sources"]
    if not isinstance(evidence_registry, dict) or not isinstance(sources, dict):
        raise TypeError("evidence 또는 source registry가 객체가 아닙니다")

    counts = Counter(str(row["answerability"]) for row in rows)
    product_rows = [row for row in rows if str(row["test_id"]).startswith("PROD-")]
    policy_rows = [row for row in rows if str(row["test_id"]).startswith("POLICY-")]
    header = f"""# PR #128 한투 30문항 Gold Answer 표

이 문서는 [Gold Answer JSONL](hantoo_selected_30.jsonl)을 사람이 검토하기 쉽게 표로 투영한 파일이다. 정규 원본은 JSONL이며, 이 표는 아래 명령으로 결정론적으로 재생성한다.

```bash
uv run python -m evals.harness.render_gold_markdown
```

## 범위와 판정 기준

- 질문: `{len(rows)}`건 (`PROD {len(product_rows)}` / `POLICY {len(policy_rows)}`)
- 근거충분도: 직접 지원 `{counts["supported"]}`, 부분 지원 `{counts["partial"]}`, 미지원 `{counts["unsupported"]}`, 최신성 공백 `{counts["temporal_gap"]}`
- Gold JSONL SHA-256: `{manifest["gold_dataset"]["sha256"]}`
- 페이지가 없는 DOCX는 원본 SHA-256, Docling JSON SHA-256과 `item_ref`가 정규 위치다.
- bbox와 표 셀 좌표는 Docling 값 그대로이며 표의 행·열은 0-based다.
- `부분 지원`, `미지원`, `최신성 공백`도 우리 에이전트가 생성해야 하는 안전한 목표 답변을 포함한다.

## 상품·운용 질문

{_render_table(product_rows, evidence_registry, sources)}

## 업무·제도 질문

{_render_table(policy_rows, evidence_registry, sources)}
"""
    return header.rstrip() + "\n"


def main() -> int:
    """Markdown 정답표를 생성하거나 현재 파일과 일치하는지 확인한다."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_PROJECT_ROOT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    output_path = args.output or repo_root / "evals/gold/hantoo_selected_30.table.md"
    rendered = render_gold_markdown(
        repo_root=repo_root,
        manifest_path=args.manifest or repo_root / "evals/gold/hantoo_selected_30.manifest.json",
        dataset_path=args.dataset or repo_root / "evals/gold/hantoo_selected_30.jsonl",
    )
    if args.check:
        if not output_path.is_file() or output_path.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Markdown Gold 표가 현재 JSONL과 일치하지 않습니다.")
        print(f"up-to-date: {output_path}")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(f"written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
