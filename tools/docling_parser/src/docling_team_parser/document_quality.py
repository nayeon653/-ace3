"""문서별 보정 없이 적용하는 Docling 결과 품질 개선 단계."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from .profiles import ParserProfile

_HASH_SIZE = 16
_HASH_BITS = _HASH_SIZE * _HASH_SIZE
_HASH_DISTANCE_RATIO = 0.16
_POSITION_TOLERANCE = 0.03
_BOTTOM_TABLE_EDGE_RATIO = 0.85
_TOP_TABLE_EDGE_RATIO = 0.15
_TABLE_HORIZONTAL_TOLERANCE_RATIO = 0.05
_TABLE_LEADING_CONTENT_TOLERANCE_RATIO = 0.004
_NUMBER_TOKEN = re.compile(r"[\d.,%]+")


@dataclass(frozen=True, slots=True)
class DocumentQualityReport:
    repeated_decorative_pictures_removed: int
    repeated_decorative_picture_pages: tuple[int, ...]
    embedded_pictures_requiring_visual_review: int
    visual_review_picture_pages: tuple[int, ...]
    picture_ocr_text_nodes_isolated: int
    repeated_text_nodes_normalized: int
    possible_cross_page_table_pairs: tuple[tuple[int, int], ...]

    @property
    def warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.repeated_decorative_pictures_removed:
            warnings.append(
                "suppressed "
                f"{self.repeated_decorative_pictures_removed} repeated small "
                "header/footer picture(s) across "
                f"{len(self.repeated_decorative_picture_pages)} page(s)"
            )
        if self.embedded_pictures_requiring_visual_review:
            pages = _format_pages(self.visual_review_picture_pages)
            location = f" on pages {pages}" if pages else ""
            warnings.append(
                f"{self.embedded_pictures_requiring_visual_review} embedded "
                f"picture(s){location} require visual review; "
                f"{self.picture_ocr_text_nodes_isolated} OCR text node(s) were "
                "preserved in Docling JSON and excluded from Markdown"
            )
        if self.repeated_text_nodes_normalized:
            warnings.append(
                "collapsed adjacent repeated text in "
                f"{self.repeated_text_nodes_normalized} node(s); original text "
                "remains in each node's orig field"
            )
        if self.possible_cross_page_table_pairs:
            pairs = ", ".join(
                f"{first}->{second}"
                for first, second in self.possible_cross_page_table_pairs
            )
            warnings.append(
                "detected "
                f"{len(self.possible_cross_page_table_pairs)} possible cross-page "
                f"table continuation(s) ({pairs}); segments were preserved without "
                "automatic merging"
            )
        return warnings


@dataclass(frozen=True, slots=True)
class _PictureDescriptor:
    item: Any
    page_no: int
    margin: str
    area_ratio: float
    center_x_ratio: float
    center_y_ratio: float
    width_ratio: float
    height_ratio: float
    perceptual_hash: int


def improve_document(
    document: Any,
    profile: ParserProfile,
    *,
    detect_cross_page_tables: bool = True,
) -> DocumentQualityReport:
    """반복 장식과 OCR 노이즈를 일반 규칙으로 줄이고 품질 신호를 만든다."""

    removed, removed_pages = _remove_repeated_decorative_pictures(document, profile)
    visual_count, visual_pages, isolated = _isolate_embedded_picture_text(
        document,
        profile,
    )
    normalized = (
        _normalize_repeated_text(document) if profile.normalize_repeated_text else 0
    )
    table_pairs = (
        _possible_cross_page_table_pairs(document)
        if profile.warn_possible_cross_page_tables and detect_cross_page_tables
        else ()
    )
    return DocumentQualityReport(
        repeated_decorative_pictures_removed=removed,
        repeated_decorative_picture_pages=removed_pages,
        embedded_pictures_requiring_visual_review=visual_count,
        visual_review_picture_pages=visual_pages,
        picture_ocr_text_nodes_isolated=isolated,
        repeated_text_nodes_normalized=normalized,
        possible_cross_page_table_pairs=table_pairs,
    )


def mark_items_invisible(items: list[Any], document: Any) -> int:
    """OCR 근거 노드를 JSON에는 남기고 기본 Markdown layer에서는 제외한다."""

    from docling_core.types.doc import ContentLayer

    count = 0
    seen: set[str] = set()

    def visit(item: Any) -> None:
        nonlocal count
        self_ref = str(getattr(item, "self_ref", id(item)))
        if self_ref in seen:
            return
        seen.add(self_ref)
        if hasattr(item, "content_layer"):
            item.content_layer = ContentLayer.INVISIBLE
            count += 1
        for child_ref in getattr(item, "children", []):
            visit(child_ref.resolve(document))

    for item in items:
        visit(item)
    return count


def _remove_repeated_decorative_pictures(
    document: Any,
    profile: ParserProfile,
) -> tuple[int, tuple[int, ...]]:
    if not profile.suppress_repeated_decorative_pictures:
        return 0, ()

    descriptors = [
        descriptor
        for picture in list(document.pictures)
        if (descriptor := _decorative_picture_descriptor(document, picture, profile))
        is not None
    ]
    clusters: list[list[_PictureDescriptor]] = []
    for descriptor in descriptors:
        for cluster in clusters:
            if _pictures_match(cluster[0], descriptor):
                cluster.append(descriptor)
                break
        else:
            clusters.append([descriptor])

    page_count = max(len(document.pages), 1)
    minimum_pages = max(
        profile.decorative_picture_min_pages,
        math.ceil(page_count * profile.decorative_picture_min_page_repeat_ratio),
    )
    selected: list[_PictureDescriptor] = []
    for cluster in clusters:
        if len({item.page_no for item in cluster}) >= minimum_pages:
            selected.extend(cluster)

    if not selected:
        return 0, ()

    document.delete_items(node_items=[item.item for item in selected])
    pages = tuple(sorted({item.page_no for item in selected}))
    return len(selected), pages


def _decorative_picture_descriptor(
    document: Any,
    picture: Any,
    profile: ParserProfile,
) -> _PictureDescriptor | None:
    if len(getattr(picture, "prov", [])) != 1:
        return None
    provenance = picture.prov[0]
    page = document.pages.get(provenance.page_no)
    if page is None or page.size.width <= 0 or page.size.height <= 0:
        return None

    bbox = provenance.bbox.to_top_left_origin(page.size.height)
    width_ratio = bbox.width / page.size.width
    height_ratio = bbox.height / page.size.height
    area_ratio = width_ratio * height_ratio
    if area_ratio > profile.decorative_picture_max_page_area_ratio:
        return None

    center_y_ratio = ((bbox.t + bbox.b) / 2) / page.size.height
    if center_y_ratio <= profile.decorative_picture_margin_ratio:
        margin = "top"
    elif center_y_ratio >= 1 - profile.decorative_picture_margin_ratio:
        margin = "bottom"
    else:
        return None

    image = picture.get_image(document)
    if image is None:
        return None
    return _PictureDescriptor(
        item=picture,
        page_no=provenance.page_no,
        margin=margin,
        area_ratio=area_ratio,
        center_x_ratio=((bbox.l + bbox.r) / 2) / page.size.width,
        center_y_ratio=center_y_ratio,
        width_ratio=width_ratio,
        height_ratio=height_ratio,
        perceptual_hash=_difference_hash(image),
    )


def _difference_hash(image: Any) -> int:
    from PIL import Image

    grayscale = image.convert("L")
    resized = grayscale.resize(
        (_HASH_SIZE + 1, _HASH_SIZE),
        resample=Image.Resampling.LANCZOS,
    )
    try:
        pixels = list(resized.get_flattened_data())
    finally:
        resized.close()
        grayscale.close()

    result = 0
    row_width = _HASH_SIZE + 1
    for y in range(_HASH_SIZE):
        offset = y * row_width
        for x in range(_HASH_SIZE):
            if pixels[offset + x] > pixels[offset + x + 1]:
                result |= 1 << (y * _HASH_SIZE + x)
    return result


def _pictures_match(first: _PictureDescriptor, second: _PictureDescriptor) -> bool:
    if first.margin != second.margin:
        return False
    geometry = (
        (first.center_x_ratio, second.center_x_ratio),
        (first.center_y_ratio, second.center_y_ratio),
        (first.width_ratio, second.width_ratio),
        (first.height_ratio, second.height_ratio),
    )
    if any(abs(left - right) > _POSITION_TOLERANCE for left, right in geometry):
        return False
    distance = (first.perceptual_hash ^ second.perceptual_hash).bit_count()
    return distance <= math.floor(_HASH_BITS * _HASH_DISTANCE_RATIO)


def _isolate_embedded_picture_text(
    document: Any,
    profile: ParserProfile,
) -> tuple[int, tuple[int, ...], int]:
    if not profile.isolate_embedded_picture_ocr:
        return 0, (), 0

    pictures: list[Any] = []
    pages: set[int] = set()
    isolated = 0
    for picture in document.pictures:
        page_ratios = _picture_page_area_ratios(document, picture)
        if not page_ratios:
            continue
        if max(ratio for _page_no, ratio in page_ratios) >= (
            profile.full_page_picture_min_page_area_ratio
        ):
            # Full-page image/scanned PDF containers must keep traversable OCR text.
            continue
        pictures.append(picture)
        pages.update(page_no for page_no, _ratio in page_ratios)
        children = [ref.resolve(document) for ref in getattr(picture, "children", [])]
        isolated += mark_items_invisible(children, document)
    return len(pictures), tuple(sorted(pages)), isolated


def _picture_page_area_ratios(document: Any, picture: Any) -> list[tuple[int, float]]:
    ratios: list[tuple[int, float]] = []
    for provenance in getattr(picture, "prov", []):
        page = document.pages.get(provenance.page_no)
        if page is None or page.size.width <= 0 or page.size.height <= 0:
            continue
        bbox = provenance.bbox.to_top_left_origin(page.size.height)
        ratios.append(
            (
                provenance.page_no,
                bbox.area() / (page.size.width * page.size.height),
            )
        )
    return ratios


def _normalize_repeated_text(document: Any) -> int:
    from docling_core.types.doc import DocItemLabel

    normalized = 0
    for item in document.texts:
        tokens = item.text.split()
        for repeat_length in range(len(tokens) // 2, 0, -1):
            if tokens[:repeat_length] != tokens[repeat_length : 2 * repeat_length]:
                continue
            safe_short_repeat = item.label is DocItemLabel.SECTION_HEADER or (
                repeat_length == 1 and _NUMBER_TOKEN.fullmatch(tokens[0]) is not None
            )
            if repeat_length < 3 and not safe_short_repeat:
                continue
            item.text = " ".join(
                tokens[:repeat_length] + tokens[repeat_length * 2 :]
            )
            normalized += 1
            break
    return normalized


def _possible_cross_page_table_pairs(document: Any) -> tuple[tuple[int, int], ...]:
    ordered: list[tuple[int, float, Any, Any, Any]] = []
    for table in document.tables:
        if len(getattr(table, "prov", [])) != 1:
            continue
        provenance = table.prov[0]
        page = document.pages.get(provenance.page_no)
        if page is None or page.size.height <= 0:
            continue
        bbox = provenance.bbox.to_top_left_origin(page.size.height)
        ordered.append((provenance.page_no, bbox.t, table, bbox, page))
    ordered.sort(key=lambda item: (item[0], item[1]))

    pairs: set[tuple[int, int]] = set()
    for first, second in pairwise(ordered):
        first_page_no, _top, first_table, first_bbox, first_page = first
        second_page_no, _top2, second_table, second_bbox, second_page = second
        if second_page_no != first_page_no + 1:
            continue
        if first_table.data.num_cols != second_table.data.num_cols:
            continue
        if first_page.size.width <= 0 or second_page.size.width <= 0:
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
        pairs.add((first_page_no, second_page_no))
    return tuple(sorted(pairs))


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


def _format_pages(pages: tuple[int, ...]) -> str:
    if len(pages) <= 12:
        return ",".join(str(page) for page in pages)
    return ",".join(str(page) for page in pages[:12]) + ",..."


__all__ = ["DocumentQualityReport", "improve_document", "mark_items_invisible"]
