"""도메인별 기본 Agent와 조립 경계를 검증한다."""

import pytest

from pension_agent.agent.contracts import (
    DomainName,
    DomainRequest,
    DomainResult,
    validate_domain_result,
)
from pension_agent.agent.orchestration import DomainRunner
from pension_agent.agent.policy import PolicyAgent
from pension_agent.agent.product import ProductAgent
from pension_agent.agent.tax_payout import TaxPayoutAgent
from pension_agent.core import DocumentType


@pytest.mark.parametrize(
    ("agent", "domain", "display_name"),
    [
        (PolicyAgent(), "policy", "업무·제도"),
        (TaxPayoutAgent(), "tax_payout", "세제·수령"),
        (ProductAgent(), "product", "상품·운용"),
    ],
)
def test_domain_agent_returns_undetermined_placeholder(
    agent: DomainRunner,
    domain: DomainName,
    display_name: str,
) -> None:
    request: DomainRequest = {
        "question": "연금계좌를 이전할 수 있나요?",
        "objective": "이전 가능 여부 판단",
    }

    result: DomainResult = agent(request)

    validate_domain_result(result)
    assert result["domain"] == domain
    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == "undetermined"
    assert display_name in result["decision"]["conclusion"]
    assert "구현 전" in result["decision"]["conclusion"]
    assert result["decision"]["missing_conditions"] == [f"{display_name} 도메인 Agent 구현"]
    assert result["evidence"] == []
    assert result["calculations"] == []


@pytest.mark.parametrize(
    ("agent", "expected_document_type"),
    [
        (PolicyAgent(), DocumentType.PENSION_REFERENCE),
        (TaxPayoutAgent(), DocumentType.PENSION_REFERENCE),
        (ProductAgent(), DocumentType.FUND_PROSPECTUS),
    ],
)
def test_domain_agents_declare_fixed_document_permissions(
    agent: PolicyAgent | TaxPayoutAgent | ProductAgent,
    expected_document_type: DocumentType,
) -> None:
    assert agent.permissions.readable_document_types == frozenset({expected_document_type})
