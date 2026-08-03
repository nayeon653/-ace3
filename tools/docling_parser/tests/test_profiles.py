from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from docling_team_parser.profiles import (
    LOCAL_PROFILE_ID,
    NAVER_PROFILE_ID,
    get_profile,
)


@pytest.mark.parametrize(
    ("profile_id", "expected_digest"),
    (
        (
            LOCAL_PROFILE_ID,
            "sha256:e22855d1a47624e7bf29582b684d6b68154db03f609965fe3c11bbbe882c805e",
        ),
        (
            NAVER_PROFILE_ID,
            "sha256:9d2ee2906962c89d83c44970139d53a372acb8487882fdad96ccc92b103768bd",
        ),
    ),
)
def test_v1_profile_digest_is_stable(profile_id: str, expected_digest: str) -> None:
    assert get_profile(profile_id).digest == expected_digest


def test_profile_is_immutable() -> None:
    profile = get_profile(LOCAL_PROFILE_ID)

    with pytest.raises(FrozenInstanceError):
        profile.images_scale = 9.0  # type: ignore[misc]
