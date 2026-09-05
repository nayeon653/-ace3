"""상품별 근거 수집의 입력 경계, 부분 실패와 취소 전파를 검증한다."""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest
from pydantic import ValidationError

from pension_agent.agent.contracts import Permission
from pension_agent.agent.contracts.comparison import ComparisonCriterion, ComparisonTarget
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
_CRITERIA: list[ComparisonCriterion] = ["risk", "capital_protection"]


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
    criteria: list[ComparisonCriterion] | None = None,
    deadline: float | None = None,
) -> ComparisonEvidenceResult:
    return await service.compare(
        product_codes=_CODES if codes is None else codes,
        criteria=_CRITERIA if criteria is None else criteria,
        targets=_targets(service.catalog) if targets is None else targets,
        expected_criteria=_CRITERIA,
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
    assert result.retrieval_coverage == "all_products"
    assert [product.product_code for product in result.products] == _CODES
    assert len(search.calls) == 3
    assert result.search_deadline == pytest.approx(parent_deadline - 30)
    assert "search_deadline" not in result.model_dump()
    for code, (request, permission, deadline) in zip(_CODES, search.calls, strict=True):
        assert request.source_file_name == catalog.resolve_source_file_name(code)
        assert permission is Permission.PRODUCT
        assert deadline == result.search_deadline
        assert "투자위험등급" in request.objective
        assert "원금보장" in request.objective
        assert "판매수수료" not in request.objective


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("statuses", "with_evidence", "expected_status", "coverage"),
    [
        (["completed", "completed", "completed"], True, "completed", "all_products"),
        (["completed", "failed", "timeout"], True, "completed", "some_products"),
        (["completed", "failed", "timeout"], False, "completed", "no_products"),
        (["completed", "completed", "completed"], False, "completed", "no_products"),
        (["timeout", "timeout", "timeout"], False, "timeout", "no_products"),
        (["failed", "failed", "failed"], False, "failed", "no_products"),
        (["failed", "timeout", "timeout"], False, "failed", "no_products"),
    ],
)
async def test_statuses_follow_success_attempts_even_when_they_find_no_chunks(
    statuses: list[str], with_evidence: bool, expected_status: str, coverage: str
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
    assert result.retrieval_coverage == coverage
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
async def test_changed_criteria_and_catalog_identity_are_rejected_before_search() -> None:
    catalog = load_product_catalog()
    search = RecordingSearch()
    service = ProductComparisonService(search, catalog)
    result = await _compare(service, criteria=["risk"])
    assert result.execution_status == "failed"
    targets = _targets(catalog)
    targets[0]["official_name"] = "다른 상품명"
    result = await _compare(service, targets=targets)
    assert result.execution_status == "failed"
    assert not search.calls


@pytest.mark.anyio
@pytest.mark.parametrize(
    "criteria, allowed",
    [
        ([], False),
        (["risk"], True),
        (["risk", "fees", "liquidity"], True),
        (["investment_strategy", "risk", "capital_protection", "fees"], False),
    ],
)
async def test_criterion_count_is_checked_before_search_even_when_plan_matches(
    criteria: list[ComparisonCriterion], allowed: bool
) -> None:
    catalog = load_product_catalog()
    search = RecordingSearch()
    result = await ProductComparisonService(search, catalog).compare(
        product_codes=_CODES,
        criteria=criteria,
        expected_criteria=criteria,
        targets=_targets(catalog),
        deadline=asyncio.get_running_loop().time() + 75,
    )

    assert result.execution_status == ("completed" if allowed else "failed")
    assert len(search.calls) == (3 if allowed else 0)
    if not allowed:
        assert result.products == []


def test_configuration_cannot_raise_criterion_limit_above_three() -> None:
    assert ProductComparisonConfig().max_criteria == 3
    with pytest.raises(ValidationError):
        ProductComparisonConfig(max_criteria=4)


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
    assert result.retrieval_coverage == "all_products"
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
async def test_failed_supplements_keep_prior_evidence_and_consume_actual_budget() -> None:
    search = RecordingSearch()
    service = ProductComparisonService(search, load_product_catalog())
    result = await _compare(service)
    original_chunks = [product.evidence for product in result.products]
    original_deadline = result.search_deadline

    async def fail(request: SearchRequest) -> SearchResult:
        del request
        raise RuntimeError("private-provider-error")

    search.callback = fail
    for code in _CODES[:2]:
        result = await service.supplement(result, code, "금리변동 위험", original_deadline + 100)
    assert result.execution_status == "completed"
    assert result.retrieval_coverage == "all_products"
    assert result.search_deadline == original_deadline
    assert [product.evidence for product in result.products] == original_chunks
    assert [len(product.attempts) for product in result.products] == [2, 2, 1]
    assert len(search.calls) == 5
    for code in _CODES:
        result = await service.supplement(result, code, "위험등급", original_deadline + 100)
    assert len(search.calls) == 5
    assert all(call[2] == original_deadline for call in search.calls)
    assert "private-provider-error" not in result.model_dump_json()


@pytest.mark.anyio
async def test_supplement_deduplicates_success_and_rejects_other_products() -> None:
    search = RecordingSearch()
    service = ProductComparisonService(search, load_product_catalog())
    result = await _compare(service)
    original = result.products[0].evidence[0]
    additional = _chunk(original.source_file_name)

    async def collect(request: SearchRequest) -> SearchResult:
        del request
        return SearchResult(execution_status="completed", retrieved_chunks=[original, additional])

    search.callback = collect
    assert result.search_deadline is not None
    result = await service.supplement(result, _CODES[0], "금리 위험", result.search_deadline)
    assert result.products[0].evidence == [original, additional]
    result = await service.supplement(result, "KR5153420022", "금리 위험", result.search_deadline)
    result = await service.supplement(result, _CODES[0], "금리 위험", result.search_deadline)
    assert len(search.calls) == 4


@pytest.mark.anyio
@pytest.mark.parametrize("expand_neighbors", [False, True])
async def test_supplement_preserves_neighbor_expansion_with_original_scope_and_deadline(
    expand_neighbors: bool,
) -> None:
    search = RecordingSearch()
    service = ProductComparisonService(search, load_product_catalog())
    result = await _compare(service)
    assert result.search_deadline is not None

    await service.supplement(
        result,
        _CODES[0],
        "위험등급 앞뒤 문맥 확인",
        result.search_deadline + 100,
        expand_neighbors=expand_neighbors,
    )

    request, permission, deadline = search.calls[-1]
    assert request.expand_neighbors is expand_neighbors
    assert request.source_file_name == result.products[0].source_file_name
    assert permission is Permission.PRODUCT
    assert deadline == result.search_deadline
    assert len(search.calls) == 4


@pytest.mark.anyio
async def test_supplement_cannot_extend_original_search_deadline() -> None:
    search = RecordingSearch()
    service = ProductComparisonService(search, load_product_catalog())
    result = await _compare(service)
    result = result.model_copy(update={"search_deadline": asyncio.get_running_loop().time() - 1})
    updated = await service.supplement(
        result, _CODES[0], "위험", asyncio.get_running_loop().time() + 75
    )
    assert len(search.calls) == 3
    assert updated.products == result.products
    assert updated.search_deadline == result.search_deadline


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
    assert result.retrieval_coverage == "no_products"
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
    assert result.retrieval_coverage == "all_products"
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
