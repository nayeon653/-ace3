"""Search Agent 설정 스키마와 기본 프로필을 검증한다."""

import pytest
from pydantic import ValidationError

from pension_agent.config import DEFAULT_SEARCH_AGENT_CONFIG, SearchAgentConfig
from pension_agent.core import SearchMode


def test_default_search_agent_config_is_versioned_and_immutable() -> None:
    assert DEFAULT_SEARCH_AGENT_CONFIG == SearchAgentConfig(
        max_model_calls=6,
        max_tool_calls=3,
        default_search_mode=SearchMode.HYBRID,
        default_result_limit=10,
        default_neighbor_before=1,
        default_neighbor_after=1,
    )

    with pytest.raises(ValidationError, match="frozen"):
        DEFAULT_SEARCH_AGENT_CONFIG.max_tool_calls = 4


def test_search_agent_config_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SearchAgentConfig(
            max_model_calls=4,
            max_tool_calls=3,
            default_search_mode=SearchMode.HYBRID,
            default_result_limit=10,
            default_neighbor_before=1,
            default_neighbor_after=1,
            unsupported=True,  # type: ignore[call-arg]
        )


def test_search_agent_config_requires_final_model_call_after_tool_calls() -> None:
    with pytest.raises(ValidationError, match="최소 1 커야"):
        SearchAgentConfig(
            max_model_calls=3,
            max_tool_calls=3,
            default_search_mode=SearchMode.HYBRID,
            default_result_limit=10,
            default_neighbor_before=1,
            default_neighbor_after=1,
        )


def test_search_agent_config_rejects_oversized_default_neighbor_window() -> None:
    with pytest.raises(ValidationError, match="100 이하여야"):
        SearchAgentConfig(
            max_model_calls=4,
            max_tool_calls=3,
            default_search_mode=SearchMode.HYBRID,
            default_result_limit=10,
            default_neighbor_before=50,
            default_neighbor_after=50,
        )
