"""도메인 Agent를 Main Supervisor Tool로 노출하는 Adapter."""

import json
import logging
from collections.abc import Awaitable
from typing import Annotated, Protocol

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool
from langgraph.types import Command
from pydantic import Field

from pension_agent.agent.contracts import (
    DomainName,
    DomainRequest,
    DomainResult,
    DomainToolResult,
    validate_domain_result,
)
from pension_agent.agent.execution import ExecutionContext
from pension_agent.agent.orchestration.state import SupervisorState


class DomainRunner(Protocol):
    """Main Supervisor Tool이 호출하는 비동기 Domain Agent 계약."""

    def __call__(
        self,
        request: DomainRequest,
        *,
        deadline: float | None = None,
    ) -> Awaitable[DomainResult]: ...


logger = logging.getLogger(__name__)


def build_domain_tool_result(result: DomainResult) -> DomainToolResult:
    """전체 결과에서 Main LLM에 필요한 필드만 복사한다."""

    validate_domain_result(result)
    tool_result: DomainToolResult = {
        "domain": result["domain"],
        "execution_status": result["execution_status"],
        "warnings": result["warnings"],
    }
    if "decision" in result:
        tool_result["decision"] = result["decision"]
    if "catalog_result" in result:
        tool_result["catalog_result"] = result["catalog_result"]
    if "error" in result:
        tool_result["error"] = result["error"]
    return tool_result


def _failed_result(domain: DomainName) -> DomainResult:
    return {
        "domain": domain,
        "execution_status": "failed",
        "evidence": [],
        "calculations": [],
        "warnings": [],
        "error": "도메인 분석을 완료하지 못했습니다.",
    }


def create_domain_agent_tool(
    *,
    name: str,
    description: str,
    domain: DomainName,
    runner: DomainRunner,
) -> BaseTool:
    """주입된 도메인 실행 함수를 호출하는 Main용 Tool을 만든다."""

    @tool(name, description=description)
    async def domain_agent_tool(
        objective: Annotated[
            str,
            Field(description="이 Tool이 수행할 하나의 구체적인 비즈니스 판단"),
        ],
        runtime: ToolRuntime[ExecutionContext, SupervisorState],
    ) -> Command:
        request: DomainRequest = {
            "question": runtime.state["question"],
            "objective": objective,
        }
        try:
            result = await runner(request, deadline=runtime.context.deadline)
            validate_domain_result(result)
            if result["domain"] != domain:
                raise ValueError("Tool과 실행 결과의 도메인이 일치하지 않습니다.")
        except Exception:
            logger.exception("%s 도메인 Agent 실행에 실패했습니다.", domain)
            result = _failed_result(domain)

        tool_call_id = runtime.tool_call_id
        if tool_call_id is None:
            raise ValueError("Domain Agent Tool 호출 ID가 없습니다.")

        tool_result = build_domain_tool_result(result)
        return Command(
            update={
                "domain_results": [result],
                "messages": [
                    ToolMessage(
                        content=json.dumps(tool_result, ensure_ascii=False),
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    return domain_agent_tool
