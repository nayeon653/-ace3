"""Search Agent의 Tool 응답과 최종 결과 계약을 검증한다."""

from typing import Any

import pytest
from pydantic import ValidationError

from pension_agent.agent.search import (
    GetChunkPayload,
    NeighborChunksPayload,
    SearchChunkPayload,
    SearchHitPayload,
    SearchHitsPayload,
    SearchResult,
    SearchSelection,
    SearchToolErrorPayload,
)
from pension_agent.core import DocumentType

_CHUNK_ID = "550e8400-e29b-41d4-a716-446655440000"
_OTHER_CHUNK_ID = "123e4567-e89b-12d3-a456-426614174000"


def _chunk(*, chunk_id: str = _CHUNK_ID) -> SearchChunkPayload:
    return SearchChunkPayload(
        chunk_id=chunk_id,
        source_file_name="guide.pdf",
        document_type=DocumentType.PENSION_REFERENCE,
        chunk_index=2,
        title="계좌 이전",
        locator="3페이지",
        content="연금계좌 이전 절차",
    )


def test_tool_success_payloads_preserve_stable_json_shapes() -> None:
    chunk = _chunk()
    chunk_json = chunk.model_dump(mode="json")

    assert SearchHitsPayload(hits=[SearchHitPayload(score=0.8, chunk=chunk)]).model_dump(
        mode="json"
    ) == {"hits": [{"score": 0.8, "chunk": chunk.model_dump(mode="json")}]}
    assert NeighborChunksPayload(chunks=[chunk]).model_dump(mode="json") == {"chunks": [chunk_json]}
    assert GetChunkPayload(chunk=chunk).model_dump(mode="json") == {"chunk": chunk_json}
    assert GetChunkPayload(chunk=None).model_dump(mode="json") == {"chunk": None}


def test_search_tool_error_requires_only_sanitized_message() -> None:
    payload = SearchToolErrorPayload(error="검색 Tool 실행에 실패했습니다.")

    assert payload.model_dump() == {"error": "검색 Tool 실행에 실패했습니다."}
    with pytest.raises(ValidationError):
        SearchToolErrorPayload(error="", provider_error="secret")


def test_search_selection_normalizes_unique_chunk_ids() -> None:
    selection = SearchSelection(
        coverage="sufficient",
        selected_chunk_ids=[_CHUNK_ID.upper(), _OTHER_CHUNK_ID],
        limitations=[],
    )

    assert selection.selected_chunk_ids == [_CHUNK_ID, _OTHER_CHUNK_ID]


@pytest.mark.parametrize(
    "values",
    [
        {"coverage": "none", "selected_chunk_ids": [_CHUNK_ID]},
        {"coverage": "partial", "selected_chunk_ids": []},
        {"coverage": "sufficient", "selected_chunk_ids": [_CHUNK_ID, _CHUNK_ID]},
        {"coverage": "sufficient", "selected_chunk_ids": ["not-a-uuid"]},
    ],
)
def test_search_selection_rejects_invalid_combinations(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SearchSelection.model_validate(values)


@pytest.mark.parametrize(
    ("coverage", "chunks"),
    [
        ("sufficient", [_chunk()]),
        ("partial", [_chunk()]),
        ("none", []),
    ],
)
def test_completed_search_result_accepts_valid_coverage_combinations(
    coverage: str,
    chunks: list[SearchChunkPayload],
) -> None:
    result = SearchResult(
        execution_status="completed",
        coverage=coverage,
        selected_chunks=chunks,
    )

    assert result.coverage == coverage
    assert result.selected_chunks == chunks
    assert result.error is None


@pytest.mark.parametrize(
    "values",
    [
        {"execution_status": "completed", "coverage": None},
        {
            "execution_status": "completed",
            "coverage": "sufficient",
            "selected_chunks": [],
        },
        {
            "execution_status": "completed",
            "coverage": "none",
            "selected_chunks": [_chunk()],
        },
        {
            "execution_status": "completed",
            "coverage": "none",
            "error": "완료 결과의 오류",
        },
        {"execution_status": "failed", "error": None},
        {
            "execution_status": "failed",
            "coverage": "partial",
            "error": "검색 실패",
        },
        {
            "execution_status": "timeout",
            "selected_chunks": [_chunk()],
            "error": "검색 시간 초과",
        },
        {
            "execution_status": "completed",
            "coverage": "sufficient",
            "selected_chunks": [_chunk(), _chunk()],
        },
    ],
)
def test_search_result_rejects_invalid_state_combinations(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SearchResult.model_validate(values)


@pytest.mark.parametrize("execution_status", ["failed", "timeout"])
def test_unsuccessful_search_result_requires_sanitized_error(
    execution_status: str,
) -> None:
    result = SearchResult(execution_status=execution_status, error="검색을 완료하지 못했습니다.")

    assert result.coverage is None
    assert result.selected_chunks == []
    assert result.error == "검색을 완료하지 못했습니다."
