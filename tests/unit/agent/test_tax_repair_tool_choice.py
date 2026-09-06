"""TaxPayout의 범용 Tool 단계와 결과 조립을 검증한다."""

from typing import Any

from langchain.messages import AIMessage, HumanMessage

from pension_agent.agent.search import SearchChunkPayload, SearchResult
from pension_agent.agent.tax_payout.agent import load_tax_payout_agent_prompt
from pension_agent.agent.tax_payout.react import (
    EnforceTaxPayoutToolSequence,
    RequireTaxPayoutTool,
    _build_tax_payout_result,
)
from pension_agent.core import DocumentType

_SEARCH_TOOL = "search_documents"
_SUBMIT_TOOL = "submit_domain_result"
_FIRST_CALCULATOR = "calculate_pension_tax_credit"
_SECOND_CALCULATOR = "calculate_dc_retirement_benefit"


def _tool_message(*tool_names: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": tool_name,
                "args": {},
                "id": f"call-{index}",
                "type": "tool_call",
            }
            for index, tool_name in enumerate(tool_names)
        ],
    )


def _kept_tool_names(state: dict[str, Any], *tool_names: str) -> list[str]:
    message = _tool_message(*tool_names)
    update = EnforceTaxPayoutToolSequence().after_model(
        {**state, "messages": [message]},
        None,
    )
    kept = message if update is None else update["messages"][0]
    return [call["name"] for call in kept.tool_calls]


def test_require_tax_tool_uses_short_generic_guidance_after_search() -> None:
    update = RequireTaxPayoutTool().after_model(
        {
            "search_result": SearchResult(execution_status="completed"),
            "calculations": [],
            "messages": [AIMessage(content="근거를 검토한 자유서술")],
        },
        None,
    )

    assert update is not None
    message = update["messages"][0]
    assert isinstance(message, HumanMessage)
    assert message.additional_kwargs == {}
    assert "Calculation Tool 하나" in message.content
    assert "submit_domain_result Tool" in message.content
    assert "바로 앞 판단" not in message.content
    assert len(message.content) < 180


def test_require_tax_tool_allows_another_calculation_after_one_result() -> None:
    update = RequireTaxPayoutTool().after_model(
        {
            "search_result": SearchResult(execution_status="completed"),
            "calculations": [{"calculator_id": "pension_tax_credit"}],
            "messages": [AIMessage(content="첫 계산 결과를 설명한 자유서술")],
        },
        None,
    )

    assert update is not None
    message = update["messages"][0]
    assert isinstance(message, HumanMessage)
    assert "추가 산출이 필요하면" in message.content
    assert "submit_domain_result Tool" in message.content


def test_require_tax_tool_requests_search_before_grounded_judgment() -> None:
    update = RequireTaxPayoutTool().after_model(
        {"messages": [AIMessage(content="바로 답변")], "calculations": []},
        None,
    )

    assert update is not None
    message = update["messages"][0]
    assert isinstance(message, HumanMessage)
    assert "search_documents Tool" in message.content


def test_tax_sequence_blocks_calculation_before_search() -> None:
    assert _kept_tool_names(
        {},
        _FIRST_CALCULATOR,
        _SEARCH_TOOL,
        _SUBMIT_TOOL,
    ) == [_SEARCH_TOOL]


def test_tax_sequence_keeps_one_calculation_per_model_response() -> None:
    assert _kept_tool_names(
        {"search_result": SearchResult(execution_status="completed")},
        _FIRST_CALCULATOR,
        _SECOND_CALCULATOR,
        _SUBMIT_TOOL,
    ) == [_FIRST_CALCULATOR]


def test_tax_sequence_allows_a_different_calculation_on_later_turn() -> None:
    assert _kept_tool_names(
        {
            "search_result": SearchResult(execution_status="completed"),
            "calculations": [{"calculator_id": "pension_tax_credit"}],
            "question": "표현과 무관한 질문",
        },
        _SECOND_CALCULATOR,
        _SUBMIT_TOOL,
    ) == [_SECOND_CALCULATOR]


def test_tax_sequence_keeps_only_first_submit_without_separate_guard() -> None:
    assert _kept_tool_names(
        {"search_result": SearchResult(execution_status="completed")},
        _SUBMIT_TOOL,
        _SUBMIT_TOOL,
    ) == [_SUBMIT_TOOL]


def test_tax_prompt_contains_eight_generic_contracts_and_controlled_fallback() -> None:
    prompt = load_tax_payout_agent_prompt()

    assert all(f"## {index}." in prompt for index in range(1, 9))
    assert "Calculation Tool 미사용 fallback" in prompt
    assert "LLM이 최종 산출값까지 계산할 수 있다" in prompt
    assert "실제 사용자별 산출값을 요청하지 않은" in prompt
    assert "개인별 계산 입력이 없다는\n  이유만으로 `missing_conditions`" in prompt
    assert "공식·입력·대입 과정·결과·단위" in prompt
    assert "Tool 입력 validation이 실패한 경우에는 fallback으로\n  우회하지 않는다" in prompt
    assert "한 모델 응답에서는 Calculation Tool 하나만 호출한다" in prompt
    assert "typed calculation output" in prompt
    assert "calculate_" not in prompt
    assert not any(marker in prompt for marker in ("#113", "#114", "#115", "#116", "#117", "#118"))


def test_calculation_result_keeps_summary_explanation_and_numeric_warning() -> None:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    chunk = SearchChunkPayload(
        chunk_id=chunk_id,
        source_file_name="guide.pdf",
        document_type=DocumentType.PENSION_REFERENCE,
        chunk_index=0,
        title="부담금 안내",
        locator="1페이지",
        content="연간임금총액을 기준으로 사용자 부담금을 산정합니다.",
    )
    calculation = {
        "calculator_id": "dc_minimum_employer_contribution",
        "inputs": {"annual_total_wages_krw": "12000000"},
        "input_sources": {
            "annual_total_wages_krw": {
                "origin": "question",
                "text": "연간임금총액은 1,200만원",
                "chunk_id": None,
            }
        },
        "outputs": {
            "annual_total_wages": "12000000",
            "minimum_employer_contribution": "1000000",
        },
        "units": {
            "annual_total_wages": "KRW",
            "minimum_employer_contribution": "KRW",
        },
        "warnings": [],
    }

    result = _build_tax_payout_result(
        search_result=SearchResult(execution_status="completed", retrieved_chunks=[chunk]),
        calculations=[calculation],
        status="determined",
        conclusion="이 계산은 질문에 명시된 연간임금총액에 적용한 결과입니다.",
        missing_conditions=[],
        warnings=["입력 금액 1,200만원의 기준기간을 확인하세요."],
        evidence_chunk_ids=[chunk_id],
    )

    conclusion = result["decision"]["conclusion"]
    assert "검증된 Python 계산 결과" in conclusion
    assert "DC 최소 사용자 부담금" in conclusion
    assert "근거 기반 설명" in conclusion
    assert "질문에 명시된 연간임금총액" in conclusion
    assert result["warnings"] == ["입력 금액 1,200만원의 기준기간을 확인하세요."]
