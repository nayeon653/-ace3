"""외부 I/O 없이 Main Supervisor 컴포넌트를 검증한다."""

from collections.abc import Sequence
from importlib import resources
from typing import Any, ClassVar

from langchain.messages import AIMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import Runnable

from pension_agent.agent.contracts import DomainName, DomainRequest, DomainResult
from pension_agent.agent.orchestration import (
    build_agent_answer,
    create_domain_agent_tool,
    create_main_supervisor,
)


class ToolCallingFakeModel(FakeMessagesListChatModel):
    """고정된 Tool 호출을 반환하는 테스트 전용 모델."""

    bindings: ClassVar[list[tuple[list[str], dict[str, Any]]]] = []

    def bind_tools(
        self,
        tools: Sequence[Any],
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        self.bindings.append(([tool.name for tool in tools], kwargs))
        return self


def _runner(
    domain: DomainName,
    conclusion: str,
    requests: list[DomainRequest],
):
    def run(request: DomainRequest) -> DomainResult:
        requests.append(request)
        return {
            "domain": domain,
            "execution_status": "completed",
            "decision": {
                "status": "determined",
                "conclusion": conclusion,
                "missing_conditions": [],
            },
            "evidence": [],
            "calculations": [],
            "warnings": [],
        }

    return run


def _tool_call(name: str, call_id: str, objective: str) -> dict[str, Any]:
    return {
        "name": name,
        "args": {"objective": objective},
        "id": call_id,
        "type": "tool_call",
    }


def test_main_supervisor_runs_domain_tools_and_accumulates_results() -> None:
    requests: list[DomainRequest] = []
    policy_tool = create_domain_agent_tool(
        name="analyze_policy",
        description="업무 판단",
        domain="policy",
        runner=_runner("policy", "이전할 수 있습니다.", requests),
    )
    product_tool = create_domain_agent_tool(
        name="analyze_product",
        description="상품 판단",
        domain="product",
        runner=_runner("product", "상품을 비교할 수 있습니다.", requests),
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    _tool_call("analyze_policy", "policy-call", "이전 가능 여부 판단"),
                    _tool_call("analyze_product", "product-call", "상품 변경 범위 판단"),
                ],
            ),
            AIMessage(
                content="이전 가능 여부와 상품 조건을 확인하세요.",
            ),
        ]
    )
    model.bindings.clear()
    supervisor = create_main_supervisor(model=model, tools=[policy_tool, product_tool])

    result = supervisor.invoke(
        {
            "messages": [{"role": "user", "content": "이전 후 상품을 바꿀 수 있나요?"}],
            "question_id": "Q-001",
            "question": "이전 후 상품을 바꿀 수 있나요?",
            "domain_results": [],
        }
    )

    answer = build_agent_answer(result["messages"])

    assert answer.answer == "이전 가능 여부와 상품 조건을 확인하세요."
    assert "structured_response" not in result
    assert {item["domain"] for item in result["domain_results"]} == {"policy", "product"}
    tool_messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert len(tool_messages) == 2
    assert all("근거 본문" not in str(message.content) for message in tool_messages)
    assert all(set(names) == {"analyze_policy", "analyze_product"} for names, _ in model.bindings)
    assert all(kwargs.get("tool_choice") is None for _, kwargs in model.bindings)
    assert {request["question"] for request in requests} == {"이전 후 상품을 바꿀 수 있나요?"}
    assert {request["objective"] for request in requests} == {
        "이전 가능 여부 판단",
        "상품 변경 범위 판단",
    }


def test_main_supervisor_prompt_is_packaged() -> None:
    prompt = (
        resources.files("pension_agent.prompts")
        .joinpath("orchestration", "main-supervisor.md")
        .read_text(encoding="utf-8")
    )

    assert "decision.status=conditional" in prompt
    assert "Tool을 함께 호출해 병렬로 실행한다" in prompt
    assert "JSON이나 Tool 호출 형식을 직접 출력하지 않는다" in prompt


def test_main_supervisor_allows_three_same_domain_judgments_and_blocks_fourth() -> None:
    requests: list[DomainRequest] = []
    policy_tool = create_domain_agent_tool(
        name="analyze_policy",
        description="업무 판단",
        domain="policy",
        runner=_runner("policy", "이전할 수 있습니다.", requests),
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    _tool_call("analyze_policy", "policy-1", "가입 가능 여부 판단"),
                    _tool_call("analyze_policy", "policy-2", "이전 가능 여부 판단"),
                    _tool_call("analyze_policy", "policy-3", "이전 절차 판단"),
                    _tool_call("analyze_policy", "policy-4", "해지 절차 판단"),
                ],
            ),
            AIMessage(content="가입, 이전 가능 여부와 이전 절차를 확인했습니다."),
        ]
    )
    supervisor = create_main_supervisor(model=model, tools=[policy_tool])

    result = supervisor.invoke(
        {
            "messages": [{"role": "user", "content": "가입과 이전 절차를 알려주세요."}],
            "question_id": "Q-MULTI-POLICY",
            "question": "가입과 이전 절차를 알려주세요.",
            "domain_results": [],
        }
    )

    assert {request["objective"] for request in requests} == {
        "가입 가능 여부 판단",
        "이전 가능 여부 판단",
        "이전 절차 판단",
    }
    assert len(result["domain_results"]) == 3
    blocked = [
        message
        for message in result["messages"]
        if isinstance(message, ToolMessage) and message.tool_call_id == "policy-4"
    ]
    assert len(blocked) == 1
