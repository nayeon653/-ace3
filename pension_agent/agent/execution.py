"""Agent 수직 경로가 공유하는 요청 실행 예산."""

import asyncio
import logging
import math
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, TypeVar

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import AIMessage, ToolMessage
from openai import APIStatusError

_ResultT = TypeVar("_ResultT")

logger = logging.getLogger(__name__)

_RATE_LIMIT_ERROR_CODE = "42901"
_UNSUPPORTED_FUNCTION_ERROR_CODE = "40009"
_RATE_LIMIT_RESET_HEADERS = (
    "retry-after",
    "x-ratelimit-reset-requests",
    "x-ratelimit-reset-tokens",
)
_RATE_LIMIT_FALLBACK_DELAY_SECONDS = 0.25
_RATE_LIMIT_RESET_BUFFER_SECONDS = 0.05
_MAX_TRANSIENT_RETRY_DELAY_SECONDS = 8.0
_RETRY_DEADLINE_GUARD_SECONDS = 0.05


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """동일 event loop의 monotonic clock으로 표현한 요청의 절대 마감 시각."""

    deadline: float


class AsyncConcurrencyLimiter:
    """프로세스 안의 비동기 작업 수를 명시된 상한으로 제한한다."""

    def __init__(self, max_concurrency: int) -> None:
        if max_concurrency < 1:
            raise ValueError("비동기 동시 실행 상한은 1 이상이어야 합니다.")
        self.max_concurrency = max_concurrency
        self._capacity = asyncio.Semaphore(max_concurrency)

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """취소와 예외에도 반환되는 실행 슬롯 하나를 대여한다."""

        async with self._capacity:
            yield


class ModelConcurrencyMiddleware(AgentMiddleware[Any, ExecutionContext, Any]):
    """여러 Agent graph가 공유하는 HCX 모델 호출 상한."""

    def __init__(self, limiter: AsyncConcurrencyLimiter) -> None:
        self._limiter = limiter

    async def awrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """공유 슬롯에서 모델을 호출하고 일시 오류만 한 번 재시도한다."""

        async def invoke() -> Any:
            async with self._limiter.slot():
                return await handler(request)

        deadline = _request_deadline(request)
        try:
            return await _run_with_transient_retry(invoke, deadline=deadline)
        except APIStatusError as error:
            fallback_request = _calculation_tool_fallback_request(request, error=error)
            if fallback_request is None or not _retry_fits_deadline(
                delay_seconds=0,
                deadline=deadline,
            ):
                raise

            logger.warning(
                "HCX가 Calculation Tool 요청을 지원하지 않아 해당 Tool을 제외하고 "
                "한 번 재호출합니다. provider_code=%s",
                _UNSUPPORTED_FUNCTION_ERROR_CODE,
            )

            async def invoke_fallback() -> Any:
                async with self._limiter.slot():
                    return await handler(fallback_request)

            try:
                return await _run_with_transient_retry(invoke_fallback, deadline=deadline)
            except APIStatusError as fallback_error:
                raise error from fallback_error

    async def arun(
        self,
        operation: Callable[[], Awaitable[_ResultT]],
        *,
        deadline: float | None = None,
    ) -> _ResultT:
        """Tool 내부 HCX 호출에 공유 상한과 제한적 재시도를 적용한다."""

        async def invoke() -> _ResultT:
            async with self._limiter.slot():
                return await operation()

        return await _run_with_transient_retry(invoke, deadline=deadline)


async def _run_with_transient_retry[RetryResultT](
    operation: Callable[[], Awaitable[RetryResultT]],
    *,
    deadline: float | None,
) -> RetryResultT:
    """무부작용 HCX 요청의 확인된 일시 오류만 최대 한 번 재시도한다."""

    try:
        return await operation()
    except APIStatusError as error:
        retry = _transient_retry(error)
        if retry is None:
            raise
        provider_code, delay_seconds = retry
        if not _retry_fits_deadline(delay_seconds=delay_seconds, deadline=deadline):
            raise

        logger.warning(
            "HCX 일시 오류를 한 번 재시도합니다. provider_code=%s delay_seconds=%.2f",
            provider_code,
            delay_seconds,
        )
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        return await operation()


def _transient_retry(error: APIStatusError) -> tuple[str, float] | None:
    """상태·제공자 코드가 모두 일치하는 재시도 조건과 대기시간을 반환한다."""

    provider_code = _provider_error_code(error)
    if error.status_code != 429 or provider_code != _RATE_LIMIT_ERROR_CODE:
        return None

    delay_seconds = _rate_limit_retry_delay(error)
    if delay_seconds > _MAX_TRANSIENT_RETRY_DELAY_SECONDS:
        return None
    return provider_code, delay_seconds


def _calculation_tool_fallback_request(request: Any, *, error: APIStatusError) -> Any | None:
    """40009일 때 과거 이력이 참조하지 않은 Calculation Tool만 제거한다."""

    if (
        error.status_code != 400
        or _provider_error_code(error) != _UNSUPPORTED_FUNCTION_ERROR_CODE
        or "unsupported function" not in _provider_error_message(error).casefold()
    ):
        return None
    tools = getattr(request, "tools", None)
    override = getattr(request, "override", None)
    messages = getattr(request, "messages", None)
    if not isinstance(tools, list) or not callable(override) or not isinstance(messages, list):
        return None

    calculation_tool_names = {
        name
        for model_tool in tools
        if (name := _model_request_tool_name(model_tool)) is not None
        and name.startswith("calculate_")
    }
    if not calculation_tool_names or calculation_tool_names.intersection(
        _historical_tool_names(messages)
    ):
        return None

    fallback_tools = [
        model_tool
        for model_tool in tools
        if _model_request_tool_name(model_tool) not in calculation_tool_names
    ]
    return override(tools=fallback_tools, tool_choice=None)


def _model_request_tool_name(model_tool: Any) -> str | None:
    """LangChain 또는 provider 형식의 Tool 이름을 읽는다."""

    name = getattr(model_tool, "name", None)
    if isinstance(name, str):
        return name
    if not isinstance(model_tool, Mapping):
        return None
    name = model_tool.get("name")
    if isinstance(name, str):
        return name
    function = model_tool.get("function")
    if not isinstance(function, Mapping):
        return None
    function_name = function.get("name")
    return function_name if isinstance(function_name, str) else None


def _historical_tool_names(messages: list[Any]) -> set[str]:
    """provider 대화 이력이 참조하는 Tool 이름을 수집한다."""

    names: set[str] = set()
    for message in messages:
        if isinstance(message, AIMessage):
            names.update(
                call["name"] for call in message.tool_calls if isinstance(call.get("name"), str)
            )
        elif isinstance(message, ToolMessage) and isinstance(message.name, str):
            names.add(message.name)
    return names


def _provider_error_code(error: APIStatusError) -> str:
    """OpenAI 호환 예외에서 CLOVA Studio 코드만 추출한다."""

    details = _provider_error_details(error)
    code = details.get("code")
    return str(code).strip() if code is not None else ""


def _provider_error_message(error: APIStatusError) -> str:
    """OpenAI 호환 예외에서 제공자 오류 메시지를 추출한다."""

    message = _provider_error_details(error).get("message")
    return str(message).strip() if message is not None else ""


def _provider_error_details(error: APIStatusError) -> Mapping[str, Any]:
    """OpenAI 호환·CLOVA 공통 오류 본문에서 상세 객체를 읽는다."""

    body = error.body
    if not isinstance(body, Mapping):
        return {}
    details = body.get("error", body.get("status", body))
    if not isinstance(details, Mapping):
        return {}
    return details


def _rate_limit_retry_delay(error: APIStatusError) -> float:
    """응답의 reset 헤더를 우선하고 없으면 짧은 기본값을 사용한다."""

    delays = [
        parsed
        for header_name in _RATE_LIMIT_RESET_HEADERS
        if (parsed := _parse_retry_delay(error.response.headers.get(header_name))) is not None
    ]
    if not delays:
        return _RATE_LIMIT_FALLBACK_DELAY_SECONDS
    return max(delays) + _RATE_LIMIT_RESET_BUFFER_SECONDS


def _parse_retry_delay(value: str | None) -> float | None:
    """CLOVA reset 헤더의 초·밀리초 표현을 초 단위로 해석한다."""

    if value is None:
        return None
    normalized = value.strip().casefold()
    try:
        if normalized.endswith("ms"):
            delay_seconds = float(normalized[:-2]) / 1000
        elif normalized.endswith("s"):
            delay_seconds = float(normalized[:-1])
        else:
            delay_seconds = float(normalized)
    except ValueError:
        return None
    if not math.isfinite(delay_seconds) or delay_seconds < 0:
        return None
    return delay_seconds


def _request_deadline(request: Any) -> float | None:
    """LangGraph model request에 전파된 절대 마감 시각을 읽는다."""

    runtime = getattr(request, "runtime", None)
    context = getattr(runtime, "context", None)
    deadline = getattr(context, "deadline", None)
    if isinstance(deadline, (int, float)) and math.isfinite(deadline):
        return float(deadline)
    return None


def _retry_fits_deadline(*, delay_seconds: float, deadline: float | None) -> bool:
    """대기 후 재호출을 시작할 최소 시간이 남아 있는지 확인한다."""

    if deadline is None:
        return True
    remaining_seconds = deadline - asyncio.get_running_loop().time()
    return remaining_seconds > delay_seconds + _RETRY_DEADLINE_GUARD_SECONDS


def effective_deadline(*, timeout_seconds: float, parent_deadline: float | None) -> float:
    """로컬 제한과 상위 요청의 남은 예산 중 먼저 끝나는 마감 시각을 반환한다."""

    local_deadline = asyncio.get_running_loop().time() + timeout_seconds
    if parent_deadline is None:
        return local_deadline
    return min(parent_deadline, local_deadline)
