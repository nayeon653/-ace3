"""Tool 기반 Search Agent 계약을 검증한다."""

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar, cast

import pytest
from langchain.messages import AIMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from pension_agent.agent import create_search_agent, create_search_tools
from pension_agent.agent.search_agent import load_search_agent_prompt
from pension_agent.core import (
    DocumentType,
    ElementType,
    NeighborRequest,
    RetrievedChunk,
    SearchFilters,
    SearchHit,
    SearchMode,
    SearchQuery,
)


class ToolCallingFakeModel(FakeMessagesListChatModel):
    bindings: ClassVar[list[tuple[list[str], dict[str, Any]]]] = []

    def bind_tools(
        self,
        tools: Sequence[Any],
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        self.bindings.append(([tool.name for tool in tools], kwargs))
        return self


@dataclass
class FakeEmbedder:
    vector: list[float] = field(default_factory=lambda: [0.1, 0.2])
    error: Exception | None = None
    calls: list[str] = field(default_factory=list)

    def embed_query(self, text: str) -> list[float]:
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return self.vector


class ExplodingVector(list[float]):
    def __iter__(self) -> Iterator[float]:
        raise RuntimeError("provider secret=LAZY")


@dataclass
class FakeSearchBackend:
    hits: list[SearchHit] = field(default_factory=list)
    chunks: list[RetrievedChunk] = field(default_factory=list)
    chunk: RetrievedChunk | None = None
    chunk_searches: list[tuple[SearchQuery, SearchFilters | None, int]] = field(
        default_factory=list
    )
    document_searches: list[tuple[SearchQuery, str, int]] = field(default_factory=list)
    neighbor_requests: list[NeighborRequest] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    search_error: Exception | None = None

    def search_chunks(
        self,
        query: SearchQuery,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        if self.search_error is not None:
            raise self.search_error
        self.chunk_searches.append((query, filters, limit))
        return self.hits

    def search_within_document(
        self,
        query: SearchQuery,
        *,
        source_file_name: str,
        limit: int = 10,
    ) -> list[SearchHit]:
        self.document_searches.append((query, source_file_name, limit))
        return self.hits

    def get_neighbor_chunks(self, request: NeighborRequest) -> list[RetrievedChunk]:
        self.neighbor_requests.append(request)
        return self.chunks

    def get_chunk(self, chunk_id: str) -> RetrievedChunk | None:
        self.chunk_ids.append(chunk_id)
        return self.chunk


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="550e8400-e29b-41d4-a716-446655440000",
        source_file_name="guide.pdf",
        source_format="pdf",
        document_type=DocumentType.PENSION_REFERENCE,
        chunk_index=2,
        content="연금계좌 이전 절차",
        heading_path=("계좌 이전",),
        captions=(),
        element_types=(ElementType.TEXT,),
        page_numbers=(3,),
        title="계좌 이전",
        locator="3페이지",
    )


def _tools(
    *,
    embedder: FakeEmbedder | None = None,
    backend: FakeSearchBackend | None = None,
) -> tuple[dict[str, BaseTool], FakeEmbedder, FakeSearchBackend]:
    resolved_embedder = embedder or FakeEmbedder()
    resolved_backend = backend or FakeSearchBackend()
    tools = create_search_tools(embedder=resolved_embedder, backend=resolved_backend)
    return {tool.name: tool for tool in tools}, resolved_embedder, resolved_backend


@pytest.mark.parametrize("mode", [SearchMode.DENSE, SearchMode.HYBRID])
def test_search_chunks_tool_embeds_and_serializes_hits(mode: SearchMode) -> None:
    chunk = _chunk()
    backend = FakeSearchBackend(hits=[SearchHit(chunk=chunk, score=0.8)])
    tools, embedder, _backend = _tools(backend=backend)

    content = tools["search_chunks"].invoke(
        {
            "text": "  IRP 이전 절차  ",
            "mode": mode.value,
            "document_type": DocumentType.PENSION_REFERENCE.value,
            "limit": 7,
        }
    )

    payload = json.loads(content)
    assert payload["hits"][0]["chunk"]["chunk_id"] == chunk.chunk_id
    assert payload["hits"][0]["score"] == 0.8
    assert embedder.calls == ["IRP 이전 절차"]
    query, filters, limit = backend.chunk_searches[0]
    assert query == SearchQuery(text="IRP 이전 절차", dense=(0.1, 0.2), mode=mode)
    assert filters == SearchFilters(document_type=DocumentType.PENSION_REFERENCE)
    assert limit == 7


def test_sparse_search_tool_skips_embedding() -> None:
    embedder = FakeEmbedder(error=RuntimeError("호출되면 안 됩니다."))
    tools, _embedder, backend = _tools(embedder=embedder)

    content = tools["search_chunks"].invoke(
        {"text": "IRP 이전 절차", "mode": SearchMode.SPARSE.value}
    )

    assert json.loads(content) == {"hits": []}
    assert embedder.calls == []
    query, _filters, _limit = backend.chunk_searches[0]
    assert query == SearchQuery(text="IRP 이전 절차", mode=SearchMode.SPARSE)


def test_document_search_tool_preserves_document_scope() -> None:
    tools, embedder, backend = _tools()

    tools["search_within_document"].invoke(
        {
            "text": "중도해지",
            "source_file_name": " guide.pdf ",
            "mode": SearchMode.DENSE.value,
            "limit": 4,
        }
    )

    query, source_file_name, limit = backend.document_searches[0]
    assert query == SearchQuery(text="중도해지", dense=(0.1, 0.2), mode=SearchMode.DENSE)
    assert source_file_name == "guide.pdf"
    assert limit == 4
    assert embedder.calls == ["중도해지"]


def test_lookup_tools_delegate_without_embedding() -> None:
    chunk = _chunk()
    embedder = FakeEmbedder(error=RuntimeError("호출되면 안 됩니다."))
    backend = FakeSearchBackend(chunks=[chunk], chunk=chunk)
    tools, _embedder, _backend = _tools(embedder=embedder, backend=backend)

    neighbor_content = tools["get_neighbor_chunks"].invoke(
        {"source_file_name": "guide.pdf", "chunk_index": 2, "before": 1, "after": 1}
    )
    chunk_content = tools["get_chunk"].invoke({"chunk_id": chunk.chunk_id})

    assert json.loads(neighbor_content)["chunks"][0]["chunk_id"] == chunk.chunk_id
    assert json.loads(chunk_content)["chunk"]["content"] == chunk.content
    assert backend.neighbor_requests == [
        NeighborRequest(source_file_name="guide.pdf", chunk_index=2)
    ]
    assert backend.chunk_ids == [chunk.chunk_id]
    assert embedder.calls == []


@pytest.mark.parametrize("limit", [0, 101, True])
def test_tool_schema_rejects_invalid_limit_before_embedding(limit: int) -> None:
    embedder = FakeEmbedder(error=RuntimeError("호출되면 안 됩니다."))
    tools, _embedder, backend = _tools(embedder=embedder)

    with pytest.raises(ValidationError):
        tools["search_chunks"].invoke({"text": "IRP 이전", "limit": limit})

    assert embedder.calls == []
    assert backend.chunk_searches == []


def test_empty_document_name_returns_safe_tool_error_before_embedding() -> None:
    embedder = FakeEmbedder(error=RuntimeError("호출되면 안 됩니다."))
    tools, _embedder, backend = _tools(embedder=embedder)

    content = tools["search_within_document"].invoke({"text": "IRP 이전", "source_file_name": "  "})

    assert json.loads(content) == {"error": "원본 파일명 필터는 비어 있을 수 없습니다."}
    assert embedder.calls == []
    assert backend.document_searches == []


@pytest.mark.parametrize(
    "embedder",
    [
        FakeEmbedder(error=RuntimeError("provider secret=DIRECT")),
        FakeEmbedder(vector=[]),
        FakeEmbedder(vector=[float("nan")]),
        FakeEmbedder(vector=ExplodingVector()),
    ],
)
def test_embedding_failure_is_sanitized_in_tool_message(embedder: FakeEmbedder) -> None:
    tools, _embedder, backend = _tools(embedder=embedder)

    content = tools["search_chunks"].invoke({"text": "IRP 이전"})

    payload = json.loads(content)
    assert set(payload) == {"error"}
    assert "secret" not in content
    assert backend.chunk_searches == []


def test_unexpected_backend_error_is_sanitized_in_tool_message() -> None:
    backend = FakeSearchBackend(search_error=RuntimeError("backend secret=HIDDEN"))
    tools, _embedder, _backend = _tools(backend=backend)

    content = tools["search_chunks"].invoke({"text": "IRP 이전"})

    assert json.loads(content) == {"error": "검색 Tool 실행에 실패했습니다."}
    assert "secret" not in content


def test_invalid_neighbor_request_returns_safe_tool_error() -> None:
    tools, embedder, backend = _tools()

    content = tools["get_neighbor_chunks"].invoke({"source_file_name": "  ", "chunk_index": 2})

    assert json.loads(content) == {"error": "원본 파일명은 비어 있을 수 없습니다."}
    assert embedder.calls == []
    assert backend.neighbor_requests == []


def test_search_tools_have_stable_names_and_argument_schemas() -> None:
    tools, _embedder, _backend = _tools()

    assert set(tools) == {
        "search_chunks",
        "search_within_document",
        "get_neighbor_chunks",
        "get_chunk",
    }
    search_schema = cast(type[BaseModel], tools["search_chunks"].tool_call_schema)
    assert set(search_schema.model_json_schema()["properties"]) == {
        "text",
        "mode",
        "document_type",
        "limit",
    }


def test_create_search_agent_binds_tools_and_runs_react_loop() -> None:
    chunk = _chunk()
    backend = FakeSearchBackend(hits=[SearchHit(chunk=chunk, score=0.9)])
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_chunks",
                        "args": {"text": "IRP 이전", "mode": "sparse", "limit": 3},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="guide.pdf 3페이지에서 이전 절차 근거를 찾았습니다."),
        ]
    )
    model.bindings.clear()
    agent = create_search_agent(model=model, embedder=FakeEmbedder(), backend=backend)

    result = agent.invoke({"messages": [{"role": "user", "content": "IRP 이전 근거 검색"}]})

    tool_messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert len(tool_messages) == 1
    assert chunk.chunk_id in str(tool_messages[0].content)
    assert result["messages"][-1].text == "guide.pdf 3페이지에서 이전 절차 근거를 찾았습니다."
    assert all(
        set(names)
        == {"search_chunks", "search_within_document", "get_neighbor_chunks", "get_chunk"}
        for names, _kwargs in model.bindings
    )


def test_search_agent_prompt_is_packaged() -> None:
    prompt = load_search_agent_prompt()

    assert "필요한 최소 Tool만 호출" in prompt
    assert "검색 결과에 없는 사실" in prompt
