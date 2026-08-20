"""CLOVA bge-m3 검색·문서 임베더 팩토리를 검증한다."""

from __future__ import annotations

import asyncio
from threading import Lock
from time import sleep
from typing import Any

import pytest
from httpx import AsyncClient, Client
from pydantic import SecretStr

from pension_agent.config import BGE_M3_EMBEDDING_CONFIG, ClovaStudioConnection
from pension_agent.retrieval.clova_embedder import (
    ClovaDocumentEmbedder,
    ClovaEmbeddingFactoryError,
    create_clova_query_embedder,
)


class _Client:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.lock = Lock()

    def embed_query(self, text: str) -> list[float]:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        sleep(0.01)
        with self.lock:
            self.active -= 1
        return [float(text)]


def test_embedding_profile_is_fixed_to_bge_m3() -> None:
    assert BGE_M3_EMBEDDING_CONFIG.model == "bge-m3"
    assert BGE_M3_EMBEDDING_CONFIG.dimensions == 1024


def test_embedder_factory_requires_credentials() -> None:
    with pytest.raises(ClovaEmbeddingFactoryError, match="CLOVASTUDIO_API_KEY"):
        create_clova_query_embedder(
            config=BGE_M3_EMBEDDING_CONFIG,
            connection=ClovaStudioConnection(api_key=None, api_base_url="https://example.com"),
        )


def test_connection_secret_repr_is_safe() -> None:
    connection = ClovaStudioConnection(
        api_key=SecretStr("secret-token"),
        api_base_url="https://example.com",
    )

    assert "secret-token" not in repr(connection)


def test_embed_documents_preserves_order_and_limits_concurrency() -> None:
    client = _Client()
    embedder = ClovaDocumentEmbedder(  # type: ignore[arg-type]
        client=client,
        max_workers=2,
        requests_per_minute=60_000,
    )

    result = embedder.embed_documents(["3", "1", "2"])

    assert result == [[3.0], [1.0], [2.0]]
    assert client.max_active == 2


def test_embed_documents_returns_empty_without_creating_work() -> None:
    client = _Client()
    embedder = ClovaDocumentEmbedder(  # type: ignore[arg-type]
        client=client,
        max_workers=2,
        requests_per_minute=60_000,
    )

    assert embedder.embed_documents([]) == []
    assert client.max_active == 0


def test_embedder_rejects_invalid_worker_count() -> None:
    with pytest.raises(ValueError, match="worker"):
        ClovaDocumentEmbedder(client=Any, max_workers=0)  # type: ignore[arg-type]


def test_embedder_rejects_invalid_request_rate() -> None:
    with pytest.raises(ValueError, match="분당"):
        ClovaDocumentEmbedder(  # type: ignore[arg-type]
            client=Any,
            requests_per_minute=0,
        )


def test_query_embedder_uses_runtime_owned_http_clients() -> None:
    connection = ClovaStudioConnection(
        api_key=SecretStr("test-secret-key"),
        api_base_url="https://example.test/v1/openai",
    )
    http_client = Client()
    http_async_client = AsyncClient()
    try:
        embedder = create_clova_query_embedder(
            config=BGE_M3_EMBEDDING_CONFIG,
            connection=connection,
            http_client=http_client,
            http_async_client=http_async_client,
        )

        assert embedder.http_client is http_client
        assert embedder.http_async_client is http_async_client
    finally:
        http_client.close()
        asyncio.run(http_async_client.aclose())
