"""Qdrant 적재기의 cache, batch, vector 검증 동작을 확인한다."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from qdrant_client import models

from pension_agent.ingest.qdrant_indexer import (
    EmbeddingCache,
    QdrantIndexingError,
    index_chunks,
)
from pension_agent.ingest.qdrant_input import PreparedChunk


def _chunk(index: int) -> PreparedChunk:
    text = f"퇴직 연금 청크 {index}"
    return PreparedChunk(
        source_chunk_id=f"knowledge-abc-{index:04d}",
        point_id=f"550e8400-e29b-41d4-a716-{index:012d}",
        canonical_doc_id="knowledge-abc",
        embedding_content=text,
        embedding_content_hash=f"{index:064x}",
        payload={"content": text},
    )


class _Embedder:
    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions
        self.calls: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(index + 1)] * self.dimensions for index, _text in enumerate(texts)]


class _Client:
    def __init__(self) -> None:
        self.points: dict[str, models.PointStruct] = {}
        self.upsert_calls = 0

    def upsert(self, **kwargs: Any) -> None:
        self.upsert_calls += 1
        for point in kwargs["points"]:
            self.points[str(point.id)] = point

    def count(self, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(count=len(self.points))


def test_index_chunks_reuses_cache_on_retry(tmp_path: Path) -> None:
    client = _Client()
    embedder = _Embedder(dimensions=3)
    chunks = [_chunk(0), _chunk(1)]

    with EmbeddingCache(tmp_path / "cache.sqlite3") as cache:
        first = index_chunks(
            client,  # type: ignore[arg-type]
            collection_name="test",
            chunks=chunks,
            embedder=embedder,
            embedding_model="bge-m3",
            dense_dimensions=3,
            cache=cache,
            batch_size=2,
        )
        second = index_chunks(
            client,  # type: ignore[arg-type]
            collection_name="test",
            chunks=chunks,
            embedder=embedder,
            embedding_model="bge-m3",
            dense_dimensions=3,
            cache=cache,
            batch_size=2,
        )

    assert first.embedded == 2
    assert first.cache_hits == 0
    assert second.embedded == 0
    assert second.cache_hits == 2
    assert len(embedder.calls) == 1
    assert client.upsert_calls == 2
    point = client.points[chunks[0].point_id]
    assert isinstance(point.vector, dict)
    assert point.vector["dense"] == [1.0, 1.0, 1.0]
    assert isinstance(point.vector["sparse"], models.Document)


def test_index_chunks_rejects_wrong_embedding_dimensions(tmp_path: Path) -> None:
    client = _Client()
    embedder = _Embedder(dimensions=2)

    with (
        EmbeddingCache(tmp_path / "cache.sqlite3") as cache,
        pytest.raises(QdrantIndexingError, match="vector"),
    ):
        index_chunks(
            client,  # type: ignore[arg-type]
            collection_name="test",
            chunks=[_chunk(0)],
            embedder=embedder,
            embedding_model="bge-m3",
            dense_dimensions=3,
            cache=cache,
        )


def test_limit_marks_run_partial_and_does_not_require_full_count(tmp_path: Path) -> None:
    client = _Client()
    embedder = _Embedder(dimensions=3)

    with EmbeddingCache(tmp_path / "cache.sqlite3") as cache:
        result = index_chunks(
            client,  # type: ignore[arg-type]
            collection_name="test",
            chunks=[_chunk(0), _chunk(1)],
            embedder=embedder,
            embedding_model="bge-m3",
            dense_dimensions=3,
            cache=cache,
            limit=1,
        )

    assert result.complete is False
    assert result.processed == 1
    assert result.collection_points == 1


def test_identical_embedding_content_is_embedded_once(tmp_path: Path) -> None:
    client = _Client()
    embedder = _Embedder(dimensions=3)
    first = _chunk(0)
    second = PreparedChunk(
        source_chunk_id="knowledge-other-0000",
        point_id="550e8400-e29b-41d4-a716-999999999999",
        canonical_doc_id="knowledge-other",
        embedding_content=first.embedding_content,
        embedding_content_hash=first.embedding_content_hash,
        payload={"content": first.embedding_content},
    )

    with EmbeddingCache(tmp_path / "cache.sqlite3") as cache:
        result = index_chunks(
            client,  # type: ignore[arg-type]
            collection_name="test",
            chunks=[first, second],
            embedder=embedder,
            embedding_model="bge-m3",
            dense_dimensions=3,
            cache=cache,
            batch_size=2,
        )

    assert result.embedded == 1
    assert embedder.calls == [[first.embedding_content]]
    assert len(client.points) == 2
