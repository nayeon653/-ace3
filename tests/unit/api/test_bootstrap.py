"""API 계층이 Agent 런타임 팩토리만 호출하는지 검증한다."""

from typing import cast

import pytest

from pension_agent.agent.orchestration import AnswerService
from pension_agent.api import bootstrap


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_build_answer_service_delegates_to_agent_runtime(
    monkeypatch,
    anyio_backend: str,
) -> None:
    del anyio_backend
    sentinel = cast(AnswerService, object())
    calls: list[None] = []

    async def build() -> AnswerService:
        calls.append(None)
        return sentinel

    monkeypatch.setattr(bootstrap, "build_runtime_answer_service", build)

    assert await bootstrap.build_answer_service() is sentinel
    assert calls == [None]
