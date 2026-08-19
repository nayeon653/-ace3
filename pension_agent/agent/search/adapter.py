"""Domain Agent와 Search Agent LangGraph를 분리하는 실행 Adapter."""

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Protocol

from langchain.messages import AIMessage, ToolMessage
from pydantic import TypeAdapter, ValidationError

from pension_agent.agent.contracts import Permission
from pension_agent.agent.execution import ExecutionContext, effective_deadline
from pension_agent.agent.search.schemas import SearchResult
from pension_agent.config import DEFAULT_SEARCH_AGENT_CONFIG, SearchAgentConfig

_SEARCH_RESULT_ADAPTER = TypeAdapter(SearchResult)
logger = logging.getLogger(__name__)
_SEARCH_TOOL_NAMES = frozenset(
    {"search_chunks", "search_within_document", "get_neighbor_chunks", "get_chunk"}
)


class SearchGraph(Protocol):
    """Adapter가 사용하는 최소 Search Agent 실행 계약."""

    async def ainvoke(
        self,
        input: dict[str, Any],
        /,
        *,
        context: ExecutionContext,
    ) -> Mapping[str, Any]:
        """초기 상태로 Search Agent를 실행한다."""


@dataclass(slots=True)
class SearchAgentAdapter:
    """하나의 구체적인 검색 목표를 검증된 SearchResult로 변환한다."""

    graph: SearchGraph
    config: SearchAgentConfig = DEFAULT_SEARCH_AGENT_CONFIG
    max_concurrency: int | None = None
    _capacity: asyncio.Semaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        concurrency = (
            self.config.max_concurrency if self.max_concurrency is None else self.max_concurrency
        )
        if concurrency < 1:
            raise ValueError("Search Agent 동시 실행 상한은 1 이상이어야 합니다.")
        self.max_concurrency = concurrency
        self._capacity = asyncio.Semaphore(concurrency)

    async def search(
        self,
        objective: str,
        *,
        permission: Permission,
        deadline: float | None = None,
    ) -> SearchResult:
        """검색 목표만 Agent에 전달하고 자유 형식 답변은 사용하지 않는다."""

        normalized_objective = objective.strip()
        if not normalized_objective:
            return _failed_result("검색 목표는 비어 있을 수 없습니다.")

        started_at = monotonic()
        search_deadline = effective_deadline(
            timeout_seconds=self.config.timeout_seconds,
            parent_deadline=deadline,
        )
        if search_deadline <= asyncio.get_running_loop().time():
            result = _timeout_result()
            _log_search_run(
                permission=permission,
                state=None,
                result=result,
                elapsed_seconds=monotonic() - started_at,
            )
            return result

        try:
            async with asyncio.timeout_at(search_deadline):
                await self._capacity.acquire()
                try:
                    state = await self.graph.ainvoke(
                        {
                            "messages": [{"role": "user", "content": normalized_objective}],
                            "permission": permission,
                            "observed_chunks": [],
                            "search_attempted": False,
                        },
                        context=ExecutionContext(deadline=search_deadline),
                    )
                finally:
                    self._capacity.release()
        except TimeoutError:
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
