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
        "calculations": [{"calculator_name": "example", "inputs": {"amount": 1}, "result": 1}],
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


def test_domain_tool_result_excludes_evidence_and_calculations() -> None:
    tool_result = build_domain_tool_result(_completed_result())

    assert "evidence" not in tool_result
    assert "calculations" not in tool_result
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


def test_agent_answer_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AgentAnswer(answer="답변", evidence=[])


def test_domain_request_schema_describes_tool_arguments() -> None:
    properties = TypeAdapter(DomainRequest).json_schema()["properties"]

    assert "질문 원문" in properties["question"]["description"]
    assert "하나의 구체적인 비즈니스 판단" in properties["objective"]["description"]
