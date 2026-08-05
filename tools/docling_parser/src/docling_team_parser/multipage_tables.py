"""페이지별로 분리된 연속 표를 하나의 Docling 표로 병합한다."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

_BOTTOM_TABLE_EDGE_RATIO = 0.85
_TOP_TABLE_EDGE_RATIO = 0.15
_TABLE_HORIZONTAL_TOLERANCE_RATIO = 0.05
_TABLE_LEADING_CONTENT_TOLERANCE_RATIO = 0.004
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class MergedTableSegment:
    source_table_ref: str
    page_no: int
    source_rows: int
    output_row_start: int
    output_row_end: int
    repeated_header_rows_removed: int
    continuation_row_merged_into: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_table_ref": self.source_table_ref,
            "page_no": self.page_no,
            "source_rows": self.source_rows,
            "output_row_start": self.output_row_start,
            "output_row_end": self.output_row_end,
            "repeated_header_rows_removed": self.repeated_header_rows_removed,
            "continuation_row_merged_into": self.continuation_row_merged_into,
        }


@dataclass(frozen=True, slots=True)
class MergedMultipageTable:
    table_ref: str
    pages: tuple[int, ...]
    segments: tuple[MergedTableSegment, ...]

    @property
    def repeated_header_rows_removed(self) -> int:
        return sum(item.repeated_header_rows_removed for item in self.segments)

    @property
    def continuation_rows_merged(self) -> int:
        return sum(
            item.continuation_row_merged_into is not None for item in self.segments
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_ref": self.table_ref,
            "pages": list(self.pages),
            "segments": [item.to_dict() for item in self.segments],
        }


@dataclass(frozen=True, slots=True)
class MultipageTableMergeReport:
    merged_tables: tuple[MergedMultipageTable, ...]
    unmerged_page_pairs: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class _TableContinuation:
    first: Any
    second: Any
    first_page_no: int
    second_page_no: int


@dataclass(slots=True)
class _PendingMergedTable:
    survivor: Any
    pages: tuple[int, ...]
    segments: tuple[MergedTableSegment, ...]


def merge_multipage_tables(
    document: Any,
    *,
    enabled: bool,
) -> MultipageTableMergeReport:
    """고신뢰 연속 표를 병합하고 병합 전 segment의 행 provenance를 반환한다."""

    candidates = _find_table_continuations(document)
    if not candidates:
        return MultipageTableMergeReport(merged_tables=(), unmerged_page_pairs=())
    if not enabled:
        return MultipageTableMergeReport(
            merged_tables=(),
            unmerged_page_pairs=_page_pairs(candidates),
        )

    mergeable = [item for item in candidates if _can_merge(item)]
    unmerged = [item for item in candidates if not _can_merge(item)]
    groups = _continuation_groups(mergeable)
    grouped_ids = {
        id(table)
        for group in groups
        for table in group
    }
    unmerged.extend(
        item
        for item in mergeable
        if id(item.first) not in grouped_ids or id(item.second) not in grouped_ids
    )

    pending: list[_PendingMergedTable] = []
    absorbed: list[Any] = []
    for group in groups:
        pending.append(_merge_group(document, group))
        absorbed.extend(group[1:])

    if absorbed:
        document.delete_items(node_items=absorbed)

    merged = tuple(
        MergedMultipageTable(
            table_ref=str(item.survivor.self_ref),
            pages=item.pages,
            segments=item.segments,
        )
        for item in pending
    )
    return MultipageTableMergeReport(
        merged_tables=merged,
        unmerged_page_pairs=_page_pairs(unmerged),
    )


def _find_table_continuations(document: Any) -> list[_TableContinuation]:
    ordered: list[tuple[int, float, Any, Any, Any]] = []
    for table in document.tables:
        if len(getattr(table, "prov", [])) != 1:
            continue
        provenance = table.prov[0]
        page = document.pages.get(provenance.page_no)
        if page is None or page.size.width <= 0 or page.size.height <= 0:
            continue
        bbox = provenance.bbox.to_top_left_origin(page.size.height)
        ordered.append((provenance.page_no, bbox.t, table, bbox, page))
    ordered.sort(key=lambda item: (item[0], item[1]))

    candidates: list[_TableContinuation] = []
    for first, second in pairwise(ordered):
        first_page_no, _top, first_table, first_bbox, first_page = first
        second_page_no, _top2, second_table, second_bbox, second_page = second
        if second_page_no != first_page_no + 1:
            continue
        if first_table.data.num_cols != second_table.data.num_cols:
            continue
        if abs(
            (first_bbox.l / first_page.size.width)
            - (second_bbox.l / second_page.size.width)
        ) > _TABLE_HORIZONTAL_TOLERANCE_RATIO:
            continue
        if abs(
            (first_bbox.r / first_page.size.width)
            - (second_bbox.r / second_page.size.width)
        ) > _TABLE_HORIZONTAL_TOLERANCE_RATIO:
            continue
        if first_bbox.b / first_page.size.height < _BOTTOM_TABLE_EDGE_RATIO:
            continue
        if second_bbox.t / second_page.size.height > _TOP_TABLE_EDGE_RATIO:
            continue
        if _has_body_content_before_table(
            document,
            second_table,
            second_bbox,
            second_page,
        ):
            continue
        candidates.append(
            _TableContinuation(
                first=first_table,
                second=second_table,
                first_page_no=first_page_no,
                second_page_no=second_page_no,
            )
        )
    return candidates


def _has_body_content_before_table(
    document: Any,
    table: Any,
    table_bbox: Any,
    page: Any,
) -> bool:
    from docling_core.types.doc import ContentLayer, DocItemLabel

    tolerance = page.size.height * _TABLE_LEADING_CONTENT_TOLERANCE_RATIO
    ignored_labels = {DocItemLabel.PAGE_HEADER, DocItemLabel.PAGE_FOOTER}
    for item, _level in document.iterate_items(
        with_groups=False,
        traverse_pictures=False,
    ):
        if item is table or getattr(item, "content_layer", None) is not ContentLayer.BODY:
            continue
        if getattr(item, "label", None) in ignored_labels:
            continue
        if hasattr(item, "text") and not item.text.strip():
            continue
        for provenance in getattr(item, "prov", []):
            if provenance.page_no != table.prov[0].page_no:
                continue
            bbox = provenance.bbox.to_top_left_origin(page.size.height)
            if bbox.b <= table_bbox.t + tolerance:
                return True
    return False


def _can_merge(item: _TableContinuation) -> bool:
    first = item.first
    second = item.second
    first_parent = first.parent.cref if first.parent is not None else None
    second_parent = second.parent.cref if second.parent is not None else None
    return (
        first.data.num_cols > 0
        and first.data.num_rows > 0
        and second.data.num_rows > 0
        and first.data.orientation == second.data.orientation
        and first.content_layer == second.content_layer
        and first_parent == second_parent
    )


def _continuation_groups(candidates: list[_TableContinuation]) -> list[list[Any]]:
    if not candidates:
        return []
    by_first = {id(item.first): item for item in candidates}
    second_ids = {id(item.second) for item in candidates}
    groups: list[list[Any]] = []
    visited_edges: set[int] = set()

    for start in candidates:
        if id(start.first) in second_ids:
            continue
        group = [start.first]
        current = start.first
        while (continuation := by_first.get(id(current))) is not None:
            edge_id = id(continuation)
            if edge_id in visited_edges:
                break
            visited_edges.add(edge_id)
            group.append(continuation.second)
            current = continuation.second
        if len(group) > 1:
            groups.append(group)
    return groups


def _merge_group(document: Any, tables: list[Any]) -> _PendingMergedTable:
    survivor = tables[0]
    original_refs = {id(table): str(table.self_ref) for table in tables}
    first_page = survivor.prov[0].page_no
    segments: list[MergedTableSegment] = [
        MergedTableSegment(
            source_table_ref=original_refs[id(survivor)],
            page_no=first_page,
            source_rows=survivor.data.num_rows,
            output_row_start=0,
            output_row_end=survivor.data.num_rows,
            repeated_header_rows_removed=0,
            continuation_row_merged_into=None,
        )
    ]

    for table in tables[1:]:
        source_rows = table.data.num_rows
        repeated_headers = _repeated_header_rows(survivor.data, table.data)
        continuation_row = repeated_headers
        continuation_merged_into: int | None = None
        if _is_continuation_row(table.data, continuation_row):
            continuation_merged_into = survivor.data.num_rows - 1
            _append_continuation_row(
                survivor.data,
                table.data,
                continuation_row,
            )

        dropped_rows = repeated_headers + (continuation_merged_into is not None)
        output_start = survivor.data.num_rows
        _append_table_data(survivor.data, table.data, dropped_rows=dropped_rows)
        output_end = survivor.data.num_rows
        page_no = table.prov[0].page_no
        segments.append(
            MergedTableSegment(
                source_table_ref=original_refs[id(table)],
                page_no=page_no,
                source_rows=source_rows,
                output_row_start=output_start,
                output_row_end=output_end,
                repeated_header_rows_removed=repeated_headers,
                continuation_row_merged_into=continuation_merged_into,
            )
        )
        survivor.prov.extend(item.model_copy(deep=True) for item in table.prov)
        _transfer_related_items(document, survivor, table)

    return _PendingMergedTable(
        survivor=survivor,
        pages=tuple(item.prov[0].page_no for item in tables),
        segments=tuple(segments),
    )


def _leading_header_rows(data: Any) -> int:
    header_rows = {
        cell.start_row_offset_idx
        for cell in data.table_cells
        if cell.column_header
    }
    count = 0
    while count in header_rows:
        count += 1
    return count


def _repeated_header_rows(base: Any, addition: Any) -> int:
    maximum = min(_leading_header_rows(base), addition.num_rows)
    for count in range(maximum, 0, -1):
        if not _can_drop_prefix(addition, count):
            continue
        if all(
            _row_signature(base, row_index)
            == _row_signature(addition, row_index)
            for row_index in range(count)
        ):
            return count
    return 0


def _row_signature(data: Any, row_index: int) -> tuple[str, ...]:
    return tuple(_normalize_text(cell.text) for cell in data.grid[row_index])


def _normalize_text(value: str) -> str:
    return _WHITESPACE.sub(
        " ",
        unicodedata.normalize("NFKC", value).strip(),
    ).casefold()


def _can_drop_prefix(data: Any, row_count: int) -> bool:
    return not any(
        cell.start_row_offset_idx < row_count < cell.end_row_offset_idx
        for cell in data.table_cells
    )


def _is_continuation_row(data: Any, row_index: int) -> bool:
    if row_index >= data.num_rows or not _can_drop_prefix(data, row_index + 1):
        return False
    row = data.grid[row_index]
    normalized = [_normalize_text(cell.text) for cell in row]
    if not normalized or normalized[0]:
        return False
    return any(normalized[1:])


def _append_continuation_row(base: Any, addition: Any, row_index: int) -> None:
    target_row = base.grid[-1]
    source_row = addition.grid[row_index]
    seen_sources: set[int] = set()
    for column, source_cell in enumerate(source_row):
        source_id = id(source_cell)
        if source_id in seen_sources or not source_cell.text.strip():
            continue
        seen_sources.add(source_id)
        target_cell = target_row[column]
        if all(target_cell is not item for item in base.table_cells):
            base.table_cells.append(target_cell)
        target_cell.text = _join_continued_text(target_cell.text, source_cell.text)


def _join_continued_text(first: str, second: str) -> str:
    left = first.rstrip()
    right = second.lstrip()
    if not left:
        return right
    if not right:
        return left
    return f"{left}\n{right}"


def _append_table_data(base: Any, addition: Any, *, dropped_rows: int) -> None:
    row_offset = base.num_rows
    for cell in addition.table_cells:
        if cell.end_row_offset_idx <= dropped_rows:
            continue
        copied = cell.model_copy(deep=True)
        copied.start_row_offset_idx = (
            max(cell.start_row_offset_idx, dropped_rows) - dropped_rows + row_offset
        )
        copied.end_row_offset_idx = (
            cell.end_row_offset_idx - dropped_rows + row_offset
        )
        copied.row_span = copied.end_row_offset_idx - copied.start_row_offset_idx
        base.table_cells.append(copied)
    base.num_rows += addition.num_rows - dropped_rows


def _transfer_related_items(document: Any, survivor: Any, absorbed: Any) -> None:
    survivor_ref = survivor.get_ref()
    for child_ref in absorbed.children:
        child_ref.resolve(document).parent = survivor_ref
    survivor.children.extend(absorbed.children)
    absorbed.children = []

    for field_name in ("captions", "references", "footnotes", "comments"):
        target = getattr(survivor, field_name)
        existing = {str(item.cref) for item in target}
        for item in getattr(absorbed, field_name):
            if str(item.cref) not in existing:
                target.append(item)
                existing.add(str(item.cref))
        setattr(absorbed, field_name, [])

    survivor.source.extend(absorbed.source)
    absorbed.source = []


def _page_pairs(items: list[_TableContinuation]) -> tuple[tuple[int, int], ...]:
    return tuple(
        sorted({(item.first_page_no, item.second_page_no) for item in items})
    )


__all__ = [
    "MergedMultipageTable",
    "MergedTableSegment",
    "MultipageTableMergeReport",
    "merge_multipage_tables",
]
