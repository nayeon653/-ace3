"""애플리케이션 조립 경계의 기본 Agent 구성을 검증한다."""

from typing import cast

from langchain_core.tools import BaseTool
from pydantic import BaseModel

from pension_agent.api.bootstrap import create_domain_agent_tools


def test_domain_agents_are_registered_with_stable_tool_contracts() -> None:
    tools = create_domain_agent_tools()

    assert all(isinstance(tool, BaseTool) for tool in tools)
    assert {tool.name for tool in tools} == {
        "analyze_policy",
        "analyze_tax_payout",
        "analyze_product",
    }
    for tool in tools:
        schema = cast(type[BaseModel], tool.tool_call_schema)
        assert set(schema.model_json_schema()["properties"]) == {"objective"}
