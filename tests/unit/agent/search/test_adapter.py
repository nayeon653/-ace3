"""Domain Agent용 Search Agent 실행 Adapter를 검증한다."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep
from typing import Any

from pension_agent.agent.contracts import Permission
from pension_agent.agent.search import SearchAgentAdapter, SearchResult
from pension_agent.config import SearchAgentConfig
from pension_agent.core import SearchMode


class FakeGraph:
    def __init__(self, result: dict[str, Any] | Exception, *, delay: float = 0) -> None:
        self.result = result
        self.delay = delay
        self.inputs: list[dict[str, Any]] = []

    def invoke(self, input: dict[str, Any], /) -> dict[str, Any]:
        self.inputs.append(input)
        if self.delay:
            sleep(self.delay)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _config(timeout_seconds: float = 1) -> SearchAgentConfig:
    return SearchAgentConfig(
        max_model_calls=4,
        max_tool_calls=3,
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
    try:
        result = adapter.search("이전 근거 검색", permission=Permission.POLICY)
    finally:
        adapter.close()

    assert result == expected
    assert graph.inputs[0]["permission"] is Permission.POLICY
    assert graph.inputs[0]["observed_chunks"] == []


def test_adapter_does_not_parse_free_form_answer() -> None:
    adapter = SearchAgentAdapter(FakeGraph({"messages": ["근거가 있습니다."]}), config=_config())
    try:
        result = adapter.search("근거 검색", permission=Permission.POLICY)
    finally:
        adapter.close()

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
    try:
        result = adapter.search("근거 검색", permission=Permission.POLICY)
    finally:
        adapter.close()

    assert result.execution_status == "timeout"
    assert "0.01" not in result.error


def test_adapter_waits_for_capacity_and_runs_within_the_same_deadline() -> None:
    started = Event()
    release = Event()
    calls: list[str] = []

    class BlockingGraph:
        def invoke(self, input: dict[str, Any], /) -> dict[str, Any]:
            calls.append(input["messages"][0]["content"])
            if len(calls) == 1:
                started.set()
                release.wait(timeout=1)
            return {"search_result": SearchResult(execution_status="completed", coverage="none")}

    adapter = SearchAgentAdapter(
        BlockingGraph(),
        config=_config(timeout_seconds=1),
        max_workers=1,
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(
                adapter.search,
                "첫 검색",
                permission=Permission.POLICY,
            )
            assert started.wait(timeout=1)
            second_future = executor.submit(
                adapter.search,
                "후속 검색",
                permission=Permission.POLICY,
            )
            sleep(0.01)
            assert not second_future.done()

            release.set()
            first = first_future.result(timeout=1)
            second = second_future.result(timeout=1)
    finally:
        release.set()
        adapter.close()

    assert first.execution_status == "completed"
    assert second.execution_status == "completed"
    assert calls == ["첫 검색", "후속 검색"]


def test_adapter_capacity_wait_uses_the_search_deadline() -> None:
    started = Event()
    release = Event()

    class BlockingGraph:
        def invoke(self, input: dict[str, Any], /) -> dict[str, Any]:
            del input
            started.set()
            release.wait(timeout=1)
            return {"search_result": SearchResult(execution_status="completed", coverage="none")}

    adapter = SearchAgentAdapter(
        BlockingGraph(),
        config=_config(timeout_seconds=0.01),
        max_workers=1,
    )
    try:
        first = adapter.search("첫 검색", permission=Permission.POLICY)
        assert started.is_set()

        second = adapter.search("후속 검색", permission=Permission.POLICY)
    finally:
        release.set()
        adapter.close()

    assert first.execution_status == "timeout"
    assert second.execution_status == "timeout"
    assert second.error == "Search Agent 실행 시간이 초과됐습니다."
