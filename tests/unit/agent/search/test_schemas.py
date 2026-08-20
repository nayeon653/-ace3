"""Router 기반 검색 요청, 계획과 원문 결과 계약을 검증한다."""

from typing import Any

import pytest
from pydantic import ValidationError

from pension_agent.agent.search import (
    SearchChunkPayload,
    SearchPlan,
    SearchRequest,
    SearchResult,
)
from pension_agent.core import DocumentType, SearchMode

_CHUNK_ID = "550e8400-e29b-41d4-a716-446655440000"
_OTHER_CHUNK_ID = "123e4567-e89b-12d3-a456-426614174000"
_DOCUMENT_TYPES = frozenset({DocumentType.PENSION_REFERENCE})


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


def _plan_values(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "route": "global",
        "query": "IRP 이전",
        "mode": SearchMode.HYBRID,
        "document_types": _DOCUMENT_TYPES,
        "candidate_limit": 10,
        "neighbor_before": 1,
        "neighbor_after": 1,
    }
    values.update(overrides)
    return values


def test_search_request_normalizes_semantic_hints() -> None:
    request = SearchRequest(
        objective="  IRP 이전 근거  ",
        chunk_id=_CHUNK_ID.upper(),
        expand_neighbors=True,
    )

    assert request.objective == "IRP 이전 근거"
    assert request.chunk_id == _CHUNK_ID
    assert request.expand_neighbors is True


@pytest.mark.parametrize(
    "values",
    [
        {"objective": ""},
        {"objective": "근거", "chunk_id": "not-a-uuid"},
        {"objective": "근거", "expand_neighbors": 1},
        {
            "objective": "근거",
            "source_file_name": "guide.pdf",
            "chunk_id": _CHUNK_ID,
        },
        {"objective": "근거", "mode": "hybrid"},
    ],
)
def test_search_request_rejects_invalid_or_implementation_level_inputs(
    values: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        SearchRequest.model_validate(values)


@pytest.mark.parametrize(
    "values",
    [
        _plan_values(),
        _plan_values(
            route="within_document",
            source_file_name="guide.pdf",
        ),
        _plan_values(
            route="chunk_lookup",
            query=None,
            mode=None,
            chunk_id=_CHUNK_ID,
        ),
    ],
)
def test_search_plan_accepts_one_self_contained_initial_route(values: dict[str, Any]) -> None:
    plan = SearchPlan.model_validate(values)

    assert plan.document_types == _DOCUMENT_TYPES
    assert plan.candidate_limit == 10
    assert plan.neighbor_before == 1
    assert plan.neighbor_after == 1


@pytest.mark.parametrize(
    "values",
    [
        _plan_values(query=None),
        _plan_values(source_file_name="guide.pdf"),
        _plan_values(route="within_document"),
        _plan_values(
            route="within_document",
            source_file_name="guide.pdf",
            chunk_id=_CHUNK_ID,
        ),
        _plan_values(route="chunk_lookup", query=None, mode=None),
        _plan_values(route="chunk_lookup", chunk_id=_CHUNK_ID),
        _plan_values(document_types=frozenset()),
        _plan_values(candidate_limit=True),
        _plan_values(neighbor_before=50, neighbor_after=50),
    ],
)
def test_search_plan_rejects_ambiguous_or_unbounded_routes(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SearchPlan.model_validate(values)


def test_search_chunk_payload_has_stable_raw_json_shape() -> None:
    assert _chunk().model_dump(mode="json") == {
        "chunk_id": _CHUNK_ID,
        "source_file_name": "guide.pdf",
        "document_type": "pension_reference",
        "chunk_index": 2,
        "title": "계좌 이전",
        "locator": "3페이지",
        "content": "연금계좌 이전 절차",
    }


def test_completed_search_result_allows_raw_chunks_or_no_matches() -> None:
    with_chunks = SearchResult(
        execution_status="completed",
        retrieved_chunks=[_chunk()],
        limitations=["최종 판단은 Domain Agent가 수행합니다."],
    )
    without_chunks = SearchResult(execution_status="completed")

    assert with_chunks.retrieved_chunks == [_chunk()]
    assert with_chunks.error is None
    assert without_chunks.retrieved_chunks == []


@pytest.mark.parametrize(
    "values",
    [
        {"execution_status": "completed", "error": "완료 결과의 오류"},
        {"execution_status": "failed"},
        {
            "execution_status": "timeout",
            "retrieved_chunks": [_chunk()],
            "error": "시간 초과",
        },
        {
            "execution_status": "completed",
            "retrieved_chunks": [_chunk(), _chunk()],
        },
        {"execution_status": "completed", "coverage": "sufficient"},
        {"execution_status": "completed", "selected_chunks": [_chunk()]},
    ],
)
def test_search_result_rejects_invalid_or_old_contract_fields(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SearchResult.model_validate(values)


@pytest.mark.parametrize("execution_status", ["failed", "timeout"])
def test_unsuccessful_search_result_requires_only_sanitized_error(
    execution_status: str,
) -> None:
    result = SearchResult(
        execution_status=execution_status,
        error="검색을 완료하지 못했습니다.",
    )

    assert result.retrieved_chunks == []
    assert result.error == "검색을 완료하지 못했습니다."


def test_search_result_rejects_duplicate_chunk_ids_even_when_payloads_differ() -> None:
    duplicate = _chunk().model_copy(update={"content": "다른 내용"})

    with pytest.raises(ValidationError, match="중복"):
        SearchResult(execution_status="completed", retrieved_chunks=[_chunk(), duplicate])


def test_search_schema_is_immutable() -> None:
    request = SearchRequest(objective="연금 근거")

    with pytest.raises(ValidationError, match="frozen"):
        request.objective = "변경"


def test_search_chunk_payload_normalizes_uuid() -> None:
    assert _chunk(chunk_id=_OTHER_CHUNK_ID.upper()).chunk_id == _OTHER_CHUNK_ID
