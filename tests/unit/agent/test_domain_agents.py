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
from pension_agent.agent.product.react import (
    _FUND_CLASS_MISSING_CONDITION,
    _LATEST_DISCLOSURE_MISSING_CONDITION,
    EnforceProductToolSequence,
    _build_product_result,
    _product_tool_call_is_allowed,
    _product_var_missing_conditions,
    _reported_var_call_missing_condition,
)
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
            "calculate_fund_reported_var_risk",
            "calculate_fund_var_risk",
            "calculate_fund_frontend_sales_fee",
            "calculate_fund_deferred_sales_fee",
            "calculate_fund_redemption_fee",
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
    expected_objective = (
        "이전 가능 여부의 문서 근거 확인"
        if domain == "product"
        else "이전 가능 여부 판단\n이전 가능 여부의 문서 근거 확인"
    )
    expected_request = SearchRequest(
        objective=expected_objective,
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
    assert domain == "policy" or all(
        set(names)
        == (
            {
                "lookup_product_codes",
                "search_documents",
                "calculate_fund_standard_price",
                "calculate_fund_reported_var_risk",
                "calculate_fund_var_risk",
                "calculate_fund_frontend_sales_fee",
                "calculate_fund_deferred_sales_fee",
                "calculate_fund_redemption_fee",
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
                    "calculate_db_retirement_benefit",
                    "calculate_dc_minimum_employer_contribution",
                    "calculate_dc_retirement_benefit",
                    "calculate_db_to_dc_transfer_amount",
                    "calculate_executive_retirement_income_limit",
                    "submit_domain_result",
                }
                if domain == "tax_payout"
                else {
                    "search_documents",
                    "calculate_dc_medical_withdrawal_threshold",
                    "calculate_isa_transfer_deadline",
                    "submit_domain_result",
                }
            )
        )
        for names, _kwargs in model.bindings
    )
    if domain == "policy":
        assert [(names, kwargs.get("tool_choice")) for names, kwargs in model.bindings] == [
            (["search_documents", "submit_domain_result"], None),
            (
                [
                    "search_documents",
                    "calculate_dc_medical_withdrawal_threshold",
                    "calculate_isa_transfer_deadline",
                    "submit_domain_result",
                ],
                None,
            ),
        ]
    if domain == "product":
        assert model.tool_argument_names["lookup_product_codes"] == set()
        assert model.tool_argument_names["search_documents"] == {
            "objective",
            "product_code",
            "expand_neighbors",
        }
        assert model.tool_required_argument_names["search_documents"] == {"objective"}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("factory", "permission"),
    [
        (create_policy_agent, Permission.POLICY),
        (create_tax_payout_agent, Permission.TAX_PAYOUT),
    ],
)
async def test_policy_and_tax_search_preserve_domain_objective_when_focus_is_narrower(
    factory: Callable[..., DomainRunner],
    permission: Permission,
) -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
        )
    )
    agent = factory(
        model=_model(),
        search_service=cast(SearchRunner, search),
    )
    domain_objective = "이전 가능 여부와 계좌 유형별 조건·제한 및 신청 절차 판단"

    result = await agent(
        {
            "question": "연금계좌를 이전할 수 있나요?",
            "objective": domain_objective,
        }
    )

    assert result["execution_status"] == "completed"
    assert search.calls == [
        (
            SearchRequest(objective=(f"{domain_objective}\n이전 가능 여부의 문서 근거 확인")),
            permission,
        )
    ]


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
async def test_product_agent_accepts_initial_not_applicable_without_catalog_or_search() -> None:
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
                            "conclusion": "계좌 메뉴는 Policy Agent의 책임입니다.",
                            "missing_conditions": ["임의 조건"],
                            "warnings": ["임의 경고"],
                            "evidence_chunk_ids": [],
                        },
                        "id": "not-applicable-submit",
                        "type": "tool_call",
                    }
                ],
            )
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
            "question": "IRP 계좌에서 거래내역 메뉴는 어디인가요?",
            "objective": "계좌 거래내역 메뉴 확인",
        }
    )

    assert result["execution_status"] == "completed"
    assert result["decision"] == {
        "status": "not_applicable",
        "conclusion": "이 질문에는 해당 도메인 판단이 적용되지 않습니다.",
        "missing_conditions": [],
    }
    assert result["evidence"] == []
    assert result["calculations"] == []
    assert result["warnings"] == []
    assert planner.calls == []
    assert search.calls == []
    assert model.invocation_count == 1


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
                objective=("이전 절차 판단\nguide.pdf 이전 절차"),
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
@pytest.mark.parametrize(
    ("evidence", "conclusion"),
    [
        (
            "ISA 만기자금은 만기일부터 60일 이내 연금계좌로 전환해야 합니다.",
            "ISA 만기자금은 만기일부터 60일 이내 연금계좌로 전환해야 합니다.",
        ),
        (
            "연간 사적연금소득이 1,500만 원을 초과하면 16.5퍼센트 분리과세를 선택할 수 있습니다.",
            "연간 사적연금소득이 1500만원을 초과하면 16.5% 분리과세를 선택할 수 있습니다.",
        ),
        (
            "추가 세액공제 대상금액은 최대 900만원입니다.",
            "추가 세액공제 대상금액은 최대 900만원입니다.",
        ),
    ],
)
async def test_tax_agent_preserves_numeric_facts_copied_from_selected_evidence(
    evidence: str,
    conclusion: str,
) -> None:
    chunk = _chunk(DocumentType.PENSION_REFERENCE, content=evidence)
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    model = _model(conclusion=conclusion)
    agent = create_tax_payout_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent({"question": "법정 기준은?", "objective": "법정 기준 확인"})

    assert result["decision"]["status"] == "determined"
    assert result["decision"]["conclusion"] == conclusion
    assert result["calculations"] == []
    assert result["warnings"] == []
    assert model.invocation_count == 2


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
                            "conclusion": "검색 근거의 평가액과 수령연차에 계산 결과를 적용했습니다.",
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
    assert (
        "검색 근거의 평가액과 수령연차에 계산 결과를 적용했습니다."
        in result["decision"]["conclusion"]
    )
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
                            "conclusion": "검색 근거의 납입액과 소득 조건에 계산 결과를 적용했습니다.",
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
    assert (
        "검색 근거의 납입액과 소득 조건에 계산 결과를 적용했습니다."
        in result["decision"]["conclusion"]
    )
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
    *,
    calculations: list[dict[str, Any]],
    tool_names: list[str],
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
    update = EnforceTaxPayoutToolSequence(max_model_calls=5).after_model(state, None)
    kept_message = message if update is None else update["messages"][0]
    return [call["name"] for call in kept_message.tool_calls]


def test_tax_sequence_keeps_one_calculation_per_model_response() -> None:
    kept = _sequence_result_tool_names(
        calculations=[],
        tool_names=[
            "calculate_pension_income_tax",
            "calculate_non_pension_withdrawal_tax",
            "submit_domain_result",
        ],
    )

    assert kept == ["calculate_pension_income_tax"]


def test_tax_sequence_allows_a_different_calculation_after_prior_result() -> None:
    kept = _sequence_result_tool_names(
        calculations=[{"calculator_id": "pension_withdrawal_allocation"}],
        tool_names=[
            "calculate_pension_withdrawal_tax_breakdown",
            "submit_domain_result",
        ],
    )

    assert kept == ["calculate_pension_withdrawal_tax_breakdown"]


def test_tax_sequence_keeps_exposed_calculation_capability_after_search() -> None:
    kept = _sequence_result_tool_names(
        calculations=[],
        tool_names=["calculate_pension_withdrawal_allocation"],
    )

    assert kept == ["calculate_pension_withdrawal_allocation"]


def test_tax_sequence_filters_unexposed_tool_capability() -> None:
    kept = _sequence_result_tool_names(
        calculations=[],
        tool_names=["calculate_unexposed_value", "submit_domain_result"],
    )

    assert kept == ["submit_domain_result"]


@pytest.mark.anyio
async def test_tax_agent_enforces_per_calculator_run_budget() -> None:
    chunk = _chunk(
        DocumentType.PENSION_REFERENCE,
        content="계좌 평가액 1천만원; 연금수령연차 1년차",
    )
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    calculation_call = {
        "name": "calculate_pension_withdrawal_limit",
        "args": {
            "account_valuation_krw": "10000000",
            "pension_year": 1,
            "account_valuation_source": "계좌 평가액 1천만원",
            "pension_year_source": "연금수령연차 1년차",
        },
        "id": "calculation-call",
        "type": "tool_call",
    }
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "연금수령한도 입력과 산식 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="", tool_calls=[calculation_call]),
            AIMessage(
                content="",
                tool_calls=[{**calculation_call, "id": "repeated-calculation-call"}],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_domain_result",
                        "args": {
                            "status": "determined",
                            "conclusion": "검색 근거의 평가액과 수령연차에 계산을 적용했습니다.",
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

    result = await agent({"question": "연금수령한도는?", "objective": "한도 계산"})

    assert [item["calculator_id"] for item in result["calculations"]] == [
        "pension_withdrawal_limit"
    ]
    assert model.invocation_count == 4


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
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
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


def test_tax_sequence_runs_calculation_before_simultaneous_submit() -> None:
    kept = _sequence_result_tool_names(
        calculations=[{"calculator_id": "pension_income_tax"}],
        tool_names=[
            "calculate_non_pension_withdrawal_tax",
            "submit_domain_result",
        ],
    )

    assert kept == ["calculate_non_pension_withdrawal_tax"]


def test_tax_agent_keeps_only_first_when_deferred_and_other_calculators_are_requested() -> None:
    kept = _sequence_result_tool_names(
        calculations=[],
        tool_names=[
            "calculate_deferred_retirement_withdrawal_tax",
            "calculate_pension_income_tax",
        ],
    )

    assert kept == ["calculate_deferred_retirement_withdrawal_tax"]


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


def test_fund_fee_presentations_distinguish_fixed_and_maximum() -> None:
    fixed = {
        "calculator_id": "fund_frontend_sales_fee",
        "inputs": {
            "subscription_amount_krw": "1000000",
            "selected_rate_percent": "1.0",
            "rate_kind": "fixed",
        },
        "input_sources": {},
        "outputs": {"fee_amount_krw": "10000.0"},
        "units": {"fee_amount_krw": "KRW"},
        "warnings": [],
    }
    maximum = {
        "calculator_id": "fund_redemption_fee",
        "inputs": {
            "redemption_profit_krw": "1000000",
            "selected_rate_percent": "1.0",
            "rate_kind": "maximum",
        },
        "input_sources": {},
        "outputs": {"maximum_fee_amount_krw": "10000.0"},
        "units": {"maximum_fee_amount_krw": "KRW"},
        "warnings": [],
    }

    summary = format_calculation_summary([fixed, maximum])

    assert "- 납입금액: 1000000 KRW" in summary
    assert "- 선취판매수수료율: 1.0 %" in summary
    assert "- 선취판매수수료: 10000.0 KRW" in summary
    assert "- 이익금: 1000000 KRW" in summary
    assert "- 환매수수료 상한율: 1.0 %" in summary
    assert "- 최대 환매수수료: 10000.0 KRW" in summary
    assert "- 환매수수료: 10000.0 KRW" not in summary


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


def _reported_var_state(
    *,
    question: str,
    content: str,
    source_file_name: str = "R2_KR510902511M.pdf",
) -> dict[str, Any]:
    return {
        "question": question,
        "product_candidate_codes": ["KR510902511M"],
        "product_scoped_search_completed": True,
        "product_scoped_source_file_name": "R2_KR510902511M.pdf",
        "search_result": SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.FUND_PROSPECTUS,
                    source_file_name=source_file_name,
                    title="위험등급",
                    content=content,
                )
            ],
        ),
        "calculations": [],
        "messages": [],
    }


@pytest.mark.anyio
async def test_product_agent_uses_reported_var_and_defers_simultaneous_submit() -> None:
    source = "A 클래스 투자설명서 공시 연환산 97.5% VaR는 10%"
    chunk = _chunk(
        DocumentType.FUND_PROSPECTUS,
        source_file_name="R2_KR510902511M.pdf",
        title="위험등급",
        content=source,
    )
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    premature_submit = {
        "name": "submit_domain_result",
        "args": {
            "status": "determined",
            "conclusion": "위험등급은 1등급입니다.",
            "missing_conditions": [],
            "warnings": [],
            "evidence_chunk_ids": [chunk.chunk_id],
        },
        "id": "premature-submit",
        "type": "tool_call",
    }
    calculation_call = {
        "name": "calculate_fund_reported_var_risk",
        "args": {
            "annualized_var_percent": "10",
            "annualized_var_source": source,
        },
        "id": "reported-var-call",
        "type": "tool_call",
    }
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
                            "objective": "공시 연환산 VaR 확인",
                            "product_code": "KR510902511M",
                        },
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="", tool_calls=[premature_submit, calculation_call]),
            AIMessage(content="", tool_calls=[premature_submit | {"id": "final-submit"}]),
        ]
    )
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
        catalog_matcher=_product_matcher(),
    )

    result = await agent(
        {
            "question": "미래에셋 장기성장 A 클래스의 위험등급은?",
            "objective": "공시 연환산 VaR 위험등급 계산",
        }
    )

    assert result["decision"]["status"] == "determined"
    assert "공시 연환산 97.5% VaR: 10 %" in result["decision"]["conclusion"]
    assert "위험등급: 5등급 (낮은 위험)" in result["decision"]["conclusion"]
    assert result["calculations"][0]["calculator_id"] == "fund_reported_var_risk"
    assert (
        result["calculations"][0]["input_sources"]["annualized_var_percent"]["chunk_id"]
        == chunk.chunk_id
    )


@pytest.mark.anyio
async def test_product_agent_accepts_exact_reported_var_from_question() -> None:
    question_source = "미래에셋 장기성장 공시 연환산 97.5% VaR는 10%"
    chunk = _chunk(
        DocumentType.FUND_PROSPECTUS,
        source_file_name="R2_KR510902511M.pdf",
        title="위험 공시",
        content="이 상품은 투자설명서에서 위험을 공시합니다.",
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
                        "args": {
                            "objective": "질문 대상 상품 확인",
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
                        "name": "calculate_fund_reported_var_risk",
                        "args": {
                            "annualized_var_percent": "10",
                            "annualized_var_source": question_source,
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
                            "conclusion": "질문의 공시값을 계산했습니다.",
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
        {"question": question_source, "objective": "제공된 공시 VaR 위험등급 계산"}
    )

    source_record = result["calculations"][0]["input_sources"]["annualized_var_percent"]
    assert source_record == {"origin": "question", "text": question_source, "chunk_id": None}
    assert result["calculations"][0]["outputs"]["risk_grade"] == 5


def test_reported_var_guard_rejects_product_and_class_mismatch() -> None:
    source = "C 클래스 공시 연환산 97.5% VaR는 10%"
    call = {
        "name": "calculate_fund_reported_var_risk",
        "args": {"annualized_var_percent": "10", "annualized_var_source": source},
        "id": "call",
        "type": "tool_call",
    }
    class_state = _reported_var_state(
        question="미래에셋 장기성장 A 클래스 위험등급",
        content=source,
    )
    product_state = _reported_var_state(
        question="미래에셋 장기성장 C 클래스 위험등급",
        content=source,
        source_file_name="R2_KR9999999999.pdf",
    )

    assert _reported_var_call_missing_condition(call, class_state) == (
        _FUND_CLASS_MISSING_CONDITION
    )
    assert _reported_var_call_missing_condition(call, product_state) == "대상 펀드 확인 필요"
    assert _FUND_CLASS_MISSING_CONDITION in _product_var_missing_conditions(class_state)


def test_latest_reported_var_requires_trusted_date_metadata() -> None:
    source = "A 클래스 공시 연환산 97.5% VaR는 10%"
    state = _reported_var_state(
        question="미래에셋 장기성장 A 클래스의 최신 위험등급",
        content=source,
    )
    call = {
        "name": "calculate_fund_reported_var_risk",
        "args": {"annualized_var_percent": "10", "annualized_var_source": source},
        "id": "call",
        "type": "tool_call",
    }

    assert _reported_var_call_missing_condition(call, state) == (
        _LATEST_DISCLOSURE_MISSING_CONDITION
    )
    assert _product_var_missing_conditions(state) == (_LATEST_DISCLOSURE_MISSING_CONDITION,)


def test_product_result_preserves_python_var_condition_as_conditional() -> None:
    chunk = _chunk(DocumentType.FUND_PROSPECTUS)
    result = _build_product_result(
        search_result=SearchResult(
            execution_status="completed",
            retrieved_chunks=[chunk],
        ),
        calculations=[],
        status="determined",
        conclusion="최신 위험등급입니다.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[chunk.chunk_id],
        enforced_missing_conditions=(_LATEST_DISCLOSURE_MISSING_CONDITION,),
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == [_LATEST_DISCLOSURE_MISSING_CONDITION]


def test_reported_var_context_blocks_daily_tool_and_keeps_reported_tool() -> None:
    source = "A 클래스 공시 연환산 97.5% VaR는 10%"
    state = _reported_var_state(
        question="미래에셋 장기성장 A 클래스 위험등급",
        content=source,
    )
    daily_call = {
        "name": "calculate_fund_var_risk",
        "args": {
            "daily_loss_percentile_percent": "10",
            "daily_loss_percentile_source": source,
        },
        "id": "daily",
        "type": "tool_call",
    }
    reported_call = {
        "name": "calculate_fund_reported_var_risk",
        "args": {"annualized_var_percent": "10", "annualized_var_source": source},
        "id": "reported",
        "type": "tool_call",
    }
    allowed = (
        "calculate_fund_reported_var_risk",
        "calculate_fund_var_risk",
        "submit_domain_result",
    )

    assert not _product_tool_call_is_allowed(daily_call, state=state, allowed_tools=allowed)
    assert _product_tool_call_is_allowed(reported_call, state=state, allowed_tools=allowed)

    state["messages"] = [AIMessage(content="", tool_calls=[daily_call, reported_call])]
    update = EnforceProductToolSequence(
        lookup_tool_name="lookup_product_codes",
        max_search_calls=2,
        calculation_tool_names=(
            "calculate_fund_reported_var_risk",
            "calculate_fund_var_risk",
        ),
    ).after_model(state, None)
    assert update is not None
    assert update["messages"][0].tool_calls == [reported_call]


@pytest.mark.anyio
async def test_product_agent_records_and_presents_fixed_frontend_sales_fee() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.FUND_PROSPECTUS,
                    source_file_name="R2_KR510902511M.pdf",
                    title="선취판매수수료",
                    content="납입금액 1,000,000원; 선취판매수수료율 1.0%를 부과합니다.",
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
                            "objective": "선취판매수수료율 확인",
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
                        "name": "calculate_fund_frontend_sales_fee",
                        "args": {
                            "subscription_amount_krw": "1000000",
                            "selected_rate_percent": "1.0",
                            "rate_kind": "fixed",
                            "subscription_amount_source": "납입금액 1,000,000원",
                            "selected_rate_source": "선취판매수수료율 1.0%를 부과합니다.",
                            "rate_kind_source": "선취판매수수료율 1.0%를 부과합니다.",
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
            "question": "미래에셋 장기성장 상품에 납입금액 100만원을 넣으면 선취판매수수료는 얼마인가요?",
            "objective": "선취판매수수료 계산",
        }
    )

    assert result["decision"]["status"] == "determined"
    assert result["calculations"][0]["calculator_id"] == "fund_frontend_sales_fee"
    assert result["calculations"][0]["outputs"] == {"fee_amount_krw": "10000.0"}
    conclusion = result["decision"]["conclusion"]
    assert "- 납입금액: 1000000 KRW" in conclusion
    assert "- 선취판매수수료율: 1.0 %" in conclusion
    assert "- 선취판매수수료: 10000.0 KRW" in conclusion
    assert "임의 결론" not in conclusion


@pytest.mark.anyio
async def test_product_agent_runs_reported_var_and_frontend_fee_in_one_conversation() -> None:
    var_source = "A 클래스 투자설명서 공시 연환산 97.5% VaR는 10%"
    fee_source = "납입금액 1,000,000원; 선취판매수수료율 1.0%를 부과합니다."
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.FUND_PROSPECTUS,
                    source_file_name="R2_KR510902511M.pdf",
                    title="위험등급과 수수료",
                    content=f"{var_source}; {fee_source}",
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
                            "objective": "위험등급과 선취판매수수료 확인",
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
                        "name": "calculate_fund_reported_var_risk",
                        "args": {
                            "annualized_var_percent": "10",
                            "annualized_var_source": var_source,
                        },
                        "id": "var-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_fund_frontend_sales_fee",
                        "args": {
                            "subscription_amount_krw": "1000000",
                            "selected_rate_percent": "1.0",
                            "rate_kind": "fixed",
                            "subscription_amount_source": "납입금액 1,000,000원",
                            "selected_rate_source": fee_source,
                            "rate_kind_source": fee_source,
                        },
                        "id": "fee-call",
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
            "question": "미래에셋 장기성장 A 클래스의 위험등급과 선취판매수수료를 알려줘",
            "objective": "위험등급과 선취판매수수료 계산",
        }
    )

    assert result["decision"]["status"] == "determined"
    calculator_ids = {calculation["calculator_id"] for calculation in result["calculations"]}
    assert calculator_ids == {"fund_reported_var_risk", "fund_frontend_sales_fee"}


@pytest.mark.anyio
async def test_product_agent_presents_maximum_redemption_fee_as_upper_bound() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.FUND_PROSPECTUS,
                    source_file_name="R2_KR5194450018.pdf",
                    title="환매수수료",
                    content="이익금 1,000,000원; 환매수수료율 1.0% 이내를 부과합니다.",
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
                            "objective": "환매수수료율 확인",
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
                        "name": "calculate_fund_redemption_fee",
                        "args": {
                            "redemption_profit_krw": "1000000",
                            "selected_rate_percent": "1.0",
                            "rate_kind": "maximum",
                            "redemption_profit_source": "이익금 1,000,000원",
                            "selected_rate_source": "환매수수료율 1.0% 이내를 부과합니다.",
                            "rate_kind_source": "환매수수료율 1.0% 이내를 부과합니다.",
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
            "question": "미래에셋 장기성장 상품의 환매수수료는 최대 얼마인가요?",
            "objective": "환매수수료 계산",
        }
    )

    assert result["decision"]["status"] == "determined"
    assert result["calculations"][0]["calculator_id"] == "fund_redemption_fee"
    assert result["calculations"][0]["outputs"] == {"maximum_fee_amount_krw": "10000.0"}
    conclusion = result["decision"]["conclusion"]
    assert "- 환매수수료 상한율: 1.0 %" in conclusion
    assert "- 최대 환매수수료: 10000.0 KRW" in conclusion
    assert "- 환매수수료: 10000.0 KRW" not in conclusion


@pytest.mark.anyio
async def test_product_agent_rejects_aggregate_expense_as_fee_rate_and_stays_conditional() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                _chunk(
                    DocumentType.FUND_PROSPECTUS,
                    source_file_name="R2_KR510902511M.pdf",
                    title="펀드 수수료",
                    content="납입금액 1,000,000원; 총보수 1.0%",
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
                            "objective": "펀드 수수료 확인",
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
                        "name": "calculate_fund_frontend_sales_fee",
                        "args": {
                            "subscription_amount_krw": "1000000",
                            "selected_rate_percent": "1.0",
                            "rate_kind": "fixed",
                            "subscription_amount_source": "납입금액 1,000,000원",
                            "selected_rate_source": "총보수 1.0%",
                            "rate_kind_source": "총보수 1.0%",
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
                            "conclusion": "수수료 종류 확인이 필요합니다.",
                            "missing_conditions": ["수수료 종류 확인 필요"],
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
            "question": "미래에셋 장기성장 상품 수수료가 얼마인가요?",
            "objective": "펀드 수수료 확인",
        }
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == ["수수료 종류 확인 필요"]
    assert result["calculations"] == []


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
async def test_policy_agent_not_applicable_accepted_without_search() -> None:
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
                            "conclusion": "펀드 위험은 Product Agent의 책임입니다.",
                            "missing_conditions": ["임의 조건"],
                            "warnings": ["임의 경고"],
                            "evidence_chunk_ids": [],
                        },
                        "id": "not-applicable-submit",
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
            "question": "A펀드의 위험과 보수는 어떤가요?",
            "objective": "개별 펀드 위험과 보수 판단",
        }
    )

    assert result["execution_status"] == "completed"
    assert result["decision"] == {
        "status": "not_applicable",
        "conclusion": "이 질문에는 해당 도메인 판단이 적용되지 않습니다.",
        "missing_conditions": [],
    }
    assert result["evidence"] == []
    assert result["calculations"] == []
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


def test_domain_prompts_are_packaged_with_tool_and_evidence_contracts() -> None:
    policy_prompt = load_policy_agent_prompt()
    assert "search_documents" in policy_prompt
    product_prompt = load_product_agent_prompt()
    assert "search_documents" in product_prompt
    assert "lookup_product_codes" in product_prompt
    assert "후보가 하나일 때만 반환된 정확한 `product_code`" in product_prompt
    assert "현재 `objective`가 상품·운용 범위 밖이면" in product_prompt
    assert "Calculation Tool을 우선 사용" in product_prompt
    assert "Calculation Tool 미사용 fallback" in product_prompt
    assert "validation 실패나 계산 오류" in product_prompt
    assert "submit_domain_result" in product_prompt
    assert "evidence_chunk_ids" in product_prompt
    assert "calculate_" not in product_prompt
    assert "2회" not in product_prompt
    assert "두 번" not in product_prompt
    assert '"product_code":"KR510902511M"' not in product_prompt
    assert "{{PRODUCT_CATALOG_JSON}}" not in product_prompt
    tax_prompt = load_tax_payout_agent_prompt()
    assert all(f"## {index}." in tax_prompt for index in range(1, 9))
    assert "search_documents" in tax_prompt
    assert "Calculation Tool을 우선" in tax_prompt
    assert "Calculation Tool 미사용 fallback" in tax_prompt
    assert "공식·입력·대입 과정·결과·단위" in tax_prompt
    assert "validation이 실패" in tax_prompt
    assert "submit_domain_result" in tax_prompt
    assert "evidence_chunk_ids" in tax_prompt
    assert "not_applicable" in tax_prompt
    assert "calculate_" not in tax_prompt
    assert "#11" not in tax_prompt
    assert "Calculation Tool을 우선 사용" in policy_prompt
    assert "Calculation Tool 미사용 fallback" in policy_prompt
    assert "validation 실패" in policy_prompt
    assert "evidence_chunk_ids" in policy_prompt
    assert "not_applicable" in policy_prompt
    assert "source_file_name" in policy_prompt


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


def test_policy_keeps_first_calculation_without_question_matching() -> None:
    assert _policy_sequence_tool_names(
        [],
        [
            "calculate_dc_medical_withdrawal_threshold",
            "calculate_isa_transfer_deadline",
            "submit_domain_result",
        ],
    ) == ["calculate_dc_medical_withdrawal_threshold"]
    assert _policy_sequence_tool_names(
        [],
        [
            "calculate_isa_transfer_deadline",
            "calculate_dc_medical_withdrawal_threshold",
            "submit_domain_result",
        ],
    ) == ["calculate_isa_transfer_deadline"]


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


def _isa_deadline_calculation(
    *, completion_date: str | None = None, within_deadline: bool | None = None
) -> Any:
    inputs: dict[str, Any] = {"isa_maturity_date": "2026-06-30"}
    outputs: dict[str, Any] = {"transfer_deadline_date": "2026-08-29"}
    if completion_date is not None:
        inputs["transfer_completion_date"] = completion_date
    if within_deadline is not None:
        outputs["within_deadline"] = within_deadline
    return {
        "calculator_id": "isa_transfer_deadline",
        "inputs": inputs,
        "input_sources": {},
        "outputs": outputs,
        "units": {},
        "warnings": [],
    }


def test_policy_result_preserves_explicit_missing_conditions_after_calculation() -> None:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    calculations = [_isa_deadline_calculation()]
    result = _build_policy_result(
        search_result=SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE, chunk_id=chunk_id)],
        ),
        calculations=calculations,
        status="conditional",
        conclusion="계산 가능한 마감일을 확인했습니다.",
        missing_conditions=["실제 완료 처리일 확인 필요"],
        warnings=[],
        evidence_chunk_ids=[chunk_id],
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == ["실제 완료 처리일 확인 필요"]
    assert result["calculations"] == calculations


@pytest.mark.parametrize(
    ("completion_date", "within_deadline", "label"),
    [
        ("2026-08-29", True, "60일 기한: 충족"),
        ("2026-08-30", False, "60일 기한: 초과"),
    ],
)
def test_policy_presents_rules_isa_completion_result_without_recalculation(
    completion_date: str,
    within_deadline: bool,
    label: str,
) -> None:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    result = _build_policy_result(
        search_result=SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE, chunk_id=chunk_id)],
        ),
        calculations=[
            _isa_deadline_calculation(
                completion_date=completion_date, within_deadline=within_deadline
            )
        ],
        status="determined",
        conclusion="60일 기한만 판정했습니다.",
        missing_conditions=[],
        warnings=[],
        evidence_chunk_ids=[chunk_id],
    )

    assert result["decision"]["status"] == "determined"
    assert "ISA 만기일: 2026-06-30" in result["decision"]["conclusion"]
    assert "연금전환 마감일: 2026-08-29" in result["decision"]["conclusion"]
    assert f"입금확인·전환완료 처리일: {completion_date}" in result["decision"]["conclusion"]
    assert label in result["decision"]["conclusion"]


@pytest.mark.anyio
async def test_policy_agent_runs_isa_deadline_before_simultaneous_submit() -> None:
    chunk = _chunk(DocumentType.PENSION_REFERENCE)
    maturity_source = "ISA 만기일은 2026-06-30"
    completion_source = "입금확인 처리일은 2026-08-29"
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[
                chunk.model_copy(update={"content": f"{maturity_source}; {completion_source}"})
            ],
        )
    )
    submit_call = {
        "name": "submit_domain_result",
        "args": {
            "status": "determined",
            "conclusion": "60일 기한 기준으로 판정했습니다.",
            "missing_conditions": [],
            "warnings": [],
            "evidence_chunk_ids": [chunk.chunk_id],
        },
        "id": "submit-call",
        "type": "tool_call",
    }
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "ISA 연금전환 60일 기한 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_isa_transfer_deadline",
                        "args": {
                            "isa_maturity_date": "2026-06-30",
                            "transfer_completion_date": "2026-08-29",
                            "isa_maturity_date_source": maturity_source,
                            "transfer_completion_date_source": completion_source,
                        },
                        "id": "calculation-call",
                        "type": "tool_call",
                    },
                    submit_call,
                ],
            ),
            AIMessage(content="", tool_calls=[submit_call]),
        ]
    )
    agent = create_policy_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent(
        {
            "question": f"{maturity_source}; {completion_source}. ISA 연금전환 기한 안이야?",
            "objective": "ISA 만기자금 연금전환 60일 기한 판정",
        }
    )

    assert result["decision"]["status"] == "determined"
    assert result["calculations"][0]["calculator_id"] == "isa_transfer_deadline"
    assert result["calculations"][0]["outputs"]["within_deadline"] is True
    assert result["calculations"][0]["input_sources"]
    assert result["evidence"]


@pytest.mark.anyio
async def test_policy_agent_preserves_explicit_missing_condition_after_deadline_calculation() -> (
    None
):
    chunk = _chunk(DocumentType.PENSION_REFERENCE)
    maturity_source = "ISA 만기일은 2026-06-30"
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[chunk.model_copy(update={"content": maturity_source})],
        )
    )
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "ISA 연금전환 60일 기한 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_isa_transfer_deadline",
                        "args": {
                            "isa_maturity_date": "2026-06-30",
                            "isa_maturity_date_source": maturity_source,
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
                            "conclusion": "계산 가능한 마감일을 확인했습니다.",
                            "missing_conditions": ["실제 완료 처리일 확인 필요"],
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
        {
            "question": f"{maturity_source}; 2026-08-20에 신청했어. ISA 연금전환 기한 안이야?",
            "objective": "ISA 만기자금 연금전환 완료 여부",
        }
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == ["실제 완료 처리일 확인 필요"]
    assert result["calculations"][0]["outputs"] == {"transfer_deadline_date": "2026-08-29"}


def test_policy_result_keeps_explicit_conditions_with_calculation() -> None:
    chunk_id = "550e8400-e29b-41d4-a716-446655440000"
    result = _build_policy_result(
        search_result=SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE, chunk_id=chunk_id)],
        ),
        calculations=[_dc_threshold_calculation()],
        status="conditional",
        conclusion="임금 기준을 초과했습니다.",
        missing_conditions=["제도상 자격 확인 필요"],
        warnings=[],
        evidence_chunk_ids=[chunk_id],
    )

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == ["제도상 자격 확인 필요"]
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
                            "status": "conditional",
                            "conclusion": "임금 기준을 초과합니다.",
                            "missing_conditions": ["제도상 자격 확인 필요"],
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

    result = await agent({"question": content, "objective": "DC 의료비 인출 가능 여부"})

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == ["제도상 자격 확인 필요"]
    assert result["calculations"][0]["calculator_id"] == "dc_medical_withdrawal_threshold"
    assert result["calculations"][0]["input_sources"]
    assert result["evidence"]


@pytest.mark.anyio
async def test_policy_agent_can_submit_without_calling_a_calculator() -> None:
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


_EXEC_LIMIT_SALARY_2012_2019 = "2012년부터 2019년까지 총급여 연평균 환산액 100,000,000원"
_EXEC_LIMIT_MONTHS_2012_2019 = "2012년부터 2019년까지 근무월수 96개월"
_EXEC_LIMIT_SALARY_2020_ONWARD = "2020년 이후 총급여 연평균 환산액 120,000,000원"
_EXEC_LIMIT_MONTHS_2020_ONWARD = "2020년 이후 근무월수 60개월"
_EXEC_LIMIT_PAYMENT = "2012년 이후 한도 적용대상 지급액 400,000,000원"


@pytest.mark.anyio
async def test_tax_agent_records_executive_limit_with_both_periods_and_payment() -> None:
    content = (
        f"{_EXEC_LIMIT_SALARY_2012_2019}; {_EXEC_LIMIT_MONTHS_2012_2019}; "
        f"{_EXEC_LIMIT_SALARY_2020_ONWARD}; {_EXEC_LIMIT_MONTHS_2020_ONWARD}; "
        f"{_EXEC_LIMIT_PAYMENT}"
    )
    chunk = _chunk(DocumentType.PENSION_REFERENCE, content=content)
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "임원 퇴직소득 한도 계산 입력 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_executive_retirement_income_limit",
                        "args": {
                            "average_annualized_salary_2012_2019_krw": "100000000",
                            "average_annualized_salary_2012_2019_source": (
                                _EXEC_LIMIT_SALARY_2012_2019
                            ),
                            "service_months_2012_2019": 96,
                            "service_months_2012_2019_source": _EXEC_LIMIT_MONTHS_2012_2019,
                            "average_annualized_salary_2020_onward_krw": "120000000",
                            "average_annualized_salary_2020_onward_source": (
                                _EXEC_LIMIT_SALARY_2020_ONWARD
                            ),
                            "service_months_2020_onward": 60,
                            "service_months_2020_onward_source": _EXEC_LIMIT_MONTHS_2020_ONWARD,
                            "post_2011_limit_subject_payment_krw": "400000000",
                            "post_2011_limit_subject_payment_source": _EXEC_LIMIT_PAYMENT,
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
                            "conclusion": "근거에 나온 기간별 보수와 지급액에 계산 결과를 적용했습니다.",
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

    result = await agent(
        {
            "question": (
                "임원 퇴직금이 4억원인데 세법상 퇴직소득으로 인정되는 금액과 초과 근로소득은 "
                f"얼마인가요? {content}"
            ),
            "objective": "임원 퇴직소득 한도와 초과 근로소득 계산",
        }
    )

    assert result["decision"]["status"] == "determined"
    assert result["calculations"][0]["calculator_id"] == "executive_retirement_income_limit"
    assert result["calculations"][0]["outputs"] == {
        "limit_2012_2019_krw": "240000000.0",
        "limit_2020_onward_krw": "120000000.0",
        "post_2011_total_limit_krw": "360000000.0",
        "retirement_income_amount_krw": "360000000.0",
        "wage_income_excess_krw": "40000000.0",
    }
    conclusion = result["decision"]["conclusion"]
    assert "2012~2019년 한도 구성액: 240000000.0 KRW" in conclusion
    assert "2020년 이후 한도 구성액: 120000000.0 KRW" in conclusion
    assert "임원 퇴직소득 한도 합계: 360000000.0 KRW" in conclusion
    assert "퇴직소득 인정액: 360000000.0 KRW" in conclusion
    assert "한도 초과 근로소득 금액: 40000000.0 KRW" in conclusion
    assert "근거에 나온 기간별 보수와 지급액에 계산 결과를 적용했습니다." in conclusion


@pytest.mark.anyio
async def test_tax_agent_computes_executive_limit_only_without_payment() -> None:
    content = f"{_EXEC_LIMIT_SALARY_2020_ONWARD}; {_EXEC_LIMIT_MONTHS_2020_ONWARD}"
    chunk = _chunk(DocumentType.PENSION_REFERENCE, content=content)
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "임원 퇴직소득 한도 계산 입력 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_executive_retirement_income_limit",
                        "args": {
                            "average_annualized_salary_2020_onward_krw": "120000000",
                            "average_annualized_salary_2020_onward_source": (
                                _EXEC_LIMIT_SALARY_2020_ONWARD
                            ),
                            "service_months_2020_onward": 60,
                            "service_months_2020_onward_source": _EXEC_LIMIT_MONTHS_2020_ONWARD,
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

    result = await agent(
        {
            "question": f"임원 퇴직소득 한도가 얼마인가요? {content}",
            "objective": "임원 퇴직소득 한도 계산",
        }
    )

    assert result["decision"]["status"] == "determined"
    outputs = result["calculations"][0]["outputs"]
    assert outputs["limit_2012_2019_krw"] == "0"
    assert outputs["limit_2020_onward_krw"] == "120000000.0"
    assert "retirement_income_amount_krw" not in outputs
    assert "wage_income_excess_krw" not in outputs
    conclusion = result["decision"]["conclusion"]
    assert "퇴직소득 인정액" not in conclusion
    assert "한도 초과 근로소득" not in conclusion


def _retirement_calculation(
    calculator_id: str, *, negative_dc: bool = False, equal_transfer: bool = False
) -> Any:
    if calculator_id == "db_retirement_benefit":
        return {
            "calculator_id": calculator_id,
            "inputs": {
                "wages_for_average_period_krw": "9000000",
                "included_days_for_average_wage": 90,
                "verified_service_years": "3.5",
            },
            "input_sources": {},
            "outputs": {
                "average_daily_wage": "100000",
                "average_wage_30_days": "3000000",
                "verified_service_years": "3.5",
                "retirement_benefit": "10500000.0",
            },
            "units": {
                "average_daily_wage": "KRW/day",
                "average_wage_30_days": "KRW",
                "verified_service_years": "years",
                "retirement_benefit": "KRW",
            },
            "warnings": [],
        }
    if calculator_id == "dc_retirement_benefit":
        result = "-1000000" if negative_dc else "11000000"
        gain_loss = "-11000000" if negative_dc else "1000000"
        return {
            "calculator_id": calculator_id,
            "inputs": {
                "accumulated_contributions_krw": "10000000",
                "investment_gain_loss_krw": gain_loss,
            },
            "input_sources": {},
            "outputs": {
                "accumulated_contributions": "10000000",
                "investment_gain_loss": gain_loss,
                "retirement_benefit": result,
            },
            "units": {
                "accumulated_contributions": "KRW",
                "investment_gain_loss": "KRW",
                "retirement_benefit": "KRW",
            },
            "warnings": ["DC 퇴직급여 계산 결과가 음수입니다."] if negative_dc else [],
        }
    if calculator_id == "db_to_dc_transfer_amount":
        basis_type = "equal" if equal_transfer else "annual_wage_monthly_basis"
        return {
            "calculator_id": calculator_id,
            "inputs": {
                "final_average_wage_30_days_krw": "4000000",
                "final_annual_total_wages_krw": "48000000",
                "verified_service_years": "3.5",
            },
            "input_sources": {},
            "outputs": {
                "final_average_wage_30_days": "4000000",
                "annual_wage_monthly_basis": "4000000",
                "selected_basis": "4000000",
                "selected_basis_type": basis_type,
                "verified_service_years": "3.5",
                "transfer_amount": "14000000.0",
            },
            "units": {
                "final_average_wage_30_days": "KRW",
                "annual_wage_monthly_basis": "KRW",
                "selected_basis": "KRW",
                "verified_service_years": "years",
                "transfer_amount": "KRW",
            },
            "warnings": [],
        }
    return {
        "calculator_id": "dc_minimum_employer_contribution",
        "inputs": {"annual_total_wages_krw": "48000000"},
        "input_sources": {},
        "outputs": {
            "annual_total_wages": "48000000",
            "minimum_employer_contribution": "4000000",
        },
        "units": {"annual_total_wages": "KRW", "minimum_employer_contribution": "KRW"},
        "warnings": [],
    }


def test_retirement_presentations_preserve_intermediate_negative_and_equal_values() -> None:
    summary = format_calculation_summary(
        [
            _retirement_calculation("db_retirement_benefit"),
            _retirement_calculation("dc_minimum_employer_contribution"),
            _retirement_calculation("dc_retirement_benefit", negative_dc=True),
            _retirement_calculation("db_to_dc_transfer_amount", equal_transfer=True),
        ]
    )

    assert "평균일급: 100000 KRW/day" in summary
    assert "30일 평균임금: 3000000 KRW" in summary
    assert "DC 최소 사용자 부담금: 4000000 KRW" in summary
    assert "누적 운용손익: -11000000 KRW" in summary
    assert "DC 퇴직급여: -1000000 KRW" in summary
    assert "두 기준 동일" in summary
    assert "더 큼" not in summary


@pytest.mark.parametrize(
    "calculation",
    [
        _retirement_calculation("dc_retirement_benefit", negative_dc=True),
        _retirement_calculation("db_to_dc_transfer_amount", equal_transfer=True),
    ],
)
def test_retirement_negative_and_equal_results_remain_determined(calculation: Any) -> None:
    result = _build_result_with_calculations([calculation])

    assert result["decision"]["status"] == "determined"
    assert result["decision"]["missing_conditions"] == []


@pytest.mark.anyio
async def test_tax_agent_runs_db_benefit_with_evidence() -> None:
    content = (
        "최근 3개월 임금 합계는 9,000,000원; "
        "평균임금 산정 포함 일수는 90일; 검증된 근속연수는 3.5년"
    )
    chunk = _chunk(DocumentType.PENSION_REFERENCE, content=content)
    search = FakeSearchService(SearchResult(execution_status="completed", retrieved_chunks=[chunk]))
    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "DB 퇴직급여 입력 확인"},
                        "id": "search-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate_db_retirement_benefit",
                        "args": {
                            "wages_for_average_period_krw": "9000000",
                            "included_days_for_average_wage": 90,
                            "verified_service_years": "3.5",
                            "wages_for_average_period_krw_source": (
                                "최근 3개월 임금 합계는 9,000,000원"
                            ),
                            "included_days_for_average_wage_source": (
                                "평균임금 산정 포함 일수는 90일"
                            ),
                            "verified_service_years_source": "검증된 근속연수는 3.5년",
                        },
                        "id": "db-call",
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
                            "conclusion": "DB 급여 계산 결과입니다.",
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
    agent = create_tax_payout_agent(model=model, search_service=cast(SearchRunner, search))

    result = await agent({"question": "DB 퇴직급여를 계산해줘", "objective": "DB 급여 계산"})

    assert result["decision"]["status"] == "determined"
    assert [item["calculator_id"] for item in result["calculations"]] == ["db_retirement_benefit"]
    assert result["evidence"][0]["chunk_id"] == chunk.chunk_id
    assert "평균일급" in result["decision"]["conclusion"]
