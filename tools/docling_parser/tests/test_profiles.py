from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from docling_team_parser.profiles import (
    LOCAL_PROFILE_ID,
    NAVER_PROFILE_ID,
    NO_OCR_FORMULA_PROFILE_ID,
    NO_OCR_NATIVE_PROFILE_ID,
    get_profile,
)


@pytest.mark.parametrize(
    ("profile_id", "expected_digest"),
    (
        (
            LOCAL_PROFILE_ID,
            "sha256:d4fa70592665ad78000811b58b1ff5b20ed30c35c7fbde5c52c0b1b4deafc639",
        ),
        (
            NAVER_PROFILE_ID,
            "sha256:a78b84564e1cce07ab34bc5020ec25b15235db58eb28f5fa434d45f0725387e3",
        ),
        (
            NO_OCR_FORMULA_PROFILE_ID,
            "sha256:60c05d014329a29fd1b7ed021186e3509f52b778c353e1b87a868bf86e370de1",
        ),
        (
            NO_OCR_NATIVE_PROFILE_ID,
            "sha256:d279b03f248f796f04a8674b709d9084cfed40c98793a59de347c67d5997b5d1",
        ),
    ),
)
def test_v1_profile_digest_is_stable(profile_id: str, expected_digest: str) -> None:
    assert get_profile(profile_id).digest == expected_digest


def test_profile_is_immutable() -> None:
    profile = get_profile(LOCAL_PROFILE_ID)

    with pytest.raises(FrozenInstanceError):
        profile.images_scale = 9.0  # type: ignore[misc]
