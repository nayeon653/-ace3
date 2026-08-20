"""외부 연결 없이 전체 Agent 그래프 문서를 생성한다."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

from pension_agent.agent.execution import AsyncConcurrencyLimiter, ModelConcurrencyMiddleware
from pension_agent.agent.orchestration import create_domain_agent_tool, create_main_supervisor
from pension_agent.agent.policy import (
    POLICY_TOOL_DESCRIPTION,
    POLICY_TOOL_NAME,
    create_policy_agent,
)
from pension_agent.agent.product import (
    PRODUCT_TOOL_DESCRIPTION,
    PRODUCT_TOOL_NAME,
    create_product_agent,
)
from pension_agent.agent.tax_payout import (
    TAX_PAYOUT_TOOL_DESCRIPTION,
    TAX_PAYOUT_TOOL_NAME,
    create_tax_payout_agent,
)
from pension_agent.config import DEFAULT_AGENT_RUNTIME_CONFIG

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "docs" / "architecture" / "agent-graphs.md"

_SYSTEM_OVERVIEW = """flowchart TB
    question[\"GET /answer 질문\"] --> supervisor

    subgraph main[\"Main Supervisor · CompiledStateGraph\"]
        supervisor[\"HCX-005 model\"] <--> domain_tools[\"Domain Agent tools\"]
    end

    domain_tools -->|analyze_policy| policy
    domain_tools -->|analyze_tax_payout| tax_payout
    domain_tools -->|analyze_product| product

    subgraph domains[\"Domain Agents · 각각 CompiledStateGraph\"]
        policy[\"Policy Agent\"]
        tax_payout[\"Tax/Payout Agent\"]
        product[\"Product Agent\"]
    end

    policy --> domain_tools
    tax_payout --> domain_tools
    product --> domain_tools

    policy --> search_tools
    tax_payout --> search_tools
    product --> search_tools

    subgraph search[\"공용 검색 경로\"]
        search_tools[\"search_documents\"] --> search_service[\"SearchService\"]
        search_service --> embedding[\"CLOVA bge-m3 query embedding\"]
        search_service --> qdrant[\"Qdrant hybrid retrieval\"]
    end

    supervisor --> answer[\"최종 답변\"]
"""

_GRAPH_TITLES = {
    "main-supervisor": "Main Supervisor 컴파일 그래프",
    "policy": "Policy Domain Agent 컴파일 그래프",
    "tax-payout": "Tax/Payout Domain Agent 컴파일 그래프",
    "product": "Product Domain Agent 컴파일 그래프",
}


class _OfflineSearchService:
    """그래프 조립 중 실제 검색 실행을 허용하지 않는 대체 객체."""

    async def search(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("그래프 생성 중에는 SearchService를 실행할 수 없습니다.")


def _compiled_graphs() -> dict[str, Any]:
    """제품 런타임과 같은 Factory·middleware 구성의 컴파일 그래프를 반환한다."""

    model = FakeMessagesListChatModel(responses=[])
    search_service = _OfflineSearchService()
    model_concurrency = ModelConcurrencyMiddleware(
        AsyncConcurrencyLimiter(DEFAULT_AGENT_RUNTIME_CONFIG.max_concurrent_hcx_calls)
    )
    domain_agents = {
        "policy": create_policy_agent(
            model=model,
            search_service=search_service,
            model_concurrency=model_concurrency,
        ),
        "tax-payout": create_tax_payout_agent(
            model=model,
            search_service=search_service,
            model_concurrency=model_concurrency,
        ),
        "product": create_product_agent(
            model=model,
            search_service=search_service,
            model_concurrency=model_concurrency,
        ),
    }
    domain_tools = (
        create_domain_agent_tool(
            name=POLICY_TOOL_NAME,
            description=POLICY_TOOL_DESCRIPTION,
            domain="policy",
            runner=domain_agents["policy"],
        ),
        create_domain_agent_tool(
            name=TAX_PAYOUT_TOOL_NAME,
            description=TAX_PAYOUT_TOOL_DESCRIPTION,
            domain="tax_payout",
            runner=domain_agents["tax-payout"],
        ),
        create_domain_agent_tool(
            name=PRODUCT_TOOL_NAME,
            description=PRODUCT_TOOL_DESCRIPTION,
            domain="product",
            runner=domain_agents["product"],
        ),
    )
    supervisor = create_main_supervisor(
        model=model,
        tools=domain_tools,
        model_concurrency=model_concurrency,
    )
    return {
        "main-supervisor": supervisor,
        **{name: agent.graph for name, agent in domain_agents.items()},
    }


def render_document() -> str:
    """전체 구조와 실제 컴파일 그래프를 GitHub Mermaid 문서로 만든다."""

    sections = [
        "# Agent 전체 그래프",
        "",
        "<!-- 이 파일은 tools/render_agent_graphs.py로 생성됩니다. 직접 수정하지 마세요. -->",
        "",
        (
            "`make agent-graph`로 현재 코드에서 다시 생성합니다. 그래프 생성에는 HCX, "
            "Qdrant 또는 외부 네트워크 연결이 필요하지 않습니다."
        ),
        "",
        "## 전체 호출 구조",
        "",
        (
            "Supervisor가 Domain Agent를 LangChain Tool로 호출하므로, 이 그림은 독립적으로 "
            "컴파일된 그래프 사이의 런타임 호출 경계를 함께 표시합니다."
        ),
        "",
        "```mermaid",
        _SYSTEM_OVERVIEW.rstrip(),
        "```",
    ]
    for name, graph in _compiled_graphs().items():
        sections.extend(
            (
                "",
                f"## {_GRAPH_TITLES[name]}",
                "",
                "```mermaid",
                graph.get_graph().draw_mermaid().rstrip(),
                "```",
            )
        )
    return "\n".join(sections) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="전체 Agent 그래프 문서를 생성합니다.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="생성할 Markdown 경로",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="기존 문서가 현재 그래프와 일치하는지만 확인",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output = args.output.resolve()
    rendered = render_document()
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
            print(f"Agent 그래프 문서가 최신 상태가 아닙니다: {output}")
            return 1
        print(f"Agent 그래프 문서가 최신 상태입니다: {output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Agent 그래프 문서를 생성했습니다: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
