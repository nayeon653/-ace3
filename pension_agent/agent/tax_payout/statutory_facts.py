"""세제·수령 도메인의 법정 수치 registry.

LLM은 fact_id만 선택한다. value·unit·role·scope·문장은 전부 이 registry에서
Python이 그대로 만든다 — LLM이 다시 쓸 수 없다. 이 파일은 폐기된 NumericClaim
방식(LLM이 value/role/scope를 직접 작성하고 Python이 사후 검증)을 대체한다.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pension_agent.agent.contracts import VerifiedNumericStatement
from pension_agent.agent.search import SearchChunkPayload

NumericRole = Literal[
    "contribution_limit",
    "tax_credit_limit",
    "taxable_income_threshold",
    "tax_rate",
    "withdrawal_limit",
]
NumericUnit = Literal["KRW", "percent", "year", "month", "day", "count"]
ResourceType = Literal[
    "tax_credit_contribution",
    "investment_earnings",
    "retirement_income_principal",
    "non_tax_credit_principal",
]


class StatutoryNumericFact(BaseModel):
    """제공 문서의 법정 수치와 그 canonical 문장을 함께 보존한 registry record."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    fact_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    value: str = Field(min_length=1)
    unit: NumericUnit
    role: NumericRole
    scope: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    condition_ids: tuple[str, ...] = ()
    applies_to: tuple[ResourceType, ...]
    excludes: tuple[ResourceType, ...] = ()
    source_file_name: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    source_text: str = Field(min_length=1)
    effective_period: str = Field(min_length=1)
    canonical_text: str = Field(min_length=1)


@lru_cache(maxsize=1)
def _registry() -> dict[str, StatutoryNumericFact]:
    path = files(__package__).joinpath("statutory_numeric_facts.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    facts = [StatutoryNumericFact.model_validate(item) for item in payload]
    fact_ids = [fact.fact_id for fact in facts]
    if len(fact_ids) != len(set(fact_ids)):
        raise ValueError("statutory numeric fact_id는 중복될 수 없습니다.")
    return {fact.fact_id: fact for fact in facts}


def candidate_fact_hints(chunks: list[SearchChunkPayload]) -> list[dict[str, str]]:
    """검색된 청크와 같은 출처의 fact만 후보로 노출한다.

    registry 전체를 매번 보여주지 않는다. value·role·scope·canonical_text는
    포함하지 않는다 — LLM은 fact_id와 그 fact가 어떤 원문 발췌에서 왔는지만
    보고 고른다.
    """

    chunk_keys = {(chunk.source_file_name, chunk.locator) for chunk in chunks}
    return [
        {"fact_id": fact.fact_id, "source_excerpt": fact.source_text}
        for fact in _registry().values()
        if (fact.source_file_name, fact.locator) in chunk_keys
    ]


def resolve_statutory_facts(
    fact_ids: list[str],
    selected_chunks: list[SearchChunkPayload],
    fact_resource_types: dict[str, list[ResourceType]] | None = None,
) -> list[VerifiedNumericStatement]:
    """알려진 fact_id 중 제출된 evidence와 출처가 일치하는 것만 검증한다.

    unknown fact_id나 provenance가 맞지 않는 fact는 조용히 버린다 — 제출 전체를
    reject하지 않는다. 결론 전체를 막아 model-call 예산을 낭비하는 대신, 신뢰할
    수 있는 fact만 골라 Main Numeric Firewall이 최종 안전을 보장하게 한다.
    """

    registry = _registry()
    verified: list[VerifiedNumericStatement] = []
    for fact_id in dict.fromkeys(fact_ids):
        fact = registry.get(fact_id)
        if fact is None:
            continue
        if not _provenance_matches(fact, selected_chunks):
            continue
        selected_resource_types = (
            None if fact_resource_types is None else set(fact_resource_types.get(fact_id, []))
        )
        if not _applicability_matches(fact, selected_resource_types):
            continue
        verified.append(
            {
                "source_type": "statutory_fact",
                "source_id": fact.fact_id,
                "text": fact.canonical_text,
            }
        )
    return verified


def _applicability_matches(
    fact: StatutoryNumericFact, resource_types: set[ResourceType] | None
) -> bool:
    """LLM이 제안한 재원과 registry 적용 범위가 일치할 때만 fact를 허용한다."""

    # None은 기존 Python 호출자의 호환 경로다. 제품 Tool은 항상 list를 전달하며,
    # 빈 list는 재원 미제출이므로 fail-closed 한다.
    if resource_types is None:
        return True
    if not resource_types:
        return False
    if resource_types.intersection(fact.excludes):
        return False
    return resource_types.issubset(fact.applies_to)


def _provenance_matches(
    fact: StatutoryNumericFact, selected_chunks: list[SearchChunkPayload]
) -> bool:
    return any(
        chunk.source_file_name == fact.source_file_name
        and chunk.locator == fact.locator
        and fact.source_text in chunk.content
        for chunk in selected_chunks
    )
