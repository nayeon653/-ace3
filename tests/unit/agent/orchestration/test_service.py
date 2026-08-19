"""HTTP와 분리된 Answer Service 실행 경계를 검증한다."""

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from pension_agent.agent.contracts import DomainResult
from pension_agent.agent.execution import ExecutionContext
from pension_agent.agent.orchestration import (
    AnswerService,
    AnswerServiceOverloadedError,
    AnswerServiceTimeoutError,
    FinalAnswerMissingError,
    InvalidSupervisorResultError,
    SupervisorExecutionError,
)
from pension_agent.config import AgentRuntimeConfig

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeSupervisor:
    """고정된 최종 상태 또는 오류를 반환하는 테스트 Supervisor."""

    def __init__(
        self,
        *,
        result: Mapping[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.inputs: list[dict[str, Any]] = []
        self.contexts: list[ExecutionContext] = []

    async def ainvoke(
        self,
        input: dict[str, Any],
        /,
        *,
        context: ExecutionContext,
    ) -> Mapping[str, Any]:
        self.inputs.append(input)
        self.contexts.append(context)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _completed_result() -> DomainResult:
    return {
        "domain": "policy",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": "이전할 수 있습니다.",
            "missing_conditions": [],
        },
        "evidence": [],
        "calculations": [],
        "warnings": [],
    }


def _failed_result() -> DomainResult:
    return {
        "domain": "product",
        "execution_status": "failed",
        "evidence": [],
        "calculations": [],
        "warnings": [],
        "error": "도메인 분석을 완료하지 못했습니다.",
    }


def _state(*, messages: list[Any], domain_results: list[DomainResult]) -> dict[str, Any]:
    return {
        "messages": messages,
        "question_id": "Q-001",
        "question": "연금계좌를 이전할 수 있나요?",
        "domain_results": domain_results,
    }


async def test_answer_service_returns_answer_and_final_state() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="연금계좌를 이전할 수 있습니다.")],
            domain_results=[_completed_result()],
        )
    )
    service = AnswerService(supervisor)

    result = await service.run(
        question_id="Q-001",
        question="연금계좌를 이전할 수 있나요?",
    )

    assert result.answer.answer == "연금계좌를 이전할 수 있습니다."
    assert result.state["question_id"] == "Q-001"
    assert result.state["question"] == "연금계좌를 이전할 수 있나요?"
    assert result.state["domain_results"] == [_completed_result()]
    assert len(supervisor.inputs) == 1
    assert isinstance(supervisor.inputs[0]["messages"][0], HumanMessage)
    assert supervisor.inputs[0]["messages"][0].text == "연금계좌를 이전할 수 있나요?"
    assert supervisor.inputs[0]["domain_results"] == []
    assert len(supervisor.contexts) == 1


async def test_answer_service_preserves_tool_failure_as_valid_execution_state() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="상품 분석을 완료하지 못해 판단할 수 없습니다.")],
            domain_results=[_failed_result()],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001",
        question="연금계좌를 이전할 수 있나요?",
    )

    assert result.answer.answer == "상품 분석을 완료하지 못해 판단할 수 없습니다."
    assert result.state["domain_results"][0]["execution_status"] == "failed"
    assert result.state["domain_results"][0]["error"] == "도메인 분석을 완료하지 못했습니다."


async def test_answer_service_normalizes_supervisor_execution_failure() -> None:
    supervisor = FakeSupervisor(error=RuntimeError("provider 내부 오류와 민감정보"))

    with pytest.raises(SupervisorExecutionError) as exc_info:
        await AnswerService(supervisor).run(
            question_id="Q-001",
            question="연금계좌를 이전할 수 있나요?",
        )

    assert str(exc_info.value) == "Main Supervisor 실행에 실패했습니다."
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


async def test_answer_service_rejects_missing_final_answer() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[HumanMessage(content="연금계좌를 이전할 수 있나요?")],
            domain_results=[_completed_result()],
        )
    )

    with pytest.raises(FinalAnswerMissingError):
        await AnswerService(supervisor).run(
            question_id="Q-001",
            question="연금계좌를 이전할 수 있나요?",
        )


async def test_answer_service_rejects_invalid_domain_result() -> None:
    invalid_result = _completed_result()
    del invalid_result["decision"]
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="완료했습니다.")],
            domain_results=[invalid_result],
        )
    )

    with pytest.raises(InvalidSupervisorResultError):
        await AnswerService(supervisor).run(
            question_id="Q-001",
            question="연금계좌를 이전할 수 있나요?",
        )


class BlockingSupervisor:
    """동시 실행 수와 취소를 관찰하는 테스트 Supervisor."""

    def __init__(self, *, delay_seconds: float | None = None) -> None:
        self.delay_seconds = delay_seconds
        self.active = 0
        self.max_active = 0
        self.calls = 0
        self.started = asyncio.Event()
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
        self.started.set()
        try:
            if self.delay_seconds is None:
                await self.release.wait()
            else:
                await asyncio.sleep(self.delay_seconds)
        finally:
            self.active -= 1
        return {
            "messages": [AIMessage(content="완료했습니다.")],
            "question_id": input["question_id"],
            "question": input["question"],
            "domain_results": [],
        }


async def test_answer_service_limits_concurrent_requests_and_waits_for_capacity() -> None:
    supervisor = BlockingSupervisor()
    config = AgentRuntimeConfig(max_concurrent_answers=2, answer_timeout_seconds=1)
    service = AnswerService(supervisor, config=config)
    tasks = [
        asyncio.create_task(service.run(question_id=f"Q-{index}", question="질문"))
        for index in range(3)
    ]

    while supervisor.active < 2:
        await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert supervisor.calls == 2
    assert supervisor.max_active == 2

    supervisor.release.set()
    results = await asyncio.gather(*tasks)

    assert [result.state["question_id"] for result in results] == ["Q-0", "Q-1", "Q-2"]
    assert supervisor.calls == 3
    assert supervisor.max_active == 2


async def test_answer_service_rejects_above_bounded_admission_limit() -> None:
    supervisor = BlockingSupervisor()
    service = AnswerService(
        supervisor,
        config=AgentRuntimeConfig(
            max_concurrent_answers=1,
            max_pending_answers=0,
            answer_timeout_seconds=1,
        ),
    )
    active = asyncio.create_task(service.run(question_id="Q-active", question="질문"))
    await supervisor.started.wait()

    rejected = await asyncio.gather(
        *(service.run(question_id=f"Q-overflow-{index}", question="질문") for index in range(100)),
        return_exceptions=True,
    )

    assert all(isinstance(result, AnswerServiceOverloadedError) for result in rejected)
    assert supervisor.calls == 1
    assert supervisor.max_active == 1

    supervisor.release.set()
    result = await active
    assert result.state["question_id"] == "Q-active"


async def test_answer_service_deadline_includes_capacity_wait_and_graph_execution() -> None:
    supervisor = BlockingSupervisor(delay_seconds=0.05)
    config = AgentRuntimeConfig(
        max_concurrent_answers=1,
        answer_timeout_seconds=0.02,
    )
    service = AnswerService(supervisor, config=config)

    tasks = [
        asyncio.create_task(service.run(question_id=f"Q-{index}", question="질문"))
        for index in range(2)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    assert all(isinstance(result, AnswerServiceTimeoutError) for result in results)
    assert supervisor.calls == 1
    assert supervisor.max_active == 1


async def test_answer_service_cancellation_releases_capacity() -> None:
    supervisor = BlockingSupervisor()
    config = AgentRuntimeConfig(max_concurrent_answers=1, answer_timeout_seconds=1)
    service = AnswerService(supervisor, config=config)
    cancelled = asyncio.create_task(service.run(question_id="Q-1", question="질문"))
    await supervisor.started.wait()

    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled

    supervisor.release.set()
    result = await service.run(question_id="Q-2", question="질문")

    assert result.state["question_id"] == "Q-2"
    assert supervisor.max_active == 1
