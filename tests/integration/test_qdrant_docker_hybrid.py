"""Docker Qdrant에서 실제 적재와 기본 Hybrid 검색 계약을 검증한다."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient, QdrantClient

from pension_agent.config import DEFAULT_SEARCH_SERVICE_CONFIG
from pension_agent.core import SearchMode, SearchQuery
from pension_agent.ingest.qdrant_indexer import EmbeddingCache, ensure_collection, index_chunks
from pension_agent.ingest.qdrant_input import PreparedChunk
from pension_agent.retrieval import AsyncQdrantChunkRetriever

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("QDRANT_DOCKER_INTEGRATION") != "1",
        reason="Docker Qdrant 통합 테스트는 전용 CI job이나 make target에서 실행합니다.",
    ),
    pytest.mark.anyio,
]

_QDRANT_URL = "http://127.0.0.1:6333"
_DENSE_DIMENSIONS = 2


class _FixedDocumentEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["IRP 이전\nIRP 계좌 이전 절차와 가입 유형 확인"]
        return [[1.0, 0.0]]


def _chunk() -> PreparedChunk:
    point_id = str(uuid4())
    embedding_content = "IRP 이전\nIRP 계좌 이전 절차와 가입 유형 확인"
    return PreparedChunk(
        source_chunk_id="knowledge-hybrid-smoke-0000",
        point_id=point_id,
        canonical_doc_id="knowledge-hybrid-smoke",
        embedding_content=embedding_content,
        embedding_content_hash=hashlib.sha256(embedding_content.encode("utf-8")).hexdigest(),
        payload={
            "source_file_name": "hybrid-smoke.pdf",
            "source_format": "pdf",
            "document_type": "pension_reference",
            "chunk_index": 0,
            "content": "IRP 계좌 이전 절차와 가입 유형 확인",
            "embedding_content": embedding_content,
            "heading_path": ["IRP 이전"],
            "captions": [],
            "element_types": ["text"],
            "page_numbers": [1],
        },
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_indexed_chunk_is_found_by_default_hybrid_search(tmp_path: Path) -> None:
    assert DEFAULT_SEARCH_SERVICE_CONFIG.default_search_mode is SearchMode.HYBRID

    collection_name = f"pension_documents_hybrid_smoke_{uuid4().hex}"
    client = QdrantClient(
        url=_QDRANT_URL,
        cloud_inference=False,
    )
    async_client: AsyncQdrantClient | None = None
    try:
        ensure_collection(
            client,
            collection_name=collection_name,
            dense_dimensions=_DENSE_DIMENSIONS,
        )
        chunk = _chunk()
        with EmbeddingCache(tmp_path / "embedding_cache.sqlite3") as cache:
            result = index_chunks(
                client,
                collection_name=collection_name,
                chunks=[chunk],
                embedder=_FixedDocumentEmbedder(),
                embedding_model="test-bge-m3",
                dense_dimensions=_DENSE_DIMENSIONS,
                cache=cache,
            )

        assert result.complete is True
        async_client = AsyncQdrantClient(
            url=_QDRANT_URL,
            cloud_inference=False,
        )
        retriever = AsyncQdrantChunkRetriever(
            async_client,
            collection_name=collection_name,
        )
        hits = await retriever.search_chunks(
            SearchQuery(
                text="IRP 계좌 이전",
                dense=(1.0, 0.0),
                mode=DEFAULT_SEARCH_SERVICE_CONFIG.default_search_mode,
            ),
            limit=1,
        )

        assert [hit.chunk.chunk_id for hit in hits] == [chunk.point_id]
        assert hits[0].chunk.content == "IRP 계좌 이전 절차와 가입 유형 확인"
    finally:
        if async_client is not None:
            await async_client.close()
        if client.collection_exists(collection_name):
            client.delete_collection(collection_name)
        client.close()
