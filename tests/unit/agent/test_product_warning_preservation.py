"""Product 결과가 숫자가 포함된 유효한 경고를 보존하는지 검증한다."""

from pension_agent.agent.contracts import CalculationResult
from pension_agent.agent.product.react import _build_product_result
from pension_agent.agent.search import SearchChunkPayload, SearchResult
from pension_agent.core import DocumentType


def test_product_result_keeps_numeric_warning_with_python_calculation() -> None:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    search_result = SearchResult(
        execution_status="completed",
        retrieved_chunks=[
            SearchChunkPayload(
                chunk_id=chunk_id,
                source_file_name="fund.pdf",
                document_type=DocumentType.FUND_PROSPECTUS,
                chunk_index=1,
                title="기준가격",
                locator="1페이지",
                content="기준가격 산식과 입력값",
            )
        ],
    )
    calculation: CalculationResult = {
        "calculator_id": "fund_standard_price",
        "inputs": {
            "fund_net_asset_value_krw": "1000",
            "total_units": "1000",
        },
        "input_sources": {
            "fund_net_asset_value_krw": {
                "origin": "question",
                "text": "순자산총액 1,000원",
                "chunk_id": None,
            },
            "total_units": {
                "origin": "question",
                "text": "총좌수 1,000좌",
                "chunk_id": None,
            },
        },
        "outputs": {"standard_price_per_1000_units": "1000"},
        "units": {"standard_price_per_1000_units": "KRW"},
        "warnings": [],
    }

    result = _build_product_result(
        search_result=search_result,
        calculations=[calculation],
        status="determined",
        conclusion="모델의 임시 결론",
        missing_conditions=[],
        warnings=["1,000원은 제공된 입력을 적용한 결과입니다."],
        evidence_chunk_ids=[chunk_id],
    )

    assert result["warnings"] == ["1,000원은 제공된 입력을 적용한 결과입니다."]
