"""Domain Agent용 Calculation Tool 어댑터를 검증한다."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from langgraph.types import Command

from pension_agent.agent.calculation import (
    create_fund_standard_price_tool,
    create_fund_var_risk_tool,
    create_pension_withdrawal_limit_tool,
    format_calculation_summary,
)
from pension_agent.agent.search import SearchResult


def _runtime(*, with_evidence: bool = True) -> SimpleNamespace:
    chunks = (
        [
            {
                "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_file_name": "rules.pdf",
                "document_type": "pension_reference",
                "chunk_index": 0,
                "title": "계산 규칙",
                "locator": "1쪽",
                "content": "검증된 계산 규칙",
            }
        ]
        if with_evidence
        else []
    )
    return SimpleNamespace(
        state={
            "search_result": SearchResult(
                execution_status="completed",
                retrieved_chunks=chunks,
            )
        },
        tool_call_id="call-1",
    )


@pytest.mark.anyio
async def test_pension_tool_records_rules_result_in_state() -> None:
    result = await create_pension_withdrawal_limit_tool().coroutine(
        account_valuation_krw=Decimal(10000000),
        pension_year=1,
        runtime=_runtime(),
    )

    assert isinstance(result, Command)
    calculation = result.update["calculations"][0]
    assert calculation["calculator_id"] == "pension_withdrawal_limit"
    assert calculation["outputs"]["withdrawal_limit"] == "1200000.0"


@pytest.mark.anyio
async def test_product_tools_record_only_their_calculator_results() -> None:
    standard_price = await create_fund_standard_price_tool().coroutine(
        total_assets_krw=Decimal(1000000),
        total_liabilities_krw=Decimal(100000),
        total_units=Decimal(100000),
        runtime=_runtime(),
    )
    var_risk = await create_fund_var_risk_tool().coroutine(
        daily_loss_percentile_percent=Decimal(-2),
        runtime=_runtime(),
    )

    assert isinstance(standard_price, Command)
    assert isinstance(var_risk, Command)
    assert standard_price.update["calculations"][0]["calculator_id"] == "fund_standard_price"
    assert var_risk.update["calculations"][0]["calculator_id"] == "fund_var_risk"


@pytest.mark.anyio
async def test_calculation_tool_requires_completed_search_evidence() -> None:
    result = await create_pension_withdrawal_limit_tool().coroutine(
        account_valuation_krw=Decimal(10000000),
        pension_year=1,
        runtime=_runtime(with_evidence=False),
    )

    assert isinstance(result, str)
    assert "문서 근거" in result


def test_calculation_summary_preserves_verified_values() -> None:
    summary = format_calculation_summary(
        [
            {
                "calculator_id": "fund_var_risk",
                "inputs": {"daily_loss_percentile_percent": "-2"},
                "outputs": {
                    "annualized_var_percent": "31.62277660168379331998893544",
                    "risk_grade": 2,
                    "risk_label": "높은 위험",
                },
                "units": {"annualized_var_percent": "%"},
                "warnings": [],
            }
        ]
    )

    assert "31.62277660168379331998893544 %" in summary
    assert "2등급 (높은 위험)" in summary
