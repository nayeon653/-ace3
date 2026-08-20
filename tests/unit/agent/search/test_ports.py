"""외부 provider의 프로세스 공용 async 동시성 경계를 검증한다."""

import asyncio

from pension_agent.agent.execution import AsyncConcurrencyLimiter
from pension_agent.agent.search import LimitedChunkRetriever, LimitedQueryEmbedder
from pension_agent.core import SearchHit, SearchQuery


class RecordingEmbedder:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def aembed_query(self, text: str) -> list[float]:
        del text
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return [0.1]
        finally:
            self.active -= 1


class RecordingRetriever:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def search_chunks(self, query: SearchQuery, **kwargs: object) -> list[SearchHit]:
        del query, kwargs
        return await self._record([])

    async def search_within_document(
        self,
        query: SearchQuery,
        **kwargs: object,
    ) -> list[SearchHit]:
        del query, kwargs
        return await self._record([])

    async def get_neighbor_chunks(self, request: object, **kwargs: object) -> list[object]:
        del request, kwargs
        return await self._record([])

    async def get_chunk(self, chunk_id: str, **kwargs: object) -> None:
        del chunk_id, kwargs
        return await self._record(None)

    async def _record(self, result: object) -> object:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return result
        finally:
            self.active -= 1


def test_limited_query_embedder_serializes_shared_provider_calls() -> None:
    inner = RecordingEmbedder()
    embedder = LimitedQueryEmbedder(inner, AsyncConcurrencyLimiter(1))

    async def scenario() -> None:
        await asyncio.gather(*(embedder.aembed_query(str(index)) for index in range(3)))

    asyncio.run(scenario())

    assert inner.max_active == 1


def test_limited_chunk_retriever_shares_one_limit_across_operations() -> None:
    inner = RecordingRetriever()
    retriever = LimitedChunkRetriever(inner, AsyncConcurrencyLimiter(1))

    async def scenario() -> None:
        await asyncio.gather(
            retriever.search_chunks(SearchQuery(text="첫째", dense=(0.1,))),
            retriever.search_within_document(
                SearchQuery(text="둘째", dense=(0.1,)),
                source_file_name="guide.pdf",
            ),
        )

    asyncio.run(scenario())

    assert inner.max_active == 1
