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

from pension_agent.agent.contracts import DomainName, Permission, validate_domain_result
from pension_agent.agent.domain_agent import DomainAgent
from pension_agent.agent.policy import create_policy_agent, load_policy_agent_prompt
from pension_agent.agent.product import create_product_agent, load_product_agent_prompt
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
from pension_agent.config import DomainAgentConfig
from pension_agent.core import DocumentType


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class ToolCallingFakeModel(FakeMessagesListChatModel):
    bindings: ClassVar[list[tuple[list[str], dict[str, Any]]]] = []
    tool_argument_names: ClassVar[dict[str, set[str]]] = {}
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
        self.tool_argument_names.update(
            {
                tool.name: set(tool.tool_call_schema.model_json_schema()["properties"])
                for tool in tools
            }
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


def _chunk(document_type: DocumentType) -> SearchChunkPayload:
    return SearchChunkPayload(
        chunk_id="550e8400-e29b-41d4-a716-446655440000",
        source_file_name="guide.pdf",
        document_type=document_type,
        chunk_index=2,
        title="이전 절차",
        locator="3페이지",
        content="가입 유형에 따라 이전 절차가 달라집니다.",
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
    if product_code is not None:
        search_args["product_code"] = product_code
    return ToolCallingFakeModel(
        responses=[
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
    factory: Callable[..., DomainAgent],
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
    agent = factory(model=model, search_service=cast(SearchRunner, search))
    assert agent.max_concurrency == 3
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
        set(names) == {"search_documents", "submit_domain_result"}
        for names, _kwargs in model.bindings
    )
    if domain == "product":
        assert model.tool_argument_names["search_documents"] == {
            "objective",
            "product_code",
            "expand_neighbors",
        }


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
    model = _model(product_code="KR510902511M")
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


@pytest.mark.anyio
async def test_product_agent_rejects_unknown_product_code_before_search_service() -> None:
    search = FakeSearchService(SearchResult(execution_status="completed"))
    model = _model(product_code="KR9999999999")
    agent = create_product_agent(
        model=model,
        search_service=cast(SearchRunner, search),
    )

    result = await agent(
        {
            "question": "존재하지 않는 상품을 확인해줘",
            "objective": "상품 확인",
        }
    )

    assert result["execution_status"] == "failed"
    assert search.calls == []
    assert model.invocation_count == 1


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
    )
    result = await agent({"question": "상품 위험은?", "objective": "상품 위험 판단"})

    assert result["execution_status"] == "failed"
    assert result["evidence"] == []
    assert result["calculations"] == []
    assert "provider" not in result["error"].lower()
    assert model.invocation_count == 1


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
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
        )
    )
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
                            "evidence_chunk_ids": ["550e8400-e29b-41d4-a716-446655440000"],
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
    result = await agent({"question": "세율은?", "objective": "세율 판단"})

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["conclusion"] == (
        "확정 수치 판단에는 결정론적 계산 Tool 결과가 필요합니다."
    )
    assert "10" not in result["decision"]["conclusion"]
    assert result["calculations"] == []


@pytest.mark.anyio
async def test_tax_agent_blocks_numeric_claims_from_all_untrusted_text_fields() -> None:
    search = FakeSearchService(
        SearchResult(
            execution_status="completed",
            retrieved_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
            limitations=["한도는 900만원입니다.", "자료 범위가 제한적입니다."],
        )
    )
    agent = create_tax_payout_agent(
        model=_model(
            conclusion="계산 결과를 확인해야 합니다.",
            missing_conditions=["연봉 5천만원 여부"],
            warnings=["세율은 10%입니다.", "일반적인 주의가 필요합니다."],
        ),
        search_service=cast(SearchRunner, search),
    )
    result = await agent({"question": "공제액은?", "objective": "공제액 판단"})

    serialized = str(result)
    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == ["결정론적 계산 Tool 결과"]
    assert "10%" not in serialized
    assert "900만원" not in serialized
    assert "5천만원" not in serialized
    assert "일반적인 주의가 필요합니다." in result["warnings"]
    assert "자료 범위가 제한적입니다." in result["warnings"]


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

    class BlockingGraph:
        async def ainvoke(
            self,
            input: dict[str, Any],
            /,
            *,
            context: Any,
        ) -> dict[str, Any]:
            del input
            assert context.deadline > asyncio.get_running_loop().time()
            started.set()
            await release.wait()
            return _completed_graph_state()

    agent = DomainAgent(
        domain="policy",
        graph=BlockingGraph(),
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

    class BlockingGraph:
        async def ainvoke(
            self,
            input: dict[str, Any],
            /,
            *,
            context: Any,
        ) -> dict[str, Any]:
            del input, context
            started.set()
            await release.wait()
            return _completed_graph_state()

    agent = DomainAgent(domain="policy", graph=BlockingGraph(), max_concurrency=1)
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
async def test_domain_agent_does_not_start_graph_after_parent_deadline() -> None:
    class UnexpectedGraph:
        async def ainvoke(
            self,
            input: dict[str, Any],
            /,
            *,
            context: Any,
        ) -> dict[str, Any]:
            raise AssertionError((input, context))

    agent = DomainAgent(domain="policy", graph=UnexpectedGraph())

    result = await agent(
        {"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"},
        deadline=asyncio.get_running_loop().time() - 1,
    )

    assert result["execution_status"] == "timeout"


@pytest.mark.anyio
async def test_domain_agent_timeout_cancels_graph_and_releases_capacity() -> None:
    cancelled = asyncio.Event()

    class TimeoutOnceGraph:
        calls = 0

        async def ainvoke(
            self,
            input: dict[str, Any],
            /,
            *,
            context: Any,
        ) -> dict[str, Any]:
            del input, context
            self.calls += 1
            if self.calls == 1:
                try:
                    await asyncio.sleep(10)
                finally:
                    cancelled.set()
            return _completed_graph_state()

    agent = DomainAgent(
        domain="policy",
        graph=TimeoutOnceGraph(),
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

    class CancellableGraph:
        block = True

        async def ainvoke(
            self,
            input: dict[str, Any],
            /,
            *,
            context: Any,
        ) -> dict[str, Any]:
            del input, context
            if self.block:
                started.set()
                await asyncio.sleep(10)
            return _completed_graph_state()

    graph = CancellableGraph()
    agent = DomainAgent(domain="policy", graph=graph, max_concurrency=1)
    request = {"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"}
    task = asyncio.create_task(agent(request))
    await started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    graph.block = False

    result = await agent(request)

    assert result["execution_status"] == "completed"


@pytest.mark.anyio
async def test_domain_agent_propagates_tracing_context_to_async_graph() -> None:
    observed_parent_ids: list[UUID | None] = []

    class ContextRecordingGraph:
        async def ainvoke(
            self,
            input: dict[str, Any],
            /,
            *,
            context: Any,
        ) -> dict[str, Any]:
            del input, context
            current_run = get_current_run_tree()
            observed_parent_ids.append(current_run.id if current_run is not None else None)
            return _completed_graph_state()

    agent = DomainAgent(domain="policy", graph=ContextRecordingGraph(), max_concurrency=1)
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


def _completed_graph_state() -> dict[str, Any]:
    return {
        "domain_result": {
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
    }


def test_domain_prompts_are_packaged_and_tax_prompt_blocks_numeric_generation() -> None:
    assert "search_documents" in load_policy_agent_prompt()
    product_prompt = load_product_agent_prompt()
    assert "search_documents" in product_prompt
    assert '"product_code":"KR510902511M"' in product_prompt
    assert "{{PRODUCT_CATALOG_JSON}}" not in product_prompt
    tax_prompt = load_tax_payout_agent_prompt()
    assert "확정 세금, 금액, 세율, 한도를 생성하지 않는다" in tax_prompt
    assert "submit_domain_result" in tax_prompt
