"""무OCR, 로컬 OCR 및 NAVER OCR에 사용하는 고정 Docling 프로필."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Literal

from .errors import ParserError

LOCAL_PROFILE_ID = "docling-local-ocr-v1"
NAVER_PROFILE_ID = "docling-naver-ocr-v1"
NO_OCR_FORMULA_PROFILE_ID = "docling-no-ocr-formula-v1"
NO_OCR_NATIVE_PROFILE_ID = "docling-no-ocr-native-v1"
_LAYOUT_MODEL_REPO_ID = "docling-project/docling-layout-heron"
_LAYOUT_MODEL_REVISION = "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8"
_FORMULA_MODEL_REPO_ID = "docling-project/CodeFormulaV2"
_FORMULA_MODEL_REVISION = "ecedbe111d15c2dc60bfd4a823cbe80127b58af4"


class OcrProvider(StrEnum):
    NONE = "none"
    NONE_NATIVE = "none-native"
    LOCAL = "local"
    NAVER = "naver"


@dataclass(frozen=True, slots=True)
class ParserProfile:
    # 실행기가 직접 읽지 않는 필드도 프로필 digest 재현성을 위해 유지한다.
    id: str
    description: str
    ocr_provider: OcrProvider
    external_data_transfer: bool
    languages: tuple[str, ...]
    version: int = 1
    ocr_mode: Literal["pdf_aware_layout_regions"] = "pdf_aware_layout_regions"
    office_picture_ocr_mode: Literal["full_page"] = "full_page"
    office_picture_image_scale: float = 1.0
    accelerator_device: Literal["cpu"] = "cpu"
    accelerator_threads: int = 4
    images_scale: float = 2.0
    table_mode: Literal["accurate"] = "accurate"
    layout_model_repo_id: str = _LAYOUT_MODEL_REPO_ID
    layout_model_revision: str = _LAYOUT_MODEL_REVISION
    do_table_structure: bool = True
    generate_picture_images: bool = True
    export_images: bool = True
    traverse_pictures: bool = True
    suppress_repeated_decorative_pictures: bool = True
    decorative_picture_max_page_area_ratio: float = 0.02
    decorative_picture_margin_ratio: float = 0.12
    decorative_picture_min_page_repeat_ratio: float = 0.2
    decorative_picture_min_pages: int = 3
    isolate_embedded_picture_ocr: bool = True
    full_page_picture_min_page_area_ratio: float = 0.65
    normalize_repeated_text: bool = True
    merge_multipage_tables: bool = True
    warn_possible_cross_page_tables: bool = True
    local_confidence_threshold: float | None = None
    local_image_scale: float | None = None
    naver_api_version: Literal["V2"] | None = None
    naver_image_scale: float | None = None
    naver_timeout_seconds: float | None = None
    naver_max_attempts: int | None = None
    naver_enable_table_detection: bool | None = None
    naver_max_image_edge: int | None = None
    naver_max_image_bytes: int | None = None
    do_formula_enrichment: bool | None = None
    formula_model_repo_id: str | None = None
    formula_model_revision: str | None = None
    formula_compile_model: bool | None = None
    generate_page_images: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ocr_provider"] = self.ocr_provider.value
        # 기존 v1 프로필의 digest를 바꾸지 않도록 새 선택 필드만 미설정 시 제외한다.
        for key in (
            "do_formula_enrichment",
            "formula_model_repo_id",
            "formula_model_revision",
            "formula_compile_model",
            "generate_page_images",
        ):
            if payload[key] is None:
                del payload[key]
        return payload

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"


_PROFILES = {
    NO_OCR_FORMULA_PROFILE_ID: ParserProfile(
        id=NO_OCR_FORMULA_PROFILE_ID,
        description=(
            "Docling native-text parsing without OCR or remote services; local "
            "CodeFormulaV2 enrichment is enabled for mathematical formulas."
        ),
        ocr_provider=OcrProvider.NONE,
        external_data_transfer=False,
        languages=(),
        do_formula_enrichment=True,
        formula_model_repo_id=_FORMULA_MODEL_REPO_ID,
        formula_model_revision=_FORMULA_MODEL_REVISION,
        formula_compile_model=False,
        generate_page_images=True,
        generate_picture_images=False,
        isolate_embedded_picture_ocr=False,
    ),
    NO_OCR_NATIVE_PROFILE_ID: ParserProfile(
        id=NO_OCR_NATIVE_PROFILE_ID,
        description=(
            "Docling native-text and accurate-table parsing without OCR, formula "
            "VLM enrichment, page-image retention, or remote services."
        ),
        ocr_provider=OcrProvider.NONE_NATIVE,
        external_data_transfer=False,
        languages=(),
        do_formula_enrichment=False,
        generate_page_images=False,
        generate_picture_images=False,
        export_images=False,
        traverse_pictures=False,
        isolate_embedded_picture_ocr=False,
    ),
    LOCAL_PROFILE_ID: ParserProfile(
        id=LOCAL_PROFILE_ID,
        description=(
            "Docling PDF-aware OCR with EasyOCR ko/en on CPU; embedded Office "
            "pictures are reparsed through Docling image input with full-page OCR."
        ),
        ocr_provider=OcrProvider.LOCAL,
        external_data_transfer=False,
        languages=("ko", "en"),
        local_confidence_threshold=0.35,
        local_image_scale=3.0,
    ),
    NAVER_PROFILE_ID: ParserProfile(
        id=NAVER_PROFILE_ID,
        description=(
            "Docling PDF-aware OCR backed by NAVER CLOVA OCR General V2; embedded "
            "Office pictures are reparsed through Docling image input."
        ),
        ocr_provider=OcrProvider.NAVER,
        external_data_transfer=True,
        # CLOVA General OCR 요청 언어 힌트는 ko/ja/zh-TW만 허용한다.
        languages=("ko",),
        # PDF는 약 150 DPI로 렌더링하고 Office 그림은 원본 픽셀을 사용한다.
        naver_image_scale=2.1,
        naver_api_version="V2",
        naver_timeout_seconds=60.0,
        naver_max_attempts=3,
        naver_enable_table_detection=False,
        naver_max_image_edge=7_900,
        naver_max_image_bytes=49_000_000,
    ),
}


def get_profile(profile_id: str) -> ParserProfile:
    try:
        return _PROFILES[profile_id]
    except KeyError as exc:
        raise ParserError("PROFILE_NOT_FOUND", f"지원하지 않는 프로필: {profile_id}") from exc


def profile_for_provider(provider: str | OcrProvider) -> ParserProfile:
    selected = OcrProvider(provider)
    profile_id = {
        OcrProvider.NONE: NO_OCR_FORMULA_PROFILE_ID,
        OcrProvider.NONE_NATIVE: NO_OCR_NATIVE_PROFILE_ID,
        OcrProvider.LOCAL: LOCAL_PROFILE_ID,
        OcrProvider.NAVER: NAVER_PROFILE_ID,
    }[selected]
    return get_profile(profile_id)
