"""공유 async 실행 예산의 동시성·deadline 동작을 검증한다."""

import asyncio

import pytest

from pension_agent.agent.execution import (
    AsyncConcurrencyLimiter,
    ModelConcurrencyMiddleware,
    effective_deadline,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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
