"""실제 런타임 팩토리의 조립 순서와 자원 정리를 검증한다."""

import asyncio
from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from pension_agent.agent import runtime
from pension_agent.agent.orchestration.service import SupervisorRunner
from pension_agent.agent.search import LimitedChunkRetriever, LimitedQueryEmbedder
from pension_agent.config import AgentRuntimeConfig


@dataclass
class AsyncClosable:
    name: str
    closed: list[str]

    async def close(self) -> None:
        self.closed.append(self.name)


@dataclass
class FakeHttpClients:
    name: str
    closed: list[str]
    sync: object = field(default_factory=object)
    async_: object = field(default_factory=object)

    async def aclose(self) -> None:
        self.closed.append(self.name)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _install_http_client_factory(
    monkeypatch: pytest.MonkeyPatch,
    *,
    closed: list[str],
    created: dict[str, Any],
) -> None:
    names = iter(("model-http", "embedding-http"))

    def create(*, max_concurrency: int) -> FakeHttpClients:
        name = next(names)
        pair = FakeHttpClients(name, closed)
        created[name] = pair
        created.setdefault("http_limits", []).append(max_concurrency)
        return pair

    monkeypatch.setattr(runtime._ProviderHttpClients, "create", create)


@pytest.mark.anyio
async def test_runtime_applies_shared_limits_and_closes_owned_clients_in_reverse_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[str] = []
    created: dict[str, Any] = {}
    model = object()
    embedder = object()
    qdrant_client = AsyncClosable("qdrant", closed)
    retriever = object()
    search_service = object()
    _install_http_client_factory(monkeypatch, closed=closed, created=created)

    async def prewarm() -> None:
        created["kiwi_prewarmed"] = True

    def create_model(**kwargs: Any) -> object:
        created["model_factory"] = kwargs
        return model

    def create_embedder(**kwargs: Any) -> object:
        created["embedder_factory"] = kwargs
        return embedder

    def create_qdrant(connection: Any, *, pool_size: int) -> AsyncClosable:
        created["qdrant_connection"] = connection
        created["qdrant_pool_size"] = pool_size
        return qdrant_client

    monkeypatch.setattr(runtime, "create_chat_clovax", create_model)
    monkeypatch.setattr(runtime, "create_clova_query_embedder", create_embedder)
    monkeypatch.setattr(runtime, "prewarm_kiwi", prewarm)
    monkeypatch.setattr(runtime, "create_async_qdrant_client", create_qdrant)
    monkeypatch.setattr(
        runtime,
        "create_async_qdrant_retriever",
        lambda passed_client, *, connection: (
            created.update(client=passed_client, retriever_connection=connection) or retriever
        ),
    )

    def create_search_service(**kwargs: Any) -> object:
        created["search_service"] = kwargs
        return search_service

    monkeypatch.setattr(runtime, "SearchService", create_search_service)

    def domain_factory(name: str):
        def build(**kwargs: Any) -> object:
            created[name] = kwargs
            return object()

        return build

    monkeypatch.setattr(runtime, "create_policy_agent", domain_factory("policy"))
    monkeypatch.setattr(runtime, "create_tax_payout_agent", domain_factory("tax_payout"))
    monkeypatch.setattr(runtime, "create_product_agent", domain_factory("product"))
    supervisor = cast(SupervisorRunner, object())

    def create_supervisor(**kwargs: Any) -> SupervisorRunner:
        created["supervisor"] = kwargs
        return supervisor

    monkeypatch.setattr(runtime, "create_main_supervisor", create_supervisor)

    config = AgentRuntimeConfig(
        max_concurrent_answers=6,
        max_concurrent_hcx_calls=2,
        max_concurrent_embedding_calls=3,
        max_concurrent_qdrant_calls=5,
        answer_timeout_seconds=123,
        shutdown_timeout_seconds=9,
    )
    service = await runtime.build_runtime_answer_service(config=config)
    await service.aclose()
    await service.aclose()

    model_http = created["model-http"]
    embedding_http = created["embedding-http"]
    assert created["kiwi_prewarmed"] is True
    assert created["http_limits"] == [2, 3]
    assert created["model_factory"]["http_client"] is model_http.sync
    assert created["model_factory"]["http_async_client"] is model_http.async_
    assert created["embedder_factory"]["http_client"] is embedding_http.sync
    assert created["embedder_factory"]["http_async_client"] is embedding_http.async_
    assert created["qdrant_pool_size"] == 5
    assert created["client"] is qdrant_client
    assert set(created["search_service"]) == {"embedder", "retriever"}
    assert isinstance(created["search_service"]["embedder"], LimitedQueryEmbedder)
    assert created["search_service"]["embedder"].inner is embedder
    assert created["search_service"]["embedder"].limiter.max_concurrency == 3
    assert isinstance(created["search_service"]["retriever"], LimitedChunkRetriever)
    assert created["search_service"]["retriever"].inner is retriever
    assert created["search_service"]["retriever"].limiter.max_concurrency == 5
    shared_model_limit = created["policy"]["model_concurrency"]
    assert shared_model_limit._limiter.max_concurrency == 2
    assert created["policy"]["search_service"] is search_service
    assert created["tax_payout"]["search_service"] is search_service
    assert created["product"]["search_service"] is search_service
    assert created["policy"]["model_concurrency"] is shared_model_limit
    assert created["tax_payout"]["model_concurrency"] is shared_model_limit
    assert created["product"]["model_concurrency"] is shared_model_limit
    assert created["supervisor"]["model_concurrency"] is shared_model_limit
    assert [tool.name for tool in created["supervisor"]["tools"]] == [
        "analyze_policy",
        "analyze_tax_payout",
        "analyze_product",
    ]
    assert service._config is config
    assert closed == ["qdrant", "embedding-http", "model-http"]


@pytest.mark.anyio
async def test_runtime_closes_partial_resources_when_domain_creation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[str] = []
    created: dict[str, Any] = {}
    qdrant_client = AsyncClosable("qdrant", closed)
    _install_http_client_factory(monkeypatch, closed=closed, created=created)

    async def prewarm() -> None:
        return None

    monkeypatch.setattr(runtime, "create_chat_clovax", lambda **kwargs: object())
    monkeypatch.setattr(runtime, "create_clova_query_embedder", lambda **kwargs: object())
    monkeypatch.setattr(runtime, "prewarm_kiwi", prewarm)
    monkeypatch.setattr(
        runtime,
        "create_async_qdrant_client",
        lambda connection, *, pool_size: qdrant_client,
    )
    monkeypatch.setattr(
        runtime,
        "create_async_qdrant_retriever",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(runtime, "SearchService", lambda **kwargs: object())
    monkeypatch.setattr(runtime, "create_policy_agent", lambda **kwargs: object())
    monkeypatch.setattr(runtime, "create_tax_payout_agent", lambda **kwargs: object())

    def fail_product(**kwargs: Any) -> object:
        raise RuntimeError("provider secret")

    monkeypatch.setattr(runtime, "create_product_agent", fail_product)

    with pytest.raises(runtime.AgentRuntimeBuildError, match="Agent 런타임 초기화") as exc_info:
        await runtime.build_runtime_answer_service()

    assert "provider secret" not in str(exc_info.value)
    assert closed == ["qdrant", "embedding-http", "model-http"]


@pytest.mark.anyio
async def test_runtime_startup_cancellation_closes_created_http_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[str] = []
    created: dict[str, Any] = {}
    prewarm_started = asyncio.Event()
    _install_http_client_factory(monkeypatch, closed=closed, created=created)

    async def prewarm() -> None:
        prewarm_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(runtime, "create_chat_clovax", lambda **kwargs: object())
    monkeypatch.setattr(runtime, "create_clova_query_embedder", lambda **kwargs: object())
    monkeypatch.setattr(runtime, "prewarm_kiwi", prewarm)

    build = asyncio.create_task(runtime.build_runtime_answer_service())
    await prewarm_started.wait()
    build.cancel()

    with pytest.raises(asyncio.CancelledError):
        await build

    assert closed == ["embedding-http", "model-http"]


@pytest.mark.anyio
async def test_runtime_startup_cleanup_survives_repeated_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    prewarm_started = asyncio.Event()
    embedding_close_started = asyncio.Event()
    release_embedding_close = asyncio.Event()
    names = iter(("model-http", "embedding-http"))

    class BlockingHttpClients(FakeHttpClients):
        async def aclose(self) -> None:
            events.append(f"{self.name}-close-started")
            if self.name == "embedding-http":
                embedding_close_started.set()
                await release_embedding_close.wait()
            events.append(f"{self.name}-closed")

    def create(*, max_concurrency: int) -> BlockingHttpClients:
        del max_concurrency
        return BlockingHttpClients(next(names), [])

    async def prewarm() -> None:
        prewarm_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(runtime._ProviderHttpClients, "create", create)
    monkeypatch.setattr(runtime, "create_chat_clovax", lambda **kwargs: object())
    monkeypatch.setattr(runtime, "create_clova_query_embedder", lambda **kwargs: object())
    monkeypatch.setattr(runtime, "prewarm_kiwi", prewarm)

    build = asyncio.create_task(runtime.build_runtime_answer_service())
    await prewarm_started.wait()
    build.cancel()
    await embedding_close_started.wait()
    build.cancel()
    release_embedding_close.set()

    with pytest.raises(asyncio.CancelledError):
        await build

    assert events == [
        "embedding-http-close-started",
        "embedding-http-closed",
        "model-http-close-started",
        "model-http-closed",
    ]


@pytest.mark.anyio
async def test_provider_http_close_always_closes_sync_fallback() -> None:
    events: list[str] = []

    class SyncClient:
        def close(self) -> None:
            events.append("sync")

    class FailingAsyncClient:
        async def aclose(self) -> None:
            events.append("async")
            raise RuntimeError("close failed")

    clients = runtime._ProviderHttpClients(  # type: ignore[arg-type]
        sync=SyncClient(),
        async_=FailingAsyncClient(),
    )

    with pytest.raises(RuntimeError, match="close failed"):
        await clients.aclose()

    assert events == ["async", "sync"]
