"""EvidenceFilter의 순위, 중복 제거와 문맥 보존 규칙을 검증한다."""

from uuid import UUID

import pytest

from pension_agent.agent.search import EvidenceFilter
from pension_agent.config import SearchServiceConfig
from pension_agent.core import DocumentType, ElementType, RetrievedChunk, SearchHit


def _chunk(
    chunk_index: int,
    *,
    title: str | None = None,
    content: str | None = None,
    chunk_id: str | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id or str(UUID(int=chunk_index + 1)),
        source_file_name="guide.pdf",
        source_format="pdf",
        document_type=DocumentType.PENSION_REFERENCE,
        chunk_index=chunk_index,
        content=content or f"{chunk_index}번 청크의 연금 근거",
        heading_path=("연금",),
        captions=(),
        element_types=(ElementType.TEXT,),
        page_numbers=(chunk_index + 1,),
        title=title or f"연금 근거 {chunk_index}",
        locator=f"{chunk_index + 1}페이지",
    )


def _filter(
    *,
    result_limit: int = 5,
    minimum_score: float | None = None,
) -> EvidenceFilter:
    return EvidenceFilter(
        SearchServiceConfig(
            candidate_limit=10,
            result_limit=result_limit,
            minimum_score=minimum_score,
        )
    )


def test_filter_hits_ranks_then_removes_low_score_duplicate_and_navigation_chunks() -> None:
    first = _chunk(1)
    second = _chunk(2)
    navigation = _chunk(3, title=" 목차 ", content="1. 가입\n2. 이전")
    hits = [
        SearchHit(chunk=first, score=0.7),
        SearchHit(chunk=second, score=0.9),
        SearchHit(chunk=second, score=0.8),
        SearchHit(chunk=navigation, score=0.99),
        SearchHit(chunk=_chunk(4), score=0.49),
        SearchHit(chunk=_chunk(5), score=float("nan")),
    ]

    selected = _filter(result_limit=2, minimum_score=0.5).filter_hits(hits)

    assert selected == [second, first]


@pytest.mark.parametrize(
    "chunk",
    [
        _chunk(1, title="질문 목록", content="가입할 수 있나요?\n이전할 수 있나요?"),
        _chunk(2, title="FAQ", content="가입할 수 있나요？\n이전할 수 있나요?"),
    ],
)
def test_filter_chunks_removes_navigation_only_content(chunk: RetrievedChunk) -> None:
    assert _filter().filter_chunks([chunk]) == []


def test_navigation_title_with_answer_content_is_preserved() -> None:
    chunk = _chunk(
        1,
        title="질문 목록",
        content="가입할 수 있나요?\n답변: 가입 요건을 충족하면 가능합니다.",
    )

    assert _filter().filter_chunks([chunk]) == [chunk]


def test_filter_context_keeps_document_order_and_anchor_when_truncated() -> None:
    chunks = [_chunk(index) for index in range(1, 6)]
    anchor = chunks[3]

    selected = _filter(result_limit=2).filter_context(
        chunks,
        anchor_chunk_id=anchor.chunk_id,
    )

    assert [chunk.chunk_index for chunk in selected] == [3, 4]
    assert anchor in selected


def test_filter_context_requires_anchor_when_truncation_needs_it() -> None:
    chunks = [_chunk(index) for index in range(3)]

    with pytest.raises(ValueError, match="anchor"):
        _filter(result_limit=2).filter_context(
            chunks,
            anchor_chunk_id=str(UUID(int=100)),
        )


def test_filter_context_without_anchor_preserves_order_and_limit() -> None:
    duplicate_id = str(UUID(int=10))
    first = _chunk(1, chunk_id=duplicate_id)
    duplicate = _chunk(2, chunk_id=duplicate_id)
    third = _chunk(3)

    assert _filter(result_limit=2).filter_context([first, duplicate, third]) == [first, third]


def test_to_payloads_exposes_only_domain_search_contract_fields() -> None:
    chunk = _chunk(2)

    payload = _filter().to_payloads([chunk])[0]

    assert payload.model_dump(mode="json") == {
        "chunk_id": chunk.chunk_id,
        "source_file_name": "guide.pdf",
        "document_type": "pension_reference",
        "chunk_index": 2,
        "title": "연금 근거 2",
        "locator": "3페이지",
        "content": "2번 청크의 연금 근거",
    }
