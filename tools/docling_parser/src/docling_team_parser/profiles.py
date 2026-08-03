"""로컬 및 NAVER OCR에 사용하는 고정 Docling 프로필."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Literal

from .errors import ParserError

LOCAL_PROFILE_ID = "docling-local-ocr-v1"
NAVER_PROFILE_ID = "docling-naver-ocr-v1"
_LAYOUT_MODEL_REPO_ID = "docling-project/docling-layout-heron"
_LAYOUT_MODEL_REVISION = "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8"


class OcrProvider(StrEnum):
    LOCAL = "local"
    NAVER = "naver"


@dataclass(frozen=True, slots=True)
class ParserProfile:
    # 실행기가 직접 읽지 않는 필드도 v1 프로필 digest 호환을 위해 유지한다.
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
    local_confidence_threshold: float | None = None
    local_image_scale: float | None = None
    naver_api_version: Literal["V2"] | None = None
    naver_image_scale: float | None = None
    naver_timeout_seconds: float | None = None
    naver_max_attempts: int | None = None
    naver_enable_table_detection: bool | None = None
    naver_max_image_edge: int | None = None
    naver_max_image_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ocr_provider"] = self.ocr_provider.value
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
    profile_id = LOCAL_PROFILE_ID if selected is OcrProvider.LOCAL else NAVER_PROFILE_ID
    return get_profile(profile_id)
