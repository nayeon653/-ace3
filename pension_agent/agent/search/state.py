"""Search Agent의 요청 단위 실행 상태."""

from typing import Annotated, NotRequired

from langchain.agents import AgentState

from pension_agent.agent.contracts import Permission
from pension_agent.agent.search.schemas import SearchChunkPayload, SearchResult


def merge_observed_chunks(
    current: list[SearchChunkPayload],
    update: list[SearchChunkPayload],
) -> list[SearchChunkPayload]:
    """검색 Tool이 관찰한 청크를 ID 기준으로 누적한다."""

    by_id = {chunk.chunk_id: chunk for chunk in current}
    for chunk in update:
        by_id.setdefault(chunk.chunk_id, chunk)
    return list(by_id.values())


def merge_search_attempted(current: bool, update: bool) -> bool:
    """성공한 검색 Tool 호출 여부를 유지한다."""

    return current or update


class SearchAgentState(AgentState):
    """호출자가 주입한 문서 접근 권한을 포함하는 Search Agent 상태."""

    permission: Permission
    observed_chunks: Annotated[list[SearchChunkPayload], merge_observed_chunks]
    search_attempted: Annotated[bool, merge_search_attempted]
    search_result: NotRequired[SearchResult]
