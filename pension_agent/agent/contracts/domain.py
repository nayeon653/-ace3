"""Main과 도메인 Agent가 공유하는 실행 계약."""

from typing import Annotated, Any, Literal, NotRequired

from pydantic import Field
from typing_extensions import TypedDict

from pension_agent.agent.contracts.comparison import ComparisonResult, validate_comparison_result

DomainName = Literal["policy", "tax_payout", "product"]
ExecutionStatus = Literal["completed", "failed", "timeout"]
DecisionStatus = Literal[
    "determined",
    "conditional",
    "undetermined",
    "not_applicable",
]
CatalogReturnMode = Literal["count", "items", "count_and_items"]
NumericStatementSourceType = Literal["statutory_fact", "calculation"]


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


class CalculationInputSource(TypedDict):
    """계산 입력이 실제로 확인된 질문 또는 검색 청크 출처."""

    origin: Literal["question", "evidence"]
    text: str
    chunk_id: str | None


class CalculationResult(TypedDict):
    """Python 계산 함수가 생성한 확정 계산 기록."""

    calculator_id: str
    inputs: dict[str, Any]
    input_sources: dict[str, CalculationInputSource]
    outputs: dict[str, Any]
    units: dict[str, str]
    warnings: list[str]


class DomainDecision(TypedDict):
    """도메인의 비즈니스 판단과 누락 조건."""

    status: DecisionStatus
    conclusion: str
    missing_conditions: list[str]


class VerifiedNumericStatement(TypedDict):
    """Main이 다시 쓸 수 없는, Python이 registry·계산 결과에서 그대로 만든 숫자 문장.

    Main Supervisor는 이 TypedDict의 ``text``를 직접 보지 않는다. Main에는
    placeholder token만 노출되고, 최종 답변 조립 단계에서 Python이 이 ``text``로
    치환한다.
    """

    source_type: NumericStatementSourceType
    source_id: str
    text: str


class VerifiedNumericPlaceholder(TypedDict):
    """Main Supervisor에 노출하는 placeholder와 그 주제 — 실제 문장(text)은 없다."""

    placeholder: str
    source_id: str


class CatalogItem(TypedDict):
    """결정론적 상품 카탈로그 조회가 반환한 최소 상품 항목."""

    product_code: str
    official_name: str
    provider: str


class CatalogResult(TypedDict):
    """Main Agent가 그대로 사용할 검증된 상품 카탈로그 조회 결과."""

    route: Literal["browse_catalog"]
    provider: str | None
    return_mode: CatalogReturnMode
    total_count: int
    items: list[CatalogItem]
    catalog_version: str


class DomainResult(TypedDict):
    """State와 API 조립에 사용하는 전체 도메인 실행 결과."""

    domain: DomainName
    execution_status: ExecutionStatus
    decision: NotRequired[DomainDecision]
    evidence: list[EvidenceChunk]
    calculations: list[CalculationResult]
    warnings: list[str]
    catalog_result: NotRequired[CatalogResult]
    comparison_result: NotRequired[ComparisonResult]
    comparison_answer: NotRequired[str]
    error: NotRequired[str]
    verified_numeric_statements: NotRequired[list[VerifiedNumericStatement]]


class DomainToolResult(TypedDict):
    """Main LLM에 전달하는 축약 도메인 실행 결과."""

    domain: DomainName
    execution_status: ExecutionStatus
    decision: NotRequired[DomainDecision]
    calculations: list[CalculationResult]
    warnings: list[str]
    catalog_result: NotRequired[CatalogResult]
    comparison_result: NotRequired[ComparisonResult]
    comparison_answer_ready: NotRequired[bool]
    error: NotRequired[str]
    verified_numeric_placeholders: NotRequired[list[VerifiedNumericPlaceholder]]


def validate_domain_result(result: DomainResult) -> None:
    """실행 상태와 판단 상태의 필드 조합을 검증한다."""

    execution_status = result["execution_status"]
    has_decision = "decision" in result
    has_error = "error" in result
    has_catalog_result = "catalog_result" in result
    has_comparison_result = "comparison_result" in result
    has_comparison_answer = "comparison_answer" in result

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
        if has_catalog_result:
            raise ValueError("실패한 결과에는 카탈로그 조회 결과를 포함할 수 없습니다.")
        if result.get("verified_numeric_statements"):
            raise ValueError("실패한 결과에는 검증된 숫자 문장을 포함할 수 없습니다.")
        if has_comparison_result or has_comparison_answer:
            raise ValueError("실패한 결과에는 비교 결과를 포함할 수 없습니다.")

    _validate_verified_numeric_statements(result)

    if not has_decision:
        return

    _validate_calculation_sources(result)

    if has_comparison_answer:
        if (
            result["domain"] != "product"
            or has_catalog_result
            or has_comparison_result
            or result["calculations"]
        ):
            raise ValueError("비교 답안은 계산·카탈로그·비교 셀이 없는 product 결과여야 합니다.")
        return

    decision = result["decision"]
    missing_conditions = decision["missing_conditions"]
    if decision["status"] in {"determined", "not_applicable"}:
        if missing_conditions:
            raise ValueError("확정되거나 적용되지 않는 판단에는 누락 조건이 없어야 합니다.")
    elif not missing_conditions:
        raise ValueError("조건부이거나 미확정인 판단에는 누락 조건이 필요합니다.")

    if has_catalog_result:
        _validate_catalog_result(result)
    if has_comparison_result:
        if result["domain"] != "product" or has_catalog_result or result["calculations"]:
            raise ValueError("비교 결과는 계산·카탈로그 조회가 없는 product 결과에만 허용됩니다.")
        comparison = result["comparison_result"]
        validate_comparison_result(comparison, result["evidence"])
        allowed_statuses = {
            "complete": {"determined", "conditional"},
            "partial": {"conditional"},
            "none": {"undetermined"},
        }
        if decision["status"] not in allowed_statuses[comparison["coverage"]]:
            raise ValueError("비교 범위와 도메인 판단 상태가 일치해야 합니다.")
        if any(not condition.strip() for condition in missing_conditions):
            raise ValueError("비교 누락 조건은 구체적인 내용이 필요합니다.")


def _validate_verified_numeric_statements(result: DomainResult) -> None:
    """검증된 숫자 문장의 출처·본문이 비어 있지 않은지 확인한다."""

    for statement in result.get("verified_numeric_statements", []):
        if not statement["source_id"].strip():
            raise ValueError("검증된 숫자 문장의 source_id가 비어 있습니다.")
        if not statement["text"].strip():
            raise ValueError("검증된 숫자 문장의 text가 비어 있습니다.")


def _validate_calculation_sources(result: DomainResult) -> None:
    """계산 입력 출처와 최종 근거 청크의 연결을 검증한다."""

    evidence_ids = {chunk["chunk_id"] for chunk in result["evidence"]}
    for calculation in result["calculations"]:
        if calculation["inputs"].keys() != calculation["input_sources"].keys():
            raise ValueError("계산 입력과 출처 필드가 일치해야 합니다.")
        for source in calculation["input_sources"].values():
            if not source["text"].strip():
                raise ValueError("계산 입력 출처 원문이 필요합니다.")
            if source["origin"] == "question":
                if source["chunk_id"] is not None:
                    raise ValueError("질문 출처에는 근거 청크 ID를 포함할 수 없습니다.")
            elif source["chunk_id"] not in evidence_ids:
                raise ValueError("계산 입력의 근거 청크가 최종 evidence에 필요합니다.")


def _validate_catalog_result(result: DomainResult) -> None:
    """카탈로그 결과의 도메인·개수·목록 일관성을 검증한다."""

    if result["domain"] != "product":
        raise ValueError("카탈로그 조회 결과는 product 도메인에만 포함할 수 있습니다.")
    if result["decision"]["status"] != "determined":
        raise ValueError("카탈로그 조회 결과는 확정 판단이어야 합니다.")
    if result["calculations"]:
        raise ValueError("카탈로그 조회 결과에는 계산 기록을 포함할 수 없습니다.")
    if not result["evidence"]:
        raise ValueError("카탈로그 조회 결과에는 검증된 조회 근거가 필요합니다.")

    catalog_result = result["catalog_result"]
    if catalog_result["route"] != "browse_catalog":
        raise ValueError("카탈로그 조회 route가 올바르지 않습니다.")
    if catalog_result["total_count"] < 0:
        raise ValueError("카탈로그 상품 개수는 음수일 수 없습니다.")
    if not catalog_result["catalog_version"].strip():
        raise ValueError("카탈로그 버전이 필요합니다.")

    items = catalog_result["items"]
    if catalog_result["return_mode"] == "count":
        if items:
            raise ValueError("count 결과에는 상품 목록을 포함할 수 없습니다.")
    elif len(items) != catalog_result["total_count"]:
        raise ValueError("카탈로그 상품 개수와 목록 길이가 일치하지 않습니다.")

    codes = [item["product_code"] for item in items]
    if len(codes) != len(set(codes)):
        raise ValueError("카탈로그 상품 코드는 중복될 수 없습니다.")
    provider = catalog_result["provider"]
    if provider is not None and any(item["provider"] != provider for item in items):
        raise ValueError("카탈로그 상품의 운용사가 조회 조건과 일치하지 않습니다.")
