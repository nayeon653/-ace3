"""Search Agent의 Tool 사용과 모델 호출 상한을 제어한다."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRequest,
    ModelResponse,
    hook_config,
)
from langchain.messages import AIMessage, ToolMessage

from pension_agent.agent.contracts import validate_permission

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
    """정상 검색 결과를 얻을 때까지 Tool 사용을 강제한다."""

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        return handler(self._with_required_tool(request))

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        return await handler(self._with_required_tool(request))

    @staticmethod
    def _with_required_tool(request: ModelRequest[Any]) -> ModelRequest[Any]:
        for message in request.messages:
            if not isinstance(message, ToolMessage) or message.name not in SEARCH_TOOL_NAMES:
                continue
            if not isinstance(message.content, str):
                continue
            try:
                payload = json.loads(message.content)
            except (TypeError, ValueError):
                continue
            if isinstance(payload, dict) and "error" not in payload:
                return request
        return request.override(tool_choice="required")


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
