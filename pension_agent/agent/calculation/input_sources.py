"""Calculation Tool 입력값과 사용자·검색 원문의 대응을 검증한다."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from pension_agent.agent.contracts import CalculationInputSource, CalculationResult

_WHITESPACE_PATTERN = re.compile(r"\s+")
_QUANTITY_PATTERN = re.compile(
    r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"\s*(?:천만|백만|십만|억|만|천|백|십)?"
)
_UNIT_MULTIPLIERS = {
    "억": Decimal(100000000),
    "천만": Decimal(10000000),
    "백만": Decimal(1000000),
    "십만": Decimal(100000),
    "만": Decimal(10000),
    "천": Decimal(1000),
    "백": Decimal(100),
    "십": Decimal(10),
}
_UNIT_SUFFIX_PATTERN = re.compile(r"(천만|백만|십만|억|만|천|백|십)$")
_PHRASE_SPLIT_PATTERN = re.compile(r"[;\n]+|,(?!\d)")
_AGE_PATTERN = re.compile(r"([+-]?(?:\d{1,3}(?:,\d{3})+|\d+))\s*세")
_NEGATION_EXPRESSIONS = ("아님", "아닌", "아니다", "해당하지 않음", "해당하지 않는다")
_NON_EXACT_EXPRESSIONS = (
    "이상",
    "이하",
    "초과",
    "미만",
    "부터",
    "전후",
    "약 ",
    "정도",
    "무렵",
)
_AGE_NON_EXACT_EXPRESSIONS = (
    "이상",
    "이하",
    "초과",
    "미만",
    "부터",
    "전후",
    "약 ",
    "정도",
    "무렵",
)
_RECEIPT_YEAR_PATTERN = re.compile(r"([+-]?(?:\d{1,3}(?:,\d{3})+|\d+))\s*년차")
_SOURCE_REQUIREMENTS = {
    "account_valuation_krw": (("평가액",), ("원",)),
    "pension_year": (("수령연차", "연금수령연차", "년차"), ("년", "연차")),
    "total_assets_krw": (("자산총액", "총자산", "자산"), ("원",)),
    "total_liabilities_krw": (("부채총액", "총부채", "부채"), ("원",)),
    "total_units": (("총좌수", "좌수"), ("좌",)),
    "daily_loss_percentile_percent": (("손실률",), ("%", "퍼센트")),
}
_PENSION_TAX_CREDIT_SOURCE_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    "pension_savings_net_contribution_krw": (("연금저축",), ("납입", "순납입")),
    "retirement_pension_net_contribution_krw": (("퇴직연금", "IRP"), ("납입", "순납입")),
    "pension_savings_isa_transfer_krw": (("연금저축",), ("ISA",), ("전환", "만기자금")),
    "retirement_pension_isa_transfer_krw": (
        ("퇴직연금", "IRP"),
        ("ISA",),
        ("전환", "만기자금"),
    ),
    "prior_same_maturity_isa_extra_eligible_contribution_used_krw": (
        ("ISA",),
        ("전년도", "기존 사용"),
    ),
    "remaining_tax_before_pension_credit_krw": (("잔여",), ("산출세액",)),
}
_INCOME_BASIS_LABELS: dict[str, tuple[str, ...]] = {
    "salary": ("총급여",),
    "comprehensive_income": ("종합소득금액",),
}
_PENSION_INCOME_MONEY_SOURCE_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    "target_taxable_amount_krw": (
        ("연금수령", "연금소득"),
        ("과세대상", "세액공제 받은 원금", "운용수익"),
    ),
    "annual_private_pension_taxable_income_krw": (
        ("연간", "해당 연도"),
        ("사적연금",),
        ("과세대상",),
        ("합계", "전체"),
    ),
    "taxable_amount_krw": (
        ("연금외수령", "중도해지", "일시금", "한도초과"),
        ("과세대상", "세액공제 받은 원금", "운용수익"),
    ),
}
_PENSION_INSTALLMENT_SOURCE_FIELDS = {
    "account_valuation_krw",
    "pension_year",
    "remaining_annual_limit_krw",
    "remaining_payments_in_year",
    "current_valuation_krw",
    "remaining_payments",
    "remaining_units",
    "standard_price_per_1000_units_krw",
}
_PENSION_WITHDRAWAL_AMOUNT_SOURCE_FIELDS = {
    "requested_withdrawal_krw",
    "tax_free_source_balance_krw",
    "deferred_retirement_source_balance_krw",
    "credited_and_earnings_source_balance_krw",
    "pension_treated_withdrawal_krw",
    "non_pension_treated_withdrawal_krw",
    "annual_private_pension_taxable_income_krw",
    "pension_treated_allocated_deferred_retirement_tax_krw",
    "non_pension_treated_allocated_deferred_retirement_tax_krw",
}


def validated_input_sources(
    *,
    inputs: Mapping[str, Any],
    input_sources: Mapping[str, str],
    state: Mapping[str, Any],
    calculator_id: str | None = None,
) -> dict[str, CalculationInputSource] | None:
    """각 입력의 필드 의미·수치·원문 출처를 검증해 정규화한다."""

    if inputs.keys() != input_sources.keys():
        return None
    question, chunks = _trusted_sources(state)
    if not question and not chunks:
        return None
    target_source = input_sources.get("target_taxable_amount_krw")
    annual_source = input_sources.get("annual_private_pension_taxable_income_krw")
    if (
        target_source is not None
        and annual_source is not None
        and _normalize_text(target_source) == _normalize_text(annual_source)
    ):
        return None
    installment_sources = [
        _normalize_text(input_sources[field])
        for field in inputs
        if field in _PENSION_INSTALLMENT_SOURCE_FIELDS
    ]
    if len(installment_sources) != len(set(installment_sources)):
        return None
    withdrawal_sources = [
        _normalize_text(input_sources[field])
        for field in inputs
        if field in _PENSION_WITHDRAWAL_AMOUNT_SOURCE_FIELDS
    ]
    if len(withdrawal_sources) != len(set(withdrawal_sources)):
        return None
    validated: dict[str, CalculationInputSource] = {}
    for field, value in inputs.items():
        source = _normalize_text(input_sources[field])
        if field == "wages_for_average_period_krw":
            if not _matches_average_period_wages_source(source, value):
                return None
        elif field == "included_days_for_average_wage":
            if not _matches_average_wage_included_days_source(source, value):
                return None
        elif field == "verified_service_years":
            if not _matches_verified_service_years_source(source, value):
                return None
        elif field == "annual_total_wages_krw":
            if not _matches_dc_annual_total_wages_source(source, value):
                return None
        elif field == "accumulated_contributions_krw":
            if not _matches_accumulated_contributions_source(source, value):
                return None
        elif field == "investment_gain_loss_krw":
            if not _matches_investment_gain_loss_source(source, value):
                return None
        elif field == "final_average_wage_30_days_krw":
            if not _matches_final_average_wage_source(source, value):
                return None
        elif field == "final_annual_total_wages_krw":
            if not _matches_final_annual_wages_source(source, value):
                return None
        elif field == "employment_duration_category":
            if not _matches_employment_duration_category(value, source):
                return None
        elif field == "previous_year_annual_wages_krw":
            if not _matches_previous_year_annual_wages_source(source, value):
                return None
        elif field == "preceding_12_month_wages_krw":
            if not _matches_preceding_12_month_wages_source(source, value):
                return None
        elif field == "average_monthly_wage_during_employment_krw":
            if not _matches_average_monthly_wage_source(source, value):
                return None
        elif field == "documented_medical_expenses_krw":
            if not _matches_documented_medical_expenses_source(source, value):
                return None
        elif field == "actual_medical_expenses_krw":
            if not _matches_actual_medical_expenses_source(source, value):
                return None
        elif field == "care_expenses_krw":
            if not _matches_care_expenses_source(source, value):
                return None
        elif field == "own_leave_months":
            if not _matches_own_leave_months_source(source, value):
                return None
        elif field == "pension_year":
            if not _matches_pension_year_source(value, source):
                return None
        elif field == "account_valuation_krw":
            if not _matches_account_valuation_source(value, source):
                return None
        elif field == "remaining_annual_limit_krw":
            if not _matches_remaining_annual_limit_source(value, source):
                return None
        elif field == "remaining_payments_in_year":
            if not _matches_annual_remaining_payments_source(value, source):
                return None
        elif field == "current_valuation_krw":
            if not _matches_current_valuation_source(value, source):
                return None
        elif field == "remaining_payments":
            if not _matches_total_remaining_payments_source(value, source):
                return None
        elif field == "remaining_units":
            if not _matches_remaining_units_source(value, source):
                return None
        elif field == "standard_price_per_1000_units_krw":
            if not _matches_standard_price_source(value, source):
                return None
        elif field == "pension_treatment":
            if not _matches_pension_treatment_source(value, source):
                return None
        elif field == "receipt_type":
            if not _matches_deferred_retirement_receipt_type_source(value, source):
                return None
        elif field == "actual_pension_receipt_year":
            if not _matches_actual_pension_receipt_year_source(value, source):
                return None
        elif field == "allocated_deferred_retirement_tax_krw":
            if not _matches_allocated_deferred_retirement_tax_source(source, value):
                return None
        elif field == "requested_withdrawal_krw":
            if calculator_id in {
                "medical_care_withdrawal_tax_limit",
                "medical_care_withdrawal_tax_breakdown",
            }:
                matches_request = _matches_medical_care_requested_withdrawal_source(source, value)
            else:
                matches_request = _matches_requested_withdrawal_source(source, value)
            if not matches_request:
                return None
        elif field == "tax_free_source_balance_krw":
            if not _matches_withdrawal_balance_source(source, value, "tax_free"):
                return None
        elif field == "deferred_retirement_source_balance_krw":
            if not _matches_withdrawal_balance_source(source, value, "deferred_retirement"):
                return None
        elif field == "credited_and_earnings_source_balance_krw":
            if not _matches_withdrawal_balance_source(source, value, "credited_and_earnings"):
                return None
        elif field == "pension_treated_withdrawal_krw":
            if not _matches_treated_withdrawal_source(source, value, pension=True):
                return None
        elif field == "non_pension_treated_withdrawal_krw":
            if not _matches_treated_withdrawal_source(source, value, pension=False):
                return None
        elif field == "pension_treated_allocated_deferred_retirement_tax_krw":
            if not _matches_treated_allocated_tax_source(source, value, pension=True):
                return None
        elif field == "non_pension_treated_allocated_deferred_retirement_tax_krw":
            if not _matches_treated_allocated_tax_source(source, value, pension=False):
                return None
        elif field == "recipient_age":
            if not _matches_recipient_age_source(value, source):
                return None
        elif field == "is_lifetime_annuity":
            if not _matches_lifetime_annuity_source(value, source):
                return None
        elif field == "target_taxable_amount_krw":
            if not _matches_target_taxable_amount_source(
                source, value, inputs.get("pension_treatment")
            ):
                return None
        elif field in _PENSION_INCOME_MONEY_SOURCE_GROUPS:
            if not _matches_grouped_money_source(
                _PENSION_INCOME_MONEY_SOURCE_GROUPS[field], source, value
            ):
                return None
        elif field == "income_basis":
            if not _matches_income_basis_label(value, source):
                return None
        elif field == "income_amount_krw":
            if not _matches_income_amount_source(source, inputs.get("income_basis")):
                return None
            if not _matches_single_quantity(source, value):
                return None
        elif field == "average_annualized_salary_2012_2019_krw":
            if not _matches_executive_salary_2012_2019_source(source, value):
                return None
        elif field == "average_annualized_salary_2020_onward_krw":
            if not _matches_executive_salary_2020_onward_source(source, value):
                return None
        elif field == "service_months_2012_2019":
            if not _matches_executive_service_months_2012_2019_source(source, value):
                return None
        elif field == "service_months_2020_onward":
            if not _matches_executive_service_months_2020_onward_source(source, value):
                return None
        elif field == "post_2011_limit_subject_payment_krw":
            if not _matches_post_2011_limit_subject_payment_source(source, value):
                return None
        else:
            if field in _PENSION_TAX_CREDIT_SOURCE_GROUPS:
                if not _matches_pension_tax_credit_source(field, source, value):
                    return None
            else:
                requirements = _SOURCE_REQUIREMENTS.get(field)
                if requirements is None:
                    return None
                labels, units = requirements
                if not any(label in source for label in labels) or not any(
                    unit in source for unit in units
                ):
                    return None
                if not _matches_single_quantity(source, value):
                    return None
        matched_source = _match_trusted_source(source, question=question, chunks=chunks)
        if matched_source is None:
            return None
        validated[field] = matched_source
    return validated


def _matches_average_period_wages_source(source: str, value: Any) -> bool:
    return _matches_retirement_money_source(
        source,
        value,
        required_groups=(
            ("최근 3개월", "평균임금 산정 대상 3개월"),
            ("임금 합계", "임금총액", "임금 총액"),
        ),
        forbidden=(
            "연간임금",
            "월급",
            "계좌입금",
            "최종 연간",
            "의료비",
            "threshold",
        ),
        ignored_tokens=("3개월",),
    )


def _matches_average_wage_included_days_source(source: str, value: Any) -> bool:
    return any(
        any(label in phrase for label in ("평균임금 산정 포함 일수", "산정일수", "포함 일수"))
        and not any(label in phrase for label in ("근속", "휴직", "요양", "재직"))
        and not _is_non_exact_phrase(phrase)
        and not _is_negated_phrase(phrase)
        and "일" in phrase
        and _matches_single_quantity(phrase, value)
        for phrase in _source_phrases(source)
    )


def _matches_verified_service_years_source(source: str, value: Any) -> bool:
    return any(
        any(label in phrase for label in ("계속근로연수", "검증된 근속연수", "근속연수"))
        and not any(label in phrase for label in ("배우자", "가족", "타인", "다른 사람"))
        and not _is_non_exact_phrase(phrase)
        and not _is_negated_phrase(phrase)
        and "년" in phrase
        and _matches_single_quantity(phrase, value)
        for phrase in _source_phrases(source)
    )


def _matches_dc_annual_total_wages_source(source: str, value: Any) -> bool:
    return _matches_retirement_money_source(
        source,
        value,
        required_groups=(("연간임금총액", "연간 임금총액"),),
        forbidden=(
            "최근 3개월",
            "월급",
            "직전 12개월",
            "직전연도",
            "의료비",
            "threshold",
            "누적 부담금",
            "계좌잔액",
            "최종 30일",
            "전환 기준",
            "전환기준",
        ),
    )


def _matches_accumulated_contributions_source(source: str, value: Any) -> bool:
    return _matches_retirement_money_source(
        source,
        value,
        required_groups=(("DC",), ("실제 누적 부담금", "누적 부담금")),
        forbidden=("계좌잔액", "계좌 잔액", "최소 사용자 부담금", "예상", "월 납입액"),
    )


def _matches_investment_gain_loss_source(source: str, value: Any) -> bool:
    for phrase in _source_phrases(source):
        if (
            any(label in phrase for label in ("%", "퍼센트", "수익률", "평가액", "계좌잔액"))
            or any(label in phrase for label in ("예상", "전망", "추정"))
            or _is_non_exact_phrase(phrase)
            or _is_negated_phrase(phrase)
            or "원" not in phrase
        ):
            continue
        quantities = _quantities(phrase)
        if len(quantities) != 1:
            continue
        quantity = quantities[0]
        expected = _decimal(value)
        if "운용손실" in phrase and "운용손익" not in phrase:
            if quantity >= 0 and expected == -quantity:
                return True
        elif "운용수익" in phrase and "운용손익" not in phrase:
            if quantity >= 0 and expected == quantity:
                return True
        elif "운용손익" in phrase and expected == quantity:
            return True
    return False


def _matches_final_average_wage_source(source: str, value: Any) -> bool:
    return _matches_retirement_money_source(
        source,
        value,
        required_groups=(
            ("DB→DC 전환 기준", "DB에서 DC로 전환 기준", "전환 기준", "전환기준"),
            ("최종 30일 평균임금", "최종 30일평균임금"),
        ),
        forbidden=("평균일급", "월급", "연간임금", "과거"),
        ignored_tokens=("30일",),
    )


def _matches_final_annual_wages_source(source: str, value: Any) -> bool:
    return _matches_retirement_money_source(
        source,
        value,
        required_groups=(
            ("DB→DC 전환 기준", "DB에서 DC로 전환 기준", "전환 기준", "전환기준"),
            ("최종 연간임금총액", "최종 연간 임금총액"),
        ),
        forbidden=("최근 3개월", "30일 평균임금", "누적 부담금"),
    )


def _matches_retirement_money_source(
    source: str,
    value: Any,
    *,
    required_groups: tuple[tuple[str, ...], ...],
    forbidden: tuple[str, ...],
    ignored_tokens: tuple[str, ...] = (),
) -> bool:
    return any(
        all(any(label in phrase for label in group) for group in required_groups)
        and not any(label in phrase for label in forbidden)
        and not _is_non_exact_phrase(phrase)
        and not _is_negated_phrase(phrase)
        and "원" in phrase
        and _matches_single_quantity(_without_tokens(phrase, ignored_tokens), value)
        for phrase in _source_phrases(source)
    )


def _without_tokens(source: str, tokens: tuple[str, ...]) -> str:
    for token in tokens:
        source = source.replace(token, "")
    return source


def _is_non_exact_phrase(phrase: str) -> bool:
    if any(expression in phrase for expression in _NON_EXACT_EXPRESSIONS):
        return True
    return bool(re.search(r"\d(?:[\d,.]*\d)?\s*[~∼]\s*\d", phrase))


def _matches_pension_tax_credit_source(field: str, source: str, value: Any) -> bool:
    groups = _PENSION_TAX_CREDIT_SOURCE_GROUPS[field]
    return _matches_grouped_money_source(groups, source, value)


def _matches_pension_year_source(value: Any, source: str) -> bool:
    normalized_source = source.replace(" ", "")
    has_explicit_label = "연금수령연차" in normalized_source
    return any(
        "실제수령연차" not in phrase.replace(" ", "")
        and (not has_explicit_label or "연금수령연차" in phrase.replace(" ", ""))
        and _matches_single_quantity(phrase, value)
        and len(_RECEIPT_YEAR_PATTERN.findall(phrase)) == 1
        for phrase in _source_phrases(source)
    )


def _matches_account_valuation_source(value: Any, source: str) -> bool:
    return _matches_grouped_money_source((("평가액", "평가금액"),), source, value)


def _matches_remaining_annual_limit_source(value: Any, source: str) -> bool:
    return _matches_grouped_money_source(
        (("당해연도", "올해"), ("남은", "잔여"), ("연금수령한도",)), source, value
    )


def _matches_annual_remaining_payments_source(value: Any, source: str) -> bool:
    return any(
        any(label in phrase for label in ("당해연도", "올해"))
        and any(label in phrase for label in ("잔여 지급횟수", "남은 지급횟수"))
        and "회" in phrase
        and _matches_single_quantity(phrase, value)
        for phrase in _source_phrases(source)
    )


def _matches_current_valuation_source(value: Any, source: str) -> bool:
    return _matches_grouped_money_source(
        (("현재",), ("계좌 평가액", "계좌평가액", "평가액")), source, value
    )


def _matches_total_remaining_payments_source(value: Any, source: str) -> bool:
    return any(
        any(label in phrase for label in ("전체 기간", "전체", "총"))
        and any(label in phrase for label in ("잔여 지급횟수", "잔여회차", "남은 지급횟수"))
        and not any(label in phrase for label in ("당해연도", "올해"))
        and "회" in phrase
        and _matches_single_quantity(phrase, value)
        for phrase in _source_phrases(source)
    )


def _matches_remaining_units_source(value: Any, source: str) -> bool:
    return any(
        any(label in phrase for label in ("잔고좌수", "보유좌수"))
        and "좌" in phrase
        and "원" not in phrase
        and _matches_single_quantity(phrase, value)
        for phrase in _source_phrases(source)
    )


def _matches_standard_price_source(value: Any, source: str) -> bool:
    return any(
        any(label in phrase.replace(" ", "") for label in ("1,000좌당기준가격", "1000좌당기준가격"))
        and "원" in phrase
        and _matches_single_quantity(
            re.sub(r"1,?000\s*좌당", "", phrase),
            value,
        )
        for phrase in _source_phrases(source)
    )


def _matches_grouped_money_source(
    groups: tuple[tuple[str, ...], ...], source: str, value: Any
) -> bool:
    return any(
        "원" in phrase
        and all(any(token in phrase for token in group) for group in groups)
        and _matches_single_quantity(phrase, value)
        for phrase in _source_phrases(source)
    )


_EXECUTIVE_APPROXIMATE_EXPRESSIONS = ("대략", "최대")
# "부터"는 일반적으로 개방형 범위 표현(예: "55세부터")이라 거부 대상이지만, 임원 한도
# 기간 필드는 "2012" "2019"(또는 "2020") 양쪽 연도가 모두 요구되는 닫힌 구간이므로
# "2012년부터 2019년까지"처럼 원문 그대로의 폐구간 표현을 허용한다.
_EXECUTIVE_NON_EXACT_EXPRESSIONS = tuple(
    expression for expression in _NON_EXACT_EXPRESSIONS if expression != "부터"
)


def _is_executive_non_exact_phrase(phrase: str) -> bool:
    if any(expression in phrase for expression in _EXECUTIVE_APPROXIMATE_EXPRESSIONS):
        return True
    if any(expression in phrase for expression in _EXECUTIVE_NON_EXACT_EXPRESSIONS):
        return True
    return bool(re.search(r"\d(?:[\d,.]*\d)?\s*[~∼]\s*\d", phrase))


_EXECUTIVE_YEAR_TOKENS = ("2012", "2019", "2020", "2011")


def _matches_executive_salary_2012_2019_source(source: str, value: Any) -> bool:
    return any(
        "2012" in phrase
        and "2019" in phrase
        and "2020" not in phrase
        and any(label in phrase for label in ("연평균", "연환산"))
        and any(label in phrase for label in ("총급여", "급여"))
        and "퇴직급여" not in phrase
        and "퇴직금" not in phrase
        and not _is_executive_non_exact_phrase(phrase)
        and not _is_negated_phrase(phrase)
        and "원" in phrase
        and _matches_single_quantity(_without_tokens(phrase, _EXECUTIVE_YEAR_TOKENS), value)
        for phrase in _source_phrases(source)
    )


def _matches_executive_salary_2020_onward_source(source: str, value: Any) -> bool:
    return any(
        "2020" in phrase
        and "2019" not in phrase
        and any(label in phrase for label in ("연평균", "연환산"))
        and any(label in phrase for label in ("총급여", "급여"))
        and "퇴직급여" not in phrase
        and "퇴직금" not in phrase
        and not _is_executive_non_exact_phrase(phrase)
        and not _is_negated_phrase(phrase)
        and "원" in phrase
        and _matches_single_quantity(_without_tokens(phrase, _EXECUTIVE_YEAR_TOKENS), value)
        for phrase in _source_phrases(source)
    )


def _matches_executive_service_months_2012_2019_source(source: str, value: Any) -> bool:
    return any(
        "2012" in phrase
        and "2019" in phrase
        and "2020" not in phrase
        and any(label in phrase for label in ("근무월수", "근무기간", "근속월수"))
        and "개월" in phrase
        and not _is_executive_non_exact_phrase(phrase)
        and not _is_negated_phrase(phrase)
        and _matches_single_quantity(_without_tokens(phrase, _EXECUTIVE_YEAR_TOKENS), value)
        for phrase in _source_phrases(source)
    )


def _matches_executive_service_months_2020_onward_source(source: str, value: Any) -> bool:
    return any(
        "2020" in phrase
        and "2019" not in phrase
        and any(label in phrase for label in ("근무월수", "근무기간", "근속월수"))
        and "개월" in phrase
        and not _is_executive_non_exact_phrase(phrase)
        and not _is_negated_phrase(phrase)
        and _matches_single_quantity(_without_tokens(phrase, _EXECUTIVE_YEAR_TOKENS), value)
        for phrase in _source_phrases(source)
    )


def _matches_post_2011_limit_subject_payment_source(source: str, value: Any) -> bool:
    return any(
        any(
            label in phrase
            for label in ("2012년 이후", "2012년이후", "한도 적용대상", "한도적용대상")
        )
        and any(label in phrase for label in ("지급액", "퇴직금"))
        and not _is_executive_non_exact_phrase(phrase)
        and not _is_negated_phrase(phrase)
        and "원" in phrase
        and _matches_single_quantity(_without_tokens(phrase, _EXECUTIVE_YEAR_TOKENS), value)
        for phrase in _source_phrases(source)
    )


def _matches_pension_treatment_source(value: Any, source: str) -> bool:
    for phrase in _source_phrases(source):
        if value == "ordinary" and (
            "연금수령" in phrase
            and "연금외수령" not in phrase
            and "부득이" not in phrase
            and not _is_negated_phrase(phrase)
        ):
            return True
        if value == "unavoidable" and "부득이" in phrase and not _is_negated_phrase(phrase):
            return True
    return False


def _matches_deferred_retirement_receipt_type_source(value: Any, source: str) -> bool:
    if value == "pension":
        return any(label in source for label in ("연금수령", "연금으로 수령")) and not any(
            label in source for label in ("연금외수령", "일시금", "중도해지", "한도초과")
        )
    if value == "non_pension":
        return any(label in source for label in ("연금외수령", "일시금", "중도해지", "한도초과"))
    return False


def _matches_actual_pension_receipt_year_source(value: Any, source: str) -> bool:
    if "실제" not in source or "횟수" in source or re.search(r"\d\s*회", source):
        return False
    if not any(
        label in source
        for label in ("실제수령연차", "실제 수령연차", "실제 연금수령연차", "실제 연금 수령 연차")
    ):
        return False
    years = [
        _decimal(match.group(1).replace(",", ""))
        for match in _RECEIPT_YEAR_PATTERN.finditer(source)
    ]
    return len(years) == 1 and years[0] == _decimal(value)


def _matches_allocated_deferred_retirement_tax_source(source: str, value: Any) -> bool:
    groups = (
        ("해당 인출분", "배분된"),
        ("이연퇴직소득세", "퇴직소득세"),
    )
    return "계좌 전체" not in source and _matches_grouped_money_source(groups, source, value)


def _matches_requested_withdrawal_source(source: str, value: Any) -> bool:
    return any(
        any(
            label in phrase
            for label in ("현재 인출 요청액", "이번 인출 요청액", "인출 요청액", "찾을 금액")
        )
        and not any(label in phrase for label in ("잔액", "연간", "합계", "과세대상"))
        and "원" in phrase
        and _matches_single_quantity(phrase, value)
        for phrase in _source_phrases(source)
    )


def _matches_employment_duration_category(value: Any, source: str) -> bool:
    if any(label in source for label in ("약 ", "정도", "무렵", "전후")):
        return False
    for phrase in _source_phrases(source):
        if (
            "재직" not in phrase
            or _is_negated_phrase(phrase)
            or any(label in phrase for label in ("배우자", "가족", "타인"))
        ):
            continue
        if value == "less_than_one_year" and "1년 미만" in phrase:
            return True
        if value == "at_least_one_year" and "1년 이상" in phrase:
            return True
        month_matches = re.findall(r"(\d+)\s*개월", phrase)
        if len(month_matches) == 1:
            months = int(month_matches[0])
            if value == "less_than_one_year" and months < 12:
                return True
            if value == "at_least_one_year" and months >= 12:
                return True
    return False


def _matches_previous_year_annual_wages_source(source: str, value: Any) -> bool:
    return _matches_medical_care_money_source(
        source,
        value,
        required_groups=(("직전연도", "직전 연도"), ("연간임금총액", "연간 임금총액")),
        forbidden=("직전 12개월", "월평균", "월급", "현재 연봉", "배우자", "가족", "타인"),
    )


def _matches_preceding_12_month_wages_source(source: str, value: Any) -> bool:
    return any(
        "직전 12개월" in phrase
        and any(label in phrase for label in ("임금", "급여"))
        and not any(
            label in phrase
            for label in ("직전연도", "직전 연도", "월평균", "배우자", "가족", "타인")
        )
        and not _is_negated_phrase(phrase)
        and _matches_single_quantity(phrase.replace("12개월", ""), value)
        for phrase in _source_phrases(source)
    )


def _matches_average_monthly_wage_source(source: str, value: Any) -> bool:
    return _matches_medical_care_money_source(
        source,
        value,
        required_groups=(("재직 중",), ("월평균 급여", "월 평균 급여", "월평균 임금")),
        forbidden=(
            "연간임금",
            "연간 임금",
            "직전 12개월",
            "직전연도",
            "배우자",
            "가족",
            "타인",
        ),
    )


def _matches_documented_medical_expenses_source(source: str, value: Any) -> bool:
    return _matches_medical_care_money_source(
        source,
        value,
        required_groups=(("근로자 부담", "본인 부담"), ("증빙 의료비", "의료비")),
        forbidden=("요청액", "인출액", "잔액", "간병비"),
    )


def _matches_medical_care_requested_withdrawal_source(source: str, value: Any) -> bool:
    return _matches_medical_care_money_source(
        source,
        value,
        required_groups=(
            ("의료·요양", "의료 요양", "의료비·요양", "의료비 요양", "의료 목적", "요양 목적"),
            ("총 인출 요청액", "총 요청 인출액", "인출 요청액", "요청한 총 인출액"),
        ),
        forbidden=("잔액", "실제 의료비", "간병비", "한도"),
    )


def _matches_actual_medical_expenses_source(source: str, value: Any) -> bool:
    return _matches_medical_care_money_source(
        source,
        value,
        required_groups=(("실제 의료비",),),
        forbidden=("요청액", "인출액", "잔액", "간병비"),
    )


def _matches_care_expenses_source(source: str, value: Any) -> bool:
    return _matches_medical_care_money_source(
        source,
        value,
        required_groups=(("간병비",),),
        forbidden=("의료비", "요청액", "인출액", "잔액"),
    )


def _matches_medical_care_money_source(
    source: str,
    value: Any,
    *,
    required_groups: tuple[tuple[str, ...], ...],
    forbidden: tuple[str, ...],
) -> bool:
    return any(
        all(any(label in phrase for label in group) for group in required_groups)
        and not any(label in phrase for label in forbidden)
        and not _is_negated_phrase(phrase)
        and _matches_zero_or_single_quantity(phrase, value, unit="원")
        for phrase in _source_phrases(source)
    )


def _matches_own_leave_months_source(source: str, value: Any) -> bool:
    return any(
        "본인" in phrase
        and "휴직" in phrase
        and not any(label in phrase for label in ("배우자", "가족", "요양기간", "재직기간"))
        and not _is_negated_phrase(phrase)
        and _matches_zero_or_single_quantity(phrase, value, unit="개월")
        for phrase in _source_phrases(source)
    )


def _matches_zero_or_single_quantity(source: str, value: Any, *, unit: str) -> bool:
    if _decimal(value) == 0 and any(label in source for label in ("없음", "없다", "없습니다")):
        return not _quantities(source)
    return unit in source and _matches_single_quantity(source, value)


def _matches_withdrawal_balance_source(source: str, value: Any, source_type: str) -> bool:
    labels = {
        "tax_free": ("세액공제 미적용 원금", "비과세 재원"),
        "deferred_retirement": ("이연퇴직소득", "퇴직금 재원"),
        "credited_and_earnings": ("세액공제 받은 원금·운용수익", "세액공제 받은 원금과 운용수익"),
    }[source_type]
    return any(
        any(label in phrase for label in labels)
        and "현재" in phrase
        and "잔액" in phrase
        and not any(label in phrase for label in ("이번 인출", "현재 인출액", "요청액"))
        and "원" in phrase
        and _matches_single_quantity(phrase, value)
        for phrase in _source_phrases(source)
    )


def _matches_treated_withdrawal_source(source: str, value: Any, *, pension: bool) -> bool:
    return any(
        any(label in phrase for label in ("현재 요청", "이번 인출", "현재 인출"))
        and (
            (pension and "연금수령" in phrase and "연금외수령" not in phrase)
            or (not pension and "연금외수령" in phrase)
        )
        and any(label in phrase for label in ("처리 금액", "처리되는 금액", "처리액"))
        and not any(label in phrase for label in ("연간", "합계", "잔액", "과세대상"))
        and "원" in phrase
        and _matches_single_quantity(phrase, value)
        for phrase in _source_phrases(source)
    )


def _matches_treated_allocated_tax_source(source: str, value: Any, *, pension: bool) -> bool:
    return any(
        any(label in phrase for label in ("해당 인출분", "배분된"))
        and any(label in phrase for label in ("이연퇴직소득세", "퇴직소득세"))
        and (
            (pension and "연금수령 처리" in phrase and "연금외수령 처리" not in phrase)
            or (not pension and "연금외수령 처리" in phrase)
        )
        and "계좌 전체" not in phrase
        and "원" in phrase
        and _matches_single_quantity(phrase, value)
        for phrase in _source_phrases(source)
    )


def _matches_recipient_age_source(value: Any, source: str) -> bool:
    for phrase in _source_phrases(source):
        if any(label in phrase for label in ("배우자", "가족", "부양가족", "자녀", "부모")):
            continue
        if not (
            any(label in phrase for label in ("나이", "연령"))
            or re.search(r"만\s*\d[\d,]*\s*세", phrase)
        ):
            continue
        if any(expression in phrase for expression in _AGE_NON_EXACT_EXPRESSIONS):
            continue
        if "~" in phrase or "∼" in phrase or "-" in phrase:
            continue
        ages = [
            _decimal(match.group(1).replace(",", "")) for match in _AGE_PATTERN.finditer(phrase)
        ]
        if len(ages) == 1 and ages[0] == _decimal(value):
            return True
    return False


def _matches_lifetime_annuity_source(value: Any, source: str) -> bool:
    if value is True:
        return any(
            "종신연금" in phrase and "비종신" not in phrase and not _is_negated_phrase(phrase)
            for phrase in _source_phrases(source)
        )
    if value is False:
        return any(
            any(
                label in phrase
                for label in (
                    "비종신",
                    "종신이 아님",
                    "종신연금이 아님",
                    "종신연금에 해당하지 않음",
                    "종신연금에 해당하지 않는다",
                    "확정기간",
                )
            )
            for phrase in _source_phrases(source)
        )
    return False


def _matches_target_taxable_amount_source(source: str, value: Any, pension_treatment: Any) -> bool:
    for phrase in _source_phrases(source):
        if any(label in phrase for label in ("연간", "합계", "전체 사적연금소득")):
            continue
        has_current_meaning = any(
            label in phrase
            for label in (
                "현재 인출",
                "현재 수령",
                "현재 연금수령",
                "이번 인출",
                "이번 수령",
                "해당 인출",
            )
        )
        if pension_treatment == "unavoidable" and "부득이한 사유로 인출" in phrase:
            has_current_meaning = True
        has_taxable_meaning = any(
            label in phrase for label in ("과세대상", "세액공제 받은 원금", "운용수익")
        )
        if not has_current_meaning or not has_taxable_meaning:
            continue
        if pension_treatment == "ordinary" and "연금수령" not in phrase:
            continue
        if pension_treatment == "unavoidable" and (
            "부득이" not in phrase or _is_negated_phrase(phrase)
        ):
            continue
        if "원" in phrase and _matches_single_quantity(phrase, value):
            return True
    return False


def _is_negated_phrase(phrase: str) -> bool:
    return any(expression in phrase for expression in _NEGATION_EXPRESSIONS)


def _source_phrases(source: str) -> list[str]:
    return [phrase.strip() for phrase in _PHRASE_SPLIT_PATTERN.split(source) if phrase.strip()]


def _matches_income_basis_label(value: Any, source: str) -> bool:
    labels = _INCOME_BASIS_LABELS.get(str(value))
    return labels is not None and any(label in source for label in labels)


def _matches_income_amount_source(source: str, income_basis: Any) -> bool:
    if "원" not in source:
        return False
    labels = _INCOME_BASIS_LABELS.get(str(income_basis))
    return labels is not None and any(label in source for label in labels)


def _matches_single_quantity(source: str, value: Any) -> bool:
    quantities = _quantities(source)
    return len(quantities) == 1 and quantities[0] == _decimal(value)


def calculation_evidence_chunk_ids(calculations: list[CalculationResult]) -> list[str]:
    """계산 입력이 검색 근거에서 왔다면 해당 청크 ID를 순서대로 반환한다."""

    return list(
        dict.fromkeys(
            source["chunk_id"]
            for calculation in calculations
            for source in calculation["input_sources"].values()
            if source["origin"] == "evidence" and source["chunk_id"] is not None
        )
    )


def _trusted_sources(state: Mapping[str, Any]) -> tuple[str, tuple[tuple[str, str], ...]]:
    question_value = state.get("question", "")
    question = _normalize_text(question_value) if isinstance(question_value, str) else ""
    chunks: list[tuple[str, str]] = []
    search_result = state.get("search_result")
    if search_result is not None:
        chunks.extend(
            (chunk.chunk_id, _normalize_text(chunk.content))
            for chunk in search_result.retrieved_chunks
            if chunk.content.strip()
        )
    return question, tuple(chunks)


def _match_trusted_source(
    source: str,
    *,
    question: str,
    chunks: tuple[tuple[str, str], ...],
) -> CalculationInputSource | None:
    if source and source in question:
        return {"origin": "question", "text": source, "chunk_id": None}
    for chunk_id, content in chunks:
        if source and source in content:
            return {"origin": "evidence", "text": source, "chunk_id": chunk_id}
    return None


def _normalize_text(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip()


def _quantities(source: str) -> list[Decimal]:
    values: list[Decimal] = []
    for match in _QUANTITY_PATTERN.finditer(source):
        token = match.group().replace(" ", "")
        unit_match = _UNIT_SUFFIX_PATTERN.search(token)
        unit = unit_match.group(1) if unit_match is not None else None
        number = token[: -len(unit)] if unit is not None else token
        try:
            value = Decimal(number.replace(",", ""))
        except InvalidOperation:
            continue
        if unit is not None:
            value *= _UNIT_MULTIPLIERS[unit]
        if value not in values:
            values.append(value)
    return values


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal("NaN")
