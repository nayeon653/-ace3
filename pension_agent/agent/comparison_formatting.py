"""검증된 상품 비교 구조를 새 생성 없이 사용자 답변으로 직렬화한다."""

from pension_agent.agent.contracts import ComparisonCriterion, DomainResult


def format_comparison_answer(result: DomainResult) -> str:
    """Tool이 작성한 본문에 실제 선택 문서와 반환된 조건·주의사항을 붙인다."""

    parts = [result["comparison_answer"]]
    if result["evidence"]:
        parts.append(
            "근거 문서:\n"
            + "\n".join(
                f"- {chunk['source_file_name']} — {chunk['title']}, {chunk['locator']}"
                for chunk in result["evidence"]
            )
        )
    for label, values in (
        ("확인이 필요한 조건", result["decision"]["missing_conditions"]),
        ("주의사항", result["warnings"]),
    ):
        if values:
            parts.append(label + ":\n" + "\n".join(f"- {value}" for value in dict.fromkeys(values)))
    return "\n\n".join(parts)


_CRITERION_LABELS: dict[ComparisonCriterion, str] = {
    "investment_strategy": "투자전략",
    "risk": "위험",
    "capital_protection": "원금보장·예금자보호",
    "fees": "보수·비용",
    "liquidity": "환매·유동성",
}
_STATUS_LABELS = {
    "supported": "근거 확인",
    "not_verified": "미확인",
    "conflicting": "근거 상충",
    "not_comparable": "직접 비교 어려움",
}


def format_comparison_result(result: DomainResult) -> str:
    """조건별 설명, 전체 비교 셀, 출처, 누락 조건과 경고를 보존한다."""

    comparison = result["comparison_result"]
    coverage = comparison["coverage"]
    parts = [
        {
            "complete": "요청하신 모든 상품과 비교 항목에서 근거를 확인했습니다.",
            "partial": "확인된 근거 범위에서만 비교합니다. 일부 대상 또는 항목은 확인이 필요합니다.",
            "none": "제공 자료에서 비교 판단에 필요한 근거를 확인하지 못해 상품 차이와 우열을 판단할 수 없습니다.",
        }[coverage]
    ]
    if coverage != "none" and result["decision"]["conclusion"].strip():
        parts.append(result["decision"]["conclusion"])

    source_numbers = {
        chunk["chunk_id"]: index for index, chunk in enumerate(result["evidence"], start=1)
    }
    cells = {(cell["target_id"], cell["criterion"]): cell for cell in comparison["cells"]}
    table = [
        "| 상품 | 비교 항목 | 확인 내용 | 상태 | 근거 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for target in comparison["targets"]:
        name = target.get("official_name") or " · ".join(target["mention_parts"])
        for criterion in comparison["criteria"]:
            cell = cells[(target["target_id"], criterion)]
            finding = (
                cell["finding"] if cell["status"] != "not_verified" else "제공 자료에서 미확인"
            )
            if cell["limitations"]:
                finding += " / 제한: " + "; ".join(cell["limitations"])
            references = (
                ", ".join(f"[{source_numbers[ref['chunk_id']]}]" for ref in cell["evidence_refs"])
                or "없음"
            )
            row = [
                name,
                _CRITERION_LABELS[criterion],
                finding,
                _STATUS_LABELS[cell["status"]],
                references,
            ]
            table.append("| " + " | ".join(_table_text(value) for value in row) + " |")
    parts.append("\n".join(table))
    if result["evidence"]:
        parts.append(
            "근거 문서:\n"
            + "\n".join(
                f"[{source_numbers[chunk['chunk_id']]}] {chunk['source_file_name']}"
                f" — {chunk['title']}, {chunk['locator']}"
                for chunk in result["evidence"]
            )
        )
    for label, values in (
        ("비교 제한", comparison["limitations"]),
        ("확인이 필요한 조건", result["decision"]["missing_conditions"]),
        ("주의사항", result["warnings"]),
    ):
        if values:
            parts.append(label + ":\n" + "\n".join(f"- {value}" for value in dict.fromkeys(values)))
    return "\n\n".join(parts)


def _table_text(value: str) -> str:
    """원문의 표 구분자와 개행이 셀 구조를 바꾸지 않도록 정리한다."""

    return value.replace("|", "\\|").replace("\r", "").replace("\n", "<br>")
