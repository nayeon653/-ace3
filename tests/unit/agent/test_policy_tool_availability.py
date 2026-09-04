"""Policy Agent의 단계별 Tool 노출과 범용 결과 안전화를 검증한다."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

from pension_agent.agent.policy.agent import load_policy_agent_prompt
from pension_agent.agent.policy.react import (
    SEARCH_DOCUMENTS_TOOL_NAME,
    SUBMIT_DOMAIN_RESULT_TOOL_NAME,
    EnforcePolicyToolSequence,
    PolicyToolAvailabilityMiddleware,
    _build_policy_result,
)
from pension_agent.agent.search import SearchResult


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


_DC_TOOL = "calculate_dc_medical_withdrawal_threshold"
_ISA_TOOL = "calculate_isa_transfer_deadline"
_ALL_TOOLS = [SEARCH_DOCUMENTS_TOOL_NAME, _DC_TOOL, _ISA_TOOL, SUBMIT_DOMAIN_RESULT_TOOL_NAME]


def _history(*tool_names: str) -> list[Any]:
    messages: list[Any] = [HumanMessage(content="질문")]
    for index, tool_name in enumerate(tool_names):
        call_id = f"call-{index}"
        messages.extend(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": tool_name,
                            "args": {},
                            "id": call_id,
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(content="결과", tool_call_id=call_id, name=tool_name),
            ]
        )
    return messages


async def _captured_request(
    state: dict[str, Any],
    *,
    messages: list[Any] | None = None,
    tool_names: list[str] | None = None,
) -> ModelRequest[Any]:
    request = ModelRequest(
        model=FakeMessagesListChatModel(responses=[]),
        messages=cast(Any, messages or []),
        tools=cast(
            Any,
            [SimpleNamespace(name=name) for name in (tool_names or _ALL_TOOLS)],
        ),
        state=cast(Any, state),
    )
    received: list[ModelRequest[Any]] = []

    async def handler(model_request: ModelRequest[Any]) -> ModelResponse[Any]:
        received.append(model_request)
        return ModelResponse(result=[])

    await PolicyToolAvailabilityMiddleware().awrap_model_call(request, handler)
    return received[0]


def _tool_names(request: ModelRequest[Any]) -> list[str]:
    return [cast(str, tool.name) for tool in request.tools]


@pytest.mark.anyio
async def test_policy_tool_availability_exposes_search_and_submit_before_search() -> None:
    received = await _captured_request({"question": "이전 가능한가요?", "calculations": []})

    assert received.tool_choice is None
    assert _tool_names(received) == [SEARCH_DOCUMENTS_TOOL_NAME, SUBMIT_DOMAIN_RESULT_TOOL_NAME]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "question",
    [
        "연금계좌를 이전할 수 있나요?",
        "만기자금 전환 날짜를 계산해줘",
        "의료비 중도인출 기준금액을 계산해줘",
    ],
)
async def test_policy_tool_availability_exposes_both_calculators_after_search(
    question: str,
) -> None:
    received = await _captured_request(
        {
            "question": question,
            "search_result": SearchResult(execution_status="completed"),
            "calculations": [],
        },
        messages=_history(SEARCH_DOCUMENTS_TOOL_NAME),
    )

    assert received.tool_choice is None
    assert _tool_names(received) == [
        SEARCH_DOCUMENTS_TOOL_NAME,
        _DC_TOOL,
        _ISA_TOOL,
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
    ]


@pytest.mark.anyio
async def test_policy_tool_availability_preserves_executed_calculator_history() -> None:
    received = await _captured_request(
        {
            "question": "만기자금 전환 마감일을 계산해줘",
            "search_result": SearchResult(execution_status="completed"),
            "calculations": [{"calculator_id": "isa_transfer_deadline"}],
        },
        messages=_history(SEARCH_DOCUMENTS_TOOL_NAME, _ISA_TOOL),
    )

    assert received.tool_choice is None
    assert _tool_names(received) == [
        SEARCH_DOCUMENTS_TOOL_NAME,
        _ISA_TOOL,
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
    ]


@pytest.mark.anyio
async def test_policy_tool_availability_allows_unavailable_optional_calculators() -> None:
    received = await _captured_request(
        {
            "search_result": SearchResult(execution_status="completed"),
            "calculations": [],
        },
        messages=_history(SEARCH_DOCUMENTS_TOOL_NAME),
        tool_names=[SEARCH_DOCUMENTS_TOOL_NAME, SUBMIT_DOMAIN_RESULT_TOOL_NAME],
    )

    assert _tool_names(received) == [
        SEARCH_DOCUMENTS_TOOL_NAME,
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
    ]


@pytest.mark.anyio
async def test_policy_tool_availability_rejects_missing_history_schema() -> None:
    with pytest.raises(RuntimeError, match="Policy 상태별 Tool 구성이 올바르지 않습니다"):
        await _captured_request(
            {
                "question": "연금계좌를 이전할 수 있나요?",
                "search_result": SearchResult(execution_status="completed"),
                "calculations": [],
            },
            messages=_history(SEARCH_DOCUMENTS_TOOL_NAME),
            tool_names=[SUBMIT_DOMAIN_RESULT_TOOL_NAME],
        )


def _tool_call(name: str, index: int) -> dict[str, Any]:
    return {
        "name": name,
        "args": {},
        "id": f"call-{index}",
        "type": "tool_call",
    }


def _enforced_tool_names(state: dict[str, Any], *tool_names: str) -> list[str]:
    model_message = AIMessage(
        content="",
        tool_calls=[_tool_call(name, index) for index, name in enumerate(tool_names)],
    )
    update = EnforcePolicyToolSequence().after_model(
        {**state, "messages": [model_message]},
        runtime=None,
    )
    if update is None:
        return [call["name"] for call in model_message.tool_calls]
    updated_message = cast(AIMessage, update["messages"][0])
    return [call["name"] for call in updated_message.tool_calls]


def test_policy_tool_sequence_uses_phase_without_question_matching() -> None:
    assert _enforced_tool_names(
        {"question": "어떤 계산인지 묻는 문장"},
        _ISA_TOOL,
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
        SEARCH_DOCUMENTS_TOOL_NAME,
    ) == [SEARCH_DOCUMENTS_TOOL_NAME]

    assert _enforced_tool_names(
        {
            "question": "계산기 이름과 일치하지 않는 표현",
            "search_result": SearchResult(execution_status="completed"),
            "calculations": [],
        },
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
        _DC_TOOL,
        _ISA_TOOL,
    ) == [_DC_TOOL]

    assert _enforced_tool_names(
        {
            "search_result": SearchResult(execution_status="completed"),
            "calculations": [{"calculator_id": "any"}],
        },
        _ISA_TOOL,
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
    ) == [SUBMIT_DOMAIN_RESULT_TOOL_NAME]


def test_policy_tool_sequence_keeps_only_one_submit_call() -> None:
    assert _enforced_tool_names(
        {"search_result": SearchResult(execution_status="completed"), "calculations": []},
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
    ) == [SUBMIT_DOMAIN_RESULT_TOOL_NAME]


def test_policy_no_evidence_preserves_specific_missing_conditions() -> None:
    result = _build_policy_result(
        search_result=SearchResult(execution_status="completed"),
        calculations=[],
        status="conditional",
        conclusion="근거 없이 작성한 결론",
        missing_conditions=["계좌의 현재 상태 확인 필요"],
        warnings=["근거 없는 경고"],
        evidence_chunk_ids=[],
    )

    assert result["decision"] == {
        "status": "undetermined",
        "conclusion": "제공 문서에서 관련 근거를 확인하지 못해 판단할 수 없습니다.",
        "missing_conditions": ["계좌의 현재 상태 확인 필요"],
    }
    assert result["warnings"] == ["검색된 원문 청크 중 결론에 사용한 근거가 제출되지 않았습니다."]


def test_policy_prompt_requires_complete_objective_coverage() -> None:
    prompt = load_policy_agent_prompt()

    assert "여러 결과를 요구하면 각\n  결과를 모두 결론 또는 누락 조건에 대응" in prompt
    assert "상위\n  표현은 구체 조건이나 절차" in prompt
    assert "`objective`의 모든 판단 항목" in prompt
