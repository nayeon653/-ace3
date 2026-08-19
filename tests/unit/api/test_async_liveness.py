"""답변 요청이 포화돼도 async API의 liveness가 유지되는지 검증한다."""

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage

from pension_agent.agent.execution import ExecutionContext
from pension_agent.agent.orchestration import AnswerService
from pension_agent.api.app import create_app
from pension_agent.config import AgentRuntimeConfig


class BlockingSupervisor:
    """AnswerService의 실제 capacity 안에서 provider 대기를 재현하는 fake graph."""

    def __init__(self, expected_active: int) -> None:
        self.expected_active = expected_active
        self.active = 0
        self.max_active = 0
        self.calls = 0
        self.saturated = asyncio.Event()
        self.release = asyncio.Event()

    async def ainvoke(
        self,
        input: dict[str, Any],
        /,
        *,
        context: ExecutionContext,
    ) -> Mapping[str, Any]:
        del context
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if self.active == self.expected_active:
            self.saturated.set()
        try:
            await self.release.wait()
        finally:
            self.active -= 1
        return {
            "messages": [AIMessage(content="완료")],
            "question_id": input["question_id"],
            "question": input["question"],
            "domain_results": [],
        }


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health_responds_while_forty_answer_requests_are_capacity_blocked() -> None:
    supervisor = BlockingSupervisor(expected_active=4)
    service = AnswerService(
        supervisor,
        config=AgentRuntimeConfig(
            max_concurrent_answers=4,
            answer_timeout_seconds=5,
        ),
    )

    async def factory() -> AnswerService:
        return service

    application = create_app(answer_service_factory=factory)
    transport = ASGITransport(app=application)
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        answer_tasks = [
            asyncio.create_task(
                client.get(
                    "/answer",
                    params={"question_id": f"Q-{index}", "question": "질문"},
                )
            )
            for index in range(40)
        ]
        try:
            await asyncio.wait_for(supervisor.saturated.wait(), timeout=1)
            assert supervisor.calls == 4
            health = await asyncio.wait_for(client.get("/health"), timeout=0.5)
        finally:
            supervisor.release.set()
            answers = await asyncio.gather(*answer_tasks)

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert all(response.status_code == 200 for response in answers)
    assert supervisor.calls == 40
    assert supervisor.max_active == 4
