"""완성된 상품 비교 본문과 조건·경고를 사용자 답변으로 전달한다."""

from pension_agent.agent.contracts import DomainResult


def format_comparison_answer(result: DomainResult) -> str:
    """Tool이 작성한 본문과 반환된 조건·주의사항을 보존한다."""

    parts = [result["comparison_answer"]]
    for label, values in (
        ("확인이 필요한 조건", result["decision"]["missing_conditions"]),
        ("주의사항", result["warnings"]),
    ):
        if values:
            parts.append(label + ":\n" + "\n".join(f"- {value}" for value in dict.fromkeys(values)))
    return "\n\n".join(parts)
