"""HTTP와 분리된 Main Supervisor 실행 경계."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import TypeAdapter, ValidationError

from pension_agent.agent.schemas import AgentAnswer, DomainResult, validate_domain_result
from pension_agent.agent.state import SupervisorState
from pension_agent.agent.supervisor import build_agent_answer

_DOMAIN_RESULT_ADAPTER = TypeAdapter(DomainResult)


class SupervisorRunner(Protocol):
    """Answer Service가 사용하는 최소 Supervisor 실행 계약."""

    def invoke(self, input: dict[str, Any], /) -> Mapping[str, Any]:
        """초기 상태로 Supervisor를 실행하고 최종 상태를 반환한다."""


class AnswerServiceError(RuntimeError):
    """Answer Service가 외부에 노출하는 정제된 실행 오류."""


class SupervisorExecutionError(AnswerServiceError):
    """Supervisor 실행 자체를 완료하지 못한 경우."""


class InvalidSupervisorResultError(AnswerServiceError):
    """Supervisor가 공통 계약에 맞지 않는 최종 상태를 반환한 경우."""


class FinalAnswerMissingError(InvalidSupervisorResultError):
    """Supervisor 최종 상태에 자연어 답변이 없는 경우."""


@dataclass(frozen=True, slots=True)
class AnswerServiceResult:
    """검증된 자연어 답변과 최종 Supervisor 상태."""

    answer: AgentAnswer
    state: SupervisorState


class AnswerService:
    """질문을 Main Supervisor에 전달하고 애플리케이션 결과로 변환한다."""

    def __init__(self, supervisor: SupervisorRunner) -> None:
        self._supervisor = supervisor

    def run(self, *, question_id: str, question: str) -> AnswerServiceResult:
        """Supervisor를 실행하고 검증된 답변과 상태를 반환한다."""

        initial_state: dict[str, Any] = {
            "messages": [HumanMessage(content=question)],
            "question_id": question_id,
            "question": question,
            "domain_results": [],
        }
        try:
            raw_state = self._supervisor.invoke(initial_state)
        # Supervisor 경계에서 모든 실행 오류를 애플리케이션 오류로 정규화한다.
        except Exception:  # noqa: BLE001
            raise SupervisorExecutionError("Main Supervisor 실행에 실패했습니다.") from None

        state = _validate_supervisor_state(
            raw_state,
            question_id=question_id,
            question=question,
        )
        try:
            answer = build_agent_answer(state["messages"])
        except ValueError:
            raise FinalAnswerMissingError(
                "Main Supervisor의 최종 자연어 답변이 없습니다."
            ) from None

        return AnswerServiceResult(answer=answer, state=state)


def _validate_supervisor_state(
    raw_state: Mapping[str, Any],
    *,
    question_id: str,
    question: str,
) -> SupervisorState:
    """Supervisor 최종 상태의 필수 필드와 도메인 결과를 검증한다."""

    if not isinstance(raw_state, Mapping):
        raise InvalidSupervisorResultError("Main Supervisor 결과가 객체가 아닙니다.")
    if raw_state.get("question_id") != question_id:
        raise InvalidSupervisorResultError("Main Supervisor가 question_id를 변경했습니다.")
    if raw_state.get("question") != question:
        raise InvalidSupervisorResultError("Main Supervisor가 질문 원문을 변경했습니다.")

    messages = raw_state.get("messages")
    if not isinstance(messages, list) or not all(
        isinstance(message, BaseMessage) for message in messages
    ):
        raise InvalidSupervisorResultError("Main Supervisor 메시지 결과가 올바르지 않습니다.")

    raw_domain_results = raw_state.get("domain_results")
    if not isinstance(raw_domain_results, list):
        raise InvalidSupervisorResultError("Main Supervisor 도메인 결과가 올바르지 않습니다.")

    domain_results: list[DomainResult] = []
    for raw_result in raw_domain_results:
        try:
            result = _DOMAIN_RESULT_ADAPTER.validate_python(raw_result)
            validate_domain_result(result)
        except (KeyError, TypeError, ValueError, ValidationError):
            raise InvalidSupervisorResultError(
                "Main Supervisor 도메인 결과가 계약을 위반했습니다."
            ) from None
        domain_results.append(result)

    normalized_state = dict(raw_state)
    normalized_state["messages"] = list(messages)
    normalized_state["domain_results"] = domain_results
    return cast(SupervisorState, normalized_state)
