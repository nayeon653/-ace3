"""외부 I/O 없이 Main Supervisor 컴포넌트를 검증한다."""

import asyncio
from collections.abc import Sequence
from importlib import resources
from typing import Any, ClassVar

import pytest
from langchain.messages import AIMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import Runnable

from pension_agent.agent.contracts import DomainName, DomainRequest, DomainResult
from pension_agent.agent.execution import ExecutionContext
from pension_agent.agent.orchestration import (
    AnswerService,
    FinalAnswerMissingError,
    build_agent_answer,
    create_domain_agent_tool,
    create_main_supervisor,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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
    async def run(
        request: DomainRequest,
        *,
        deadline: float | None = None,
    ) -> DomainResult:
        assert deadline is not None
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


@pytest.mark.anyio
async def test_main_supervisor_runs_domain_tools_and_accumulates_results(
    anyio_backend: str,
) -> None:
    del anyio_backend
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

    result = await supervisor.ainvoke(
        {
            "messages": [{"role": "user", "content": "이전 후 상품을 바꿀 수 있나요?"}],
            "question_id": "Q-001",
            "question": "이전 후 상품을 바꿀 수 있나요?",
            "domain_results": [],
        },
        context=ExecutionContext(deadline=asyncio.get_running_loop().time() + 30),
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


def test_main_supervisor_prompt_has_data_aware_routing_boundaries() -> None:
    prompt = (
        resources.files("pension_agent.prompts")
        .joinpath("orchestration", "main-supervisor.md")
        .read_text(encoding="utf-8")
    )

    assert "연금저축·IRP 전용 클래스 설명이 반복" in prompt
    assert "판단에 필요한 근거 문서군을 기준으로 Tool을 선택" in prompt
    assert "계좌·제도 이름에 `펀드`가 포함" in prompt
    assert ("`연금저축펀드와 IRP는 무엇이 다른가요?` → 업무·제도 + 세제·수령") in prompt
    assert "`A펀드와 B펀드의 위험과 보수를 비교해 주세요.` → 상품·운용" in prompt


def test_main_supervisor_prompt_has_medical_care_routing_boundaries() -> None:
    prompt = (
        resources.files("pension_agent.prompts")
        .joinpath("orchestration", "main-supervisor.md")
        .read_text(encoding="utf-8")
    )

    assert "가능 여부, 자격, 적용 조건" in prompt
    assert "한도, 세율, 세액, 과세 또는 세후액" in prompt
    assert "업무·제도와 세제·수령 Tool을 각각 한 번 호출" in prompt
    assert "`의료비`나 `요양`이라는 단어만" in prompt
    assert "세액, 한도 또는 세후액을 직접 계산하지 않는다" in prompt


def test_main_supervisor_prompt_has_retirement_benefit_routing_boundaries() -> None:
    prompt = (
        resources.files("pension_agent.prompts")
        .joinpath("orchestration", "main-supervisor.md")
        .read_text(encoding="utf-8")
    )

    assert "제도 유형이 불명확한 `퇴직급여가 얼마야?`" in prompt
    assert "DB와 DC 퇴직급여 금액을 비교" in prompt
    assert "DB→DC 전환 가능 여부와 전환금액" in prompt
    assert "기존 인출 세금 Tool을 임의로 연쇄 호출하지 않는다" in prompt
    assert "기간·근속연수·급여·전환금액·세금을 직접 계산" in prompt


def test_main_supervisor_prompt_has_executive_retirement_limit_routing_boundaries() -> None:
    prompt = (
        resources.files("pension_agent.prompts")
        .joinpath("orchestration", "main-supervisor.md")
        .read_text(encoding="utf-8")
    )

    assert "임원 퇴직소득 한도, 임원 퇴직소득 인정액과 한도초과 근로소득은" in prompt
    assert "DB/DC 제도 유형 판단과 무관하다" in prompt
    assert "임원 해당 여부 자체를" in prompt
    assert "임원 퇴직소득 한도가 얼마인가요?" in prompt


def test_main_supervisor_prompt_has_tax_word_procedural_routing_boundaries() -> None:
    prompt = (
        resources.files("pension_agent.prompts")
        .joinpath("orchestration", "main-supervisor.md")
        .read_text(encoding="utf-8")
    )

    assert "세율·공제액·과세 여부 자체를 판단하는" in prompt
    assert "화면에 뜨는 오류·안내 메시지의 원인을 묻거나" in prompt
    assert "제출 절차를 다루는 업무 안내 자료다" in prompt
    assert (
        "`'세금우대 약정정보가 없습니다'라는 메시지가 나옵니다.` → 업무·제도" in prompt
    )
    assert (
        "`연금개시나 중도인출, 해지할 때 소득·세액공제확인서를 꼭 제출해야하나요?` "
        "→ 업무·제도" in prompt
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("question", "expected_domains"),
    [
        ("'세금우대 약정정보가 없습니다'라는 메시지가 나옵니다.", {"policy"}),
        (
            "연금개시나 중도인출, 해지할 때 소득·세액공제확인서를 꼭 제출해야하나요?",
            {"policy"},
        ),
        ("연금저축계좌를 해지하면 세금이 많이 나오나요?", {"tax_payout"}),
    ],
)
async def test_main_supervisor_routes_tax_worded_procedural_questions_to_policy(
    anyio_backend: str,
    question: str,
    expected_domains: set[str],
) -> None:
    del anyio_backend
    requests: list[DomainRequest] = []
    tools = [
        create_domain_agent_tool(
            name="analyze_policy",
            description="업무 판단",
            domain="policy",
            runner=_runner("policy", "제도 판단 결과입니다.", requests),
        ),
        create_domain_agent_tool(
            name="analyze_tax_payout",
            description="세제 판단",
            domain="tax_payout",
            runner=_runner("tax_payout", "세제 판단 결과입니다.", requests),
        ),
    ]
    tool_calls = [
        _tool_call(
            "analyze_policy" if domain == "policy" else "analyze_tax_payout",
            f"{domain}-call",
            "제도 판단" if domain == "policy" else "세제 판단",
        )
        for domain in sorted(expected_domains)
    ]
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(content="", tool_calls=tool_calls),
            AIMessage(content="도메인 결과를 통합했습니다."),
        ]
    )
    supervisor = create_main_supervisor(model=model, tools=tools)

    result = await supervisor.ainvoke(
        {
            "messages": [{"role": "user", "content": question}],
            "question_id": "Q-TAX-WORD-ROUTING",
            "question": question,
            "domain_results": [],
        },
        context=ExecutionContext(deadline=asyncio.get_running_loop().time() + 30),
    )

    assert {result["domain"] for result in result["domain_results"]} == expected_domains
    assert len(requests) == len(expected_domains)
    assert {request["question"] for request in requests} == {question}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("question", "tool_calls", "expected_domains"),
    [
        (
            "DC 의료비 중도인출은 가능한가요?",
            [_tool_call("analyze_policy", "policy-call", "의료비 중도인출 가능 여부 판단")],
            {"policy"},
        ),
        (
            "요양 인출 과세와 한도, 세후액을 계산해 주세요.",
            [
                _tool_call(
                    "analyze_tax_payout",
                    "tax-call",
                    "요양 인출 과세·한도·세후액 판단",
                )
            ],
            {"tax_payout"},
        ),
        (
            "DC 의료비 중도인출이 가능한지와 세금까지 알려 주세요.",
            [
                _tool_call("analyze_policy", "policy-call", "의료비 중도인출 가능 여부 판단"),
                _tool_call("analyze_tax_payout", "tax-call", "의료비 인출 세금 판단"),
            ],
            {"policy", "tax_payout"},
        ),
    ],
)
async def test_main_supervisor_routes_medical_care_intents_to_required_domains(
    anyio_backend: str,
    question: str,
    tool_calls: list[dict[str, Any]],
    expected_domains: set[str],
) -> None:
    del anyio_backend
    requests: list[DomainRequest] = []
    policy_tool = create_domain_agent_tool(
        name="analyze_policy",
        description="업무 판단",
        domain="policy",
        runner=_runner("policy", "제도상 가능 여부를 판단했습니다.", requests),
    )
    tax_tool = create_domain_agent_tool(
        name="analyze_tax_payout",
        description="세제 판단",
        domain="tax_payout",
        runner=_runner("tax_payout", "세제 결과를 계산했습니다.", requests),
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(content="", tool_calls=tool_calls),
            AIMessage(content="도메인 결과를 통합했습니다."),
        ]
    )
    supervisor = create_main_supervisor(model=model, tools=[policy_tool, tax_tool])

    result = await supervisor.ainvoke(
        {
            "messages": [{"role": "user", "content": question}],
            "question_id": "Q-MEDICAL-ROUTING",
            "question": question,
            "domain_results": [],
        },
        context=ExecutionContext(deadline=asyncio.get_running_loop().time() + 30),
    )

    assert {result["domain"] for result in result["domain_results"]} == expected_domains
    assert len(requests) == len(expected_domains)
    assert {request["question"] for request in requests} == {question}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("question", "expected_domains"),
    [
        ("DB와 DC의 적용 조건 차이가 뭐야?", {"policy"}),
        ("이 근속기간이 DB 퇴직급여 근속연수에 포함돼?", {"policy"}),
        ("DB에서 DC로 전환할 수 있어?", {"policy"}),
        (
            "최근 3개월 임금 900만원, 포함일수 90일, 검증 근속 10년이면 DB 퇴직급여 얼마야?",
            {"tax_payout"},
        ),
        ("연간임금총액 6000만원이면 DC 최소 사용자 부담금 얼마야?", {"tax_payout"}),
        ("누적 부담금 5000만원, 운용손실 500만원이면 DC 급여 얼마야?", {"tax_payout"}),
        ("검증된 최종 평균임금·연간임금·근속연수로 DB→DC 전환금액을 계산해줘", {"tax_payout"}),
        ("근속 인정 여부를 확인해서 DB 퇴직급여도 계산해줘", {"policy", "tax_payout"}),
        ("DB→DC 전환 가능한지와 전환금액을 알려줘", {"policy", "tax_payout"}),
        ("DB/DC 중 어떤 제도인지 확인하고 받을 금액도 계산해줘", {"policy", "tax_payout"}),
        ("입력이 확인된 DB와 DC 퇴직급여 금액을 비교해줘", {"tax_payout"}),
        ("내 경우 DB와 DC 중 어느 쪽이 적용되고 얼마 차이 나?", {"policy", "tax_payout"}),
        ("퇴직급여가 얼마야?", {"policy"}),
        ("DB 퇴직급여와 퇴직소득세까지 계산해줘", {"tax_payout"}),
        ("임원 퇴직소득 한도가 얼마야?", {"tax_payout"}),
        ("임원 퇴직금 중 세법상 퇴직소득으로 얼마까지 인정돼?", {"tax_payout"}),
        ("임원 퇴직소득 한도 초과분이 얼마야?", {"tax_payout"}),
        ("임원 퇴직소득 한도와 초과분 세금까지 계산해줘", {"tax_payout"}),
    ],
)
async def test_main_supervisor_routes_retirement_benefit_intents(
    anyio_backend: str,
    question: str,
    expected_domains: set[str],
) -> None:
    del anyio_backend
    requests: list[DomainRequest] = []
    tools = [
        create_domain_agent_tool(
            name="analyze_policy",
            description="업무 판단",
            domain="policy",
            runner=_runner("policy", "제도 판단 결과입니다.", requests),
        ),
        create_domain_agent_tool(
            name="analyze_tax_payout",
            description="급여·세제 판단",
            domain="tax_payout",
            runner=_runner("tax_payout", "금액 판단 결과입니다.", requests),
        ),
    ]
    tool_calls = [
        _tool_call(
            "analyze_policy" if domain == "policy" else "analyze_tax_payout",
            f"{domain}-call",
            "제도 판단" if domain == "policy" else "금액 판단",
        )
        for domain in sorted(expected_domains)
    ]
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(content="", tool_calls=tool_calls),
            AIMessage(content="도메인 결과를 통합했습니다."),
        ]
    )
    supervisor = create_main_supervisor(model=model, tools=tools)

    result = await supervisor.ainvoke(
        {
            "messages": [{"role": "user", "content": question}],
            "question_id": "Q-RETIREMENT-ROUTING",
            "question": question,
            "domain_results": [],
        },
        context=ExecutionContext(deadline=asyncio.get_running_loop().time() + 30),
    )

    assert {item["domain"] for item in result["domain_results"]} == expected_domains
    assert len(requests) == len(expected_domains)
    assert {request["question"] for request in requests} == {question}


@pytest.mark.anyio
async def test_main_supervisor_allows_three_same_domain_judgments_and_blocks_fourth(
    anyio_backend: str,
) -> None:
    del anyio_backend
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

    result = await supervisor.ainvoke(
        {
            "messages": [{"role": "user", "content": "가입과 이전 절차를 알려주세요."}],
            "question_id": "Q-MULTI-POLICY",
            "question": "가입과 이전 절차를 알려주세요.",
            "domain_results": [],
        },
        context=ExecutionContext(deadline=asyncio.get_running_loop().time() + 30),
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


@pytest.mark.anyio
async def test_main_supervisor_model_limit_is_not_returned_as_a_user_answer(
    anyio_backend: str,
) -> None:
    del anyio_backend
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
                    _tool_call(
                        "analyze_policy",
                        f"policy-{index}",
                        f"이전 가능 여부 판단 {index}",
                    )
                ],
            )
            for index in range(12)
        ]
    )
    supervisor = create_main_supervisor(model=model, tools=[policy_tool])
    service = AnswerService(supervisor)

    with pytest.raises(FinalAnswerMissingError, match="최종 자연어 답변"):
        await service.run(question_id="Q-LIMIT", question="이전할 수 있나요?")
