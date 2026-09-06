"""상품별 근거 수집의 입력 경계, 부분 실패와 취소 전파를 검증한다."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from pension_agent.agent.contracts import Permission
from pension_agent.agent.contracts.comparison import ComparisonTarget
from pension_agent.agent.product.comparison import (
    ComparisonEvidenceResult,
    ProductComparisonService,
    ProductEvidence,
)
from pension_agent.agent.search import SearchChunkPayload, SearchRequest, SearchResult
from pension_agent.config import ProductComparisonConfig
from pension_agent.core import DocumentType
from pension_agent.retrieval import ProductCatalog, load_product_catalog

_CODES = ["KR5153420063", "KR5153420079", "KR5153420105"]
_COMPARISON_QUERY = "상품별 투자원금 손실 가능성과 안정성을 비교해 주세요."


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _targets(catalog: ProductCatalog, codes: list[str] | None = None) -> list[ComparisonTarget]:
    return [
        {
            "target_id": f"target-{index + 1}",
            "mention_parts": [entry.official_name],
            "resolution_status": "single",
            "product_code": entry.product_code,
            "official_name": entry.official_name,
            "provider": entry.provider,
        }
        for index, entry in enumerate(catalog.select_products(_CODES if codes is None else codes))
    ]


def _chunk(source: str, *, chunk_id: str | None = None) -> SearchChunkPayload:
    return SearchChunkPayload(
        chunk_id=chunk_id or str(uuid4()),
        source_file_name=source,
        document_type=DocumentType.FUND_PROSPECTUS,
        chunk_index=0,
        title="투자위험",
        locator="제2부 투자위험",
        content="이 투자신탁의 투자원금 손실 가능성을 확인해야 합니다.",
    )


class RecordingSearch:
    """실제 요청의 권한·문서 범위·마감과 독립 실행 수를 기록한다."""

    def __init__(
        self,
        callback: Callable[[SearchRequest], Awaitable[SearchResult]] | None = None,
    ) -> None:
        self.callback = callback
        self.calls: list[tuple[SearchRequest, Permission, float | None]] = []

    async def search(
        self,
        request: SearchRequest,
        *,
        permission: Permission,
        deadline: float | None = None,
    ) -> SearchResult:
        self.calls.append((request, permission, deadline))
        if self.callback is not None:
            return await self.callback(request)
        assert request.source_file_name is not None
        return SearchResult(
            execution_status="completed", retrieved_chunks=[_chunk(request.source_file_name)]
        )


async def _compare(
    service: ProductComparisonService,
    *,
    codes: list[str] | None = None,
    targets: list[ComparisonTarget] | None = None,
    comparison_query: str = _COMPARISON_QUERY,
    deadline: float | None = None,
) -> ComparisonEvidenceResult:
    return await service.compare(
        product_codes=_CODES if codes is None else codes,
        comparison_query=comparison_query,
        targets=_targets(service.catalog) if targets is None else targets,
        deadline=asyncio.get_running_loop().time() + 75 if deadline is None else deadline,
    )


@pytest.mark.anyio
async def test_comparison_parallel_searches_keep_order_scope_and_reserved_deadline() -> None:
    catalog = load_product_catalog()
    all_started = asyncio.Event()
    started = 0

    async def collect(request: SearchRequest) -> SearchResult:
        nonlocal started
        started += 1
        if started == len(_CODES):
            all_started.set()
        await asyncio.wait_for(all_started.wait(), timeout=1)
        assert request.source_file_name is not None
        return SearchResult(
            execution_status="completed", retrieved_chunks=[_chunk(request.source_file_name)]
        )

    search = RecordingSearch(collect)
    parent_deadline = asyncio.get_running_loop().time() + 40
    result = await _compare(ProductComparisonService(search, catalog), deadline=parent_deadline)

    assert result.execution_status == "completed"
    assert [product.product_code for product in result.products] == _CODES
    assert len(search.calls) == 3
    assert result.search_deadline == pytest.approx(parent_deadline - 30)
    assert "search_deadline" not in result.model_dump()
    for code, (request, permission, deadline) in zip(_CODES, search.calls, strict=True):
        assert request.source_file_name == catalog.resolve_source_file_name(code)
        assert permission is Permission.PRODUCT
        assert deadline == result.search_deadline
        assert request.objective == result.comparison_query == _COMPARISON_QUERY


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("statuses", "with_evidence", "expected_status"),
    [
        (["completed", "completed", "completed"], True, "completed"),
        (["completed", "failed", "timeout"], True, "completed"),
        (["completed", "failed", "timeout"], False, "completed"),
        (["completed", "completed", "completed"], False, "completed"),
        (["timeout", "timeout", "timeout"], False, "timeout"),
        (["failed", "failed", "failed"], False, "failed"),
        (["failed", "timeout", "timeout"], False, "failed"),
    ],
)
async def test_statuses_follow_success_attempts_even_when_they_find_no_chunks(
    statuses: list[str], with_evidence: bool, expected_status: str
) -> None:
    catalog = load_product_catalog()
    by_source = dict(
        zip((catalog.resolve_source_file_name(code) for code in _CODES), statuses, strict=True)
    )

    async def collect(request: SearchRequest) -> SearchResult:
        assert request.source_file_name is not None
        status = by_source[request.source_file_name]
        if status == "completed":
            return SearchResult(
                execution_status="completed",
                retrieved_chunks=[_chunk(request.source_file_name)] if with_evidence else [],
            )
        return SearchResult.model_validate({"execution_status": status, "error": "검색 오류"})

    result = await _compare(ProductComparisonService(RecordingSearch(collect), catalog))

    assert result.execution_status == expected_status
    assert [bool(product.evidence) for product in result.products] == [
        status == "completed" and with_evidence for status in statuses
    ]
    assert len(result.products) == 3
    assert (result.error is None) == (expected_status == "completed")
    if "failed" in statuses:
        assert any("검색 오류" in text for text in result.limitations)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "codes",
    [
        [],
        _CODES[:1],
        _CODES[:2],
        _CODES[::-1],
        [*_CODES, _CODES[0]],
        [*_CODES, "KR5153420022"],
        [_CODES[0], _CODES[1], "KR0000000000"],
        [*_CODES, *_CODES],
        [code.lower() for code in _CODES],
    ],
)
async def test_invalid_changed_or_incomplete_target_set_never_searches(codes: list[str]) -> None:
    search = RecordingSearch()
    result = await _compare(ProductComparisonService(search, load_product_catalog()), codes=codes)
    assert result.execution_status == "failed"
    assert not result.products
    assert not search.calls


@pytest.mark.anyio
async def test_changed_catalog_identity_is_rejected_before_search() -> None:
    catalog = load_product_catalog()
    search = RecordingSearch()
    targets = _targets(catalog)
    targets[0]["official_name"] = "다른 상품명"

    result = await _compare(ProductComparisonService(search, catalog), targets=targets)

    assert result.execution_status == "failed"
    assert not search.calls


@pytest.mark.anyio
@pytest.mark.parametrize(
    "query",
    [
        "환헤지 방식과 외화 노출을 비교해 주세요.",
        "설정일과 최근 결산일, 분배금 지급 주기를 비교해 주세요.",
        "운용 인력의 변경 내역과 운용 경험은 어떻게 다른가요?\n각 상품의 차이를 설명해 주세요.",
    ],
)
async def test_free_comparison_query_is_shared_verbatim_by_all_product_searches(query: str) -> None:
    catalog = load_product_catalog()
    search = RecordingSearch()

    result = await _compare(ProductComparisonService(search, catalog), comparison_query=query)

    assert result.execution_status == "completed"
    assert result.comparison_query == query
    assert len(search.calls) == len(_CODES)
    assert [request.objective for request, _, _ in search.calls] == [query] * len(_CODES)
    assert [request.source_file_name for request, _, _ in search.calls] == [
        catalog.resolve_source_file_name(code) for code in _CODES
    ]


@pytest.mark.anyio
async def test_query_outer_whitespace_is_normalized_once_for_search_and_writer_input() -> None:
    search = RecordingSearch()
    query = "  환헤지 방식과 외화 노출 비교\n조건과 예외도 설명해 주세요.  "

    result = await _compare(
        ProductComparisonService(search, load_product_catalog()), comparison_query=query
    )

    assert result.comparison_query == query.strip()
    assert all(request.objective == result.comparison_query for request, _, _ in search.calls)


@pytest.mark.anyio
@pytest.mark.parametrize("query", ["", " \n ", None, 123, ["환헤지 비교"]])
async def test_empty_or_nontext_comparison_query_never_searches(query: Any) -> None:
    search = RecordingSearch()

    result = await _compare(
        ProductComparisonService(search, load_product_catalog()), comparison_query=query
    )

    assert result.execution_status == "failed"
    assert result.products == []
    assert search.calls == []


@pytest.mark.anyio
async def test_unresolved_and_repeated_targets_are_preserved_without_duplicate_search() -> None:
    catalog = load_product_catalog()
    search = RecordingSearch()
    targets = _targets(catalog)
    targets.extend(
        [
            {
                "target_id": "target-4",
                "mention_parts": ["미식별"],
                "resolution_status": "not_found",
            },
            {**targets[0], "target_id": "target-5"},
        ]
    )
    result = await _compare(ProductComparisonService(search, catalog), targets=targets)
    assert result.targets == targets
    assert len(search.calls) == 3
    assert any("미식별" in text for text in result.limitations)
    targets.append({**targets[0], "target_id": "target-6"})
    invalid = await _compare(ProductComparisonService(search, catalog), targets=targets)
    assert invalid.execution_status == "failed"
    assert len(search.calls) == 3


@pytest.mark.anyio
async def test_expired_search_budget_preserves_unstarted_timeout_attempts() -> None:
    search = RecordingSearch()
    result = await _compare(
        ProductComparisonService(search, load_product_catalog()),
        deadline=asyncio.get_running_loop().time() + 20,
    )
    assert result.execution_status == "timeout"
    assert len(result.products) == 3
    assert all(product.attempts[0].execution_status == "timeout" for product in result.products)
    assert not search.calls


@pytest.mark.anyio
async def test_shared_timeout_cancels_and_drains_all_outstanding_searches() -> None:
    stopped = 0

    async def wait_forever(request: SearchRequest) -> SearchResult:
        nonlocal stopped
        del request
        try:
            await asyncio.Event().wait()
        finally:
            stopped += 1
        raise AssertionError("도달할 수 없습니다.")

    search = RecordingSearch(wait_forever)
    config = ProductComparisonConfig(search_timeout_seconds=0.02)
    result = await _compare(ProductComparisonService(search, load_product_catalog(), config))
    assert result.execution_status == "timeout"
    assert stopped == len(search.calls) == 3


@pytest.mark.anyio
async def test_parent_cancellation_propagates_after_draining_child_searches() -> None:
    all_started = asyncio.Event()
    started = stopped = 0

    async def wait_forever(request: SearchRequest) -> SearchResult:
        nonlocal started, stopped
        del request
        started += 1
        if started == 3:
            all_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped += 1
        raise AssertionError("도달할 수 없습니다.")

    service = ProductComparisonService(RecordingSearch(wait_forever), load_product_catalog())
    task = asyncio.create_task(_compare(service))
    await asyncio.wait_for(all_started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped == 3


@pytest.mark.anyio
async def test_other_product_source_cannot_be_injected_into_search_result() -> None:
    async def wrong_source(request: SearchRequest) -> SearchResult:
        del request
        return SearchResult(
            execution_status="completed", retrieved_chunks=[_chunk("R2_KR5153420022.pdf")]
        )

    result = await _compare(
        ProductComparisonService(RecordingSearch(wrong_source), load_product_catalog())
    )
    assert result.execution_status == "failed"
    assert all(not product.evidence for product in result.products)


@pytest.mark.anyio
async def test_shared_document_alias_preserves_separate_product_associations() -> None:
    loaded = load_product_catalog()
    catalog = ProductCatalog.from_payloads(
        {"products": [entry.to_dict() for entry in loaded.select_products(_CODES)]},
        {"aliases": {_CODES[1]: _CODES[0]}},
    )
    shared = _chunk(catalog.resolve_source_file_name(_CODES[0]))

    async def collect(request: SearchRequest) -> SearchResult:
        assert request.source_file_name is not None
        chunk = (
            shared
            if request.source_file_name == shared.source_file_name
            else _chunk(request.source_file_name)
        )
        return SearchResult(execution_status="completed", retrieved_chunks=[chunk])

    result = await _compare(ProductComparisonService(RecordingSearch(collect), catalog))
    assert result.products[0].evidence == result.products[1].evidence == [shared]
    assert result.products[0].product_code != result.products[1].product_code


def test_evidence_model_rejects_unrecorded_or_cross_source_chunks() -> None:
    chunk = _chunk("expected.pdf")
    with pytest.raises(ValidationError):
        ProductEvidence(
            product_code=_CODES[0],
            official_name="상품",
            provider="운용사",
            source_file_name="expected.pdf",
            attempts=[SearchResult(execution_status="completed")],
            evidence=[chunk],
        )
    with pytest.raises(ValidationError):
        ProductEvidence(
            product_code=_CODES[0],
            official_name="상품",
            provider="운용사",
            source_file_name="other.pdf",
            attempts=[SearchResult(execution_status="completed", retrieved_chunks=[chunk])],
            evidence=[chunk],
        )
