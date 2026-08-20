"""Router 기반 Search Service 설정과 기본 프로필을 검증한다."""

import pytest
from pydantic import ValidationError

from pension_agent.config import DEFAULT_SEARCH_SERVICE_CONFIG, SearchServiceConfig
from pension_agent.core import SearchMode


def test_default_search_service_config_is_versioned_and_immutable() -> None:
    assert DEFAULT_SEARCH_SERVICE_CONFIG == SearchServiceConfig(
        max_concurrency=4,
        timeout_seconds=45.0,
        default_search_mode=SearchMode.HYBRID,
        candidate_limit=10,
        result_limit=5,
        minimum_score=None,
        neighbor_before=1,
        neighbor_after=1,
    )

    with pytest.raises(ValidationError, match="frozen"):
        DEFAULT_SEARCH_SERVICE_CONFIG.result_limit = 4


def test_search_service_config_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SearchServiceConfig(unsupported=True)  # type: ignore[call-arg]


def test_search_service_config_rejects_result_limit_above_candidate_limit() -> None:
    with pytest.raises(ValidationError, match="후보 검색 결과 수"):
        SearchServiceConfig(candidate_limit=2, result_limit=3)


def test_search_service_config_rejects_oversized_neighbor_window() -> None:
    with pytest.raises(ValidationError, match="100 이하여야"):
        SearchServiceConfig(neighbor_before=50, neighbor_after=50)


@pytest.mark.parametrize(
    "values",
    [
        {"max_concurrency": 0},
        {"timeout_seconds": 0},
        {"candidate_limit": 101},
        {"result_limit": 0},
        {"minimum_score": float("nan")},
    ],
)
def test_search_service_config_rejects_invalid_bounds(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SearchServiceConfig.model_validate(values)
