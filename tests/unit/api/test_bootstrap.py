"""API 계층이 Agent 런타임 팩토리만 호출하는지 검증한다."""

from typing import cast

from pension_agent.agent.orchestration import AnswerService
from pension_agent.api import bootstrap


def test_build_answer_service_delegates_to_agent_runtime(monkeypatch) -> None:
    sentinel = cast(AnswerService, object())
    calls: list[None] = []

    def build() -> AnswerService:
        calls.append(None)
        return sentinel

    monkeypatch.setattr(bootstrap, "build_runtime_answer_service", build)

    assert bootstrap.build_answer_service() is sentinel
    assert calls == [None]
