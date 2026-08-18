"""Search Agent의 Tool 사용과 모델 호출 상한을 제어한다."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    ToolCallRequest,
    hook_config,
)
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from pension_agent.agent.contracts import validate_permission
from pension_agent.agent.search.schemas import (
    GetChunkPayload,
    NeighborChunksPayload,
    SearchChunkPayload,
    SearchHitsPayload,
)

SEARCH_LIMIT_MESSAGE = (
    "검색 호출 한도에 도달해 추가 근거를 확인하지 못했습니다. "
    "현재까지 확인된 검색 결과만 사용하거나 검색 범위를 좁혀야 합니다."
)
SEARCH_TOOL_NAMES = frozenset(
    {"search_chunks", "search_within_document", "get_neighbor_chunks", "get_chunk"}
)


class RequireSearchPermission(AgentMiddleware[Any, Any, Any]):
    """첫 모델 호출 전에 요청의 검색 문서 접근 권한을 검증한다."""

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        try:
            validate_permission(state.get("permission"))
        except (TypeError, ValueError) as exc:
            return {
                "jump_to": "end",
                "messages": [AIMessage(content=str(exc))],
            }
        return None

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


class RequireSearchToolResult(AgentMiddleware[Any, Any, Any]):
    """HCX가 자유 형식으로 종료하면 Function calling을 다시 요청한다."""

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("search_result") is not None:
            return None
        last_message = state.get("messages", [])[-1]
        if isinstance(last_message, AIMessage) and not last_message.tool_calls:
            return {
                "jump_to": "model",
                "messages": [
                    HumanMessage(
                        content=(
                            "자유 형식 답변은 사용하지 않습니다. 검색 Tool을 호출하고 "
                            "최종 검색 결과 제출 Tool로 결과를 제출하세요."
                        )
                    )
                ],
            }
        return None

    @hook_config(can_jump_to=["model"])
    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


class RecordSearchCandidates(AgentMiddleware[Any, Any, Any]):
    """정상 검색 Tool 결과의 청크를 신뢰된 상태에 누적한다."""

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        response = handler(request)
        if request.tool_call["name"] not in SEARCH_TOOL_NAMES or not isinstance(
            response, ToolMessage
        ):
            return response
        chunks = _chunks_from_tool_message(response)
        if chunks is None:
            return response
        return Command(
            update={
                "observed_chunks": chunks,
                "search_attempted": True,
                "messages": [response],
            }
        )

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        response = await handler(request)
        if request.tool_call["name"] not in SEARCH_TOOL_NAMES or not isinstance(
            response, ToolMessage
        ):
            return response
        chunks = _chunks_from_tool_message(response)
        if chunks is None:
            return response
        return Command(
            update={
                "observed_chunks": chunks,
                "search_attempted": True,
                "messages": [response],
            }
        )


class SearchToolCallLimit(ToolCallLimitMiddleware):
    """최종 제출 Tool은 제외하고 검색 Tool 호출 상한을 강제한다."""

    def __init__(self, *, max_tool_calls: int) -> None:
        super().__init__(run_limit=max_tool_calls, exit_behavior="continue")

    def _matches_tool_filter(self, tool_call: Any) -> bool:
        return tool_call["name"] in SEARCH_TOOL_NAMES

    @hook_config(can_jump_to=["end"])
    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        update = super().after_model(state, runtime)
        if update is None or "messages" not in update:
            return update
        messages = list(update["messages"])
        messages.append(
            HumanMessage(
                content=(
                    "검색 Tool 호출 상한에 도달했습니다. 더 이상 검색하지 말고 "
                    "현재까지 관찰한 ID로 최종 검색 결과 제출 Tool을 호출하세요. "
                    "관련 후보가 없으면 coverage=none과 빈 ID 목록을 제출하세요."
                )
            )
        )
        update["messages"] = messages
        return update

    @hook_config(can_jump_to=["end"])
    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


class CompleteSearchResult(AgentMiddleware[Any, Any, Any]):
    """최종 검색 결과 제출 직후 추가 모델 호출 없이 종료한다."""

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("search_result") is None:
            return None
        return {"jump_to": "end"}

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


class SearchModelCallLimit(ModelCallLimitMiddleware):
    """모델 호출 상한에서 안전한 Search Agent 응답으로 종료한다."""

    def __init__(self, *, max_model_calls: int) -> None:
        super().__init__(run_limit=max_model_calls, exit_behavior="end")
        self._max_model_calls = max_model_calls

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("run_model_call_count", 0) < self._max_model_calls:
            return None
        return {
            "jump_to": "end",
            "messages": [AIMessage(content=SEARCH_LIMIT_MESSAGE)],
        }

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


def _chunks_from_tool_message(message: ToolMessage) -> list[SearchChunkPayload] | None:
    if not isinstance(message.content, str):
        return None
    try:
        payload = json.loads(message.content)
        if message.name in {"search_chunks", "search_within_document"}:
            return [hit.chunk for hit in SearchHitsPayload.model_validate(payload).hits]
        if message.name == "get_neighbor_chunks":
            return NeighborChunksPayload.model_validate(payload).chunks
        if message.name == "get_chunk":
            chunk = GetChunkPayload.model_validate(payload).chunk
            return [chunk] if chunk is not None else []
    except (TypeError, ValueError):
        return None
    return None
