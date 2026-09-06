"""셀 없이 전달하는 비교 답안과 미완료 안내의 공유 계약을 검증한다."""

from typing import Any

import pytest
from langchain_core.messages import AIMessage
from pydantic import TypeAdapter

from pension_agent.agent.contracts import ComparisonTarget, DomainResult, validate_domain_result
from pension_agent.agent.orchestration import AnswerService, build_domain_tool_result
from pension_agent.agent.product.comparison_submission import unresolved_comparison_result
from pension_agent.api.presentation import build_answer_response


def comparison_domain() -> DomainResult:
    answer = "솔로몬 단기국공채와 솔로몬 장기국공채의 가격이 10% 하락할 수 있습니다."
    return {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "conditional",
            "conclusion": answer,
            "missing_conditions": ["투자기간 확인 필요"],
        },
        "comparison_answer": answer,
        "evidence": [
            {
                "chunk_id": "chunk-1",
                "source_file_name": "fund-1.pdf",
                "title": "위험",
                "locator": "1쪽",
                "content": "가격이 10% 하락할 수 있습니다.",
            }
        ],
        "calculations": [],
        "warnings": ["문서 기준일 확인 필요"],
    }


def test_comparison_answer_contract_and_main_tool_preserve_body_once() -> None:
    result = comparison_domain()
    validate_domain_result(result)
    normalized = TypeAdapter(DomainResult).validate_python(result)
    assert normalized["comparison_answer"] == result["comparison_answer"]
    tool_result = build_domain_tool_result(result)
    assert tool_result["comparison_answer_ready"] is True
    assert tool_result["decision"]["conclusion"] == result["comparison_answer"]
    assert "comparison_answer" not in tool_result
    assert "comparison_result" not in tool_result
    assert "evidence" not in tool_result


@pytest.mark.parametrize("mutation", ["wrong_domain", "failed", "calculations", "catalog"])
def test_comparison_answer_rejects_incompatible_domain_results(mutation: str) -> None:
    result = comparison_domain()
    if mutation == "wrong_domain":
        result["domain"] = "policy"
    elif mutation == "failed":
        result.update(execution_status="failed", error="실패", evidence=[])
        del result["decision"]
    elif mutation == "calculations":
        result["calculations"] = [
            {
                "calculator_id": "unused",
                "inputs": {},
                "input_sources": {},
                "outputs": {},
                "units": {},
                "warnings": [],
            }
        ]
    else:
        result["catalog_result"] = {
            "route": "browse_catalog",
            "provider": None,
            "return_mode": "count",
            "total_count": 0,
            "items": [],
            "catalog_version": "v1",
        }
    with pytest.raises(ValueError):
        validate_domain_result(result)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class ComparisonSupervisor:
    """도메인 결과와 채택하면 안 되는 Main 재작성 답변을 반환한다."""

    def __init__(self, results: list[DomainResult]) -> None:
        self.results = results

    async def ainvoke(self, input: dict[str, Any], *, context: Any) -> dict[str, Any]:
        return {
            **input,
            "domain_results": self.results,
            "messages": [AIMessage(content="단기채가 원금을 보장하므로 무조건 추천합니다.")],
        }


@pytest.mark.anyio
async def test_unresolved_comparison_keeps_names_and_reasons_without_cells_or_appendix() -> None:
    targets: list[ComparisonTarget] = [
        {
            "target_id": "short",
            "mention_parts": ["솔로몬", "단기"],
            "resolution_status": "single",
            "product_code": "KR5153420063",
            "official_name": "솔로몬 단기국공채",
            "provider": "미래에셋",
        },
        {
            "target_id": "unknown",
            "mention_parts": ["새봄", "원금보장"],
            "resolution_status": "not_found",
        },
        {
            "target_id": "ambiguous",
            "mention_parts": ["솔로몬", "국공채"],
            "resolution_status": "ambiguous",
        },
    ]
    reason = "서로 다른 상품을 2개 이상 식별하지 못해 비교를 실행하지 않았습니다."
    additional = "정확한 비교 대상을 확인할 수 있는 상품 정보가 필요합니다."
    domain = unresolved_comparison_result(
        targets=targets, limitation=reason, limitations=[reason, additional]
    )
    validate_domain_result(domain)

    result = await AnswerService(ComparisonSupervisor([domain])).run(
        question_id="Q-unresolved", question="솔로몬 단기, 새봄 원금보장, 솔로몬 국공채 비교"
    )
    response = build_answer_response(result).model_dump()

    assert set(response) == {
        "question_id",
        "question",
        "retrieved_context",
        "think_trace",
        "answer",
    }
    assert response["answer"] == domain["comparison_answer"] == domain["decision"]["conclusion"]
    assert domain["decision"]["status"] == "undetermined"
    assert response["answer"].count(reason) == 1
    assert response["answer"].count(additional) == 1
    assert "솔로몬 단기국공채" in response["answer"]
    assert "새봄 원금보장 (카탈로그에서 찾지 못함)" in response["answer"]
    assert "솔로몬 국공채 (후보가 여러 개여서 미식별)" in response["answer"]
    assert response["retrieved_context"] == []
    assert "무조건 추천" not in response["answer"]
    assert "|" not in response["answer"]
    assert "근거 문서:" not in response["answer"]
    assert "comparison_result" not in domain
    assert "coverage" not in response["think_trace"]
    assert "compare_products에서" not in response["think_trace"]
    assert build_domain_tool_result(domain)["comparison_answer_ready"] is True


@pytest.mark.anyio
async def test_mixed_comparison_preserves_other_domain_calculations_and_catalog() -> None:
    other: DomainResult = {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": "conditional",
            "conclusion": "연금수령한도는 999원입니다.",
            "missing_conditions": ["세율 확인 필요"],
        },
        "calculations": [
            {
                "calculator_id": "pension_withdrawal_limit",
                "inputs": {"account_valuation_krw": "10000000", "pension_year": 1},
                "input_sources": {
                    "account_valuation_krw": {
                        "origin": "question",
                        "text": "평가액 1천만원",
                        "chunk_id": None,
                    },
                    "pension_year": {"origin": "question", "text": "1년차", "chunk_id": None},
                },
                "outputs": {"withdrawal_limit": "1200000.0"},
                "units": {"withdrawal_limit": "KRW"},
                "warnings": ["반올림 규칙 미확인"],
            }
        ],
        "warnings": ["수령 조건 확인"],
        "evidence": [],
    }
    catalog: DomainResult = {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": "카탈로그 0개",
            "missing_conditions": [],
        },
        "calculations": [],
        "warnings": [],
        "evidence": [
            {
                "chunk_id": "catalog",
                "source_file_name": "catalog.json",
                "title": "조회",
                "locator": "전체",
                "content": "0개",
            }
        ],
        "catalog_result": {
            "route": "browse_catalog",
            "provider": None,
            "return_mode": "count",
            "total_count": 0,
            "items": [],
            "catalog_version": "v1",
        },
    }
    failed: DomainResult = {
        "domain": "policy",
        "execution_status": "timeout",
        "evidence": [],
        "calculations": [],
        "warnings": [],
        "error": "실행 시간이 초과됐습니다.",
    }
    result = await AnswerService(
        ComparisonSupervisor([comparison_domain(), other, catalog, failed])
    ).run(question_id="Q-mixed", question="비교와 수령한도, 전체 상품 수, 이전 조건")
    answer = result.answer.answer
    for expected in (
        "솔로몬 단기국공채",
        "세율 확인 필요",
        "1200000.0 KRW",
        "반올림 규칙 미확인",
        "수령 조건 확인",
        "전체 상품은 총 0개",
        "업무·제도 분석을 완료하지 못했습니다",
    ):
        assert expected in answer
    assert "무조건 추천" not in answer
    assert "999원" not in answer


@pytest.mark.anyio
async def test_mixed_comparison_preserves_document_numeric_conclusion_and_conditions() -> None:
    conclusion = "테스트 문서의 연간 납입 한도는 1800만원입니다."
    tax: DomainResult = {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": "conditional",
            "conclusion": conclusion,
            "missing_conditions": ["올해 납입액 확인 필요"],
        },
        "evidence": [
            {
                "chunk_id": "tax-limit",
                "source_file_name": "tax.pdf",
                "title": "납입 한도",
                "locator": "1쪽",
                "content": conclusion,
            }
        ],
        "calculations": [],
        "warnings": ["계좌 합산 기준 확인 필요"],
    }

    result = await AnswerService(ComparisonSupervisor([comparison_domain(), tax])).run(
        question_id="Q-comparison-tax-limit",
        question="솔로몬 단기·장기를 비교하고 연간 납입 한도를 알려주세요.",
    )

    answer = result.answer.answer
    for expected in (
        "솔로몬 단기국공채",
        "솔로몬 장기국공채",
        "가격이 10% 하락할 수 있습니다.",
        conclusion,
        "올해 납입액 확인 필요",
        "계좌 합산 기준 확인 필요",
        "tax.pdf",
    ):
        assert expected in answer
    assert answer.count(conclusion) == 1
    assert "무조건 추천" not in answer
    assert result.state["domain_results"][1] == tax
