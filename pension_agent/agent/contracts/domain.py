"""Main과 도메인 Agent가 공유하는 실행 계약."""

from typing import Annotated, Any, Literal, NotRequired

from pydantic import Field
from typing_extensions import TypedDict

DomainName = Literal["policy", "tax_payout", "product"]
ExecutionStatus = Literal["completed", "failed", "timeout"]
DecisionStatus = Literal[
    "determined",
    "conditional",
    "undetermined",
    "not_applicable",
]


class DomainRequest(TypedDict):
    """Main이 도메인 Agent에 요청하는 하나의 판단."""

    question: Annotated[
        str,
        Field(description="조건을 추가하거나 요약하지 않은 사용자의 질문 원문"),
    ]
    objective: Annotated[
        str,
        Field(description="이 Tool이 수행할 하나의 구체적인 비즈니스 판단"),
    ]


class EvidenceChunk(TypedDict):
    """도메인 결론에 실제 사용한 문서 청크."""

    chunk_id: str
    source_file_name: str
    title: str
    locator: str
    content: str


class CalculationResult(TypedDict):
    """Python 계산 함수가 생성한 확정 계산 기록."""

    calculator_name: str
    inputs: dict[str, Any]
    result: Any
    unit: NotRequired[str]


class DomainDecision(TypedDict):
    """도메인의 비즈니스 판단과 누락 조건."""

    status: DecisionStatus
    conclusion: str
    missing_conditions: list[str]


class DomainResult(TypedDict):
    """State와 API 조립에 사용하는 전체 도메인 실행 결과."""

    domain: DomainName
    execution_status: ExecutionStatus
    decision: NotRequired[DomainDecision]
    evidence: list[EvidenceChunk]
    calculations: list[CalculationResult]
    warnings: list[str]
    error: NotRequired[str]


class DomainToolResult(TypedDict):
    """Main LLM에 전달하는 축약 도메인 실행 결과."""

    domain: DomainName
    execution_status: ExecutionStatus
    decision: NotRequired[DomainDecision]
    warnings: list[str]
    error: NotRequired[str]


def validate_domain_result(result: DomainResult) -> None:
    """실행 상태와 판단 상태의 필드 조합을 검증한다."""

    execution_status = result["execution_status"]
    has_decision = "decision" in result
    has_error = "error" in result

    if execution_status == "completed":
        if not has_decision:
            raise ValueError("completed 결과에는 decision이 필요합니다.")
        if has_error:
            raise ValueError("completed 결과에는 error를 포함할 수 없습니다.")
    else:
        if has_decision:
            raise ValueError("실패한 결과에는 decision을 포함할 수 없습니다.")
        if not has_error or not result["error"].strip():
            raise ValueError("실패한 결과에는 정제된 error가 필요합니다.")
        if result["evidence"] or result["calculations"]:
            raise ValueError("실패한 결과의 근거와 계산 기록은 비어 있어야 합니다.")

    if not has_decision:
        return

    decision = result["decision"]
    missing_conditions = decision["missing_conditions"]
    if decision["status"] in {"determined", "not_applicable"}:
        if missing_conditions:
            raise ValueError("확정되거나 적용되지 않는 판단에는 누락 조건이 없어야 합니다.")
    elif not missing_conditions:
        raise ValueError("조건부이거나 미확정인 판단에는 누락 조건이 필요합니다.")
