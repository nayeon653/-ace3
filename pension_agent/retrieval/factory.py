"""Qdrant SDK client와 검색 Adapter 조립."""

from qdrant_client import AsyncQdrantClient, QdrantClient

from pension_agent.config import QdrantConnection
from pension_agent.retrieval.qdrant_retriever import (
    AsyncQdrantChunkRetriever,
    QdrantChunkRetriever,
)


def create_qdrant_client(connection: QdrantConnection) -> QdrantClient:
    """환경 설정을 Qdrant SDK client로 변환한다."""

    api_key = connection.api_key.get_secret_value() if connection.api_key is not None else None
    return QdrantClient(
        url=connection.url,
        api_key=api_key,
        timeout=connection.timeout_seconds,
        cloud_inference=connection.cloud_inference_enabled,
    )


def create_qdrant_retriever(
    client: QdrantClient,
    *,
    connection: QdrantConnection,
) -> QdrantChunkRetriever:
    """연결 프로필의 collection과 prefetch 상한을 검색 Adapter에 적용한다."""

    return QdrantChunkRetriever(
        client,
        collection_name=connection.collection,
        prefetch_limit=connection.prefetch_limit,
    )


def create_async_qdrant_client(
    connection: QdrantConnection,
    *,
    pool_size: int | None = None,
) -> AsyncQdrantClient:
    """온라인 Agent용 native async Qdrant client를 만든다."""

    if pool_size is not None and pool_size < 1:
        raise ValueError("Qdrant async connection pool 크기는 1 이상이어야 합니다.")
    api_key = connection.api_key.get_secret_value() if connection.api_key is not None else None
    return AsyncQdrantClient(
        url=connection.url,
        api_key=api_key,
        timeout=connection.timeout_seconds,
        cloud_inference=connection.cloud_inference_enabled,
        pool_size=pool_size,
    )


def create_async_qdrant_retriever(
    client: AsyncQdrantClient,
    *,
    connection: QdrantConnection,
) -> AsyncQdrantChunkRetriever:
    """연결 프로필을 온라인 async 검색 Adapter에 적용한다."""

    return AsyncQdrantChunkRetriever(
        client,
        collection_name=connection.collection,
        prefetch_limit=connection.prefetch_limit,
    )
