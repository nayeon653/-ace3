"""Main과 도메인 Agent의 공통 계약을 단위 테스트한다."""

import pytest
from pydantic import TypeAdapter, ValidationError

from pension_agent.agent.contracts import (
    AgentAnswer,
    DomainRequest,
    DomainResult,
    Permission,
    document_types_for_permission,
    validate_domain_result,
)
from pension_agent.agent.orchestration import build_domain_tool_result
from pension_agent.core import DocumentType


def _completed_result() -> DomainResult:
    return {
        "domain": "policy",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": "이전할 수 있습니다.",
            "missing_conditions": [],
        },
        "evidence": [
            {
                "chunk_id": "CH-001",
                "source_file_name": "policy.pdf",
                "title": "업무 지침",
                "locator": "계약 이전",
                "content": "외부 전달 금지",
            }
        ],
        "calculations": [
            {
                "calculator_id": "example",
                "inputs": {"amount": "1"},
                "input_sources": {
                    "amount": {
                        "origin": "question",
                        "text": "금액 1원",
                        "chunk_id": None,
                    }
                },
                "outputs": {"result": "1"},
                "units": {"result": "KRW"},
                "warnings": [],
            }
        ],
        "warnings": [],
    }


@pytest.mark.parametrize(
    ("permission", "expected_document_type"),
    [
        (Permission.POLICY, DocumentType.PENSION_REFERENCE),
        (Permission.TAX_PAYOUT, DocumentType.PENSION_REFERENCE),
        (Permission.PRODUCT, DocumentType.FUND_PROSPECTUS),
    ],
)
def test_permission_maps_domain_to_document_types(
    permission: Permission,
    expected_document_type: DocumentType,
) -> None:
    assert document_types_for_permission(permission) == frozenset({expected_document_type})


def test_domain_tool_result_excludes_evidence_and_includes_calculations() -> None:
    tool_result = build_domain_tool_result(_completed_result())

    assert "evidence" not in tool_result
    assert tool_result["calculations"] == _completed_result()["calculations"]
    assert tool_result["decision"]["conclusion"] == "이전할 수 있습니다."


def test_domain_tool_result_includes_verified_catalog_result() -> None:
    result: DomainResult = {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": "미래에셋 상품 1개를 조회했습니다.",
            "missing_conditions": [],
        },
        "evidence": [
            {
                "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_file_name": "product_catalog.json",
                "title": "검증된 상품 카탈로그 조회 결과",
                "locator": "provider=미래에셋;catalog_version=v1",
                "content": "결정론적 카탈로그 결과",
            }
        ],
        "calculations": [],
        "warnings": [],
        "catalog_result": {
            "route": "browse_catalog",
            "provider": "미래에셋",
            "return_mode": "count_and_items",
            "total_count": 1,
            "items": [
                {
                    "product_code": "KR510902511M",
                    "official_name": "미래에셋장기성장포커스",
                    "provider": "미래에셋",
                }
            ],
            "catalog_version": "v1",
        },
    }

    tool_result = build_domain_tool_result(result)

    assert tool_result["catalog_result"] == result["catalog_result"]
    assert "evidence" not in tool_result


def test_invalid_domain_result_combinations_raise() -> None:
    missing_decision = _completed_result()
    del missing_decision["decision"]

    failed_with_decision = _completed_result()
    failed_with_decision.update(execution_status="failed", error="실패")

    conditional_without_condition = _completed_result()
    conditional_without_condition["decision"]["status"] = "conditional"

    for result in (missing_decision, failed_with_decision, conditional_without_condition):
        with pytest.raises(ValueError):
            validate_domain_result(result)


def test_domain_tool_result_exposes_placeholder_not_canonical_text() -> None:
    result = _completed_result()
    result["verified_numeric_statements"] = [
        {
            "source_type": "statutory_fact",
            "source_id": "tax_credit_limit_combined",
            "text": "연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
        }
    ]

    tool_result = build_domain_tool_result(result)

    assert tool_result["verified_numeric_placeholders"] == [
        {
            "placeholder": "{{VERIFIED_NUMERIC:policy:tax_credit_limit_combined}}",
            "source_id": "tax_credit_limit_combined",
        }
    ]
    assert "900만원" not in str(tool_result)
    assert "text" not in str(tool_result["verified_numeric_placeholders"][0])


def test_domain_tool_result_omits_placeholders_when_no_statements() -> None:
    tool_result = build_domain_tool_result(_completed_result())

    assert "verified_numeric_placeholders" not in tool_result


def test_domain_result_rejects_verified_numeric_statement_on_failed_result() -> None:
    result: DomainResult = {
        "domain": "tax_payout",
        "execution_status": "failed",
        "evidence": [],
        "calculations": [],
        "warnings": [],
        "error": "실패",
        "verified_numeric_statements": [
            {"source_type": "statutory_fact", "source_id": "x", "text": "x"}
        ],
    }

    with pytest.raises(ValueError, match="검증된 숫자 문장"):
        validate_domain_result(result)


@pytest.mark.parametrize(
    ("source_id", "text"),
    [("", "본문"), ("id", ""), ("   ", "본문"), ("id", "   ")],
)
def test_domain_result_rejects_blank_verified_numeric_statement_fields(
    source_id: str, text: str
) -> None:
    result = _completed_result()
    result["verified_numeric_statements"] = [
        {"source_type": "statutory_fact", "source_id": source_id, "text": text}
    ]

    with pytest.raises(ValueError):
        validate_domain_result(result)


def test_domain_result_requires_calculation_source_evidence() -> None:
    result = _completed_result()
    result["calculations"][0]["input_sources"]["amount"] = {
        "origin": "evidence",
        "text": "금액 1원",
        "chunk_id": "CH-MISSING",
    }

    with pytest.raises(ValueError, match="최종 evidence"):
        validate_domain_result(result)


def test_agent_answer_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AgentAnswer(answer="답변", evidence=[])


def test_domain_request_schema_describes_tool_arguments() -> None:
    properties = TypeAdapter(DomainRequest).json_schema()["properties"]

    assert "질문 원문" in properties["question"]["description"]
    assert "하나의 구체적인 비즈니스 판단" in properties["objective"]["description"]
