"""제품의 Qdrant 기반 Agent 수직 경로 조립."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from httpx import AsyncClient, Client, Limits
from langchain_core.language_models import BaseChatModel

from pension_agent.agent.contracts import DomainName
from pension_agent.agent.domain_agent import DomainAgent
from pension_agent.agent.execution import AsyncConcurrencyLimiter, ModelConcurrencyMiddleware
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
from pension_agent.agent.search import (
    LimitedChunkRetriever,
    LimitedQueryEmbedder,
    SearchRunner,
    SearchService,
)
from pension_agent.agent.tax_payout import (
    TAX_PAYOUT_TOOL_DESCRIPTION,
    TAX_PAYOUT_TOOL_NAME,
    create_tax_payout_agent,
)
from pension_agent.config import (
    BGE_M3_EMBEDDING_CONFIG,
    DEFAULT_AGENT_RUNTIME_CONFIG,
    MAIN_SUPERVISOR_HCX_CONFIG,
    AgentRuntimeConfig,
    ClovaStudioConnection,
    QdrantConnection,
)
from pension_agent.retrieval import (
    create_async_qdrant_client,
    create_async_qdrant_retriever,
    create_clova_query_embedder,
    prewarm_kiwi,
)

logger = logging.getLogger(__name__)


class AgentRuntimeBuildError(RuntimeError):
    """Agent 런타임을 안전하게 조립하지 못한 경우."""


class DomainAgentFactory(Protocol):
    """런타임 Domain Agent Factory의 공통 호출 계약."""

    def __call__(
        self,
        *,
        model: BaseChatModel,
        search_service: SearchRunner,
        model_concurrency: ModelConcurrencyMiddleware | None = None,
    ) -> DomainAgent: ...


@dataclass(frozen=True, slots=True)
class DomainAgentSpec:
    """런타임과 시각화가 공유하는 Domain Agent 등록 정보."""

    slug: str
    display_name: str
    domain: DomainName
    tool_name: str
    tool_description: str
    factory: DomainAgentFactory


def domain_agent_specs() -> tuple[DomainAgentSpec, ...]:
    """현재 런타임에 등록된 Domain Agent 명세를 반환한다."""

    return (
        DomainAgentSpec(
            slug="policy",
            display_name="Policy",
            domain="policy",
            tool_name=POLICY_TOOL_NAME,
            tool_description=POLICY_TOOL_DESCRIPTION,
            factory=create_policy_agent,
        ),
        DomainAgentSpec(
            slug="tax-payout",
            display_name="Tax/Payout",
            domain="tax_payout",
            tool_name=TAX_PAYOUT_TOOL_NAME,
            tool_description=TAX_PAYOUT_TOOL_DESCRIPTION,
            factory=create_tax_payout_agent,
        ),
        DomainAgentSpec(
            slug="product",
            display_name="Product",
            domain="product",
            tool_name=PRODUCT_TOOL_NAME,
            tool_description=PRODUCT_TOOL_DESCRIPTION,
            factory=create_product_agent,
        ),
    )


@dataclass(frozen=True, slots=True)
class _ProviderHttpClients:
    """langchain-naver에 주입하고 런타임이 직접 닫는 HTTP client 한 쌍."""

    sync: Client
    async_: AsyncClient

    @classmethod
    def create(cls, *, max_concurrency: int) -> "_ProviderHttpClients":
        limits = Limits(
            max_connections=max_concurrency,
            max_keepalive_connections=max_concurrency,
        )
        sync = Client(limits=limits)
        try:
            async_ = AsyncClient(limits=limits)
        except Exception:
            sync.close()
            raise
        return cls(sync=sync, async_=async_)

    async def aclose(self) -> None:
        """async 연결을 먼저 닫고 사용하지 않는 sync fallback도 정리한다."""

        try:
            await self.async_.aclose()
        finally:
            self.sync.close()


async def _close_partial_runtime(
    callbacks: tuple[Callable[[], Awaitable[None]], ...],
) -> None:
    """부분 조립 자원을 모두 시도해 닫고 개별 close 오류는 정제한다."""

    for callback in callbacks:
        try:
            await callback()
        except BaseException:  # noqa: BLE001
            logger.warning("Agent 런타임 초기화 리소스 정리에 실패했습니다.")


async def _drain_partial_runtime_cleanup(
    callbacks: tuple[Callable[[], Awaitable[None]], ...],
) -> None:
    """startup task가 반복 취소돼도 별도 cleanup task의 소유권을 유지한다."""

    cleanup_task = asyncio.create_task(
        _close_partial_runtime(callbacks),
        name="agent-runtime-startup-cleanup",
    )
    while not cleanup_task.done():
        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError:
            continue
    await cleanup_task


async def build_runtime_answer_service(
    *,
    config: AgentRuntimeConfig = DEFAULT_AGENT_RUNTIME_CONFIG,
) -> AnswerService:
    """환경 설정으로 전체 Agent 수직 경로와 정리 콜백을 조립한다."""

    close_callbacks: list[Callable[[], Awaitable[None]]] = []
    try:
        clova_connection = ClovaStudioConnection()
        qdrant_connection = QdrantConnection()
        model_http = _ProviderHttpClients.create(max_concurrency=config.max_concurrent_hcx_calls)
        close_callbacks.append(model_http.aclose)
        model = create_chat_clovax(
            config=MAIN_SUPERVISOR_HCX_CONFIG,
            connection=clova_connection,
            http_client=model_http.sync,
            http_async_client=model_http.async_,
        )
        embedding_http = _ProviderHttpClients.create(
            max_concurrency=config.max_concurrent_embedding_calls
        )
        close_callbacks.append(embedding_http.aclose)
        embedder = create_clova_query_embedder(
            config=BGE_M3_EMBEDDING_CONFIG,
            connection=clova_connection,
            http_client=embedding_http.sync,
            http_async_client=embedding_http.async_,
        )
        await prewarm_kiwi()
        qdrant_client = create_async_qdrant_client(
            qdrant_connection,
            pool_size=config.max_concurrent_qdrant_calls,
        )
        close_callbacks.append(qdrant_client.close)
        retriever = create_async_qdrant_retriever(
            qdrant_client,
            connection=qdrant_connection,
        )
        model_concurrency = ModelConcurrencyMiddleware(
            AsyncConcurrencyLimiter(config.max_concurrent_hcx_calls)
        )
        limited_embedder = LimitedQueryEmbedder(
            embedder,
            AsyncConcurrencyLimiter(config.max_concurrent_embedding_calls),
        )
        limited_retriever = LimitedChunkRetriever(
            retriever,
            AsyncConcurrencyLimiter(config.max_concurrent_qdrant_calls),
        )
        search_service = SearchService(
            embedder=limited_embedder,
            retriever=limited_retriever,
        )

        domain_agents = tuple(
            (
                spec,
                spec.factory(
                    model=model,
                    search_service=search_service,
                    model_concurrency=model_concurrency,
                ),
            )
            for spec in domain_agent_specs()
        )
        domain_tools = tuple(
            create_domain_agent_tool(
                name=spec.tool_name,
                description=spec.tool_description,
                domain=spec.domain,
                runner=agent,
            )
            for spec, agent in domain_agents
        )
        supervisor = create_main_supervisor(
            model=model,
            tools=domain_tools,
            model_concurrency=model_concurrency,
        )
        return AnswerService(
            supervisor,
            config=config,
            close_callbacks=tuple(reversed(close_callbacks)),
        )
    # 부분 조립 실패와 startup 취소 모두 이미 만든 자원을 역순으로 정리한다.
    except BaseException as error:
        await _drain_partial_runtime_cleanup(tuple(reversed(close_callbacks)))
        if isinstance(error, Exception):
            raise AgentRuntimeBuildError("Agent 런타임 초기화에 실패했습니다.") from None
        raise
