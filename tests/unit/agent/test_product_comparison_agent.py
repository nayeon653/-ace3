"""실제 Product 그래프에서 비교 Tool의 답변 소유권과 별도 모델 입력을 검증한다."""

import asyncio
import json
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
from pension_agent.agent.execution import ExecutionContext
from pension_agent.agent.product import create_product_agent
from pension_agent.agent.product.catalog_query import (
    PRODUCT_CATALOG_QUERY_TOOL_NAME,
    CatalogQueryPlanError,
    HCXProductCatalogQueryPlanner,
)
from pension_agent.agent.product.react import ProductReactAgent, _product_model_tool_name
from pension_agent.agent.search import SearchChunkPayload, SearchRequest, SearchResult, SearchRunner
from pension_agent.core import DocumentType
from pension_agent.retrieval import load_product_catalog

_QUESTION = "솔로몬 국공채 단기와 중장기, 장기 상품의 투자위험과 원금보장 여부를 비교해 주세요."
_CODES = ["KR5153420063", "KR5153420079", "KR5153420105"]
_COMPARISON_QUERY = "투자위험과 원금보장 여부를 비교해 주세요."


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


def _start_calls(*, comparison_query: str = _COMPARISON_QUERY) -> list[AIMessage]:
    return [
        _call("lookup_product_codes", {}, "lookup"),
        _call(
            "compare_products",
            {"product_codes": _CODES, "comparison_query": comparison_query},
            "compare",
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
@pytest.mark.parametrize(
    "comparison_query",
    [_COMPARISON_QUERY, "벤치마크, 환헤지 방식, 분배 주기와 클래스별 가입 자격을 비교해 주세요."],
)
async def test_product_graph_finishes_with_tool_written_answer_and_cited_evidence(
    comparison_query: str,
) -> None:
    model = ComparisonFakeModel(
        responses=[
            *_start_calls(comparison_query=comparison_query),
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
    assert json.loads(writer_input)["comparison_query"] == comparison_query
    assert all(request.objective == comparison_query for request, _, _ in search.calls)
    for index in range(3):
        assert writer_input.count(_chunk(index).content) == 1
        assert writer_input.count(_chunk(index, unused=True).chunk_id) >= 1
    assert not any(
        isinstance(message, ToolMessage) and message.name == "compare_products"
        for messages in model.received_messages
        for message in messages
    )


@pytest.mark.anyio
@pytest.mark.parametrize("inject_code_planner", [False, True])
async def test_product_selection_boundary_keeps_codes_for_search_and_comparison(
    inject_code_planner: bool,
) -> None:
    catalog = load_product_catalog()
    row_ids = {
        product.product_code: f"P{index:03d}"
        for index, product in enumerate(catalog.products, start=1)
    }
    targets = _targets()
    if not inject_code_planner:
        targets = [
            {
                "mention_parts": target["mention_parts"],
                "resolution_status": target["resolution_status"],
                "selected_row_id": row_ids[target["product_code"]],
            }
            for target in targets
        ]
    planner_model = _planner(targets)
    injected = (
        HCXProductCatalogQueryPlanner(model=planner_model, catalog=catalog)
        if inject_code_planner
        else None
    )
    model = ComparisonFakeModel(responses=_start_calls())
    writer = ComparisonFakeModel(responses=[_answer_call()])
    search = _search_results()
    agent = create_product_agent(
        model=model,
        catalog_planner_model=planner_model,
        catalog_query_planner=injected,
        catalog_selection_mode="row_ids",
        comparison_answer_model=writer,
        search_service=cast(SearchRunner, search),
        catalog=catalog,
    )

    result = await agent({"question": _QUESTION, "objective": "상품 비교"})

    lookup = next(
        message
        for message in model.received_messages[1]
        if isinstance(message, ToolMessage) and message.name == "lookup_product_codes"
    )
    payload = json.loads(str(lookup.content))
    writer_payload = json.loads(str(writer.received_messages[0][1].content))
    expected_products = catalog.select_products(_CODES)
    assert payload["product_codes"] == _CODES
    assert [target["official_name"] for target in payload["targets"]] == [
        product.official_name for product in expected_products
    ]
    assert writer_payload["targets"] == payload["targets"]
    assert "selected_row_id" not in str(lookup.content)
    assert {request.source_file_name for request, _, _ in search.calls} == {
        catalog.resolve_source_file_name(code) for code in _CODES
    }
    assert result["execution_status"] == "completed"
    assert result["comparison_answer"] == _ANSWER
    assert len(planner_model.received_messages) == 1
    assert planner_model.bound_tool_names == [[PRODUCT_CATALOG_QUERY_TOOL_NAME]]


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
@pytest.mark.parametrize("comparison_query", ["", "   ", 7, ["위험"]])
async def test_invalid_comparison_query_finishes_without_search_or_repair(
    comparison_query: Any,
) -> None:
    model = ComparisonFakeModel(
        responses=[
            _start_calls()[0],
            _call(
                "compare_products",
                {"product_codes": _CODES, "comparison_query": comparison_query},
                "invalid-compare",
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
    assert "상품 비교" in result["error"]
    assert len(model.received_messages) == 2
    assert len(planner.received_messages) == 1
    assert writer.received_messages == []
    assert search.calls == []
    assert result["evidence"] == []


@pytest.mark.anyio
@pytest.mark.parametrize("retry_hint", [7, ""])
async def test_single_lookup_invalid_retry_hint_finishes_and_keeps_raw_tool_error(
    retry_hint: Any,
) -> None:
    model = ComparisonFakeModel(
        responses=[
            _call("lookup_product_codes", {"retry_hint": retry_hint}, "invalid-hint"),
            _call("lookup_product_codes", {}, "unused-retry"),
        ]
    )
    planner = _planner()
    search = _search_results()
    agent = create_product_agent(
        model=model, catalog_planner_model=planner, search_service=cast(SearchRunner, search)
    )
    implementation = agent.implementation
    assert isinstance(implementation, ProductReactAgent)

    state = await implementation.graph.ainvoke(
        {
            "question": "솔로몬 단기국공채의 위험은?",
            "objective": "투자 위험 확인",
            "messages": [HumanMessage(content="솔로몬 단기국공채의 위험은?")],
            "calculations": [],
        },
        context=ExecutionContext(deadline=asyncio.get_running_loop().time() + 30),
    )

    result = state["domain_result"]
    validate_domain_result(result)
    assert result["execution_status"] == "failed"
    assert "조회 입력이 올바르지 않습니다" in result["error"]
    assert "retry_hint" not in result["error"]
    assert len(model.received_messages) == 1
    assert planner.received_messages == []
    assert search.calls == []
    assert not state.get("product_catalog_retry_count")
    feedback = next(
        message
        for message in state["messages"]
        if isinstance(message, ToolMessage) and message.tool_call_id == "invalid-hint"
    )
    assert feedback.status == "error"
    assert "retry_hint" in str(feedback.content)
    assert feedback.content != result["error"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "status", "message"),
    [
        (
            CatalogQueryPlanError("provider 응답 실패"),
            "failed",
            "provider 응답 실패",
        ),
        (TimeoutError(), "timeout", "상품 카탈로그 조회 계획 시간이 초과됐습니다."),
        (RuntimeError("예기치 않은 내부 오류"), "failed", "Domain Agent 실행에 실패했습니다."),
    ],
)
async def test_catalog_execution_errors_preserve_their_failure_reason(
    error: Exception, status: str, message: str
) -> None:
    class FailingPlanner:
        async def plan(
            self,
            *,
            question: str,
            objective: str,
            deadline: float,
            retry_hint: str | None = None,
        ) -> Never:
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
@pytest.mark.parametrize("invalid_code", ["KR511902511", "KR5000000000"])
async def test_catalog_code_failure_returns_to_product_for_one_explicit_retry(
    invalid_code: str,
) -> None:
    targets = _targets()
    targets[0]["product_code"] = invalid_code
    failed_query = {"route": "resolve_products", "targets": targets}
    retry_hint = f"직전 제출 코드 {invalid_code}를 전체 카탈로그에서 다시 확인하세요."
    objective = "세 상품의 위험과 원금보장 여부 비교"
    model = ComparisonFakeModel(
        responses=[
            _start_calls()[0],
            _call(
                "lookup_product_codes",
                {"retry_hint": retry_hint},
                "lookup-retry",
            ),
            _start_calls()[1],
        ]
    )
    planner = ComparisonFakeModel(
        responses=[
            _call(PRODUCT_CATALOG_QUERY_TOOL_NAME, {"query": failed_query}, "invalid-plan"),
            _planner().responses[0],
        ]
    )
    writer = ComparisonFakeModel(responses=[_answer_call()])
    search = _search_results()
    agent = create_product_agent(
        model=model,
        catalog_planner_model=planner,
        comparison_answer_model=writer,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": _QUESTION, "objective": objective})

    validate_domain_result(result)
    assert result["execution_status"] == "completed"
    assert result["comparison_answer"] == _ANSWER
    assert len(model.received_messages) == 3
    assert len(planner.received_messages) == 2
    assert len(writer.received_messages) == 1
    assert len(search.calls) == 3
    feedback = model.received_messages[1][-1]
    assert isinstance(feedback, ToolMessage)
    assert feedback.name == "lookup_product_codes"
    assert feedback.status == "error"
    feedback_payload = json.loads(str(feedback.content))
    assert feedback_payload["execution_status"] == "failed"
    assert feedback_payload["retryable"] is True
    assert feedback_payload["submitted_query"] == failed_query
    assert "카탈로그" in feedback_payload["error"]
    assert [type(message) for message in planner.received_messages[0]] == [
        SystemMessage,
        HumanMessage,
    ]
    assert [type(message) for message in planner.received_messages[1]] == [
        SystemMessage,
        HumanMessage,
    ]
    assert json.loads(str(planner.received_messages[0][1].content)) == {
        "question": _QUESTION,
        "objective": objective,
    }
    assert json.loads(str(planner.received_messages[1][1].content)) == {
        "question": _QUESTION,
        "objective": objective,
        "retry_hint": retry_hint,
    }
    lookup_results = [
        message
        for message in model.received_messages[2]
        if isinstance(message, ToolMessage) and message.name == "lookup_product_codes"
    ]
    assert len(lookup_results) == 2
    assert json.loads(str(lookup_results[1].content))["product_codes"] == _CODES
    assert {request.source_file_name for request, _, _ in search.calls} == set(search.results)


@pytest.mark.anyio
async def test_second_catalog_code_failure_finishes_without_third_lookup_or_search() -> None:
    targets = _targets()
    targets[0]["product_code"] = "KR511902511"
    failed_query = {"route": "resolve_products", "targets": targets}
    model = ComparisonFakeModel(
        responses=[
            _start_calls()[0],
            _call(
                "lookup_product_codes",
                {
                    "retry_hint": "직전 제출 코드가 카탈로그에 없으므로 다시 확인하세요.",
                },
                "lookup-retry",
            ),
            *_start_calls(),
        ]
    )
    planner = ComparisonFakeModel(
        responses=[
            _call(PRODUCT_CATALOG_QUERY_TOOL_NAME, {"query": failed_query}, "first-plan"),
            _call(PRODUCT_CATALOG_QUERY_TOOL_NAME, {"query": failed_query}, "second-plan"),
            _planner().responses[0],
        ]
    )
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
    assert "카탈로그" in result["error"]
    assert len(model.received_messages) == 2
    assert len(planner.received_messages) == 2
    assert writer.received_messages == []
    assert search.calls == []
    assert result["evidence"] == []
    assert "comparison_answer" not in result


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        AIMessage(content="구조화 조회 계획이 없는 응답입니다."),
        _call(
            PRODUCT_CATALOG_QUERY_TOOL_NAME,
            {"query": {"route": "resolve_products", "targets": "잘못된 자료형"}},
            "malformed-plan",
        ),
    ],
)
async def test_catalog_response_format_failure_finishes_without_product_retry(
    response: AIMessage,
) -> None:
    model = ComparisonFakeModel(responses=_start_calls())
    planner = ComparisonFakeModel(responses=[response, _planner().responses[0]])
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
    assert "응답 형식" in result["error"]
    assert len(model.received_messages) == 1
    assert len(planner.received_messages) == 1
    assert writer.received_messages == []
    assert search.calls == []


@pytest.mark.anyio
async def test_existing_catalog_codes_are_searched_without_product_name_reinterpretation() -> None:
    targets = _targets()
    targets[0]["product_code"], targets[1]["product_code"] = _CODES[1], _CODES[0]
    selected_codes = [_CODES[1], _CODES[0], _CODES[2]]
    model = ComparisonFakeModel(
        responses=[
            _start_calls()[0],
            _call(
                "compare_products",
                {"product_codes": selected_codes, "comparison_query": _COMPARISON_QUERY},
                "compare",
            ),
        ]
    )
    planner = _planner(targets)
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
    assert result["execution_status"] == "completed"
    assert result["comparison_answer"] == _ANSWER
    assert len(model.received_messages) == 2
    assert len(planner.received_messages) == 1
    assert len(search.calls) == 3
    writer_input = json.loads(str(writer.received_messages[0][1].content))
    assert [target["product_code"] for target in writer_input["targets"]] == selected_codes
    assert writer_input["targets"][0]["mention_parts"] == ["솔로몬", "국공채", "단기"]
    assert (
        writer_input["targets"][0]["official_name"]
        == load_product_catalog().select_products([_CODES[1]])[0].official_name
    )
    assert {request.source_file_name for request, _, _ in search.calls} == set(search.results)


@pytest.mark.anyio
async def test_single_product_lookup_keeps_the_single_product_path() -> None:
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
    assert "comparison_result" not in result
    for target in targets:
        label = (
            load_product_catalog().select_products([target["product_code"]])[0].official_name
            if target["resolution_status"] == "single"
            else " ".join(target["mention_parts"])
        )
        assert label in result["comparison_answer"]
    assert "|" not in result["comparison_answer"]
    assert result["evidence"] == []
    assert len(model.received_messages) == 1
    assert search.calls == []
    assert "2개 이상 식별하지 못해" in result["comparison_answer"]


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
