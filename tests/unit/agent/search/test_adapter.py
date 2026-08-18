"""Domain Agent용 Search Agent 실행 Adapter를 검증한다."""

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


def test_adapter_rejects_new_work_instead_of_queueing_behind_timed_out_call() -> None:
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
    assert second.execution_status == "failed"
    assert "처리 가능한 요청 수" in second.error
