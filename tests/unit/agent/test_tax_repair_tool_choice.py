"""TaxPayout의 범용 Tool 단계와 결과 조립을 검증한다."""

from typing import Any

from langchain.messages import AIMessage, HumanMessage

from pension_agent.agent.search import SearchChunkPayload, SearchResult
from pension_agent.agent.tax_payout.agent import load_tax_payout_agent_prompt
from pension_agent.agent.tax_payout.react import (
    EnforceTaxPayoutToolSequence,
    RequireTaxPayoutTool,
    TaxPayoutModelCallLimit,
    _build_tax_payout_result,
    _safe_terminal_tax_payout_result,
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


def _kept_tool_names(
    state: dict[str, Any], *tool_names: str, max_model_calls: int = 5
) -> list[str]:
    message = _tool_message(*tool_names)
    update = EnforceTaxPayoutToolSequence(max_model_calls=max_model_calls).after_model(
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


# ---------------------------------------------------------------------------
# #159 static statutory fact 선택 — item 10의 A~D, H, I, J.
# ---------------------------------------------------------------------------

_DOC41_CHUNK_ID = "4c8f5763-1014-5d69-a612-5ca1c897a0b1"


def _doc41_chunk() -> SearchChunkPayload:
    return SearchChunkPayload(
        chunk_id=_DOC41_CHUNK_ID,
        source_file_name="doc41.docx",
        document_type=DocumentType.PENSION_REFERENCE,
        chunk_index=0,
        title="doc41",
        locator="문서 내 청크 1",
        content=(
            "연금저축과 IRP는 합산해서 연1,800만원까지 입금이 가능하다. "
            "연금저축은 연600만원, IRP는 연금저축 납입액을 포함해서 연900만원이다."
        ),
    )


def test_fact_A_combined_tax_credit_selection_renders_canonical_text() -> None:
    result = _build_tax_payout_result(
        search_result=SearchResult(execution_status="completed", retrieved_chunks=[_doc41_chunk()]),
        calculations=[],
        status="determined",
        conclusion="합산 세액공제 한도를 안내합니다.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[_DOC41_CHUNK_ID],
        selected_fact_ids=["combined_pension_tax_credit_limit"],
    )

    assert result["verified_numeric_statements"] == [
        {
            "source_type": "statutory_fact",
            "source_id": "combined_pension_tax_credit_limit",
            "text": "연금저축과 IRP를 합산한 세액공제 대상 납입한도는 900만원입니다.",
        }
    ]


def test_fact_B_total_contribution_limit_selection() -> None:
    result = _build_tax_payout_result(
        search_result=SearchResult(execution_status="completed", retrieved_chunks=[_doc41_chunk()]),
        calculations=[],
        status="determined",
        conclusion="전체 납입한도를 안내합니다.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[_DOC41_CHUNK_ID],
        selected_fact_ids=["annual_pension_account_contribution_limit"],
    )

    assert result["verified_numeric_statements"][0]["text"] == (
        "연금저축과 IRP를 합산한 연간 납입한도는 1,800만원입니다."
    )


def test_fact_C_pension_savings_only_tax_credit_selection() -> None:
    result = _build_tax_payout_result(
        search_result=SearchResult(execution_status="completed", retrieved_chunks=[_doc41_chunk()]),
        calculations=[],
        status="determined",
        conclusion="연금저축 단독 세액공제 한도를 안내합니다.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[_DOC41_CHUNK_ID],
        selected_fact_ids=["pension_savings_tax_credit_limit"],
    )

    assert result["verified_numeric_statements"][0]["text"] == (
        "연금저축 단독 세액공제 대상 납입한도는 600만원입니다."
    )


def test_fact_D_both_contribution_and_tax_credit_selected_together() -> None:
    result = _build_tax_payout_result(
        search_result=SearchResult(execution_status="completed", retrieved_chunks=[_doc41_chunk()]),
        calculations=[],
        status="determined",
        conclusion="납입한도와 세액공제 한도를 함께 안내합니다.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[_DOC41_CHUNK_ID],
        selected_fact_ids=[
            "annual_pension_account_contribution_limit",
            "combined_pension_tax_credit_limit",
        ],
    )

    texts = {statement["text"] for statement in result["verified_numeric_statements"]}
    assert "연금저축과 IRP를 합산한 연간 납입한도는 1,800만원입니다." in texts
    assert "연금저축과 IRP를 합산한 세액공제 대상 납입한도는 900만원입니다." in texts


def test_fact_H_qualitative_only_omits_verified_numeric_statements() -> None:
    """H: fact_id를 선택하지 않으면(정성 질문) verified_numeric_statements가 없다."""

    result = _build_tax_payout_result(
        search_result=SearchResult(execution_status="completed", retrieved_chunks=[_doc41_chunk()]),
        calculations=[],
        status="determined",
        conclusion="연금저축과 IRP는 세제상 이러한 개념적 차이가 있습니다.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[_DOC41_CHUNK_ID],
        selected_fact_ids=[],
    )

    assert "verified_numeric_statements" not in result


def test_fact_I_calculation_required_path_is_unaffected() -> None:
    """I: calculation-only 제출은 selected_fact_ids 없이도 기존과 동일하게 동작한다."""

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
        "units": {"annual_total_wages": "KRW", "minimum_employer_contribution": "KRW"},
        "warnings": [],
    }

    result = _build_tax_payout_result(
        search_result=SearchResult(execution_status="completed", retrieved_chunks=[chunk]),
        calculations=[calculation],
        status="determined",
        conclusion="계산 결과를 안내합니다.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[chunk_id],
    )

    assert "verified_numeric_statements" not in result
    assert "DC 최소 사용자 부담금" in result["decision"]["conclusion"]


def test_fact_J_static_plus_calculation_mixed_coexist() -> None:
    """J: static fact와 calculation이 한 제출에 함께 있어도 서로 간섭하지 않는다."""

    calc_chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    calc_chunk = SearchChunkPayload(
        chunk_id=calc_chunk_id,
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
        "units": {"annual_total_wages": "KRW", "minimum_employer_contribution": "KRW"},
        "warnings": [],
    }

    result = _build_tax_payout_result(
        search_result=SearchResult(
            execution_status="completed", retrieved_chunks=[calc_chunk, _doc41_chunk()]
        ),
        calculations=[calculation],
        status="determined",
        conclusion="계산 결과와 법정 한도를 함께 안내합니다.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[calc_chunk_id, _DOC41_CHUNK_ID],
        selected_fact_ids=["combined_pension_tax_credit_limit"],
    )

    assert "DC 최소 사용자 부담금" in result["decision"]["conclusion"]
    assert result["verified_numeric_statements"] == [
        {
            "source_type": "statutory_fact",
            "source_id": "combined_pension_tax_credit_limit",
            "text": "연금저축과 IRP를 합산한 세액공제 대상 납입한도는 900만원입니다.",
        }
    ]


def test_fact_K_unknown_fact_id_is_dropped_not_rejected() -> None:
    """K: unknown fact_id가 섞여도 제출 전체가 거부되지 않고, 그 fact만 빠진다."""

    result = _build_tax_payout_result(
        search_result=SearchResult(execution_status="completed", retrieved_chunks=[_doc41_chunk()]),
        calculations=[],
        status="determined",
        conclusion="세액공제 한도를 안내합니다.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[_DOC41_CHUNK_ID],
        selected_fact_ids=["combined_pension_tax_credit_limit", "hallucinated_fact_id"],
    )

    assert [s["source_id"] for s in result["verified_numeric_statements"]] == [
        "combined_pension_tax_credit_limit"
    ]


def test_fact_regression_wrong_neighbor_selection_never_mislabels_the_number() -> None:
    """item 9 핵심 회귀: '다 합쳐서' 질문에서 contribution_limit(1,800만원)을 골라도
    그 문장은 '납입한도'로만 렌더링되고, 세액공제 한도로 오인되지 않는다."""

    result = _build_tax_payout_result(
        search_result=SearchResult(execution_status="completed", retrieved_chunks=[_doc41_chunk()]),
        calculations=[],
        status="determined",
        conclusion="연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[_DOC41_CHUNK_ID],
        selected_fact_ids=["annual_pension_account_contribution_limit"],
    )

    text = result["verified_numeric_statements"][0]["text"]
    assert "1,800만원" in text
    assert "납입한도" in text
    assert "세액공제" not in text  # registry가 render하므로 role이 뒤섞이지 않는다


# ---------------------------------------------------------------------------
# #158 terminalization — static fact producer 위로 이식.
# ---------------------------------------------------------------------------


def test_tax_sequence_forces_submit_only_on_last_call_budget() -> None:
    """마지막으로 허용된 모델 호출에서는 새 계산 시도 없이 submit만 허용한다 (#158)."""

    assert _kept_tool_names(
        {
            "search_result": SearchResult(execution_status="completed"),
            "run_model_call_count": 4,
        },
        _SECOND_CALCULATOR,
        _SUBMIT_TOOL,
        max_model_calls=5,
    ) == [_SUBMIT_TOOL]


def test_tax_sequence_still_allows_search_near_call_budget_exhaustion() -> None:
    """검색을 아직 못했다면 예산이 임박해도 search_documents는 계속 허용한다 (#158)."""

    assert _kept_tool_names(
        {"run_model_call_count": 4},
        _SEARCH_TOOL,
        max_model_calls=5,
    ) == [_SEARCH_TOOL]


def test_call_limit_middleware_sets_safe_domain_result_on_exhaustion() -> None:
    """모델 호출 한도에 도달하면 None 대신 안전한 terminal DomainResult를 state에 채운다 (#158)."""

    update = TaxPayoutModelCallLimit(max_model_calls=2).before_model(
        {
            "run_model_call_count": 2,
            "search_result": SearchResult(execution_status="completed"),
        },
        None,
    )

    assert update is not None
    assert update["jump_to"] == "end"
    domain_result = update["domain_result"]
    assert domain_result["execution_status"] == "completed"
    assert domain_result["decision"]["status"] == "undetermined"
    assert domain_result["decision"]["missing_conditions"]


def test_call_limit_middleware_does_not_intervene_before_limit() -> None:
    assert (
        TaxPayoutModelCallLimit(max_model_calls=5).before_model({"run_model_call_count": 3}, None)
        is None
    )


def test_safe_terminal_result_fails_cleanly_without_search() -> None:
    result = _safe_terminal_tax_payout_result({})

    assert result["execution_status"] == "failed"
    assert result["evidence"] == []
    assert result["calculations"] == []
    assert "error" in result


def test_safe_terminal_result_is_undetermined_without_evidence() -> None:
    result = _safe_terminal_tax_payout_result(
        {"search_result": SearchResult(execution_status="completed")}
    )

    assert result["decision"]["status"] == "undetermined"


def test_safe_terminal_result_preserves_calculations_and_linked_evidence() -> None:
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
                "origin": "evidence",
                "text": "연간임금총액은 1,200만원",
                "chunk_id": chunk_id,
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
        "warnings": ["참고용 안내"],
    }

    result = _safe_terminal_tax_payout_result(
        {
            "search_result": SearchResult(execution_status="completed", retrieved_chunks=[chunk]),
            "calculations": [calculation],
        }
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"]
    assert "DC 최소 사용자 부담금" in result["decision"]["conclusion"]
    assert [item["chunk_id"] for item in result["evidence"]] == [chunk_id]
    assert result["calculations"] == [calculation]
    assert "참고용 안내" in result["warnings"]


def test_safe_terminal_result_never_fabricates_verified_numeric_statements() -> None:
    """H: safe terminalization은 static fact를 새로 선택·검증하지 않는다.

    domain_result는 successful submit_domain_result Command로만 채워지므로,
    이 경로(예산 소진)에 도달했다는 것 자체가 그런 성공한 제출이 없었다는
    뜻이다 — verified_numeric_statements 키가 아예 생기지 않아야 한다.
    """

    result = _safe_terminal_tax_payout_result(
        {
            "search_result": SearchResult(
                execution_status="completed", retrieved_chunks=[_doc41_chunk()]
            )
        }
    )

    assert "verified_numeric_statements" not in result
