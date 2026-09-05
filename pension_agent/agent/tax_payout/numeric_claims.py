"""Tax/Payout 결론에 포함된 수치의 의미와 출처를 검증한다."""

from __future__ import annotations

import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pension_agent.agent.contracts import CalculationResult
from pension_agent.agent.search import SearchChunkPayload

NumericOrigin = Literal["evidence", "user_input", "calculation"]
NumericRole = Literal[
    "contribution_limit",
    "tax_credit_limit",
    "tax_rate",
    "taxable_income_threshold",
    "withdrawal_limit",
    "tax_amount",
    "duration",
    "factual_input",
]
NumericUnit = Literal["KRW", "percent", "year", "month", "day", "count"]


class NumericClaim(BaseModel):
    """LLM이 제출하고 Python이 독립적으로 검증하는 수치 주장."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    value: str = Field(min_length=1)
    unit: NumericUnit
    role: NumericRole
    scope: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    condition_ids: tuple[str, ...] = ()
    origin: NumericOrigin
    source_ref: str = Field(min_length=1)


class StatutoryNumericFact(BaseModel):
    """제공 문서의 수치와 의미를 함께 보존한 registry record."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    fact_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    value: str = Field(min_length=1)
    unit: NumericUnit
    role: NumericRole
    scope: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    condition_ids: tuple[str, ...] = ()
    source_file_name: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    source_text: str = Field(min_length=1)
    effective_period: str = Field(min_length=1)


_MENTION_PATTERN = re.compile(
    r"(?P<number>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>억\s*원|천\s*만\s*원|만\s*원|천\s*원|원|%|퍼센트|프로|년|개월|일)?"
)
_UNIT_MULTIPLIERS = {
    "억원": Decimal(100000000),
    "천만원": Decimal(10000000),
    "만원": Decimal(10000),
    "천원": Decimal(1000),
    "원": Decimal(1),
}
_UNIT_NAMES = {
    "%": "percent",
    "퍼센트": "percent",
    "프로": "percent",
    "년": "year",
    "개월": "month",
    "일": "day",
}


def validate_numeric_claims(
    *,
    conclusion: str,
    claims: list[NumericClaim],
    question: str,
    selected_chunks: list[SearchChunkPayload],
    calculations: list[CalculationResult],
) -> bool:
    """결론의 모든 수치가 의미와 provenance까지 승인됐는지 확인한다."""

    mentions = _numeric_mentions(conclusion)
    if not mentions:
        return True
    approved: list[tuple[Decimal, str]] = []
    for claim in claims:
        normalized = _claim_value(claim)
        if normalized is None:
            return False
        if claim.origin == "evidence":
            if not _valid_evidence_claim(claim, selected_chunks):
                return False
        elif claim.origin == "user_input":
            if not _valid_user_input_claim(claim, question):
                return False
        elif not _valid_calculation_claim(claim, calculations):
            return False
        approved.append(normalized)
    return Counter(mentions) == Counter(approved)


def _valid_evidence_claim(claim: NumericClaim, selected_chunks: list[SearchChunkPayload]) -> bool:
    chunks = [chunk for chunk in selected_chunks if chunk.chunk_id == claim.source_ref]
    if len(chunks) != 1:
        return False
    chunk = chunks[0]
    claim_value = _claim_value(claim)
    if claim_value not in _numeric_mentions(chunk.content):
        return False
    claim_key = _semantic_key(claim)
    return any(
        _semantic_key(fact) == claim_key
        and fact.source_file_name == chunk.source_file_name
        and fact.locator == chunk.locator
        and fact.source_text in chunk.content
        for fact in _registry()
    )


def _valid_user_input_claim(claim: NumericClaim, question: str) -> bool:
    if claim.role != "factual_input" or claim.scope != "user_input":
        return False
    return claim.source_ref in question and _claim_value(claim) in _numeric_mentions(
        claim.source_ref
    )


def _valid_calculation_claim(claim: NumericClaim, calculations: list[CalculationResult]) -> bool:
    try:
        calculator_id, output_field = claim.source_ref.split(".", maxsplit=1)
    except ValueError:
        return False
    for calculation in calculations:
        if calculation["calculator_id"] != calculator_id:
            continue
        if output_field not in calculation["outputs"]:
            continue
        output = calculation["outputs"][output_field]
        unit = calculation["units"].get(output_field)
        if _normalized_value(output, unit) == _claim_value(claim):
            return True
    return False


def _semantic_key(
    value: NumericClaim | StatutoryNumericFact,
) -> tuple[Decimal, str, str, str, tuple[str, ...]]:
    normalized = _normalized_value(value.value, value.unit)
    if normalized is None:
        raise ValueError("registry 수치가 올바르지 않습니다.")
    return (*normalized, value.role, value.scope, tuple(value.condition_ids))


def _claim_value(claim: NumericClaim) -> tuple[Decimal, str] | None:
    return _normalized_value(claim.value, claim.unit)


def _normalized_value(value: object, unit: object) -> tuple[Decimal, str] | None:
    try:
        number = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    normalized_unit = str(unit)
    if normalized_unit in {"KRW", "percent", "year", "month", "day", "count"}:
        return number, normalized_unit
    return None


def _numeric_mentions(text: str) -> list[tuple[Decimal, str]]:
    mentions: list[tuple[Decimal, str]] = []
    for match in _MENTION_PATTERN.finditer(text):
        number = Decimal(match.group("number").replace(",", ""))
        raw_unit = re.sub(r"\s+", "", match.group("unit") or "")
        if raw_unit in _UNIT_MULTIPLIERS:
            mentions.append((number * _UNIT_MULTIPLIERS[raw_unit], "KRW"))
        else:
            mentions.append((number, _UNIT_NAMES.get(raw_unit, "count")))
    return mentions


@lru_cache(maxsize=1)
def _registry() -> tuple[StatutoryNumericFact, ...]:
    path = files(__package__).joinpath("statutory_numeric_facts.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    registry = tuple(StatutoryNumericFact.model_validate(item) for item in payload)
    fact_ids = [fact.fact_id for fact in registry]
    if len(fact_ids) != len(set(fact_ids)):
        raise ValueError("statutory numeric fact_id는 중복될 수 없습니다.")
    return registry
