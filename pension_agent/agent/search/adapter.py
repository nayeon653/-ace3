"""Domain Agent와 Search Agent LangGraph를 분리하는 실행 Adapter."""

import logging
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from threading import BoundedSemaphore
from time import monotonic
from typing import Any, Protocol

from langchain.messages import AIMessage, ToolMessage
from pydantic import TypeAdapter, ValidationError

from pension_agent.agent.contracts import Permission
from pension_agent.agent.search.schemas import SearchResult
from pension_agent.config import DEFAULT_SEARCH_AGENT_CONFIG, SearchAgentConfig

_SEARCH_RESULT_ADAPTER = TypeAdapter(SearchResult)
logger = logging.getLogger(__name__)
_SEARCH_TOOL_NAMES = frozenset(
    {"search_chunks", "search_within_document", "get_neighbor_chunks", "get_chunk"}
)


class SearchGraph(Protocol):
    """Adapter가 사용하는 최소 Search Agent 실행 계약."""

    def invoke(self, input: dict[str, Any], /) -> Mapping[str, Any]:
        """초기 상태로 Search Agent를 실행한다."""


@dataclass(slots=True)
class SearchAgentAdapter:
    """하나의 구체적인 검색 목표를 검증된 SearchResult로 변환한다."""

    graph: SearchGraph
    config: SearchAgentConfig = DEFAULT_SEARCH_AGENT_CONFIG
    max_workers: int = 4
    _executor: ThreadPoolExecutor = field(init=False, repr=False)
    _capacity: BoundedSemaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("Search Agent worker 수는 1 이상이어야 합니다.")
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="search-agent",
        )
        self._capacity = BoundedSemaphore(self.max_workers)

    def search(self, objective: str, *, permission: Permission) -> SearchResult:
        """검색 목표만 Agent에 전달하고 자유 형식 답변은 사용하지 않는다."""

        normalized_objective = objective.strip()
        if not normalized_objective:
            return _failed_result("검색 목표는 비어 있을 수 없습니다.")

        started_at = monotonic()
        deadline = started_at + self.config.timeout_seconds
        if not self._capacity.acquire(timeout=self.config.timeout_seconds):
            result = _timeout_result()
            _log_search_run(
                permission=permission,
                state=None,
                result=result,
                elapsed_seconds=monotonic() - started_at,
            )
            return result

        remaining_seconds = deadline - monotonic()
        if remaining_seconds <= 0:
            self._capacity.release()
            result = _timeout_result()
            _log_search_run(
                permission=permission,
                state=None,
                result=result,
                elapsed_seconds=monotonic() - started_at,
            )
            return result

        try:
            future: Future[Mapping[str, Any]] = self._executor.submit(
                self.graph.invoke,
                {
                    "messages": [{"role": "user", "content": normalized_objective}],
                    "permission": permission,
                    "observed_chunks": [],
                    "search_attempted": False,
                },
            )
        except RuntimeError:
            self._capacity.release()
            return _failed_result("Search Agent 실행기를 사용할 수 없습니다.")
        future.add_done_callback(lambda completed: self._capacity.release())
        try:
            state = future.result(timeout=remaining_seconds)
        except TimeoutError:
            future.cancel()
            result = _timeout_result()
            _log_search_run(
                permission=permission,
                state=None,
                result=result,
                elapsed_seconds=monotonic() - started_at,
            )
            return result
        except Exception:  # noqa: BLE001
            result = _failed_result("Search Agent 실행에 실패했습니다.")
            _log_search_run(
                permission=permission,
                state=None,
                result=result,
                elapsed_seconds=monotonic() - started_at,
            )
            return result

        try:
            result = _SEARCH_RESULT_ADAPTER.validate_python(state.get("search_result"))
        except (AttributeError, TypeError, ValueError, ValidationError):
            result = _failed_result("Search Agent가 최종 검색 결과를 제출하지 못했습니다.")
        _log_search_run(
            permission=permission,
            state=state,
            result=result,
            elapsed_seconds=monotonic() - started_at,
        )
        return result

    def close(self) -> None:
        """프로세스 종료 시 실행 worker를 정리한다."""

        self._executor.shutdown(wait=False, cancel_futures=True)


def _failed_result(message: str) -> SearchResult:
    return SearchResult(execution_status="failed", error=message)


def _timeout_result() -> SearchResult:
    return SearchResult(
        execution_status="timeout",
        error="Search Agent 실행 시간이 초과됐습니다.",
    )


def _log_search_run(
    *,
    permission: Permission,
    state: Mapping[str, Any] | None,
    result: SearchResult,
    elapsed_seconds: float,
) -> None:
    messages = state.get("messages", []) if state is not None else []
    queries = [
        str(call.get("args", {}).get("text", ""))
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
        if call.get("name") in {"search_chunks", "search_within_document"}
    ]
    tool_calls = sum(
        isinstance(message, ToolMessage)
        and message.name in _SEARCH_TOOL_NAMES
        and message.status != "error"
        for message in messages
    )
    model_calls = sum(isinstance(message, AIMessage) for message in messages)
    logger.info(
        "Search Agent 실행: permission=%s status=%s coverage=%s queries=%s "
        "selected_chunk_ids=%s model_calls=%s tool_calls=%s elapsed_ms=%d error=%s",
        permission.value,
        result.execution_status,
        result.coverage,
        queries,
        [chunk.chunk_id for chunk in result.selected_chunks],
        model_calls,
        tool_calls,
        round(elapsed_seconds * 1000),
        result.error,
    )
