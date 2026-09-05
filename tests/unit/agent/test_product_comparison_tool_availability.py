"""비교 위임 전의 Tool 선택과 위임 완료 후 그래프 종료를 검증한다."""

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import AIMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import Runnable
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

from pension_agent.agent.contracts import Permission
from pension_agent.agent.product import create_product_agent
from pension_agent.agent.product.catalog_query import PRODUCT_CATALOG_QUERY_TOOL_NAME
from pension_agent.agent.product.react import (
    CompleteProductResult,
    EnforceProductToolSequence,
    ProductComparisonToolAvailabilityMiddleware,
    _allowed_product_tools,
    _create_product_result_tool,
    _product_model_tool_name,
)
from pension_agent.agent.search import SearchChunkPayload, SearchRequest, SearchResult
from pension_agent.core import DocumentType

_LOOKUP = "lookup_product_codes"
_COMPARE = "compare_products"
_SEARCH = "search_documents"
_SUBMIT = "submit_domain_result"
_CALCULATE = "calculate_fund_standard_price"
_ALL_TOOLS = [_LOOKUP, _COMPARE, _SEARCH, _CALCULATE, _SUBMIT]
_STATE = {
    "comparison_targets": [{"target_id": "target_1"}, {"target_id": "target_2"}],
    "comparison_criteria": ["risk", "capital_protection"],
}


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
        tools=cast(
            Any,
            [
                _create_product_result_tool() if name == _SUBMIT else SimpleNamespace(name=name)
                for name in (names or _ALL_TOOLS)
            ],
        ),
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
    return [cast(str, _product_model_tool_name(tool)) for tool in request.tools]


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


@pytest.mark.parametrize("name", [_LOOKUP, _SEARCH, _SUBMIT, _CALCULATE])
def test_comparison_targets_only_allow_delegating_to_compare_tool(name: str) -> None:
    state = {
        **_STATE,
        "product_candidate_codes": ["KR5153420063", "KR5153420105"],
        "messages": [*_history(_LOOKUP), _call(name)],
    }
    update = EnforceProductToolSequence(
        lookup_tool_name=_LOOKUP, max_search_calls=2, calculation_tool_names=(_CALCULATE,)
    ).after_model(state, runtime=None)

    assert update is not None
    assert update["messages"][0].tool_calls == []


def test_completed_comparison_has_no_executable_tools_and_skips_the_model() -> None:
    state = {
        **_STATE,
        "domain_result": {"comparison_answer": "비교 Tool에서 작성한 답변"},
        "messages": _history(_LOOKUP, _COMPARE),
    }

    assert not _allowed_product_tools(
        state,
        lookup_tool_name=_LOOKUP,
        max_search_calls=2,
        calculation_tool_names=(_CALCULATE,),
    )
    assert CompleteProductResult().before_model(state, runtime=None) == {"jump_to": "end"}


def test_product_submit_schema_does_not_ask_for_comparison_cells() -> None:
    schema = convert_to_openai_tool(_create_product_result_tool())["function"]["parameters"]

    assert "comparison_cells" not in schema["properties"]
    assert "evidence_chunk_ids" in schema["properties"]


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
    bound_tool_schemas: list[dict[str, dict[str, Any]]] = Field(default_factory=list)

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable[Any, AIMessage]:
        self.bound_tool_schemas.append(
            {
                cast(str, _product_model_tool_name(tool)): convert_to_openai_tool(tool)["function"][
                    "parameters"
                ]
                for tool in tools
            }
        )
        self.bindings.append(
            (
                [cast(str, _product_model_tool_name(tool)) for tool in tools],
                kwargs.get("tool_choice"),
            )
        )
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
async def test_product_graph_binds_comparison_once_and_writer_owns_the_answer_schema() -> None:
    codes = ["KR5153420063", "KR5153420105"]
    targets = [
        {"mention_parts": ["솔로몬", duration], "resolution_status": "single", "product_code": code}
        for duration, code in zip(["단기", "장기"], codes, strict=True)
    ]
    model = BindingRecorderModel(
        responses=[
            _call(_LOOKUP, {"comparison_criteria": ["risk"]}, call_id="lookup"),
            _call(_COMPARE, {"product_codes": codes, "criteria": ["risk"]}, call_id="compare"),
            AIMessage(content="비교 Tool 실행 뒤 Product 모델 호출은 없어야 합니다."),
        ]
    )
    writer = BindingRecorderModel(
        responses=[
            _call(
                "submit_comparison_answer",
                {
                    "status": "determined",
                    "answer": "두 상품에 금리 변동에 따른 손실 가능성이 있습니다.",
                    "missing_conditions": [],
                    "warnings": [],
                    "evidence_chunk_ids": [str(UUID(int=index)) for index in (1, 2)],
                },
                call_id="comparison-answer",
            )
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
        model=model,
        catalog_planner_model=planner,
        comparison_answer_model=writer,
        search_service=ScopedSearch(),
    )

    result = await agent(
        {"question": "솔로몬 단기와 장기의 위험을 비교해 주세요.", "objective": "위험 비교"}
    )

    assert result["execution_status"] == "completed"
    assert result["comparison_answer"] == "두 상품에 금리 변동에 따른 손실 가능성이 있습니다."
    assert model.bindings[0][1] is None
    assert model.bindings[1:] == [([_LOOKUP, _COMPARE], _COMPARE)]
    assert len(writer.bindings) == 1
    assert writer.bindings[0][0] == ["submit_comparison_answer"]
    writer_schema = writer.bound_tool_schemas[0]["submit_comparison_answer"]
    assert set(writer_schema["properties"]) == {
        "answer",
        "status",
        "missing_conditions",
        "warnings",
        "evidence_chunk_ids",
    }
    assert "comparison_cells" not in model.bound_tool_schemas[0][_SUBMIT]["properties"]
    lookup_schema = model.bound_tool_schemas[0][_LOOKUP]
    assert "comparison_criteria" not in lookup_schema.get("required", [])
    lookup_criteria = next(
        branch
        for branch in lookup_schema["properties"]["comparison_criteria"]["anyOf"]
        if branch.get("type") == "array"
    )
    compare_criteria = model.bound_tool_schemas[1][_COMPARE]["properties"]["criteria"]
    for criteria_schema in (lookup_criteria, compare_criteria):
        assert criteria_schema["minItems"] == 1
        assert criteria_schema["maxItems"] == 3
        assert set(criteria_schema["items"]["enum"]) == {
            "investment_strategy",
            "risk",
            "capital_protection",
            "fees",
            "liquidity",
        }
