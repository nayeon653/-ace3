"""상품 식별을 마치지 못한 비교 요청의 결정론적 결과를 만든다."""

from __future__ import annotations

from pension_agent.agent.contracts import (
    ComparisonCell,
    ComparisonCriterion,
    ComparisonTarget,
    DomainResult,
    validate_domain_result,
)

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
