"""HTTP와 분리된 Main Supervisor 실행 경계."""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Any, Protocol, cast

from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import TypeAdapter, ValidationError

from pension_agent.agent.calculation import format_calculation_summary
from pension_agent.agent.comparison_formatting import format_comparison_result
from pension_agent.agent.contracts import (
    AgentAnswer,
    CatalogResult,
    DomainResult,
    validate_domain_result,
)
from pension_agent.agent.execution import ExecutionContext
from pension_agent.agent.orchestration.numeric_firewall import (
    extract_numbers,
    placeholder_token,
    scan_placeholders,
    strip_known_placeholders,
)
from pension_agent.agent.orchestration.state import SupervisorState
from pension_agent.agent.orchestration.supervisor import build_agent_answer
from pension_agent.config import DEFAULT_AGENT_RUNTIME_CONFIG, AgentRuntimeConfig

_DOMAIN_RESULT_ADAPTER = TypeAdapter(DomainResult)
logger = logging.getLogger(__name__)


class SupervisorRunner(Protocol):
    """Answer Service가 사용하는 최소 Supervisor 실행 계약."""

    async def ainvoke(
        self,
        input: dict[str, Any],
        /,
        *,
        context: ExecutionContext,
    ) -> Mapping[str, Any]:
        """초기 상태로 Supervisor를 실행하고 최종 상태를 반환한다."""


class AnswerServiceError(RuntimeError):
    """Answer Service가 외부에 노출하는 정제된 실행 오류."""


class SupervisorExecutionError(AnswerServiceError):
    """Supervisor 실행 자체를 완료하지 못한 경우."""


class AnswerServiceTimeoutError(AnswerServiceError):
    """capacity 대기부터 응답 조립까지의 요청 전체 예산을 초과한 경우."""


class AnswerServiceOverloadedError(AnswerServiceError):
    """프로세스의 bounded answer 대기열까지 모두 사용 중인 경우."""


class AnswerServiceClosedError(AnswerServiceError):
    """종료가 시작된 프로세스 공용 Service에 새 요청이 들어온 경우."""


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

    def __init__(
        self,
        supervisor: SupervisorRunner,
        *,
        config: AgentRuntimeConfig = DEFAULT_AGENT_RUNTIME_CONFIG,
        close_callbacks: tuple[Callable[[], Awaitable[None]], ...] = (),
    ) -> None:
        self._supervisor = supervisor
        self._config = config
        self._close_callbacks = close_callbacks
        self._capacity = asyncio.Semaphore(config.max_concurrent_answers)
        admission_limit = config.max_concurrent_answers + config.max_pending_answers
        self._admission = asyncio.Queue[None](maxsize=admission_limit)
        for _ in range(admission_limit):
            self._admission.put_nowait(None)
        self._active_tasks: set[asyncio.Task[Any]] = set()
        self._shutdown_lock = asyncio.Lock()
        self._resource_close_lock = asyncio.Lock()
        self._resources_closed = False
        self._closed = False

    async def run(self, *, question_id: str, question: str) -> AnswerServiceResult:
        """Supervisor를 실행하고 검증된 답변과 상태를 반환한다."""

        if self._closed:
            raise AnswerServiceClosedError("Answer Service가 이미 종료됐습니다.")
        try:
            self._admission.get_nowait()
        except asyncio.QueueEmpty:
            raise AnswerServiceOverloadedError(
                "Answer Service 요청 대기열이 가득 찼습니다."
            ) from None

        try:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + self._config.answer_timeout_seconds
            context = ExecutionContext(deadline=deadline)
            current_task = asyncio.current_task()
            if current_task is not None:
                self._active_tasks.add(current_task)

            initial_state: dict[str, Any] = {
                "messages": [HumanMessage(content=question)],
                "question_id": question_id,
                "question": question,
                "domain_results": [],
            }
            try:
                try:
                    async with asyncio.timeout_at(deadline):
                        async with self._capacity:
                            if self._closed:
                                raise AnswerServiceClosedError(
                                    "Answer Service가 이미 종료됐습니다."
                                )
                            raw_state = await _invoke_supervisor(
                                self._supervisor,
                                initial_state,
                                context=context,
                            )
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
                            answer = _strip_pseudo_placeholder_syntax(
                                _stabilize_verified_answer(
                                    answer, state["domain_results"], question
                                )
                            )
                except TimeoutError:
                    raise AnswerServiceTimeoutError(
                        "Answer Service 요청 전체 실행 시간이 초과됐습니다."
                    ) from None
            finally:
                if current_task is not None:
                    self._active_tasks.discard(current_task)
        finally:
            self._admission.put_nowait(None)

        return AnswerServiceResult(answer=answer, state=state)

    async def aclose(self) -> None:
        """요청을 먼저 회수하고 외부 client를 한 번만 정리한다."""

        async with self._shutdown_lock:
            if self._resources_closed:
                return

            self._closed = True
            current_task = asyncio.current_task()
            active_tasks = {
                task for task in self._active_tasks if task is not current_task and not task.done()
            }
            for task in active_tasks:
                task.cancel()
            if active_tasks:
                done, pending = await asyncio.wait(
                    active_tasks,
                    timeout=self._config.shutdown_timeout_seconds,
                )
                for task in done:
                    if not task.cancelled():
                        task.exception()
                if pending:
                    logger.warning(
                        "Answer Service 종료 제한 시간 안에 %d개 요청이 끝나지 않아 "
                        "실행 중 client를 닫지 않고 정리를 건너뜁니다.",
                        len(pending),
                    )
                    return

            await self._close_resources()

    async def _close_resources(self) -> None:
        """runtime 소유 리소스를 등록된 의존성 역순으로 한 번만 닫는다."""

        async with self._resource_close_lock:
            if self._resources_closed:
                return
            for callback in self._close_callbacks:
                try:
                    await callback()
                except Exception:  # noqa: BLE001
                    logger.warning("Answer Service 리소스 정리에 실패했습니다.")
            self._resources_closed = True


async def _invoke_supervisor(
    supervisor: SupervisorRunner,
    initial_state: dict[str, Any],
    *,
    context: ExecutionContext,
) -> Mapping[str, Any]:
    """원본 예외 연결을 남기지 않고 Supervisor 실행 오류를 정규화한다."""

    try:
        return await supervisor.ainvoke(initial_state, context=context)
    # Supervisor 경계에서 모든 실행 오류를 애플리케이션 오류로 정규화한다.
    except Exception:  # noqa: BLE001
        error = SupervisorExecutionError("Main Supervisor 실행에 실패했습니다.")

    raise error


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


def _stabilize_verified_answer(
    answer: AgentAnswer, domain_results: list[DomainResult], question: str
) -> AgentAnswer:
    """비교 또는 실행 실패가 포함된 답변을 검증된 도메인 결과로 조립한다."""

    if any(
        "comparison_result" in result or result["execution_status"] != "completed"
        for result in domain_results
    ):
        parts: list[str] = []
        for result in domain_results:
            if "comparison_result" in result:
                parts.append(format_comparison_result(result))
            elif "catalog_result" in result:
                parts.append(_catalog_answer(result["catalog_result"]))
            else:
                parts.append(_format_other_domain_result(result, question))
        return AgentAnswer(answer="\n\n".join(part for part in parts if part))
    return _stabilize_catalog_answer(
        _stabilize_calculation_answer(
            _stabilize_verified_numeric_answer(
                _stabilize_unverified_calculation_answer(answer, domain_results, question),
                domain_results,
            ),
            domain_results,
        ),
        domain_results,
    )


def _format_other_domain_result(result: DomainResult, question: str) -> str:
    """비교와 함께 요청된 다른 도메인의 검증된 결과를 그대로 보존한다."""

    label = _domain_label(result["domain"])
    if result["execution_status"] != "completed":
        return f"{label} 분석을 완료하지 못했습니다: {result['error']}"
    decision = result["decision"]
    if decision["status"] == "not_applicable":
        return ""
    statements = result.get("verified_numeric_statements", [])
    parts = list(dict.fromkeys(statement["text"] for statement in statements))
    if not statements and not result["calculations"]:
        conclusion = _stabilize_unverified_calculation_answer(
            AgentAnswer(answer=decision["conclusion"]), [result], question
        ).answer
        parts.append(f"{label}: {conclusion}")
    warnings = list(result["warnings"])
    if result["calculations"]:
        parts.append(
            "검증된 Python 계산 결과:\n" + format_calculation_summary(result["calculations"])
        )
        warnings.extend(
            warning for calculation in result["calculations"] for warning in calculation["warnings"]
        )
    for heading, values in (
        (f"{label} 확인 조건", decision["missing_conditions"]),
        (f"{label} 주의사항", list(dict.fromkeys(warnings))),
    ):
        if values:
            parts.append(heading + ":\n" + "\n".join(f"- {value}" for value in values))
    if result["evidence"]:
        parts.append(
            "근거 문서:\n"
            + "\n".join(
                f"- {chunk['source_file_name']}, {chunk['title']}, {chunk['locator']}"
                for chunk in result["evidence"]
            )
        )
    return "\n\n".join(parts)


def _stabilize_catalog_answer(
    answer: AgentAnswer,
    domain_results: list[DomainResult],
) -> AgentAnswer:
    """LLM 표현과 무관하게 검증된 카탈로그 개수와 목록을 보존한다."""

    catalog_results = [
        result["catalog_result"] for result in domain_results if "catalog_result" in result
    ]
    if not catalog_results:
        return answer

    catalog_text = "\n\n".join(_catalog_answer(result) for result in catalog_results)
    if len(catalog_results) == len(domain_results):
        return AgentAnswer(answer=catalog_text)
    return AgentAnswer(answer=f"{answer.answer.rstrip()}\n\n{catalog_text}")


def _stabilize_calculation_answer(
    answer: AgentAnswer,
    domain_results: list[DomainResult],
) -> AgentAnswer:
    """LLM 표현과 무관하게 검증된 Python 계산값을 최종 답변에 보존한다."""

    calculation_domains = [result for result in domain_results if result["calculations"]]
    calculations = [
        calculation for result in calculation_domains for calculation in result["calculations"]
    ]
    if not calculations:
        return answer

    conclusions: list[str] = []
    conditions: list[str] = []
    warnings: list[str] = []
    for result in domain_results:
        if "catalog_result" in result:
            continue
        warnings.extend(result["warnings"])
        if result["execution_status"] != "completed":
            conclusions.append(
                f"{_domain_label(result['domain'])} 분석을 완료하지 못했습니다: {result['error']}"
            )
            continue
        decision = result["decision"]
        if decision["status"] == "not_applicable":
            continue
        if not result["calculations"]:
            conclusions.append(decision["conclusion"])
        if decision["missing_conditions"]:
            condition_text = "\n".join(
                f"- {condition}" for condition in decision["missing_conditions"]
            )
            conditions.append(f"{_domain_label(result['domain'])} 확인 조건:\n{condition_text}")
    calculation_text = "검증된 Python 계산 결과:\n" + format_calculation_summary(calculations)
    conclusions.append(calculation_text)
    warnings.extend(warning for calculation in calculations for warning in calculation["warnings"])
    answer_parts = [*conclusions, *conditions]
    unique_warnings = list(dict.fromkeys(warnings))
    if unique_warnings:
        warning_text = "\n".join(f"- {warning}" for warning in unique_warnings)
        answer_parts.append(f"주의사항:\n{warning_text}")
    return AgentAnswer(answer="\n\n".join(answer_parts))


def _stabilize_unverified_calculation_answer(
    answer: AgentAnswer,
    domain_results: list[DomainResult],
    question: str,
) -> AgentAnswer:
    """계산 근거가 없는 파생 숫자가 Main 응답으로 빠져나가는 것을 막는다."""

    if any(
        result["calculations"] or result.get("verified_numeric_statements", [])
        for result in domain_results
    ):
        return answer
    answer_numbers = set(extract_numbers(answer.answer))
    if not answer_numbers:
        return answer
    question_numbers = set(extract_numbers(question))
    has_incomplete_result = any(
        result["execution_status"] != "completed"
        or result["decision"]["status"] in {"conditional", "undetermined"}
        for result in domain_results
    )
    if not has_incomplete_result and answer_numbers <= question_numbers:
        return answer
    if not has_incomplete_result and not question_numbers:
        return answer
    if answer_numbers <= question_numbers:
        return answer
    return AgentAnswer(answer=_unverified_calculation_fallback(domain_results, question_numbers))


def _unverified_calculation_fallback(
    domain_results: list[DomainResult],
    question_numbers: AbstractSet[object],
) -> str:
    """미검증 파생 숫자를 제외하고 상태·누락 조건·경고만 결정적으로 보존한다."""

    conclusions: list[str] = []
    conditions: list[str] = []
    warnings: list[str] = []
    for result in domain_results:
        if "catalog_result" in result:
            continue
        warnings.extend(result["warnings"])
        if result["execution_status"] != "completed":
            conclusions.append(
                f"{_domain_label(result['domain'])} 분석을 완료하지 못했습니다. {result['error']}"
            )
            continue
        decision = result["decision"]
        if decision["status"] == "not_applicable":
            continue
        conclusion_numbers = set(extract_numbers(decision["conclusion"]))
        if conclusion_numbers - question_numbers:
            conclusions.append(
                f"{_domain_label(result['domain'])}: 검증된 계산 결과가 없어 "
                "새로운 수치 결론을 제공할 수 없습니다."
            )
        else:
            conclusions.append(decision["conclusion"])
        if decision["missing_conditions"]:
            condition_text = "\n".join(
                f"- {condition}" for condition in decision["missing_conditions"]
            )
            conditions.append(f"{_domain_label(result['domain'])} 확인 조건:\n{condition_text}")
    if not conclusions:
        conclusions.append("검증된 계산 결과가 없어 새로운 수치 결론을 제공할 수 없습니다.")
    answer_parts = [*conclusions, *conditions]
    unique_warnings = list(dict.fromkeys(warnings))
    if unique_warnings:
        answer_parts.append("주의사항:\n" + "\n".join(f"- {item}" for item in unique_warnings))
    return "\n\n".join(answer_parts)


def _stabilize_verified_numeric_answer(
    answer: AgentAnswer,
    domain_results: list[DomainResult],
) -> AgentAnswer:
    """Main이 검증된 숫자 placeholder 밖에서 새 숫자를 만들지 못하게 막는다.

    Main은 `VerifiedNumericStatement.text`를 직접 본 적이 없다 — Tool 결과에서는
    placeholder token만 받았다. 따라서 최종 답변에서 그 token들이 정확히(같은
    token 반복은 허용) 등장하고, token 밖 자유 생성 영역에 금액·세율 같은
    검증되지 않은 숫자가 전혀 없을 때만 Main의 표현을 그대로 쓴다. 하나라도
    어긋나면 Main 답변 전체를 버리고 결정론적으로 다시 조립한다 — 문장 일부만
    지우면 문맥이 깨지므로 부분 삭제는 하지 않는다.
    """

    canonical_by_token: dict[str, str] = {
        placeholder_token(result["domain"], statement["source_id"]): statement["text"]
        for result in domain_results
        for statement in result.get("verified_numeric_statements", [])
    }
    if not canonical_by_token:
        return answer

    expected_tokens = set(canonical_by_token)
    text = answer.answer
    scan = scan_placeholders(text, expected_tokens)
    missing = expected_tokens - set(scan.counts)
    free_text = strip_known_placeholders(text, expected_tokens)
    leaked = extract_numbers(free_text)

    if missing or scan.malformed or leaked:
        return AgentAnswer(answer=_deterministic_numeric_fallback(domain_results))

    return AgentAnswer(answer=_substitute_with_dedup(text, canonical_by_token))


def _substitute_with_dedup(text: str, canonical_by_token: dict[str, str]) -> str:
    """token 첫 등장만 canonical 문장으로 바꾸고, 반복 등장은 지운다.

    Main은 placeholder를 완결된 문장이 아니라 맨숫자 자리인 것처럼 다뤄
    "...600만원입니다.만원까지..."처럼 canonical 문장 바로 뒤에 단위 잔여물을
    이어 붙이기도 한다. canonical 문장이 이미 마침표로 끝나 있다면 그 잔여물만
    제거한다 — 반복 등장(dedup으로 지워지는 자리)에는 적용하지 않는다.
    """

    result = text
    for token, canonical_text in canonical_by_token.items():
        parts = result.split(token)
        if len(parts) <= 1:
            continue
        first_tail = _strip_trailing_unit_residue(parts[1], canonical_text)
        result = parts[0] + canonical_text + first_tail + "".join(parts[2:])
    return result


_UNIT_RESIDUE_WORDS = ("만원", "천원", "억원", "원", "퍼센트", "프로", "%")
_TRAILING_UNIT_RESIDUE = re.compile(
    "^(?:"
    + "|".join(re.escape(word) for word in sorted(_UNIT_RESIDUE_WORDS, key=len, reverse=True))
    + ")(?:까지|만|은|는|이|가|을|를|도)?"
)


def _strip_trailing_unit_residue(tail: str, canonical_text: str) -> str:
    """치환된 문장이 이미 완결됐는데 바로 뒤에 붙은 단위 잔여물만 제거한다.

    canonical_text가 마침표로 끝나지 않으면(완결된 문장이 아니면) 손대지 않는다.
    특정 숫자가 아니라 단위 어휘(만원/원/%/퍼센트 등)만 인식하므로 다른 조사나
    서술어로 자연스럽게 이어지는 문장은 건드리지 않는다.
    """

    if not canonical_text.rstrip().endswith("."):
        return tail
    match = _TRAILING_UNIT_RESIDUE.match(tail)
    if match is None:
        return tail
    return tail[match.end() :]


_PSEUDO_PLACEHOLDER = re.compile(r"\{\{([^{}\n]{1,60})\}\}")


def _strip_pseudo_placeholder_syntax(answer: AgentAnswer) -> AgentAnswer:
    """알려진 치환을 모두 마친 뒤에도 `{{...}}` 구문이 남아 있으면 정리한다.

    `_stabilize_verified_numeric_answer`는 도메인 결과 중 하나라도
    `verified_numeric_statements`를 가질 때만 개입한다. Policy/Product처럼
    그 필드가 전혀 없는 답변에서 Main이 스스로 `{{1800}}` 같은 임의의
    `{{...}}` 표기를 흉내 내면 어떤 stabilizer도 거치지 않고 그대로 노출될 수
    있다 — 이 함수는 그 경로까지 포함해 최종 답변 전체에 적용하는 마지막
    안전망이다. 특정 숫자를 하드코딩하지 않고 중괄호만 벗겨 안쪽 텍스트를
    그대로 남긴다.
    """

    text = answer.answer
    cleaned = _PSEUDO_PLACEHOLDER.sub(lambda match: match.group(1), text)
    if cleaned == text:
        return answer
    return AgentAnswer(answer=cleaned)


def _deterministic_numeric_fallback(domain_results: list[DomainResult]) -> str:
    """LLM 호출 없이 검증된 텍스트만으로 안전한 답변을 다시 조립한다."""

    conclusions: list[str] = []
    conditions: list[str] = []
    warnings: list[str] = []
    for result in domain_results:
        if "catalog_result" in result:
            continue
        warnings.extend(result["warnings"])
        if result["execution_status"] != "completed":
            conclusions.append(
                f"{_domain_label(result['domain'])} 분석을 완료하지 못했습니다: {result['error']}"
            )
            continue
        decision = result["decision"]
        if decision["status"] == "not_applicable":
            continue
        statements = result.get("verified_numeric_statements", [])
        if statements:
            conclusions.extend(dict.fromkeys(statement["text"] for statement in statements))
        elif result["calculations"]:
            conclusions.append(
                "검증된 Python 계산 결과:\n" + format_calculation_summary(result["calculations"])
            )
        else:
            conclusions.append(decision["conclusion"])
        if decision["missing_conditions"]:
            condition_text = "\n".join(
                f"- {condition}" for condition in decision["missing_conditions"]
            )
            conditions.append(f"{_domain_label(result['domain'])} 확인 조건:\n{condition_text}")
        warnings.extend(
            warning for calculation in result["calculations"] for warning in calculation["warnings"]
        )
    if not conclusions:
        conclusions.append("검증된 근거만으로는 확인할 수 있는 결론이 없습니다.")
    answer_parts = [*conclusions, *conditions]
    unique_warnings = list(dict.fromkeys(warnings))
    if unique_warnings:
        warning_text = "\n".join(f"- {warning}" for warning in unique_warnings)
        answer_parts.append(f"주의사항:\n{warning_text}")
    return "\n\n".join(answer_parts)


def _domain_label(domain: str) -> str:
    """내부 도메인 이름을 사용자용 레이블로 변환한다."""

    return {
        "policy": "업무·제도",
        "tax_payout": "세제·수령",
        "product": "상품·운용",
    }.get(domain, domain)


def _catalog_answer(result: CatalogResult) -> str:
    """CatalogResult의 return_mode에 맞는 결정론적 한국어 답변을 만든다."""

    subject = result["provider"] or "전체"
    parts: list[str] = []
    if result["return_mode"] in {"count", "count_and_items"}:
        parts.append(f"{subject} 상품은 총 {result['total_count']}개입니다.")
    if result["return_mode"] in {"items", "count_and_items"}:
        lines = [
            f"- {item['official_name']} ({item['provider']}, {item['product_code']})"
            for item in result["items"]
        ]
        parts.append(f"{subject} 상품 목록:\n" + "\n".join(lines))
    return "\n\n".join(parts)
