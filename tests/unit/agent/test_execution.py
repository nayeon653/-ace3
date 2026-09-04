"""공유 async 실행 예산의 동시성·deadline 동작을 검증한다."""

import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from langchain.agents.middleware import ModelRequest
from langchain.messages import AIMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from openai import APIStatusError, BadRequestError, RateLimitError

from pension_agent.agent import execution
from pension_agent.agent.execution import (
    AsyncConcurrencyLimiter,
    ExecutionContext,
    ModelConcurrencyMiddleware,
    effective_deadline,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _provider_error(
    *,
    status_code: int,
    provider_code: str,
    provider_message: str,
    headers: dict[str, str] | None = None,
) -> APIStatusError:
    request = httpx.Request("POST", "https://clova.invalid/v1/chat/completions")
    response = httpx.Response(status_code, request=request, headers=headers)
    body = {
        "error": {
            "code": provider_code,
            "message": provider_message,
        }
    }
    error_type: type[APIStatusError]
    if status_code == 400:
        error_type = BadRequestError
    elif status_code == 429:
        error_type = RateLimitError
    else:
        error_type = APIStatusError
    return error_type("CLOVA Studio 요청이 실패했습니다.", response=response, body=body)


def _model_request_with_deadline(deadline: float) -> SimpleNamespace:
    return SimpleNamespace(runtime=SimpleNamespace(context=ExecutionContext(deadline=deadline)))


def _tool_schema(name: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"{name} 설명",
            "parameters": {"type": "object", "properties": {}},
        },
    }


@pytest.mark.anyio
async def test_concurrency_limiter_waits_and_releases_after_cancellation() -> None:
    limiter = AsyncConcurrencyLimiter(1)
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_started = asyncio.Event()

    async def first() -> None:
        async with limiter.slot():
            first_started.set()
            await release_first.wait()

    async def second() -> None:
        async with limiter.slot():
            second_started.set()

    first_task = asyncio.create_task(first())
    await first_started.wait()
    second_task = asyncio.create_task(second())
    await asyncio.sleep(0)
    assert not second_started.is_set()

    first_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first_task
    await second_task

    assert second_started.is_set()


@pytest.mark.anyio
async def test_cancelling_capacity_waiter_does_not_consume_next_slot() -> None:
    limiter = AsyncConcurrencyLimiter(1)
    holder_started = asyncio.Event()
    release_holder = asyncio.Event()

    async def holder() -> None:
        async with limiter.slot():
            holder_started.set()
            await release_holder.wait()

    async def wait_for_slot() -> None:
        async with limiter.slot():
            pass

    holder_task = asyncio.create_task(holder())
    await holder_started.wait()
    cancelled_waiter = asyncio.create_task(wait_for_slot())
    await asyncio.sleep(0)
    cancelled_waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_waiter

    release_holder.set()
    await holder_task
    await asyncio.wait_for(wait_for_slot(), timeout=0.1)


@pytest.mark.anyio
async def test_effective_deadline_never_extends_parent_budget() -> None:
    loop = asyncio.get_running_loop()
    parent_deadline = loop.time() + 0.1

    inherited = effective_deadline(timeout_seconds=10, parent_deadline=parent_deadline)
    local = effective_deadline(timeout_seconds=10, parent_deadline=None)

    assert inherited == parent_deadline
    assert local > parent_deadline


@pytest.mark.anyio
async def test_model_middleware_limits_hcx_calls_shared_by_multiple_graphs() -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(2))
    active = 0
    max_active = 0

    async def handler(request: object) -> object:
        nonlocal active, max_active
        del request
        active += 1
        max_active = max(max_active, active)
        try:
            await asyncio.sleep(0.01)
            return object()
        finally:
            active -= 1

    await asyncio.gather(*(middleware.awrap_model_call(object(), handler) for _ in range(5)))

    assert max_active == 2


@pytest.mark.anyio
async def test_model_middleware_shares_limit_with_tool_internal_hcx_calls() -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    graph_started = asyncio.Event()
    release_graph = asyncio.Event()
    tool_started = asyncio.Event()

    async def graph_handler(request: object) -> object:
        del request
        graph_started.set()
        await release_graph.wait()
        return object()

    async def tool_operation() -> object:
        tool_started.set()
        return object()

    graph_call = asyncio.create_task(middleware.awrap_model_call(object(), graph_handler))
    await graph_started.wait()
    tool_call = asyncio.create_task(middleware.arun(tool_operation))
    await asyncio.sleep(0)
    assert not tool_started.is_set()

    release_graph.set()
    await graph_call
    await tool_call

    assert tool_started.is_set()


@pytest.mark.anyio
async def test_model_middleware_does_not_retry_40009_without_calculation_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    retryable_error = _provider_error(
        status_code=400,
        provider_code="40009",
        provider_message="Unsupported function",
    )
    request = ModelRequest(
        model=FakeMessagesListChatModel(responses=[]),
        messages=[],
        tools=[_tool_schema("search_documents"), _tool_schema("submit_domain_result")],
        tool_choice="submit_domain_result",
    )
    calls: list[ModelRequest[Any]] = []
    sleeps: list[float] = []

    async def fake_sleep(delay_seconds: float) -> None:
        sleeps.append(delay_seconds)

    async def handler(received_request: ModelRequest[Any]) -> object:
        calls.append(received_request)
        raise retryable_error

    monkeypatch.setattr(execution.asyncio, "sleep", fake_sleep)

    with pytest.raises(APIStatusError) as raised:
        await middleware.awrap_model_call(request, handler)

    assert raised.value is retryable_error
    assert calls == [request]
    assert calls[0].tool_choice == "submit_domain_result"
    assert sleeps == []


@pytest.mark.anyio
async def test_model_middleware_retries_40009_after_removing_calculation_tools() -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    provider_error = _provider_error(
        status_code=400,
        provider_code="40009",
        provider_message="Unsupported function",
    )
    request = ModelRequest(
        model=FakeMessagesListChatModel(responses=[]),
        messages=[],
        tools=[
            _tool_schema("search_documents"),
            _tool_schema("calculate_tax"),
            _tool_schema("submit_domain_result"),
        ],
        tool_choice="calculate_tax",
    )
    received: list[ModelRequest[Any]] = []

    async def handler(model_request: ModelRequest[Any]) -> str:
        received.append(model_request)
        if len(received) == 1:
            raise provider_error
        return "LLM fallback"

    result = await middleware.awrap_model_call(request, handler)

    assert result == "LLM fallback"
    assert received[0] is request
    assert received[1] is not request
    assert [tool["function"]["name"] for tool in received[0].tools] == [
        "search_documents",
        "calculate_tax",
        "submit_domain_result",
    ]
    assert received[1].tool_choice is None
    assert [tool["function"]["name"] for tool in received[1].tools] == [
        "search_documents",
        "submit_domain_result",
    ]


@pytest.mark.anyio
async def test_model_middleware_does_not_remove_calculator_referenced_by_history() -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    provider_error = _provider_error(
        status_code=400,
        provider_code="40009",
        provider_message="Unsupported function",
    )
    request = ModelRequest(
        model=FakeMessagesListChatModel(responses=[]),
        messages=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_tax",
                        "args": {},
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="계산 결과",
                tool_call_id="calculation-call",
                name="calculate_tax",
            ),
        ],
        tools=[_tool_schema("calculate_tax"), _tool_schema("submit_domain_result")],
    )
    call_count = 0

    async def handler(_: ModelRequest[Any]) -> str:
        nonlocal call_count
        call_count += 1
        raise provider_error

    with pytest.raises(APIStatusError) as raised:
        await middleware.awrap_model_call(request, handler)

    assert raised.value is provider_error
    assert call_count == 1
    assert [tool["function"]["name"] for tool in request.tools] == [
        "calculate_tax",
        "submit_domain_result",
    ]


@pytest.mark.anyio
async def test_model_middleware_does_not_treat_other_40009_as_tool_fallback() -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    provider_error = _provider_error(
        status_code=400,
        provider_code="40009",
        provider_message="Unsupported input format",
    )
    request = ModelRequest(
        model=FakeMessagesListChatModel(responses=[]),
        messages=[],
        tools=[_tool_schema("calculate_tax"), _tool_schema("submit_domain_result")],
    )
    call_count = 0

    async def handler(_: ModelRequest[Any]) -> str:
        nonlocal call_count
        call_count += 1
        raise provider_error

    with pytest.raises(APIStatusError) as raised:
        await middleware.awrap_model_call(request, handler)

    assert raised.value is provider_error
    assert call_count == 1


@pytest.mark.anyio
async def test_model_middleware_propagates_original_error_when_tool_fallback_fails() -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    original_error = _provider_error(
        status_code=400,
        provider_code="40009",
        provider_message="Unsupported function",
    )
    fallback_error = _provider_error(
        status_code=400,
        provider_code="40009",
        provider_message="Unsupported function after fallback",
    )
    request = ModelRequest(
        model=FakeMessagesListChatModel(responses=[]),
        messages=[],
        tools=[_tool_schema("calculate_tax"), _tool_schema("submit_domain_result")],
    )
    call_count = 0

    async def handler(_: ModelRequest[Any]) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise original_error
        raise fallback_error

    with pytest.raises(APIStatusError) as raised:
        await middleware.awrap_model_call(request, handler)

    assert raised.value is original_error
    assert call_count == 2


@pytest.mark.anyio
async def test_model_middleware_uses_short_rate_limit_reset_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    retryable_error = _provider_error(
        status_code=429,
        provider_code="42901",
        provider_message="Too many requests - rate exceeded",
        headers={
            "x-ratelimit-reset-requests": "2.5s",
            "x-ratelimit-reset-tokens": "3s",
        },
    )
    request = _model_request_with_deadline(asyncio.get_running_loop().time() + 10)
    call_count = 0
    sleeps: list[float] = []

    async def fake_sleep(delay_seconds: float) -> None:
        sleeps.append(delay_seconds)

    async def handler(_: Any) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise retryable_error
        return "recovered"

    monkeypatch.setattr(execution.asyncio, "sleep", fake_sleep)

    result = await middleware.awrap_model_call(request, handler)

    assert result == "recovered"
    assert call_count == 2
    assert sleeps == [pytest.approx(3.05)]


@pytest.mark.anyio
async def test_model_middleware_retries_observed_six_second_token_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    retryable_error = _provider_error(
        status_code=429,
        provider_code="42901",
        provider_message="Too many requests - rate exceeded",
        headers={
            "x-ratelimit-reset-requests": "6s",
            "x-ratelimit-reset-tokens": "6s",
        },
    )
    request = _model_request_with_deadline(asyncio.get_running_loop().time() + 10)
    call_count = 0
    sleeps: list[float] = []

    async def fake_sleep(delay_seconds: float) -> None:
        sleeps.append(delay_seconds)

    async def handler(_: Any) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise retryable_error
        return "recovered"

    monkeypatch.setattr(execution.asyncio, "sleep", fake_sleep)

    result = await middleware.awrap_model_call(request, handler)

    assert result == "recovered"
    assert call_count == 2
    assert sleeps == [pytest.approx(6.05)]


@pytest.mark.anyio
async def test_model_middleware_never_retries_more_than_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    retryable_error = _provider_error(
        status_code=429,
        provider_code="42901",
        provider_message="Too many requests - rate exceeded",
    )
    request = _model_request_with_deadline(asyncio.get_running_loop().time() + 10)
    call_count = 0

    async def fake_sleep(_: float) -> None:
        pass

    async def handler(_: Any) -> object:
        nonlocal call_count
        call_count += 1
        raise retryable_error

    monkeypatch.setattr(execution.asyncio, "sleep", fake_sleep)

    with pytest.raises(APIStatusError) as raised:
        await middleware.awrap_model_call(request, handler)

    assert raised.value is retryable_error
    assert call_count == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status_code", "provider_code", "provider_message"),
    [
        (400, "40008", "Unsupported function"),
        (400, "40009", "Invalid request"),
        (401, "40009", "Unsupported function"),
        (429, "42902", "Too many requests - overloaded"),
    ],
)
async def test_model_middleware_does_not_retry_other_provider_errors(
    status_code: int,
    provider_code: str,
    provider_message: str,
) -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    provider_error = _provider_error(
        status_code=status_code,
        provider_code=provider_code,
        provider_message=provider_message,
    )
    call_count = 0

    async def handler(_: Any) -> object:
        nonlocal call_count
        call_count += 1
        raise provider_error

    with pytest.raises(APIStatusError) as raised:
        await middleware.awrap_model_call(object(), handler)

    assert raised.value is provider_error
    assert call_count == 1


@pytest.mark.anyio
async def test_model_middleware_does_not_retry_non_provider_exception() -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    expected_error = RuntimeError("모델 응답 파싱 실패")
    call_count = 0

    async def handler(_: Any) -> object:
        nonlocal call_count
        call_count += 1
        raise expected_error

    with pytest.raises(RuntimeError) as raised:
        await middleware.awrap_model_call(object(), handler)

    assert raised.value is expected_error
    assert call_count == 1


@pytest.mark.anyio
async def test_model_middleware_skips_retry_when_reset_exceeds_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    retryable_error = _provider_error(
        status_code=429,
        provider_code="42901",
        provider_message="Too many requests - rate exceeded",
        headers={"x-ratelimit-reset-requests": "3s"},
    )
    request = _model_request_with_deadline(asyncio.get_running_loop().time() + 3)
    call_count = 0

    async def forbidden_sleep(_: float) -> None:
        pytest.fail("deadline을 넘는 재시도를 기다리면 안 됩니다.")

    async def handler(_: Any) -> object:
        nonlocal call_count
        call_count += 1
        raise retryable_error

    monkeypatch.setattr(execution.asyncio, "sleep", forbidden_sleep)

    with pytest.raises(APIStatusError) as raised:
        await middleware.awrap_model_call(request, handler)

    assert raised.value is retryable_error
    assert call_count == 1


@pytest.mark.anyio
async def test_model_middleware_skips_long_rate_limit_reset() -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    retryable_error = _provider_error(
        status_code=429,
        provider_code="42901",
        provider_message="Too many requests - rate exceeded",
        headers={"x-ratelimit-reset-requests": "9s"},
    )
    call_count = 0

    async def handler(_: Any) -> object:
        nonlocal call_count
        call_count += 1
        raise retryable_error

    with pytest.raises(APIStatusError) as raised:
        await middleware.awrap_model_call(object(), handler)

    assert raised.value is retryable_error
    assert call_count == 1


@pytest.mark.anyio
async def test_model_middleware_arun_applies_deadline_aware_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1))
    retryable_error = _provider_error(
        status_code=429,
        provider_code="42901",
        provider_message="Too many requests - rate exceeded",
    )
    call_count = 0

    async def fake_sleep(_: float) -> None:
        pass

    async def operation() -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise retryable_error
        return "recovered"

    monkeypatch.setattr(execution.asyncio, "sleep", fake_sleep)

    result = await middleware.arun(
        operation,
        deadline=asyncio.get_running_loop().time() + 10,
    )

    assert result == "recovered"
    assert call_count == 2
