"""도메인 검색 목표 조합 규칙을 검증한다."""

import pytest

from pension_agent.agent.search import combine_search_objective


def test_combine_search_objective_preserves_full_domain_scope_and_model_focus() -> None:
    result = combine_search_objective(
        domain_objective=(
            "ETF 정기 자동매수의 제공 여부와 대상 상품, 설정 제한 및 신청 절차를 확인한다."
        ),
        model_focus="ETF 정기 자동매수 설정 가능 여부",
    )

    assert result == (
        "ETF 정기 자동매수의 제공 여부와 대상 상품, 설정 제한 및 신청 절차를 확인한다.\n"
        "ETF 정기 자동매수 설정 가능 여부"
    )


def test_combine_search_objective_does_not_duplicate_identical_focus() -> None:
    assert (
        combine_search_objective(
            domain_objective="연금계좌 이전 조건 확인",
            model_focus=" 연금계좌 이전 조건 확인 ",
        )
        == "연금계좌 이전 조건 확인"
    )


@pytest.mark.parametrize(
    ("domain_objective", "model_focus"),
    [("", "세부 검색"), ("전체 판단", "")],
)
def test_combine_search_objective_rejects_missing_scope(
    domain_objective: str,
    model_focus: str,
) -> None:
    with pytest.raises(ValueError):
        combine_search_objective(
            domain_objective=domain_objective,
            model_focus=model_focus,
        )
