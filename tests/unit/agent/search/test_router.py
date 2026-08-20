"""SearchRouter의 결정론적 단일 경로 선택을 검증한다."""

import pytest
from pydantic import ValidationError

from pension_agent.agent.search import SearchRequest, SearchRouter
from pension_agent.config import SearchServiceConfig
from pension_agent.core import DocumentType, SearchMode

_CHUNK_ID = "550e8400-e29b-41d4-a716-446655440000"
_PENSION_TYPES = frozenset({DocumentType.PENSION_REFERENCE})


def _router() -> SearchRouter:
    return SearchRouter(
        SearchServiceConfig(
            default_search_mode=SearchMode.DENSE,
            candidate_limit=7,
            result_limit=5,
            neighbor_before=2,
            neighbor_after=3,
        )
    )


def test_router_uses_global_search_for_plain_semantic_request() -> None:
    plan = _router().route(
        SearchRequest(objective="연금 이전 근거"),
        document_types=_PENSION_TYPES,
    )

    assert plan.route == "global"
    assert plan.query == "연금 이전 근거"
    assert plan.mode is SearchMode.DENSE
    assert plan.source_file_name is None
    assert plan.chunk_id is None
    assert plan.document_types == _PENSION_TYPES
    assert plan.candidate_limit == 7
    assert (plan.neighbor_before, plan.neighbor_after) == (2, 3)


def test_router_uses_document_route_only_for_explicit_source_hint() -> None:
    plan = _router().route(
        SearchRequest(
            objective="중도 해지 근거",
            source_file_name=" guide.pdf ",
            expand_neighbors=True,
        ),
        document_types=_PENSION_TYPES,
    )

    assert plan.route == "within_document"
    assert plan.query == "중도 해지 근거"
    assert plan.source_file_name == "guide.pdf"
    assert plan.expand_neighbors is True


def test_router_uses_chunk_lookup_only_for_explicit_chunk_hint() -> None:
    plan = _router().route(
        SearchRequest(
            objective="이 청크의 앞뒤 문맥",
            chunk_id=_CHUNK_ID.upper(),
            expand_neighbors=True,
        ),
        document_types=_PENSION_TYPES,
    )

    assert plan.route == "chunk_lookup"
    assert plan.chunk_id == _CHUNK_ID
    assert plan.query is None
    assert plan.mode is None
    assert plan.expand_neighbors is True


def test_router_copies_authorized_document_types_into_plan_provenance() -> None:
    product_types = frozenset({DocumentType.FUND_PROSPECTUS})

    plan = _router().route(
        SearchRequest(objective="펀드 수수료"),
        document_types=product_types,
    )

    assert plan.document_types == product_types


def test_router_fails_closed_for_empty_authorized_document_types() -> None:
    with pytest.raises(ValidationError):
        _router().route(
            SearchRequest(objective="연금 근거"),
            document_types=frozenset(),
        )
