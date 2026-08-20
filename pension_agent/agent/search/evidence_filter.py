"""검색 후보를 원문 근거 후보로 정제하는 결정론적 필터."""

from dataclasses import dataclass
from math import isfinite

from pension_agent.agent.search.schemas import SearchChunkPayload
from pension_agent.config import SearchServiceConfig
from pension_agent.core import RetrievedChunk, SearchHit

_NAVIGATION_TITLES = frozenset({"목차", "질문 목록", "질문 리스트"})


@dataclass(frozen=True, slots=True)
class EvidenceFilter:
    """권한 검증이 끝난 검색 후보의 중복·순위·크기를 정리한다."""

    config: SearchServiceConfig

    def filter_hits(self, hits: list[SearchHit]) -> list[RetrievedChunk]:
        """점수 순서로 중복과 탐색 전용 청크를 제거하고 최종 후보를 제한한다."""

        ranked = sorted(hits, key=lambda hit: hit.score, reverse=True)
        selected: list[RetrievedChunk] = []
        seen: set[str] = set()
        for hit in ranked:
            if not isfinite(hit.score):
                continue
            if self.config.minimum_score is not None and hit.score < self.config.minimum_score:
                continue
            chunk = hit.chunk
            if chunk.chunk_id in seen or _is_navigation_only(chunk):
                continue
            seen.add(chunk.chunk_id)
            selected.append(chunk)
            if len(selected) == self.config.result_limit:
                break
        return selected

    def filter_chunks(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """직접·인접 조회 청크를 입력 순서대로 검증하고 중복을 제거한다."""

        return self.filter_context(chunks)

    def filter_context(
        self,
        chunks: list[RetrievedChunk],
        *,
        anchor_chunk_id: str | None = None,
    ) -> list[RetrievedChunk]:
        """인접 문맥의 문서 순서와 필수 anchor 청크를 함께 보존한다."""

        selected: list[RetrievedChunk] = []
        seen: set[str] = set()
        for chunk in chunks:
            if chunk.chunk_id in seen or _is_navigation_only(chunk):
                continue
            seen.add(chunk.chunk_id)
            selected.append(chunk)
        if len(selected) <= self.config.result_limit:
            return selected
        if anchor_chunk_id is None:
            return selected[: self.config.result_limit]
        anchor = next(
            (chunk for chunk in selected if chunk.chunk_id == anchor_chunk_id),
            None,
        )
        if anchor is None:
            raise ValueError("EvidenceFilter 문맥에 anchor 청크가 없습니다.")
        nearest_ids = {
            chunk.chunk_id
            for chunk in sorted(
                selected,
                key=lambda chunk: (
                    abs(chunk.chunk_index - anchor.chunk_index),
                    chunk.chunk_index,
                ),
            )[: self.config.result_limit]
        }
        return [chunk for chunk in selected if chunk.chunk_id in nearest_ids]

    def to_payloads(self, chunks: list[RetrievedChunk]) -> list[SearchChunkPayload]:
        """검증된 원본 청크를 Domain Agent 공개 계약으로 변환한다."""

        return [
            SearchChunkPayload(
                chunk_id=chunk.chunk_id,
                source_file_name=chunk.source_file_name,
                document_type=chunk.document_type,
                chunk_index=chunk.chunk_index,
                title=chunk.title,
                locator=chunk.locator,
                content=chunk.content,
            )
            for chunk in chunks
        ]


def _is_navigation_only(chunk: RetrievedChunk) -> bool:
    """목차나 질문 색인처럼 단독 답변 근거가 아닌 청크를 보수적으로 제외한다."""

    normalized_title = " ".join(chunk.title.split()).casefold()
    if normalized_title in _NAVIGATION_TITLES and not any(
        marker in chunk.content.casefold() for marker in ("답변", "answer")
    ):
        return True
    lines = [line.strip() for line in chunk.content.splitlines() if line.strip()]
    return len(lines) >= 2 and all(line.endswith(("?", "？")) for line in lines)
