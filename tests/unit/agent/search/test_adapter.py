"""Domain Agent용 Search Agent 실행 Adapter를 검증한다."""

import asyncio
from typing import Any
from uuid import UUID

import pytest
from langsmith import RunTree, get_current_run_tree, tracing_context

from pension_agent.agent.contracts import Permission
from pension_agent.agent.execution import ExecutionContext
from pension_agent.agent.search import SearchAgentAdapter, SearchResult
from pension_agent.config import SearchAgentConfig
from pension_agent.core import SearchMode


class FakeGraph:
    def __init__(self, result: dict[str, Any] | Exception, *, delay: float = 0) -> None:
        self.result = result
        self.delay = delay
        self.inputs: list[dict[str, Any]] = []
        self.contexts: list[ExecutionContext] = []

    async def ainvoke(
        self,
        input: dict[str, Any],
        /,
        *,
        context: ExecutionContext,
    ) -> dict[str, Any]:
        self.inputs.append(input)
        self.contexts.append(context)
        if self.delay:
            await asyncio.sleep(self.delay)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _config(timeout_seconds: float = 1, *, max_concurrency: int = 4) -> SearchAgentConfig:
    return SearchAgentConfig(
        max_model_calls=4,
        max_tool_calls=3,
        max_concurrency=max_concurrency,
        timeout_seconds=timeout_seconds,
        default_search_mode=SearchMode.HYBRID,
        default_result_limit=10,
        default_neighbor_before=1,
        default_neighbor_after=1,
    )


def test_adapter_returns_only_structured_search_result() -> None:
    expected = SearchResult(execution_status="completed", coverage="none")
    graph = FakeGraph({"search_result": expected, "messages": ["free-form ignored"]})
    adapter = SearchAgentAdapter(graph, config=_config())

    result = asyncio.run(adapter.search("이전 근거 검색", permission=Permission.POLICY))

    assert result == expected
    assert graph.inputs[0]["permission"] is Permission.POLICY
    assert graph.inputs[0]["observed_chunks"] == []


def test_adapter_does_not_parse_free_form_answer() -> None:
    adapter = SearchAgentAdapter(FakeGraph({"messages": ["근거가 있습니다."]}), config=_config())

    result = asyncio.run(adapter.search("근거 검색", permission=Permission.POLICY))

    assert result.execution_status == "failed"
    assert result.selected_chunks == []


def test_adapter_timeout_is_sanitized() -> None:
    adapter = SearchAgentAdapter(
        FakeGraph(
            {"search_result": SearchResult(execution_status="completed", coverage="none")},
            delay=0.1,
        ),
        config=_config(timeout_seconds=0.01),
    )

    result = asyncio.run(adapter.search("근거 검색", permission=Permission.POLICY))

    assert result.execution_status == "timeout"
    assert "0.01" not in result.error


def test_adapter_waits_for_capacity_within_one_absolute_deadline() -> None:
    calls: list[str] = []
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    class SequencedGraph:
        async def ainvoke(
            self,
            input: dict[str, Any],
            /,
            *,
            context: ExecutionContext,
        ) -> dict[str, Any]:
            del context
            calls.append(input["messages"][0]["content"])
            first_started.set()
            await release_first.wait()
            return {"search_result": SearchResult(execution_status="completed", coverage="none")}

    async def scenario() -> tuple[SearchResult, SearchResult]:
        adapter = SearchAgentAdapter(
            SequencedGraph(),
            config=_config(timeout_seconds=1, max_concurrency=1),
        )
        first_task = asyncio.create_task(adapter.search("첫 검색", permission=Permission.POLICY))
        await first_started.wait()
        second = await adapter.search(
            "후속 검색",
            permission=Permission.POLICY,
            deadline=asyncio.get_running_loop().time() + 0.01,
        )
        release_first.set()
        return await first_task, second

    first, second = asyncio.run(scenario())

    assert first.execution_status == "completed"
    assert second.execution_status == "timeout"
    assert calls == ["첫 검색"]


def test_adapter_uses_parent_deadline_and_passes_effective_context() -> None:
    graph = FakeGraph(
        {"search_result": SearchResult(execution_status="completed", coverage="none")},
        delay=0.03,
    )

    async def scenario() -> tuple[SearchResult, float, float]:
        loop = asyncio.get_running_loop()
        parent_deadline = loop.time() + 0.01
        adapter = SearchAgentAdapter(graph, config=_config(timeout_seconds=1))
        result = await adapter.search(
            "근거 검색",
            permission=Permission.POLICY,
            deadline=parent_deadline,
        )
        return result, parent_deadline, graph.contexts[0].deadline

    result, parent_deadline, nested_deadline = asyncio.run(scenario())

    assert result.execution_status == "timeout"
    assert nested_deadline == parent_deadline


def test_adapter_does_not_start_graph_after_parent_deadline() -> None:
    graph = FakeGraph(
        {"search_result": SearchResult(execution_status="completed", coverage="none")}
    )

    async def scenario() -> SearchResult:
        adapter = SearchAgentAdapter(graph, config=_config(timeout_seconds=1))
        return await adapter.search(
            "근거 검색",
            permission=Permission.POLICY,
            deadline=asyncio.get_running_loop().time() - 1,
        )

    result = asyncio.run(scenario())

    assert result.execution_status == "timeout"
    assert graph.inputs == []


def test_adapter_cancellation_returns_capacity_without_leak() -> None:
    async def scenario() -> tuple[SearchResult, int]:
        started = asyncio.Event()
        calls = 0

        class CancellableGraph:
            async def ainvoke(
                self,
                input: dict[str, Any],
                /,
                *,
                context: ExecutionContext,
            ) -> dict[str, Any]:
                nonlocal calls
                del input, context
                calls += 1
                if calls == 1:
                    started.set()
                    await asyncio.Event().wait()
                return {
                    "search_result": SearchResult(execution_status="completed", coverage="none")
                }

        adapter = SearchAgentAdapter(
            CancellableGraph(),
            config=_config(max_concurrency=1),
        )
        first_task = asyncio.create_task(
            adapter.search("취소할 검색", permission=Permission.POLICY)
        )
        await started.wait()
        first_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first_task
        result = await adapter.search("후속 검색", permission=Permission.POLICY)
        return result, calls

    result, calls = asyncio.run(scenario())

    assert result.execution_status == "completed"
    assert calls == 2


def test_adapter_preserves_tracing_context_across_async_execution() -> None:
    parents = [
        RunTree(
            name=f"request-{index}",
            inputs={},
            project_name="unit-test",
            ls_client=object(),
        )
        for index in range(2)
    ]
    observed_parent_ids: dict[str, UUID | None] = {}

    async def scenario() -> None:
        started = 0
        both_started = asyncio.Event()

        class ContextRecordingGraph:
            async def ainvoke(
                self,
                input: dict[str, Any],
                /,
                *,
                context: ExecutionContext,
            ) -> dict[str, Any]:
                nonlocal started
                del context
                started += 1
                if started == 2:
                    both_started.set()
                await both_started.wait()
                objective = str(input["messages"][0]["content"])
                current_run = get_current_run_tree()
                observed_parent_ids[objective] = current_run.id if current_run is not None else None
                return {
                    "search_result": SearchResult(
                        execution_status="completed",
                        coverage="none",
                    )
                }

        adapter = SearchAgentAdapter(
            ContextRecordingGraph(),
            config=_config(max_concurrency=2),
        )
        tasks = []
        for index, parent in enumerate(parents):
            with tracing_context(parent=parent, enabled=False):
                tasks.append(
                    asyncio.create_task(
                        adapter.search(f"근거 검색 {index}", permission=Permission.POLICY)
                    )
                )
        results = await asyncio.gather(*tasks)
        assert all(result.execution_status == "completed" for result in results)

    asyncio.run(scenario())

    assert observed_parent_ids == {
        f"근거 검색 {index}": parent.id for index, parent in enumerate(parents)
    }
