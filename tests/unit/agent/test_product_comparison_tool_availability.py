"""비교 전용 Tool 선택·과거 schema 보존과 실제 모델 바인딩을 검증한다."""

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import Runnable
from pydantic import Field

from pension_agent.agent.contracts import Permission
from pension_agent.agent.product import create_product_agent
from pension_agent.agent.product.catalog_query import PRODUCT_CATALOG_QUERY_TOOL_NAME
from pension_agent.agent.product.react import (
    EnforceProductToolSequence,
    ProductComparisonToolAvailabilityMiddleware,
)
from pension_agent.agent.search import SearchChunkPayload, SearchRequest, SearchResult
from pension_agent.core import DocumentType
from pension_agent.retrieval import load_product_catalog

_LOOKUP = "lookup_product_codes"
_COMPARE = "compare_products"
_SEARCH = "search_documents"
_SUBMIT = "submit_domain_result"
_CALCULATE = "calculate_fund_standard_price"
_ALL_TOOLS = [_LOOKUP, _COMPARE, _SEARCH, _CALCULATE, _SUBMIT]
_STATE = {"comparison_targets": [{"target_id": "target_1"}]}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _call(name: str, args: dict[str, Any] | None = None, *, call_id: str = "call") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args or {}, "id": call_id, "type": "tool_call"}],
    )


def _history(*names: str) -> list[Any]:
    return [
        message
        for index, name in enumerate(names)
        for message in (
            _call(name, call_id=f"call-{index}"),
            ToolMessage(content="도구 결과", name=name, tool_call_id=f"call-{index}"),
        )
    ]


async def _captured(
    state: dict[str, Any],
    *,
    names: list[str] | None = None,
    history: list[Any] | None = None,
) -> tuple[ModelRequest[Any], ModelRequest[Any]]:
    request = ModelRequest(
        model=FakeMessagesListChatModel(responses=[]),
        messages=history or [],
        tools=cast(Any, [SimpleNamespace(name=name) for name in (names or _ALL_TOOLS)]),
        state=cast(Any, state),
        tool_choice="auto",
    )
    received: list[ModelRequest[Any]] = []

    async def handler(overridden: ModelRequest[Any]) -> ModelResponse[Any]:
        received.append(overridden)
        return ModelResponse(result=[])

    await ProductComparisonToolAvailabilityMiddleware(
        lookup_tool_name=_LOOKUP, max_search_calls=2
    ).awrap_model_call(request, handler)
    return request, received[0]


def _names(request: ModelRequest[Any]) -> list[str]:
    return [cast(str, tool.name) for tool in request.tools]


@pytest.mark.anyio
async def test_comparison_before_search_forces_compare_and_preserves_lookup_schema() -> None:
    original, received = await _captured(_STATE, history=_history(_LOOKUP))

    assert received.tool_choice == _COMPARE
    assert _names(received) == [_LOOKUP, _COMPARE]
    assert _names(original) == _ALL_TOOLS
    assert original.tool_choice == "auto"


def test_comparison_rejects_uncontracted_search_parameters() -> None:
    codes = ["KR5153420063", "KR5153420105"]
    criteria = ["risk"]
    call = _call(_COMPARE, {"product_codes": codes, "criteria": criteria, "timeout": 120})
    state = {
        **_STATE,
        "product_candidate_codes": codes,
        "comparison_criteria": criteria,
        "messages": [*_history(_LOOKUP), call],
    }
    update = EnforceProductToolSequence(
        lookup_tool_name=_LOOKUP, max_search_calls=2, calculation_tool_names=()
    ).after_model(state, runtime=None)
    assert update is not None
    assert update["messages"][0].tool_calls == []


@pytest.mark.anyio
async def test_comparison_after_search_uses_auto_and_keeps_history_schemas() -> None:
    _, received = await _captured(
        {**_STATE, "comparison_evidence": object()}, history=_history(_LOOKUP, _COMPARE)
    )

    assert received.tool_choice is None
    assert _names(received) == [_LOOKUP, _COMPARE, _SEARCH, _SUBMIT]


@pytest.mark.anyio
async def test_comparison_keeps_search_history_but_enforces_search_limit() -> None:
    history = _history(_LOOKUP, _COMPARE, _SEARCH, _SEARCH)
    state = {**_STATE, "comparison_evidence": object(), "messages": history}
    _, received = await _captured(state, history=history)

    assert received.tool_choice == _SUBMIT
    assert _names(received) == [_LOOKUP, _COMPARE, _SEARCH, _SUBMIT]
    invalid_search = _call(_SEARCH, {"product_code": "KR5153420063"})
    update = EnforceProductToolSequence(
        lookup_tool_name=_LOOKUP, max_search_calls=2, calculation_tool_names=(_CALCULATE,)
    ).after_model({**state, "messages": [*history, invalid_search]}, runtime=None)
    assert update is not None
    assert update["messages"][0].tool_calls == []


@pytest.mark.anyio
async def test_comparison_after_free_text_forces_named_submit_and_keeps_history() -> None:
    history = [
        *_history(_LOOKUP, _COMPARE),
        AIMessage(content="제출 도구 없이 작성한 자유 형식 답변"),
        HumanMessage(content="최종 제출 도구로 제출하세요."),
    ]
    _, received = await _captured({**_STATE, "comparison_evidence": object()}, history=history)

    assert received.tool_choice == _SUBMIT
    assert _names(received) == [_LOOKUP, _COMPARE, _SEARCH, _SUBMIT]


@pytest.mark.anyio
async def test_comparison_rejected_historical_tool_call_forces_named_submit() -> None:
    state = {**_STATE, "comparison_evidence": object()}
    history = _history(_LOOKUP, _COMPARE)
    repeated_lookup = _call(_LOOKUP)
    update = EnforceProductToolSequence(
        lookup_tool_name=_LOOKUP, max_search_calls=2, calculation_tool_names=(_CALCULATE,)
    ).after_model({**state, "messages": [*history, repeated_lookup]}, runtime=None)
    assert update is not None
    _, received = await _captured(
        state,
        history=[
            *history,
            *update["messages"],
            HumanMessage(content="허용된 제출 도구를 사용하세요."),
        ],
    )

    assert received.tool_choice == _SUBMIT


@pytest.mark.anyio
async def test_comparison_preserves_historical_tool_schema_from_ai_message_alone() -> None:
    _, received = await _captured(
        {**_STATE, "comparison_evidence": object()},
        history=[_call(_LOOKUP), _call(_COMPARE), _call(_CALCULATE)],
    )

    assert _names(received) == _ALL_TOOLS


@pytest.mark.anyio
@pytest.mark.parametrize("state", [{}, {"product_candidate_codes": ["KR5153420063"]}])
async def test_single_product_model_request_is_not_modified(state: dict[str, Any]) -> None:
    original, received = await _captured(state, history=_history(_LOOKUP))

    assert received is original
    assert received.tool_choice == "auto"
    assert _names(received) == _ALL_TOOLS


@pytest.mark.anyio
@pytest.mark.parametrize(
    "names",
    [
        [_COMPARE, _SEARCH, _SUBMIT],
        [_LOOKUP, _SEARCH, _SUBMIT],
        [_LOOKUP, _COMPARE, _COMPARE, _SEARCH, _SUBMIT],
    ],
)
async def test_comparison_rejects_missing_or_duplicate_required_schema(names: list[str]) -> None:
    with pytest.raises(RuntimeError, match="비교 상태별 Tool 구성"):
        await _captured(_STATE, names=names, history=_history(_LOOKUP))


class BindingRecorderModel(FakeMessagesListChatModel):
    """실제 그래프가 모델에 전달한 Tool 선택과 schema 이름을 기록한다."""

    bindings: list[tuple[list[str], Any]] = Field(default_factory=list)

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable[Any, AIMessage]:
        self.bindings.append(([tool.name for tool in tools], kwargs.get("tool_choice")))
        return self


class ScopedSearch:
    async def search(
        self,
        request: SearchRequest,
        *,
        permission: Permission,
        deadline: float | None = None,
    ) -> SearchResult:
        assert permission == Permission.PRODUCT
        assert deadline is not None and request.source_file_name is not None
        code = request.source_file_name.removeprefix("R2_").removesuffix(".pdf")
        chunk_id = str(UUID(int=1 if code == "KR5153420063" else 2))
        return SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                SearchChunkPayload(
                    chunk_id=chunk_id,
                    source_file_name=request.source_file_name,
                    document_type=DocumentType.FUND_PROSPECTUS,
                    chunk_index=0,
                    title="투자 위험",
                    locator="1페이지",
                    content="테스트 문서에는 금리 변동에 따른 손실 가능성이 명시되어 있습니다.",
                )
            ],
        )


@pytest.mark.anyio
@pytest.mark.parametrize("free_response", [False, True])
async def test_product_graph_uses_supported_choices_and_recovers_free_text(
    free_response: bool,
) -> None:
    codes = ["KR5153420063", "KR5153420105"]
    targets = [
        {"mention_parts": ["솔로몬", duration], "resolution_status": "single", "product_code": code}
        for duration, code in zip(["단기", "장기"], codes, strict=True)
    ]
    cells = [
        {
            "target_id": f"target_{index}",
            "criterion": "risk",
            "status": "supported",
            "finding": "금리 변동에 따른 손실 가능성이 있습니다.",
            "evidence_refs": [{"product_code": code, "chunk_id": str(UUID(int=index))}],
            "limitations": [],
        }
        for index, code in enumerate(codes, start=1)
    ]
    model = BindingRecorderModel(
        responses=[
            _call(_LOOKUP, {"comparison_criteria": ["risk"]}, call_id="lookup"),
            _call(_COMPARE, {"product_codes": codes, "criteria": ["risk"]}, call_id="compare"),
            *([AIMessage(content="두 상품에는 금리 위험이 있습니다.")] if free_response else []),
            _call(
                _SUBMIT,
                {
                    "status": "determined",
                    "conclusion": "두 상품에 금리 변동에 따른 손실 가능성이 있습니다.",
                    "missing_conditions": [],
                    "warnings": [],
                    "evidence_chunk_ids": [],
                    "comparison_cells": cells,
                },
                call_id="submit",
            ),
        ]
    )
    planner = BindingRecorderModel(
        responses=[
            _call(
                PRODUCT_CATALOG_QUERY_TOOL_NAME,
                {"query": {"route": "resolve_products", "targets": targets}},
            )
        ]
    )
    agent = create_product_agent(
        model=model, catalog_planner_model=planner, search_service=ScopedSearch()
    )

    result = await agent(
        {"question": "솔로몬 단기와 장기의 위험을 비교해 주세요.", "objective": "위험 비교"}
    )

    assert result["execution_status"] == "completed"
    assert result["comparison_result"]["coverage"] == "complete"
    assert result["comparison_result"]["catalog_version"] == load_product_catalog().version
    assert model.bindings[0][1] is None
    assert model.bindings[1:] == [
        ([_LOOKUP, _COMPARE], _COMPARE),
        ([_LOOKUP, _COMPARE, _SEARCH, _SUBMIT], None),
        *([([_LOOKUP, _COMPARE, _SEARCH, _SUBMIT], _SUBMIT)] if free_response else []),
    ]
