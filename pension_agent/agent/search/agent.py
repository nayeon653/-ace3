"""검색 Tool을 사용하는 ReAct Search Agent 조립."""

from importlib import resources
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from pension_agent.agent.search.middleware import RequireSearchToolResult, SearchModelCallLimit
from pension_agent.agent.search.ports import ChunkRetriever, QueryEmbedder
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
        tools=create_search_tools(embedder=embedder, retriever=retriever, config=config),
        system_prompt=load_search_agent_prompt(),
        state_schema=SearchAgentState,
        middleware=(
            RequireSearchToolResult(),
            SearchModelCallLimit(max_model_calls=config.max_model_calls),
            ToolCallLimitMiddleware(run_limit=config.max_tool_calls, exit_behavior="continue"),
        ),
        name="search_agent",
    )
