"""Search Service 결과를 사용하는 얇은 Domain Agent를 검증한다."""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
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

from pension_agent.agent.contracts import (
    DomainName,
    DomainResult,
    DomainRunner,
    Permission,
    validate_domain_result,
)
from pension_agent.agent.domain_runner import GuardedDomainRunner
from pension_agent.agent.policy import create_policy_agent, load_policy_agent_prompt
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
from pension_agent.agent.tax_payout.react import _build_tax_payout_result
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
                    "submit_domain_result",
                }
                if domain == "tax_payout"
                else {"search_documents", "submit_domain_result"}
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
    assert result["calculations"][0]["outputs"] == {"withdrawal_limit": "1200000.0"}
    assert result["calculations"][0]["input_sources"]["account_valuation_krw"] == {
        "origin": "evidence",
        "text": "평가액 1천만원",
        "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
    }
    assert [chunk["chunk_id"] for chunk in result["evidence"]] == [
        "550e8400-e29b-41d4-a716-446655440000"
    ]


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
    assert "search_documents" in load_policy_agent_prompt()
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
    assert "지원하지 않는 세금, 금액, 세율이나 한도를 직접 계산하지 않는다" in tax_prompt
    assert "submit_domain_result" in tax_prompt
    assert "Product Agent 책임이므로" in tax_prompt
    assert "Policy Agent 책임이므로" in tax_prompt
    assert "검색된 청크 전체가 아니라 결론에 실제 인용한 최소" in tax_prompt
    assert "근거 부족 판단을 계산 필요 판단으로 바꾸지 않는다" in tax_prompt
