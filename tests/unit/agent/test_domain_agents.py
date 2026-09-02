"""Search Service 결과를 사용하는 얇은 Domain Agent를 검증한다."""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, ClassVar, cast
from uuid import UUID

import pytest
from langchain.messages import AIMessage
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable
from langsmith import RunTree, get_current_run_tree, tracing_context

from pension_agent.agent.calculation import format_calculation_summary
from pension_agent.agent.contracts import (
    DomainName,
    DomainResult,
    DomainRunner,
    Permission,
    validate_domain_result,
)
from pension_agent.agent.domain_runner import GuardedDomainRunner
from pension_agent.agent.policy import create_policy_agent, load_policy_agent_prompt
from pension_agent.agent.policy.react import (
    _DC_ELIGIBILITY_MISSING_CONDITION,
    EnforcePolicyToolSequence,
    _build_policy_result,
)
from pension_agent.agent.product import (
    PRODUCT_CATALOG_QUERY_TOOL_NAME,
    AmbiguousProductQuery,
    BrowseAllCatalogQuery,
    BrowseProviderCatalogQuery,
    CatalogQueryPlan,
    NotFoundProductQuery,
    ProductCatalogMatch,
    create_product_agent,
    load_product_agent_prompt,
)
from pension_agent.agent.product.react import _build_product_result
from pension_agent.agent.search import (
    SearchChunkPayload,
    SearchRequest,
    SearchResult,
    SearchRunner,
)
from pension_agent.agent.tax_payout import (
    create_tax_payout_agent,
    load_tax_payout_agent_prompt,
)
from pension_agent.agent.tax_payout.react import (
    _ANNUAL_PRIVATE_PENSION_INCOME_MISSING_CONDITION,
    _INCOME_BASIS_MISSING_CONDITION,
    _MEDICAL_CARE_EXCESS_MISSING_CONDITION,
    _PENSION_TAX_FILING_CHOICE_MISSING_CONDITION,
    _RECIPIENT_AGE_MISSING_CONDITION,
    EnforceTaxPayoutToolSequence,
    _build_tax_payout_result,
)
from pension_agent.config import DomainAgentConfig
from pension_agent.core import DocumentType
from pension_agent.retrieval import load_product_catalog


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class ToolCallingFakeModel(FakeMessagesListChatModel):
    bindings: ClassVar[list[tuple[list[str], dict[str, Any]]]] = []
    tool_argument_names: ClassVar[dict[str, set[str]]] = {}
    tool_required_argument_names: ClassVar[dict[str, set[str]]] = {}
    invocation_count: int = 0

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.invocation_count += 1
        return super()._generate(
            messages,
            stop=stop,
            run_manager=run_manager,
            **kwargs,
        )

    def bind_tools(
        self,
        tools: Sequence[Any],
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        self.bindings.append(([tool.name for tool in tools], kwargs))
        schemas = {tool.name: tool.tool_call_schema.model_json_schema() for tool in tools}
        self.tool_argument_names.update(
            {name: set(schema["properties"]) for name, schema in schemas.items()}
        )
        self.tool_required_argument_names.update(
            {name: set(schema.get("required", [])) for name, schema in schemas.items()}
        )
        return self


@dataclass
class FakeSearchService:
    result: SearchResult
    calls: list[tuple[SearchRequest, Permission]] = field(default_factory=list)

    async def search(
        self,
        request: SearchRequest,
        *,
        permission: Permission,
        deadline: float | None = None,
    ) -> SearchResult:
        assert deadline is not None
        self.calls.append((request, permission))
        return self.result


@dataclass
class ScriptedSearchService:
    results: list[SearchResult]
    calls: list[tuple[SearchRequest, Permission]] = field(default_factory=list)

    async def search(
        self,
        request: SearchRequest,
        *,
        permission: Permission,
        deadline: float | None = None,
    ) -> SearchResult:
        assert deadline is not None
        result = self.results[len(self.calls)]
        self.calls.append((request, permission))
        return result


@dataclass
class FakeProductCatalogMatcher:
    result: ProductCatalogMatch
    calls: list[tuple[str, str]] = field(default_factory=list)

    async def match(
        self,
        *,
        question: str,
        objective: str,
        deadline: float,
    ) -> ProductCatalogMatch:
        assert deadline > asyncio.get_running_loop().time()
        self.calls.append((question, objective))
        return self.result


@dataclass
class FakeProductCatalogQueryPlanner:
    result: CatalogQueryPlan
    calls: list[tuple[str, str]] = field(default_factory=list)

    async def plan(
        self,
        *,
        question: str,
        objective: str,
        deadline: float,
    ) -> CatalogQueryPlan:
        assert deadline > asyncio.get_running_loop().time()
        self.calls.append((question, objective))
        return self.result


def _product_matcher(
    status: str = "single",
    *product_codes: str,
) -> FakeProductCatalogMatcher:
    codes = list(product_codes or ("KR510902511M",))
    candidates = load_product_catalog().select_products(codes if status != "not_found" else [])
    return FakeProductCatalogMatcher(
        ProductCatalogMatch(status=cast(Any, status), candidates=candidates)
    )


def _catalog_browse_planner(
    *,
    provider: str | None = "미래에셋",
    return_mode: str = "count_and_items",
) -> FakeProductCatalogQueryPlanner:
    query = (
        BrowseAllCatalogQuery(
            route="browse_all_catalog",
            return_mode=cast(Any, return_mode),
        )
        if provider is None
        else BrowseProviderCatalogQuery(
            route="browse_provider_catalog",
            provider=provider,
            return_mode=cast(Any, return_mode),
        )
    )
    return FakeProductCatalogQueryPlanner(query)


def _chunk(
    document_type: DocumentType,
    *,
    chunk_id: str = "550e8400-e29b-41d4-a716-446655440000",
    source_file_name: str = "guide.pdf",
    title: str = "이전 절차",
    content: str = "가입 유형에 따라 이전 절차가 달라집니다.",
) -> SearchChunkPayload:
    return SearchChunkPayload(
        chunk_id=chunk_id,
        source_file_name=source_file_name,
        document_type=document_type,
        chunk_index=2,
        title=title,
        locator="3페이지",
        content=content,
    )


def _model(
    *,
    decision_status: str = "determined",
    conclusion: str = "가입 유형에 따라 이전 가능 여부가 달라집니다.",
    missing_conditions: list[str] | None = None,
    warnings: list[str] | None = None,
    evidence_chunk_ids: list[str] | None = None,
    product_code: str | None = None,
) -> ToolCallingFakeModel:
    if missing_conditions is None:
        missing_conditions = (
            [] if decision_status in {"determined", "not_applicable"} else ["가입 유형"]
        )
    if warnings is None:
        warnings = []
    if evidence_chunk_ids is None:
        evidence_chunk_ids = ["550e8400-e29b-41d4-a716-446655440000"]
    search_args = {"objective": "이전 가능 여부의 문서 근거 확인"}
    responses: list[AIMessage] = []
    if product_code is not None:
        responses.append(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            )
        )
        search_args["product_code"] = product_code
    responses.extend(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": search_args,
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": decision_status,
                            "conclusion": conclusion,
                            "missing_conditions": missing_conditions,
                            "warnings": warnings,
                            "evidence_chunk_ids": evidence_chunk_ids,
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    return ToolCallingFakeModel(responses=responses)


def test_product_agent_binds_catalog_planner_to_separate_model() -> None:
    class ProductReactModel(ToolCallingFakeModel):
        bindings: ClassVar[list[tuple[list[str], dict[str, Any]]]] = []

    class CatalogPlannerModel(ToolCallingFakeModel):
        bindings: ClassVar[list[tuple[list[str], dict[str, Any]]]] = []

    react_model = ProductReactModel(responses=[])
    planner_model = CatalogPlannerModel(responses=[])

    create_product_agent(
        model=react_model,
        catalog_planner_model=planner_model,
        search_service=cast(
            SearchRunner,
            FakeSearchService(SearchResult(execution_status="completed")),
        ),
    )

    assert planner_model.bindings == [
        ([PRODUCT_CATALOG_QUERY_TOOL_NAME], {"tool_choice": PRODUCT_CATALOG_QUERY_TOOL_NAME})
    ]
    assert all(
        set(names)
        == {
            "lookup_product_codes",
            "search_documents",
            "calculate_fund_standard_price",
            "calculate_fund_var_risk",
            "submit_domain_result",
        }
        for names, _kwargs in react_model.bindings
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("factory", "domain", "permission", "document_type"),
    [
        (create_policy_agent, "policy", Permission.POLICY, DocumentType.PENSION_REFERENCE),
        (
            create_tax_payout_agent,
            "tax_payout",
            Permission.TAX_PAYOUT,
            DocumentType.PENSION_REFERENCE,
        ),
        (create_product_agent, "product", Permission.PRODUCT, DocumentType.FUND_PROSPECTUS),
    ],
)
async def test_domain_agents_use_search_result_and_submit_verified_result(
    factory: Callable[..., DomainRunner],
    domain: DomainName,
    permission: Permission,
    document_type: DocumentType,
) -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(document_type)],
        )
    )
    product_code = "KR510902511M" if domain == "product" else None
    model = _model(product_code=product_code)
    model.bindings.clear()
    factory_kwargs: dict[str, Any] = {}
    if domain == "product":
        factory_kwargs["catalog_matcher"] = _product_matcher()
    agent = factory(model=model, search_service=cast(SearchRunner, search), **factory_kwargs)
    assert agent.max_concurrency == 3
    assert agent.config.max_search_calls == (2 if domain == "product" else 1)
    result = await agent(
        {"question": "연금계좌를 이전할 수 있나요?", "objective": "이전 가능 여부 판단"}
    )

    validate_domain_result(result)
    assert result["domain"] == domain
    assert result["decision"]["status"] == "determined"
    assert result["evidence"] == [
        {
            "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
            "source_file_name": "guide.pdf",
            "title": "이전 절차",
            "locator": "3페이지",
            "content": "가입 유형에 따라 이전 절차가 달라집니다.",
        }
    ]
    assert result["calculations"] == []
    expected_request = SearchRequest(
        objective="이전 가능 여부의 문서 근거 확인",
        source_file_name="R2_KR510902511M.pdf" if domain == "product" else None,
    )
    assert search.calls == [
        (
            expected_request,
            permission,
        )
    ]
    assert {evidence["chunk_id"] for evidence in result["evidence"]} <= {
        chunk.chunk_id for chunk in search.result.retrieved_chunks
    }
    assert all(
        set(names)
        == (
            {
                "lookup_product_codes",
                "search_documents",
                "calculate_fund_standard_price",
                "calculate_fund_var_risk",
                "submit_domain_result",
            }
            if domain == "product"
            else (
                {
                    "search_documents",
                    "calculate_pension_withdrawal_limit",
                    "calculate_pension_annual_limit_installment",
                    "calculate_pension_period_installment",
                    "calculate_pension_unit_installment",
                    "calculate_pension_tax_credit",
                    "calculate_pension_income_tax",
                    "calculate_non_pension_withdrawal_tax",
                    "calculate_deferred_retirement_withdrawal_tax",
                    "calculate_pension_withdrawal_allocation",
                    "calculate_pension_withdrawal_tax_breakdown",
                    "calculate_medical_care_withdrawal_tax_limit",
                    "calculate_medical_care_withdrawal_tax_breakdown",
                    "submit_domain_result",
                }
                if domain == "tax_payout"
                else {
                    "search_documents",
                    "calculate_dc_medical_withdrawal_threshold",
                    "submit_domain_result",
                }
            )
        )
        for names, _kwargs in model.bindings
    )
    if domain == "product":
        assert model.tool_argument_names["lookup_product_codes"] == set()
        assert model.tool_argument_names["search_documents"] == {
            "objective",
            "product_code",
            "expand_neighbors",
        }
        assert model.tool_required_argument_names["search_documents"] == {"objective"}


@pytest.mark.anyio
async def test_domain_agent_rejects_evidence_id_outside_search_result() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
        )
    )
    valid_chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "이전 가능 여부의 문서 근거 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "이전할 수 있습니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": ["123e4567-e89b-12d3-a456-426614174000"],
                        },
                        "id": "invalid-submit",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "가입 유형에 따라 이전할 수 있습니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [valid_chunk_id],
                        },
                        "id": "valid-submit",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_policy_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"})

    assert [evidence["chunk_id"] for evidence in result["evidence"]] == [valid_chunk_id]
    assert "123e4567-e89b-12d3-a456-426614174000" not in str(result)


@pytest.mark.anyio
async def test_parallel_domain_submissions_keep_only_first_call() -> None:
    chunk = _chunk(DocumentType.PENSION_REFERENCE)
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "이전 근거"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "첫 번째 검증된 결론",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "submit-first",
                        "type": "tool_call",
                    },
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "두 번째 결론",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "submit-second",
                        "type": "tool_call",
                    },
                ],
            ),
        ]
    )
    agent = create_policy_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": "이전 가능해?", "objective": "이전 판단"})

    assert result["execution_status"] == "completed"
    assert result["decision"]["conclusion"] == "첫 번째 검증된 결론"
    assert model.invocation_count == 2


@pytest.mark.anyio
async def test_no_evidence_forces_undetermined_result() -> None:
    search = FakeSearchService(
        SearchResult(execution_status="completed", limitations=["근거 없음"])
    )
    model = _model()
    agent = create_policy_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )
    result = await agent({"question": "외부 정보를 알려줘", "objective": "제공 문서 근거 확인"})

    assert result["decision"]["status"] == "undetermined"
    assert result["decision"]["conclusion"] == (
        "제공 문서에서 관련 근거를 확인하지 못해 판단할 수 없습니다."
    )
    assert result["decision"]["missing_conditions"] == ["제공 문서의 관련 근거"]
    assert result["evidence"] == []
    assert model.invocation_count == 1


@pytest.mark.parametrize(
    "invalid_search_args",
    [
        {"objective": "상품 위험 근거"},
        {"objective": "상품 위험 근거", "product_code": "KR9999999999"},
    ],
)
@pytest.mark.anyio
async def test_product_agent_retries_invalid_scoped_product_code(
    invalid_search_args: dict[str, Any],
) -> None:
    chunk = _chunk(
        DocumentType.FUND_PROSPECTUS,
        source_file_name="R2_KR510902511M.pdf",
    )
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": invalid_search_args,
                        "id": "invalid-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "상품 위험 근거",
                            "product_code": "KR510902511M",
                        },
                        "id": "valid-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "검증된 상품 근거입니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_matcher=_product_matcher(),
    )

    result = await agent(
        {
            "question": "미래에셋 장기성장 위험은?",
            "objective": "상품 위험 판단",
        }
    )

    assert result["execution_status"] == "completed"
    assert search.calls == [
        (
            SearchRequest(
                objective="상품 위험 근거",
                source_file_name="R2_KR510902511M.pdf",
            ),
            Permission.PRODUCT,
        )
    ]
    assert model.invocation_count == 4


@pytest.mark.anyio
async def test_product_agent_returns_verified_ambiguous_candidates_without_document_search() -> (
    None
):
    search = FakeSearchService(SearchResult(execution_status="completed"))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    matcher = _product_matcher("ambiguous", "KR510902511M", "KR510902773M")
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_matcher=matcher,
    )

    result = await agent({"question": "미리에셋 상품은 어때?", "objective": "상품 후보 식별"})

    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == "conditional"
    assert "KR510902511M" in result["decision"]["conclusion"]
    assert "KR510902773M" in result["decision"]["conclusion"]
    assert result["evidence"] == []
    assert search.calls == []
    assert matcher.calls == [("미리에셋 상품은 어때?", "상품 후보 식별")]
    assert model.invocation_count == 1


@pytest.mark.anyio
async def test_product_agent_returns_deterministic_catalog_result_without_document_search() -> None:
    search = FakeSearchService(SearchResult(execution_status="completed"))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "catalog-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "모델이 만든 개수와 목록",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "catalog-submit",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    planner = _catalog_browse_planner()
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_query_planner=planner,
    )

    result = await agent(
        {
            "question": "미레에셋 상품은 몇 개고 어떤 것들이 있나요?",
            "objective": "미래에셋 상품 개수와 목록 조회",
        }
    )

    catalog_result = result["catalog_result"]
    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == "determined"
    assert catalog_result["provider"] == "미래에셋"
    assert catalog_result["return_mode"] == "count_and_items"
    assert catalog_result["total_count"] == 25
    assert len(catalog_result["items"]) == 25
    assert catalog_result["items"][0]["product_code"] == "KR510902511M"
    assert result["evidence"][0]["source_file_name"] == "product_catalog.json"
    assert catalog_result["catalog_version"] in result["evidence"][0]["content"]
    assert search.calls == []
    assert planner.calls == [
        (
            "미레에셋 상품은 몇 개고 어떤 것들이 있나요?",
            "미래에셋 상품 개수와 목록 조회",
        )
    ]
    assert model.invocation_count == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("question", "objective"),
    [
        ("미래에셋 상품 추천", "미래에셋 상품 추천"),
        ("추천은 하지 말고 미래에셋 상품 목록만 알려줘", "미래에셋 상품 목록 조회"),
    ],
)
async def test_product_agent_preserves_catalog_for_broad_product_requests(
    question: str,
    objective: str,
) -> None:
    search = FakeSearchService(SearchResult(execution_status="completed"))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "catalog-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "검증된 카탈로그 상품 목록입니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "catalog-submit",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_query_planner=(planner := _catalog_browse_planner()),
    )

    result = await agent({"question": question, "objective": objective})

    catalog_result = result["catalog_result"]
    assert result["decision"]["status"] == "determined"
    assert catalog_result["provider"] == "미래에셋"
    assert catalog_result["total_count"] == 25
    assert len(catalog_result["items"]) == 25
    assert result["evidence"][0]["source_file_name"] == "product_catalog.json"
    assert search.calls == []
    assert planner.calls == [(question, objective)]
    assert model.invocation_count == 2


@pytest.mark.anyio
async def test_product_agent_rejects_initial_conditional_submit_before_catalog_lookup() -> None:
    search = FakeSearchService(SearchResult(execution_status="completed"))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "conditional",
                            "conclusion": "추천 조건이 필요합니다.",
                            "missing_conditions": ["투자 기간"],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "early-submit",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "catalog-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "검증된 카탈로그 상품 목록입니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "catalog-submit",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    planner = _catalog_browse_planner()
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_query_planner=planner,
    )

    result = await agent({"question": "미래에셋 상품 추천", "objective": "미래에셋 상품 추천"})

    assert result["decision"]["status"] == "determined"
    assert result["catalog_result"]["total_count"] == 25
    assert planner.calls == [("미래에셋 상품 추천", "미래에셋 상품 추천")]
    assert search.calls == []
    assert model.invocation_count == 3


@pytest.mark.anyio
async def test_product_agent_returns_undetermined_when_catalog_has_no_candidate() -> None:
    search = FakeSearchService(SearchResult(execution_status="completed"))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_matcher=_product_matcher("not_found"),
    )

    result = await agent({"question": "없는 상품", "objective": "상품 후보 식별"})

    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == "undetermined"
    assert result["decision"]["missing_conditions"]
    assert result["evidence"] == []
    assert search.calls == []
    assert model.invocation_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("resolution_status", "decision_status"),
    [("not_found", "undetermined"), ("ambiguous", "conditional")],
)
async def test_product_agent_ends_unresolved_query_without_document_search(
    resolution_status: str,
    decision_status: str,
) -> None:
    search = FakeSearchService(SearchResult(execution_status="completed"))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    query = (
        NotFoundProductQuery(route="product_not_found", resolution_status="not_found")
        if resolution_status == "not_found"
        else AmbiguousProductQuery(route="product_ambiguous", resolution_status="ambiguous")
    )
    planner = FakeProductCatalogQueryPlanner(query)
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_query_planner=planner,
    )

    result = await agent({"question": "식별하기 어려운 상품", "objective": "상품 식별"})

    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == decision_status
    assert result["decision"]["missing_conditions"]
    assert result["evidence"] == []
    assert search.calls == []
    assert planner.calls == [("식별하기 어려운 상품", "상품 식별")]
    assert model.invocation_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("question", "query", "execution_status", "decision_status"),
    [
        (
            "메리츠 상품은 몇 개가 등록돼 있어?",
            {
                "route": "provider_not_found",
                "provider": "메리츠",
                "return_mode": "count",
            },
            "completed",
            "undetermined",
        ),
        (
            "새봄 연금펀드의 위험과 수수료를 알려줘.",
            {
                "route": "product_not_found",
                "resolution_status": "not_found",
            },
            "completed",
            "undetermined",
        ),
        (
            "새봄 연금펀드의 위험과 수수료를 알려줘.",
            {
                "route": "resolve_product",
                "resolution_status": "single",
                "product_code": None,
            },
            "failed",
            None,
        ),
    ],
)
async def test_product_agent_handles_unregistered_and_invalid_hcx_queries_without_search(
    question: str,
    query: dict[str, Any],
    execution_status: str,
    decision_status: str | None,
) -> None:
    search = FakeSearchService(SearchResult(execution_status="completed"))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "return_product_catalog_query",
                        "args": {"query": query},
                        "id": "query-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_product_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent({"question": question, "objective": "상품 카탈로그 확인"})

    assert result["execution_status"] == execution_status
    if decision_status is None:
        assert "decision" not in result
        assert "계획을 확정하지 못했습니다" in result["error"]
    else:
        assert result["decision"]["status"] == decision_status
        assert result["decision"]["missing_conditions"]
        assert "카탈로그에 등록" in result["decision"]["conclusion"]
    assert result["evidence"] == []
    assert search.calls == []
    assert model.invocation_count == 2


@pytest.mark.anyio
async def test_product_agent_default_matcher_calls_nested_hcx_before_document_search() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.FUND_PROSPECTUS)],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "return_product_catalog_query",
                        "args": {
                            "query": {
                                "route": "resolve_product",
                                "resolution_status": "single",
                                "provider": "미래에셋",
                                "product_code": "KR510902511M",
                            }
                        },
                        "id": "selection-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "상품 위험 근거 확인",
                            "product_code": "KR510902511M",
                        },
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "검증된 상품 결론",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": ["550e8400-e29b-41d4-a716-446655440000"],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_product_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent({"question": "미리에셋 장기성장 위험은?", "objective": "상품 위험 판단"})

    assert result["execution_status"] == "completed"
    assert result["decision"]["conclusion"] == "검증된 상품 결론"
    assert search.calls[0][0].source_file_name == "R2_KR510902511M.pdf"
    assert model.invocation_count == 4


@pytest.mark.anyio
async def test_product_agent_can_search_globally_before_catalog_lookup() -> None:
    global_chunk = _chunk(
        DocumentType.FUND_PROSPECTUS,
        source_file_name="R2_KR510902773M.pdf",
        title="상품 비용 용어",
        content="상품 비용은 총보수와 수수료 항목에서 확인합니다.",
    )
    scoped_chunk = _chunk(
        DocumentType.FUND_PROSPECTUS,
        chunk_id="123e4567-e89b-12d3-a456-426614174000",
        source_file_name="R2_KR510902511M.pdf",
        title="해당 상품의 보수",
        content="이 상품의 보수와 수수료는 투자설명서에 기재됩니다.",
    )
    search = ScriptedSearchService(
        results=[
            SearchResult(execution_status="completed", retrieved_chunks=[global_chunk]),
            SearchResult(execution_status="completed", retrieved_chunks=[scoped_chunk]),
        ]
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "상품 비용을 설명하는 문서 용어 탐색"},
                        "id": "global-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "전체 검색 결과를 특정 상품 결론으로 제출합니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [global_chunk.chunk_id],
                        },
                        "id": "premature-submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "총보수와 수수료의 문서 근거",
                            "product_code": "KR510902511M",
                        },
                        "id": "scoped-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "해당 상품의 보수와 수수료는 투자설명서에 기재됩니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [scoped_chunk.chunk_id],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    matcher = _product_matcher()
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_matcher=matcher,
    )

    result = await agent(
        {"question": "미래에셋 장기성장 상품은 비싸?", "objective": "상품 비용 판단"}
    )

    assert [request for request, _permission in search.calls] == [
        SearchRequest(objective="상품 비용을 설명하는 문서 용어 탐색"),
        SearchRequest(
            objective="총보수와 수수료의 문서 근거",
            source_file_name="R2_KR510902511M.pdf",
        ),
    ]
    assert matcher.calls == [("미래에셋 장기성장 상품은 비싸?", "상품 비용 판단")]
    assert [evidence["chunk_id"] for evidence in result["evidence"]] == [scoped_chunk.chunk_id]
    assert global_chunk.chunk_id not in {evidence["chunk_id"] for evidence in result["evidence"]}
    assert model.invocation_count == 5


@pytest.mark.anyio
async def test_product_agent_discards_unverified_code_from_search_before_lookup() -> None:
    chunk = _chunk(
        DocumentType.FUND_PROSPECTUS,
        source_file_name="R2_KR510902511M.pdf",
    )
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "검증 전 상품 검색",
                            "product_code": "KR510902511M",
                        },
                        "id": "unverified-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "검증 후 상품 검색",
                            "product_code": "KR510902511M",
                        },
                        "id": "verified-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "검증된 상품 근거입니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_matcher=_product_matcher(),
    )

    result = await agent({"question": "미래에셋 장기성장 위험은?", "objective": "상품 위험 판단"})

    assert search.calls == [
        (
            SearchRequest(
                objective="검증 후 상품 검색",
                source_file_name="R2_KR510902511M.pdf",
            ),
            Permission.PRODUCT,
        )
    ]
    assert result["execution_status"] == "completed"
    assert model.invocation_count == 4


@pytest.mark.anyio
async def test_product_agent_rewrites_query_after_empty_search() -> None:
    chunk = _chunk(
        DocumentType.FUND_PROSPECTUS,
        title="보수와 수수료",
        content="총보수와 운용보수는 투자설명서의 비용 항목에 기재됩니다.",
    )
    search = ScriptedSearchService(
        results=[
            SearchResult(execution_status="completed", limitations=["근거 없음"]),
            SearchResult(execution_status="completed", retrieved_chunks=[chunk]),
        ]
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "미리에셋 이거 비싼지 확인",
                            "product_code": "KR510902511M",
                        },
                        "id": "first-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "총보수, 운용보수와 판매수수료의 문서 근거",
                            "product_code": "KR510902511M",
                        },
                        "id": "second-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "비용은 투자설명서의 보수와 수수료 항목으로 판단합니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_matcher=_product_matcher(),
    )

    result = await agent({"question": "미리에셋 이거 비싸?", "objective": "상품 비용 판단"})

    assert agent.config.max_search_calls == 2
    assert [request.objective for request, _permission in search.calls] == [
        "미리에셋 이거 비싼지 확인",
        "총보수, 운용보수와 판매수수료의 문서 근거",
    ]
    assert [evidence["chunk_id"] for evidence in result["evidence"]] == [chunk.chunk_id]
    assert "근거 없음" not in result["warnings"]


@pytest.mark.anyio
async def test_product_agent_ends_safely_after_two_empty_searches() -> None:
    search = ScriptedSearchService(
        results=[
            SearchResult(execution_status="completed", limitations=["첫 검색 근거 없음"]),
            SearchResult(execution_status="completed", limitations=["재검색 근거 없음"]),
        ]
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "상품 비용 근거",
                            "product_code": "KR510902511M",
                        },
                        "id": "first-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "총보수와 수수료 항목",
                            "product_code": "KR510902511M",
                        },
                        "id": "second-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_matcher=_product_matcher(),
    )

    result = await agent({"question": "상품 비용은?", "objective": "상품 비용 판단"})

    assert len(search.calls) == 2
    assert result["decision"]["status"] == "undetermined"
    assert result["warnings"] == [
        "첫 검색 근거 없음",
        "재검색 근거 없음",
        "제공 문서에서 관련 근거를 확인하지 못했습니다.",
    ]
    assert model.invocation_count == 3


@pytest.mark.anyio
async def test_product_agent_caps_searches_and_keeps_deduplicated_evidence() -> None:
    first_chunk = _chunk(
        DocumentType.FUND_PROSPECTUS,
        title="위험등급",
        content="이 상품의 위험등급을 확인해야 합니다.",
    )
    second_chunk = _chunk(
        DocumentType.FUND_PROSPECTUS,
        chunk_id="123e4567-e89b-12d3-a456-426614174000",
        title="환매와 유동성",
        content="환매 조건과 지급 시기를 확인해야 합니다.",
    )
    search = ScriptedSearchService(
        results=[
            SearchResult(execution_status="completed", retrieved_chunks=[first_chunk]),
            SearchResult(
                execution_status="completed",
                retrieved_chunks=[first_chunk, second_chunk],
            ),
        ]
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "위험등급의 문서 근거",
                            "product_code": "KR510902511M",
                        },
                        "id": "first-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "환매 조건과 지급 시기의 문서 근거",
                            "product_code": "KR510902511M",
                        },
                        "id": "second-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "차단되어야 하는 추가 검색",
                            "product_code": "KR510902511M",
                        },
                        "id": "blocked-search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "위험등급과 환매 조건을 함께 확인해야 합니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [first_chunk.chunk_id, second_chunk.chunk_id],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_matcher=_product_matcher(),
    )

    result = await agent(
        {"question": "미래에셋 장기성장 위험과 환매는?", "objective": "위험과 유동성 판단"}
    )

    assert len(search.calls) == 2
    assert [evidence["chunk_id"] for evidence in result["evidence"]] == [
        first_chunk.chunk_id,
        second_chunk.chunk_id,
    ]
    assert model.invocation_count == 5


@pytest.mark.anyio
async def test_product_agent_keeps_lookup_before_parallel_early_search_call() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.FUND_PROSPECTUS)],
        )
    )
    first_response = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "lookup_product_codes",
                "args": {},
                "id": "lookup-call",
                "type": "tool_call",
            },
            {
                "name": "search_documents",
                "args": {
                    "objective": "상품 위험 근거 확인",
                    "product_code": "KR510902511M",
                },
                "id": "early-search-call",
                "type": "tool_call",
            },
        ],
    )
    remaining = _model(product_code=None).responses
    remaining[0] = remaining[0].model_copy(
        update={
            "tool_calls": [
                {
                    "name": "search_documents",
                    "args": {
                        "objective": "상품 위험 근거 확인",
                        "product_code": "KR510902511M",
                    },
                    "id": "search-call",
                    "type": "tool_call",
                }
            ]
        }
    )
    model = ToolCallingFakeModel(responses=[first_response, *remaining])
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_matcher=_product_matcher(),
    )

    result = await agent({"question": "미래에셋 장기성장 위험은?", "objective": "상품 위험 판단"})

    assert result["execution_status"] == "completed"
    assert len(search.calls) == 1
    assert model.invocation_count == 3


@pytest.mark.anyio
async def test_no_evidence_discards_ungrounded_model_conclusion_and_conditions() -> None:
    search = FakeSearchService(
        SearchResult(execution_status="completed", limitations=["근거 없음"])
    )
    model = _model(
        conclusion="모든 가입자는 언제나 이전할 수 있습니다.",
        missing_conditions=["가입자의 임의 조건"],
    )
    agent = create_policy_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )
    result = await agent({"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"})

    assert result["decision"] == {
        "status": "undetermined",
        "conclusion": "제공 문서에서 관련 근거를 확인하지 못해 판단할 수 없습니다.",
        "missing_conditions": ["제공 문서의 관련 근거"],
    }
    assert "언제나 이전" not in str(result)
    assert "가입자의 임의 조건" not in str(result)
    assert model.invocation_count == 1


@pytest.mark.anyio
async def test_domain_agent_owns_search_sufficiency_decision() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
        )
    )
    agent = create_policy_agent(
        model=_model(decision_status="conditional", missing_conditions=["가입 유형"]),
        search_service=cast(SearchRunner, search),
    )
    result = await agent({"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"})

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"]


@pytest.mark.anyio
async def test_search_failure_is_returned_without_evidence() -> None:
    search = FakeSearchService(
        SearchResult(execution_status="failed", error="검색을 완료하지 못했습니다.")
    )
    model = _model(product_code="KR510902511M")
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_matcher=_product_matcher(),
    )
    result = await agent({"question": "상품 위험은?", "objective": "상품 위험 판단"})

    assert result["execution_status"] == "failed"
    assert result["evidence"] == []
    assert result["calculations"] == []
    assert "provider" not in result["error"].lower()
    assert model.invocation_count == 2


@pytest.mark.anyio
async def test_user_provided_source_hint_is_forwarded_to_search_service() -> None:
    search = FakeSearchService(SearchResult(execution_status="completed"))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "guide.pdf 이전 절차",
                            "source_file_name": "guide.pdf",
                        },
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    agent = create_policy_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent(
        {
            "question": "guide.pdf에서 이전 절차를 찾아줘",
            "objective": "이전 절차 판단",
        }
    )

    assert result["decision"]["status"] == "undetermined"
    assert search.calls == [
        (
            SearchRequest(
                objective="guide.pdf 이전 절차",
                source_file_name="guide.pdf",
            ),
            Permission.POLICY,
        )
    ]


@pytest.mark.anyio
async def test_model_generated_source_hint_is_rejected_before_search_service() -> None:
    search = FakeSearchService(SearchResult(execution_status="completed"))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "이전 절차",
                            "source_file_name": "hallucinated.pdf",
                        },
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    agent = create_policy_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": "이전 절차를 알려줘", "objective": "이전 절차 판단"})

    assert result["execution_status"] == "failed"
    assert result["evidence"] == []
    assert search.calls == []
    assert model.invocation_count == 1


@pytest.mark.anyio
async def test_tax_agent_replaces_numeric_claim_without_calculator() -> None:
    chunk = _chunk(DocumentType.PENSION_REFERENCE)
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "세율 판단 근거 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "세율은 10%입니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "first-submit",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "세율은 여전히 10%로 확정됩니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "second-submit",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )
    result = await agent({"question": "세율은?", "objective": "세율 판단"})

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["conclusion"] == (
        "확정 수치 판단에는 결정론적 계산 Tool 결과가 필요합니다."
    )
    assert "10" not in result["decision"]["conclusion"]
    assert result["calculations"] == []
    assert len(search.calls) == 1
    assert model.invocation_count == 3


@pytest.mark.anyio
async def test_tax_agent_records_and_uses_verified_pension_calculation() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.PENSION_REFERENCE,
                    title="연금수령한도",
                    content="평가액 1천만원, 수령연차 1년차에 대한 산식입니다.",
                )
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "연금수령한도 산식 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    },
                    {
                        "name": "calculate_pension_withdrawal_limit",
                        "args": {
                            "account_valuation_krw": "10000000",
                            "pension_year": 1,
                            "account_valuation_source": "평가액 1천만원",
                            "pension_year_source": "1년차",
                        },
                        "id": "early-calculation-call",
                        "type": "tool_call",
                    },
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_pension_withdrawal_limit",
                        "args": {
                            "account_valuation_krw": "10000000",
                            "pension_year": 1,
                            "account_valuation_source": "평가액 1천만원",
                            "pension_year_source": "1년차",
                        },
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "임의 계산값은 999원입니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent(
        {
            "question": "검색 문서 기준 연금수령한도는?",
            "objective": "연금수령한도 계산",
        }
    )

    assert result["decision"]["status"] == "determined"
    assert "1200000.0 KRW" in result["decision"]["conclusion"]
    assert "999" not in result["decision"]["conclusion"]
    assert result["calculations"][0]["calculator_id"] == "pension_withdrawal_limit"
    assert result["calculations"][0]["outputs"] == {
        "withdrawal_limit": "1200000.0",
        "limit_applies": True,
    }
    assert result["calculations"][0]["input_sources"]["account_valuation_krw"] == {
        "origin": "evidence",
        "text": "평가액 1천만원",
        "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
    }
    assert [chunk["chunk_id"] for chunk in result["evidence"]] == [
        "550e8400-e29b-41d4-a716-446655440000"
    ]


@pytest.mark.anyio
async def test_tax_agent_records_and_uses_verified_tax_credit_calculation() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.PENSION_REFERENCE,
                    title="세액공제",
                    content=(
                        "연금저축 순납입액 600만원, 퇴직연금 순납입액 300만원 납입, "
                        "연금저축 ISA 전환액 0원, 퇴직연금 ISA 전환액 0원, "
                        "총급여 5천만원에 대한 세액공제 규칙입니다."
                    ),
                )
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "세액공제 산식 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_pension_tax_credit",
                        "args": {
                            "pension_savings_net_contribution_krw": "6000000",
                            "retirement_pension_net_contribution_krw": "3000000",
                            "pension_savings_isa_transfer_krw": "0",
                            "retirement_pension_isa_transfer_krw": "0",
                            "pension_savings_net_contribution_source": "연금저축 순납입액 600만원",
                            "retirement_pension_net_contribution_source": "퇴직연금 순납입액 300만원",
                            "pension_savings_isa_transfer_source": "연금저축 ISA 전환액 0원",
                            "retirement_pension_isa_transfer_source": "퇴직연금 ISA 전환액 0원",
                            "income_basis": "salary",
                            "income_basis_source": "총급여",
                            "income_amount_krw": "50000000",
                            "income_amount_source": "총급여 5천만원",
                        },
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "임의 세액은 999원입니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent(
        {
            "question": "세액공제 대상액과 세액을 계산해줘",
            "objective": "연금계좌 세액공제 계산",
        }
    )

    assert result["decision"]["status"] == "determined"
    assert "999" not in result["decision"]["conclusion"]
    assert "연금계좌 세액공제 대상액" in result["decision"]["conclusion"]
    assert "이론상 세액" in result["decision"]["conclusion"]
    assert result["calculations"][0]["calculator_id"] == "pension_tax_credit"
    assert Decimal(result["calculations"][0]["outputs"]["eligible_contribution_krw"]) == Decimal(
        9_000_000
    )
    assert [chunk["chunk_id"] for chunk in result["evidence"]] == [
        "550e8400-e29b-41d4-a716-446655440000"
    ]


@pytest.mark.anyio
async def test_tax_agent_summarizes_both_income_scenarios_without_income_input() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.PENSION_REFERENCE,
                    title="세액공제",
                    content=(
                        "연금저축 순납입액 600만원, 퇴직연금 순납입액 300만원 납입, "
                        "연금저축 ISA 전환액 0원, 퇴직연금 ISA 전환액 0원에 대한 "
                        "세액공제 규칙입니다."
                    ),
                )
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "세액공제 산식 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_pension_tax_credit",
                        "args": {
                            "pension_savings_net_contribution_krw": "6000000",
                            "retirement_pension_net_contribution_krw": "3000000",
                            "pension_savings_isa_transfer_krw": "0",
                            "retirement_pension_isa_transfer_krw": "0",
                            "pension_savings_net_contribution_source": "연금저축 순납입액 600만원",
                            "retirement_pension_net_contribution_source": "퇴직연금 순납입액 300만원",
                            "pension_savings_isa_transfer_source": "연금저축 ISA 전환액 0원",
                            "retirement_pension_isa_transfer_source": "퇴직연금 ISA 전환액 0원",
                        },
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "임의 결론",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": "세액공제 대상액은?", "objective": "연금계좌 세액공제 계산"})

    conclusion = result["decision"]["conclusion"]
    assert "16.5%" in conclusion
    assert "13.2%" in conclusion


@pytest.mark.anyio
async def test_tax_agent_leaves_income_bracket_as_missing_condition_when_omitted() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.PENSION_REFERENCE,
                    title="세액공제",
                    content=(
                        "연금저축 순납입액 600만원, 퇴직연금 순납입액 300만원 납입, "
                        "연금저축 ISA 전환액 0원, 퇴직연금 ISA 전환액 0원에 대한 "
                        "세액공제 규칙입니다."
                    ),
                )
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "세액공제 산식 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_pension_tax_credit",
                        "args": {
                            "pension_savings_net_contribution_krw": "6000000",
                            "retirement_pension_net_contribution_krw": "3000000",
                            "pension_savings_isa_transfer_krw": "0",
                            "retirement_pension_isa_transfer_krw": "0",
                            "pension_savings_net_contribution_source": "연금저축 순납입액 600만원",
                            "retirement_pension_net_contribution_source": "퇴직연금 순납입액 300만원",
                            "pension_savings_isa_transfer_source": "연금저축 ISA 전환액 0원",
                            "retirement_pension_isa_transfer_source": "퇴직연금 ISA 전환액 0원",
                        },
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "conditional",
                            "conclusion": "임의 결론",
                            "missing_conditions": ["총급여 또는 종합소득금액 확인"],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": "세액공제 대상액은?", "objective": "연금계좌 세액공제 계산"})

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == [
        "총급여 또는 종합소득금액 확인",
        _INCOME_BASIS_MISSING_CONDITION,
    ]
    assert result["calculations"][0]["calculator_id"] == "pension_tax_credit"
    conclusion = result["decision"]["conclusion"]
    assert "16.5%" in conclusion
    assert "13.2%" in conclusion


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("question", "content", "tool_name", "tool_args", "expected_calculator", "expected_text"),
    [
        (
            "일반 연금수령 세금을 계산해줘",
            (
                "일반 연금수령; 수령자 나이 55세; 비종신 연금; "
                "현재 연금수령 과세대상 금액 100만원; "
                "연간 사적연금 과세대상 합계 1,000만원"
            ),
            "calculate_pension_income_tax",
            {
                "pension_treatment": "ordinary",
                "recipient_age": 55,
                "pension_treatment_source": "일반 연금수령",
                "recipient_age_source": "수령자 나이 55세",
                "target_taxable_amount_krw": "1000000",
                "target_taxable_amount_krw_source": "현재 연금수령 과세대상 금액 100만원",
                "is_lifetime_annuity": False,
                "is_lifetime_annuity_source": "비종신 연금",
                "annual_private_pension_taxable_income_krw": "10000000",
                "annual_private_pension_taxable_income_krw_source": (
                    "연간 사적연금 과세대상 합계 1,000만원"
                ),
            },
            "pension_income_tax",
            "일반 연금수령 적용 기본세율",
        ),
        (
            "54세 부득이한 사유 인출 세율은?",
            "부득이한 사유 연금수령; 수령자 연령 54세",
            "calculate_pension_income_tax",
            {
                "pension_treatment": "unavoidable",
                "recipient_age": 54,
                "pension_treatment_source": "부득이한 사유 연금수령",
                "recipient_age_source": "수령자 연령 54세",
            },
            "pension_income_tax",
            "부득이한 사유 인출 적용 기본세율",
        ),
        (
            "중도해지 운용수익 세금을 계산해줘",
            "중도해지 운용수익 과세대상 금액 100만원",
            "calculate_non_pension_withdrawal_tax",
            {
                "taxable_amount_krw": "1000000",
                "taxable_amount_krw_source": "중도해지 운용수익 과세대상 금액 100만원",
            },
            "non_pension_withdrawal_tax",
            "세액공제 원금·운용수익의 연금외수령",
        ),
    ],
)
async def test_tax_agent_runs_pension_income_tax_paths(
    question: str,
    content: str,
    tool_name: str,
    tool_args: dict[str, object],
    expected_calculator: str,
    expected_text: str,
) -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(DocumentType.PENSION_REFERENCE, title="연금 과세", content=content)
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "연금 과세 근거 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": tool_name,
                        "args": tool_args,
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "임의 결론",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent({"question": question, "objective": "연금 과세 계산"})

    assert result["calculations"][0]["calculator_id"] == expected_calculator
    assert expected_text in result["decision"]["conclusion"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("question", "content", "tool_args", "expected_label", "expected_ratio"),
    [
        (
            "이연퇴직소득을 연금으로 받으면 세금은?",
            (
                "이연퇴직소득 연금수령; 실제수령연차 10년차; "
                "해당 인출분에 배분된 이연퇴직소득세 100만원"
            ),
            {
                "receipt_type": "pension",
                "receipt_type_source": "이연퇴직소득 연금수령",
                "actual_pension_receipt_year": 10,
                "actual_pension_receipt_year_source": "실제수령연차 10년차",
                "allocated_deferred_retirement_tax_krw": "1000000",
                "allocated_deferred_retirement_tax_krw_source": (
                    "해당 인출분에 배분된 이연퇴직소득세 100만원"
                ),
            },
            "이연퇴직소득 연금수령 납부 비율",
            "70.00 %",
        ),
        (
            "이연퇴직소득을 일시금으로 받으면 세금은?",
            "이연퇴직소득 일시금; 해당 인출분에 배분된 퇴직소득세 100만원",
            {
                "receipt_type": "non_pension",
                "receipt_type_source": "이연퇴직소득 일시금",
                "allocated_deferred_retirement_tax_krw": "1000000",
                "allocated_deferred_retirement_tax_krw_source": (
                    "해당 인출분에 배분된 퇴직소득세 100만원"
                ),
            },
            "이연퇴직소득 연금외수령 납부 비율",
            "100 %",
        ),
    ],
)
async def test_tax_agent_runs_deferred_retirement_tax_paths(
    question: str,
    content: str,
    tool_args: dict[str, object],
    expected_label: str,
    expected_ratio: str,
) -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(DocumentType.PENSION_REFERENCE, title="이연퇴직소득세", content=content)
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "이연퇴직소득세 근거 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_deferred_retirement_withdrawal_tax",
                        "args": tool_args,
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "임의 결론",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent({"question": question, "objective": "이연퇴직소득세 계산"})

    assert result["calculations"][0]["calculator_id"] == ("deferred_retirement_withdrawal_tax")
    assert expected_label in result["decision"]["conclusion"]
    assert expected_ratio in result["decision"]["conclusion"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "missing_conditions"),
    [
        ("determined", []),
        ("conditional", ["해당 인출분에 배분된 이연퇴직소득세 확인 필요"]),
    ],
)
async def test_tax_agent_keeps_model_intent_for_omitted_allocated_deferred_tax(
    status: str, missing_conditions: list[str]
) -> None:
    content = "이연퇴직소득 연금수령; 실제수령연차 10년차"
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(DocumentType.PENSION_REFERENCE, title="이연퇴직소득세", content=content)
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "이연퇴직소득세 비율 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_deferred_retirement_withdrawal_tax",
                        "args": {
                            "receipt_type": "pension",
                            "receipt_type_source": "이연퇴직소득 연금수령",
                            "actual_pension_receipt_year": 10,
                            "actual_pension_receipt_year_source": "실제수령연차 10년차",
                        },
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": status,
                            "conclusion": "이연퇴직소득세 비율 결과입니다.",
                            "missing_conditions": missing_conditions,
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent(
        {"question": "이연퇴직소득세 비율 또는 납부세액은?", "objective": "비율 계산"}
    )

    assert result["decision"]["status"] == status
    assert result["decision"]["missing_conditions"] == missing_conditions
    assert "납부세액" not in result["decision"]["conclusion"]


def _tool_call(name: str, call_id: str) -> dict[str, Any]:
    return {"name": name, "args": {}, "id": call_id, "type": "tool_call"}


def _sequence_result_tool_names(
    *, calculations: list[dict[str, Any]], tool_names: list[str]
) -> list[str]:
    message = AIMessage(
        content="",
        tool_calls=[_tool_call(name, f"call-{index}") for index, name in enumerate(tool_names)],
    )
    state = {
        "search_result": SearchResult(execution_status="completed"),
        "calculations": calculations,
        "messages": [message],
    }
    update = EnforceTaxPayoutToolSequence().after_model(state, None)
    kept_message = message if update is None else update["messages"][0]
    return [call["name"] for call in kept_message.tool_calls]


def test_tax_agent_keeps_exact_pension_tax_comparison_pair_in_one_model_call() -> None:
    kept = _sequence_result_tool_names(
        calculations=[],
        tool_names=[
            "calculate_pension_income_tax",
            "calculate_non_pension_withdrawal_tax",
            "submit_domain_result",
        ],
    )

    assert kept == [
        "calculate_pension_income_tax",
        "calculate_non_pension_withdrawal_tax",
    ]


def test_tax_agent_keeps_only_first_pension_installment_tool() -> None:
    kept = _sequence_result_tool_names(
        calculations=[],
        tool_names=[
            "calculate_pension_annual_limit_installment",
            "calculate_pension_period_installment",
            "calculate_pension_unit_installment",
        ],
    )

    assert kept == ["calculate_pension_annual_limit_installment"]


def test_tax_agent_keeps_only_first_pension_withdrawal_tool() -> None:
    kept = _sequence_result_tool_names(
        calculations=[],
        tool_names=[
            "calculate_pension_withdrawal_tax_breakdown",
            "calculate_pension_withdrawal_allocation",
        ],
    )

    assert kept == ["calculate_pension_withdrawal_tax_breakdown"]


def test_tax_agent_allows_only_submit_after_pension_withdrawal_calculation() -> None:
    kept = _sequence_result_tool_names(
        calculations=[{"calculator_id": "pension_withdrawal_allocation"}],
        tool_names=[
            "calculate_pension_income_tax",
            "calculate_pension_withdrawal_tax_breakdown",
            "submit_domain_result",
        ],
    )

    assert kept == ["submit_domain_result"]


def test_tax_agent_allows_allocation_after_failed_breakdown_without_calculation() -> None:
    kept = _sequence_result_tool_names(
        calculations=[],
        tool_names=["calculate_pension_withdrawal_allocation"],
    )

    assert kept == ["calculate_pension_withdrawal_allocation"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("calculator_tool", "calculator_args", "expected_calculator"),
    [
        (
            "calculate_pension_withdrawal_allocation",
            {
                "requested_withdrawal_krw": "500",
                "tax_free_source_balance_krw": "1000",
                "deferred_retirement_source_balance_krw": "0",
                "credited_and_earnings_source_balance_krw": "0",
                "requested_withdrawal_krw_source": "현재 인출 요청액 500원",
                "tax_free_source_balance_krw_source": (
                    "세액공제 미적용 원금 비과세 재원의 현재 잔액 1000원"
                ),
                "deferred_retirement_source_balance_krw_source": (
                    "이연퇴직소득 퇴직금 재원의 현재 잔액 0원"
                ),
                "credited_and_earnings_source_balance_krw_source": (
                    "세액공제 받은 원금·운용수익 재원의 현재 잔액 0원"
                ),
            },
            "pension_withdrawal_allocation",
        ),
        (
            "calculate_pension_withdrawal_tax_breakdown",
            {
                "requested_withdrawal_krw": "500",
                "tax_free_source_balance_krw": "0",
                "deferred_retirement_source_balance_krw": "0",
                "credited_and_earnings_source_balance_krw": "1000",
                "pension_treated_withdrawal_krw": "0",
                "non_pension_treated_withdrawal_krw": "500",
                "requested_withdrawal_krw_source": "현재 인출 요청액 500원",
                "tax_free_source_balance_krw_source": (
                    "세액공제 미적용 원금 비과세 재원의 현재 잔액 0원"
                ),
                "deferred_retirement_source_balance_krw_source": (
                    "이연퇴직소득 퇴직금 재원의 현재 잔액 0원"
                ),
                "credited_and_earnings_source_balance_krw_source": (
                    "세액공제 받은 원금·운용수익 재원의 현재 잔액 1000원"
                ),
                "pension_treated_withdrawal_krw_source": (
                    "현재 요청 중 연금수령으로 처리되는 금액 0원"
                ),
                "non_pension_treated_withdrawal_krw_source": (
                    "현재 요청 중 연금외수령으로 처리되는 금액 500원"
                ),
            },
            "pension_withdrawal_tax_breakdown",
        ),
    ],
)
async def test_tax_agent_runs_pension_withdrawal_paths(
    calculator_tool: str,
    calculator_args: dict[str, Any],
    expected_calculator: str,
) -> None:
    content = "; ".join(
        str(value) for key, value in calculator_args.items() if key.endswith("source")
    )
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE, content=content)],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "인출 계산"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": calculator_tool,
                        "args": calculator_args,
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "계산 결과를 적용합니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": ["550e8400-e29b-41d4-a716-446655440000"],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent({"question": content, "objective": "인출 계산"})

    assert result["calculations"][0]["calculator_id"] == expected_calculator
    assert result["calculations"][0]["input_sources"]
    assert result["evidence"]


def test_tax_agent_allows_only_submit_after_pension_installment_calculation() -> None:
    kept = _sequence_result_tool_names(
        calculations=[{"calculator_id": "pension_annual_limit_installment"}],
        tool_names=[
            "calculate_pension_period_installment",
            "calculate_pension_unit_installment",
            "submit_domain_result",
        ],
    )

    assert kept == ["submit_domain_result"]


@pytest.mark.anyio
async def test_tax_agent_runs_pension_annual_limit_installment_path() -> None:
    content = "올해 남은 연금수령한도 120만원; 올해 잔여 지급횟수 12회"
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.PENSION_REFERENCE,
                    title="당해연도 분할지급",
                    content=content,
                )
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "당해연도 분할지급 근거 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_pension_annual_limit_installment",
                        "args": {
                            "remaining_annual_limit_krw": "1200000",
                            "remaining_payments_in_year": 12,
                            "remaining_annual_limit_source": ("올해 남은 연금수령한도 120만원"),
                            "remaining_payments_in_year_source": ("올해 잔여 지급횟수 12회"),
                        },
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "당해연도 회당 지급액을 계산했습니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent({"question": "올해 회당 얼마씩 받아?", "objective": "회당 지급액 계산"})

    assert result["decision"]["status"] == "determined"
    assert "당해연도 잔여한도 기준 회당 지급액: 100000 KRW" in result["decision"]["conclusion"]
    assert result["calculations"][0]["calculator_id"] == ("pension_annual_limit_installment")


def test_pension_withdrawal_limit_presentation_distinguishes_not_applied() -> None:
    applied = format_calculation_summary(
        [
            {
                "calculator_id": "pension_withdrawal_limit",
                "inputs": {"account_valuation_krw": "10000000", "pension_year": 10},
                "input_sources": {},
                "outputs": {"withdrawal_limit": "12000000", "limit_applies": True},
                "units": {"withdrawal_limit": "KRW"},
                "warnings": [],
            }
        ]
    )
    not_applied = format_calculation_summary(
        [
            {
                "calculator_id": "pension_withdrawal_limit",
                "inputs": {"pension_year": 11},
                "input_sources": {},
                "outputs": {"withdrawal_limit": None, "limit_applies": False},
                "units": {"withdrawal_limit": "KRW"},
                "warnings": [],
            }
        ]
    )

    assert "연금수령한도: 12000000 KRW" in applied
    assert "11년차 이후로 연금수령한도가 적용되지 않습니다" in not_applied
    assert "0원" not in not_applied
    assert "None" not in not_applied


@pytest.mark.parametrize(
    ("calculator_id", "label"),
    [
        ("pension_annual_limit_installment", "당해연도 잔여한도 기준 회당 지급액"),
        ("pension_period_installment", "현재 평가액·전체 잔여회차 기준 회당 지급액"),
        ("pension_unit_installment", "잔고좌수·1,000좌당 기준가격 기준 회당 지급액"),
    ],
)
def test_pension_installment_presentations(calculator_id: str, label: str) -> None:
    summary = format_calculation_summary(
        [
            {
                "calculator_id": calculator_id,
                "inputs": {},
                "input_sources": {},
                "outputs": {"installment_krw": "0.3333333333333333333333333333"},
                "units": {"installment_krw": "KRW"},
                "warnings": [],
            }
        ]
    )

    assert f"{label}: 0.3333333333333333333333333333 KRW" in summary


@pytest.mark.anyio
async def test_tax_agent_preserves_both_pension_tax_comparison_results() -> None:
    content = (
        "일반 연금수령; 수령자 나이 55세; 비종신 연금; "
        "현재 연금수령 과세대상 금액 100만원; "
        "연간 사적연금 과세대상 합계 1,000만원; "
        "중도해지 운용수익 과세대상 금액 100만원"
    )
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(DocumentType.PENSION_REFERENCE, title="수령 방식별 과세", content=content)
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "수령 방식별 과세 비교"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_pension_income_tax",
                        "args": {
                            "pension_treatment": "ordinary",
                            "recipient_age": 55,
                            "pension_treatment_source": "일반 연금수령",
                            "recipient_age_source": "수령자 나이 55세",
                            "target_taxable_amount_krw": "1000000",
                            "target_taxable_amount_krw_source": (
                                "현재 연금수령 과세대상 금액 100만원"
                            ),
                            "is_lifetime_annuity": False,
                            "is_lifetime_annuity_source": "비종신 연금",
                            "annual_private_pension_taxable_income_krw": "10000000",
                            "annual_private_pension_taxable_income_krw_source": (
                                "연간 사적연금 과세대상 합계 1,000만원"
                            ),
                        },
                        "id": "pension-income-call",
                        "type": "tool_call",
                    },
                    {
                        "name": "calculate_non_pension_withdrawal_tax",
                        "args": {
                            "taxable_amount_krw": "1000000",
                            "taxable_amount_krw_source": (
                                "중도해지 운용수익 과세대상 금액 100만원"
                            ),
                        },
                        "id": "non-pension-call",
                        "type": "tool_call",
                    },
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "수령 방식별 결과를 비교합니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent(
        {"question": "연금수령과 중도해지 세금을 비교해줘", "objective": "세금 비교"}
    )

    assert {calculation["calculator_id"] for calculation in result["calculations"]} == {
        "pension_income_tax",
        "non_pension_withdrawal_tax",
    }
    assert len(result["calculations"]) == 2
    assert [evidence["chunk_id"] for evidence in result["evidence"]] == [
        "550e8400-e29b-41d4-a716-446655440000"
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("first_calculator", ["pension", "non_pension"])
async def test_tax_agent_defers_submit_until_remaining_comparison_calculation_finishes(
    first_calculator: str,
) -> None:
    content = (
        "일반 연금수령; 수령자 나이 55세; 비종신 연금; "
        "현재 연금수령 과세대상 금액 100만원; "
        "연간 사적연금 과세대상 합계 1,000만원; "
        "중도해지 운용수익 과세대상 금액 100만원"
    )
    pension_call = {
        "name": "calculate_pension_income_tax",
        "args": {
            "pension_treatment": "ordinary",
            "recipient_age": 55,
            "pension_treatment_source": "일반 연금수령",
            "recipient_age_source": "수령자 나이 55세",
            "target_taxable_amount_krw": "1000000",
            "target_taxable_amount_krw_source": "현재 연금수령 과세대상 금액 100만원",
            "is_lifetime_annuity": False,
            "is_lifetime_annuity_source": "비종신 연금",
            "annual_private_pension_taxable_income_krw": "10000000",
            "annual_private_pension_taxable_income_krw_source": (
                "연간 사적연금 과세대상 합계 1,000만원"
            ),
        },
        "id": "pension-call",
        "type": "tool_call",
    }
    non_pension_call = {
        "name": "calculate_non_pension_withdrawal_tax",
        "args": {
            "taxable_amount_krw": "1000000",
            "taxable_amount_krw_source": "중도해지 운용수익 과세대상 금액 100만원",
        },
        "id": "non-pension-call",
        "type": "tool_call",
    }
    first_call, remaining_call = (
        (pension_call, non_pension_call)
        if first_calculator == "pension"
        else (non_pension_call, pension_call)
    )
    premature_submit = {
        "name": "submit_domain_result",
        "args": {
            "status": "determined",
            "conclusion": "두 계산 결과를 비교합니다.",
            "missing_conditions": [],
            "warnings": [],
            "evidence_chunk_ids": [],
        },
        "id": "premature-submit-call",
        "type": "tool_call",
    }
    final_submit = {
        **premature_submit,
        "id": "final-submit-call",
    }
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(DocumentType.PENSION_REFERENCE, title="수령 방식별 과세", content=content)
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "수령 방식별 과세 비교"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="", tool_calls=[first_call]),
            AIMessage(content="", tool_calls=[remaining_call, premature_submit]),
            AIMessage(content="", tool_calls=[final_submit]),
        ]
    )
    agent = create_tax_payout_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent(
        {"question": "연금수령과 중도해지 세금을 비교해줘", "objective": "세금 비교"}
    )

    assert {calculation["calculator_id"] for calculation in result["calculations"]} == {
        "pension_income_tax",
        "non_pension_withdrawal_tax",
    }
    assert "일반 연금수령 적용 기본세율" in result["decision"]["conclusion"]
    assert "연금외수령 적용 기본세율" in result["decision"]["conclusion"]


def test_tax_agent_defers_submit_when_remaining_comparison_tool_is_requested() -> None:
    kept = _sequence_result_tool_names(
        calculations=[{"calculator_id": "pension_income_tax"}],
        tool_names=[
            "calculate_pension_withdrawal_limit",
            "calculate_non_pension_withdrawal_tax",
            "submit_domain_result",
        ],
    )

    assert kept == ["calculate_non_pension_withdrawal_tax"]


def test_tax_agent_allows_only_submit_after_both_comparison_calculations() -> None:
    kept = _sequence_result_tool_names(
        calculations=[
            {"calculator_id": "pension_income_tax"},
            {"calculator_id": "non_pension_withdrawal_tax"},
        ],
        tool_names=["calculate_pension_income_tax", "submit_domain_result"],
    )

    assert kept == ["submit_domain_result"]


def test_tax_agent_keeps_only_first_when_deferred_and_other_calculators_are_requested() -> None:
    kept = _sequence_result_tool_names(
        calculations=[],
        tool_names=[
            "calculate_deferred_retirement_withdrawal_tax",
            "calculate_pension_income_tax",
        ],
    )

    assert kept == ["calculate_deferred_retirement_withdrawal_tax"]


def test_tax_agent_allows_only_submit_after_deferred_retirement_calculation() -> None:
    kept = _sequence_result_tool_names(
        calculations=[{"calculator_id": "deferred_retirement_withdrawal_tax"}],
        tool_names=[
            "calculate_pension_income_tax",
            "calculate_deferred_retirement_withdrawal_tax",
            "submit_domain_result",
        ],
    )

    assert kept == ["submit_domain_result"]


def test_deferred_retirement_tax_presentation_omits_unavailable_amounts() -> None:
    summary = format_calculation_summary(
        [
            {
                "calculator_id": "deferred_retirement_withdrawal_tax",
                "inputs": {
                    "receipt_type": "pension",
                    "actual_pension_receipt_year": 10,
                },
                "input_sources": {},
                "outputs": {
                    "payable_ratio_percent": "70.00",
                    "reduction_ratio_percent": "30.00",
                },
                "units": {
                    "payable_ratio_percent": "%",
                    "reduction_ratio_percent": "%",
                },
                "warnings": [],
            }
        ]
    )

    assert "납부 비율: 70.00 %" in summary
    assert "감면 비율: 30.00 %" in summary
    assert "납부세액" not in summary
    assert "감면세액" not in summary
    assert "세후 인출액" not in summary
    assert "인출 원금" not in summary
    assert "계좌 전체" not in summary


def test_deferred_retirement_tax_presentation_preserves_zero_amounts() -> None:
    summary = format_calculation_summary(
        [
            {
                "calculator_id": "deferred_retirement_withdrawal_tax",
                "inputs": {
                    "receipt_type": "pension",
                    "actual_pension_receipt_year": 10,
                    "allocated_deferred_retirement_tax_krw": "0",
                },
                "input_sources": {},
                "outputs": {
                    "payable_ratio_percent": "70.00",
                    "reduction_ratio_percent": "30.00",
                    "tax_payable_krw": "0.00",
                    "tax_reduction_krw": "0.00",
                },
                "units": {
                    "payable_ratio_percent": "%",
                    "reduction_ratio_percent": "%",
                    "tax_payable_krw": "KRW",
                    "tax_reduction_krw": "KRW",
                },
                "warnings": [],
            }
        ]
    )

    assert "납부세액: 0.00 KRW" in summary
    assert "감면세액: 0.00 KRW" in summary
    assert "세후 인출액" not in summary
    assert "계좌 전체" not in summary


@pytest.mark.anyio
async def test_tax_agent_keeps_only_first_calculation_tool_when_two_are_requested() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.PENSION_REFERENCE,
                    title="연금수령한도",
                    content="평가액 1천만원, 수령연차 1년차에 대한 산식입니다.",
                )
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "연금수령한도 산식 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_pension_withdrawal_limit",
                        "args": {
                            "account_valuation_krw": "10000000",
                            "pension_year": 1,
                            "account_valuation_source": "평가액 1천만원",
                            "pension_year_source": "1년차",
                        },
                        "id": "withdrawal-call",
                        "type": "tool_call",
                    },
                    {
                        "name": "calculate_pension_tax_credit",
                        "args": {
                            "pension_savings_net_contribution_krw": "6000000",
                            "retirement_pension_net_contribution_krw": "3000000",
                            "pension_savings_isa_transfer_krw": "0",
                            "retirement_pension_isa_transfer_krw": "0",
                            "pension_savings_net_contribution_source": "연금저축 순납입액 600만원",
                            "retirement_pension_net_contribution_source": "퇴직연금 순납입액 300만원",
                            "pension_savings_isa_transfer_source": "연금저축 ISA 전환액 0원",
                            "retirement_pension_isa_transfer_source": "퇴직연금 ISA 전환액 0원",
                        },
                        "id": "tax-credit-call",
                        "type": "tool_call",
                    },
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "결과를 제출합니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": "연금수령한도는?", "objective": "연금수령한도 계산"})

    assert len(result["calculations"]) == 1
    assert result["calculations"][0]["calculator_id"] == "pension_withdrawal_limit"


@pytest.mark.anyio
async def test_tax_agent_allows_only_submit_after_a_calculation_is_recorded() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.PENSION_REFERENCE,
                    title="세액공제",
                    content=(
                        "연금저축 순납입액 600만원, 퇴직연금 순납입액 300만원 납입, "
                        "연금저축 ISA 전환액 0원, 퇴직연금 ISA 전환액 0원에 대한 "
                        "세액공제 규칙입니다."
                    ),
                )
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "세액공제 산식 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_pension_tax_credit",
                        "args": {
                            "pension_savings_net_contribution_krw": "6000000",
                            "retirement_pension_net_contribution_krw": "3000000",
                            "pension_savings_isa_transfer_krw": "0",
                            "retirement_pension_isa_transfer_krw": "0",
                            "pension_savings_net_contribution_source": "연금저축 순납입액 600만원",
                            "retirement_pension_net_contribution_source": "퇴직연금 순납입액 300만원",
                            "pension_savings_isa_transfer_source": "연금저축 ISA 전환액 0원",
                            "retirement_pension_isa_transfer_source": "퇴직연금 ISA 전환액 0원",
                        },
                        "id": "tax-credit-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_pension_withdrawal_limit",
                        "args": {
                            "account_valuation_krw": "10000000",
                            "pension_year": 1,
                            "account_valuation_source": "평가액 1천만원",
                            "pension_year_source": "1년차",
                        },
                        "id": "withdrawal-call",
                        "type": "tool_call",
                    },
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "결과를 제출합니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    },
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": "세액공제 대상액은?", "objective": "연금계좌 세액공제 계산"})

    assert len(result["calculations"]) == 1
    assert result["calculations"][0]["calculator_id"] == "pension_tax_credit"
    assert result["decision"]["status"] == "conditional"


def test_pension_tax_credit_summary_does_not_claim_usable_credit_is_refund() -> None:
    summary = format_calculation_summary(
        [
            {
                "calculator_id": "pension_tax_credit",
                "inputs": {
                    "pension_savings_net_contribution_krw": "6000000",
                    "retirement_pension_net_contribution_krw": "3000000",
                    "income_basis": "salary",
                    "income_amount_krw": "50000000",
                    "remaining_tax_before_pension_credit_krw": "1000000",
                },
                "input_sources": {},
                "outputs": {
                    "regular_eligible_contribution_krw": "9000000",
                    "isa_extra_remaining_cap_krw": "3000000",
                    "isa_extra_limit_krw": "0.00",
                    "isa_extra_eligible_contribution_krw": "0",
                    "eligible_contribution_krw": "9000000",
                    "credit_rate_percent": "16.5",
                    "theoretical_credit_krw": "1485000",
                    "usable_credit_krw": "1000000",
                },
                "units": {
                    "eligible_contribution_krw": "KRW",
                    "credit_rate_percent": "%",
                    "theoretical_credit_krw": "KRW",
                    "usable_credit_krw": "KRW",
                },
                "warnings": [],
            }
        ]
    )

    assert "환급액" not in summary
    assert "잔여 산출세액 기준 사용 가능 세액: 1000000 KRW" in summary
    assert "이론상 세액: 1485000 KRW" in summary
    assert "ISA" not in summary


def test_pension_tax_credit_summary_keeps_isa_section_when_extra_limit_is_zero() -> None:
    summary = format_calculation_summary(
        [
            {
                "calculator_id": "pension_tax_credit",
                "inputs": {
                    "pension_savings_net_contribution_krw": "36000000",
                    "retirement_pension_net_contribution_krw": "3000000",
                    "pension_savings_isa_transfer_krw": "30000000",
                    "prior_same_maturity_isa_extra_eligible_contribution_used_krw": ("3000000"),
                },
                "input_sources": {},
                "outputs": {
                    "regular_eligible_contribution_krw": "9000000",
                    "isa_extra_remaining_cap_krw": "0",
                    "isa_extra_limit_krw": "0.00",
                    "isa_extra_eligible_contribution_krw": "0",
                    "eligible_contribution_krw": "9000000",
                    "lower_income_rate_percent": "16.5",
                    "lower_income_theoretical_credit_krw": "1485000",
                    "other_income_rate_percent": "13.2",
                    "other_income_theoretical_credit_krw": "1188000",
                },
                "units": {
                    "eligible_contribution_krw": "KRW",
                    "isa_extra_limit_krw": "KRW",
                    "isa_extra_eligible_contribution_krw": "KRW",
                    "isa_extra_remaining_cap_krw": "KRW",
                },
                "warnings": [],
            }
        ]
    )

    assert "ISA 추가한도: 0.00 KRW" in summary
    assert "ISA 추가 공제대상액: 0 KRW" in summary
    assert "잔여 ISA 추가한도: 0 KRW" in summary


def _pension_tax_credit_rate_scenarios_calculation(
    *, extra_inputs: dict[str, Any] | None = None
) -> Any:
    return {
        "calculator_id": "pension_tax_credit",
        "inputs": {
            "pension_savings_net_contribution_krw": "6000000",
            "retirement_pension_net_contribution_krw": "3000000",
            **(extra_inputs or {}),
        },
        "input_sources": {},
        "outputs": {
            "eligible_contribution_krw": "9000000",
            "lower_income_rate_percent": "16.5",
            "lower_income_theoretical_credit_krw": "1485000",
            "other_income_rate_percent": "13.2",
            "other_income_theoretical_credit_krw": "1188000",
        },
        "units": {"eligible_contribution_krw": "KRW"},
        "warnings": [],
    }


def _pension_tax_credit_single_rate_calculation() -> Any:
    return {
        "calculator_id": "pension_tax_credit",
        "inputs": {
            "pension_savings_net_contribution_krw": "6000000",
            "retirement_pension_net_contribution_krw": "3000000",
            "income_basis": "salary",
            "income_amount_krw": "50000000",
        },
        "input_sources": {},
        "outputs": {
            "eligible_contribution_krw": "9000000",
            "credit_rate_percent": "16.5",
            "theoretical_credit_krw": "1485000",
        },
        "units": {"eligible_contribution_krw": "KRW"},
        "warnings": [],
    }


def test_pension_tax_credit_income_guard_overrides_determined_status_with_empty_missing() -> None:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    result = _build_tax_payout_result(
        search_result=SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE, chunk_id=chunk_id)],
        ),
        calculations=[_pension_tax_credit_rate_scenarios_calculation()],
        status="determined",
        conclusion="임의 결론",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[chunk_id],
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == [_INCOME_BASIS_MISSING_CONDITION]


def test_pension_tax_credit_income_guard_preserves_existing_missing_conditions() -> None:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    result = _build_tax_payout_result(
        search_result=SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE, chunk_id=chunk_id)],
        ),
        calculations=[_pension_tax_credit_rate_scenarios_calculation()],
        status="conditional",
        conclusion="임의 결론",
        missing_conditions=["기존 누락 조건"],
        warnings=[],
        evidence_chunk_ids=[chunk_id],
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == [
        "기존 누락 조건",
        _INCOME_BASIS_MISSING_CONDITION,
    ]


def test_pension_tax_credit_income_guard_does_not_duplicate_missing_condition() -> None:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    result = _build_tax_payout_result(
        search_result=SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE, chunk_id=chunk_id)],
        ),
        calculations=[_pension_tax_credit_rate_scenarios_calculation()],
        status="conditional",
        conclusion="임의 결론",
        missing_conditions=[_INCOME_BASIS_MISSING_CONDITION],
        warnings=[],
        evidence_chunk_ids=[chunk_id],
    )

    assert result["decision"]["missing_conditions"] == [_INCOME_BASIS_MISSING_CONDITION]


def test_pension_tax_credit_income_guard_keeps_model_status_when_income_provided() -> None:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    result = _build_tax_payout_result(
        search_result=SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE, chunk_id=chunk_id)],
        ),
        calculations=[_pension_tax_credit_single_rate_calculation()],
        status="determined",
        conclusion="임의 결론",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[chunk_id],
    )

    assert result["decision"]["status"] == "determined"
    assert result["decision"]["missing_conditions"] == []


def test_pension_tax_credit_income_guard_keeps_both_rate_scenario_summary() -> None:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    result = _build_tax_payout_result(
        search_result=SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE, chunk_id=chunk_id)],
        ),
        calculations=[_pension_tax_credit_rate_scenarios_calculation()],
        status="determined",
        conclusion="임의 결론",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[chunk_id],
    )

    conclusion = result["decision"]["conclusion"]
    assert "16.5%" in conclusion
    assert "13.2%" in conclusion
    assert result["calculations"] == [_pension_tax_credit_rate_scenarios_calculation()]


def _pension_income_calculation(
    *, threshold_status: str, filing_choice_required: bool | None = None
) -> Any:
    outputs: dict[str, Any] = {
        "base_rate_percent": "5.500",
        "annual_threshold_status": threshold_status,
    }
    inputs: dict[str, Any] = {
        "pension_treatment": "ordinary",
        "recipient_age": 55,
        "is_lifetime_annuity": False,
    }
    if threshold_status != "unknown":
        inputs["annual_private_pension_taxable_income_krw"] = "15000001"
    if filing_choice_required is not None:
        outputs["filing_choice_required"] = filing_choice_required
    if filing_choice_required:
        outputs.update(
            {
                "separate_tax_option_rate_percent": "16.5",
                "separate_tax_option_tax_krw": "2475000.165",
                "separate_tax_option_after_tax_krw": "12525000.835",
            }
        )
    return {
        "calculator_id": "pension_income_tax",
        "inputs": inputs,
        "input_sources": {},
        "outputs": outputs,
        "units": {"base_rate_percent": "%"},
        "warnings": [],
    }


def _build_result_with_calculations(
    calculations: list[Any],
    *,
    missing_conditions: list[str] | None = None,
    question: str = "",
) -> DomainResult:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    return _build_tax_payout_result(
        search_result=SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE, chunk_id=chunk_id)],
        ),
        calculations=calculations,
        question=question,
        status="determined",
        conclusion="임의 결론",
        missing_conditions=missing_conditions or [],
        warnings=[],
        evidence_chunk_ids=[chunk_id],
    )


def test_pension_income_unknown_annual_total_forces_conditional_status() -> None:
    result = _build_result_with_calculations(
        [_pension_income_calculation(threshold_status="unknown")]
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == [
        _ANNUAL_PRIVATE_PENSION_INCOME_MISSING_CONDITION
    ]
    assert all("금액" not in condition for condition in result["decision"]["missing_conditions"])


def test_pension_income_filing_choice_forces_conditional_status() -> None:
    result = _build_result_with_calculations(
        [_pension_income_calculation(threshold_status="exceeded", filing_choice_required=True)]
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == [
        _PENSION_TAX_FILING_CHOICE_MISSING_CONDITION
    ]


def test_pension_income_guards_preserve_and_deduplicate_missing_conditions() -> None:
    result = _build_result_with_calculations(
        [_pension_income_calculation(threshold_status="exceeded", filing_choice_required=True)],
        missing_conditions=["기존 조건", _PENSION_TAX_FILING_CHOICE_MISSING_CONDITION],
    )

    assert result["decision"]["missing_conditions"] == [
        "기존 조건",
        _PENSION_TAX_FILING_CHOICE_MISSING_CONDITION,
    ]


def test_non_pension_rate_only_does_not_force_missing_amount() -> None:
    calculation = {
        "calculator_id": "non_pension_withdrawal_tax",
        "inputs": {},
        "input_sources": {},
        "outputs": {"base_rate_percent": "16.5"},
        "units": {"base_rate_percent": "%"},
        "warnings": [],
    }

    result = _build_result_with_calculations([calculation])

    assert result["decision"]["status"] == "determined"
    assert result["decision"]["missing_conditions"] == []


def _withdrawal_calculation(
    calculator_id: str,
    *,
    outputs: dict[str, Any],
    inputs: dict[str, Any] | None = None,
) -> Any:
    return {
        "calculator_id": calculator_id,
        "inputs": inputs or {},
        "input_sources": {
            "requested_withdrawal_krw": {
                "origin": "question",
                "text": "요청 인출액 10원",
                "chunk_id": None,
            }
        },
        "outputs": outputs,
        "units": {key: "KRW" for key in outputs},
        "warnings": ["비과세 재원도 연금수령한도를 소진합니다."],
    }


def test_withdrawal_allocation_does_not_force_conditional_status() -> None:
    result = _build_result_with_calculations(
        [
            _withdrawal_calculation(
                "pension_withdrawal_allocation",
                inputs={"requested_withdrawal_krw": "10.25"},
                outputs={
                    "tax_free_withdrawal_krw": "10.25",
                    "tax_free_remaining_balance_krw": "89.75",
                    "deferred_retirement_withdrawal_krw": "0",
                    "deferred_retirement_remaining_balance_krw": "50",
                    "credited_and_earnings_withdrawal_krw": "0",
                    "credited_and_earnings_remaining_balance_krw": "25",
                },
            )
        ]
    )

    assert result["decision"]["status"] == "determined"
    assert "10.25" in result["decision"]["conclusion"]
    assert result["calculations"][0]["input_sources"]
    assert result["evidence"]


def test_withdrawal_breakdown_null_without_annual_total_forces_conditional() -> None:
    result = _build_result_with_calculations(
        [
            _withdrawal_calculation(
                "pension_withdrawal_tax_breakdown",
                outputs={
                    "credited_and_earnings_pension_withdrawal_krw": "10",
                    "credited_and_earnings_pension_tax_krw": None,
                    "credited_and_earnings_pension_after_tax_krw": None,
                    "current_withdrawal_tax_krw": None,
                    "current_withdrawal_after_tax_krw": None,
                },
            )
        ],
        missing_conditions=["기존 조건", _ANNUAL_PRIVATE_PENSION_INCOME_MISSING_CONDITION],
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == [
        "기존 조건",
        _ANNUAL_PRIVATE_PENSION_INCOME_MISSING_CONDITION,
    ]
    assert "확정할 수 없음" in result["decision"]["conclusion"]
    assert "None원" not in result["decision"]["conclusion"]
    assert "0원" not in result["decision"]["conclusion"]


def test_withdrawal_breakdown_separate_tax_option_forces_conditional() -> None:
    result = _build_result_with_calculations(
        [
            _withdrawal_calculation(
                "pension_withdrawal_tax_breakdown",
                inputs={"annual_private_pension_taxable_income_krw": "20000000"},
                outputs={
                    "credited_and_earnings_pension_withdrawal_krw": "10",
                    "credited_and_earnings_pension_tax_krw": None,
                    "credited_and_earnings_pension_after_tax_krw": None,
                    "current_withdrawal_tax_krw": None,
                    "current_withdrawal_after_tax_krw": None,
                    "annual_private_pension_separate_tax_option_tax_krw": "3300000.00",
                },
            )
        ],
        missing_conditions=["기존 조건", _PENSION_TAX_FILING_CHOICE_MISSING_CONDITION],
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == [
        "기존 조건",
        _PENSION_TAX_FILING_CHOICE_MISSING_CONDITION,
    ]
    conclusion = result["decision"]["conclusion"]
    assert "연간 전체 과세대상 사적연금소득 기준 16.5% 분리과세 선택세액" in conclusion
    assert "현재 인출 세액" not in conclusion
    assert "초과분 세액" not in conclusion
    assert "환급액" not in conclusion


def test_withdrawal_presentations_show_allocation_and_only_positive_breakdown_paths() -> None:
    allocation = _withdrawal_calculation(
        "pension_withdrawal_allocation",
        inputs={"requested_withdrawal_krw": "10.25"},
        outputs={
            "tax_free_withdrawal_krw": "10.25",
            "tax_free_remaining_balance_krw": "89.75",
            "deferred_retirement_withdrawal_krw": "0",
            "deferred_retirement_remaining_balance_krw": "50",
            "credited_and_earnings_withdrawal_krw": "0",
            "credited_and_earnings_remaining_balance_krw": "25",
        },
    )
    breakdown = _withdrawal_calculation(
        "pension_withdrawal_tax_breakdown",
        outputs={
            "tax_free_pension_withdrawal_krw": "10.25",
            "tax_free_pension_tax_krw": "0",
            "tax_free_pension_after_tax_krw": "10.25",
            "deferred_retirement_pension_withdrawal_krw": "0",
            "deferred_retirement_pension_tax_krw": "0",
            "deferred_retirement_pension_after_tax_krw": "0",
            "current_withdrawal_tax_krw": "0",
            "current_withdrawal_after_tax_krw": "10.25",
        },
    )

    summary = format_calculation_summary([allocation, breakdown])

    assert "요청 인출액: 10.25" in summary
    assert "비과세 재원 인출액: 10.25 KRW, 남은 잔액: 89.75 KRW" in summary
    assert "비과세 재원·연금 처리 인출액: 10.25 KRW" in summary
    assert "이연퇴직소득·연금 처리 인출액" not in summary
    assert "비과세 재원도 연금수령한도를 소진합니다." in breakdown["warnings"]


def test_pension_income_presentations_do_not_misstate_tax_meaning() -> None:
    summary = format_calculation_summary(
        [
            _pension_income_calculation(threshold_status="exceeded", filing_choice_required=True),
            {
                "calculator_id": "non_pension_withdrawal_tax",
                "inputs": {"taxable_amount_krw": "1000000"},
                "input_sources": {},
                "outputs": {
                    "base_rate_percent": "16.5",
                    "tax_krw": "165000.000",
                    "after_tax_krw": "835000.000",
                },
                "units": {
                    "base_rate_percent": "%",
                    "tax_krw": "KRW",
                    "after_tax_krw": "KRW",
                },
                "warnings": [],
            },
        ]
    )

    assert "연간 전체 과세대상 사적연금소득 기준 16.5% 분리과세 선택세액" in summary
    assert "세액공제 원금·운용수익의 연금외수령 적용 기본세율" in summary
    assert "종합과세 최종세액" not in summary
    assert "환급액" not in summary
    assert "초과분 세액" not in summary


@pytest.mark.anyio
async def test_product_agent_records_and_uses_verified_standard_price_calculation() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.FUND_PROSPECTUS,
                    source_file_name="R2_KR510902511M.pdf",
                    title="기준가격 산정방법",
                    content="순자산총액을 총좌수로 나누어 1,000좌당 기준가격을 계산합니다.",
                )
            ],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_product_codes",
                        "args": {},
                        "id": "lookup-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {
                            "objective": "기준가격 산정방법 확인",
                            "product_code": "KR510902511M",
                        },
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_fund_standard_price",
                        "args": {
                            "total_assets_krw": "1000000",
                            "total_liabilities_krw": "100000",
                            "total_units": "100000",
                            "total_assets_source": "자산 100만원",
                            "total_liabilities_source": "부채 10만원",
                            "total_units_source": "총좌수 10만좌",
                        },
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "임의 기준가격은 1원입니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": ["550e8400-e29b-41d4-a716-446655440000"],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_matcher=_product_matcher(),
    )

    result = await agent(
        {
            "question": "미래에셋 장기성장 상품의 자산 100만원, 부채 10만원, "
            "총좌수 10만좌일 때 기준가격은?",
            "objective": "펀드 기준가격 계산",
        }
    )

    assert result["decision"]["status"] == "determined"
    assert "9000.00 KRW/1,000 units" in result["decision"]["conclusion"]
    assert "1원" not in result["decision"]["conclusion"]
    assert result["calculations"][0]["calculator_id"] == "fund_standard_price"
    assert result["calculations"][0]["outputs"] == {"standard_price_per_1000_units": "9000.00"}


@pytest.mark.parametrize(
    ("builder", "document_type", "calculation"),
    [
        (
            _build_tax_payout_result,
            DocumentType.PENSION_REFERENCE,
            {
                "calculator_id": "pension_withdrawal_limit",
                "inputs": {"account_valuation_krw": "10000000", "pension_year": 1},
                "input_sources": {
                    "account_valuation_krw": {
                        "origin": "question",
                        "text": "평가액 1천만원",
                        "chunk_id": None,
                    },
                    "pension_year": {
                        "origin": "question",
                        "text": "1년차",
                        "chunk_id": None,
                    },
                },
                "outputs": {"withdrawal_limit": "1200000.0"},
                "units": {"withdrawal_limit": "KRW"},
                "warnings": [],
            },
        ),
        (
            _build_product_result,
            DocumentType.FUND_PROSPECTUS,
            {
                "calculator_id": "fund_standard_price",
                "inputs": {
                    "total_assets_krw": "1000000",
                    "total_liabilities_krw": "100000",
                    "total_units": "100000",
                },
                "input_sources": {
                    "total_assets_krw": {
                        "origin": "question",
                        "text": "자산 100만원",
                        "chunk_id": None,
                    },
                    "total_liabilities_krw": {
                        "origin": "question",
                        "text": "부채 10만원",
                        "chunk_id": None,
                    },
                    "total_units": {
                        "origin": "question",
                        "text": "총좌수 10만좌",
                        "chunk_id": None,
                    },
                },
                "outputs": {"standard_price_per_1000_units": "9000.00"},
                "units": {"standard_price_per_1000_units": "KRW/1,000 units"},
                "warnings": [],
            },
        ),
    ],
)
def test_partial_calculation_preserves_missing_conditions(
    builder: Callable[..., DomainResult],
    document_type: DocumentType,
    calculation: Any,
) -> None:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    result = builder(
        search_result=SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(document_type, chunk_id=chunk_id)],
        ),
        calculations=[calculation],
        status="conditional",
        conclusion="지원되는 항목만 계산했습니다.",
        missing_conditions=["지원되지 않은 추가 계산식"],
        warnings=[],
        evidence_chunk_ids=[chunk_id],
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == ["지원되지 않은 추가 계산식"]
    assert "검증된 Python 계산 결과" in result["decision"]["conclusion"]
    validate_domain_result(result)


@pytest.mark.anyio
async def test_tax_agent_keeps_conclusion_when_only_missing_or_warnings_have_numbers() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
            limitations=["한도는 900만원입니다.", "자료 범위가 제한적입니다."],
        )
    )
    conclusion = (
        "가입 유형에 따라 세액공제 조건이 달라지며, 자세한 조건은 근거 문서를 확인해야 합니다."
    )
    model = _model(
        conclusion=conclusion,
        missing_conditions=["연봉 5천만원 여부"],
        warnings=["세율은 10%입니다.", "일반적인 주의가 필요합니다."],
    )
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )
    result = await agent({"question": "공제 조건은?", "objective": "공제 조건 판단"})

    serialized = str(result)
    assert result["decision"]["status"] == "determined"
    assert result["decision"]["conclusion"] == conclusion
    assert result["decision"]["missing_conditions"] == []
    assert "10%" not in serialized
    assert "900만원" not in serialized
    assert "5천만원" not in serialized
    assert "일반적인 주의가 필요합니다." in result["warnings"]
    assert "자료 범위가 제한적입니다." in result["warnings"]
    assert "근거 없이 제출된 확정 수치는 결과에서 제거했습니다." in result["warnings"]
    assert model.invocation_count == 2


@pytest.mark.anyio
async def test_tax_agent_undetermined_uses_generic_missing_condition_when_all_are_numeric() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
        )
    )
    agent = create_tax_payout_agent(
        model=_model(
            decision_status="undetermined",
            conclusion="정확한 초과분은 확인이 어렵습니다.",
            missing_conditions=["초과분 900만원 여부"],
        ),
        search_service=cast(SearchRunner, search),
    )
    result = await agent(
        {
            "question": "연금수령한도를 초과하면 어떻게 과세되나요?",
            "objective": "연금수령한도 초과 과세 판단",
        }
    )

    assert result["decision"]["status"] == "undetermined"
    assert result["decision"]["conclusion"] == "정확한 초과분은 확인이 어렵습니다."
    assert result["decision"]["missing_conditions"] == ["제공 문서의 관련 근거 또는 필수 조건"]


@pytest.mark.anyio
async def test_tax_agent_conditional_missing_falls_back_to_user_condition() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
        )
    )
    conclusion = "가입 기간과 연령 조건을 충족하는지에 따라 과세 여부가 달라집니다."
    agent = create_tax_payout_agent(
        model=_model(
            decision_status="conditional",
            conclusion=conclusion,
            missing_conditions=["55세 이상 여부"],
        ),
        search_service=cast(SearchRunner, search),
    )
    result = await agent(
        {"question": "55세에 연금을 받으면 세율이 어떻게 되나요?", "objective": "연령별 세율 판단"}
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["conclusion"] == conclusion
    assert result["decision"]["missing_conditions"] == ["판단에 필요한 사용자 조건"]
    assert "결정론적 계산 Tool 결과" not in result["decision"]["missing_conditions"]
    assert "근거 없이 제출된 확정 수치는 결과에서 제거했습니다." in result["warnings"]
    assert "계산 Tool 없이 세금·금액·세율·한도를 확정하지 않았습니다." not in result["warnings"]


@pytest.mark.anyio
async def test_tax_agent_does_not_treat_topic_words_alone_as_numeric_claim() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
        )
    )
    conclusion = "적용 세율과 공제 한도는 가입 유형과 소득 구간에 따라 달라집니다."
    agent = create_tax_payout_agent(
        model=_model(conclusion=conclusion),
        search_service=cast(SearchRunner, search),
    )
    result = await agent(
        {"question": "세율과 한도는 어떻게 정해지나요?", "objective": "세율·한도 결정 조건 판단"}
    )

    assert result["decision"]["status"] == "determined"
    assert result["decision"]["conclusion"] == conclusion


@pytest.mark.anyio
async def test_tax_agent_numeric_claim_does_not_upgrade_undetermined_to_conditional() -> None:
    chunk = _chunk(DocumentType.PENSION_REFERENCE)
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "중도해지 과세 근거 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "undetermined",
                            "conclusion": (
                                "중도해지 시 세금이 부과되나 정확한 금액은 10% 내외로 다양합니다."
                            ),
                            "missing_conditions": ["가입 기간"],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "first-submit",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "undetermined",
                            "conclusion": ("정확한 금액은 여전히 10% 내외로 확정하기 어렵습니다."),
                            "missing_conditions": ["가입 기간"],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "second-submit",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )
    result = await agent(
        {"question": "중도해지하면 세금이 얼마나 나오나요?", "objective": "중도해지 과세 판단"}
    )

    assert result["decision"]["status"] == "undetermined"
    assert result["decision"]["conclusion"] == (
        "제공 근거만으로는 확정 수치를 포함한 결론을 판단할 수 없습니다."
    )
    assert result["decision"]["missing_conditions"] == ["가입 기간"]
    assert "10%" not in str(result)
    assert "결정론적 계산 Tool 결과" not in result["decision"]["missing_conditions"]
    assert "계산 Tool 없이 세금·금액·세율·한도를 확정하지 않았습니다." not in result["warnings"]
    assert "근거 없이 제출된 확정 수치는 결과에서 제거했습니다." in result["warnings"]
    assert model.invocation_count == 3


@pytest.mark.anyio
async def test_tax_agent_not_applicable_is_not_overridden_by_numeric_guard() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
        )
    )
    agent = create_tax_payout_agent(
        model=_model(
            decision_status="not_applicable",
            conclusion="이 펀드의 위험 등급은 3등급이며 보수는 연 1.5%입니다.",
            warnings=["최근 수익률은 10%였습니다."],
        ),
        search_service=cast(SearchRunner, search),
    )
    result = await agent({"question": "이 펀드의 위험은?", "objective": "펀드 위험 판단"})

    assert result["decision"] == {
        "status": "not_applicable",
        "conclusion": "이 질문에는 해당 도메인 판단이 적용되지 않습니다.",
        "missing_conditions": [],
    }
    assert result["warnings"] == []
    assert result["evidence"] == []


@pytest.mark.anyio
async def test_tax_agent_not_applicable_accepted_without_search() -> None:
    search = FakeSearchService(SearchResult(execution_status="completed"))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "not_applicable",
                            "conclusion": "이 펀드의 위험은 Product Agent의 책임입니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": "이 펀드의 위험은?", "objective": "펀드 위험 판단"})

    assert result["execution_status"] == "completed"
    assert result["decision"] == {
        "status": "not_applicable",
        "conclusion": "이 질문에는 해당 도메인 판단이 적용되지 않습니다.",
        "missing_conditions": [],
    }
    assert result["evidence"] == []
    assert result["warnings"] == []
    assert search.calls == []
    assert model.invocation_count == 1


@pytest.mark.anyio
async def test_tax_agent_determined_still_requires_search_before_submit() -> None:
    chunk = _chunk(DocumentType.PENSION_REFERENCE)
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    conclusion = "가입 유형에 따라 세액공제 조건이 달라집니다."
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": conclusion,
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [],
                        },
                        "id": "early-submit",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "세액공제 조건 근거 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": conclusion,
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": "세액공제 조건은?", "objective": "세액공제 조건 판단"})

    assert result["decision"]["status"] == "determined"
    assert len(search.calls) == 1
    assert model.invocation_count == 3


@pytest.mark.anyio
async def test_tax_agent_accepts_qualitative_resubmit_after_numeric_conclusion() -> None:
    chunk = _chunk(DocumentType.PENSION_REFERENCE)
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    qualitative_conclusion = "소득 기준과 납입 한도를 충족해야 세액공제를 받을 수 있습니다."
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "세액공제 조건 근거 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "세액공제율은 16.5%입니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "numeric-submit",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": qualitative_conclusion,
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "qualitative-submit",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": "세액공제 조건은?", "objective": "세액공제 조건 판단"})

    assert result["decision"]["status"] == "determined"
    assert result["decision"]["conclusion"] == qualitative_conclusion
    assert "16.5" not in str(result)
    assert len(search.calls) == 1
    assert model.invocation_count == 3


@pytest.mark.anyio
async def test_not_applicable_result_cannot_expose_substantive_ungrounded_conclusion() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
        )
    )
    agent = create_policy_agent(
        model=_model(
            decision_status="not_applicable",
            conclusion="연금 이전은 언제나 가능합니다.",
            warnings=["반드시 이전하세요."],
        ),
        search_service=cast(SearchRunner, search),
    )
    result = await agent({"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"})

    assert result["decision"] == {
        "status": "not_applicable",
        "conclusion": "이 질문에는 해당 도메인 판단이 적용되지 않습니다.",
        "missing_conditions": [],
    }
    assert result["warnings"] == []
    assert result["evidence"] == []


@pytest.mark.anyio
async def test_domain_agent_waits_for_capacity_instead_of_failing_fast() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    class BlockingRunner:
        async def __call__(
            self,
            request: dict[str, str],
            *,
            deadline: float | None = None,
        ) -> DomainResult:
            del request
            assert deadline is not None
            assert deadline > asyncio.get_running_loop().time()
            started.set()
            await release.wait()
            return _completed_result()

    agent = GuardedDomainRunner(
        domain="policy",
        implementation=cast(DomainRunner, BlockingRunner()),
        max_concurrency=1,
    )
    request = {"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"}
    first_task = asyncio.create_task(agent(request))
    await started.wait()
    second_task = asyncio.create_task(agent(request))
    await asyncio.sleep(0)
    assert not second_task.done()
    release.set()
    first, second = await asyncio.gather(first_task, second_task)

    assert first["execution_status"] == "completed"
    assert second["execution_status"] == "completed"


@pytest.mark.anyio
async def test_domain_agent_capacity_wait_respects_parent_deadline() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    class BlockingRunner:
        async def __call__(
            self,
            request: dict[str, str],
            *,
            deadline: float | None = None,
        ) -> DomainResult:
            del request, deadline
            started.set()
            await release.wait()
            return _completed_result()

    agent = GuardedDomainRunner(
        domain="policy",
        implementation=cast(DomainRunner, BlockingRunner()),
        max_concurrency=1,
    )
    request = {"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"}
    first_task = asyncio.create_task(agent(request))
    await started.wait()

    second = await agent(
        request,
        deadline=asyncio.get_running_loop().time() + 0.01,
    )
    release.set()
    first = await first_task

    assert first["execution_status"] == "completed"
    assert second["execution_status"] == "timeout"


@pytest.mark.anyio
async def test_domain_agent_does_not_start_implementation_after_parent_deadline() -> None:
    class UnexpectedRunner:
        async def __call__(
            self,
            request: dict[str, str],
            *,
            deadline: float | None = None,
        ) -> DomainResult:
            raise AssertionError((request, deadline))

    agent = GuardedDomainRunner(
        domain="policy",
        implementation=cast(DomainRunner, UnexpectedRunner()),
    )

    result = await agent(
        {"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"},
        deadline=asyncio.get_running_loop().time() - 1,
    )

    assert result["execution_status"] == "timeout"


@pytest.mark.anyio
async def test_domain_agent_timeout_cancels_implementation_and_releases_capacity() -> None:
    cancelled = asyncio.Event()

    class TimeoutOnceRunner:
        calls = 0

        async def __call__(
            self,
            request: dict[str, str],
            *,
            deadline: float | None = None,
        ) -> DomainResult:
            del request, deadline
            self.calls += 1
            if self.calls == 1:
                try:
                    await asyncio.sleep(10)
                finally:
                    cancelled.set()
            return _completed_result()

    agent = GuardedDomainRunner(
        domain="policy",
        implementation=cast(DomainRunner, TimeoutOnceRunner()),
        config=DomainAgentConfig(timeout_seconds=0.01, max_concurrency=1),
    )
    request = {"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"}

    first = await agent(request)
    second = await agent(request)

    assert first["execution_status"] == "timeout"
    assert cancelled.is_set()
    assert second["execution_status"] == "completed"


@pytest.mark.anyio
async def test_domain_agent_external_cancellation_releases_capacity() -> None:
    started = asyncio.Event()

    class CancellableRunner:
        block = True

        async def __call__(
            self,
            request: dict[str, str],
            *,
            deadline: float | None = None,
        ) -> DomainResult:
            del request, deadline
            if self.block:
                started.set()
                await asyncio.sleep(10)
            return _completed_result()

    runner = CancellableRunner()
    agent = GuardedDomainRunner(
        domain="policy",
        implementation=cast(DomainRunner, runner),
        max_concurrency=1,
    )
    request = {"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"}
    task = asyncio.create_task(agent(request))
    await started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    runner.block = False

    result = await agent(request)

    assert result["execution_status"] == "completed"


@pytest.mark.anyio
async def test_domain_agent_propagates_tracing_context_to_async_implementation() -> None:
    observed_parent_ids: list[UUID | None] = []

    class ContextRecordingRunner:
        async def __call__(
            self,
            request: dict[str, str],
            *,
            deadline: float | None = None,
        ) -> DomainResult:
            del request, deadline
            current_run = get_current_run_tree()
            observed_parent_ids.append(current_run.id if current_run is not None else None)
            return _completed_result()

    agent = GuardedDomainRunner(
        domain="policy",
        implementation=cast(DomainRunner, ContextRecordingRunner()),
        max_concurrency=1,
    )
    parents = [
        RunTree(
            name=f"request-{index}",
            inputs={},
            project_name="unit-test",
            ls_client=object(),
        )
        for index in range(2)
    ]
    for parent in parents:
        with tracing_context(parent=parent, enabled=False):
            result = await agent(
                {"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"}
            )

    assert result["execution_status"] == "completed"
    assert observed_parent_ids == [parent.id for parent in parents]


def _completed_result() -> DomainResult:
    return {
        "domain": "policy",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": "이전할 수 있습니다.",
            "missing_conditions": [],
        },
        "evidence": [],
        "calculations": [],
        "warnings": [],
    }


def test_domain_prompts_are_packaged_and_limit_numeric_generation_to_tools() -> None:
    policy_prompt = load_policy_agent_prompt()
    assert "search_documents" in policy_prompt
    product_prompt = load_product_agent_prompt()
    assert "search_documents" in product_prompt
    assert "lookup_product_codes" in product_prompt
    assert "`product_code` 없이 `search_documents`" in product_prompt
    assert "전체 검색을 먼저 했다면 다음 단계에서 반드시 `lookup_product_codes`" in product_prompt
    assert "특정 상품의 최종 근거로 바로 제출하지 않는다" in product_prompt
    assert "문서 근거 검색에 적합한 구체적인 `objective`로 재작성한다" in product_prompt
    assert "누락된 판단 기준과 다른 문서 용어" in product_prompt
    assert "calculate_fund_standard_price" in product_prompt
    assert "calculate_fund_var_risk" in product_prompt
    assert "2회" not in product_prompt
    assert "두 번" not in product_prompt
    assert '"product_code":"KR510902511M"' not in product_prompt
    assert "{{PRODUCT_CATALOG_JSON}}" not in product_prompt
    tax_prompt = load_tax_payout_agent_prompt()
    assert "calculate_pension_withdrawal_limit" in tax_prompt
    assert "calculate_pension_annual_limit_installment" in tax_prompt
    assert "calculate_pension_period_installment" in tax_prompt
    assert "calculate_pension_unit_installment" in tax_prompt
    assert "올해 남은 연금수령한도" in tax_prompt
    assert "전체 기간 잔여회차" in tax_prompt
    assert "1,000좌당 기준가격" in tax_prompt
    assert "11년차 이후에는 연금수령한도가 적용되지 않으며" in tax_prompt
    assert "calculate_pension_tax_credit" in tax_prompt
    assert "calculate_pension_withdrawal_allocation" in tax_prompt
    assert "calculate_pension_withdrawal_tax_breakdown" in tax_prompt
    assert "재원별 인출 순서·배분만 필요" in tax_prompt
    assert "그 전에 `calculate_pension_withdrawal_allocation`을 호출하지 않는다" in tax_prompt
    assert "두 #115 Tool을 동시에 또는 연속 호출하지 않는다" in tax_prompt
    assert "지원하지 않는 세금, 금액, 세율이나 한도를 직접 계산하지 않는다" in tax_prompt
    assert "submit_domain_result" in tax_prompt
    assert "Product Agent 책임이므로" in tax_prompt
    assert "Policy Agent 책임이므로" in tax_prompt
    assert "검색된 청크 전체가 아니라 결론에 실제 인용한 최소" in tax_prompt
    assert "근거 부족 판단을 계산 필요 판단으로 바꾸지 않는다" in tax_prompt
    assert "calculate_dc_medical_withdrawal_threshold" in policy_prompt
    assert "6개월 이상 요양" in policy_prompt
    assert "IRP" in policy_prompt
    assert "calculate_medical_care_withdrawal_tax_limit" in tax_prompt
    assert "calculate_medical_care_withdrawal_tax_breakdown" in tax_prompt
    assert "3개월 이상 요양" in tax_prompt
    assert "그 전에 limit 또는 `calculate_pension_income_tax`를 호출하지 않는다" in tax_prompt


def _policy_sequence_tool_names(calculations: list[Any], tool_names: list[str]) -> list[str]:
    message = AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": {}, "id": f"call-{index}", "type": "tool_call"}
            for index, name in enumerate(tool_names)
        ],
    )
    update = EnforcePolicyToolSequence().after_model(
        {
            "messages": [message],
            "search_result": SearchResult(execution_status="completed"),
            "calculations": calculations,
        },
        None,
    )
    kept = message if update is None else update["messages"][0]
    return [call["name"] for call in kept.tool_calls]


def test_policy_separates_dc_threshold_submit_and_blocks_after_success() -> None:
    assert _policy_sequence_tool_names(
        [], ["calculate_dc_medical_withdrawal_threshold", "submit_domain_result"]
    ) == ["calculate_dc_medical_withdrawal_threshold"]
    assert _policy_sequence_tool_names(
        [{"calculator_id": "dc_medical_withdrawal_threshold"}],
        ["calculate_dc_medical_withdrawal_threshold", "submit_domain_result"],
    ) == ["submit_domain_result"]


def _dc_threshold_calculation() -> Any:
    return {
        "calculator_id": "dc_medical_withdrawal_threshold",
        "inputs": {"employment_duration_category": "at_least_one_year"},
        "input_sources": {},
        "outputs": {
            "applicable_wages_krw": "100000000",
            "wage_basis": "previous_year_annual_wages",
            "medical_expense_threshold_krw": "12500000.000",
            "threshold_met": True,
        },
        "units": {
            "applicable_wages_krw": "KRW",
            "medical_expense_threshold_krw": "KRW",
        },
        "warnings": [],
    }


def test_policy_dc_threshold_requires_separate_eligibility_confirmation() -> None:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    result = _build_policy_result(
        search_result=SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE, chunk_id=chunk_id)],
        ),
        calculations=[_dc_threshold_calculation()],
        status="determined",
        conclusion="임금 기준을 초과했습니다.",
        missing_conditions=["기존 조건"],
        warnings=[],
        evidence_chunk_ids=[chunk_id],
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == [
        "기존 조건",
        _DC_ELIGIBILITY_MISSING_CONDITION,
    ]
    assert result["calculations"] == [_dc_threshold_calculation()]
    assert "DC 의료비 기준 적용 임금" in result["decision"]["conclusion"]


def _medical_care_calculation(
    calculator_id: str, *, excess: str = "0", null_totals: bool = False
) -> Any:
    outputs: dict[str, Any] = {
        "tax_limit_krw": "2750000",
        "amount_within_limit_krw": "2750000",
        "excess_amount_krw": excess,
    }
    if calculator_id == "medical_care_withdrawal_tax_breakdown":
        outputs.update(
            {
                "within_limit_tax_rate_percent": "5.5",
                "within_limit_tax_krw": "151250.000",
                "within_limit_after_tax_krw": "2598750.000",
                "current_withdrawal_tax_krw": None if null_totals else "151250.000",
                "current_withdrawal_after_tax_krw": (None if null_totals else "2598750.000"),
            }
        )
    return {
        "calculator_id": calculator_id,
        "inputs": {"requested_withdrawal_krw": "2750000"},
        "input_sources": {},
        "outputs": outputs,
        "units": {key: "%" if key == "within_limit_tax_rate_percent" else "KRW" for key in outputs},
        "warnings": ["초과액 세액을 확정할 수 없습니다."] if null_totals else [],
    }


def test_medical_care_limit_status_depends_on_question_intent() -> None:
    calculation = _medical_care_calculation("medical_care_withdrawal_tax_limit")
    pure_limit = _build_result_with_calculations(
        [calculation], question="의료·요양 저율과세 한도가 얼마인가요?"
    )
    tax_question = _build_result_with_calculations(
        [calculation],
        missing_conditions=["기존 조건", _RECIPIENT_AGE_MISSING_CONDITION],
        question="의료·요양 인출의 세액과 세후액은 얼마인가요?",
    )

    assert pure_limit["decision"]["status"] == "determined"
    assert pure_limit["decision"]["missing_conditions"] == []
    assert tax_question["decision"]["status"] == "conditional"
    assert tax_question["decision"]["missing_conditions"] == [
        "기존 조건",
        _RECIPIENT_AGE_MISSING_CONDITION,
    ]


def test_medical_care_excess_forces_conditional_and_preserves_nulls() -> None:
    result = _build_result_with_calculations(
        [
            _medical_care_calculation(
                "medical_care_withdrawal_tax_breakdown", excess="250000", null_totals=True
            )
        ],
        question="의료·요양 인출 세액은 얼마인가요?",
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == [_MEDICAL_CARE_EXCESS_MISSING_CONDITION]
    outputs = result["calculations"][0]["outputs"]
    assert outputs["current_withdrawal_tax_krw"] is None
    assert outputs["current_withdrawal_after_tax_krw"] is None
    assert "확정할 수 없음" in result["decision"]["conclusion"]
    assert "None원" not in result["decision"]["conclusion"]


def test_tax_sequence_enforces_single_medical_care_tool_and_submit_after_success() -> None:
    assert _sequence_result_tool_names(
        calculations=[],
        tool_names=[
            "calculate_medical_care_withdrawal_tax_breakdown",
            "calculate_medical_care_withdrawal_tax_limit",
        ],
    ) == ["calculate_medical_care_withdrawal_tax_breakdown"]
    assert _sequence_result_tool_names(
        calculations=[], tool_names=["calculate_medical_care_withdrawal_tax_limit"]
    ) == ["calculate_medical_care_withdrawal_tax_limit"]
    assert _sequence_result_tool_names(
        calculations=[{"calculator_id": "medical_care_withdrawal_tax_breakdown"}],
        tool_names=[
            "calculate_pension_income_tax",
            "calculate_deferred_retirement_withdrawal_tax",
            "calculate_pension_withdrawal_tax_breakdown",
            "calculate_pension_withdrawal_limit",
            "submit_domain_result",
        ],
    ) == ["submit_domain_result"]


def test_medical_care_presentations_do_not_render_null_as_amount() -> None:
    summary = format_calculation_summary(
        [
            _dc_threshold_calculation(),
            _medical_care_calculation("medical_care_withdrawal_tax_limit"),
            _medical_care_calculation(
                "medical_care_withdrawal_tax_breakdown", excess="250000", null_totals=True
            ),
        ]
    )

    assert "임금 기준액의 12.5%" in summary
    assert "의료·요양 저율과세 한도" in summary
    assert "현재 전체 세액: 확정할 수 없음" in summary
    assert "None원" not in summary


@pytest.mark.anyio
async def test_policy_agent_runs_dc_threshold_and_preserves_calculation_evidence() -> None:
    chunk = _chunk(DocumentType.PENSION_REFERENCE)
    content = "재직 1년 이상; 근로자 부담 증빙 의료비 1,300만원; 직전연도 연간임금총액 1억원"
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "DC 의료비 중도인출 기준 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_dc_medical_withdrawal_threshold",
                        "args": {
                            "employment_duration_category": "at_least_one_year",
                            "documented_medical_expenses_krw": "13000000",
                            "employment_duration_category_source": "재직 1년 이상",
                            "documented_medical_expenses_krw_source": (
                                "근로자 부담 증빙 의료비 1,300만원"
                            ),
                            "previous_year_annual_wages_krw": "100000000",
                            "previous_year_annual_wages_krw_source": (
                                "직전연도 연간임금총액 1억원"
                            ),
                        },
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "임금 기준을 초과합니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                            "dc_medical_eligibility_conditions_confirmed": False,
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_policy_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent({"question": content, "objective": "DC 의료비 인출 가능 여부"})

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == [_DC_ELIGIBILITY_MISSING_CONDITION]
    assert result["calculations"][0]["calculator_id"] == "dc_medical_withdrawal_threshold"
    assert result["calculations"][0]["input_sources"]
    assert result["evidence"]


@pytest.mark.anyio
async def test_policy_agent_does_not_call_dc_threshold_for_irp_question() -> None:
    chunk = _chunk(DocumentType.PENSION_REFERENCE)
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "IRP 의료비 중도인출 조건 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "conditional",
                            "conclusion": "IRP의 다른 중도인출 요건을 확인해야 합니다.",
                            "missing_conditions": ["IRP 중도인출의 나머지 적용 요건"],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_policy_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent(
        {"question": "IRP 의료비 중도인출이 가능한가요?", "objective": "가능 여부"}
    )

    assert result["decision"]["status"] == "conditional"
    assert result["calculations"] == []
    assert model.invocation_count == 2


@pytest.mark.anyio
async def test_tax_agent_runs_pure_medical_care_limit_as_determined() -> None:
    chunk = _chunk(DocumentType.PENSION_REFERENCE)
    content = "의료·요양 총 인출 요청액 300만원; 실제 의료비 50만원; 간병비 25만원; 본인 휴직 0개월"
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "의료·요양 저율과세 한도 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_medical_care_withdrawal_tax_limit",
                        "args": {
                            "requested_withdrawal_krw": "3000000",
                            "actual_medical_expenses_krw": "500000",
                            "care_expenses_krw": "250000",
                            "own_leave_months": 0,
                            "requested_withdrawal_krw_source": ("의료·요양 총 인출 요청액 300만원"),
                            "actual_medical_expenses_krw_source": "실제 의료비 50만원",
                            "care_expenses_krw_source": "간병비 25만원",
                            "own_leave_months_source": "본인 휴직 0개월",
                        },
                        "id": "calculation-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "한도를 계산했습니다.",
                            "missing_conditions": [],
                            "warnings": [],
                            "evidence_chunk_ids": [chunk.chunk_id],
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = create_tax_payout_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent({"question": content, "objective": "저율과세 한도 계산"})

    assert result["decision"]["status"] == "determined"
    assert result["calculations"][0]["calculator_id"] == "medical_care_withdrawal_tax_limit"
    assert "의료·요양 저율과세 한도" in result["decision"]["conclusion"]
