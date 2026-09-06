"""실제 Product 그래프에서 비교 Tool의 답변 소유권과 별도 모델 입력을 검증한다."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Never, cast
from uuid import UUID

import pytest
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable
from pydantic import Field

from pension_agent.agent.contracts import Permission, validate_domain_result
from pension_agent.agent.product import create_product_agent
from pension_agent.agent.product.catalog_query import (
    PRODUCT_CATALOG_QUERY_TOOL_NAME,
    CatalogQueryPlanError,
)
from pension_agent.agent.product.react import _product_model_tool_name
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
        self.bound_tool_names.append([cast(str, _product_model_tool_name(tool)) for tool in tools])
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
            else f"테스트 상품 {index + 1}은 국공채에 투자하며 금리 변동 위험이 있고 원금이 보장되지 않습니다."
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


def _start_calls(*, criteria: list[str] | None = None) -> list[AIMessage]:
    selected_criteria = _CRITERIA if criteria is None else criteria
    return [
        _call("lookup_product_codes", {"comparison_criteria": selected_criteria}, "lookup"),
        _call(
            "compare_products", {"product_codes": _CODES, "criteria": selected_criteria}, "compare"
        ),
    ]


_ANSWER = "세 상품 모두 금리 변동 위험이 있고 원금은 보장되지 않습니다. [근거 1]"


def _answer_call(
    *, answer: str = _ANSWER, status: str = "determined", failed_index: int | None = None
) -> AIMessage:
    return _call(
        "submit_comparison_answer",
        {
            "answer": answer,
            "status": status,
            "missing_conditions": [],
            "warnings": [],
            "evidence_chunk_ids": [
                _chunk(index).chunk_id for index in range(3) if index != failed_index
            ],
        },
        "comparison-answer",
    )


@pytest.mark.anyio
@pytest.mark.parametrize("criteria", [_CRITERIA, ["investment_strategy", *_CRITERIA]])
async def test_product_graph_finishes_with_tool_written_answer_and_cited_evidence(
    criteria: list[str],
) -> None:
    model = ComparisonFakeModel(
        responses=[
            *_start_calls(criteria=criteria),
            AIMessage(content="이 외부 모델의 재작성은 실행되면 안 됩니다."),
        ]
    )
    writer = ComparisonFakeModel(responses=[_answer_call()])
    planner = _planner()
    search = _search_results()
    agent = create_product_agent(
        model=model,
        catalog_planner_model=planner,
        comparison_answer_model=writer,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    validate_domain_result(result)
    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == "determined"
    assert result["decision"]["conclusion"] == _ANSWER
    assert result["comparison_answer"] == _ANSWER
    assert "comparison_result" not in result
    assert [chunk["chunk_id"] for chunk in result["evidence"]] == [
        _chunk(index).chunk_id for index in range(3)
    ]
    assert len(planner.received_messages) == 1
    assert len(model.received_messages) == 2
    assert len(writer.received_messages) == 1
    assert writer.bound_tool_names == [["submit_comparison_answer"]]
    assert {request.source_file_name for request, _, _ in search.calls} == set(search.results)
    assert len(search.calls) == 3
    assert all(permission == Permission.PRODUCT for _, permission, _ in search.calls)
    assert len({deadline for _, _, deadline in search.calls}) == 1
    assert all(not request.expand_neighbors for request, _, _ in search.calls)

    writer_messages = writer.received_messages[0]
    assert [type(message) for message in writer_messages] == [SystemMessage, HumanMessage]
    writer_input = str(writer_messages[1].content)
    assert _QUESTION in writer_input
    assert "상품별 위험과 원금보장 비교" in writer_input
    for code in _CODES:
        assert code in writer_input
    for criterion in criteria:
        assert criterion in writer_input
    for index in range(3):
        assert writer_input.count(_chunk(index).content) == 1
        assert writer_input.count(_chunk(index, unused=True).chunk_id) >= 1
    assert not any(
        isinstance(message, ToolMessage) and message.name == "compare_products"
        for messages in model.received_messages
        for message in messages
    )


@pytest.mark.anyio
async def test_product_graph_same_model_fallback_still_starts_fresh_comparison_context() -> None:
    model = ComparisonFakeModel(responses=[*_start_calls(), _answer_call()])
    search = _search_results()
    agent = create_product_agent(
        model=model, catalog_planner_model=_planner(), search_service=cast(SearchRunner, search)
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    assert result["execution_status"] == "completed"
    assert result["comparison_answer"] == _ANSWER
    assert len(model.received_messages) == 3
    assert any(isinstance(message, ToolMessage) for message in model.received_messages[1])
    assert [type(message) for message in model.received_messages[2]] == [
        SystemMessage,
        HumanMessage,
    ]
    assert model.bound_tool_names.count(["submit_comparison_answer"]) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "criteria",
    [
        [],
        ["investment_strategy", "risk", "capital_protection", "fees"],
        ["investment_strategy", "risk", "capital_protection", "fees", "liquidity"],
        ["unknown_criterion"],
        ["risk", 1],
        ["risk", "risk"],
        "risk",
    ],
)
async def test_product_graph_finishes_on_invalid_criteria_without_repair_call(
    criteria: Any,
) -> None:
    model = ComparisonFakeModel(
        responses=[
            _call(
                "lookup_product_codes",
                {"comparison_criteria": criteria},
                "invalid-lookup",
            ),
            *_start_calls(),
        ]
    )
    planner = _planner()
    writer = ComparisonFakeModel(responses=[_answer_call()])
    search = _search_results()
    agent = create_product_agent(
        model=model,
        catalog_planner_model=planner,
        comparison_answer_model=writer,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": _QUESTION, "objective": "세 상품 비교"})

    validate_domain_result(result)
    assert result["execution_status"] == "failed"
    assert "비교 항목" in result["error"]
    assert "1~3개" in result["error"]
    assert len(model.received_messages) == 1
    assert planner.received_messages == []
    assert writer.received_messages == []
    assert search.calls == []
    assert result["evidence"] == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "status", "message"),
    [
        (
            CatalogQueryPlanError("provider 응답 실패"),
            "failed",
            "상품 카탈로그 조회 계획을 확정하지 못했습니다.",
        ),
        (TimeoutError(), "timeout", "상품 카탈로그 조회 계획 시간이 초과됐습니다."),
        (RuntimeError("예기치 않은 내부 오류"), "failed", "Domain Agent 실행에 실패했습니다."),
    ],
)
async def test_catalog_execution_errors_are_not_mislabeled_as_invalid_comparison_criteria(
    error: Exception, status: str, message: str
) -> None:
    class FailingPlanner:
        async def plan(self, *, question: str, objective: str, deadline: float) -> Never:
            raise error

    model = ComparisonFakeModel(responses=_start_calls())
    writer = ComparisonFakeModel(responses=[_answer_call()])
    search = _search_results()
    agent = create_product_agent(
        model=model,
        catalog_query_planner=FailingPlanner(),
        comparison_answer_model=writer,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    validate_domain_result(result)
    assert result["execution_status"] == status
    assert result["error"] == message
    assert len(model.received_messages) == 1
    assert writer.received_messages == []
    assert search.calls == []


@pytest.mark.anyio
async def test_single_product_lookup_still_omits_comparison_criteria() -> None:
    model = ComparisonFakeModel(
        responses=[
            _call("lookup_product_codes", {}, "lookup"),
            _call(
                "search_documents",
                {"product_code": _CODES[0], "objective": "투자 위험과 원금보장 여부"},
                "search",
            ),
            _call(
                "submit_domain_result",
                {
                    "status": "determined",
                    "conclusion": "금리 변동 위험이 있고 원금은 보장되지 않습니다.",
                    "missing_conditions": [],
                    "warnings": [],
                    "evidence_chunk_ids": [_chunk(0).chunk_id],
                },
                "submit",
            ),
        ]
    )
    planner = ComparisonFakeModel(
        responses=[
            _call(
                PRODUCT_CATALOG_QUERY_TOOL_NAME,
                {
                    "query": {
                        "route": "resolve_product",
                        "resolution_status": "single",
                        "product_code": _CODES[0],
                    }
                },
                "catalog-plan",
            )
        ]
    )
    search = _search_results()
    agent = create_product_agent(
        model=model, catalog_planner_model=planner, search_service=cast(SearchRunner, search)
    )

    result = await agent({"question": "솔로몬 단기국공채의 위험은?", "objective": "투자 위험 확인"})

    validate_domain_result(result)
    assert result["execution_status"] == "completed"
    assert "comparison_result" not in result
    assert len(planner.received_messages) == 1
    assert len(search.calls) == 1
    assert [chunk["chunk_id"] for chunk in result["evidence"]] == [_chunk(0).chunk_id]


@pytest.mark.anyio
async def test_partial_search_preserves_writer_answer_without_cell_or_status_gate() -> None:
    model = ComparisonFakeModel(responses=_start_calls())
    writer = ComparisonFakeModel(responses=[_answer_call(failed_index=1)])
    search = _search_results(failed_index=1)
    agent = create_product_agent(
        model=model,
        catalog_planner_model=_planner(),
        comparison_answer_model=writer,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    validate_domain_result(result)
    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == "determined"
    assert result["comparison_answer"] == _ANSWER
    assert "comparison_result" not in result
    assert {chunk["chunk_id"] for chunk in result["evidence"]} == {
        _chunk(0).chunk_id,
        _chunk(2).chunk_id,
    }
    assert any("검색 서비스 오류" in warning for warning in result["warnings"])
    assert len(model.received_messages) == 2
    assert len(writer.received_messages) == 1
    assert "검색 서비스 오류" in str(writer.received_messages[0][1].content)
    assert len(search.calls) == 3


@pytest.mark.anyio
async def test_product_graph_invalid_writer_output_finishes_without_outer_rewrite_or_retry() -> (
    None
):
    model = ComparisonFakeModel(
        responses=[*_start_calls(), AIMessage(content="외부 Product가 다시 쓴 답변")]
    )
    writer = ComparisonFakeModel(responses=[AIMessage(content="제출 도구 없는 응답")])
    search = _search_results()
    agent = create_product_agent(
        model=model,
        catalog_planner_model=_planner(),
        comparison_answer_model=writer,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    validate_domain_result(result)
    assert result["execution_status"] == "failed"
    assert result["evidence"] == []
    assert "comparison_answer" not in result
    assert len(model.received_messages) == 2
    assert len(writer.received_messages) == 1
    assert len(search.calls) == 3


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
@pytest.mark.parametrize("failed_index", [None, 1])
async def test_empty_comparison_evidence_finishes_without_answer_model(
    failed_index: int | None,
) -> None:
    model = ComparisonFakeModel(
        responses=[*_start_calls(), AIMessage(content="단기 상품을 추천합니다.")]
    )
    writer = ComparisonFakeModel(responses=[_answer_call()])
    search = _search_results(empty=True, failed_index=failed_index)
    agent = create_product_agent(
        model=model,
        catalog_planner_model=_planner(),
        comparison_answer_model=writer,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    validate_domain_result(result)
    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == "undetermined"
    assert result["comparison_answer"] == result["decision"]["conclusion"]
    assert "comparison_result" not in result
    assert result["evidence"] == []
    assert "추천" not in result["decision"]["conclusion"]
    assert result["decision"]["missing_conditions"]
    assert len(model.received_messages) == 2
    assert writer.received_messages == []
    assert len(search.calls) == 3
    if failed_index is not None:
        assert any("검색 서비스 오류" in warning for warning in result["warnings"])


@pytest.mark.anyio
async def test_all_comparison_searches_failed_do_not_invoke_answer_model() -> None:
    model = ComparisonFakeModel(responses=_start_calls())
    writer = ComparisonFakeModel(responses=[_answer_call()])
    search = _search_results()
    search.results = {
        source: SearchResult(execution_status="failed", error="검색 서비스 오류")
        for source in search.results
    }
    agent = create_product_agent(
        model=model,
        catalog_planner_model=_planner(),
        comparison_answer_model=writer,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"})

    validate_domain_result(result)
    assert result["execution_status"] == "failed"
    assert result["evidence"] == []
    assert "comparison_answer" not in result
    assert len(model.received_messages) == 2
    assert writer.received_messages == []
    assert len(search.calls) == 3


@pytest.mark.anyio
async def test_comparison_parent_deadline_keeps_answer_reserve_and_skips_expired_searches() -> None:
    model = ComparisonFakeModel(responses=_start_calls())
    writer = ComparisonFakeModel(responses=[_answer_call()])
    search = _search_results()
    agent = create_product_agent(
        model=model,
        catalog_planner_model=_planner(),
        comparison_answer_model=writer,
        search_service=cast(SearchRunner, search),
    )
    deadline = asyncio.get_running_loop().time() + 10

    result = await agent(
        {"question": _QUESTION, "objective": "상품별 위험과 원금보장 비교"}, deadline=deadline
    )

    validate_domain_result(result)
    assert result["execution_status"] == "timeout"
    assert result["evidence"] == []
    assert len(model.received_messages) == 2
    assert writer.received_messages == []
    assert search.calls == []
