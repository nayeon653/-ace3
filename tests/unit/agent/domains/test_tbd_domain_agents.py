"""도메인별 TBD Agent와 조립 경계를 검증한다."""

from typing import cast

import pytest
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from pension_agent.agent.domains.assembly import create_tbd_domain_agent_tools
from pension_agent.agent.domains.policy import TbdPolicyAgent
from pension_agent.agent.domains.product import TbdProductAgent
from pension_agent.agent.domains.tax_payout import TbdTaxPayoutAgent
from pension_agent.agent.schemas import (
    DomainName,
    DomainRequest,
    DomainResult,
    validate_domain_result,
)
from pension_agent.agent.tools import DomainRunner


@pytest.mark.parametrize(
    ("agent", "domain", "display_name"),
    [
        (TbdPolicyAgent(), "policy", "업무·제도"),
        (TbdTaxPayoutAgent(), "tax_payout", "세제·수령"),
        (TbdProductAgent(), "product", "상품·운용"),
    ],
)
def test_tbd_agent_returns_undetermined_placeholder(
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
    assert "TBD" in result["decision"]["conclusion"]
    assert result["decision"]["missing_conditions"] == [f"{display_name} 도메인 Agent 구현"]
    assert result["evidence"] == []
    assert result["calculations"] == []


def test_tbd_agents_are_registered_with_stable_tool_contracts() -> None:
    tools = create_tbd_domain_agent_tools()

    assert all(isinstance(tool, BaseTool) for tool in tools)
    assert {tool.name for tool in tools} == {
        "analyze_policy",
        "analyze_tax_payout",
        "analyze_product",
    }
    for tool in tools:
        schema = cast(type[BaseModel], tool.tool_call_schema)
        assert set(schema.model_json_schema()["properties"]) == {"objective"}
