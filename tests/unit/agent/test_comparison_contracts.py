"""비교 결과의 대상·셀·근거 관계와 도메인 상태 계약을 검증한다."""

from copy import deepcopy

import pytest
from pydantic import TypeAdapter, ValidationError

from pension_agent.agent.contracts import (
    ComparisonCell,
    ComparisonResult,
    DomainResult,
    comparison_coverage,
    validate_comparison_result,
    validate_domain_result,
)
from pension_agent.agent.orchestration import build_domain_tool_result


def comparison_domain() -> DomainResult:
    comparison: ComparisonResult = {
        "catalog_version": "v1",
        "targets": [
            {
                "target_id": f"target-{index}",
                "mention_parts": [name],
                "resolution_status": "single",
                "product_code": code,
                "official_name": name,
                "provider": "미래에셋",
            }
            for index, (code, name) in enumerate(
                [("KR5153420063", "솔로몬 단기국공채"), ("KR5153420105", "솔로몬 장기국공채")],
                start=1,
            )
        ],
        "criteria": ["risk"],
        "coverage": "complete",
        "cells": [
            {
                "target_id": f"target-{index}",
                "criterion": "risk",
                "status": "supported",
                "finding": "금리 변동으로 가격이 하락할 수 있습니다.",
                "evidence_refs": [{"product_code": code, "chunk_id": f"chunk-{index}"}],
                "limitations": [],
            }
            for index, code in enumerate(["KR5153420063", "KR5153420105"], start=1)
        ],
        "limitations": [],
    }
    return {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "conditional",
            "conclusion": "두 상품에 금리 위험이 있습니다. 투자기간을 확인해야 합니다.",
            "missing_conditions": ["투자기간 확인 필요"],
        },
        "evidence": [
            {
                "chunk_id": f"chunk-{index}",
                "source_file_name": f"fund-{index}.pdf",
                "title": "위험",
                "locator": "1쪽",
                "content": "금리 변동으로 가격이 하락할 수 있습니다.",
            }
            for index in (1, 2)
        ],
        "calculations": [],
        "warnings": ["문서 기준일 확인 필요"],
        "comparison_result": comparison,
    }


def unverified(cell: ComparisonCell) -> None:
    cell.update(
        status="not_verified",
        finding="확인하지 못했습니다.",
        evidence_refs=[],
        limitations=["근거 부족"],
    )


def test_comparison_contract_and_main_tool_preserve_structure() -> None:
    result = comparison_domain()
    validate_domain_result(result)
    normalized = TypeAdapter(DomainResult).validate_python(result)
    assert normalized["comparison_result"] == result["comparison_result"]
    tool_result = build_domain_tool_result(result)
    assert tool_result["comparison_result"] == result["comparison_result"]
    assert "evidence" not in tool_result


@pytest.mark.parametrize("coverage", ["partial", "none"])
def test_partial_and_none_require_conservative_statuses(coverage: str) -> None:
    result = comparison_domain()
    comparison = result["comparison_result"]
    unverified(comparison["cells"][1])
    result["evidence"].pop()
    if coverage == "none":
        unverified(comparison["cells"][0])
        result["evidence"].clear()
    comparison["coverage"] = comparison_coverage(comparison["targets"], comparison["cells"])
    comparison["limitations"] = ["일부 상품 근거 부족"]
    result["decision"]["status"] = "conditional" if coverage == "partial" else "undetermined"
    validate_domain_result(result)
    result["decision"]["status"] = "determined"
    result["decision"]["missing_conditions"] = []
    with pytest.raises(ValueError, match="판단 상태"):
        validate_domain_result(result)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra_target", "extra_criterion"])
def test_cartesian_cells_reject_omissions_duplicates_and_extra(mutation: str) -> None:
    result = comparison_domain()
    comparison = result["comparison_result"]
    if mutation == "missing":
        comparison["cells"].pop()
    elif mutation == "duplicate":
        comparison["cells"].append(deepcopy(comparison["cells"][0]))
    elif mutation == "extra_target":
        comparison["cells"][0]["target_id"] = "unrequested"
    else:
        comparison["cells"][0]["criterion"] = "fees"
    with pytest.raises(ValueError, match="셀"):
        validate_domain_result(result)


@pytest.mark.parametrize("mutation", ["wrong_product", "unknown_chunk", "unused", "duplicate_ref"])
def test_evidence_must_belong_to_target_and_exact_final_union(mutation: str) -> None:
    result = comparison_domain()
    cell = result["comparison_result"]["cells"][0]
    if mutation == "wrong_product":
        cell["evidence_refs"][0]["product_code"] = "KR5153420105"
    elif mutation == "unknown_chunk":
        cell["evidence_refs"][0]["chunk_id"] = "missing"
    elif mutation == "unused":
        result["evidence"].append({**result["evidence"][0], "chunk_id": "unused"})
    else:
        cell["evidence_refs"].append(deepcopy(cell["evidence_refs"][0]))
    with pytest.raises(ValueError):
        validate_domain_result(result)


@pytest.mark.parametrize("status", ["conflicting", "not_comparable"])
def test_non_comparable_and_conflicting_cells_are_partial(status: str) -> None:
    result = comparison_domain()
    comparison = result["comparison_result"]
    for cell in comparison["cells"]:
        cell["status"] = status
        cell["limitations"] = ["문서별 기준시점 차이"]
        if status == "conflicting":
            original_ref = cell["evidence_refs"][0]
            additional_id = original_ref["chunk_id"] + "-other"
            cell["evidence_refs"].append({**original_ref, "chunk_id": additional_id})
            result["evidence"].append({**result["evidence"][0], "chunk_id": additional_id})
    comparison["coverage"] = "partial"
    comparison["limitations"] = ["기준시점 확인 필요"]
    validate_domain_result(result)
    comparison["coverage"] = "complete"
    with pytest.raises(ValueError, match="coverage"):
        validate_domain_result(result)


def test_unresolved_target_cannot_use_document_evidence() -> None:
    result = comparison_domain()
    target = result["comparison_result"]["targets"][0]
    target["resolution_status"] = "not_found"
    for field in ("product_code", "official_name", "provider"):
        target.pop(field)
    with pytest.raises(ValueError, match="미식별"):
        validate_domain_result(result)


def test_shared_chunk_can_be_attributed_to_two_verified_products() -> None:
    result = comparison_domain()
    result["comparison_result"]["cells"][1]["evidence_refs"][0]["chunk_id"] = "chunk-1"
    result["evidence"].pop()
    validate_domain_result(result)


def test_repeated_single_product_cannot_be_complete_comparison() -> None:
    result = comparison_domain()
    comparison = result["comparison_result"]
    comparison["targets"][1].update(
        product_code=comparison["targets"][0]["product_code"],
        official_name=comparison["targets"][0]["official_name"],
    )
    comparison["cells"][1]["evidence_refs"][0]["product_code"] = "KR5153420063"
    assert comparison_coverage(comparison["targets"], comparison["cells"]) == "partial"
    with pytest.raises(ValueError, match="coverage"):
        validate_domain_result(result)


@pytest.mark.parametrize("mutation", ["wrong_domain", "failed", "calculations", "empty_conditions"])
def test_domain_comparison_rejects_invalid_combinations(mutation: str) -> None:
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
        result["decision"]["missing_conditions"] = [" "]
    with pytest.raises(ValueError):
        validate_domain_result(result)


def test_comparison_contract_rejects_extra_fields() -> None:
    result = comparison_domain()
    result["comparison_result"]["cells"][0]["recommendation"] = "단기를 추천"  # type: ignore[typeddict-unknown-key]
    with pytest.raises(ValidationError):
        validate_comparison_result(result["comparison_result"], result["evidence"])


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class ComparisonSupervisor:
    """검증된 도메인 결과와 잘못된 Main 답변을 반환한다."""

    def __init__(self, results: list[DomainResult]) -> None:
        self.results = results

    async def ainvoke(self, input, *, context):
        from langchain_core.messages import AIMessage

        return {
            **input,
            "domain_results": self.results,
            "messages": [AIMessage(content="단기채가 원금을 보장하므로 무조건 추천합니다.")],
        }


@pytest.mark.anyio
@pytest.mark.parametrize("coverage", ["complete", "partial", "none"])
async def test_answer_service_preserves_comparison_and_exact_api_shape(coverage: str) -> None:
    from pension_agent.agent.orchestration import AnswerService
    from pension_agent.api.presentation import build_answer_response

    domain = comparison_domain()
    comparison = domain["comparison_result"]
    if coverage in {"partial", "none"}:
        unverified(comparison["cells"][1])
        domain["evidence"].pop()
        comparison["limitations"] = ["장기 상품 위험 근거 부족"]
    if coverage == "none":
        unverified(comparison["cells"][0])
        domain["evidence"].clear()
        domain["decision"]["status"] = "undetermined"
        domain["decision"]["conclusion"] = "근거는 없지만 단기 상품은 무위험으로 원금보장됩니다."
    comparison["coverage"] = comparison_coverage(comparison["targets"], comparison["cells"])
    for cell in comparison["cells"]:
        if cell["status"] == "not_verified":
            cell["finding"] = "무위험으로 원금보장됩니다."
    result = await AnswerService(ComparisonSupervisor([domain])).run(
        question_id="Q-comparison", question="솔로몬 단기와 장기 비교"
    )
    response = build_answer_response(result).model_dump()
    assert set(response) == {
        "question_id",
        "question",
        "retrieved_context",
        "think_trace",
        "answer",
    }
    assert response["retrieved_context"] == domain["evidence"]
    assert f"coverage={coverage}" in response["think_trace"]
    assert "솔로몬 단기국공채" in response["answer"]
    assert "솔로몬 장기국공채" in response["answer"]
    assert "투자기간 확인 필요" in response["answer"]
    assert "문서 기준일 확인 필요" in response["answer"]
    for output in (response["think_trace"], response["answer"]):
        assert "원금보장됩니다" not in output
        assert "무조건 추천" not in output
    if coverage == "none":
        assert "우열을 판단할 수 없습니다" in response["answer"]
        assert not response["retrieved_context"]
    else:
        assert domain["decision"]["conclusion"] in response["answer"]
        assert "fund-1.pdf" in response["answer"]
    if coverage == "partial":
        assert "장기 상품 위험 근거 부족" in response["answer"]


@pytest.mark.anyio
async def test_mixed_comparison_preserves_other_domain_calculations_and_catalog() -> None:
    from pension_agent.agent.orchestration import AnswerService

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


def test_fifteen_cells_are_preserved_and_sixth_target_is_rejected() -> None:
    result = comparison_domain()
    comparison = result["comparison_result"]
    template = comparison["targets"][0]
    comparison["targets"] = [
        {**template, "target_id": f"target-{index}", "product_code": f"CODE-{index}"}
        for index in range(5)
    ]
    comparison["criteria"] = [
        "investment_strategy",
        "risk",
        "capital_protection",
    ]
    comparison["cells"] = [
        {
            "target_id": target["target_id"],
            "criterion": criterion,
            "status": "supported",
            "finding": "제공 문서에서 확인한 사실",
            "limitations": [],
            "evidence_refs": [{"product_code": target["product_code"], "chunk_id": "shared"}],
        }
        for target in comparison["targets"]
        for criterion in comparison["criteria"]
    ]
    result["evidence"] = [{**result["evidence"][0], "chunk_id": "shared"}]
    validate_domain_result(result)
    assert len(build_domain_tool_result(result)["comparison_result"]["cells"]) == 15
    comparison["targets"].append({**template, "target_id": "sixth"})
    with pytest.raises(ValueError, match="2~5"):
        validate_domain_result(result)


def test_four_criteria_are_rejected_even_when_all_cells_have_valid_references() -> None:
    result = comparison_domain()
    comparison = result["comparison_result"]
    comparison["criteria"] = ["investment_strategy", "risk", "capital_protection", "fees"]
    comparison["cells"] = [
        {**cell, "criterion": criterion}
        for cell in comparison["cells"]
        for criterion in comparison["criteria"]
    ]

    assert len(comparison["cells"]) == 8
    with pytest.raises(ValueError, match="1~3"):
        validate_domain_result(result)


def _numeric_comparison_domain() -> DomainResult:
    result = comparison_domain()
    finding = "가격이 10% 하락할 수 있습니다."
    result["comparison_result"]["cells"][0]["finding"] = finding
    result["evidence"][0]["content"] = finding
    return result


@pytest.mark.anyio
async def test_mixed_comparison_preserves_numeric_cells_and_tax_canonical_statement() -> None:
    from pension_agent.agent.orchestration import AnswerService

    canonical = "연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다."
    tax: DomainResult = {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": "conditional",
            "conclusion": "세액공제 한도는 999만원입니다.",
            "missing_conditions": ["소득 구간 확인 필요"],
        },
        "evidence": [],
        "calculations": [],
        "warnings": ["세액공제 적용 조건 확인"],
        "verified_numeric_statements": [
            {
                "source_type": "statutory_fact",
                "source_id": "tax_credit_limit_combined",
                "text": canonical,
            }
        ],
    }

    result = await AnswerService(ComparisonSupervisor([_numeric_comparison_domain(), tax])).run(
        question_id="Q-comparison-canonical", question="솔로몬 단기·장기와 세액공제 한도"
    )

    answer = result.answer.answer
    for expected in (
        "| 상품 | 비교 항목 | 확인 내용 | 상태 | 근거 |",
        "솔로몬 단기국공채",
        "솔로몬 장기국공채",
        "가격이 10% 하락할 수 있습니다.",
        "fund-1.pdf",
        "소득 구간 확인 필요",
        "세액공제 적용 조건 확인",
    ):
        assert expected in answer
    assert answer.count(canonical) == 1
    assert "999만원" not in answer
    assert "VERIFIED_NUMERIC" not in answer


@pytest.mark.anyio
async def test_mixed_comparison_keeps_numeric_cells_with_unverified_tax_calculation() -> None:
    from pension_agent.agent.orchestration import AnswerService

    tax: DomainResult = {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": "conditional",
            "conclusion": "연금수령한도는 999만원입니다.",
            "missing_conditions": ["연금수령연차 확인 필요"],
        },
        "evidence": [],
        "calculations": [],
        "warnings": ["검증된 계산 결과 없음"],
    }

    result = await AnswerService(ComparisonSupervisor([_numeric_comparison_domain(), tax])).run(
        question_id="Q-comparison-unverified",
        question="평가액 1천만원인 계좌의 수령한도와 솔로몬 단기·장기를 비교해주세요.",
    )

    answer = result.answer.answer
    for expected in (
        "| 상품 | 비교 항목 | 확인 내용 | 상태 | 근거 |",
        "솔로몬 단기국공채",
        "솔로몬 장기국공채",
        "가격이 10% 하락할 수 있습니다.",
        "fund-1.pdf",
        "새로운 수치 결론을 제공할 수 없습니다",
        "연금수령연차 확인 필요",
        "검증된 계산 결과 없음",
    ):
        assert expected in answer
    assert "999만원" not in answer
