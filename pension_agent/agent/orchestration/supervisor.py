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
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from pension_agent.agent.contracts import AgentAnswer
from pension_agent.agent.execution import ExecutionContext, ModelConcurrencyMiddleware
from pension_agent.agent.injection_classifier import PromptInjectionClassifier
from pension_agent.agent.orchestration.state import SupervisorState
from pension_agent.agent.prompt_injection import MainInputGuardMiddleware, PromptInjectionMiddleware


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
    injection_classifier: PromptInjectionClassifier | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """모델과 Domain Agent Tool을 주입받아 Main Supervisor를 만든다."""

    middleware = cast(
        Sequence[AgentMiddleware[Any, Any, Any]],
        (
            MainInputGuardMiddleware(injection_classifier),
            PromptInjectionMiddleware(),
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
