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
