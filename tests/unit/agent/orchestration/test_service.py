"""HTTP와 분리된 Answer Service 실행 경계를 검증한다."""

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from pension_agent.agent.contracts import DomainResult
from pension_agent.agent.execution import ExecutionContext
from pension_agent.agent.orchestration import (
    AnswerService,
    AnswerServiceClosedError,
    AnswerServiceOverloadedError,
    AnswerServiceTimeoutError,
    FinalAnswerMissingError,
    InvalidSupervisorResultError,
    SupervisorExecutionError,
)
from pension_agent.agent.orchestration.numeric_firewall import placeholder_token
from pension_agent.config import AgentRuntimeConfig

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeSupervisor:
    """고정된 최종 상태 또는 오류를 반환하는 테스트 Supervisor."""

    def __init__(
        self,
        *,
        result: Mapping[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.inputs: list[dict[str, Any]] = []
        self.contexts: list[ExecutionContext] = []

    async def ainvoke(
        self,
        input: dict[str, Any],
        /,
        *,
        context: ExecutionContext,
    ) -> Mapping[str, Any]:
        self.inputs.append(input)
        self.contexts.append(context)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _completed_result() -> DomainResult:
    return {
        "domain": "policy",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": "이전할 수 있습니다.",
            "missing_conditions": [],
        },
        "evidence": [],
        "calculations": [],
        "warnings": [],
    }


def _failed_result() -> DomainResult:
    return {
        "domain": "product",
        "execution_status": "failed",
        "evidence": [],
        "calculations": [],
        "warnings": [],
        "error": "도메인 분석을 완료하지 못했습니다.",
    }


def _catalog_result() -> DomainResult:
    return {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": "미래에셋 상품 카탈로그에서 2개를 조회했습니다.",
            "missing_conditions": [],
        },
        "evidence": [
            {
                "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_file_name": "product_catalog.json",
                "title": "검증된 상품 카탈로그 조회 결과",
                "locator": "provider=미래에셋;catalog_version=v1",
                "content": "결정론적 카탈로그 결과",
            }
        ],
        "calculations": [],
        "warnings": [],
        "catalog_result": {
            "route": "browse_catalog",
            "provider": "미래에셋",
            "return_mode": "count_and_items",
            "total_count": 2,
            "items": [
                {
                    "product_code": "KR510902511M",
                    "official_name": "미래에셋장기성장포커스",
                    "provider": "미래에셋",
                },
                {
                    "product_code": "KR510902773M",
                    "official_name": "미래에셋고배당포커스",
                    "provider": "미래에셋",
                },
            ],
            "catalog_version": "v1",
        },
    }


def _calculation_result() -> DomainResult:
    return {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": "검증된 Python 계산 결과입니다.",
            "missing_conditions": [],
        },
        "evidence": [
            {
                "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_file_name": "rules.pdf",
                "title": "연금수령한도",
                "locator": "1쪽",
                "content": "연금수령한도 계산 규칙",
            }
        ],
        "calculations": [
            {
                "calculator_id": "pension_withdrawal_limit",
                "inputs": {
                    "account_valuation_krw": "10000000",
                    "pension_year": 1,
                },
                "input_sources": {
                    "account_valuation_krw": {
                        "origin": "question",
                        "text": "평가액 1천만원",
                        "chunk_id": None,
                    },
                    "pension_year": {
                        "origin": "question",
                        "text": "1년차",
                        "chunk_id": None,
                    },
                },
                "outputs": {"withdrawal_limit": "1200000.0"},
                "units": {"withdrawal_limit": "KRW"},
                "warnings": [
                    "출처에는 최종 지급 단위의 반올림·절사 규칙이 명시되지 않았습니다.",
                ],
            }
        ],
        "warnings": ["검색 범위가 제한적입니다."],
    }


def _retirement_benefit_result(*, conditional: bool = False) -> DomainResult:
    return {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": "conditional" if conditional else "determined",
            "conclusion": "DB 퇴직급여를 계산했으며 퇴직소득세는 별도 계산이 필요합니다.",
            "missing_conditions": (
                ["퇴직소득세 산출에 필요한 별도 계산 계약과 입력 확인 필요"] if conditional else []
            ),
        },
        "evidence": [
            {
                "chunk_id": "550e8400-e29b-41d4-a716-446655440002",
                "source_file_name": "retirement.pdf",
                "title": "DB 퇴직급여",
                "locator": "3쪽",
                "content": "DB 퇴직급여 계산 근거",
            }
        ],
        "calculations": [
            {
                "calculator_id": "db_retirement_benefit",
                "inputs": {
                    "wages_for_average_period_krw": "9000000",
                    "included_days_for_average_wage": 90,
                    "verified_service_years": "10",
                },
                "input_sources": {
                    "wages_for_average_period_krw": {
                        "origin": "question",
                        "text": "최근 3개월 임금 900만원",
                        "chunk_id": None,
                    },
                    "included_days_for_average_wage": {
                        "origin": "question",
                        "text": "포함일수 90일",
                        "chunk_id": None,
                    },
                    "verified_service_years": {
                        "origin": "question",
                        "text": "검증 근속 10년",
                        "chunk_id": None,
                    },
                },
                "outputs": {
                    "average_daily_wage": "100000",
                    "average_wage_30_days": "3000000",
                    "verified_service_years": "10",
                    "retirement_benefit": "30000000",
                },
                "units": {
                    "average_daily_wage": "KRW/day",
                    "average_wage_30_days": "KRW",
                    "verified_service_years": "years",
                    "retirement_benefit": "KRW",
                },
                "warnings": ["퇴직소득세는 이 계산에 포함되지 않습니다."],
            }
        ],
        "warnings": ["최초 퇴직소득세 전체 계산기는 현재 제공되지 않습니다."],
    }


def _state(*, messages: list[Any], domain_results: list[DomainResult]) -> dict[str, Any]:
    return {
        "messages": messages,
        "question_id": "Q-001",
        "question": "연금계좌를 이전할 수 있나요?",
        "domain_results": domain_results,
    }


async def test_answer_service_returns_answer_and_final_state() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="연금계좌를 이전할 수 있습니다.")],
            domain_results=[_completed_result()],
        )
    )
    service = AnswerService(supervisor)

    result = await service.run(
        question_id="Q-001",
        question="연금계좌를 이전할 수 있나요?",
    )

    assert result.answer.answer == "연금계좌를 이전할 수 있습니다."
    assert result.state["question_id"] == "Q-001"
    assert result.state["question"] == "연금계좌를 이전할 수 있나요?"
    assert result.state["domain_results"] == [_completed_result()]
    assert len(supervisor.inputs) == 1
    assert isinstance(supervisor.inputs[0]["messages"][0], HumanMessage)
    assert supervisor.inputs[0]["messages"][0].text == "연금계좌를 이전할 수 있나요?"
    assert supervisor.inputs[0]["domain_results"] == []
    assert len(supervisor.contexts) == 1


async def test_answer_service_preserves_tool_failure_as_valid_execution_state() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="상품 분석을 완료하지 못해 판단할 수 없습니다.")],
            domain_results=[_failed_result()],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001",
        question="연금계좌를 이전할 수 있나요?",
    )

    assert result.answer.answer == "상품 분석을 완료하지 못해 판단할 수 없습니다."
    assert result.state["domain_results"][0]["execution_status"] == "failed"
    assert result.state["domain_results"][0]["error"] == "도메인 분석을 완료하지 못했습니다."


async def test_answer_service_replaces_catalog_only_answer_with_verified_values() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="미래에셋 상품은 99개입니다.")],
            domain_results=[_catalog_result()],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001",
        question="연금계좌를 이전할 수 있나요?",
    )

    assert result.answer.answer == (
        "미래에셋 상품은 총 2개입니다.\n\n"
        "미래에셋 상품 목록:\n"
        "- 미래에셋장기성장포커스 (미래에셋, KR510902511M)\n"
        "- 미래에셋고배당포커스 (미래에셋, KR510902773M)"
    )
    assert "99" not in result.answer.answer


async def test_answer_service_replaces_calculation_only_answer_with_verified_values() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="연금수령한도는 999원입니다.")],
            domain_results=[_calculation_result()],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001",
        question="연금계좌를 이전할 수 있나요?",
    )

    assert "연금수령한도: 1200000.0 KRW" in result.answer.answer
    assert "반올림·절사 규칙" in result.answer.answer
    assert "999" not in result.answer.answer


async def test_answer_service_rebuilds_mixed_answer_from_verified_domain_results() -> None:
    conditional_result = _completed_result()
    conditional_result["decision"] = {
        "status": "conditional",
        "conclusion": "조건에 따라 이전할 수 있습니다.",
        "missing_conditions": ["가입 유형"],
    }
    conditional_result["warnings"] = ["이전 전 수수료를 확인해야 합니다."]
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="이전할 수 없고 계산값은 999원입니다.")],
            domain_results=[conditional_result, _calculation_result(), _failed_result()],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001",
        question="연금계좌를 이전할 수 있나요?",
    )

    assert "조건에 따라 이전할 수 있습니다." in result.answer.answer
    assert "가입 유형" in result.answer.answer
    assert "이전 전 수수료" in result.answer.answer
    assert "검색 범위가 제한적" in result.answer.answer
    assert "상품·운용 분석을 완료하지 못했습니다" in result.answer.answer
    assert "연금수령한도: 1200000.0 KRW" in result.answer.answer
    assert "999" not in result.answer.answer


async def test_answer_service_preserves_both_medical_care_domain_results() -> None:
    policy_result = _completed_result()
    policy_result["decision"] = {
        "status": "conditional",
        "conclusion": "DC 의료비 중도인출 가능 여부는 요양기간에 따라 달라집니다.",
        "missing_conditions": ["제도상 요양기간 확인"],
    }
    policy_result["evidence"] = [
        {
            "chunk_id": "550e8400-e29b-41d4-a716-446655440001",
            "source_file_name": "policy.pdf",
            "title": "의료비 중도인출 사유",
            "locator": "2쪽",
            "content": "제도상 의료비 중도인출 조건",
        }
    ]
    policy_result["warnings"] = ["계좌 유형을 확인해야 합니다."]
    tax_result = _calculation_result()
    tax_result["decision"] = {
        "status": "determined",
        "conclusion": "의료 목적 인출의 세액과 세후액을 계산했습니다.",
        "missing_conditions": [],
    }
    question = "DC 의료비 중도인출이 가능한지와 세금까지 알려 주세요."
    supervisor_state = _state(
        messages=[AIMessage(content="의료비 인출 결과입니다.")],
        domain_results=[policy_result, tax_result],
    )
    supervisor_state["question"] = question
    supervisor = FakeSupervisor(result=supervisor_state)

    result = await AnswerService(supervisor).run(
        question_id="Q-001",
        question=question,
    )

    assert result.state["domain_results"] == [policy_result, tax_result]
    assert result.state["domain_results"][0]["evidence"] == policy_result["evidence"]
    assert result.state["domain_results"][1]["evidence"] == tax_result["evidence"]
    assert (
        result.state["domain_results"][1]["calculations"][0]["input_sources"]
        == tax_result["calculations"][0]["input_sources"]
    )
    assert "제도상 요양기간 확인" in result.answer.answer
    assert "계좌 유형을 확인해야 합니다." in result.answer.answer
    assert "연금수령한도: 1200000.0 KRW" in result.answer.answer


@pytest.mark.parametrize(
    ("policy_conditional", "tax_conditional"),
    [(True, False), (False, True)],
)
async def test_answer_service_preserves_retirement_composite_domain_results(
    policy_conditional: bool, tax_conditional: bool
) -> None:
    policy_result = _completed_result()
    policy_result["decision"] = {
        "status": "conditional" if policy_conditional else "determined",
        "conclusion": "근속 인정 여부를 판단했습니다.",
        "missing_conditions": ["계속근로·근속 인정 여부 확인 필요"] if policy_conditional else [],
    }
    policy_result["warnings"] = ["제도 판단 주의사항"]
    tax_result = _retirement_benefit_result(conditional=tax_conditional)
    question = "근속 인정 여부와 DB 퇴직급여를 알려줘"
    state = _state(
        messages=[AIMessage(content="임의 숫자 999원")],
        domain_results=[policy_result, tax_result],
    )
    state["question"] = question

    result = await AnswerService(FakeSupervisor(result=state)).run(
        question_id="Q-001", question=question
    )

    assert result.state["domain_results"] == [policy_result, tax_result]
    assert (
        tax_result["calculations"][0]["input_sources"]
        == result.state["domain_results"][1]["calculations"][0]["input_sources"]
    )
    assert tax_result["evidence"] == result.state["domain_results"][1]["evidence"]
    assert "DB 퇴직급여: 30000000 KRW" in result.answer.answer
    assert "999" not in result.answer.answer
    if policy_conditional:
        assert "계속근로·근속 인정 여부 확인 필요" in result.answer.answer
    if tax_conditional:
        assert "퇴직소득세 산출에 필요한 별도 계산 계약과 입력 확인 필요" in result.answer.answer


async def test_answer_service_preserves_benefit_and_does_not_invent_retirement_tax() -> None:
    tax_result = _retirement_benefit_result(conditional=True)
    question = "DB 퇴직급여와 퇴직소득세까지 계산해줘"
    state = _state(
        messages=[AIMessage(content="퇴직소득세는 999원입니다.")],
        domain_results=[tax_result],
    )
    state["question"] = question

    result = await AnswerService(FakeSupervisor(result=state)).run(
        question_id="Q-001", question=question
    )

    assert "DB 퇴직급여: 30000000 KRW" in result.answer.answer
    assert "퇴직소득세 산출에 필요한 별도 계산 계약과 입력 확인 필요" in result.answer.answer
    assert "최초 퇴직소득세 전체 계산기는 현재 제공되지 않습니다." in result.answer.answer
    assert "999" not in result.answer.answer
    assert [item["calculator_id"] for item in tax_result["calculations"]] == [
        "db_retirement_benefit"
    ]


def _verified_numeric_result(
    *,
    domain: str = "tax_payout",
    statements: list[dict[str, str]],
    conclusion: str = "검증된 근거 기반 결론입니다.",
    missing_conditions: list[str] | None = None,
    calculations: list[Any] | None = None,
) -> DomainResult:
    status = "conditional" if missing_conditions else "determined"
    result: DomainResult = {
        "domain": domain,
        "execution_status": "completed",
        "decision": {
            "status": status,
            "conclusion": conclusion,
            "missing_conditions": missing_conditions or [],
        },
        "evidence": [],
        "calculations": calculations or [],
        "warnings": [],
    }
    result["verified_numeric_statements"] = statements
    return result


def _statement(*, source_id: str, text: str, source_type: str = "statutory_fact") -> dict[str, str]:
    return {"source_type": source_type, "source_id": source_id, "text": text}


# ---------------------------------------------------------------------------
# Main Numeric Firewall — item 11의 A~O 공격 케이스.
# ---------------------------------------------------------------------------


async def test_firewall_A_single_static_verified_number_is_substituted() -> None:
    statement = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    domain_result = _verified_numeric_result(statements=[statement])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"세액공제 한도는 {token}입니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert (
        result.answer.answer
        == "세액공제 한도는 연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.입니다."
    )
    assert token not in result.answer.answer


async def test_firewall_B_two_static_verified_numbers_are_both_substituted() -> None:
    contribution = _statement(
        source_id="contribution_limit_combined",
        text="연금저축과 IRP를 합산한 납입한도는 연 1,800만원입니다.",
    )
    tax_credit = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    token_a = placeholder_token("tax_payout", "contribution_limit_combined")
    token_b = placeholder_token("tax_payout", "tax_credit_limit_combined")
    domain_result = _verified_numeric_result(statements=[contribution, tax_credit])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"납입한도는 {token_a}, 공제한도는 {token_b}입니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "1,800만원" in result.answer.answer
    assert "900만원" in result.answer.answer
    assert token_a not in result.answer.answer
    assert token_b not in result.answer.answer


async def test_firewall_C_static_plus_calculation_mixed_when_no_calculations_present() -> None:
    """이번 단계는 calculation path를 재설계하지 않는다 — verified_numeric_statements만
    있고 calculations가 비어 있으면(정적 사실 전용) 그대로 firewall만 적용된다."""

    statement = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    domain_result = _verified_numeric_result(statements=[statement])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"세액공제 한도는 {token}입니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "900만원" in result.answer.answer


async def test_firewall_C2_existing_calculation_stabilizer_still_wins_when_calculations_present() -> (
    None
):
    """기존 `_stabilize_calculation_answer` 동작은 이번 작업으로 절대 깨지지 않는다."""

    domain_result = _calculation_result()
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="연금수령한도는 999원입니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "연금수령한도: 1200000.0 KRW" in result.answer.answer
    assert "999" not in result.answer.answer


async def test_firewall_D_reformatted_verified_number_outside_placeholder_falls_back() -> None:
    statement = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    domain_result = _verified_numeric_result(statements=[statement])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"세액공제 한도는 9,000,000원({token})이 맞습니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "9,000,000원" not in result.answer.answer
    assert "연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다." in result.answer.answer


async def test_firewall_E_unverified_percentage_falls_back() -> None:
    statement = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    domain_result = _verified_numeric_result(statements=[statement])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"{token} 적용 세율은 16.5%입니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "16.5" not in result.answer.answer
    assert "연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다." in result.answer.answer


async def test_firewall_F_unverified_krw_amount_falls_back() -> None:
    statement = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    domain_result = _verified_numeric_result(statements=[statement])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"{token} 최대 절세액은 148만 5천원입니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "148만 5천원" not in result.answer.answer
    assert "연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다." in result.answer.answer


async def test_firewall_static_fact_regression_mislabeled_conclusion_never_leaks() -> None:
    """#159 핵심 회귀(Main 레벨): tax_payout 도메인 conclusion이 잘못 라벨링된
    숫자(세액공제 한도로 오인된 납입한도 1,800만원)를 담고 있고 Main이 그걸 그대로
    베껴 써도, verified_numeric_statements가 있으면 최종 답변은 항상 registry가
    render한 올바른 문장으로만 귀결된다."""

    statement = _statement(
        source_id="annual_pension_account_contribution_limit",
        text="연금저축과 IRP를 합산한 연간 납입한도는 1,800만원입니다.",
    )
    domain_result = _verified_numeric_result(
        statements=[statement],
        # 도메인 conclusion 자체가 잘못 라벨링됐다고 가정(방어 심층화 검증).
        conclusion="세액공제 한도는 1,800만원입니다.",
    )
    # Main이 placeholder 없이 그 잘못된 conclusion을 그대로 베껴 썼다고 가정.
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="세액공제 한도는 1,800만원입니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "연금저축과 IRP를 합산한 연간 납입한도는 1,800만원입니다." in result.answer.answer
    assert "세액공제 한도는 1,800만원입니다." not in result.answer.answer


async def test_firewall_G_hallucinated_calculation_never_survives_final_answer() -> None:
    """item 12: 관찰된 실제 hallucination(16.5%, 13.2%, 148만 5천원, 약 1,125만원)이
    최종 답변에 절대 남지 않아야 한다."""

    statement = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    domain_result = _verified_numeric_result(statements=[statement])
    hallucinated = (
        f"{token} 총 급여가 5,500만원 이하인 경우 16.5%, 이상인 경우 13.2%가 적용되며 "
        "최대 148만 5천원의 절세 효과를 볼 수 있습니다. 최대 공제를 받으려면 "
        "약 1,125만원을 납입하면 됩니다."
    )
    supervisor = FakeSupervisor(
        result=_state(messages=[AIMessage(content=hallucinated)], domain_results=[domain_result])
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    for leaked in ("16.5%", "13.2%", "148만 5천원", "1,125만원", "5,500만원"):
        assert leaked not in result.answer.answer
    assert "연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다." in result.answer.answer


async def test_firewall_H_qualitative_only_answer_is_unaffected_backward_compatible() -> None:
    """verified_numeric_statements가 없는 기존 결과는 firewall이 전혀 개입하지 않는다."""

    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="연금저축과 IRP는 세제상 차이가 있습니다.")],
            domain_results=[_completed_result()],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert result.answer.answer == "연금저축과 IRP는 세제상 차이가 있습니다."


# ---------------------------------------------------------------------------
# UX regression 이식: pseudo-placeholder 노출 / 문장 꼬리 중복.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["conditional", "undetermined"])
async def test_failed_or_terminalized_calculation_cannot_add_numeric_claim(status: str) -> None:
    question = "연금계좌 평가액이 1억원이면 연금수령한도는 얼마인가요?"
    domain_result: DomainResult = {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": status,
            "conclusion": "계산 도구 결과를 확보하지 못했습니다.",
            "missing_conditions": ["검증된 계산 결과"],
        },
        "evidence": [],
        "calculations": [],
        "warnings": ["안전한 결과로 종료했습니다."],
    }
    supervisor = FakeSupervisor(
        result={
            "messages": [AIMessage(content="연금수령한도는 1,200만원입니다.")],
            "question_id": "Q-001",
            "question": question,
            "domain_results": [domain_result],
        }
    )

    result = await AnswerService(supervisor).run(question_id="Q-001", question=question)

    assert "1,200만원" not in result.answer.answer
    assert "검증된 계산 결과" in result.answer.answer


async def test_determined_result_without_calculator_cannot_derive_new_number_from_user_inputs() -> (
    None
):
    question = "연금저축에 600만원을 납입하면 세액공제액은 얼마인가요?"
    domain_result: DomainResult = {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": "세액공제액은 99만원입니다.",
            "missing_conditions": [],
        },
        "evidence": [],
        "calculations": [],
        "warnings": [],
    }
    supervisor = FakeSupervisor(
        result={
            "messages": [AIMessage(content="세액공제액은 99만원입니다.")],
            "question_id": "Q-001",
            "question": question,
            "domain_results": [domain_result],
        }
    )

    result = await AnswerService(supervisor).run(question_id="Q-001", question=question)

    assert "99만원" not in result.answer.answer
    assert "새로운 수치 결론을 제공할 수 없습니다" in result.answer.answer


async def test_pseudo_placeholder_stripped_when_no_verified_numeric_statements_exist() -> None:
    """Policy 단독 라우팅처럼 verified_numeric_statements가 전혀 없으면
    `_stabilize_verified_numeric_answer`가 개입하지 않는다 — 그 경로에서 Main이
    스스로 흉내 낸 `{{1800}}` 같은 표기가 최종 답변에 그대로 남으면 안 된다."""

    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="연금계좌의 연간 납입 한도는 최대 {{1800}}만원입니다.")],
            domain_results=[_completed_result()],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "{{" not in result.answer.answer
    assert "}}" not in result.answer.answer
    assert "1800만원입니다" in result.answer.answer


async def test_pseudo_placeholder_cleanup_is_noop_for_normal_text() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="연금저축과 IRP는 세제상 차이가 있습니다.")],
            domain_results=[_completed_result()],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert result.answer.answer == "연금저축과 IRP는 세제상 차이가 있습니다."


async def test_sentence_tail_unit_residue_is_stripped_after_substitution() -> None:
    """치환된 canonical 문장 바로 뒤에 Main이 붙인 단위 잔여물
    ("...600만원입니다.만원까지...")이 결정론적으로 제거된다."""

    statement = _statement(
        source_id="pension_savings_tax_credit_limit",
        text="연금저축 단독 세액공제 대상 납입한도는 600만원입니다.",
    )
    token = placeholder_token("tax_payout", "pension_savings_tax_credit_limit")
    domain_result = _verified_numeric_result(statements=[statement])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"연간 최대 {token}만원까지 세액공제가 가능합니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "입니다.만원" not in result.answer.answer
    assert "연금저축 단독 세액공제 대상 납입한도는 600만원입니다." in result.answer.answer
    assert "세액공제가 가능합니다." in result.answer.answer


async def test_sentence_tail_non_unit_text_is_preserved() -> None:
    """단위 잔여물이 아닌 평범한 이어지는 문장은 그대로 보존된다(과도한 제거 방지)."""

    statement = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    domain_result = _verified_numeric_result(statements=[statement])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"{token} 이 점을 참고하세요.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "이 점을 참고하세요." in result.answer.answer


async def test_firewall_I_policy_and_tax_mixed_domain_placeholders_do_not_collide() -> None:
    policy_statement = _statement(source_id="x", text="IRP 계좌 이전은 접수 절차가 필요합니다.")
    tax_statement = _statement(source_id="x", text="세액공제 한도는 연 900만원입니다.")
    policy_token = placeholder_token("policy", "x")
    tax_token = placeholder_token("tax_payout", "x")
    assert policy_token != tax_token

    policy_result = _verified_numeric_result(domain="policy", statements=[policy_statement])
    tax_result = _verified_numeric_result(domain="tax_payout", statements=[tax_statement])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"{policy_token} 그리고 {tax_token}")],
            domain_results=[policy_result, tax_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "접수 절차가 필요합니다" in result.answer.answer
    assert "연 900만원" in result.answer.answer


async def test_firewall_J_user_input_numeric_echo_outside_placeholder_falls_back() -> None:
    """질문에 있던 숫자라도 placeholder 밖에서 그대로 쓰면 안전 우선으로 fallback한다."""

    statement = _statement(
        source_id="tax_credit_limit_pension_savings_only",
        text="연금저축 단독 세액공제 한도는 연 600만원입니다.",
    )
    token = placeholder_token("tax_payout", "tax_credit_limit_pension_savings_only")
    domain_result = _verified_numeric_result(statements=[statement])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"700만원을 납입하셨군요. {token}")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "700만원" not in result.answer.answer
    assert "연금저축 단독 세액공제 한도는 연 600만원입니다." in result.answer.answer


async def test_firewall_K_missing_placeholder_falls_back() -> None:
    statement = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    domain_result = _verified_numeric_result(statements=[statement])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="네, 맞습니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다." in result.answer.answer


async def test_firewall_L_duplicate_placeholder_is_tolerated_and_deduped() -> None:
    statement = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    domain_result = _verified_numeric_result(statements=[statement])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"{token} 다시 말하지만 {token}입니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert (
        result.answer.answer.count("연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.") == 1
    )
    assert token not in result.answer.answer


async def test_firewall_M_malformed_placeholder_falls_back() -> None:
    statement = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    domain_result = _verified_numeric_result(statements=[statement])
    broken_token = "{{VERIFIED_NUMERIC:tax_payout:tax_credit_limit_combined"  # 닫는 중괄호 없음
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"한도는 {broken_token} 입니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다." in result.answer.answer
    assert broken_token not in result.answer.answer


async def test_firewall_N_unknown_placeholder_falls_back() -> None:
    statement = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    unknown_token = placeholder_token("tax_payout", "invented_by_main")
    domain_result = _verified_numeric_result(statements=[statement])
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"{token} 그리고 참고로 {unknown_token}")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert unknown_token not in result.answer.answer
    assert "연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다." in result.answer.answer


async def test_firewall_O_reordered_placeholders_are_both_accepted() -> None:
    contribution = _statement(
        source_id="contribution_limit_combined",
        text="연금저축과 IRP를 합산한 납입한도는 연 1,800만원입니다.",
    )
    tax_credit = _statement(
        source_id="tax_credit_limit_combined",
        text="연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
    )
    token_a = placeholder_token("tax_payout", "contribution_limit_combined")
    token_b = placeholder_token("tax_payout", "tax_credit_limit_combined")
    domain_result = _verified_numeric_result(statements=[contribution, tax_credit])
    # domain_results 목록 순서(contribution, tax_credit)와 반대로 배치한다.
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content=f"공제한도는 {token_b}, 납입한도는 {token_a}입니다.")],
            domain_results=[domain_result],
        )
    )

    result = await AnswerService(supervisor).run(
        question_id="Q-001", question="연금계좌를 이전할 수 있나요?"
    )

    assert "900만원" in result.answer.answer
    assert "1,800만원" in result.answer.answer
    assert result.answer.answer.index("900만원") < result.answer.answer.index("1,800만원")


async def test_answer_service_normalizes_supervisor_execution_failure() -> None:
    supervisor = FakeSupervisor(error=RuntimeError("provider 내부 오류와 민감정보"))

    with pytest.raises(SupervisorExecutionError) as exc_info:
        await AnswerService(supervisor).run(
            question_id="Q-001",
            question="연금계좌를 이전할 수 있나요?",
        )

    assert str(exc_info.value) == "Main Supervisor 실행에 실패했습니다."
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


async def test_answer_service_rejects_missing_final_answer() -> None:
    supervisor = FakeSupervisor(
        result=_state(
            messages=[HumanMessage(content="연금계좌를 이전할 수 있나요?")],
            domain_results=[_completed_result()],
        )
    )

    with pytest.raises(FinalAnswerMissingError):
        await AnswerService(supervisor).run(
            question_id="Q-001",
            question="연금계좌를 이전할 수 있나요?",
        )


async def test_answer_service_rejects_invalid_domain_result() -> None:
    invalid_result = _completed_result()
    del invalid_result["decision"]
    supervisor = FakeSupervisor(
        result=_state(
            messages=[AIMessage(content="완료했습니다.")],
            domain_results=[invalid_result],
        )
    )

    with pytest.raises(InvalidSupervisorResultError):
        await AnswerService(supervisor).run(
            question_id="Q-001",
            question="연금계좌를 이전할 수 있나요?",
        )


class BlockingSupervisor:
    """동시 실행 수와 취소를 관찰하는 테스트 Supervisor."""

    def __init__(self, *, delay_seconds: float | None = None) -> None:
        self.delay_seconds = delay_seconds
        self.active = 0
        self.max_active = 0
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def ainvoke(
        self,
        input: dict[str, Any],
        /,
        *,
        context: ExecutionContext,
    ) -> Mapping[str, Any]:
        del context
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.started.set()
        try:
            if self.delay_seconds is None:
                await self.release.wait()
            else:
                await asyncio.sleep(self.delay_seconds)
        finally:
            self.active -= 1
        return {
            "messages": [AIMessage(content="완료했습니다.")],
            "question_id": input["question_id"],
            "question": input["question"],
            "domain_results": [],
        }


async def test_answer_service_limits_concurrent_requests_and_waits_for_capacity() -> None:
    supervisor = BlockingSupervisor()
    config = AgentRuntimeConfig(max_concurrent_answers=2, answer_timeout_seconds=1)
    service = AnswerService(supervisor, config=config)
    tasks = [
        asyncio.create_task(service.run(question_id=f"Q-{index}", question="질문"))
        for index in range(3)
    ]

    while supervisor.active < 2:
        await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert supervisor.calls == 2
    assert supervisor.max_active == 2

    supervisor.release.set()
    results = await asyncio.gather(*tasks)

    assert [result.state["question_id"] for result in results] == ["Q-0", "Q-1", "Q-2"]
    assert supervisor.calls == 3
    assert supervisor.max_active == 2


async def test_answer_service_rejects_above_bounded_admission_limit() -> None:
    supervisor = BlockingSupervisor()
    service = AnswerService(
        supervisor,
        config=AgentRuntimeConfig(
            max_concurrent_answers=1,
            max_pending_answers=0,
            answer_timeout_seconds=1,
        ),
    )
    active = asyncio.create_task(service.run(question_id="Q-active", question="질문"))
    await supervisor.started.wait()

    rejected = await asyncio.gather(
        *(service.run(question_id=f"Q-overflow-{index}", question="질문") for index in range(100)),
        return_exceptions=True,
    )

    assert all(isinstance(result, AnswerServiceOverloadedError) for result in rejected)
    assert supervisor.calls == 1
    assert supervisor.max_active == 1

    supervisor.release.set()
    result = await active
    assert result.state["question_id"] == "Q-active"


async def test_answer_service_deadline_includes_capacity_wait_and_graph_execution() -> None:
    supervisor = BlockingSupervisor(delay_seconds=0.05)
    config = AgentRuntimeConfig(
        max_concurrent_answers=1,
        answer_timeout_seconds=0.02,
    )
    service = AnswerService(supervisor, config=config)

    tasks = [
        asyncio.create_task(service.run(question_id=f"Q-{index}", question="질문"))
        for index in range(2)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    assert all(isinstance(result, AnswerServiceTimeoutError) for result in results)
    assert supervisor.calls == 1
    assert supervisor.max_active == 1


async def test_answer_service_cancellation_releases_capacity() -> None:
    supervisor = BlockingSupervisor()
    config = AgentRuntimeConfig(max_concurrent_answers=1, answer_timeout_seconds=1)
    service = AnswerService(supervisor, config=config)
    cancelled = asyncio.create_task(service.run(question_id="Q-1", question="질문"))
    await supervisor.started.wait()

    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled

    supervisor.release.set()
    result = await service.run(question_id="Q-2", question="질문")

    assert result.state["question_id"] == "Q-2"
    assert supervisor.max_active == 1


async def test_answer_service_shutdown_cancels_requests_before_closing_clients() -> None:
    events: list[str] = []

    class CancellationRecordingSupervisor(BlockingSupervisor):
        async def ainvoke(
            self,
            input: dict[str, Any],
            /,
            *,
            context: ExecutionContext,
        ) -> Mapping[str, Any]:
            try:
                return await super().ainvoke(input, context=context)
            except asyncio.CancelledError:
                events.append("request-cancelled")
                raise

    async def close_client() -> None:
        events.append("client-closed")

    supervisor = CancellationRecordingSupervisor()
    service = AnswerService(supervisor, close_callbacks=(close_client,))
    request = asyncio.create_task(service.run(question_id="Q-1", question="질문"))
    await supervisor.started.wait()

    await service.aclose()

    with pytest.raises(asyncio.CancelledError):
        await request
    assert events == ["request-cancelled", "client-closed"]
    with pytest.raises(AnswerServiceClosedError):
        await service.run(question_id="Q-2", question="질문")

    await service.aclose()
    assert events == ["request-cancelled", "client-closed"]


async def test_shutdown_never_closes_client_before_noncooperative_request_finishes() -> None:
    events: list[str] = []
    started = asyncio.Event()
    release = asyncio.Event()
    client_closed = asyncio.Event()

    class SlowCancellationSupervisor:
        async def ainvoke(
            self,
            input: dict[str, Any],
            /,
            *,
            context: ExecutionContext,
        ) -> Mapping[str, Any]:
            del context
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                events.append("request-cancelled")
                await release.wait()
            events.append("request-finished")
            return {
                "messages": [AIMessage(content="완료했습니다.")],
                "question_id": input["question_id"],
                "question": input["question"],
                "domain_results": [],
            }

    async def close_client() -> None:
        events.append("client-closed")
        client_closed.set()

    service = AnswerService(
        SlowCancellationSupervisor(),
        config=AgentRuntimeConfig(shutdown_timeout_seconds=0.01),
        close_callbacks=(close_client,),
    )
    request = asyncio.create_task(service.run(question_id="Q-1", question="질문"))
    await started.wait()

    await service.aclose()

    assert events == ["request-cancelled"]
    assert not client_closed.is_set()

    release.set()
    result = await request
    assert not client_closed.is_set()
    await service.aclose()

    assert result.state["question_id"] == "Q-1"
    assert events == ["request-cancelled", "request-finished", "client-closed"]
    await service.aclose()
    assert events == ["request-cancelled", "request-finished", "client-closed"]
