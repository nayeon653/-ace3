"""법정 수치 registry — fact 후보 노출과 provenance 검증을 단위 테스트한다."""

from pension_agent.agent.search import SearchChunkPayload
from pension_agent.agent.tax_payout.statutory_facts import (
    candidate_fact_hints,
    resolve_statutory_facts,
)
from pension_agent.core import DocumentType

_CHUNK_ID = "4c8f5763-1014-5d69-a612-5ca1c897a0b1"


def _doc41_chunk() -> SearchChunkPayload:
    return SearchChunkPayload(
        chunk_id=_CHUNK_ID,
        source_file_name="doc41.docx",
        document_type=DocumentType.PENSION_REFERENCE,
        chunk_index=0,
        title="doc41",
        locator="문서 내 청크 1",
        content=(
            "연금저축과 IRP는 합산해서 연1,800만원까지 입금이 가능하다. "
            "연금저축은 연600만원, IRP는 연금저축 납입액을 포함해서 연900만원이다."
        ),
    )


def _unrelated_chunk() -> SearchChunkPayload:
    return SearchChunkPayload(
        chunk_id="550e8400-e29b-41d4-a716-446655440000",
        source_file_name="unrelated.pdf",
        document_type=DocumentType.PENSION_REFERENCE,
        chunk_index=0,
        title="다른 문서",
        locator="1페이지",
        content="법정 수치와 무관한 내용입니다.",
    )


def _doc38_resource_scope_chunk() -> SearchChunkPayload:
    return SearchChunkPayload(
        chunk_id="a937a2ef-2e51-5cb3-b160-c53d5276677c",
        source_file_name="doc38.docx",
        document_type=DocumentType.PENSION_REFERENCE,
        chunk_index=0,
        title="doc38",
        locator="문서 내 청크 1",
        content=(
            "사적연금소득을 1년에 1,500만원 초과 수령 시 종합과세 되지만 "
            "이 1,500만원을 판단할 때 세액공제 안받은 돈과 퇴직금은 포함되지 않는다. "
            "세액공제 받은 금액과 운용수익은 연 1,500만원 초과로 인출하는 경우 "
            "종합과세된다."
        ),
    )


# --- candidate narrowing: 검색된 청크와 같은 출처의 fact만 노출한다 ---


def test_candidate_fact_hints_exposes_only_facts_from_retrieved_chunk() -> None:
    hints = candidate_fact_hints([_doc41_chunk()])

    fact_ids = {hint["fact_id"] for hint in hints}
    assert fact_ids == {
        "annual_pension_account_contribution_limit",
        "combined_pension_tax_credit_limit",
        "pension_savings_tax_credit_limit",
    }


def test_candidate_fact_hints_never_includes_registry_fields() -> None:
    """source_excerpt는 원문 발췌일 뿐, registry의 value/role/scope/canonical_text
    필드 자체는 어떤 hint에도 포함되지 않는다."""

    hints = candidate_fact_hints([_doc41_chunk()])

    for hint in hints:
        assert set(hint) == {"fact_id", "source_excerpt"}
    combined = str(hints)
    assert "합산한 세액공제 대상 납입한도는 900만원입니다" not in combined  # canonical_text
    assert "pension_savings_plus_irp" not in combined  # scope


def test_candidate_fact_hints_empty_for_unrelated_chunk() -> None:
    assert candidate_fact_hints([_unrelated_chunk()]) == []


def test_candidate_fact_hints_empty_without_chunks() -> None:
    assert candidate_fact_hints([]) == []


# --- resolve_statutory_facts: fact_id 선택 + provenance 검증 ---


def test_resolve_returns_canonical_text_for_valid_selection() -> None:
    statements = resolve_statutory_facts(["combined_pension_tax_credit_limit"], [_doc41_chunk()])

    assert statements == [
        {
            "source_type": "statutory_fact",
            "source_id": "combined_pension_tax_credit_limit",
            "text": "연금저축과 IRP를 합산한 세액공제 대상 납입한도는 900만원입니다.",
        }
    ]


def test_resolve_drops_unknown_fact_id() -> None:
    """K: unknown fact_id는 조용히 버려진다(제출 전체를 reject하지 않는다)."""

    assert resolve_statutory_facts(["hallucinated_fact_id"], [_doc41_chunk()]) == []


def test_resolve_drops_fact_when_selected_evidence_has_different_source() -> None:
    """L: registry의 실제 출처(doc41.docx)와 다른 청크만 선택되면 버려진다."""

    assert (
        resolve_statutory_facts(["combined_pension_tax_credit_limit"], [_unrelated_chunk()]) == []
    )


def test_resolve_drops_fact_when_chunk_content_does_not_contain_source_text() -> None:
    """M: 파일명·locator는 우연히 같아도 실제 원문(source_text)이 없으면 버려진다."""

    mismatched_chunk = SearchChunkPayload(
        chunk_id=_CHUNK_ID,
        source_file_name="doc41.docx",
        document_type=DocumentType.PENSION_REFERENCE,
        chunk_index=0,
        title="doc41",
        locator="문서 내 청크 1",
        content="완전히 다른 내용으로 교체된 청크입니다.",
    )

    assert resolve_statutory_facts(["combined_pension_tax_credit_limit"], [mismatched_chunk]) == []


def test_resolve_returns_empty_when_no_facts_selected() -> None:
    """N: 선택된 fact가 없으면(정성 질문 등) 검증된 문장도 없다."""

    assert resolve_statutory_facts([], [_doc41_chunk()]) == []


def test_resolve_deduplicates_repeated_fact_id_selection() -> None:
    """O: 같은 fact_id를 중복 선택해도 검증된 문장은 한 번만 나온다."""

    statements = resolve_statutory_facts(
        ["combined_pension_tax_credit_limit", "combined_pension_tax_credit_limit"],
        [_doc41_chunk()],
    )

    assert len(statements) == 1


def test_resolve_keeps_only_valid_facts_among_mixed_selection() -> None:
    """유효한 것과 무효한 것이 섞여 있으면 유효한 것만 남는다."""

    statements = resolve_statutory_facts(
        ["combined_pension_tax_credit_limit", "unknown_id"], [_doc41_chunk()]
    )

    assert [statement["source_id"] for statement in statements] == [
        "combined_pension_tax_credit_limit"
    ]


# --- E/F: 이웃 fact 구분(같은 scope 다른 role / 같은 role 다른 scope)이 각각 독립적으로 검증된다 ---


def test_resolve_distinguishes_same_scope_different_role_neighbors() -> None:
    """E: 같은 청크(같은 scope)에 contribution_limit과 tax_credit_limit이 함께 있어도
    선택한 fact_id에 정확히 대응하는 canonical_text만 나온다."""

    contribution = resolve_statutory_facts(
        ["annual_pension_account_contribution_limit"], [_doc41_chunk()]
    )
    tax_credit = resolve_statutory_facts(["combined_pension_tax_credit_limit"], [_doc41_chunk()])

    assert "납입한도" in contribution[0]["text"]
    assert "세액공제" in tax_credit[0]["text"]
    assert contribution[0]["text"] != tax_credit[0]["text"]


def test_resolve_distinguishes_same_role_different_scope_neighbors() -> None:
    """F: combined와 단독(pension_savings) 세액공제 한도는 role은 같지만 scope가
    다르므로 각각의 fact_id로만 정확히 구분된다."""

    combined = resolve_statutory_facts(["combined_pension_tax_credit_limit"], [_doc41_chunk()])
    solo = resolve_statutory_facts(["pension_savings_tax_credit_limit"], [_doc41_chunk()])

    assert "900만원" in combined[0]["text"]
    assert "600만원" in solo[0]["text"]


def test_resolve_drops_fact_when_resource_type_is_missing() -> None:
    assert (
        resolve_statutory_facts(
            ["retirement_income_principal_excluded_from_private_pension_threshold"],
            [_doc38_resource_scope_chunk()],
            {},
        )
        == []
    )


def test_resolve_drops_threshold_for_retirement_income_principal() -> None:
    chunk = SearchChunkPayload(
        chunk_id="6e63c867-ce73-5ad4-a8dc-16e67d60121e",
        source_file_name="doc38.docx",
        document_type=DocumentType.PENSION_REFERENCE,
        chunk_index=2,
        title="doc38",
        locator="문서 내 청크 3",
        content=(
            "연간 1,500만원 초과 수령 시 전액 다른 소득과 합산 종합과세 또는 16.5% 세율로 분리과세"
        ),
    )

    assert (
        resolve_statutory_facts(
            ["private_pension_taxable_income_threshold_with_filing_choice"],
            [chunk],
            {
                "private_pension_taxable_income_threshold_with_filing_choice": [
                    "retirement_income_principal"
                ]
            },
        )
        == []
    )


def test_resolve_accepts_threshold_for_credited_contribution_and_earnings() -> None:
    chunk = SearchChunkPayload(
        chunk_id="6e63c867-ce73-5ad4-a8dc-16e67d60121e",
        source_file_name="doc38.docx",
        document_type=DocumentType.PENSION_REFERENCE,
        chunk_index=2,
        title="doc38",
        locator="문서 내 청크 3",
        content=(
            "연간 1,500만원 초과 수령 시 전액 다른 소득과 합산 종합과세 또는 16.5% 세율로 분리과세"
        ),
    )

    statements = resolve_statutory_facts(
        ["private_pension_taxable_income_threshold_with_filing_choice"],
        [chunk],
        {
            "private_pension_taxable_income_threshold_with_filing_choice": [
                "tax_credit_contribution",
                "investment_earnings",
            ]
        },
    )

    assert [statement["source_id"] for statement in statements] == [
        "private_pension_taxable_income_threshold_with_filing_choice"
    ]


def test_resolve_returns_atomic_retirement_income_exclusion() -> None:
    statements = resolve_statutory_facts(
        ["retirement_income_principal_excluded_from_private_pension_threshold"],
        [_doc38_resource_scope_chunk()],
        {
            "retirement_income_principal_excluded_from_private_pension_threshold": [
                "retirement_income_principal"
            ]
        },
    )

    assert statements[0]["text"] == (
        "퇴직금 원금은 사적연금소득 연 1,500만원 판단에 포함되지 않습니다."
    )


def test_resolve_mixed_resources_binds_each_fact_independently() -> None:
    fact_ids = [
        "private_pension_threshold_applies_to_credited_contributions_and_earnings",
        "retirement_income_principal_excluded_from_private_pension_threshold",
    ]
    statements = resolve_statutory_facts(
        fact_ids,
        [_doc38_resource_scope_chunk()],
        {
            fact_ids[0]: ["tax_credit_contribution", "investment_earnings"],
            fact_ids[1]: ["retirement_income_principal"],
        },
    )

    assert [statement["source_id"] for statement in statements] == fact_ids
