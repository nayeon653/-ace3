"""Main Supervisor와 도메인 Agent 구현을 조립한다."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from pension_agent.agent.domains.assembly import create_domain_agent_tools
from pension_agent.agent.supervisor import create_main_supervisor


def create_default_main_supervisor(
    *,
    model: BaseChatModel,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """기본 도메인 Agent 3개가 연결된 Main Supervisor를 만든다."""

    return create_main_supervisor(
        model=model,
        tools=create_domain_agent_tools(),
    )
