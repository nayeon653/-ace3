from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from docling_core.types.doc import DocItemLabel, DoclingDocument
from docling_team_parser.docling_engine import DoclingEngine
from docling_team_parser.errors import NaverOcrError
from docling_team_parser.profiles import (
    LOCAL_PROFILE_ID,
    NAVER_PROFILE_ID,
    get_profile,
)
from PIL import Image


def test_pdf_and_office_image_inputs_use_distinct_ocr_scales() -> None:
    local_engine = DoclingEngine(get_profile(LOCAL_PROFILE_ID))
    local_pdf = local_engine._pdf_pipeline_options("pdf_aware_layout_regions")
    local_office = local_engine._pdf_pipeline_options("full_page", image_input=True)

    naver_engine = DoclingEngine(get_profile(NAVER_PROFILE_ID))
    naver_pdf = naver_engine._pdf_pipeline_options("pdf_aware_layout_regions")
    naver_office = naver_engine._pdf_pipeline_options("full_page", image_input=True)
    naver_engine._naver_usage_session_id = "document-session"
    naver_with_usage = naver_engine._pdf_pipeline_options(
        "pdf_aware_layout_regions"
    )

    assert local_pdf.ocr_options.scale == 3.0
    assert naver_pdf.ocr_options.scale == 2.1
    assert local_office.ocr_options.scale == 1.0
    assert naver_office.ocr_options.scale == 1.0
    assert naver_with_usage.ocr_options.usage_session_id == "document-session"
    assert "usage_session_id" not in naver_with_usage.ocr_options.model_dump()
    assert local_pdf.layout_options.model_spec.revision == (
        "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8"
    )


def test_transparent_office_picture_is_flattened_onto_white() -> None:
    source = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    source.putpixel((1, 0), (0, 0, 0, 255))
    try:
        payload = DoclingEngine._serialize_picture_png(source)
    finally:
        source.close()

    with Image.open(BytesIO(payload)) as flattened:
        assert flattened.mode == "RGB"
        assert flattened.getpixel((0, 0)) == (255, 255, 255)
        assert flattened.getpixel((1, 0)) == (0, 0, 0)


def test_office_picture_ocr_roots_are_attached_under_the_picture() -> None:
    document = DoclingDocument(name="office-document")
    picture = document.add_picture()
    image_document = DoclingDocument(name="picture-ocr")
    root = image_document.add_text(label=DocItemLabel.TEXT, text="그림 안 텍스트")

    DoclingEngine._attach_picture_ocr_roots(
        document,
        picture,
        image_document,
        [root],
    )

    assert len(document.body.children) == 1
    assert len(picture.children) == 1
    inserted = picture.children[0].resolve(document)
    assert inserted.text == "그림 안 텍스트"
    assert inserted.parent is not None
    assert inserted.parent.resolve(document) is picture


def test_naver_exception_is_recognized_through_docling_wrapper() -> None:
    try:
        try:
            raise NaverOcrError("NAVER OCR returned HTTP 503")
        except NaverOcrError as exc:
            raise RuntimeError("Pipeline StandardPdfPipeline failed") from exc
    except RuntimeError as wrapped:
        assert DoclingEngine._exception_is_naver_ocr(wrapped) is True

    unrelated = RuntimeError("Conversion failed for NAVER OCR annual-report.pdf")
    assert DoclingEngine._exception_is_naver_ocr(unrelated) is False


def test_naver_conversion_error_items_are_classified_narrowly() -> None:
    naver_errors = [
        SimpleNamespace(
            module_name="StandardPdfPipeline",
            error_message="NAVER OCR rate limit exceeded after 3 attempt(s)",
        )
    ]
    generic_errors = [
        SimpleNamespace(
            module_name="StandardPdfPipeline",
            error_message="Page failed to parse",
        )
    ]

    assert DoclingEngine._errors_include_naver_ocr(naver_errors) is True
    assert DoclingEngine._errors_include_naver_ocr(generic_errors) is False
