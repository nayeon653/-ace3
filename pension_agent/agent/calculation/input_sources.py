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


def validated_input_sources(
    *,
    inputs: Mapping[str, Any],
    input_sources: Mapping[str, str],
    state: Mapping[str, Any],
) -> dict[str, CalculationInputSource] | None:
    """각 입력의 필드 의미·수치·원문 출처를 검증해 정규화한다."""

    if inputs.keys() != input_sources.keys():
        return None
    question, chunks = _trusted_sources(state)
    if not question and not chunks:
        return None
    validated: dict[str, CalculationInputSource] = {}
    for field, value in inputs.items():
        source = _normalize_text(input_sources[field])
        if field == "pension_treatment":
            if not _matches_pension_treatment_source(value, source):
                return None
        elif field == "recipient_age":
            if not _matches_recipient_age_source(value, source):
                return None
        elif field == "is_lifetime_annuity":
            if not _matches_lifetime_annuity_source(value, source):
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


def _matches_pension_tax_credit_source(field: str, source: str, value: Any) -> bool:
    groups = _PENSION_TAX_CREDIT_SOURCE_GROUPS[field]
    return _matches_grouped_money_source(groups, source, value)


def _matches_grouped_money_source(
    groups: tuple[tuple[str, ...], ...], source: str, value: Any
) -> bool:
    return any(
        "원" in phrase
        and all(any(token in phrase for token in group) for group in groups)
        and _matches_single_quantity(phrase, value)
        for phrase in _source_phrases(source)
    )


def _matches_pension_treatment_source(value: Any, source: str) -> bool:
    if value == "ordinary":
        return "연금수령" in source and "연금외수령" not in source and "부득이" not in source
    if value == "unavoidable":
        return "부득이" in source
    return False


def _matches_recipient_age_source(value: Any, source: str) -> bool:
    if not any(label in source for label in ("나이", "연령")):
        return False
    ages = [_decimal(match.group(1).replace(",", "")) for match in _AGE_PATTERN.finditer(source)]
    return len(ages) == 1 and ages[0] == _decimal(value)


def _matches_lifetime_annuity_source(value: Any, source: str) -> bool:
    if value is True:
        return "종신연금" in source and not any(
            label in source for label in ("비종신", "종신이 아님", "종신연금이 아님")
        )
    if value is False:
        return any(
            label in source for label in ("비종신", "종신이 아님", "종신연금이 아님", "확정기간")
        )
    return False


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
