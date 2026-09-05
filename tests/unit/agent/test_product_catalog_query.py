"""HCX 상품 카탈로그 Query Planner의 구조와 재검증을 확인한다."""

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, ClassVar, TypeVar

import pytest
from langchain.messages import AIMessage, ToolMessage
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable
from openai import OpenAIError
from pydantic import Field

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
)
from pension_agent.retrieval import load_product_catalog


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
@pytest.mark.parametrize("wrong_code", ["KR5153420022", "KR5153420079", "KR9999999999"])
async def test_query_planner_rejects_wrong_registered_or_unknown_comparison_code(
    wrong_code: str,
) -> None:
    targets = _solomon_targets()
    targets[0]["product_code"] = wrong_code

    with pytest.raises(CatalogQueryPlanError):
        await _plan_comparison(targets)


@pytest.mark.anyio
async def test_query_planner_preserves_unresolved_comparison_targets() -> None:
    query = await _plan_comparison(
        [
            _comparison_target("솔로몬", "단기", product_code="KR5153420063"),
            _comparison_target("솔로몬", "국공채", resolution_status="ambiguous"),
            _comparison_target("새봄", resolution_status="not_found"),
        ],
        question="솔로몬 단기, 솔로몬 국공채, 새봄을 비교해줘.",
    )

    assert [target.resolution_status for target in query.targets] == [
        "single",
        "ambiguous",
        "not_found",
    ]
    assert [target.product_code for target in query.targets] == ["KR5153420063", None, None]
    assert query.targets[2].mention_parts == ["새봄"]


@pytest.mark.anyio
async def test_query_planner_accepts_shared_phrase_and_spacing_variation() -> None:
    query = await _plan_comparison(
        [
            _comparison_target("솔로몬 국공채", "단기", product_code="KR5153420063"),
            _comparison_target("솔로몬 국공채", "중 장 기", product_code="KR5153420079"),
        ],
        question="솔로몬 국공채 단기와 중 장 기를 비교해줘.",
    )

    assert [target.product_code for target in query.targets] == ["KR5153420063", "KR5153420079"]


@pytest.mark.anyio
async def test_query_planner_accepts_exact_codes_and_preserves_repeated_product_mentions() -> None:
    query = await _plan_comparison(
        [
            _comparison_target("kr5153420063", product_code="KR5153420063"),
            _comparison_target("솔로몬단기국공채", product_code="KR5153420063"),
            _comparison_target("KR5153420105", product_code="KR5153420105"),
        ],
        question="kr5153420063(솔로몬단기국공채)와 KR5153420105를 비교해줘.",
    )

    assert len(query.targets) == 3
    assert query.targets[0].product_code == query.targets[1].product_code


@pytest.mark.anyio
@pytest.mark.parametrize(
    "targets,question",
    [
        (_solomon_targets()[:1], "솔로몬 국공채 단기"),
        (_solomon_targets() * 2, "솔로몬 국공채 단기 중장기 장기"),
        (
            [
                _comparison_target("솔로몬", "국공채", product_code="KR5153420063"),
                _solomon_targets()[2],
            ],
            "솔로몬 국공채와 장기를 비교해줘.",
        ),
        (
            [
                _comparison_target("솔로몬", "단기", product_code="KR5153420063"),
                _solomon_targets()[2],
            ],
            "솔로몬 초단기 국공채와 장기를 비교해줘.",
        ),
        (
            [
                _comparison_target("솔로몬", "장기", product_code="KR5153420105"),
                _solomon_targets()[0],
            ],
            "솔로몬 중장기 국공채와 단기를 비교해줘.",
        ),
        (
            [
                _comparison_target("솔로몬", "단기", product_code="KR5153420063"),
                _solomon_targets()[2],
            ],
            "장기 국공채와 단기 국공채를 비교해줘.",
        ),
        (
            [
                _comparison_target("단기", "국공채", product_code="KR5153420063"),
                _comparison_target("장기", "국공채", product_code="KR5153420105"),
            ],
            "단기 국공채와 장기 국공채를 비교해줘.",
        ),
        (
            [
                _comparison_target("솔로몬", "단기", resolution_status="single"),
                _solomon_targets()[2],
            ],
            "솔로몬 국공채 단기와 장기를 비교해줘.",
        ),
        (
            [
                _comparison_target(
                    "솔로몬", "단기", resolution_status="ambiguous", product_code="KR5153420063"
                ),
                _solomon_targets()[2],
            ],
            "솔로몬 국공채 단기와 장기를 비교해줘.",
        ),
    ],
)
async def test_query_planner_rejects_invalid_comparison_targets(
    targets: list[dict[str, Any]],
    question: str,
) -> None:
    with pytest.raises(CatalogQueryPlanError):
        await _plan_comparison(targets, question=question)


@pytest.mark.anyio
async def test_query_planner_keeps_exactly_one_tool_call_contract_for_comparisons() -> None:
    response = _query_response({"route": "resolve_products", "targets": _solomon_targets()})
    response.tool_calls *= 3
    planner = HCXProductCatalogQueryPlanner(
        model=BindingFakeModel(responses=[response]),
        catalog=load_product_catalog(),
    )

    with pytest.raises(CatalogQueryPlanError):
        await planner.plan(
            question="솔로몬 국공채 단기 · 중장기 · 장기 비교",
            objective="상품 비교",
            deadline=asyncio.get_running_loop().time() + 5,
        )


_ResultT = TypeVar("_ResultT")


class RecordingConcurrency(ModelConcurrencyMiddleware):
    """실제 공유 슬롯을 사용하면서 교정 호출의 절대 마감을 기록한다."""

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


def _mismatched_comparison_response() -> AIMessage:
    targets = _solomon_targets()
    targets[0]["product_code"] = "KR5153420022"
    return _query_response({"route": "resolve_products", "targets": targets})


async def _run_recorded_planner(
    model: BindingFakeModel,
    *,
    concurrency: ModelConcurrencyMiddleware | None = None,
    deadline: float | None = None,
) -> Any:
    planner = HCXProductCatalogQueryPlanner(
        model=model,
        catalog=load_product_catalog(),
        model_concurrency=concurrency,
    )
    return await planner.plan(
        question="솔로몬 국공채 단기와 중장기, 장기 상품을 비교해 주세요.",
        objective="상품별 위험 비교",
        deadline=deadline or asyncio.get_running_loop().time() + 5,
    )


@pytest.mark.anyio
async def test_planner_repairs_only_code_mismatch_with_validated_candidate_feedback() -> None:
    model = BindingFakeModel(
        responses=[
            _mismatched_comparison_response(),
            _query_response({"route": "resolve_products", "targets": _solomon_targets()}),
        ]
    )
    concurrency = RecordingConcurrency()
    deadline = asyncio.get_running_loop().time() + 5

    query = await _run_recorded_planner(model, concurrency=concurrency, deadline=deadline)

    assert [target.product_code for target in query.targets] == [
        "KR5153420063",
        "KR5153420079",
        "KR5153420105",
    ]
    assert len(model.received_messages) == 2
    assert concurrency.deadlines == [deadline, deadline]
    correction_messages = model.received_messages[1]
    assert isinstance(correction_messages[-2], AIMessage)
    feedback = correction_messages[-1]
    assert isinstance(feedback, ToolMessage)
    assert feedback.tool_call_id == "query-call"
    payload = json.loads(str(feedback.content))
    assert payload["error"] == "comparison_product_code_mismatch"
    assert payload["instruction"]
    assert payload["mismatches"] == [
        {
            "target_index": 1,
            "mention_parts": ["솔로몬", "국공채", "단기"],
            "selected_product_code": "KR5153420022",
            "candidate": load_product_catalog().select_products(["KR5153420063"])[0].to_dict(),
        }
    ]


@pytest.mark.anyio
async def test_planner_does_not_substitute_code_or_retry_after_failed_correction() -> None:
    model = BindingFakeModel(responses=[_mismatched_comparison_response()])

    with pytest.raises(CatalogQueryPlanError):
        await _run_recorded_planner(model)

    assert len(model.received_messages) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("invalidity", ["schema", "invented_mention", "ambiguous", "tool_count"])
async def test_planner_does_not_repair_other_validation_errors(invalidity: str) -> None:
    response = _mismatched_comparison_response()
    targets = response.tool_calls[0]["args"]["query"]["targets"]
    if invalidity == "schema":
        del targets[1]["product_code"]
    elif invalidity == "invented_mention":
        targets[1]["mention_parts"] = ["원문에 없는 상품명"]
    elif invalidity == "ambiguous":
        targets[1]["mention_parts"] = ["솔로몬", "국공채"]
    else:
        response.tool_calls *= 2
    model = BindingFakeModel(responses=[response])

    with pytest.raises(CatalogQueryPlanError):
        await _run_recorded_planner(model)

    assert len(model.received_messages) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("mutation", ["order", "status", "route"])
async def test_planner_code_repair_cannot_change_original_targets(mutation: str) -> None:
    repaired = _query_response({"route": "resolve_products", "targets": _solomon_targets()})
    query = repaired.tool_calls[0]["args"]["query"]
    if mutation == "order":
        query["targets"].reverse()
    elif mutation == "status":
        query["targets"][0]["resolution_status"] = "ambiguous"
        del query["targets"][0]["product_code"]
    else:
        repaired = _query_response({"route": "browse_all_catalog", "return_mode": "count"})
    model = BindingFakeModel(responses=[_mismatched_comparison_response(), repaired])

    with pytest.raises(CatalogQueryPlanError):
        await _run_recorded_planner(model)

    assert len(model.received_messages) == 2


@pytest.mark.anyio
async def test_planner_correction_does_not_extend_original_deadline() -> None:
    class SlowRepairModel(BindingFakeModel):
        async def _agenerate(self, *args: Any, **kwargs: Any) -> ChatResult:
            if self.received_messages:
                await asyncio.sleep(10)
            return await super()._agenerate(*args, **kwargs)

    model = SlowRepairModel(responses=[_mismatched_comparison_response()])
    concurrency = RecordingConcurrency()
    deadline = asyncio.get_running_loop().time() + 0.2

    with pytest.raises(TimeoutError):
        await _run_recorded_planner(model, concurrency=concurrency, deadline=deadline)

    assert len(model.received_messages) == 1
    assert concurrency.deadlines == [deadline, deadline]


@pytest.mark.anyio
async def test_planner_two_model_call_limit_includes_concurrency_retries() -> None:
    class RepeatingConcurrency(RecordingConcurrency):
        async def arun(
            self,
            operation: Callable[[], Awaitable[_ResultT]],
            *,
            deadline: float | None = None,
        ) -> _ResultT:
            if not self.deadlines:
                await super().arun(operation, deadline=deadline)
            return await super().arun(operation, deadline=deadline)

    model = BindingFakeModel(responses=[_mismatched_comparison_response()])

    with pytest.raises(CatalogQueryPlanError):
        await _run_recorded_planner(model, concurrency=RepeatingConcurrency())

    assert len(model.received_messages) == 2


@pytest.mark.anyio
async def test_planner_provider_failure_does_not_trigger_code_correction() -> None:
    class FailingModel(BindingFakeModel):
        attempt_count: int = 0

        async def _agenerate(self, *args: Any, **kwargs: Any) -> ChatResult:
            del args, kwargs
            self.attempt_count += 1
            raise OpenAIError("테스트 provider 오류")

    model = FailingModel(responses=[])

    with pytest.raises(CatalogQueryPlanError):
        await _run_recorded_planner(model)

    assert model.attempt_count == 1
