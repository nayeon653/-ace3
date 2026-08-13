"""HTTP와 분리된 Answer Service 실행 경계를 검증한다."""

from collections.abc import Mapping
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from pension_agent.agent.answer_service import (
    AnswerService,
    FinalAnswerMissingError,
    InvalidSupervisorResultError,
    SupervisorExecutionError,
)
from pension_agent.agent.schemas import DomainResult


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

    def invoke(self, input: dict[str, Any], /) -> Mapping[str, Any]:
        self.inputs.append(input)
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


def test_answer_service_returns_answer_and_final_state() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="연금계좌를 이전할 수 있습니다.")],
            domain_results=[_completed_result()],
        )
    )
    service = AnswerService(supervisor)

    result = service.run(
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


def test_answer_service_preserves_tool_failure_as_valid_execution_state() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="상품 분석을 완료하지 못해 판단할 수 없습니다.")],
            domain_results=[_failed_result()],
        )
    )

    result = AnswerService(supervisor).run(
        question_id="Q-001",
        question="연금계좌를 이전할 수 있나요?",
    )

    assert result.answer.answer == "상품 분석을 완료하지 못해 판단할 수 없습니다."
    assert result.state["domain_results"][0]["execution_status"] == "failed"
    assert result.state["domain_results"][0]["error"] == "도메인 분석을 완료하지 못했습니다."


def test_answer_service_normalizes_supervisor_execution_failure() -> None:
    supervisor = FakeSupervisor(error=RuntimeError("provider 내부 오류와 민감정보"))

    with pytest.raises(SupervisorExecutionError) as exc_info:
        AnswerService(supervisor).run(
            question_id="Q-001",
            question="연금계좌를 이전할 수 있나요?",
        )

    assert str(exc_info.value) == "Main Supervisor 실행에 실패했습니다."
    assert exc_info.value.__cause__ is None


def test_answer_service_rejects_missing_final_answer() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[HumanMessage(content="연금계좌를 이전할 수 있나요?")],
            domain_results=[_completed_result()],
        )
    )

    with pytest.raises(FinalAnswerMissingError):
        AnswerService(supervisor).run(
            question_id="Q-001",
            question="연금계좌를 이전할 수 있나요?",
        )


def test_answer_service_rejects_invalid_domain_result() -> None:
    invalid_result = _completed_result()
    del invalid_result["decision"]
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="완료했습니다.")],
            domain_results=[invalid_result],
        )
    )

    with pytest.raises(InvalidSupervisorResultError):
        AnswerService(supervisor).run(
            question_id="Q-001",
            question="연금계좌를 이전할 수 있나요?",
        )
