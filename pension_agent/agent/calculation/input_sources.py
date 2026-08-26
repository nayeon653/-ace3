"""Calculation Tool 입력값과 사용자·검색 원문의 대응을 검증한다."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

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
_SOURCE_MARKERS = {
    "account_valuation_krw": ("원",),
    "pension_year": ("년", "연차"),
    "total_assets_krw": ("원",),
    "total_liabilities_krw": ("원",),
    "total_units": ("좌",),
    "daily_loss_percentile_percent": ("%", "퍼센트"),
}


def inputs_match_trusted_sources(
    *,
    inputs: Mapping[str, Any],
    input_sources: Mapping[str, str],
    state: Mapping[str, Any],
) -> bool:
    """각 계산 입력이 신뢰 원문에 있는 단일 수치 구절과 일치하는지 확인한다."""

    if inputs.keys() != input_sources.keys():
        return False
    trusted_texts = _trusted_texts(state)
    if not trusted_texts:
        return False
    for field, value in inputs.items():
        source = _normalize_text(input_sources[field])
        markers = _SOURCE_MARKERS.get(field)
        if markers is None or not any(marker in source for marker in markers):
            return False
        if not source or not any(source in trusted_text for trusted_text in trusted_texts):
            return False
        quantities = _quantities(source)
        if len(quantities) != 1 or quantities[0] != _decimal(value):
            return False
    return True


def _trusted_texts(state: Mapping[str, Any]) -> tuple[str, ...]:
    texts = [state.get("question", "")]
    search_result = state.get("search_result")
    if search_result is not None:
        texts.extend(chunk.content for chunk in search_result.retrieved_chunks)
    return tuple(_normalize_text(text) for text in texts if isinstance(text, str) and text.strip())


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
