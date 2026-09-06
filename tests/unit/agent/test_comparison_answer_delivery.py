"""비교 Tool의 완성 답안이 재작성이나 셀 검사 없이 API까지 전달되는지 확인한다."""

from typing import Any

import pytest
from langchain_core.messages import AIMessage

from pension_agent.agent.contracts import DomainResult, validate_domain_result
from pension_agent.agent.contracts.domain import DecisionStatus
from pension_agent.agent.orchestration import AnswerService, build_domain_tool_result
from pension_agent.api.presentation import build_answer_response


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _comparison() -> DomainResult:
    answer = "테스트 상품의 위험을 10%라고 작성한 비교 답안입니다."
    return {
        "domain": "product",
        "execution_status": "completed",
        "comparison_answer": answer,
        "decision": {
            "status": "determined",
            "conclusion": answer,
            "missing_conditions": ["사용자가 선택한 투자기간 확인 필요"],
        },
        "evidence": [
            {
                "chunk_id": "chunk-1",
                "source_file_name": "fund.pdf",
                "title": "투자위험",
                "locator": "1쪽",
                "content": "이 테스트 근거에는 구체적인 위험 수치가 없습니다.",
            }
        ],
        "calculations": [],
        "warnings": ["공시 기준일 확인 필요"],
    }


class _Supervisor:
    def __init__(self, results: list[DomainResult]) -> None:
        self.results = results

    async def ainvoke(self, input: dict[str, Any], *, context: Any) -> dict[str, Any]:
        del context
        return {
            **input,
            "domain_results": self.results,
            "messages": [AIMessage(content="Main이 임의로 다시 작성한 내용입니다.")],
        }


def test_finished_comparison_does_not_run_answer_or_decision_consistency_checks() -> None:
    domain = _comparison()
    validate_domain_result(domain)
    tool_result = build_domain_tool_result(domain)
    assert tool_result["comparison_answer_ready"] is True
    assert tool_result["decision"] == domain["decision"]
    assert "comparison_result" not in tool_result
    assert "comparison_answer" not in tool_result


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["determined", "not_applicable"])
async def test_finished_comparison_is_preserved_through_exact_five_field_api(
    status: DecisionStatus,
) -> None:
    domain = _comparison()
    domain["decision"]["status"] = status
    result = await AnswerService(_Supervisor([domain])).run(
        question_id="comparison-answer", question="두 상품을 비교해주세요."
    )
    response = build_answer_response(result).model_dump()
    assert set(response) == {
        "question_id",
        "question",
        "retrieved_context",
        "think_trace",
        "answer",
    }
    assert response["answer"].startswith(domain["comparison_answer"])
    assert "Main이 임의로" not in response["answer"]
    assert "fund.pdf" not in response["answer"]
    assert "근거 문서:" not in response["answer"]
    assert "공시 기준일 확인 필요" in response["answer"]
    assert "사용자가 선택한 투자기간 확인 필요" in response["answer"]
    assert "검증된 상품 비교" not in response["think_trace"]
    assert len(response["retrieved_context"]) == 1
    assert response["retrieved_context"][0]["source_file_name"] == "fund.pdf"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "conclusion",
    [
        "테스트 세액공제 한도는 999만원입니다.",
        "테스트 공제율은 99%입니다.",
        "테스트 납입 한도는 900만원입니다.",
        "세액공제를 받지 않은 원금은 비과세입니다. 테스트 한도는 999만원입니다.",
        "테스트 한도는 {{VERIFIED_NUMERIC:tax_payout:unknown-limit}}입니다.",
    ],
)
async def test_finished_comparison_preserves_other_domain_numeric_firewall(
    conclusion: str,
) -> None:
    comparison = _comparison()
    canonical = "테스트 세액공제 한도는 900만원입니다."
    tax: DomainResult = {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": conclusion,
            "missing_conditions": [],
        },
        "evidence": [],
        "calculations": [],
        "warnings": [],
        "verified_numeric_statements": [
            {"source_type": "statutory_fact", "source_id": "test-limit", "text": canonical}
        ],
    }
    result = await AnswerService(_Supervisor([comparison, tax])).run(
        question_id="comparison-mixed", question="상품을 비교하고 세액공제 한도를 알려주세요."
    )
    assert comparison["comparison_answer"] in result.answer.answer
    assert result.answer.answer.count(canonical) == 1
    assert conclusion not in result.answer.answer
    assert "999만원" not in result.answer.answer
    assert "99%" not in result.answer.answer
    assert "unknown-limit" not in result.answer.answer


@pytest.mark.anyio
@pytest.mark.parametrize("with_comparison", [True, False])
async def test_deterministic_assembly_preserves_other_domain_nonnumeric_conclusion(
    with_comparison: bool,
) -> None:
    companion: DomainResult = (
        _comparison()
        if with_comparison
        else {
            "domain": "product",
            "execution_status": "failed",
            "evidence": [],
            "calculations": [],
            "warnings": [],
            "error": "상품 분석을 완료하지 못했습니다.",
        }
    )
    conclusion = "세액공제를 받지 않은 원금은 인출 시 과세하지 않습니다."
    canonical = "테스트 세액공제 납입금의 연금 외 인출에는 기타소득세 16.5%가 적용됩니다."
    tax: DomainResult = {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": "conditional",
            "conclusion": conclusion,
            "missing_conditions": ["납입금의 세액공제 여부 확인"],
        },
        "evidence": [
            {
                "chunk_id": "tax-1",
                "source_file_name": "tax.pdf",
                "title": "인출 과세",
                "locator": "1쪽",
                "content": conclusion + " " + canonical,
            }
        ],
        "calculations": [],
        "warnings": ["인출 재원 구분 필요"],
        "verified_numeric_statements": [
            {"source_type": "statutory_fact", "source_id": "test-tax-rate", "text": canonical}
        ],
    }

    result = await AnswerService(_Supervisor([companion, tax])).run(
        question_id="comparison-mixed-tax",
        question="상품을 비교하고 납입 재원별 인출 과세를 설명해주세요.",
    )
    response = build_answer_response(result).model_dump()

    assert response["answer"].count(conclusion) == 1
    assert response["answer"].count(canonical) == 1
    assert "납입금의 세액공제 여부 확인" in response["answer"]
    assert "인출 재원 구분 필요" in response["answer"]
    assert "Main이 임의로" not in response["answer"]
    assert any(chunk["chunk_id"] == "tax-1" for chunk in response["retrieved_context"])
    assert result.state["domain_results"] == [companion, tax]
    if with_comparison:
        assert companion["comparison_answer"] in response["answer"]
    else:
        assert companion["error"] in response["answer"]
