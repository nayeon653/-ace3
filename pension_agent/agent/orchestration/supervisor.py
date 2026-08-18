"""Main Supervisor Agent 조립."""

from collections.abc import Sequence
from importlib import resources
from typing import Any, cast

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from pension_agent.agent.contracts import AgentAnswer
from pension_agent.agent.orchestration.state import SupervisorState


def load_main_supervisor_prompt() -> str:
    """패키지 리소스에서 Main Supervisor 프롬프트를 읽는다."""

    return (
        resources.files("pension_agent.prompts")
        .joinpath("orchestration", "main-supervisor.md")
        .read_text(encoding="utf-8")
    )


def create_main_supervisor(
    *,
    model: BaseChatModel,
    tools: Sequence[BaseTool],
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """모델과 Domain Agent Tool을 주입받아 Main Supervisor를 만든다."""

    middleware = cast(
        Sequence[AgentMiddleware[Any, Any, Any]],
        (
            ModelCallLimitMiddleware(run_limit=12, exit_behavior="end"),
            *(
                ToolCallLimitMiddleware(
                    tool_name=tool.name,
                    run_limit=3,
                    exit_behavior="continue",
                )
                for tool in tools
            ),
        ),
    )
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=load_main_supervisor_prompt(),
        state_schema=SupervisorState,
        middleware=middleware,
        name="main_supervisor",
    )


def build_agent_answer(messages: Sequence[BaseMessage]) -> AgentAnswer:
    """마지막 자연어 AI 응답을 애플리케이션 출력 계약으로 변환한다."""

    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            answer = message.text.strip()
            if answer:
                return AgentAnswer(answer=answer)
    raise ValueError("Main Supervisor의 최종 자연어 답변이 없습니다.")
