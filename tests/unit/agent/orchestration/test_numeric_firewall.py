"""Main Numeric Firewall의 숫자 정규화·placeholder 유틸리티를 검증한다."""

from decimal import Decimal

from pension_agent.agent.contracts import VerifiedNumericStatement
from pension_agent.agent.orchestration.numeric_firewall import (
    build_verified_numeric_placeholders,
    extract_numbers,
    placeholder_token,
    scan_placeholders,
    strip_known_placeholders,
)


def test_placeholder_token_is_domain_and_source_id_keyed_not_counter_based() -> None:
    """병렬 Tool 호출에도 서로 다른 도메인·source_id는 절대 충돌하지 않는다."""

    assert (
        placeholder_token("tax_payout", "tax_credit_limit_combined")
        == "{{VERIFIED_NUMERIC:tax_payout:tax_credit_limit_combined}}"
    )
    assert placeholder_token("policy", "x") != placeholder_token("tax_payout", "x")


def test_build_verified_numeric_placeholders_excludes_text() -> None:
    statements: list[VerifiedNumericStatement] = [
        {
            "source_type": "statutory_fact",
            "source_id": "tax_credit_limit_combined",
            "text": "연금저축과 IRP를 합산한 세액공제 한도는 연 900만원입니다.",
        }
    ]

    placeholders = build_verified_numeric_placeholders("tax_payout", statements)

    assert placeholders == [
        {
            "placeholder": "{{VERIFIED_NUMERIC:tax_payout:tax_credit_limit_combined}}",
            "source_id": "tax_credit_limit_combined",
        }
    ]
    assert all("text" not in placeholder for placeholder in placeholders)
    assert "900만원" not in str(placeholders)


# --- P/Q/R/S: 표현이 달라도 같은 값은 canonical 정규화로 동일하게 취급한다 ---


def test_normalizes_formatted_krw_variants_to_the_same_value() -> None:
    variants = ["900만원", "9,000,000원", "9000000원"]
    for text in variants:
        numbers = extract_numbers(text)
        assert numbers == [("money", Decimal(9000000))], text


def test_normalizes_krw_english_unit_suffix() -> None:
    assert extract_numbers("1,155,000 KRW") == [("money", Decimal(1155000))]


def test_normalizes_compound_korean_amount() -> None:
    assert extract_numbers("115만 5천원") == [("money", Decimal(1155000))]


def test_normalizes_percent_and_decimal_rate_to_the_same_value() -> None:
    assert extract_numbers("16.5%") == [("percent", Decimal("0.165"))]
    assert extract_numbers("0.165") == [("percent", Decimal("0.165"))]


def test_normalizes_eok_and_cheonman_units() -> None:
    assert extract_numbers("1억 8천만원") == [("money", Decimal(180000000))]


# --- T: 한글 조사가 바로 붙는 boundary 회귀 테스트 (버그 재도입 방지) ---


def test_recognizes_amount_immediately_followed_by_korean_particle() -> None:
    """ "900만원입니다"처럼 조사가 공백 없이 붙어도 인식해야 한다.

    `\\b`(word boundary)는 한글끼리는 걸리지 않으므로, 과거 prototype에서
    `\\b`를 썼다가 실제 문장에서 전혀 매칭되지 않는 치명적 버그가 있었다.
    이 테스트는 그 버그의 재발을 막는다.
    """

    assert extract_numbers("연 900만원입니다") == [("money", Decimal(9000000))]
    assert extract_numbers("제가 700만원을 넣었어요") == [("money", Decimal(7000000))]
    assert extract_numbers("1,155,000원이 됩니다") == [("money", Decimal(1155000))]
    assert extract_numbers("16.5%로 계산됩니다") == [("percent", Decimal("0.165"))]


# --- U: 목록 번호·날짜·조항번호는 money/percent로 오인하지 않는다 ---


def test_ignores_list_numbers_dates_and_article_numbers() -> None:
    assert extract_numbers("1. 첫째 항목") == []
    assert extract_numbers("2. 둘째 항목") == []
    assert extract_numbers("2024년 3월 5일에 신청") == []
    assert extract_numbers("제3조 2항") == []
    assert extract_numbers("55세 이후 수령") == []


def test_extracts_multiple_numbers_in_one_sentence() -> None:
    numbers = extract_numbers("납입한도는 1,800만원이고 세액공제 한도는 900만원입니다.")
    assert numbers == [("money", Decimal(18000000)), ("money", Decimal(9000000))]


# --- placeholder 스캔: 완전성/malformed 판정 ---


def test_scan_placeholders_counts_repeated_valid_token() -> None:
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    scan = scan_placeholders(f"{token} 다시 말하지만 {token}입니다.", {token})

    assert scan.counts[token] == 2
    assert scan.malformed == []


def test_scan_placeholders_flags_unknown_source_id_as_malformed() -> None:
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    unknown = placeholder_token("tax_payout", "unknown_fact")
    scan = scan_placeholders(f"{token} 그리고 {unknown}", {token})

    assert scan.counts[token] == 1
    assert len(scan.malformed) == 1


def test_scan_placeholders_flags_unclosed_and_wrong_case_as_malformed() -> None:
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    broken = "{{VERIFIED_NUMERIC:tax_payout:tax_credit_limit_combined"  # 닫는 중괄호 없음
    wrong_case = "{{Verified_Numeric:tax_payout:tax_credit_limit_combined}}"
    scan = scan_placeholders(f"{broken} {wrong_case}", {token})

    assert scan.counts[token] == 0
    assert len(scan.malformed) == 2


def test_scan_placeholders_missing_when_expected_token_absent() -> None:
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    scan = scan_placeholders("이 답변에는 placeholder가 전혀 없습니다.", {token})

    assert token not in scan.counts
    assert scan.malformed == []


def test_scan_placeholders_ignores_order() -> None:
    """O: placeholder 순서가 바뀌어도(재배치) 완전성 판정에는 영향이 없다."""

    token_a = placeholder_token("policy", "a")
    token_b = placeholder_token("tax_payout", "b")
    scan = scan_placeholders(f"{token_b} 그리고 {token_a}", {token_a, token_b})

    assert scan.counts[token_a] == 1
    assert scan.counts[token_b] == 1
    assert scan.malformed == []


def test_strip_known_placeholders_removes_only_expected_tokens() -> None:
    token = placeholder_token("tax_payout", "tax_credit_limit_combined")
    stripped = strip_known_placeholders(f"한도는 {token}입니다. 16.5%는 남는다.", {token})

    assert token not in stripped
    assert "16.5%" in stripped
