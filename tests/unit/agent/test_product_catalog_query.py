"""HCX 상품 카탈로그 계획의 구조, 모델 선택 보존과 실행 오류를 확인한다."""

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, ClassVar, TypeVar

import httpx
import pytest
from langchain.messages import AIMessage
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable
from openai import OpenAIError, RateLimitError
from pydantic import Field, ValidationError

from pension_agent.agent.execution import AsyncConcurrencyLimiter, ModelConcurrencyMiddleware
from pension_agent.agent.product import (
    PRODUCT_CATALOG_QUERY_TOOL_NAME,
    AmbiguousProductQuery,
    BrowseAllCatalogQuery,
    BrowseProviderCatalogQuery,
    CatalogQueryPlanError,
    HCXProductCatalogQueryPlanner,
    NotFoundProductQuery,
    SingleProductQuery,
    UnregisteredProviderQuery,
    load_product_catalog_query_prompt,
)
from pension_agent.agent.product.catalog_query import (
    MultipleProductsQuery,
    _return_product_catalog_query,
    _return_product_catalog_row_query,
)
from pension_agent.agent.product.catalog_selection import CatalogSelectionMode
from pension_agent.retrieval import ProductCatalog, ProductCatalogError, load_product_catalog


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class BindingFakeModel(FakeMessagesListChatModel):
    """구조화 Tool binding을 기록하는 Query Planner용 Fake 모델."""

    bindings: ClassVar[list[dict[str, Any]]] = []
    received_messages: list[list[BaseMessage]] = Field(default_factory=list)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.received_messages.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def bind_tools(
        self,
        tools: Sequence[Any],
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        del tools
        self.bindings.append(kwargs)
        return self


def _query_response(query: dict[str, Any]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": PRODUCT_CATALOG_QUERY_TOOL_NAME,
                "args": {"query": query},
                "id": "query-call",
                "type": "tool_call",
            }
        ],
    )


def test_query_planner_forces_one_structured_tool() -> None:
    model = BindingFakeModel(responses=[])
    model.bindings.clear()

    HCXProductCatalogQueryPlanner(model=model, catalog=load_product_catalog())

    assert model.bindings == [{"tool_choice": PRODUCT_CATALOG_QUERY_TOOL_NAME}]


def test_query_tool_schema_requires_code_only_for_single_product() -> None:
    schema = _return_product_catalog_query.tool_call_schema.model_json_schema()
    definitions = schema["$defs"]

    assert "product_code" in definitions["SingleProductQuery"]["required"]
    assert "product_code" not in definitions["NotFoundProductQuery"]["properties"]
    assert "product_code" not in definitions["AmbiguousProductQuery"]["properties"]
    assert schema["properties"]["query"]["anyOf"] == [
        {"$ref": "#/$defs/SingleProductQuery"},
        {"$ref": "#/$defs/NotFoundProductQuery"},
        {"$ref": "#/$defs/AmbiguousProductQuery"},
        {"$ref": "#/$defs/MultipleProductsQuery"},
        {"$ref": "#/$defs/BrowseAllCatalogQuery"},
        {"$ref": "#/$defs/BrowseProviderCatalogQuery"},
        {"$ref": "#/$defs/UnregisteredProviderQuery"},
    ]
    assert "provider" not in definitions["BrowseAllCatalogQuery"]["properties"]
    assert "provider" in definitions["BrowseProviderCatalogQuery"]["required"]
    assert "provider" in definitions["UnregisteredProviderQuery"]["required"]


@pytest.mark.anyio
async def test_query_planner_normalizes_provider_for_catalog_browse() -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(
            responses=[
                _query_response(
                    {
                        "route": "browse_provider_catalog",
                        "provider": "미래에셋",
                        "return_mode": "count_and_items",
                    }
                )
            ]
        ),
        catalog=load_product_catalog(),
    )

    query = await planner.plan(
        question="미레에셋 상품은 몇 개고 어떤 것들이 있어?",
        objective="운용사 상품 개수와 목록 조회",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert query == BrowseProviderCatalogQuery(
        route="browse_provider_catalog",
        provider="미래에셋",
        return_mode="count_and_items",
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "question",
    [
        "전체 상품은 몇 개야?",
        "등록된 상품은 몇 개야?",
        "상품 카탈로그 개수를 알려줘.",
        "현재 등록 상품 목록을 보여줘.",
    ],
)
async def test_query_planner_preserves_all_catalog_browse(question: str) -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(
            responses=[
                _query_response(
                    {
                        "route": "browse_all_catalog",
                        "return_mode": "count",
                    }
                )
            ]
        ),
        catalog=load_product_catalog(),
    )

    query = await planner.plan(
        question=question,
        objective="전체 상품 개수 조회",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert query == BrowseAllCatalogQuery(
        route="browse_all_catalog",
        return_mode="count",
    )


@pytest.mark.anyio
async def test_query_planner_resolves_one_catalog_product() -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(
            responses=[
                _query_response(
                    {
                        "route": "resolve_product",
                        "resolution_status": "single",
                        "provider": "미래에셋",
                        "product_code": "kr510902511m",
                    }
                )
            ]
        ),
        catalog=load_product_catalog(),
    )

    query = await planner.plan(
        question="미레에셋 장기성장 포커스 위험은?",
        objective="특정 상품 위험 판단",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert query == SingleProductQuery(
        route="resolve_product",
        resolution_status="single",
        provider="미래에셋",
        product_code="KR510902511M",
    )


@pytest.mark.anyio
@pytest.mark.parametrize("resolution_status", ["not_found", "ambiguous"])
async def test_query_planner_preserves_safe_unresolved_status(
    resolution_status: str,
) -> None:
    route = "product_not_found" if resolution_status == "not_found" else "product_ambiguous"
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(
            responses=[
                _query_response(
                    {
                        "route": route,
                        "resolution_status": resolution_status,
                        "provider": "미래에셋",
                    }
                )
            ]
        ),
        catalog=load_product_catalog(),
    )

    query = await planner.plan(
        question="상품을 식별하기 어려운 질문",
        objective="특정 상품 식별",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    expected_type = (
        NotFoundProductQuery if resolution_status == "not_found" else AmbiguousProductQuery
    )
    expected_route = (
        "product_not_found" if resolution_status == "not_found" else "product_ambiguous"
    )
    assert query == expected_type(
        route=expected_route,
        resolution_status=resolution_status,
        provider="미래에셋",
    )


@pytest.mark.anyio
async def test_query_planner_verifies_unregistered_provider_status() -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(
            responses=[
                _query_response(
                    {
                        "route": "provider_not_found",
                        "provider": "메리츠",
                        "return_mode": "count",
                    }
                )
            ]
        ),
        catalog=load_product_catalog(),
    )

    query = await planner.plan(
        question="메리츠 상품은 몇 개가 등록돼 있어?",
        objective="운용사 상품 개수 조회",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert query == UnregisteredProviderQuery(
        route="provider_not_found",
        provider="메리츠",
        return_mode="count",
    )


@pytest.mark.anyio
async def test_query_planner_normalizes_unknown_provider_browse_to_not_found() -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(
            responses=[
                _query_response(
                    {
                        "route": "browse_provider_catalog",
                        "provider": "메리츠",
                        "return_mode": "count",
                    }
                )
            ]
        ),
        catalog=load_product_catalog(),
    )

    query = await planner.plan(
        question="메리츠 상품은 몇 개가 등록돼 있어?",
        objective="운용사 상품 개수 조회",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert query == UnregisteredProviderQuery(
        route="provider_not_found",
        provider="메리츠",
        return_mode="count",
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "query",
    [
        {
            "route": "provider_not_found",
            "provider": "미래에셋",
            "return_mode": "count",
        },
        {
            "route": "resolve_product",
            "resolution_status": "single",
            "provider": "미래에셋",
            "product_code": "KR9999999999",
        },
        {
            "route": "resolve_product",
            "resolution_status": "single",
            "provider": "하나",
            "product_code": "KR510902511M",
        },
        {
            "route": "resolve_product",
            "resolution_status": "single",
            "provider": "미래에셋",
        },
        {
            "route": "product_not_found",
            "resolution_status": "not_found",
            "product_code": "KR510902511M",
        },
        {
            "route": "product_ambiguous",
            "resolution_status": "ambiguous",
            "product_code": "KR510902511M",
        },
        {
            "route": "browse_catalog",
            "provider_status": "registered",
            "return_mode": "count",
        },
        {
            "route": "browse_provider_catalog",
            "return_mode": "count",
        },
        {
            "route": "provider_not_found",
            "return_mode": "count",
        },
        {
            "route": "browse_all_catalog",
            "provider": "미래에셋",
            "return_mode": "count",
        },
        {
            "route": "browse_provider_catalog",
            "provider": "미래에셋",
            "return_mode": "count",
            "product_codes": ["KR510902511M"],
        },
    ],
)
async def test_query_planner_rejects_unverified_or_invalid_queries(
    query: dict[str, Any],
) -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(responses=[_query_response(query)]),
        catalog=load_product_catalog(),
    )

    with pytest.raises(CatalogQueryPlanError):
        await planner.plan(
            question="상품 조회",
            objective="상품 조회",
            deadline=asyncio.get_running_loop().time() + 5,
        )


@pytest.mark.anyio
async def test_query_planner_does_not_start_after_deadline() -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(responses=[]),
        catalog=load_product_catalog(),
    )

    with pytest.raises(TimeoutError):
        await planner.plan(
            question="상품 조회",
            objective="상품 조회",
            deadline=asyncio.get_running_loop().time(),
        )


def test_query_planner_prompt_contains_the_full_catalog_only_once() -> None:
    prompt = load_product_catalog_query_prompt(load_product_catalog())

    assert prompt.count('"product_code":"KR510902511M"') == 1
    assert '"product_code":"KR518102001M"' in prompt
    assert "{{PRODUCT_CATALOG_JSON}}" not in prompt
    assert "상품 목록, 상품 개수" in prompt
    assert "resolution_status=not_found" in prompt
    assert "resolution_status=ambiguous" in prompt
    assert "browse_all_catalog" in prompt
    assert "browse_provider_catalog" in prompt
    assert "provider_not_found" in prompt


def _comparison_target(
    *mention_parts: str,
    product_code: str | None = None,
    resolution_status: str = "single",
) -> dict[str, Any]:
    target: dict[str, Any] = {
        "mention_parts": list(mention_parts),
        "resolution_status": resolution_status,
    }
    if product_code is not None:
        target["product_code"] = product_code
    return target


def _solomon_targets() -> list[dict[str, Any]]:
    return [
        _comparison_target("솔로몬", "국공채", "단기", product_code="KR5153420063"),
        _comparison_target("솔로몬", "국공채", "중장기", product_code="KR5153420079"),
        _comparison_target("솔로몬", "국공채", "장기", product_code="KR5153420105"),
    ]


async def _plan_comparison(
    targets: list[dict[str, Any]],
    *,
    question: str = "솔로몬 국공채 단기와 중장기, 장기 상품의 위험과 원금보장 여부를 비교해 주세요.",
) -> MultipleProductsQuery:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(
            responses=[_query_response({"route": "resolve_products", "targets": targets})]
        ),
        catalog=load_product_catalog(),
    )
    query = await planner.plan(
        question=question,
        objective="명시적인 상품 비교",
        deadline=asyncio.get_running_loop().time() + 5,
    )
    assert isinstance(query, MultipleProductsQuery)
    return query


@pytest.mark.anyio
async def test_query_planner_resolves_three_products_in_one_plan() -> None:
    query = await _plan_comparison(_solomon_targets())

    assert [target.product_code for target in query.targets] == [
        "KR5153420063",
        "KR5153420079",
        "KR5153420105",
    ]
    assert query.targets[0].mention_parts == ["솔로몬", "국공채", "단기"]


@pytest.mark.anyio
@pytest.mark.parametrize("selected_code", ["KR5153420022", "KR5153420079"])
async def test_planner_preserves_registered_model_selection_without_correction(
    selected_code: str,
) -> None:
    targets = _solomon_targets()
    targets[0]["product_code"] = selected_code
    model = BindingFakeModel(
        responses=[
            _query_response({"route": "resolve_products", "targets": targets}),
            _query_response({"route": "resolve_products", "targets": _solomon_targets()}),
        ]
    )
    concurrency = RecordingConcurrency()
    deadline = asyncio.get_running_loop().time() + 5

    query = await _run_recorded_planner(model, concurrency=concurrency, deadline=deadline)

    assert query.targets[0].product_code == selected_code
    assert query.targets[0].mention_parts == targets[0]["mention_parts"]
    assert len(model.received_messages) == 1
    assert len(model.received_messages[0]) == 2
    assert concurrency.deadlines == [deadline]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mention_parts",
    [["원문에 없는 상품 표현"], ["솔로몬", "국공채"], ["솔로몬", "장기"]],
)
async def test_planner_does_not_rejudge_mention_meaning_or_uniqueness(
    mention_parts: list[str],
) -> None:
    targets = _solomon_targets()
    targets[0]["mention_parts"] = mention_parts

    query = await _plan_comparison(targets)

    assert query.targets[0].mention_parts == mention_parts
    assert query.targets[0].product_code == "KR5153420063"


@pytest.mark.anyio
async def test_query_planner_preserves_unresolved_and_repeated_comparison_targets() -> None:
    targets = [
        _comparison_target("솔로몬 단기", product_code="KR5153420063"),
        _comparison_target("솔로몬 국공채", resolution_status="ambiguous"),
        _comparison_target("새봄", resolution_status="not_found"),
        _comparison_target("같은 상품", product_code="KR5153420063"),
    ]

    query = await _plan_comparison(targets)

    assert [target.resolution_status for target in query.targets] == [
        "single",
        "ambiguous",
        "not_found",
        "single",
    ]
    assert [target.product_code for target in query.targets] == [
        "KR5153420063",
        None,
        None,
        "KR5153420063",
    ]
    assert [target.mention_parts for target in query.targets] == [
        target["mention_parts"] for target in targets
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("code", ["KR9999999999", "KR511902511"])
async def test_planner_rejects_unavailable_codes_without_internal_retry(code: str) -> None:
    targets = _solomon_targets()
    targets[0]["product_code"] = code
    model = BindingFakeModel(
        responses=[_query_response({"route": "resolve_products", "targets": targets})]
    )

    with pytest.raises(CatalogQueryPlanError, match="카탈로그와 일치하지 않습니다") as raised:
        await _run_recorded_planner(model)

    assert raised.value.retryable is True
    assert raised.value.submitted_query == {"route": "resolve_products", "targets": targets}
    assert isinstance(raised.value.__cause__, ProductCatalogError)
    assert len(model.received_messages) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "targets",
    [
        _solomon_targets()[:1],
        _solomon_targets() * 2,
        [_comparison_target("단기"), _solomon_targets()[2]],
        [
            _comparison_target("단기", resolution_status="ambiguous", product_code="KR5153420063"),
            _solomon_targets()[2],
        ],
        [_comparison_target(product_code="KR5153420063"), _solomon_targets()[2]],
        [_comparison_target("단기", product_code=""), _solomon_targets()[2]],
    ],
)
async def test_planner_keeps_basic_comparison_structure_errors_terminal(
    targets: list[dict[str, Any]],
) -> None:
    model = BindingFakeModel(
        responses=[_query_response({"route": "resolve_products", "targets": targets})]
    )

    with pytest.raises(CatalogQueryPlanError, match="응답 형식") as raised:
        await _run_recorded_planner(model)

    assert raised.value.retryable is False
    assert raised.value.submitted_query is None
    assert isinstance(raised.value.__cause__, ValidationError)
    assert len(model.received_messages) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("call_count", [0, 2])
async def test_planner_requires_one_structured_response_without_regeneration(
    call_count: int,
) -> None:
    response = _query_response({"route": "resolve_products", "targets": _solomon_targets()})
    response.tool_calls *= call_count
    model = BindingFakeModel(responses=[response])

    with pytest.raises(CatalogQueryPlanError, match="응답 형식") as raised:
        await _run_recorded_planner(model)

    assert raised.value.retryable is False
    assert raised.value.submitted_query is None
    assert isinstance(raised.value.__cause__, ValueError)
    assert len(model.received_messages) == 1


_ResultT = TypeVar("_ResultT")


class RecordingConcurrency(ModelConcurrencyMiddleware):
    """공유 슬롯을 사용하는 논리적 모델 호출과 절대 마감을 기록한다."""

    def __init__(self) -> None:
        super().__init__(AsyncConcurrencyLimiter(1))
        self.deadlines: list[float | None] = []

    async def arun(
        self,
        operation: Callable[[], Awaitable[_ResultT]],
        *,
        deadline: float | None = None,
    ) -> _ResultT:
        self.deadlines.append(deadline)
        return await super().arun(operation, deadline=deadline)


async def _run_recorded_planner(
    model: BindingFakeModel,
    *,
    concurrency: ModelConcurrencyMiddleware | None = None,
    deadline: float | None = None,
) -> MultipleProductsQuery:
    planner = HCXProductCatalogQueryPlanner(
        model=model,
        catalog=load_product_catalog(),
        model_concurrency=concurrency,
    )
    query = await planner.plan(
        question="솔로몬 국공채 단기와 중장기, 장기 상품을 비교해 주세요.",
        objective="상품별 위험 비교",
        deadline=deadline or asyncio.get_running_loop().time() + 5,
    )
    assert isinstance(query, MultipleProductsQuery)
    return query


@pytest.mark.anyio
async def test_planner_retry_hint_preserves_original_request_as_separate_input() -> None:
    model = BindingFakeModel(
        responses=[_query_response({"route": "resolve_products", "targets": _solomon_targets()})]
    )
    planner = HCXProductCatalogQueryPlanner(model=model, catalog=load_product_catalog())
    request = {
        "question": "솔로몬 국공채 단기와 장기를 비교해 주세요.",
        "objective": "상품별 위험 비교",
    }
    deadline = asyncio.get_running_loop().time() + 5
    await planner.plan(**request, deadline=deadline)
    hint = "이전 선택은 카탈로그 조회를 실행할 수 없었습니다. 상품 코드를 다시 선택해 주세요."

    await planner.plan(**request, deadline=deadline, retry_hint=hint)

    assert [len(messages) for messages in model.received_messages] == [2, 2]
    assert json.loads(str(model.received_messages[0][1].content)) == request
    assert json.loads(str(model.received_messages[1][1].content)) == {
        **request,
        "retry_hint": hint,
    }


@pytest.mark.anyio
async def test_planner_single_generation_obeys_parent_deadline() -> None:
    class SlowModel(BindingFakeModel):
        async def _agenerate(self, *args: Any, **kwargs: Any) -> ChatResult:
            await asyncio.sleep(10)
            return await super()._agenerate(*args, **kwargs)

    model = SlowModel(responses=[])
    concurrency = RecordingConcurrency()
    deadline = asyncio.get_running_loop().time() + 0.02

    with pytest.raises(TimeoutError):
        await _run_recorded_planner(model, concurrency=concurrency, deadline=deadline)

    assert concurrency.deadlines == [deadline]


@pytest.mark.anyio
async def test_planner_provider_failure_keeps_its_cause_without_regeneration() -> None:
    provider_error = OpenAIError("테스트 provider 오류")

    class FailingModel(BindingFakeModel):
        attempt_count: int = 0

        async def _agenerate(self, *args: Any, **kwargs: Any) -> ChatResult:
            del args, kwargs
            self.attempt_count += 1
            raise provider_error

    model = FailingModel(responses=[])

    with pytest.raises(CatalogQueryPlanError, match="모델 호출에 실패") as raised:
        await _run_recorded_planner(model)

    assert raised.value.retryable is False
    assert raised.value.submitted_query is None
    assert raised.value.__cause__ is provider_error
    assert model.attempt_count == 1


@pytest.mark.anyio
async def test_planner_preserves_infrastructure_rate_limit_retry() -> None:
    provider_error = RateLimitError(
        "일시적인 HCX 사용량 제한",
        response=httpx.Response(
            429,
            request=httpx.Request("POST", "https://clova.invalid/chat/completions"),
            headers={"retry-after": "0"},
        ),
        body={"error": {"code": "42901"}},
    )

    class TransientModel(BindingFakeModel):
        attempt_count: int = 0

        async def _agenerate(self, *args: Any, **kwargs: Any) -> ChatResult:
            self.attempt_count += 1
            if self.attempt_count == 1:
                raise provider_error
            return await super()._agenerate(*args, **kwargs)

    targets = _solomon_targets()
    targets[0]["product_code"] = "KR5153420022"
    model = TransientModel(
        responses=[_query_response({"route": "resolve_products", "targets": targets})]
    )
    concurrency = RecordingConcurrency()
    deadline = asyncio.get_running_loop().time() + 5

    query = await _run_recorded_planner(model, concurrency=concurrency, deadline=deadline)

    assert query.targets[0].product_code == "KR5153420022"
    assert model.attempt_count == 2
    assert len(model.received_messages) == 1
    assert concurrency.deadlines == [deadline]


def test_row_selection_schema_accepts_only_selection_ids() -> None:
    schema = _return_product_catalog_row_query.tool_call_schema.model_json_schema()
    definitions = schema["$defs"]

    assert "selected_row_id" in definitions["_SelectedRowProductQuery"]["required"]
    for definition in ["_SelectedRowProductQuery", "_SelectedRowComparisonTarget"]:
        assert "product_code" not in definitions[definition]["properties"]
        assert definitions[definition]["additionalProperties"] is False


@pytest.mark.anyio
async def test_row_selection_maps_single_product_to_original_internal_contract() -> None:
    catalog = load_product_catalog()
    model = BindingFakeModel(
        responses=[
            _query_response(
                {
                    "route": "resolve_product",
                    "resolution_status": "single",
                    "selected_row_id": "P002",
                }
            )
        ]
    )
    planner = HCXProductCatalogQueryPlanner(model=model, catalog=catalog, selection_mode="row_ids")

    result = await planner.plan(
        question=catalog.products[1].product_code,
        objective="명시적인 코드의 상품 조회",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert result == SingleProductQuery(
        route="resolve_product",
        resolution_status="single",
        provider=catalog.products[1].provider,
        product_code=catalog.products[1].product_code,
    )
    assert len(model.received_messages) == 1


@pytest.mark.anyio
async def test_row_selection_keeps_mentions_unresolved_targets_and_model_choice() -> None:
    targets = [
        {
            "mention_parts": ["다른 상품 표현"],
            "resolution_status": "single",
            "selected_row_id": "P001",
        },
        {"mention_parts": ["모호한 상품"], "resolution_status": "ambiguous"},
        {"mention_parts": ["없는 상품"], "resolution_status": "not_found"},
        {"mention_parts": ["같은 상품"], "resolution_status": "single", "selected_row_id": "P001"},
    ]
    catalog = load_product_catalog()
    model = BindingFakeModel(
        responses=[_query_response({"route": "resolve_products", "targets": targets})]
    )
    planner = HCXProductCatalogQueryPlanner(model=model, catalog=catalog, selection_mode="row_ids")

    result = await planner.plan(
        question="상품 표현을 잘못 해석한 모델 선택도 그대로 보존",
        objective="비교 상품 선택",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert isinstance(result, MultipleProductsQuery)
    assert [target.mention_parts for target in result.targets] == [
        t["mention_parts"] for t in targets
    ]
    assert [target.product_code for target in result.targets] == [
        catalog.products[0].product_code,
        None,
        None,
        catalog.products[0].product_code,
    ]
    assert len(model.received_messages) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("selection_mode", ["row_codes", "row_ids"])
@pytest.mark.parametrize(
    "query",
    [
        {"route": "product_not_found", "resolution_status": "not_found"},
        {"route": "product_ambiguous", "resolution_status": "ambiguous"},
        {"route": "browse_all_catalog", "return_mode": "items"},
        {"route": "browse_provider_catalog", "provider": "미래에셋", "return_mode": "count"},
        {"route": "provider_not_found", "provider": "없는 운용사", "return_mode": "count"},
    ],
)
async def test_selection_variants_preserve_non_selection_routes(
    selection_mode: CatalogSelectionMode,
    query: dict[str, Any],
) -> None:
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(responses=[_query_response(query)]),
        catalog=load_product_catalog(),
        selection_mode=selection_mode,
    )

    result = await planner.plan(
        question="카탈로그 조회",
        objective="조회 경로 보존",
        deadline=asyncio.get_running_loop().time() + 5,
    )

    assert result.model_dump(exclude_none=True) == query


@pytest.mark.anyio
@pytest.mark.parametrize("as_comparison", [False, True])
async def test_unknown_row_selection_returns_retryable_original_submission(
    as_comparison: bool,
) -> None:
    query: dict[str, Any] = {
        "route": "resolve_product",
        "resolution_status": "single",
        "selected_row_id": "P999",
    }
    if as_comparison:
        query = {
            "route": "resolve_products",
            "targets": [
                {
                    "mention_parts": ["첫 상품"],
                    "resolution_status": "single",
                    "selected_row_id": "P001",
                },
                {
                    "mention_parts": ["다른 상품"],
                    "resolution_status": "single",
                    "selected_row_id": "P999",
                },
            ],
        }
    model = BindingFakeModel(responses=[_query_response(query)])
    planner = HCXProductCatalogQueryPlanner(
        model=model, catalog=load_product_catalog(), selection_mode="row_ids"
    )

    with pytest.raises(CatalogQueryPlanError) as raised:
        await planner.plan(
            question="상품 조회",
            objective="실행 불가능한 행 선택",
            deadline=asyncio.get_running_loop().time() + 5,
        )

    assert raised.value.retryable is True
    assert raised.value.submitted_query == query
    assert isinstance(raised.value.__cause__, ProductCatalogError)
    assert len(model.received_messages) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "selection",
    [
        {},
        {"selected_row_id": ""},
        {"selected_row_id": 1},
        {"product_code": "KR5153420063"},
        {"selected_row_id": "P001", "product_code": "KR5153420063"},
    ],
)
async def test_row_schema_errors_do_not_trigger_selection_retry(selection: dict[str, Any]) -> None:
    model = BindingFakeModel(
        responses=[
            _query_response(
                {"route": "resolve_product", "resolution_status": "single", **selection}
            )
        ]
    )
    planner = HCXProductCatalogQueryPlanner(
        model=model, catalog=load_product_catalog(), selection_mode="row_ids"
    )

    with pytest.raises(CatalogQueryPlanError) as raised:
        await planner.plan(
            question="상품 조회",
            objective="잘못된 응답 형식",
            deadline=asyncio.get_running_loop().time() + 5,
        )

    assert raised.value.retryable is False
    assert isinstance(raised.value.__cause__, ValidationError)
    assert len(model.received_messages) == 1


@pytest.mark.anyio
async def test_concurrent_planners_resolve_against_their_own_display_order() -> None:
    original = load_product_catalog()
    reversed_catalog = ProductCatalog.from_payloads(
        {"products": [product.to_dict() for product in reversed(original.products)]},
        {"aliases": {}},
    )
    response = _query_response(
        {"route": "resolve_product", "resolution_status": "single", "selected_row_id": "P001"}
    )
    models = [BindingFakeModel(responses=[response]), BindingFakeModel(responses=[response])]
    planners = [
        HCXProductCatalogQueryPlanner(model=model, catalog=catalog, selection_mode="row_ids")
        for model, catalog in zip(models, [original, reversed_catalog], strict=True)
    ]

    results = await asyncio.gather(
        *[
            planner.plan(
                question="첫 번째 행",
                objective="스냅샷별 상품 선택",
                deadline=asyncio.get_running_loop().time() + 5,
            )
            for planner in [planners[0], planners[1], planners[0], planners[1]]
        ]
    )

    assert [
        result.product_code for result in results if isinstance(result, SingleProductQuery)
    ] == [
        original.products[0].product_code,
        original.products[-1].product_code,
        original.products[0].product_code,
        original.products[-1].product_code,
    ]
    for model, expected_code in zip(
        models, [original.products[0].product_code, original.products[-1].product_code], strict=True
    ):
        assert len(model.received_messages) == 2
        assert all(
            f'"row_id":"P001","product_code":"{expected_code}"' in str(messages[0].content)
            for messages in model.received_messages
        )
