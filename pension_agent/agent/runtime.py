"""제품의 Qdrant 기반 Agent 수직 경로 조립."""

import logging
from collections.abc import Callable

from pension_agent.agent.model_factory import create_chat_clovax
from pension_agent.agent.orchestration import (
    AnswerService,
    create_domain_agent_tool,
    create_main_supervisor,
)
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
from pension_agent.agent.search import SearchAgentAdapter, create_search_agent
from pension_agent.agent.tax_payout import (
    TAX_PAYOUT_TOOL_DESCRIPTION,
    TAX_PAYOUT_TOOL_NAME,
    create_tax_payout_agent,
)
from pension_agent.config import (
    BGE_M3_EMBEDDING_CONFIG,
    MAIN_SUPERVISOR_HCX_CONFIG,
    ClovaStudioConnection,
    QdrantConnection,
)
from pension_agent.retrieval import (
    create_clova_query_embedder,
    create_qdrant_client,
    create_qdrant_retriever,
)

logger = logging.getLogger(__name__)


class AgentRuntimeBuildError(RuntimeError):
    """Agent 런타임을 안전하게 조립하지 못한 경우."""


def build_runtime_answer_service() -> AnswerService:
    """환경 설정으로 전체 Agent 수직 경로와 정리 콜백을 조립한다."""

    close_callbacks: list[Callable[[], None]] = []
    try:
        clova_connection = ClovaStudioConnection()
        qdrant_connection = QdrantConnection()
        model = create_chat_clovax(
            config=MAIN_SUPERVISOR_HCX_CONFIG,
            connection=clova_connection,
        )
        embedder = create_clova_query_embedder(
            config=BGE_M3_EMBEDDING_CONFIG,
            connection=clova_connection,
        )
        qdrant_client = create_qdrant_client(qdrant_connection)
        close_callbacks.append(qdrant_client.close)
        retriever = create_qdrant_retriever(
            qdrant_client,
            connection=qdrant_connection,
        )
        search_graph = create_search_agent(
            model=model,
            embedder=embedder,
            retriever=retriever,
        )
        search_adapter = SearchAgentAdapter(search_graph)
        close_callbacks.insert(0, search_adapter.close)

        policy_agent = create_policy_agent(model=model, search_adapter=search_adapter)
        close_callbacks.insert(0, policy_agent.close)
        tax_payout_agent = create_tax_payout_agent(model=model, search_adapter=search_adapter)
        close_callbacks.insert(1, tax_payout_agent.close)
        product_agent = create_product_agent(model=model, search_adapter=search_adapter)
        close_callbacks.insert(2, product_agent.close)

        domain_tools = (
            create_domain_agent_tool(
                name=POLICY_TOOL_NAME,
                description=POLICY_TOOL_DESCRIPTION,
                domain="policy",
                runner=policy_agent,
            ),
            create_domain_agent_tool(
                name=TAX_PAYOUT_TOOL_NAME,
                description=TAX_PAYOUT_TOOL_DESCRIPTION,
                domain="tax_payout",
                runner=tax_payout_agent,
            ),
            create_domain_agent_tool(
                name=PRODUCT_TOOL_NAME,
                description=PRODUCT_TOOL_DESCRIPTION,
                domain="product",
                runner=product_agent,
            ),
        )
        supervisor = create_main_supervisor(model=model, tools=domain_tools)
        return AnswerService(
            supervisor,
            close_callbacks=tuple(close_callbacks),
        )
    # 부분 조립 실패도 자원을 정리하고 원시 예외는 공개하지 않는다.
    except Exception:  # noqa: BLE001
        for callback in close_callbacks:
            try:
                callback()
            except Exception:  # noqa: BLE001
                logger.warning("Agent 런타임 초기화 리소스 정리에 실패했습니다.")
        raise AgentRuntimeBuildError("Agent 런타임 초기화에 실패했습니다.") from None
