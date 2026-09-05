"""실제 Product 그래프에서 복수 식별·검색·비교 제출과 실패 복구를 검증한다."""

import asyncio
import json
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, cast
from uuid import UUID

import pytest
from langchain.messages import AIMessage, ToolMessage
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable
from pydantic import Field

from pension_agent.agent.contracts import Permission, validate_domain_result
from pension_agent.agent.product import create_product_agent
from pension_agent.agent.product.catalog_query import PRODUCT_CATALOG_QUERY_TOOL_NAME
from pension_agent.agent.search import SearchChunkPayload, SearchRequest, SearchResult, SearchRunner
from pension_agent.core import DocumentType
from pension_agent.retrieval import load_product_catalog

_QUESTION = "솔로몬 국공채 단기와 중장기, 장기 상품의 투자위험과 원금보장 여부를 비교해 주세요."
_CODES = ["KR5153420063", "KR5153420079", "KR5153420105"]
_CRITERIA = ["risk", "capital_protection"]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class ComparisonFakeModel(FakeMessagesListChatModel):
    """Tool 바인딩과 모델이 실제로 받은 도구 결과를 기록한다."""

    received_messages: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tool_names: list[list[str]] = Field(default_factory=list)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.received_messages.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable[Any, AIMessage]:
        del kwargs
        self.bound_tool_names.append([tool.name for tool in tools])
        return self


@dataclass
class ProductScopedSearch:
    """병렬 호출 순서에 의존하지 않고 문서별 검색 결과를 제공한다."""

    results: dict[str, SearchResult]
    calls: list[tuple[SearchRequest, Permission, float]] = field(default_factory=list)

    async def search(
        self,
        request: SearchRequest,
        *,
        permission: Permission,
        deadline: float | None = None,
    ) -> SearchResult:
        assert deadline is not None and deadline > asyncio.get_running_loop().time()
        assert request.source_file_name is not None
        self.calls.append((request, permission, deadline))
        return self.results[request.source_file_name]


def _call(name: str, args: dict[str, Any], call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def _chunk(index: int, *, unused: bool = False) -> SearchChunkPayload:
    return SearchChunkPayload(
        chunk_id=str(UUID(int=index + (100 if unused else 1))),
        source_file_name=load_product_catalog().resolve_source_file_name(_CODES[index]),
        document_type=DocumentType.FUND_PROSPECTUS,
        chunk_index=1 if unused else 0,
        title="운용사 주소" if unused else "투자 위험 및 원금 손실",
        locator="2페이지" if unused else "1페이지",
        content=(
            "운용사의 주소입니다."
            if unused
            else f"테스트 상품 {index + 1}은 금리 변동 위험이 있고 원금이 보장되지 않습니다."
        ),
    )


def _search_results(*, failed_index: int | None = None, empty: bool = False) -> ProductScopedSearch:
    return ProductScopedSearch(
        {
            load_product_catalog().resolve_source_file_name(code): (
                SearchResult(execution_status="failed", error="이 상품의 검색 서비스 오류")
                if index == failed_index
                else SearchResult(
                    execution_status="completed",
                    retrieved_chunks=[] if empty else [_chunk(index), _chunk(index, unused=True)],
                )
            )
            for index, code in enumerate(_CODES)
        }
    )


def _targets() -> list[dict[str, Any]]:
    return [
        {
            "mention_parts": ["솔로몬", "국공채", duration],
            "resolution_status": "single",
            "product_code": code,
        }
        for duration, code in zip(["단기", "중장기", "장기"], _CODES, strict=True)
    ]


def _planner(targets: list[dict[str, Any]] | None = None) -> ComparisonFakeModel:
    return ComparisonFakeModel(
        responses=[
            _call(
                PRODUCT_CATALOG_QUERY_TOOL_NAME,
                {"query": {"route": "resolve_products", "targets": targets or _targets()}},
                "catalog-plan",
            )
        ]
    )


def _start_calls() -> list[AIMessage]:
    return [
        _call("lookup_product_codes", {"comparison_criteria": _CRITERIA}, "lookup"),
        _call("compare_products", {"product_codes": _CODES, "criteria": _CRITERIA}, "compare"),
    ]


def _cells(*, failed_index: int | None = None) -> list[dict[str, Any]]:
    return [
        {
            "target_id": f"target_{index + 1}",
            "criterion": criterion,
            "status": "not_verified" if index == failed_index else "supported",
            "finding": (
                "검색 실패로 이 상품의 해당 항목을 확인하지 못했습니다."
                if index == failed_index
                else "금리 변동 위험이 있습니다."
                if criterion == "risk"
                else "원금이 보장되지 않습니다."
            ),
            "evidence_refs": (
                []
                if index == failed_index
                else [{"product_code": code, "chunk_id": _chunk(index).chunk_id}]
            ),
            "limitations": ["해당 상품의 문서 검색 실패"] if index == failed_index else [],
        }
        for index, code in enumerate(_CODES)
        for criterion in _CRITERIA
    ]


def _submit(cells: list[dict[str, Any]], *, call_id: str = "submit") -> AIMessage:
    return _call(
        "submit_domain_result",
        {
            "status": "determined",
            "conclusion": "확인된 상품에는 금리 변동 위험과 원금 손실 가능성이 있습니다.",
            "missing_conditions": [],
            "warnings": [],
            "evidence_chunk_ids": [],
            "comparison_cells": cells,
        },
        call_id,
    )


def _tool_results(model: ComparisonFakeModel, name: str) -> list[dict[str, Any]]:
    unique_messages = {
        message.tool_call_id: message
        for messages in model.received_messages
        for message in messages
        if isinstance(message, ToolMessage) and message.name == name
    }
    return [json.loads(str(message.content)) for message in unique_messages.values()]


@pytest.mark.anyio
async def test_product_graph_compares_three_products_and_keeps_only_cited_evidence() -> None:
    model = ComparisonFakeModel(responses=[*_start_calls(), _submit(_cells())])
    planner = _planner()
    search = _search_results()
    agent = create_product_agent(
        model=model, catalog_planner_model=planner, search_service=cast(SearchRunner, search)
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    validate_domain_result(result)
    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == "determined"
    comparison = result["comparison_result"]
    assert comparison["coverage"] == "complete"
    assert comparison["criteria"] == _CRITERIA
    assert [target["product_code"] for target in comparison["targets"]] == _CODES
    assert comparison["cells"] == _cells()
    assert [chunk["chunk_id"] for chunk in result["evidence"]] == [
        _chunk(index).chunk_id for index in range(3)
    ]
    assert len(planner.received_messages) == 1
    assert len(model.received_messages) == 3
    assert "compare_products" in {name for names in model.bound_tool_names for name in names}
    assert {request.source_file_name for request, _, _ in search.calls} == set(search.results)
    assert len(search.calls) == 3
    assert all(permission == Permission.PRODUCT for _, permission, _ in search.calls)
    assert len({deadline for _, _, deadline in search.calls}) == 1
    collected = _tool_results(model, "compare_products")[0]
    assert collected["retrieval_coverage"] == "all_products"
    assert len(collected["products"]) == 3
    assert all(
        "retrieved_chunks" not in attempt
        for product in collected["products"]
        for attempt in product["attempts"]
    )
    assert "submit_domain_result" in collected["next_step"]


@pytest.mark.anyio
async def test_product_graph_partial_search_failure_forces_conditional_result() -> None:
    model = ComparisonFakeModel(responses=[*_start_calls(), _submit(_cells(failed_index=1))])
    search = _search_results(failed_index=1)
    agent = create_product_agent(
        model=model, catalog_planner_model=_planner(), search_service=cast(SearchRunner, search)
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    validate_domain_result(result)
    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == "conditional"
    assert result["comparison_result"]["coverage"] == "partial"
    assert len(result["comparison_result"]["targets"]) == 3
    assert len(result["comparison_result"]["cells"]) == 6
    assert {chunk["chunk_id"] for chunk in result["evidence"]} == {
        _chunk(0).chunk_id,
        _chunk(2).chunk_id,
    }
    assert any("검색 서비스 오류" in warning for warning in result["warnings"])
    assert result["decision"]["missing_conditions"]
    collected = _tool_results(model, "compare_products")[0]
    assert collected["execution_status"] == "completed"
    assert collected["retrieval_coverage"] == "some_products"
    assert collected["products"][1]["attempts"][0]["execution_status"] == "failed"
    assert collected["products"][1]["evidence"] == []


@pytest.mark.anyio
@pytest.mark.parametrize("wrong_attribution", ["target_product", "chunk_product"])
async def test_product_graph_rejects_cross_product_reference_then_accepts_corrected_submission(
    wrong_attribution: str,
) -> None:
    invalid_cells = deepcopy(_cells())
    invalid_cells[0]["evidence_refs"] = [
        {
            "product_code": _CODES[1] if wrong_attribution == "target_product" else _CODES[0],
            "chunk_id": _chunk(1).chunk_id,
        }
    ]
    model = ComparisonFakeModel(
        responses=[
            *_start_calls(),
            _submit(invalid_cells, call_id="wrong-submit"),
            _submit(_cells(), call_id="correct-submit"),
        ]
    )
    search = _search_results()
    agent = create_product_agent(
        model=model, catalog_planner_model=_planner(), search_service=cast(SearchRunner, search)
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    validate_domain_result(result)
    assert result["execution_status"] == "completed"
    assert result["comparison_result"]["coverage"] == "complete"
    assert result["comparison_result"]["cells"] == _cells()
    assert len(model.received_messages) == 4
    assert len(search.calls) == 3
    errors = _tool_results(model, "submit_domain_result")
    assert len(errors) == 1
    assert "상품 비교 제출 검증 실패" in errors[0]["error"]


@pytest.mark.anyio
@pytest.mark.parametrize("resolved_count", [0, 1])
async def test_product_graph_preserves_all_unresolved_targets_without_search(
    resolved_count: int,
) -> None:
    targets = [
        (
            {
                "mention_parts": ["솔로몬", "단기"],
                "resolution_status": "single",
                "product_code": _CODES[0],
            }
            if resolved_count
            else {"mention_parts": ["솔로몬", "단기"], "resolution_status": "ambiguous"}
        ),
        {"mention_parts": ["새봄"], "resolution_status": "not_found"},
        {"mention_parts": ["솔로몬", "국공채"], "resolution_status": "ambiguous"},
    ]
    model = ComparisonFakeModel(
        responses=[
            _start_calls()[0],
            AIMessage(content="이 문장은 실행되거나 최종 답변에 포함되면 안 됩니다."),
        ]
    )
    search = _search_results()
    agent = create_product_agent(
        model=model,
        catalog_planner_model=_planner(targets),
        search_service=cast(SearchRunner, search),
    )

    result = await agent(
        {"question": "솔로몬 단기, 새봄, 솔로몬 국공채 비교", "objective": "세 대상 위험 비교"}
    )

    validate_domain_result(result)
    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == "undetermined"
    assert result["comparison_result"]["coverage"] == "none"
    assert [target["mention_parts"] for target in result["comparison_result"]["targets"]] == [
        target["mention_parts"] for target in targets
    ]
    assert len(result["comparison_result"]["cells"]) == 6
    assert all(cell["status"] == "not_verified" for cell in result["comparison_result"]["cells"])
    assert result["evidence"] == []
    assert len(model.received_messages) == 1
    assert search.calls == []
    assert "2개 이상 식별하지 못해" in result["decision"]["missing_conditions"][0]


@pytest.mark.anyio
async def test_product_graph_empty_search_stops_unverified_recommendation() -> None:
    model = ComparisonFakeModel(
        responses=[*_start_calls(), AIMessage(content="안정적이므로 단기 상품을 추천합니다.")]
    )
    search = _search_results(empty=True)
    agent = create_product_agent(
        model=model, catalog_planner_model=_planner(), search_service=cast(SearchRunner, search)
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    validate_domain_result(result)
    assert result["decision"]["status"] == "undetermined"
    assert result["comparison_result"]["coverage"] == "none"
    assert result["evidence"] == []
    assert "추천" not in result["decision"]["conclusion"]
    assert len(model.received_messages) == 2
    assert len(search.calls) == 3


@pytest.mark.anyio
async def test_product_graph_forwards_neighbor_expansion_in_comparison_supplement() -> None:
    model = ComparisonFakeModel(
        responses=[
            *_start_calls(),
            _call(
                "search_documents",
                {
                    "product_code": _CODES[0],
                    "objective": "위험등급 앞뒤 문맥 확인",
                    "expand_neighbors": True,
                },
                "supplement",
            ),
            _submit(_cells()),
        ]
    )
    search = _search_results()
    agent = create_product_agent(
        model=model, catalog_planner_model=_planner(), search_service=cast(SearchRunner, search)
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    validate_domain_result(result)
    assert result["comparison_result"]["coverage"] == "complete"
    assert len(search.calls) == 4
    assert all(not request.expand_neighbors for request, _, _ in search.calls[:3])
    request, permission, deadline = search.calls[-1]
    assert request.expand_neighbors is True
    assert request.source_file_name == load_product_catalog().resolve_source_file_name(_CODES[0])
    assert permission is Permission.PRODUCT
    assert deadline == search.calls[0][2]


@pytest.mark.anyio
async def test_product_graph_empty_success_and_search_failure_preserve_failure_limitations() -> (
    None
):
    model = ComparisonFakeModel(responses=_start_calls())
    search = _search_results(empty=True, failed_index=1)
    agent = create_product_agent(
        model=model, catalog_planner_model=_planner(), search_service=cast(SearchRunner, search)
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    validate_domain_result(result)
    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == "undetermined"
    assert result["comparison_result"]["coverage"] == "none"
    assert result["evidence"] == []
    official_name = load_product_catalog().select_products([_CODES[1]])[0].official_name
    expected_failure = f"{official_name}: 이 상품의 검색 서비스 오류"
    assert expected_failure in result["comparison_result"]["limitations"]
    assert expected_failure in result["warnings"]
    assert expected_failure in result["decision"]["missing_conditions"]
    assert len(search.calls) == 3
    assert len(model.received_messages) == 2
