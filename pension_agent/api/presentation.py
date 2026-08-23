"""검증된 Agent 결과를 외부 공개 응답으로 변환한다."""

from pension_agent.agent.contracts import DecisionStatus, DomainResult, ExecutionStatus
from pension_agent.agent.orchestration import AnswerServiceResult
from pension_agent.api.schemas import AnswerResponse, EvidenceChunkResponse

_EXECUTION_LABELS: dict[ExecutionStatus, str] = {
    "completed": "완료",
    "failed": "실패",
    "timeout": "시간 초과",
}
_DECISION_LABELS: dict[DecisionStatus, str] = {
    "determined": "확정",
    "conditional": "조건부",
    "undetermined": "미확정",
    "not_applicable": "해당 없음",
}


def build_answer_response(result: AnswerServiceResult) -> AnswerResponse:
    """Answer Service 결과를 정확한 5개 필드로 조립한다."""

    state = result.state
    return AnswerResponse(
        question_id=state["question_id"],
        question=state["question"],
        retrieved_context=_serialize_retrieved_context(state["domain_results"]),
        think_trace=build_think_trace(state["domain_results"]),
        answer=result.answer.answer,
    )


def build_think_trace(domain_results: list[DomainResult]) -> str:
    """원시 로그 없이 도메인 실행과 판단 근거를 안전하게 요약한다."""

    if not domain_results:
        return (
            "도메인 호출: 없음. 판단 요약: 도메인 판단 없이 최종 답변을 생성함. "
            "확인이 필요한 조건: 없음."
        )

    calls: list[str] = []
    decisions: list[str] = []
    missing_conditions: list[str] = []

    for result in domain_results:
        domain = result["domain"]
        execution_status = result["execution_status"]
        calls.append(f"{domain}({_EXECUTION_LABELS[execution_status]})")

        if execution_status != "completed":
            decisions.append(f"{domain}=실행 {_EXECUTION_LABELS[execution_status]}")
            continue

        decision = result["decision"]
        conclusion = _one_line(decision["conclusion"]) or "결론이 기록되지 않음"
        if "catalog_result" in result:
            catalog_result = result["catalog_result"]
            provider = catalog_result["provider"] or "전체"
            conclusion = (
                f"검증된 카탈로그 조회(route=browse_catalog, provider={provider}, "
                f"return_mode={catalog_result['return_mode']}, "
                f"total_count={catalog_result['total_count']}, "
                f"catalog_version={catalog_result['catalog_version']})"
            )
        decisions.append(f"{domain}={_DECISION_LABELS[decision['status']]}: {conclusion}")
        missing_conditions.extend(
            f"{domain}={condition}"
            for raw_condition in decision["missing_conditions"]
            if (condition := _one_line(raw_condition))
        )

    conditions_summary = "; ".join(missing_conditions) or "없음"
    return (
        f"도메인 호출: {', '.join(calls)}. "
        f"판단 요약: {'; '.join(decisions)}. "
        f"확인이 필요한 조건: {conditions_summary}."
    )


def _serialize_retrieved_context(
    domain_results: list[DomainResult],
) -> list[EvidenceChunkResponse]:
    """답변 조립 대상인 완료 판단의 근거만 직렬화한다."""

    return [
        EvidenceChunkResponse.model_validate(evidence)
        for result in domain_results
        if result["execution_status"] == "completed"
        and result["decision"]["status"] != "not_applicable"
        for evidence in result["evidence"]
    ]


def _one_line(value: str) -> str:
    """응답 조립용 텍스트에서 개행과 연속 공백을 제거한다."""

    return " ".join(value.split())
