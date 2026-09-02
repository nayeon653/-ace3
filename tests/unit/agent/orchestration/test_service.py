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
    AnswerServiceClosedError,
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


def _catalog_result() -> DomainResult:
    return {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": "미래에셋 상품 카탈로그에서 2개를 조회했습니다.",
            "missing_conditions": [],
        },
        "evidence": [
            {
                "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_file_name": "product_catalog.json",
                "title": "검증된 상품 카탈로그 조회 결과",
                "locator": "provider=미래에셋;catalog_version=v1",
                "content": "결정론적 카탈로그 결과",
            }
        ],
        "calculations": [],
        "warnings": [],
        "catalog_result": {
            "route": "browse_catalog",
            "provider": "미래에셋",
            "return_mode": "count_and_items",
            "total_count": 2,
            "items": [
                {
                    "product_code": "KR510902511M",
                    "official_name": "미래에셋장기성장포커스",
                    "provider": "미래에셋",
                },
                {
                    "product_code": "KR510902773M",
                    "official_name": "미래에셋고배당포커스",
                    "provider": "미래에셋",
                },
            ],
            "catalog_version": "v1",
        },
    }


def _calculation_result() -> DomainResult:
    return {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": "검증된 Python 계산 결과입니다.",
            "missing_conditions": [],
        },
        "evidence": [
            {
                "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_file_name": "rules.pdf",
                "title": "연금수령한도",
                "locator": "1쪽",
                "content": "연금수령한도 계산 규칙",
            }
        ],
        "calculations": [
            {
                "calculator_id": "pension_withdrawal_limit",
                "inputs": {
                    "account_valuation_krw": "10000000",
                    "pension_year": 1,
                },
                "input_sources": {
                    "account_valuation_krw": {
                        "origin": "question",
                        "text": "평가액 1천만원",
                        "chunk_id": None,
                    },
                    "pension_year": {
                        "origin": "question",
                        "text": "1년차",
                        "chunk_id": None,
                    },
                },
                "outputs": {"withdrawal_limit": "1200000.0"},
                "units": {"withdrawal_limit": "KRW"},
                "warnings": [
                    "출처에는 최종 지급 단위의 반올림·절사 규칙이 명시되지 않았습니다.",
                ],
            }
        ],
        "warnings": ["검색 범위가 제한적입니다."],
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


async def test_answer_service_replaces_catalog_only_answer_with_verified_values() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="미래에셋 상품은 99개입니다.")],
            domain_results=[_catalog_result()],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001",
        question="연금계좌를 이전할 수 있나요?",
    )

    assert result.answer.answer == (
        "미래에셋 상품은 총 2개입니다.\n\n"
        "미래에셋 상품 목록:\n"
        "- 미래에셋장기성장포커스 (미래에셋, KR510902511M)\n"
        "- 미래에셋고배당포커스 (미래에셋, KR510902773M)"
    )
    assert "99" not in result.answer.answer


async def test_answer_service_replaces_calculation_only_answer_with_verified_values() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="연금수령한도는 999원입니다.")],
            domain_results=[_calculation_result()],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001",
        question="연금계좌를 이전할 수 있나요?",
    )

    assert "연금수령한도: 1200000.0 KRW" in result.answer.answer
    assert "반올림·절사 규칙" in result.answer.answer
    assert "999" not in result.answer.answer


async def test_answer_service_rebuilds_mixed_answer_from_verified_domain_results() -> None:
    conditional_result = _completed_result()
    conditional_result["decision"] = {
        "status": "conditional",
        "conclusion": "조건에 따라 이전할 수 있습니다.",
        "missing_conditions": ["가입 유형"],
    }
    conditional_result["warnings"] = ["이전 전 수수료를 확인해야 합니다."]
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="이전할 수 없고 계산값은 999원입니다.")],
            domain_results=[conditional_result, _calculation_result(), _failed_result()],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001",
        question="연금계좌를 이전할 수 있나요?",
    )

    assert "조건에 따라 이전할 수 있습니다." in result.answer.answer
    assert "가입 유형" in result.answer.answer
    assert "이전 전 수수료" in result.answer.answer
    assert "검색 범위가 제한적" in result.answer.answer
    assert "상품·운용 분석을 완료하지 못했습니다" in result.answer.answer
    assert "연금수령한도: 1200000.0 KRW" in result.answer.answer
    assert "999" not in result.answer.answer


async def test_answer_service_preserves_both_medical_care_domain_results() -> None:
    policy_result = _completed_result()
    policy_result["decision"] = {
        "status": "conditional",
        "conclusion": "DC 의료비 중도인출 가능 여부는 요양기간에 따라 달라집니다.",
        "missing_conditions": ["제도상 요양기간 확인"],
    }
    policy_result["evidence"] = [
        {
            "chunk_id": "550e8400-e29b-41d4-a716-446655440001",
            "source_file_name": "policy.pdf",
            "title": "의료비 중도인출 사유",
            "locator": "2쪽",
            "content": "제도상 의료비 중도인출 조건",
        }
    ]
    policy_result["warnings"] = ["계좌 유형을 확인해야 합니다."]
    tax_result = _calculation_result()
    tax_result["decision"] = {
        "status": "determined",
        "conclusion": "의료 목적 인출의 세액과 세후액을 계산했습니다.",
        "missing_conditions": [],
    }
    question = "DC 의료비 중도인출이 가능한지와 세금까지 알려 주세요."
    supervisor_state = _state(
        messages=[AIMessage(content="의료비 인출 결과입니다.")],
        domain_results=[policy_result, tax_result],
    )
    supervisor_state["question"] = question
    supervisor = FakeSupervisor(result=supervisor_state)

    result = await AnswerService(supervisor).run(
        question_id="Q-001",
        question=question,
    )

    assert result.state["domain_results"] == [policy_result, tax_result]
    assert result.state["domain_results"][0]["evidence"] == policy_result["evidence"]
    assert result.state["domain_results"][1]["evidence"] == tax_result["evidence"]
    assert (
        result.state["domain_results"][1]["calculations"][0]["input_sources"]
        == tax_result["calculations"][0]["input_sources"]
    )
    assert "제도상 요양기간 확인" in result.answer.answer
    assert "계좌 유형을 확인해야 합니다." in result.answer.answer
    assert "연금수령한도: 1200000.0 KRW" in result.answer.answer


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


async def test_answer_service_shutdown_cancels_requests_before_closing_clients() -> None:
    events: list[str] = []

    class CancellationRecordingSupervisor(BlockingSupervisor):
        async def ainvoke(
            self,
            input: dict[str, Any],
            /,
            *,
            context: ExecutionContext,
        ) -> Mapping[str, Any]:
            try:
                return await super().ainvoke(input, context=context)
            except asyncio.CancelledError:
                events.append("request-cancelled")
                raise

    async def close_client() -> None:
        events.append("client-closed")

    supervisor = CancellationRecordingSupervisor()
    service = AnswerService(supervisor, close_callbacks=(close_client,))
    request = asyncio.create_task(service.run(question_id="Q-1", question="질문"))
    await supervisor.started.wait()

    await service.aclose()

    with pytest.raises(asyncio.CancelledError):
        await request
    assert events == ["request-cancelled", "client-closed"]
    with pytest.raises(AnswerServiceClosedError):
        await service.run(question_id="Q-2", question="질문")

    await service.aclose()
    assert events == ["request-cancelled", "client-closed"]


async def test_shutdown_never_closes_client_before_noncooperative_request_finishes() -> None:
    events: list[str] = []
    started = asyncio.Event()
    release = asyncio.Event()
    client_closed = asyncio.Event()

    class SlowCancellationSupervisor:
        async def ainvoke(
            self,
            input: dict[str, Any],
            /,
            *,
            context: ExecutionContext,
        ) -> Mapping[str, Any]:
            del context
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                events.append("request-cancelled")
                await release.wait()
            events.append("request-finished")
            return {
                "messages": [AIMessage(content="완료했습니다.")],
                "question_id": input["question_id"],
                "question": input["question"],
                "domain_results": [],
            }

    async def close_client() -> None:
        events.append("client-closed")
        client_closed.set()

    service = AnswerService(
        SlowCancellationSupervisor(),
        config=AgentRuntimeConfig(shutdown_timeout_seconds=0.01),
        close_callbacks=(close_client,),
    )
    request = asyncio.create_task(service.run(question_id="Q-1", question="질문"))
    await started.wait()

    await service.aclose()

    assert events == ["request-cancelled"]
    assert not client_closed.is_set()

    release.set()
    result = await request
    assert not client_closed.is_set()
    await service.aclose()

    assert result.state["question_id"] == "Q-1"
    assert events == ["request-cancelled", "request-finished", "client-closed"]
    await service.aclose()
    assert events == ["request-cancelled", "request-finished", "client-closed"]
