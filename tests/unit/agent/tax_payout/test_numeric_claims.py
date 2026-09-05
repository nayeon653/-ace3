"""Tax/Payout 수치 의미·출처 검증 회귀 테스트."""

from decimal import Decimal

from pension_agent.agent.search import SearchChunkPayload, SearchResult
from pension_agent.agent.tax_payout.numeric_claims import (
    NumericClaim,
    validate_numeric_claims,
)
from pension_agent.agent.tax_payout.react import _build_tax_payout_result


def _chunk() -> SearchChunkPayload:
    return SearchChunkPayload(
        chunk_id="4c8f5763-1014-5d69-a612-5ca1c897a0b1",
        source_file_name="doc41.docx",
        document_type="pension_reference",
        chunk_index=0,
        title="doc41",
        locator="문서 내 청크 1",
        content=(
            "연금저축과 IRP는 합산해서 연1,800만원까지 입금이 가능하다. "
            "연금저축은 연600만원, IRP는 연금저축 납입액을 포함해서 연900만원이다."
        ),
    )


def _claim(
    value: str,
    *,
    role: str,
    scope: str,
    conditions: tuple[str, ...] = ("annual",),
) -> NumericClaim:
    return NumericClaim.model_validate(
        {
            "value": value,
            "unit": "KRW",
            "role": role,
            "scope": scope,
            "condition_ids": conditions,
            "origin": "evidence",
            "source_ref": _chunk().chunk_id,
        }
    )


def test_rejects_contribution_limit_as_tax_credit_limit() -> None:
    assert not validate_numeric_claims(
        conclusion="합산 세액공제 한도는 연 1,800만원입니다.",
        claims=[
            _claim(
                "18000000",
                role="tax_credit_limit",
                scope="pension_savings_plus_irp",
                conditions=("annual", "all_financial_institutions_combined"),
            )
        ],
        question="합산 세액공제 한도는 얼마인가요?",
        selected_chunks=[_chunk()],
        calculations=[],
    )


def test_rejects_pension_savings_limit_as_combined_limit() -> None:
    assert not validate_numeric_claims(
        conclusion="합산 세액공제 한도는 연 600만원입니다.",
        claims=[
            _claim(
                "6000000",
                role="tax_credit_limit",
                scope="pension_savings_plus_irp",
            )
        ],
        question="둘의 합산 한도는 얼마인가요?",
        selected_chunks=[_chunk()],
        calculations=[],
    )


def test_accepts_supported_evidence_claims_and_multiple_numbers() -> None:
    assert validate_numeric_claims(
        conclusion="합산 납입한도는 연 1,800만원이고 합산 공제한도는 900만원입니다.",
        claims=[
            _claim(
                "18000000",
                role="contribution_limit",
                scope="pension_savings_plus_irp",
                conditions=("annual", "all_financial_institutions_combined"),
            ),
            _claim(
                "9000000",
                role="tax_credit_limit",
                scope="pension_savings_plus_irp",
            ),
        ],
        question="납입한도와 공제한도를 알려 주세요.",
        selected_chunks=[_chunk()],
        calculations=[],
    )


def test_user_input_can_only_be_repeated_as_factual_input() -> None:
    question = "연 500만원을 납입했다고 가정해 주세요."
    factual = NumericClaim(
        value="5000000",
        unit="KRW",
        role="factual_input",
        scope="user_input",
        origin="user_input",
        source_ref="연 500만원을 납입",
    )
    promoted = factual.model_copy(update={"role": "tax_credit_limit", "scope": "pension_savings"})
    assert validate_numeric_claims(
        conclusion="사용자가 제시한 납입액은 연 500만원입니다.",
        claims=[factual],
        question=question,
        selected_chunks=[],
        calculations=[],
    )
    assert not validate_numeric_claims(
        conclusion="법정 공제한도는 연 500만원입니다.",
        claims=[promoted],
        question=question,
        selected_chunks=[],
        calculations=[],
    )


def test_calculation_claim_requires_matching_output_field() -> None:
    calculation = {
        "calculator_id": "pension_tax_credit",
        "inputs": {},
        "input_sources": {},
        "outputs": {"tax_credit_krw": Decimal(825000)},
        "units": {"tax_credit_krw": "KRW"},
        "warnings": [],
    }
    claim = NumericClaim(
        value="825000",
        unit="KRW",
        role="tax_amount",
        scope="pension_tax_credit",
        origin="calculation",
        source_ref="pension_tax_credit.tax_credit_krw",
    )
    assert validate_numeric_claims(
        conclusion="세액공제액은 825,000원입니다.",
        claims=[claim],
        question="실제 공제액을 계산해 주세요.",
        selected_chunks=[],
        calculations=[calculation],
    )
    assert not validate_numeric_claims(
        conclusion="세액공제액은 900,000원입니다.",
        claims=[claim.model_copy(update={"value": "900000"})],
        question="실제 공제액을 계산해 주세요.",
        selected_chunks=[],
        calculations=[calculation],
    )


def test_rejects_unknown_numeric_span_when_other_claim_is_valid() -> None:
    assert not validate_numeric_claims(
        conclusion="합산 공제한도는 900만원이고 별도 한도는 700만원입니다.",
        claims=[
            _claim(
                "9000000",
                role="tax_credit_limit",
                scope="pension_savings_plus_irp",
            )
        ],
        question="공제한도를 알려 주세요.",
        selected_chunks=[_chunk()],
        calculations=[],
    )


def test_domain_result_keeps_supported_statutory_claim_without_calculator() -> None:
    chunk = _chunk()
    result = _build_tax_payout_result(
        search_result=SearchResult(execution_status="completed", retrieved_chunks=[chunk]),
        calculations=[],
        question="합산 공제한도는 얼마인가요?",
        objective="합산 세액공제 한도 확인",
        status="determined",
        conclusion="합산 세액공제 한도는 연 900만원입니다.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[chunk.chunk_id],
        numeric_claims=[
            _claim(
                "9000000",
                role="tax_credit_limit",
                scope="pension_savings_plus_irp",
            )
        ],
    )

    assert result["decision"]["status"] == "determined"
    assert result["decision"]["conclusion"] == "합산 세액공제 한도는 연 900만원입니다."
    assert result["calculations"] == []


def test_domain_result_uses_safe_fallback_for_semantic_mismatch() -> None:
    chunk = _chunk()
    result = _build_tax_payout_result(
        search_result=SearchResult(execution_status="completed", retrieved_chunks=[chunk]),
        calculations=[],
        question="합산 공제한도는 얼마인가요?",
        objective="합산 세액공제 한도 확인",
        status="determined",
        conclusion="합산 세액공제 한도는 연 1,800만원입니다.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[chunk.chunk_id],
        numeric_claims=[
            _claim(
                "18000000",
                role="tax_credit_limit",
                scope="pension_savings_plus_irp",
                conditions=("annual", "all_financial_institutions_combined"),
            )
        ],
    )

    assert result["decision"]["status"] == "conditional"
    assert "1,800" not in result["decision"]["conclusion"]
    assert result["decision"]["missing_conditions"] == ["검증된 수치 의미와 출처"]
