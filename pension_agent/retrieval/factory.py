"""Qdrant SDK client와 검색 Adapter 조립."""

from qdrant_client import QdrantClient

from pension_agent.config import QdrantConnection
from pension_agent.retrieval.qdrant_retriever import QdrantChunkRetriever


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
