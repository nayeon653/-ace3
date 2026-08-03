"""핵심 서비스, CLI 및 Skill이 공유하는 불변 파싱 프로필."""

from __future__ import annotations

import os
from collections.abc import Iterable

from .errors import ParserError
from .models import OcrProvider, ParserProfile
from .ocr.config import validate_naver_invoke_url

LOCAL_PROFILE_ID = "docling-local-ocr-v1"
NAVER_PROFILE_ID = "docling-naver-ocr-v1"
_LAYOUT_MODEL_REPO_ID = "docling-project/docling-layout-heron"
_LAYOUT_MODEL_REVISION = "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8"


_PROFILES: dict[str, ParserProfile] = {
    LOCAL_PROFILE_ID: ParserProfile(
        id=LOCAL_PROFILE_ID,
        description=(
            "Docling PDF-aware OCR with EasyOCR ko/en on CPU; embedded Office "
            "pictures are reparsed through Docling image input with full-page OCR."
        ),
        ocr_provider=OcrProvider.LOCAL,
        external_data_transfer=False,
        ocr_mode="pdf_aware_layout_regions",
        layout_model_repo_id=_LAYOUT_MODEL_REPO_ID,
        layout_model_revision=_LAYOUT_MODEL_REVISION,
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
        ocr_mode="pdf_aware_layout_regions",
        # CLOVA General OCR의 요청 언어 힌트는 ko/ja/zh-TW만 허용한다.
        # 영어는 이 API 필드에서 유효한 값이 아니다.
        languages=("ko",),
        layout_model_repo_id=_LAYOUT_MODEL_REPO_ID,
        layout_model_revision=_LAYOUT_MODEL_REVISION,
        naver_api_version="V2",
        # 2.1은 PDF 페이지를 약 150 DPI로 렌더링한다. Docling 이미지 백엔드는 Office
        # 그림을 이미 원본 픽셀 단위로 측정하므로 office_picture_image_scale=1.0을 쓴다.
        naver_image_scale=2.1,
        naver_timeout_seconds=60.0,
        naver_max_attempts=3,
        # Docling TableFormer는 OCR 텍스트 셀을 입력으로 사용한다. 플러그인이 구조화된
        # CLOVA 표 응답을 소비하도록 구현하기 전까지는 해당 응답을 요청하지 않는다.
        naver_enable_table_detection=False,
        naver_max_image_edge=7_900,
        naver_max_image_bytes=49_000_000,
    ),
}


def get_profile(profile_id: str) -> ParserProfile:
    try:
        return _PROFILES[profile_id]
    except KeyError as exc:
        raise ParserError(
            "PROFILE_NOT_FOUND", f"unknown profile: {profile_id}"
        ) from exc


def iter_profiles() -> Iterable[ParserProfile]:
    return tuple(_PROFILES.values())


def profile_availability(profile: ParserProfile) -> tuple[bool, str | None]:
    if profile.ocr_provider is OcrProvider.NAVER:
        if os.environ.get(
            "DOCLING_PARSER_ENABLE_NAVER_OCR", ""
        ).strip().lower() not in {
            "1",
            "true",
            "yes",
        }:
            return False, "DOCLING_PARSER_ENABLE_NAVER_OCR is not enabled"
        missing = [
            name
            for name in ("NAVER_OCR_INVOKE_URL", "NAVER_OCR_SECRET")
            if not os.environ.get(name, "").strip()
        ]
        if missing:
            return False, f"missing environment variables: {', '.join(missing)}"
        try:
            validate_naver_invoke_url(os.environ["NAVER_OCR_INVOKE_URL"])
        except ValueError as exc:
            return False, str(exc)
    return True, None
