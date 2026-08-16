"""파싱 bundle(document.docling.json)을 얇은 NormalizedDocument로 변환한다.

Docling 파서 라이브러리는 import하지 않는다 — bundle의 JSON만 읽는다. 청킹 정책
(길이 제한, heading 경로 조립)은 여기 포함하지 않는다 — PROJECT_RULES.md상 현재
작업 범위는 파싱까지다. 근거: experiments/chunking-ab A/B 실험 (docs/experiments.md
"2026-08-15 청킹 전 Normalization layer 필요성 A/B").

투자설명서(제N부 구조)는 raw Docling JSON 단계에서 계층을 복원한 뒤 이미 올바른
level이 채워진 NormalizedBlock만 내보낸다 — chunker는 label/marker/orig를 몰라도
된다. 근거: experiments/prospectus-full-survey 92건 전수조사.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

from pension_agent.core.documents import NormalizedBlock, NormalizedDocument
from pension_agent.ingest.heading_recovery import recover_doc55_heading_hierarchy

_FURNITURE_LABELS = {"page_header", "page_footer", "checkbox_unselected"}
_HEADING_LINE = re.compile(r"^(#{1,3}) (.+)$")

# 투자설명서 hierarchy 복원 — 공백 변형(제2부/제 2 부, 가./가 .)을 전부 허용한다.
_PART_RE = re.compile(r"^제\s*(\d+)\s*부\s*[.\s]?")
_ITEM_EVENT_RE = re.compile(r"(?<!\d)(\d{1,2})\s*\.(?=\s)")
_SUBITEM_EVENT_RE = re.compile(r"([가나다라마바사아자차카타파하])\s*\.(?=\s)")


def normalize_document(bundle_dir: Path) -> NormalizedDocument:
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    raw = json.loads((bundle_dir / "document.docling.json").read_text(encoding="utf-8"))

    source = manifest["source"]
    doc_id = Path(source["filename"]).stem
    doc_type = source["extension"].lstrip(".")
    metadata = {
        "filename": source["filename"],
        "ocr_profile": manifest["profile"]["id"],
        "pages": manifest["stats"]["pages"],
    }

    if doc_id == "doc55":
        markdown = (bundle_dir / "document.md").read_text(encoding="utf-8")
        blocks = _blocks_from_recovered_markdown(markdown)
    else:
        ordered_texts = list(_collect_ordered_texts(raw, raw["body"]["children"]))
        real_parts = _select_real_prospectus_parts(ordered_texts) or None
        blocks = list(_walk(raw, raw["body"]["children"], sheet=None, prospectus_parts=real_parts))

    return NormalizedDocument(doc_id=doc_id, doc_type=doc_type, metadata=metadata, blocks=blocks)


def _resolve_ref(ref: dict) -> tuple[str, int]:
    collection, idx = ref["$ref"].lstrip("#/").split("/")
    return collection, int(idx)


def _first_page(item: dict) -> int | None:
    prov = item.get("prov") or []
    return prov[0]["page_no"] if prov else None


def _table_grid(table_item: dict) -> list[list[str]]:
    data = table_item["data"]
    grid = [["" for _ in range(data["num_cols"])] for _ in range(data["num_rows"])]
    for cell in data["table_cells"]:
        row, col = cell["start_row_offset_idx"], cell["start_col_offset_idx"]
        if row < data["num_rows"] and col < data["num_cols"]:
            grid[row][col] = cell["text"]
    return grid


def _walk(
    raw: dict,
    refs: list[dict],
    sheet: str | None,
    visited: set[tuple[str, int]] | None = None,
    prospectus_parts: dict[str, int] | None = None,
    prospectus_state: list[bool] | None = None,
) -> Iterator[NormalizedBlock]:
    """body.children을 document order 그대로 재귀한다.

    pictures.children도 재귀한다 — 투자설명서 92건 전수조사 결과, 본문 텍스트가
    OCR된 picture의 자식으로 붙는 경우가 전 문서에서 나타났고(예: KR5118420036의
    "제 4 부" 헤딩이 picture 759개 자식 중 하나), groups만 재귀하면 문서당
    30~40%의 텍스트가 조용히 누락됐다. visited로 동일 노드 재방문·순환 참조를
    막는다(Docling JSON은 정상적으로는 DAG이지만 방어적으로 차단).

    prospectus_parts가 있으면(투자설명서로 판정된 문서) label을 신뢰하지 않고
    _prospectus_text_blocks가 text/orig/marker 기반으로 heading 여부와 level을
    직접 판정한다 — 그 외 문서는 기존 label 기반 분류를 그대로 쓴다.
    prospectus_state[0]은 실제 제1~5부 본문에 진입했는지를 문서 순서대로 추적하는
    단일 플래그다(한 번 True가 되면 유지) — _prospectus_text_blocks가 갱신한다.
    """

    if visited is None:
        visited = set()
    if prospectus_parts is not None and prospectus_state is None:
        prospectus_state = [False]
    for ref in refs:
        collection, idx = _resolve_ref(ref)
        key = (collection, idx)
        if key in visited:
            continue
        visited.add(key)
        item = raw[collection][idx]

        if collection == "texts":
            label = item["label"]
            if label in _FURNITURE_LABELS:
                pass
            elif prospectus_parts is not None:
                yield from _prospectus_text_blocks(item, prospectus_parts, prospectus_state)
            elif label == "section_header":
                yield NormalizedBlock(
                    type="heading",
                    text=item["text"],
                    level=item.get("level") or 1,
                    page=_first_page(item),
                )
            else:
                yield NormalizedBlock(type="text", text=item["text"], page=_first_page(item))
        elif collection == "tables":
            block_type = "faq" if sheet and "FAQ" in sheet else "table"
            yield NormalizedBlock(
                type=block_type, table_data=_table_grid(item), page=_first_page(item)
            )
        elif collection in ("groups", "pictures"):
            next_sheet = item.get("name") if item["label"] == "sheet" else sheet
            yield from _walk(
                raw,
                item.get("children", []),
                sheet=next_sheet,
                visited=visited,
                prospectus_parts=prospectus_parts,
                prospectus_state=prospectus_state,
            )


def _collect_ordered_texts(
    raw: dict, refs: list[dict], visited: set[tuple[str, int]] | None = None
) -> Iterator[dict]:
    """texts만, document order 그대로. 제N부 표지/본문 판정을 위한 사전 스캔용."""

    if visited is None:
        visited = set()
    for ref in refs:
        collection, idx = _resolve_ref(ref)
        key = (collection, idx)
        if key in visited:
            continue
        visited.add(key)
        item = raw[collection][idx]
        if collection == "texts":
            yield item
        elif collection in ("groups", "pictures"):
            yield from _collect_ordered_texts(raw, item.get("children", []), visited)


def _prospectus_source_text(item: dict) -> str:
    """list_item은 marker가 text에서 빠져있으니 orig(=marker+text)를 우선한다."""

    return (item.get("orig") or item.get("text") or "").strip()


def _select_real_prospectus_parts(ordered_texts: list[dict]) -> dict[str, int]:
    """표지/목차 echo와 실제 본문 제N부를, document order + 1→5 monotonic

    sequence로 구분한다. 각 부는 문서 순서상 직전에 선택된 부보다 뒤에 있는
    occurrence 중 가장 마지막 것을 고른다(echo는 앞쪽에 몰려있고 본문은 뒤로
    갈수록 순서대로 나온다는 corpus 전체 관찰과 일치).
    """

    candidates: dict[int, list[tuple[int, dict]]] = {}
    for pos, item in enumerate(ordered_texts):
        match = _PART_RE.match(_prospectus_source_text(item))
        if not match:
            continue
        part_no = int(match.group(1))
        if 1 <= part_no <= 5:
            candidates.setdefault(part_no, []).append((pos, item))

    selected: dict[str, int] = {}
    last_position = -1
    for part_no in range(1, 6):
        options = [(pos, item) for pos, item in candidates.get(part_no, []) if pos > last_position]
        if not options:
            continue
        pos, item = max(options, key=lambda option: option[0])
        selected[item["self_ref"]] = part_no
        last_position = pos
    return selected


def _prospectus_events(source: str) -> list[tuple[int, str]]:
    """N./가나다 패턴을 전부 찾아 (level, 내용) 이벤트로 쪼갠다.

    부모(N.)와 자식(가/나/다)이 한 node에 합쳐진 경우, 두 번째 패턴부터를 별도
    heading으로 분리한다("3. 제목 가. 소제목" -> level2 "3. 제목" + level3
    "가. 소제목"). 맨 앞이 패턴으로 시작하지 않으면(본문 문장 중간에 번호가
    우연히 나온 경우) heading으로 인정하지 않는다.
    """

    matches = [(m.start(), 2) for m in _ITEM_EVENT_RE.finditer(source)]
    matches += [(m.start(), 3) for m in _SUBITEM_EVENT_RE.finditer(source)]
    if not matches:
        return []
    matches.sort(key=lambda m: m[0])
    first_start = matches[0][0]
    if source[:first_start].strip():
        return []

    events: list[tuple[int, str]] = []
    for i, (start, level) in enumerate(matches):
        end = matches[i + 1][0] if i + 1 < len(matches) else len(source)
        content = source[start:end].strip()
        if content:
            events.append((level, content))
    return events


def _prospectus_text_blocks(
    item: dict, real_parts: dict[str, int], state: list[bool]
) -> Iterator[NormalizedBlock]:
    """실제 제1~5부 본문(state[0])에 들어가기 전에는 N./가나다를 heading으로

    승격하지 않는다. 법정 유의사항·안내문 등도 "1.", "2.", "13." 같은 번호를
    쓰는데, 이건 제N부 내부 항목 번호와 형식이 같아 구분 없이 heading으로
    잘못 승격되면(예: KR5118420036의 "13. ESG집합투자기구의 경우...") 실제
    제1부가 나오기 전까지 이후 chunk들의 section_path를 전부 오염시킨다.
    본문 진입 전 텍스트는 버리지 않고 일반 text로 보존한다.
    """

    page = _first_page(item)
    if item.get("self_ref") in real_parts:
        state[0] = True
        yield NormalizedBlock(
            type="heading", text=_prospectus_source_text(item), level=1, page=page
        )
        return

    if not state[0]:
        yield NormalizedBlock(type="text", text=item["text"], page=page)
        return

    events = _prospectus_events(_prospectus_source_text(item))
    if events:
        for level, content in events:
            yield NormalizedBlock(type="heading", text=content, level=level, page=page)
        return

    yield NormalizedBlock(type="text", text=item["text"], page=page)


def _blocks_from_recovered_markdown(markdown: str) -> list[NormalizedBlock]:
    """doc55 전용 경로. page는 항상 None이다 — 확인 결과 이 문서의

    document.docling.json에는 heading/text/table 어디에도 page provenance가
    없다(furniture 3건 제외, pages 딕셔너리도 비어 있음: docs/experiments.md
    참고). 대신 이 함수가 만드는 heading block들의 순서 자체가 section_path
    (예: "Ⅰ. 부담금 납입 업무 > 1. 부담금 종류")이므로, doc55 block을 찾을 때는
    page가 아니라 직전에 등장한 heading block 시퀀스를 source locator로 쓴다.
    """

    recovered = recover_doc55_heading_hierarchy(markdown)
    blocks: list[NormalizedBlock] = []
    table_lines: list[str] = []

    def flush_table() -> None:
        if table_lines:
            rows = [
                [cell.strip() for cell in line.strip("|").split("|")]
                for line in table_lines
                if set(line.strip()) != {"-", "|", " "}
            ]
            blocks.append(NormalizedBlock(type="table", table_data=rows))
            table_lines.clear()

    for line in recovered.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            table_lines.append(stripped)
            continue
        flush_table()
        heading = _HEADING_LINE.match(stripped)
        if heading:
            blocks.append(
                NormalizedBlock(type="heading", text=heading.group(2), level=len(heading.group(1)))
            )
        elif stripped:
            blocks.append(NormalizedBlock(type="text", text=stripped))
    flush_table()
    return blocks
