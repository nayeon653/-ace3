"""비교를 완료하지 못한 요청을 추가 모델 호출 없이 안내한다."""

from __future__ import annotations

from pension_agent.agent.contracts import ComparisonTarget, DomainResult, validate_domain_result


def unresolved_comparison_result(
    *,
    targets: list[ComparisonTarget],
    limitation: str,
    limitations: list[str] | None = None,
) -> DomainResult:
    """요청한 상품 표현과 비교하지 못한 이유를 짧은 답안으로 보존한다."""

    descriptions = []
    for target in targets:
        name = target.get("official_name") or " ".join(target["mention_parts"])
        if target["resolution_status"] == "ambiguous":
            name += " (후보가 여러 개여서 미식별)"
        elif target["resolution_status"] == "not_found":
            name += " (카탈로그에서 찾지 못함)"
        descriptions.append(name)
    parts = ["상품 비교를 완료하지 못했습니다."]
    if descriptions:
        parts.append("비교 대상: " + ", ".join(dict.fromkeys(descriptions)))
    parts.extend(dict.fromkeys([limitation, *(limitations or [])]))
    answer = "\n".join(parts)
    result: DomainResult = {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "undetermined",
            "conclusion": answer,
            "missing_conditions": [],
        },
        "comparison_answer": answer,
        "evidence": [],
        "calculations": [],
        "warnings": [],
    }
    validate_domain_result(result)
    return result
