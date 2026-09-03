"""Main Supervisor Agent 조립."""

from collections.abc import Sequence
from importlib import resources
from typing import Any, cast

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    hook_config,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from pension_agent.agent.contracts import AgentAnswer
from pension_agent.agent.execution import ExecutionContext, ModelConcurrencyMiddleware
from pension_agent.agent.orchestration.state import SupervisorState


class RequireDomainToolCall(AgentMiddleware[Any, Any, Any]):
    """도메인 Tool을 한 번도 호출하지 않고 바로 최종 답변하려 하면 재지시한다."""

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("domain_results"):
            return None
        last_message = state.get("messages", [])[-1]
        if not isinstance(last_message, AIMessage) or last_message.tool_calls:
            return None
        return {
            "jump_to": "model",
            "messages": [
                HumanMessage(
                    content=(
                        "자유 형식 답변은 사용하지 않습니다. 연금·퇴직연금·ISA와 무관한 "
                        "질문이 아니라면 최소 하나의 도메인 Tool을 먼저 호출하세요."
                    )
                )
            ],
        }

    @hook_config(can_jump_to=["model"])
    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


class SupervisorModelCallLimit(ModelCallLimitMiddleware):
    """호출 상한에서 내부 안내문을 사용자 답변으로 남기지 않는다."""

    def __init__(self, *, max_model_calls: int) -> None:
        super().__init__(run_limit=max_model_calls, exit_behavior="end")
        self._max_model_calls = max_model_calls

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("run_model_call_count", 0) < self._max_model_calls:
            return None
        return {"jump_to": "end"}

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


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
    model_concurrency: ModelConcurrencyMiddleware | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """모델과 Domain Agent Tool을 주입받아 Main Supervisor를 만든다."""

    middleware = cast(
        Sequence[AgentMiddleware[Any, Any, Any]],
        (
            *((model_concurrency,) if model_concurrency is not None else ()),
            SupervisorModelCallLimit(max_model_calls=12),
            *(
                ToolCallLimitMiddleware(
                    tool_name=tool.name,
                    run_limit=3,
                    exit_behavior="continue",
                )
                for tool in tools
            ),
            RequireDomainToolCall(),
        ),
    )
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=load_main_supervisor_prompt(),
        state_schema=SupervisorState,
        context_schema=ExecutionContext,
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
