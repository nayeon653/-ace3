"""온라인 Agent 실행 경로의 동시성·시간 예산 설정을 검증한다."""

import pytest
from pydantic import ValidationError

from pension_agent.config import (
    DEFAULT_AGENT_RUNTIME_CONFIG,
    DEFAULT_DOMAIN_AGENT_CONFIG,
    AgentRuntimeConfig,
)


def test_default_agent_runtime_budget_is_versioned_and_immutable() -> None:
    assert DEFAULT_AGENT_RUNTIME_CONFIG == AgentRuntimeConfig(
        max_concurrent_answers=4,
        max_pending_answers=64,
        max_concurrent_hcx_calls=4,
        max_concurrent_embedding_calls=4,
        max_concurrent_qdrant_calls=4,
        answer_timeout_seconds=180.0,
        shutdown_timeout_seconds=10.0,
    )

    with pytest.raises(ValidationError, match="frozen"):
        DEFAULT_AGENT_RUNTIME_CONFIG.max_concurrent_answers = 8  # type: ignore[misc]


def test_default_domain_capacity_is_versioned() -> None:
    assert DEFAULT_DOMAIN_AGENT_CONFIG.max_concurrency == 3
    assert DEFAULT_DOMAIN_AGENT_CONFIG.timeout_seconds == 75.0


@pytest.mark.parametrize("max_concurrency", [0, 33])
def test_agent_runtime_rejects_invalid_concurrency(max_concurrency: int) -> None:
    with pytest.raises(ValidationError):
        AgentRuntimeConfig(max_concurrent_answers=max_concurrency)


@pytest.mark.parametrize("max_pending", [-1, 513])
def test_agent_runtime_rejects_invalid_pending_limit(max_pending: int) -> None:
    with pytest.raises(ValidationError):
        AgentRuntimeConfig(max_pending_answers=max_pending)
