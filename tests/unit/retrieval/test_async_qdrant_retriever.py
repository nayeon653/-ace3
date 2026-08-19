"""온라인 AsyncQdrantChunkRetriever의 native async 경계를 검증한다."""

import asyncio
from threading import Event, Lock, get_ident
from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec, patch
from uuid import UUID

import pytest
from qdrant_client import AsyncQdrantClient, models

from pension_agent.config import QdrantConnection
from pension_agent.core import DocumentType, NeighborRequest, SearchFilters, SearchMode, SearchQuery
from pension_agent.retrieval import (
    AsyncQdrantChunkRetriever,
    async_to_bm25_text,
    create_async_qdrant_client,
)

_CHUNK_ID = "550e8400-e29b-41d4-a716-446655440000"


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_file_name": "guide.pdf",
        "source_format": "pdf",
        "document_type": "pension_reference",
        "chunk_index": 7,
        "content": "퇴직연금의 근거 본문입니다.",
        "embedding_content": "퇴직연금\n퇴직연금의 근거 본문입니다.",
        "heading_path": ["제2장", "가입 절차"],
        "captions": [],
        "element_types": ["text"],
        "page_numbers": [12],
    }
    payload.update(overrides)
    return payload


def _scored_point() -> models.ScoredPoint:
    return models.ScoredPoint(
        id=_CHUNK_ID,
        version=1,
        score=0.8,
        payload=_payload(),
    )


def _search() -> tuple[AsyncQdrantChunkRetriever, AsyncQdrantClient]:
    client = create_autospec(AsyncQdrantClient, instance=True)
    return AsyncQdrantChunkRetriever(client, collection_name="pension_documents"), client


def test_async_hybrid_search_awaits_qdrant_with_shared_filter() -> None:
    search, client = _search()
    client.query_points.return_value = SimpleNamespace(points=[_scored_point()])
    filters = SearchFilters(document_types=frozenset({DocumentType.PENSION_REFERENCE}))

    with patch(
        "pension_agent.retrieval.qdrant_retriever.async_to_bm25_text",
        AsyncMock(return_value="퇴직 연금 가입 절차"),
    ):
        hits = asyncio.run(
            search.search_chunks(
                SearchQuery(text="퇴직연금 가입 절차", dense=(0.1, 0.2)),
                filters=filters,
                limit=5,
            )
        )

    client.query_points.assert_awaited_once()
    kwargs = client.query_points.await_args.kwargs
    sparse, dense = kwargs["prefetch"]
    assert sparse.filter == dense.filter
    assert kwargs["query"] == models.FusionQuery(fusion=models.Fusion.RRF)
    assert hits[0].chunk.title == "가입 절차"


def test_async_sparse_search_skips_qdrant_without_content_tokens() -> None:
    search, client = _search()

    with patch(
        "pension_agent.retrieval.qdrant_retriever.async_to_bm25_text",
        AsyncMock(return_value=""),
    ):
        hits = asyncio.run(search.search_chunks(SearchQuery(text="?!", mode=SearchMode.SPARSE)))

    assert hits == []
    client.query_points.assert_not_awaited()


def test_async_neighbor_and_chunk_queries_await_qdrant() -> None:
    search, client = _search()
    client.scroll.return_value = (
        [
            models.Record(id=UUID(_CHUNK_ID), payload=_payload(chunk_index=8)),
            models.Record(id=UUID(_CHUNK_ID), payload=_payload(chunk_index=6)),
        ],
        None,
    )
    client.retrieve.return_value = [models.Record(id=UUID(_CHUNK_ID), payload=_payload())]

    async def scenario() -> tuple[list[int], str | None]:
        chunks = await search.get_neighbor_chunks(
            NeighborRequest(source_file_name="guide.pdf", chunk_index=7),
            document_types=frozenset({DocumentType.PENSION_REFERENCE}),
        )
        chunk = await search.get_chunk(_CHUNK_ID)
        return [item.chunk_index for item in chunks], chunk.chunk_id if chunk is not None else None

    indexes, chunk_id = asyncio.run(scenario())

    assert indexes == [6, 8]
    assert chunk_id == _CHUNK_ID
    client.scroll.assert_awaited_once()
    client.retrieve.assert_awaited_once()


def test_async_bm25_processing_runs_outside_event_loop_thread() -> None:
    event_loop_thread: int | None = None
    worker_thread: int | None = None

    def tokenize(text: str) -> str:
        nonlocal worker_thread
        worker_thread = get_ident()
        return text

    async def scenario() -> str:
        nonlocal event_loop_thread
        event_loop_thread = get_ident()
        return await async_to_bm25_text("퇴직연금")

    with patch("pension_agent.retrieval.qdrant_retriever.to_bm25_text", side_effect=tokenize):
        result = asyncio.run(scenario())

    assert result == "퇴직연금"
    assert worker_thread is not None
    assert worker_thread != event_loop_thread


def test_cancelled_bm25_call_keeps_capacity_until_worker_really_finishes() -> None:
    release_first = Event()
    counter_lock = Lock()
    active = 0
    max_active = 0

    async def scenario() -> tuple[bool, str]:
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        loop = asyncio.get_running_loop()

        def tokenize(text: str) -> str:
            nonlocal active, max_active
            with counter_lock:
                active += 1
                max_active = max(max_active, active)
            try:
                if text == "첫째":
                    loop.call_soon_threadsafe(first_started.set)
                    release_first.wait(timeout=1)
                else:
                    loop.call_soon_threadsafe(second_started.set)
                return text
            finally:
                with counter_lock:
                    active -= 1

        with patch(
            "pension_agent.retrieval.qdrant_retriever.to_bm25_text",
            side_effect=tokenize,
        ):
            first = asyncio.create_task(async_to_bm25_text("첫째"))
            await first_started.wait()
            first.cancel()
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(first, timeout=0.05)
            second = asyncio.create_task(async_to_bm25_text("둘째"))
            await asyncio.sleep(0.02)
            overlapped = second_started.is_set()
            release_first.set()
            second_result = await second
        return overlapped, second_result

    overlapped, second_result = asyncio.run(scenario())

    assert overlapped is False
    assert second_result == "둘째"
    assert max_active == 1


def test_async_qdrant_factory_forwards_connection_pool_size() -> None:
    connection = QdrantConnection(
        url="https://example.cloud.qdrant.io",
        collection="pension",
    )

    with patch("pension_agent.retrieval.factory.AsyncQdrantClient") as client_type:
        client = create_async_qdrant_client(connection, pool_size=4)

    assert client is client_type.return_value
    assert client_type.call_args.kwargs["pool_size"] == 4
