"""Product의 상품별 검색 근거와 비교 셀 제출을 연결한다."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import TypeAdapter

from pension_agent.agent.contracts import (
    ComparisonCell,
    ComparisonCriterion,
    ComparisonResult,
    ComparisonTarget,
    DecisionStatus,
    DomainResult,
    EvidenceChunk,
    validate_domain_result,
)
from pension_agent.agent.contracts.comparison import comparison_coverage
from pension_agent.agent.product.comparison import ComparisonEvidenceResult

_CELLS = TypeAdapter(list[ComparisonCell])
_NO_COMPARISON = "제공 문서 근거로 상품 비교를 완료하지 못했습니다."


def unresolved_comparison_result(
    *,
    targets: list[ComparisonTarget],
    criteria: list[ComparisonCriterion],
    catalog_version: str,
    limitation: str,
    limitations: list[str] | None = None,
) -> DomainResult:
    """비교를 실행하거나 제출하지 못했어도 원래 대상과 항목을 보존한다."""

    combined_limitations = list(dict.fromkeys([limitation, *(limitations or [])]))
    cells: list[ComparisonCell] = [
        {
            "target_id": target["target_id"],
            "criterion": criterion,
            "status": "not_verified",
            "finding": "제공 문서에서 비교 근거를 확인하지 못했습니다.",
            "evidence_refs": [],
            "limitations": [limitation],
        }
        for target in targets
        for criterion in criteria
    ]
    result: DomainResult = {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "undetermined",
            "conclusion": _NO_COMPARISON,
            "missing_conditions": combined_limitations,
        },
        "evidence": [],
        "calculations": [],
        "warnings": combined_limitations,
        "comparison_result": {
            "catalog_version": catalog_version,
            "targets": targets,
            "criteria": criteria,
            "coverage": "none",
            "cells": cells,
            "limitations": combined_limitations,
        },
    }
    validate_domain_result(result)
    return result


def build_comparison_domain_result(
    *,
    state: Mapping[str, Any],
    status: DecisionStatus,
    conclusion: str,
    missing_conditions: list[str],
    warnings: list[str],
    cells: list[ComparisonCell] | None,
    evidence_chunk_ids: list[str],
) -> DomainResult:
    """상품별 완료 검색에 귀속되는 셀과 실제 인용 근거만 채택한다."""

    comparison: ComparisonEvidenceResult | None = state.get("comparison_evidence")
    if comparison is None or comparison.execution_status != "completed":
        raise ValueError("완료된 상품 비교 검색이 필요합니다.")
    if cells is None:
        raise ValueError("비교 제출에는 모든 대상과 항목의 comparison_cells가 필요합니다.")
    parsed_cells = _CELLS.validate_python(cells)
    targets: list[ComparisonTarget] = state["comparison_targets"]
    criteria: list[ComparisonCriterion] = state["comparison_criteria"]
    chunks = {
        product.product_code: {chunk.chunk_id: chunk for chunk in product.evidence}
        for product in comparison.products
    }
    source_files = {
        product.product_code: product.source_file_name for product in comparison.products
    }
    selected: dict[str, EvidenceChunk] = {}
    for cell in parsed_cells:
        for ref in cell["evidence_refs"]:
            code, chunk_id = ref["product_code"], ref["chunk_id"]
            chunk = chunks.get(code, {}).get(chunk_id)
            if chunk is None or chunk.source_file_name != source_files.get(code):
                raise ValueError("비교 근거는 해당 상품의 완료된 문서 검색에 있어야 합니다.")
            evidence: EvidenceChunk = {
                "chunk_id": chunk.chunk_id,
                "source_file_name": chunk.source_file_name,
                "title": chunk.title,
                "locator": chunk.locator,
                "content": chunk.content,
            }
            if chunk_id in selected and selected[chunk_id] != evidence:
                raise ValueError("같은 청크 ID의 원문 근거가 일치하지 않습니다.")
            selected[chunk_id] = evidence
    if evidence_chunk_ids and set(evidence_chunk_ids) != set(selected):
        raise ValueError("별도 근거 ID는 비교 셀의 실제 인용 근거와 일치해야 합니다.")

    coverage = comparison_coverage(targets, parsed_cells)
    limitations = list(
        dict.fromkeys(
            [
                *comparison.limitations,
                *(value for cell in parsed_cells for value in cell["limitations"]),
                *(
                    f"{' '.join(target['mention_parts'])}: 정확한 상품 식별 필요"
                    for target in targets
                    if target["resolution_status"] != "single"
                ),
            ]
        )
    )
    missing = list(dict.fromkeys(value.strip() for value in missing_conditions if value.strip()))
    if coverage != "complete":
        missing.extend(limitations)
        missing.extend(
            f"{cell['target_id']}의 {cell['criterion']} 확인 필요"
            for cell in parsed_cells
            if cell["status"] != "supported" and not cell["limitations"]
        )
        if not missing:
            missing.append("모든 비교 대상과 항목의 문서 근거 확인 필요")
        status = "conditional" if coverage == "partial" else "undetermined"
    elif missing and status == "determined":
        status = "conditional"
    if status == "not_applicable":
        raise ValueError("상품 비교 결과를 적용되지 않는 판단으로 제출할 수 없습니다.")
    comparison_result: ComparisonResult = {
        "catalog_version": state["comparison_catalog_version"],
        "targets": targets,
        "criteria": criteria,
        "coverage": coverage,
        "cells": parsed_cells,
        "limitations": limitations,
    }
    result: DomainResult = {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": status,
            "conclusion": _NO_COMPARISON if coverage == "none" else conclusion.strip(),
            "missing_conditions": list(dict.fromkeys(missing)),
        },
        "evidence": list(selected.values()),
        "calculations": [],
        "warnings": list(dict.fromkeys([*warnings, *limitations])),
        "comparison_result": comparison_result,
    }
    validate_domain_result(result)
    return result
