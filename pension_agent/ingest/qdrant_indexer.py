"""검증된 청크를 임베딩하고 Qdrant에 재개 가능하게 적재한다."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Protocol, Self

import numpy as np
from openai import OpenAIError
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ApiException

from pension_agent.ingest.qdrant_input import PreparedChunk
from pension_agent.retrieval.qdrant_retriever import (
    BM25_OPTIONS,
    DENSE_VECTOR_NAME,
    SPARSE_MODEL_NAME,
    SPARSE_VECTOR_NAME,
    to_bm25_text,
)

_PAYLOAD_INDEXES = {
    "source_file_name": models.PayloadSchemaType.KEYWORD,
    "document_type": models.PayloadSchemaType.KEYWORD,
    "chunk_index": models.PayloadSchemaType.INTEGER,
}


class DocumentEmbedder(Protocol):
    """적재기가 요구하는 문서 임베딩 경계."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """입력 순서와 같은 dense vector 목록을 반환한다."""


class QdrantIndexingError(RuntimeError):
    """외부 임베딩·Qdrant 적재를 안전하게 완료하지 못한 경우."""


@dataclass(frozen=True)
class IndexProgress:
    """완료된 upsert batch의 누적 상태."""

    processed: int
    total: int
    embedded: int
    cache_hits: int


@dataclass(frozen=True)
class IndexResult:
    """한 번의 적재 실행 결과."""

    processed: int
    total_input_chunks: int
    embedded: int
    cache_hits: int
    collection_points: int
    complete: bool


class EmbeddingCache:
    """중단 후 재실행에서 유료 임베딩을 재사용하는 SQLite cache."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                point_id TEXT NOT NULL,
                model TEXT NOT NULL,
                source_chunk_id TEXT NOT NULL,
                embedding_content_hash TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                vector BLOB NOT NULL,
                PRIMARY KEY (point_id, model)
            )
            """
        )
        self._connection.commit()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def get(
        self,
        chunk: PreparedChunk,
        *,
        model: str,
        dimensions: int,
    ) -> list[float] | None:
        row = self._connection.execute(
            """
            SELECT source_chunk_id, embedding_content_hash, dimensions, vector
            FROM embeddings
            WHERE point_id = ? AND model = ?
            """,
            (chunk.point_id, model),
        ).fetchone()
        if row is None:
            row = self._connection.execute(
                """
                SELECT source_chunk_id, embedding_content_hash, dimensions, vector
                FROM embeddings
                WHERE model = ? AND embedding_content_hash = ? AND dimensions = ?
                LIMIT 1
                """,
                (model, chunk.embedding_content_hash, dimensions),
            ).fetchone()
        if row is None:
            return None

        _source_chunk_id, content_hash, stored_dimensions, vector_blob = row
        if content_hash != chunk.embedding_content_hash or stored_dimensions != dimensions:
            return None

        vector = np.frombuffer(vector_blob, dtype="<f4")
        if vector.size != dimensions:
            return None
        return vector.astype(float).tolist()

    def put_many(
        self,
        rows: Sequence[tuple[PreparedChunk, Sequence[float]]],
        *,
        model: str,
        dimensions: int,
    ) -> None:
        values = []
        for chunk, vector in rows:
            array = np.asarray(vector, dtype="<f4")
            if array.shape != (dimensions,) or not np.isfinite(array).all():
                raise QdrantIndexingError("임베딩 vector가 저장 계약을 위반했습니다.")
            values.append(
                (
                    chunk.point_id,
                    model,
                    chunk.source_chunk_id,
                    chunk.embedding_content_hash,
                    dimensions,
                    array.tobytes(),
                )
            )

        self._connection.executemany(
            """
            INSERT INTO embeddings (
                point_id,
                model,
                source_chunk_id,
                embedding_content_hash,
                dimensions,
                vector
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(point_id, model) DO UPDATE SET
                source_chunk_id = excluded.source_chunk_id,
                embedding_content_hash = excluded.embedding_content_hash,
                dimensions = excluded.dimensions,
                vector = excluded.vector
            """,
            values,
        )
        self._connection.commit()


def ensure_collection(
    client: QdrantClient,
    *,
    collection_name: str,
    dense_dimensions: int,
) -> bool:
    """collection을 한 번만 만들고 기존 collection은 계약 일치만 확인한다."""

    try:
        created = not client.collection_exists(collection_name)
        if created:
            client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    DENSE_VECTOR_NAME: models.VectorParams(
                        size=dense_dimensions,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    )
                },
            )

        info = client.get_collection(collection_name)
        _validate_collection(info, dense_dimensions=dense_dimensions)
        _ensure_payload_indexes(client, collection_name=collection_name, info=info)
        return created
    except QdrantIndexingError:
        raise
    except (ApiException, RuntimeError, TypeError, ValueError):
        raise QdrantIndexingError("Qdrant collection 준비에 실패했습니다.") from None


def index_chunks(
    client: QdrantClient,
    *,
    collection_name: str,
    chunks: Sequence[PreparedChunk],
    embedder: DocumentEmbedder,
    embedding_model: str,
    dense_dimensions: int,
    cache: EmbeddingCache,
    batch_size: int = 16,
    limit: int | None = None,
    progress: Callable[[IndexProgress], None] | None = None,
) -> IndexResult:
    """cache miss만 임베딩하고 결정적 UUID로 idempotent upsert한다."""

    if batch_size < 1:
        raise ValueError("batch_size는 1 이상이어야 합니다.")
    if limit is not None and limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다.")

    selected = chunks[:limit] if limit is not None else chunks
    embedded = 0
    cache_hits = 0

    for start in range(0, len(selected), batch_size):
        batch = selected[start : start + batch_size]
        vectors: list[list[float] | None] = []
        missing_by_hash: dict[str, PreparedChunk] = {}
        for chunk in batch:
            cached = cache.get(
                chunk,
                model=embedding_model,
                dimensions=dense_dimensions,
            )
            vectors.append(cached)
            if cached is None:
                missing_by_hash.setdefault(chunk.embedding_content_hash, chunk)
            else:
                cache_hits += 1

        missing = list(missing_by_hash.values())
        if missing:
            try:
                generated = embedder.embed_documents([chunk.embedding_content for chunk in missing])
            except (OpenAIError, RuntimeError, TypeError, ValueError):
                raise QdrantIndexingError("CLOVA Studio 문서 임베딩에 실패했습니다.") from None
            _validate_embeddings(
                generated,
                expected_count=len(missing),
                dimensions=dense_dimensions,
            )
            cache.put_many(
                list(zip(missing, generated, strict=True)),
                model=embedding_model,
                dimensions=dense_dimensions,
            )
            generated_iter = iter(generated)
            generated_by_hash = {
                chunk.embedding_content_hash: vector
                for chunk, vector in zip(missing, generated_iter, strict=True)
            }
            vectors = [
                generated_by_hash[chunk.embedding_content_hash] if vector is None else vector
                for chunk, vector in zip(batch, vectors, strict=True)
            ]
            embedded += len(generated)

        points = [
            _point(chunk, vector)
            for chunk, vector in zip(batch, vectors, strict=True)
            if vector is not None
        ]
        try:
            client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True,
            )
        except (ApiException, ImportError, RuntimeError, TypeError, ValueError):
            raise QdrantIndexingError("Qdrant point upsert에 실패했습니다.") from None

        if progress is not None:
            progress(
                IndexProgress(
                    processed=start + len(batch),
                    total=len(selected),
                    embedded=embedded,
                    cache_hits=cache_hits,
                )
            )

    try:
        collection_points = client.count(
            collection_name=collection_name,
            exact=True,
        ).count
    except (ApiException, RuntimeError, TypeError, ValueError):
        raise QdrantIndexingError("Qdrant point 수 검증에 실패했습니다.") from None

    complete = limit is None
    if complete and collection_points != len(chunks):
        raise QdrantIndexingError(
            "전체 적재 후 Qdrant point 수가 입력 청크 수와 일치하지 않습니다."
        )

    return IndexResult(
        processed=len(selected),
        total_input_chunks=len(chunks),
        embedded=embedded,
        cache_hits=cache_hits,
        collection_points=collection_points,
        complete=complete,
    )


def _validate_collection(info: models.CollectionInfo, *, dense_dimensions: int) -> None:
    vectors = info.config.params.vectors
    sparse_vectors = info.config.params.sparse_vectors
    if not isinstance(vectors, dict) or DENSE_VECTOR_NAME not in vectors:
        raise QdrantIndexingError("기존 collection에 dense named vector가 없습니다.")
    dense = vectors[DENSE_VECTOR_NAME]
    if dense.size != dense_dimensions or dense.distance != models.Distance.COSINE:
        raise QdrantIndexingError("기존 collection의 dense vector 설정이 다릅니다.")
    if not isinstance(sparse_vectors, dict) or SPARSE_VECTOR_NAME not in sparse_vectors:
        raise QdrantIndexingError("기존 collection에 sparse named vector가 없습니다.")
    if sparse_vectors[SPARSE_VECTOR_NAME].modifier != models.Modifier.IDF:
        raise QdrantIndexingError("기존 collection의 sparse vector 설정이 다릅니다.")


def _ensure_payload_indexes(
    client: QdrantClient,
    *,
    collection_name: str,
    info: models.CollectionInfo,
) -> None:
    for field_name, field_type in _PAYLOAD_INDEXES.items():
        existing = info.payload_schema.get(field_name)
        if existing is not None:
            if existing.data_type != field_type:
                raise QdrantIndexingError(
                    f"기존 collection의 {field_name} payload index 형식이 다릅니다."
                )
            continue
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field_name,
            field_schema=field_type,
            wait=True,
        )


def _validate_embeddings(
    vectors: Sequence[Sequence[float]],
    *,
    expected_count: int,
    dimensions: int,
) -> None:
    if len(vectors) != expected_count:
        raise QdrantIndexingError("임베딩 응답 수가 입력 수와 일치하지 않습니다.")
    for vector in vectors:
        if len(vector) != dimensions or not all(
            not isinstance(value, bool) and isfinite(float(value)) for value in vector
        ):
            raise QdrantIndexingError("임베딩 vector가 저장 계약을 위반했습니다.")


def _point(chunk: PreparedChunk, vector: Sequence[float]) -> models.PointStruct:
    sparse_text = to_bm25_text(chunk.embedding_content)
    if not sparse_text:
        raise QdrantIndexingError("Sparse 전처리 결과가 빈 청크입니다.")
    return models.PointStruct(
        id=chunk.point_id,
        vector={
            DENSE_VECTOR_NAME: [float(value) for value in vector],
            SPARSE_VECTOR_NAME: models.Document(
                text=sparse_text,
                model=SPARSE_MODEL_NAME,
                options=BM25_OPTIONS,
            ),
        },
        payload=chunk.payload,
    )
