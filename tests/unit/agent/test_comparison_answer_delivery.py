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
    assert all(isinstance(value, str) for value in response.values())
    assert response["answer"].startswith(domain["comparison_answer"])
    assert "Main이 임의로" not in response["answer"]
    assert "fund.pdf" not in response["answer"]
    assert "근거 문서:" not in response["answer"]
    assert "공시 기준일 확인 필요" in response["answer"]
    assert "사용자가 선택한 투자기간 확인 필요" in response["answer"]
    assert "검증된 상품 비교" not in response["think_trace"]
    assert response["retrieved_context"] == (
        "[문서 1]\n"
        "chunk_id: chunk-1\n"
        "source_file_name: fund.pdf\n"
        "title: 투자위험\n"
        "locator: 1쪽\n"
        "content:\n"
        "이 테스트 근거에는 구체적인 위험 수치가 없습니다."
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "conclusion",
    [
        "테스트 세액공제 한도는 900만원입니다.",
        "테스트 공제율은 16.5%입니다.",
        "테스트 연금수령 연령은 55세입니다.",
        "세액공제를 받지 않은 원금은 비과세입니다. 테스트 한도는 900만원입니다.",
    ],
)
async def test_finished_comparison_preserves_other_domain_document_numeric_conclusion(
    conclusion: str,
) -> None:
    comparison = _comparison()
    tax: DomainResult = {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": conclusion,
            "missing_conditions": [],
        },
        "evidence": [
            {
                "chunk_id": "tax-numeric",
                "source_file_name": "tax.pdf",
                "title": "세제 조건",
                "locator": "1쪽",
                "content": conclusion,
            }
        ],
        "calculations": [],
        "warnings": [],
    }
    result = await AnswerService(_Supervisor([comparison, tax])).run(
        question_id="comparison-mixed", question="상품을 비교하고 세액공제 한도를 알려주세요."
    )
    response = build_answer_response(result).model_dump()
    assert all(isinstance(value, str) for value in response.values())
    assert comparison["comparison_answer"] in response["answer"]
    assert response["answer"].count(conclusion) == 1
    assert "tax.pdf" in response["answer"]
    assert "Main이 임의로" not in response["answer"]
    context = response["retrieved_context"]
    assert context.count("[문서 ") == 2
    assert context.startswith("[문서 1]\nchunk_id: chunk-1\n")
    assert "\nsource_file_name: fund.pdf\n" in context
    assert "\n\n[문서 2]\nchunk_id: tax-numeric\n" in context
    assert "\nsource_file_name: tax.pdf\n" in context
    assert context.endswith(f"content:\n{conclusion}")
    assert result.state["domain_results"] == [comparison, tax]


@pytest.mark.anyio
@pytest.mark.parametrize("with_comparison", [True, False])
async def test_deterministic_assembly_preserves_other_domain_numeric_and_nonnumeric_conclusion(
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
    nonnumeric_conclusion = "세액공제를 받지 않은 원금은 인출 시 과세하지 않습니다."
    numeric_conclusion = "테스트 세액공제 납입금의 연금 외 인출에는 기타소득세 16.5%가 적용됩니다."
    conclusion = nonnumeric_conclusion + " " + numeric_conclusion
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
                "content": conclusion,
            }
        ],
        "calculations": [],
        "warnings": ["인출 재원 구분 필요"],
    }

    result = await AnswerService(_Supervisor([companion, tax])).run(
        question_id="comparison-mixed-tax",
        question="상품을 비교하고 납입 재원별 인출 과세를 설명해주세요.",
    )
    response = build_answer_response(result).model_dump()

    assert all(isinstance(value, str) for value in response.values())
    assert response["answer"].count(conclusion) == 1
    assert response["answer"].count(nonnumeric_conclusion) == 1
    assert response["answer"].count(numeric_conclusion) == 1
    assert "납입금의 세액공제 여부 확인" in response["answer"]
    assert "인출 재원 구분 필요" in response["answer"]
    assert "Main이 임의로" not in response["answer"]
    context = response["retrieved_context"]
    assert context.count("[문서 ") == (2 if with_comparison else 1)
    assert "\nchunk_id: tax-1\nsource_file_name: tax.pdf\n" in context
    assert context.endswith(f"content:\n{conclusion}")
    assert result.state["domain_results"] == [companion, tax]
    if with_comparison:
        assert companion["comparison_answer"] in response["answer"]
        assert context.startswith("[문서 1]\nchunk_id: chunk-1\n")
        assert "\nsource_file_name: fund.pdf\n" in context
        assert "\n\n[문서 2]\nchunk_id: tax-1\n" in context
    else:
        assert companion["error"] in response["answer"]
        assert context.startswith("[문서 1]\nchunk_id: tax-1\n")
        assert "\nsource_file_name: fund.pdf\n" not in context
