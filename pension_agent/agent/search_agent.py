"""검색 기능을 Tool로 사용하는 ReAct Search Agent."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from importlib import resources
from typing import Annotated, Any, Protocol

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRequest,
    ModelResponse,
    ToolCallLimitMiddleware,
    hook_config,
)
from langchain.messages import AIMessage, ToolMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool
from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from pension_agent.config import DEFAULT_SEARCH_AGENT_CONFIG, SearchAgentConfig
from pension_agent.core import (
    DocumentType,
    NeighborRequest,
    RetrievalError,
    RetrievedChunk,
    SearchFilters,
    SearchHit,
    SearchMode,
    SearchQuery,
)

_MAX_RESULT_LIMIT = 100
_SEARCH_LIMIT_MESSAGE = (
    "검색 호출 한도에 도달해 추가 근거를 확인하지 못했습니다. "
    "현재까지 확인된 검색 결과만 사용하거나 검색 범위를 좁혀야 합니다."
)
_SEARCH_TOOL_NAMES = frozenset(
    {"search_chunks", "search_within_document", "get_neighbor_chunks", "get_chunk"}
)


class QueryEmbedder(Protocol):
    """검색문 하나를 dense vector로 변환하는 제공자 경계."""

    def embed_query(self, text: str) -> list[float]:
        """검색문에 대응하는 dense vector를 반환한다."""


class SearchBackend(Protocol):
    """검색 Tool이 의존하는 도메인 중립 검색 기능."""

    def search_chunks(
        self,
        query: SearchQuery,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        """전체 corpus를 검색한다."""

    def search_within_document(
        self,
        query: SearchQuery,
        *,
        source_file_name: str,
        limit: int = 10,
    ) -> list[SearchHit]:
        """원본 문서 하나에서 검색한다."""

    def get_neighbor_chunks(self, request: NeighborRequest) -> list[RetrievedChunk]:
        """기준 청크 주변의 문맥을 조회한다."""

    def get_chunk(self, chunk_id: str) -> RetrievedChunk | None:
        """청크 ID로 근거 하나를 조회한다."""


class QueryEmbeddingError(RuntimeError):
    """검색문 dense embedding을 안전하게 생성하지 못한 경우."""


class SearchToolInputError(ValueError):
    """모델이 만든 검색 Tool 인자가 공개 입력 계약을 위반한 경우."""


class _RequireSearchToolResult(AgentMiddleware[Any, Any, Any]):
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
            if not isinstance(message, ToolMessage) or message.name not in _SEARCH_TOOL_NAMES:
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


class _SearchModelCallLimit(ModelCallLimitMiddleware):
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
            "messages": [AIMessage(content=_SEARCH_LIMIT_MESSAGE)],
        }

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


class _SearchOperations:
    """Search Agent Tool의 결정론적 실행부."""

    def __init__(self, *, embedder: QueryEmbedder, backend: SearchBackend) -> None:
        self._embedder = embedder
        self._backend = backend

    def search_chunks(
        self,
        text: str,
        *,
        filters: SearchFilters | None = None,
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 10,
    ) -> list[SearchHit]:
        _validate_limit(limit)
        return self._backend.search_chunks(
            self._build_query(text, mode=mode),
            filters=filters,
            limit=limit,
        )

    def search_within_document(
        self,
        text: str,
        *,
        source_file_name: str,
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 10,
    ) -> list[SearchHit]:
        _validate_limit(limit)
        source_file_name = source_file_name.strip()
        if not source_file_name:
            raise SearchToolInputError("원본 파일명 필터는 비어 있을 수 없습니다.")

        return self._backend.search_within_document(
            self._build_query(text, mode=mode),
            source_file_name=source_file_name,
            limit=limit,
        )

    def get_neighbor_chunks(self, request: NeighborRequest) -> list[RetrievedChunk]:
        return self._backend.get_neighbor_chunks(request)

    def get_chunk(self, chunk_id: str) -> RetrievedChunk | None:
        return self._backend.get_chunk(chunk_id)

    def _build_query(self, text: str, *, mode: SearchMode) -> SearchQuery:
        normalized_text = text.strip()
        if not normalized_text:
            raise SearchToolInputError("검색문은 비어 있을 수 없습니다.")

        if mode is SearchMode.SPARSE:
            return SearchQuery(text=normalized_text, mode=mode)

        provider_failed = False
        try:
            raw_dense = self._embedder.embed_query(normalized_text)
        # 외부 임베딩 구현마다 예외 계층이 달라 Provider 경계에서 한 번에 정제한다.
        except Exception:  # noqa: BLE001
            provider_failed = True

        if provider_failed:
            raise QueryEmbeddingError("검색문 임베딩 생성에 실패했습니다.")

        invalid_result = False
        try:
            query = SearchQuery(text=normalized_text, dense=tuple(raw_dense), mode=mode)
        # 지연 평가되는 Provider 반환값의 순회·변환 예외도 원문을 노출하지 않는다.
        except Exception:  # noqa: BLE001
            invalid_result = True

        if invalid_result:
            raise QueryEmbeddingError("검색문 임베딩 결과가 올바르지 않습니다.")
        return query


def load_search_agent_prompt() -> str:
    """패키지 리소스에서 Search Agent 프롬프트를 읽는다."""

    return (
        resources.files("pension_agent.prompts")
        .joinpath("search-agent.md")
        .read_text(encoding="utf-8")
    )


def create_search_tools(
    *,
    embedder: QueryEmbedder,
    backend: SearchBackend,
    config: SearchAgentConfig = DEFAULT_SEARCH_AGENT_CONFIG,
) -> tuple[BaseTool, ...]:
    """Search Agent가 선택해서 호출할 검색 Tool을 만든다."""

    operations = _SearchOperations(embedder=embedder, backend=backend)

    @tool(
        "search_chunks",
        description="전체 제공 문서에서 검색어와 관련된 근거 청크를 찾는다.",
    )
    def search_chunks(
        text: Annotated[str, Field(min_length=1, description="근거를 찾을 검색어")],
        mode: Annotated[
            SearchMode,
            Field(description="dense, sparse, hybrid 중 사용할 검색 방식"),
        ] = config.default_search_mode,
        document_type: Annotated[
            DocumentType | None,
            Field(description="검색 범위를 제한할 문서 유형"),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=_MAX_RESULT_LIMIT, strict=True, description="반환할 청크 수"),
        ] = config.default_result_limit,
    ) -> str:
        filters = SearchFilters(document_type=document_type) if document_type is not None else None
        return _tool_payload(
            lambda: {
                "hits": [
                    _search_hit_payload(hit)
                    for hit in operations.search_chunks(
                        text,
                        filters=filters,
                        mode=mode,
                        limit=limit,
                    )
                ]
            }
        )

    @tool(
        "search_within_document",
        description="지정한 원본 문서 하나에서 검색어와 관련된 근거 청크를 찾는다.",
    )
    def search_within_document(
        text: Annotated[str, Field(min_length=1, description="근거를 찾을 검색어")],
        source_file_name: Annotated[
            str,
            Field(min_length=1, description="검색 범위를 제한할 원본 파일명"),
        ],
        mode: Annotated[
            SearchMode,
            Field(description="dense, sparse, hybrid 중 사용할 검색 방식"),
        ] = config.default_search_mode,
        limit: Annotated[
            int,
            Field(ge=1, le=_MAX_RESULT_LIMIT, strict=True, description="반환할 청크 수"),
        ] = config.default_result_limit,
    ) -> str:
        return _tool_payload(
            lambda: {
                "hits": [
                    _search_hit_payload(hit)
                    for hit in operations.search_within_document(
                        text,
                        source_file_name=source_file_name,
                        mode=mode,
                        limit=limit,
                    )
                ]
            }
        )

    @tool(
        "get_neighbor_chunks",
        description="선택한 근거 청크와 같은 문서에서 앞뒤 문맥을 문서 순서로 조회한다.",
    )
    def get_neighbor_chunks(
        source_file_name: Annotated[str, Field(min_length=1, description="원본 파일명")],
        chunk_index: Annotated[int, Field(ge=0, strict=True, description="기준 청크 순서")],
        before: Annotated[
            int,
            Field(
                ge=0,
                le=99,
                strict=True,
                description="앞쪽 청크 수. before + after + 1은 100 이하여야 한다.",
            ),
        ] = config.default_neighbor_before,
        after: Annotated[
            int,
            Field(
                ge=0,
                le=99,
                strict=True,
                description="뒤쪽 청크 수. before + after + 1은 100 이하여야 한다.",
            ),
        ] = config.default_neighbor_after,
    ) -> str:
        def operation() -> dict[str, object]:
            invalid_request = False
            try:
                request = NeighborRequest(
                    source_file_name=source_file_name,
                    chunk_index=chunk_index,
                    before=before,
                    after=after,
                )
            except (TypeError, ValueError):
                invalid_request = True

            if invalid_request:
                raise SearchToolInputError("인접 청크 조회 범위가 올바르지 않습니다.")
            return {
                "chunks": [
                    _chunk_payload(chunk) for chunk in operations.get_neighbor_chunks(request)
                ]
            }

        return _tool_payload(operation)

    @tool(
        "get_chunk",
        description="이미 알고 있는 UUID 청크 ID로 근거 하나를 다시 조회한다.",
    )
    def get_chunk(
        chunk_id: Annotated[str, Field(min_length=1, description="조회할 UUID 청크 ID")],
    ) -> str:
        def operation() -> dict[str, object]:
            chunk = operations.get_chunk(chunk_id)
            return {"chunk": _chunk_payload(chunk) if chunk is not None else None}

        return _tool_payload(operation)

    return search_chunks, search_within_document, get_neighbor_chunks, get_chunk


def create_search_agent(
    *,
    model: BaseChatModel,
    embedder: QueryEmbedder,
    backend: SearchBackend,
    config: SearchAgentConfig = DEFAULT_SEARCH_AGENT_CONFIG,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """HCX 모델에 검색 Tool을 바인딩한 Search Agent를 만든다."""

    return create_agent(
        model=model,
        tools=create_search_tools(embedder=embedder, backend=backend, config=config),
        system_prompt=load_search_agent_prompt(),
        middleware=(
            _RequireSearchToolResult(),
            _SearchModelCallLimit(max_model_calls=config.max_model_calls),
            ToolCallLimitMiddleware(run_limit=config.max_tool_calls, exit_behavior="continue"),
        ),
        name="search_agent",
    )


def _tool_payload(operation: Callable[[], object]) -> str:
    unexpected_failure = False
    try:
        payload = operation()
    except (QueryEmbeddingError, RetrievalError, SearchToolInputError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    # 구현이 다른 Backend의 원시 예외는 검색 Agent의 ToolMessage에 노출하지 않는다.
    except Exception:  # noqa: BLE001
        unexpected_failure = True

    if unexpected_failure:
        return json.dumps({"error": "검색 Tool 실행에 실패했습니다."}, ensure_ascii=False)

    serialization_failed = False
    try:
        return json.dumps(payload, ensure_ascii=False)
    # Tool 경계 밖으로 직렬화 대상이나 Provider의 원시 예외를 노출하지 않는다.
    except Exception:  # noqa: BLE001
        serialization_failed = True

    if serialization_failed:
        return json.dumps({"error": "검색 Tool 결과를 처리하지 못했습니다."}, ensure_ascii=False)
    raise AssertionError("도달할 수 없는 검색 Tool 상태입니다.")


def _search_hit_payload(hit: SearchHit) -> dict[str, object]:
    return {"score": hit.score, "chunk": _chunk_payload(hit.chunk)}


def _chunk_payload(chunk: RetrievedChunk) -> dict[str, object]:
    return {
        "chunk_id": chunk.chunk_id,
        "source_file_name": chunk.source_file_name,
        "document_type": chunk.document_type.value,
        "chunk_index": chunk.chunk_index,
        "title": chunk.title,
        "locator": chunk.locator,
        "content": chunk.content,
    }


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not 1 <= limit <= _MAX_RESULT_LIMIT:
        raise SearchToolInputError(f"검색 결과 수는 1~{_MAX_RESULT_LIMIT} 사이여야 합니다.")
