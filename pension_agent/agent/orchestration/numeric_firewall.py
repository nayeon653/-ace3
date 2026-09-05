"""Main Supervisor가 검증되지 않은 숫자를 만들지 못하게 막는 결정론적 유틸리티.

Main은 `VerifiedNumericStatement.text`를 직접 보지 않는다. 대신 placeholder
token만 받아 답변에 배치하고, 실제 문장은 :mod:`orchestration.service`의
stabilizer가 마지막에 치환한다. 이 모듈은 그 경계 양쪽(Tool 노출·최종 치환)이
공유하는 placeholder 형식과 숫자 정규화 로직만 담는다.
"""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal
from typing import NamedTuple

from pension_agent.agent.contracts import (
    DomainName,
    VerifiedNumericPlaceholder,
    VerifiedNumericStatement,
)

_PLACEHOLDER_PREFIX = "VERIFIED_NUMERIC"
_TOKEN_OPEN = "{{"


def placeholder_token(domain: DomainName, source_id: str) -> str:
    """도메인과 source_id로 고유한 placeholder token을 만든다.

    카운터 없이 값만으로 결정되므로, Main이 여러 도메인 Tool을 한 turn에
    병렬로 호출해도 서로 다른 두 Tool이 같은 token을 만들 위험이 없다.
    """

    return f"{_TOKEN_OPEN}{_PLACEHOLDER_PREFIX}:{domain}:{source_id}}}}}"


def build_verified_numeric_placeholders(
    domain: DomainName,
    statements: list[VerifiedNumericStatement],
) -> list[VerifiedNumericPlaceholder]:
    """Tool 결과에 넣을 placeholder 목록을 만든다. `text`는 절대 포함하지 않는다."""

    return [
        {
            "placeholder": placeholder_token(domain, statement["source_id"]),
            "source_id": statement["source_id"],
        }
        for statement in statements
    ]


class PlaceholderScanResult(NamedTuple):
    """본문에서 찾은 유효 token 개수와, `{{`로 시작했지만 유효하지 않은 조각."""

    counts: Counter[str]
    malformed: list[str]


def scan_placeholders(text: str, expected_tokens: set[str]) -> PlaceholderScanResult:
    """`{{`로 시작하는 모든 위치를 검사해 유효 token과 그 외를 분리한다.

    대소문자 오타·중괄호 미닫힘·존재하지 않는 source_id를 포함해 `{{`로
    시작하는 모든 변형을 malformed로 잡아낸다 — 정규식 하나로 모든 오탈자
    패턴을 나열하는 대신, "유효 token 집합에 정확히 없으면 전부 의심"하는
    fail-closed 방식을 쓴다.
    """

    counts: Counter[str] = Counter()
    malformed: list[str] = []
    for match in re.finditer(re.escape(_TOKEN_OPEN), text):
        position = match.start()
        matched_token = next(
            (token for token in expected_tokens if text.startswith(token, position)),
            None,
        )
        if matched_token is not None:
            counts[matched_token] += 1
        else:
            malformed.append(text[position : position + 40])
    return PlaceholderScanResult(counts=counts, malformed=malformed)


def strip_known_placeholders(text: str, expected_tokens: set[str]) -> str:
    """알려진 token만 제거해 Main의 자유 생성 영역만 남긴다."""

    result = text
    for token in expected_tokens:
        result = result.replace(token, "")
    return result


# ---------------------------------------------------------------------------
# 숫자 정규화. `pension_agent.agent.tax_payout.numeric_claims._numeric_mentions`를
# 재사용하지 않는다 — 그 함수는 한글 조사가 뒤에 붙으면(`\b`가 한글끼리는 걸리지
# 않는다) 매칭에 실패하는 버그가 있었고, 목록 번호·날짜·조항번호를 money로
# 오인했다. 여기서는 money/percent만 type-aware로 추출한다.
# ---------------------------------------------------------------------------


class NumericKind:
    MONEY = "money"
    PERCENT = "percent"


class NormalizedNumber(NamedTuple):
    kind: str
    value: Decimal  # money: KRW 정수값. percent: 0~1 사이 소수(16.5% -> 0.165)


_UNIT_MULTIPLIERS: dict[str, Decimal] = {
    "억": Decimal(100000000),
    "천만": Decimal(10000000),
    "만": Decimal(10000),
    "천": Decimal(1000),
}
# 긴 단위부터 먼저 매칭해야 "천만"이 "천"+"만"으로 잘못 쪼개지지 않는다.
_UNIT_ALT = "|".join(sorted(_UNIT_MULTIPLIERS, key=len, reverse=True))

# "115만 5천원"처럼 (숫자)(단위) 토큰이 이어지다가 마지막에 원/KRW로 끝나는
# 연속 시퀀스를 하나의 금액으로 묶는다.
_COMPOUND_MONEY = re.compile(
    rf"(?P<body>(?:\d[\d,]*(?:\.\d+)?\s*(?:{_UNIT_ALT})\s*)+)(?:원|KRW)(?!\d)",
    re.IGNORECASE,
)
_COMPOUND_TOKEN = re.compile(rf"(\d[\d,]*(?:\.\d+)?)\s*({_UNIT_ALT})")

# 단위 없이 "9,000,000원"/"9000000원"/"1,155,000 KRW"처럼 그냥 원/KRW로 끝나는
# 금액. 한글은 조사가 공백 없이 바로 붙으므로(`\b`가 한글끼리는 걸리지 않는다)
# `\b` 대신 "뒤에 숫자가 이어지지만 않으면" 조건으로 잡는다.
_RAW_MONEY = re.compile(r"(?<![\d.,])(\d[\d,]{2,}(?:\.\d+)?)\s*(?:원|KRW)(?!\d)", re.IGNORECASE)

_PERCENT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(?:%|퍼센트|프로)")
# 0과 1 사이의 순수 소수만 세율로 본다(다른 숫자와 결합되지 않은 독립 토큰).
_DECIMAL_RATE = re.compile(r"(?<![\d.])0\.\d{1,4}(?!\d)")


def _clean_digits(raw: str) -> Decimal:
    return Decimal(raw.replace(",", ""))


def extract_numbers(text: str) -> list[NormalizedNumber]:
    """money/percent만 뽑는다. 목록 번호·날짜·조항번호는 매칭 대상이 아니다."""

    results: list[NormalizedNumber] = []
    consumed_spans: list[tuple[int, int]] = []

    for match in _COMPOUND_MONEY.finditer(text):
        total = Decimal(0)
        for token in _COMPOUND_TOKEN.finditer(match.group("body")):
            total += _clean_digits(token.group(1)) * _UNIT_MULTIPLIERS[token.group(2)]
        results.append(NormalizedNumber(NumericKind.MONEY, total))
        consumed_spans.append(match.span())

    def _is_consumed(position: int) -> bool:
        return any(start <= position < end for start, end in consumed_spans)

    for match in _RAW_MONEY.finditer(text):
        if _is_consumed(match.start()):
            continue
        results.append(NormalizedNumber(NumericKind.MONEY, _clean_digits(match.group(1))))

    for match in _PERCENT.finditer(text):
        results.append(
            NormalizedNumber(NumericKind.PERCENT, _clean_digits(match.group(1)) / Decimal(100))
        )

    for match in _DECIMAL_RATE.finditer(text):
        results.append(NormalizedNumber(NumericKind.PERCENT, Decimal(match.group(0))))

    return results
