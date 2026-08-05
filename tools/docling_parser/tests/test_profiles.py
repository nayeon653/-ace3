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
            "sha256:085ee1f8977ca4bd80211c9f0f100d0c430a78417e6c18b691c564775f6a2113",
        ),
        (
            NAVER_PROFILE_ID,
            "sha256:d53b6dc1a5b75e94d7fecd0c13a8524c354cdbe242838ee6352365d53a970c34",
        ),
    ),
)
def test_v1_profile_digest_is_stable(profile_id: str, expected_digest: str) -> None:
    assert get_profile(profile_id).digest == expected_digest


def test_profile_is_immutable() -> None:
    profile = get_profile(LOCAL_PROFILE_ID)

    with pytest.raises(FrozenInstanceError):
        profile.images_scale = 9.0  # type: ignore[misc]
