"""검색 Tool을 사용하는 ReAct Search Agent 조립."""

from importlib import resources
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from pension_agent.agent.search.middleware import (
    CompleteSearchResult,
    RecordSearchCandidates,
    RequireSearchPermission,
    RequireSearchToolResult,
    SearchModelCallLimit,
    SearchToolCallLimit,
)
from pension_agent.agent.search.ports import ChunkRetriever, QueryEmbedder
from pension_agent.agent.search.result_tool import create_search_result_tool
from pension_agent.agent.search.state import SearchAgentState
from pension_agent.agent.search.tools import create_search_tools
from pension_agent.config import DEFAULT_SEARCH_AGENT_CONFIG, SearchAgentConfig


def load_search_agent_prompt() -> str:
    """패키지 리소스에서 Search Agent 프롬프트를 읽는다."""

    return (
        resources.files("pension_agent.prompts")
        .joinpath("search", "search-agent.md")
        .read_text(encoding="utf-8")
    )


def create_search_agent(
    *,
    model: BaseChatModel,
    embedder: QueryEmbedder,
    retriever: ChunkRetriever,
    config: SearchAgentConfig = DEFAULT_SEARCH_AGENT_CONFIG,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """HCX 모델에 검색 Tool을 바인딩한 Search Agent를 만든다."""

    return create_agent(
        model=model,
        tools=(
            *create_search_tools(embedder=embedder, retriever=retriever, config=config),
            create_search_result_tool(retriever=retriever),
        ),
        system_prompt=load_search_agent_prompt(),
        state_schema=SearchAgentState,
        middleware=(
            RequireSearchPermission(),
            CompleteSearchResult(),
            RequireSearchToolResult(),
            RecordSearchCandidates(),
            SearchModelCallLimit(max_model_calls=config.max_model_calls),
            SearchToolCallLimit(max_tool_calls=config.max_tool_calls),
        ),
        name="search_agent",
    )
