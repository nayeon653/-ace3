"""Main Supervisor 라우팅 프롬프트의 도메인 조합 커버리지를 검증한다."""

import pytest

from pension_agent.agent.orchestration.supervisor import load_main_supervisor_prompt


@pytest.fixture(scope="module")
def prompt() -> str:
    return load_main_supervisor_prompt()


@pytest.mark.parametrize(
    "example",
    [
        "IRP 계좌를 다른 금융사로 이전할 수 있나요?",
        "이 근속기간이 DB 퇴직급여 근속연수에 포함되나요?",
        "DB에서 DC로 전환할 수 있나요?",
    ],
)
def test_policy_only_examples_are_documented(prompt: str, example: str) -> None:
    assert f"`{example}` → 업무·제도" in prompt


@pytest.mark.parametrize(
    "example",
    [
        "IRP와 연금저축의 세액공제 차이는?",
        "연간임금총액 6000만원이면 DC 최소 사용자 부담금은 얼마인가요?",
        "DB와 DC 퇴직급여 금액을 비교해 주세요.",
        "임원 퇴직소득 한도가 얼마인가요?",
    ],
)
def test_tax_only_examples_are_documented(prompt: str, example: str) -> None:
    assert f"`{example}` → 세제·수령" in prompt


@pytest.mark.parametrize(
    "example",
    [
        "DC에서 의료비 중도인출이 가능한지와 세금까지 알려 주세요.",
        "DC에서 의료비 중도인출 가능 여부와 세금을 알려 주세요.",
        "근속 인정 여부를 확인해서 DB 퇴직급여도 계산해 주세요.",
        "이 근속기간이 인정되는지랑 DB 퇴직급여도 계산해 주세요.",
        "DB→DC 전환 가능 여부와 전환금액을 알려 주세요.",
        "DB에서 DC로 전환할 수 있는지, 그리고 전환금액은 얼마인지 알려 주세요.",
    ],
)
def test_policy_and_tax_composite_examples_are_documented(prompt: str, example: str) -> None:
    assert f"`{example}` → 업무·제도 + 세제·수령" in prompt


@pytest.mark.parametrize(
    "example",
    [
        "A펀드와 B펀드의 위험과 보수를 비교해 주세요.",
        "IRP로 A펀드를 매수할 수 있나요?",
    ],
)
def test_product_only_examples_are_documented(prompt: str, example: str) -> None:
    assert f"`{example}` → 상품·운용" in prompt


def test_prompt_keeps_executive_limit_domain_boundary_rule(prompt: str) -> None:
    assert "임원 해당 여부 자체를 업무·제도가 판정하지 않는다" in prompt
