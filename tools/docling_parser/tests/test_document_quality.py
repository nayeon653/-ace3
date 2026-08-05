from __future__ import annotations

from dataclasses import replace

from docling_core.types.doc import (
    BoundingBox,
    ContentLayer,
    CoordOrigin,
    DocItemLabel,
    DoclingDocument,
    ImageRef,
    ProvenanceItem,
    Size,
    TableData,
)
from docling_team_parser.document_quality import improve_document
from docling_team_parser.profiles import LOCAL_PROFILE_ID, get_profile
from PIL import Image


def _provenance(page_no: int, bbox: tuple[float, float, float, float]) -> ProvenanceItem:
    return ProvenanceItem(
        page_no=page_no,
        bbox=BoundingBox.from_tuple(bbox, origin=CoordOrigin.TOPLEFT),
        charspan=(0, 0),
    )


def _image_ref(size: tuple[int, int], color: str) -> ImageRef:
    image = Image.new("RGB", size, color)
    try:
        return ImageRef.from_pil(image, dpi=72)
    finally:
        image.close()


def test_quality_pipeline_removes_repeated_decorations_but_preserves_visual_ocr() -> None:
    document = DoclingDocument(name="quality-test")
    for page_no in range(1, 5):
        document.add_page(page_no=page_no, size=Size(width=600, height=800))

    logo_ref = _image_ref((100, 30), "navy")
    for page_no in range(1, 5):
        logo = document.add_picture(
            image=logo_ref,
            prov=_provenance(page_no, (20, 750, 120, 780)),
        )
        document.add_text(
            label=DocItemLabel.TEXT,
            text="decorative logo",
            orig="decorative logo",
            parent=logo,
        )

    diagram = document.add_picture(
        image=_image_ref((300, 300), "orange"),
        prov=_provenance(2, (150, 150, 450, 550)),
    )
    diagram_text = document.add_text(
        label=DocItemLabel.TEXT,
        text="arrow token bag",
        orig="arrow token bag",
        parent=diagram,
    )

    scanned_page = document.add_picture(
        image=_image_ref((580, 760), "white"),
        prov=_provenance(3, (10, 10, 590, 790)),
    )
    scanned_text = document.add_text(
        label=DocItemLabel.TEXT,
        text="scanned page body",
        orig="scanned page body",
        parent=scanned_page,
    )
    repeated = document.add_text(
        label=DocItemLabel.TEXT,
        text="alpha beta gamma alpha beta gamma tail",
        orig="alpha beta gamma alpha beta gamma tail",
    )

    profile = replace(
        get_profile(LOCAL_PROFILE_ID),
        decorative_picture_min_page_repeat_ratio=0.5,
        decorative_picture_min_pages=3,
    )
    report = improve_document(document, profile)

    assert report.repeated_decorative_pictures_removed == 4
    assert report.repeated_decorative_picture_pages == (1, 2, 3, 4)
    assert report.embedded_pictures_requiring_visual_review == 1
    assert report.visual_review_picture_pages == (2,)
    assert report.picture_ocr_text_nodes_isolated == 1
    assert report.repeated_text_nodes_normalized == 1
    assert len(document.pictures) == 2
    assert diagram_text.content_layer is ContentLayer.INVISIBLE
    assert scanned_text.content_layer is ContentLayer.BODY
    assert repeated.text == "alpha beta gamma tail"
    assert repeated.orig == "alpha beta gamma alpha beta gamma tail"

    markdown = document.export_to_markdown(traverse_pictures=True)
    assert "decorative logo" not in markdown
    assert "arrow token bag" not in markdown
    assert "scanned page body" in markdown
    assert "alpha beta gamma tail" in markdown


def test_quality_pipeline_warns_without_merging_cross_page_tables() -> None:
    document = DoclingDocument(name="table-test")
    for page_no in (1, 2):
        document.add_page(page_no=page_no, size=Size(width=600, height=800))
    document.add_table(
        data=TableData(num_rows=3, num_cols=4),
        prov=_provenance(1, (50, 650, 550, 760)),
    )
    document.add_table(
        data=TableData(num_rows=2, num_cols=4),
        prov=_provenance(2, (50, 40, 550, 120)),
    )

    report = improve_document(document, get_profile(LOCAL_PROFILE_ID))

    assert report.possible_cross_page_table_pairs == ((1, 2),)
    assert len(document.tables) == 2
    assert "segments were preserved without automatic merging" in report.warnings[-1]


def test_cross_page_table_check_rejects_new_table_with_leading_content() -> None:
    document = DoclingDocument(name="separate-table-test")
    for page_no in (1, 2):
        document.add_page(page_no=page_no, size=Size(width=600, height=800))
    document.add_table(
        data=TableData(num_rows=3, num_cols=4),
        prov=_provenance(1, (50, 650, 550, 760)),
    )
    document.add_text(
        label=DocItemLabel.TEXT,
        text="새 표 제목",
        prov=_provenance(2, (50, 20, 250, 35)),
    )
    document.add_table(
        data=TableData(num_rows=2, num_cols=4),
        prov=_provenance(2, (50, 40, 550, 120)),
    )

    report = improve_document(document, get_profile(LOCAL_PROFILE_ID))

    assert report.possible_cross_page_table_pairs == ()


def test_cross_page_table_check_can_be_disabled_for_non_pdf_sources() -> None:
    document = DoclingDocument(name="sheet-test")
    for page_no in (1, 2):
        document.add_page(page_no=page_no, size=Size(width=600, height=800))
    document.add_table(
        data=TableData(num_rows=3, num_cols=4),
        prov=_provenance(1, (50, 650, 550, 760)),
    )
    document.add_table(
        data=TableData(num_rows=2, num_cols=4),
        prov=_provenance(2, (50, 40, 550, 120)),
    )

    report = improve_document(
        document,
        get_profile(LOCAL_PROFILE_ID),
        detect_cross_page_tables=False,
    )

    assert report.possible_cross_page_table_pairs == ()


def test_visual_review_warning_does_not_invent_pages_for_unpaginated_office() -> None:
    report = improve_document(
        DoclingDocument(name="unpaginated-office"),
        replace(
            get_profile(LOCAL_PROFILE_ID),
            isolate_embedded_picture_ocr=False,
        ),
    )
    report = replace(
        report,
        embedded_pictures_requiring_visual_review=2,
        picture_ocr_text_nodes_isolated=5,
    )

    assert report.warnings == [
        (
            "2 embedded picture(s) require visual review; 5 OCR text node(s) were "
            "preserved in Docling JSON and excluded from Markdown"
        )
    ]
