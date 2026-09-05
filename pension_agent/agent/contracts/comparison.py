"""복수 상품 비교의 공유 구조와 근거 귀속 계약."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal, NotRequired

from pydantic import ConfigDict, TypeAdapter, with_config
from typing_extensions import TypedDict

from pension_agent.config.product_comparison import MAX_PRODUCT_COMPARISON_CRITERIA

if TYPE_CHECKING:
    from pension_agent.agent.contracts.domain import EvidenceChunk

ComparisonCriterion = Literal[
    "investment_strategy", "risk", "capital_protection", "fees", "liquidity"
]
ComparisonCoverage = Literal["complete", "partial", "none"]


@with_config(ConfigDict(extra="forbid", strict=True))
class ComparisonTarget(TypedDict):
    """원문에서 식별한 대상과 카탈로그의 확정 또는 미식별 결과."""

    target_id: str
    mention_parts: list[str]
    resolution_status: Literal["single", "ambiguous", "not_found"]
    product_code: NotRequired[str]
    official_name: NotRequired[str]
    provider: NotRequired[str]


@with_config(ConfigDict(extra="forbid", strict=True))
class ComparisonEvidenceRef(TypedDict):
    """상품별 완료 검색에 속하는 근거 참조."""

    product_code: str
    chunk_id: str


@with_config(ConfigDict(extra="forbid", strict=True))
class ComparisonCell(TypedDict):
    """한 대상과 비교 항목에 대한 사실, 출처 및 제한."""

    target_id: str
    criterion: ComparisonCriterion
    status: Literal["supported", "not_verified", "conflicting", "not_comparable"]
    finding: str
    evidence_refs: list[ComparisonEvidenceRef]
    limitations: list[str]


@with_config(ConfigDict(extra="forbid", strict=True))
class ComparisonResult(TypedDict):
    """최종 응답까지 보존할 검증된 비교 결과."""

    catalog_version: str
    targets: list[ComparisonTarget]
    criteria: list[ComparisonCriterion]
    coverage: ComparisonCoverage
    cells: list[ComparisonCell]
    limitations: list[str]


_COMPARISON_ADAPTER = TypeAdapter(ComparisonResult)


def comparison_coverage(
    targets: Sequence[ComparisonTarget], cells: Sequence[ComparisonCell]
) -> ComparisonCoverage:
    """유효 셀의 상태로 전체·부분·판단 불가 범위를 계산한다."""

    distinct_codes = {
        target["product_code"] for target in targets if target["resolution_status"] == "single"
    }
    if (
        len(distinct_codes) >= 2
        and all(target["resolution_status"] == "single" for target in targets)
        and cells
        and all(cell["status"] == "supported" for cell in cells)
    ):
        return "complete"
    if any(cell["status"] != "not_verified" and cell["evidence_refs"] for cell in cells):
        return "partial"
    return "none"


def validate_comparison_result(
    result: ComparisonResult, evidence: Sequence["EvidenceChunk"]
) -> None:
    """구조, 모든 대상×항목, 코드 귀속과 최종 근거 합집합을 검사한다."""

    _COMPARISON_ADAPTER.validate_python(result)
    _require_text(result["catalog_version"])
    targets = result["targets"]
    criteria = result["criteria"]
    if not 2 <= len(targets) <= 5 or not 1 <= len(criteria) <= MAX_PRODUCT_COMPARISON_CRITERIA:
        raise ValueError("비교 대상은 2~5개, 비교 항목은 1~3개여야 합니다.")
    if len(criteria) != len(set(criteria)):
        raise ValueError("비교 항목은 중복될 수 없습니다.")
    _validate_targets(targets)
    targets_by_id = {target["target_id"]: target for target in targets}
    if len(targets_by_id) != len(targets):
        raise ValueError("비교 대상 ID는 중복될 수 없습니다.")

    expected = {(target["target_id"], criterion) for target in targets for criterion in criteria}
    seen: set[tuple[str, str]] = set()
    used_ids: set[str] = set()
    for cell in result["cells"]:
        cell_key = (cell["target_id"], cell["criterion"])
        if cell_key not in expected or cell_key in seen:
            raise ValueError("비교 셀의 대상·항목이 추가되거나 중복됐습니다.")
        seen.add(cell_key)
        _validate_cell(cell, targets_by_id[cell["target_id"]])
        used_ids.update(ref["chunk_id"] for ref in cell["evidence_refs"])
    if seen != expected:
        raise ValueError("모든 비교 대상과 항목의 셀이 정확히 한 번 필요합니다.")
    evidence_ids = [chunk["chunk_id"] for chunk in evidence]
    if len(evidence_ids) != len(set(evidence_ids)) or set(evidence_ids) != used_ids:
        raise ValueError("최종 evidence는 비교 셀에서 사용한 근거의 중복 없는 합집합이어야 합니다.")
    coverage = comparison_coverage(targets, result["cells"])
    if result["coverage"] != coverage:
        raise ValueError("비교 coverage가 대상과 셀의 확인 범위에 일치하지 않습니다.")
    _validate_text_list(result["limitations"])
    if coverage != "complete" and not result["limitations"]:
        raise ValueError("부분 비교 또는 판단 불가 결과에는 구체적인 제한이 필요합니다.")


def _validate_targets(targets: Sequence[ComparisonTarget]) -> None:
    """확정 대상만 코드·공식명·운용사를 가지며 반복 코드는 같은 상품이어야 한다."""

    identities: dict[str, tuple[str, str]] = {}
    for target in targets:
        _require_text(target["target_id"])
        _validate_text_list(target["mention_parts"])
        if not target["mention_parts"]:
            raise ValueError("비교 대상의 원문 표현이 필요합니다.")
        resolved_fields = {"product_code", "official_name", "provider"}
        if target["resolution_status"] != "single":
            if resolved_fields.intersection(target):
                raise ValueError("미식별 대상에는 상품 코드·공식명·운용사를 넣을 수 없습니다.")
            continue
        if not resolved_fields.issubset(target):
            raise ValueError("확정 대상에는 상품 코드·공식명·운용사가 필요합니다.")
        for field in (target["product_code"], target["official_name"], target["provider"]):
            _require_text(field)
        code = target["product_code"]
        identity = (target["official_name"], target["provider"])
        if code in identities and identities[code] != identity:
            raise ValueError("동일 상품 코드의 공식명과 운용사가 일치해야 합니다.")
        identities[code] = identity


def _validate_cell(cell: ComparisonCell, target: ComparisonTarget) -> None:
    """셀 상태별 근거 개수와 상품 코드 귀속을 검사한다."""

    _require_text(cell["finding"])
    _validate_text_list(cell["limitations"])
    refs = cell["evidence_refs"]
    if cell["status"] == "not_verified":
        if refs or not cell["limitations"]:
            raise ValueError("미확인 셀은 근거가 비어 있고 확인하지 못한 이유가 있어야 합니다.")
        return
    if target["resolution_status"] != "single":
        raise ValueError("미식별 대상은 미확인 셀로만 제출할 수 있습니다.")
    if not refs or (cell["status"] == "conflicting" and len(refs) < 2):
        raise ValueError("확인된 셀에는 근거가, 충돌 셀에는 최소 2개 근거가 필요합니다.")
    if cell["status"] != "supported" and not cell["limitations"]:
        raise ValueError("충돌하거나 직접 비교할 수 없는 셀에는 제한이 필요합니다.")
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        _require_text(ref["chunk_id"])
        if ref["product_code"] != target["product_code"]:
            raise ValueError("비교 셀은 해당 대상 상품의 근거만 참조할 수 있습니다.")
        key = (ref["product_code"], ref["chunk_id"])
        if key in seen:
            raise ValueError("비교 셀의 근거 참조는 중복될 수 없습니다.")
        seen.add(key)


def _require_text(value: str) -> None:
    if not value.strip():
        raise ValueError("비교 결과의 텍스트는 비어 있을 수 없습니다.")


def _validate_text_list(values: list[str]) -> None:
    for value in values:
        _require_text(value)
