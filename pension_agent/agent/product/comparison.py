"""확정된 비교 상품마다 문서 근거를 독립적으로 수집한다."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from math import isfinite

from langsmith import traceable
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from pension_agent.agent.contracts import ExecutionStatus, Permission, document_types_for_permission
from pension_agent.agent.contracts.comparison import ComparisonTarget
from pension_agent.agent.search import SearchChunkPayload, SearchRequest, SearchResult, SearchRunner
from pension_agent.config import DEFAULT_PRODUCT_COMPARISON_CONFIG, ProductComparisonConfig
from pension_agent.retrieval.product_catalog import ProductCatalog

_TARGETS_ADAPTER = TypeAdapter(list[ComparisonTarget])


class ProductEvidence(BaseModel):
    """한 상품의 검색 시도와 성공 시도에서만 누적한 원문 근거."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    product_code: str
    official_name: str
    provider: str
    source_file_name: str
    attempts: list[SearchResult] = Field(min_length=1)
    evidence: list[SearchChunkPayload] = Field(default_factory=list)

    def model_post_init(self, context: object, /) -> None:
        """다른 문서의 청크와 완료되지 않은 시도의 근거를 거절한다."""

        del context
        expected: dict[str, SearchChunkPayload] = {}
        for attempt in self.attempts:
            for chunk in attempt.retrieved_chunks:
                if not _authorized_chunk(chunk, self.source_file_name):
                    raise ValueError("상품 검색 근거의 문서 범위가 올바르지 않습니다.")
                if chunk.chunk_id in expected and expected[chunk.chunk_id] != chunk:
                    raise ValueError("같은 청크 ID의 상품 검색 근거가 서로 다릅니다.")
                expected.setdefault(chunk.chunk_id, chunk)
        if self.evidence != list(expected.values()):
            raise ValueError("상품 근거는 완료된 검색 시도의 중복 없는 합집합이어야 합니다.")


class ComparisonEvidenceResult(BaseModel):
    """원래 비교 대상, 상품별 검색 상태와 고정된 검색 마감."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    execution_status: ExecutionStatus
    catalog_version: str
    comparison_query: str
    targets: list[ComparisonTarget]
    products: list[ProductEvidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    error: str | None = None
    search_deadline: float | None = Field(default=None, exclude=True, repr=False)

    def model_post_init(self, context: object, /) -> None:
        """수집 상태와 근거 범위, 상품 순서의 일관성을 검증한다."""

        del context
        if self.execution_status != "completed":
            if self.error is None or any(product.evidence for product in self.products):
                raise ValueError("실패한 비교 검색에는 오류가 필요하며 근거는 금지됩니다.")
        elif self.error is not None:
            raise ValueError("완료된 비교 검색에는 전체 오류를 포함할 수 없습니다.")
        if self.products:
            if [product.product_code for product in self.products] != _resolved_codes(self.targets):
                raise ValueError("비교 검색 상품은 확정된 대상 전체와 순서까지 같아야 합니다.")
            if self.execution_status != _aggregate_status(self.products):
                raise ValueError("전체 검색 상태가 상품별 시도와 일치하지 않습니다.")


@dataclass(frozen=True, slots=True)
class ProductComparisonService:
    """같은 검색 마감과 기존 SearchRunner의 동시성 제한을 공유한다."""

    search_service: SearchRunner
    catalog: ProductCatalog
    config: ProductComparisonConfig = DEFAULT_PRODUCT_COMPARISON_CONFIG

    @traceable(name="product_comparison_search", run_type="chain")
    async def compare(
        self,
        product_codes: list[str],
        comparison_query: str,
        targets: list[ComparisonTarget],
        deadline: float,
    ) -> ComparisonEvidenceResult:
        """입력을 검증한 뒤 모든 확정 상품을 한 번씩 병렬 검색한다."""

        safe_targets: list[ComparisonTarget] = []
        safe_query = comparison_query.strip() if isinstance(comparison_query, str) else ""
        try:
            safe_targets = _TARGETS_ADAPTER.validate_python(targets)
            self._validate_inputs(product_codes, safe_query, safe_targets, deadline)
        except (ValueError, TypeError, ValidationError):
            return ComparisonEvidenceResult(
                execution_status="failed",
                catalog_version=self.catalog.version,
                comparison_query=safe_query,
                targets=safe_targets,
                error="상품 비교 입력의 대상 또는 비교 쿼리가 올바르지 않습니다.",
            )

        search_deadline = min(
            asyncio.get_running_loop().time() + self.config.search_timeout_seconds,
            deadline - self.config.submission_reserve_seconds,
        )
        entries = self.catalog.select_products(product_codes)
        requests = [
            SearchRequest(
                objective=safe_query,
                source_file_name=self.catalog.resolve_source_file_name(entry.product_code),
            )
            for entry in entries
        ]
        tasks = [
            asyncio.create_task(self._search(request, search_deadline=search_deadline))
            for request in requests
        ]
        try:
            attempts = await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        products = [
            ProductEvidence(
                product_code=entry.product_code,
                official_name=entry.official_name,
                provider=entry.provider,
                source_file_name=self.catalog.resolve_source_file_name(entry.product_code),
                attempts=[attempt],
                evidence=attempt.retrieved_chunks,
            )
            for entry, attempt in zip(entries, attempts, strict=True)
        ]
        return self._assemble(products, safe_targets, safe_query, search_deadline)

    def _validate_inputs(
        self,
        product_codes: list[str],
        comparison_query: str,
        targets: list[ComparisonTarget],
        deadline: float,
    ) -> None:
        if (
            not isinstance(product_codes, list)
            or not 2 <= len(product_codes) <= self.config.max_targets
        ):
            raise ValueError("비교 상품 수가 올바르지 않습니다.")
        if not 2 <= len(targets) <= self.config.max_targets:
            raise ValueError("비교 대상 수가 올바르지 않습니다.")
        if not comparison_query:
            raise ValueError("상품 비교 쿼리가 비어 있습니다.")
        if product_codes != _resolved_codes(targets):
            raise ValueError("상품 코드가 확정된 대상 전체와 일치하지 않습니다.")
        if len({target["target_id"] for target in targets}) != len(targets):
            raise ValueError("비교 대상 ID가 중복됩니다.")
        if not isfinite(deadline):
            raise ValueError("상위 실행 마감이 올바르지 않습니다.")
        entries = self.catalog.select_products(product_codes)
        if [entry.product_code for entry in entries] != product_codes:
            raise ValueError("상품 코드는 카탈로그의 정규화된 코드여야 합니다.")
        by_code = {entry.product_code: entry for entry in entries}
        for target in targets:
            if not target["mention_parts"] or any(
                not part.strip() for part in target["mention_parts"]
            ):
                raise ValueError("비교 대상의 원문 표현이 없습니다.")
            if target["resolution_status"] == "single":
                entry = by_code[target["product_code"]]
                if (
                    target.get("official_name") != entry.official_name
                    or target.get("provider") != entry.provider
                ):
                    raise ValueError("상품의 공식명 또는 운용사가 카탈로그와 다릅니다.")
            elif any(key in target for key in ("product_code", "official_name", "provider")):
                raise ValueError("미식별 대상에 확정 상품 정보를 넣을 수 없습니다.")

    async def _search(self, request: SearchRequest, *, search_deadline: float) -> SearchResult:
        if search_deadline <= asyncio.get_running_loop().time():
            return _timeout_result()
        try:
            async with asyncio.timeout_at(search_deadline):
                result = await self.search_service.search(
                    request, permission=Permission.PRODUCT, deadline=search_deadline
                )
            if not isinstance(result, SearchResult) or any(
                not _authorized_chunk(chunk, request.source_file_name)
                for chunk in result.retrieved_chunks
            ):
                return SearchResult(
                    execution_status="failed",
                    error="상품 검색 결과의 문서 범위가 올바르지 않습니다.",
                )
            return result
        except TimeoutError:
            return _timeout_result()
        except Exception:  # noqa: BLE001
            return SearchResult(execution_status="failed", error="상품 문서 검색에 실패했습니다.")

    def _assemble(
        self,
        products: list[ProductEvidence],
        targets: list[ComparisonTarget],
        comparison_query: str,
        search_deadline: float,
    ) -> ComparisonEvidenceResult:
        status = _aggregate_status(products)
        limitations: list[str] = []
        for target in targets:
            if target["resolution_status"] != "single":
                limitations.append(
                    f"{' '.join(target['mention_parts'])}: 비교 대상을 확정하지 못했습니다."
                )
        for product in products:
            for attempt in product.attempts:
                limitations.extend(
                    f"{product.official_name}: {text}" for text in attempt.limitations
                )
                if attempt.error:
                    limitations.append(f"{product.official_name}: {attempt.error}")
        return ComparisonEvidenceResult(
            execution_status=status,
            catalog_version=self.catalog.version,
            comparison_query=comparison_query,
            targets=targets,
            products=products,
            limitations=list(dict.fromkeys(limitations)),
            error=(
                None
                if status == "completed"
                else "상품 비교 검색 시간이 초과됐습니다."
                if status == "timeout"
                else "상품 비교 문서 검색에 실패했습니다."
            ),
            search_deadline=search_deadline,
        )


def _resolved_codes(targets: list[ComparisonTarget]) -> list[str]:
    try:
        return list(
            dict.fromkeys(
                target["product_code"]
                for target in targets
                if target["resolution_status"] == "single"
            )
        )
    except KeyError:
        raise ValueError("확정 대상에 상품 코드가 없습니다.") from None


def _aggregate_status(products: list[ProductEvidence]) -> ExecutionStatus:
    statuses = {attempt.execution_status for product in products for attempt in product.attempts}
    if "completed" in statuses:
        return "completed"
    return "failed" if "failed" in statuses else "timeout"


def _authorized_chunk(chunk: SearchChunkPayload, source_file_name: str | None) -> bool:
    return (
        chunk.source_file_name == source_file_name
        and chunk.document_type in document_types_for_permission(Permission.PRODUCT)
    )


def _timeout_result() -> SearchResult:
    return SearchResult(execution_status="timeout", error="상품 비교 검색 시간이 초과됐습니다.")
