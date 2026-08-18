"""Search Agent 결과를 사용하는 얇은 Domain Agent를 검증한다."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from threading import Event
from typing import Any, ClassVar, cast

import pytest
from langchain.messages import AIMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import Runnable

from pension_agent.agent.contracts import DomainName, Permission, validate_domain_result
from pension_agent.agent.domain_agent import DomainAgent
from pension_agent.agent.policy import create_policy_agent, load_policy_agent_prompt
from pension_agent.agent.product import create_product_agent, load_product_agent_prompt
from pension_agent.agent.search import SearchAgentAdapter, SearchChunkPayload, SearchResult
from pension_agent.agent.tax_payout import (
    create_tax_payout_agent,
    load_tax_payout_agent_prompt,
)
from pension_agent.config import DomainAgentConfig
from pension_agent.core import DocumentType


class ToolCallingFakeModel(FakeMessagesListChatModel):
    bindings: ClassVar[list[tuple[list[str], dict[str, Any]]]] = []

    def bind_tools(
        self,
        tools: Sequence[Any],
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        self.bindings.append(([tool.name for tool in tools], kwargs))
        return self


@dataclass
class FakeSearchAdapter:
    result: SearchResult
    calls: list[tuple[str, Permission]] = field(default_factory=list)

    def search(self, objective: str, *, permission: Permission) -> SearchResult:
        self.calls.append((objective, permission))
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
) -> ToolCallingFakeModel:
    if missing_conditions is None:
        missing_conditions = (
            [] if decision_status in {"determined", "not_applicable"} else ["가입 유형"]
        )
    if warnings is None:
        warnings = []
    return ToolCallingFakeModel(
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
                            "status": decision_status,
                            "conclusion": conclusion,
                            "missing_conditions": missing_conditions,
                            "warnings": warnings,
                        },
                        "id": "submit-call",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )


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
def test_domain_agents_use_search_result_and_submit_verified_result(
    factory: Callable[..., DomainAgent],
    domain: DomainName,
    permission: Permission,
    document_type: DocumentType,
) -> None:
    search = FakeSearchAdapter(
        SearchResult(
            execution_status="completed",
            coverage="sufficient",
            selected_chunks=[_chunk(document_type)],
        )
    )
    model = _model()
    model.bindings.clear()
    agent = factory(model=model, search_adapter=cast(SearchAgentAdapter, search))
    try:
        result = agent(
            {"question": "연금계좌를 이전할 수 있나요?", "objective": "이전 가능 여부 판단"}
        )
    finally:
        agent.close()

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
    assert search.calls == [("이전 가능 여부의 문서 근거 확인", permission)]
    assert all(
        set(names) == {"search_documents", "submit_domain_result"}
        for names, _kwargs in model.bindings
    )


def test_no_evidence_forces_undetermined_result() -> None:
    search = FakeSearchAdapter(
        SearchResult(execution_status="completed", coverage="none", limitations=["근거 없음"])
    )
    agent = create_policy_agent(
        model=_model(),
        search_adapter=cast(SearchAgentAdapter, search),
    )
    try:
        result = agent({"question": "외부 정보를 알려줘", "objective": "제공 문서 근거 확인"})
    finally:
        agent.close()

    assert result["decision"]["status"] == "undetermined"
    assert result["decision"]["conclusion"] == (
        "제공 문서에서 관련 근거를 확인하지 못해 판단할 수 없습니다."
    )
    assert result["decision"]["missing_conditions"] == ["제공 문서의 관련 근거"]
    assert result["evidence"] == []


def test_no_evidence_discards_ungrounded_model_conclusion_and_conditions() -> None:
    search = FakeSearchAdapter(
        SearchResult(execution_status="completed", coverage="none", limitations=["근거 없음"])
    )
    agent = create_policy_agent(
        model=_model(
            conclusion="모든 가입자는 언제나 이전할 수 있습니다.",
            missing_conditions=["가입자의 임의 조건"],
        ),
        search_adapter=cast(SearchAgentAdapter, search),
    )
    try:
        result = agent({"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"})
    finally:
        agent.close()

    assert result["decision"] == {
        "status": "undetermined",
        "conclusion": "제공 문서에서 관련 근거를 확인하지 못해 판단할 수 없습니다.",
        "missing_conditions": ["제공 문서의 관련 근거"],
    }
    assert "언제나 이전" not in str(result)
    assert "가입자의 임의 조건" not in str(result)


def test_partial_evidence_cannot_be_promoted_to_determined() -> None:
    search = FakeSearchAdapter(
        SearchResult(
            execution_status="completed",
            coverage="partial",
            selected_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
        )
    )
    agent = create_policy_agent(
        model=_model(),
        search_adapter=cast(SearchAgentAdapter, search),
    )
    try:
        result = agent({"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"})
    finally:
        agent.close()

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"]


def test_search_failure_is_returned_without_evidence() -> None:
    search = FakeSearchAdapter(
        SearchResult(execution_status="failed", error="검색을 완료하지 못했습니다.")
    )
    agent = create_product_agent(
        model=_model(),
        search_adapter=cast(SearchAgentAdapter, search),
    )
    try:
        result = agent({"question": "상품 위험은?", "objective": "상품 위험 판단"})
    finally:
        agent.close()

    assert result["execution_status"] == "failed"
    assert result["evidence"] == []
    assert result["calculations"] == []
    assert "provider" not in result["error"].lower()


def test_tax_agent_replaces_numeric_claim_without_calculator() -> None:
    search = FakeSearchAdapter(
        SearchResult(
            execution_status="completed",
            coverage="sufficient",
            selected_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
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
        search_adapter=cast(SearchAgentAdapter, search),
    )
    try:
        result = agent({"question": "세율은?", "objective": "세율 판단"})
    finally:
        agent.close()

    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["conclusion"] == (
        "확정 수치 판단에는 결정론적 계산 Tool 결과가 필요합니다."
    )
    assert "10" not in result["decision"]["conclusion"]
    assert result["calculations"] == []


def test_tax_agent_blocks_numeric_claims_from_all_untrusted_text_fields() -> None:
    search = FakeSearchAdapter(
        SearchResult(
            execution_status="completed",
            coverage="sufficient",
            selected_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
            limitations=["한도는 900만원입니다.", "자료 범위가 제한적입니다."],
        )
    )
    agent = create_tax_payout_agent(
        model=_model(
            conclusion="계산 결과를 확인해야 합니다.",
            missing_conditions=["연봉 5천만원 여부"],
            warnings=["세율은 10%입니다.", "일반적인 주의가 필요합니다."],
        ),
        search_adapter=cast(SearchAgentAdapter, search),
    )
    try:
        result = agent({"question": "공제액은?", "objective": "공제액 판단"})
    finally:
        agent.close()

    serialized = str(result)
    assert result["decision"]["status"] == "conditional"
    assert result["decision"]["missing_conditions"] == ["결정론적 계산 Tool 결과"]
    assert "10%" not in serialized
    assert "900만원" not in serialized
    assert "5천만원" not in serialized
    assert "일반적인 주의가 필요합니다." in result["warnings"]
    assert "자료 범위가 제한적입니다." in result["warnings"]


def test_not_applicable_result_cannot_expose_substantive_ungrounded_conclusion() -> None:
    search = FakeSearchAdapter(
        SearchResult(
            execution_status="completed",
            coverage="sufficient",
            selected_chunks=[_chunk(DocumentType.PENSION_REFERENCE)],
        )
    )
    agent = create_policy_agent(
        model=_model(
            decision_status="not_applicable",
            conclusion="연금 이전은 언제나 가능합니다.",
            warnings=["반드시 이전하세요."],
        ),
        search_adapter=cast(SearchAgentAdapter, search),
    )
    try:
        result = agent({"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"})
    finally:
        agent.close()

    assert result["decision"] == {
        "status": "not_applicable",
        "conclusion": "이 질문에는 해당 도메인 판단이 적용되지 않습니다.",
        "missing_conditions": [],
    }
    assert result["warnings"] == []
    assert result["evidence"] == []


def test_domain_agent_rejects_new_work_instead_of_queueing_behind_timeout() -> None:
    started = Event()
    release = Event()

    class BlockingGraph:
        def invoke(self, input: dict[str, Any], /) -> dict[str, Any]:
            del input
            started.set()
            release.wait(timeout=1)
            return {}

    agent = DomainAgent(
        domain="policy",
        graph=BlockingGraph(),
        config=DomainAgentConfig(timeout_seconds=0.01),
        max_workers=1,
    )
    request = {"question": "이전할 수 있나요?", "objective": "이전 가능 여부 판단"}
    try:
        first = agent(request)
        assert started.is_set()
        second = agent(request)
    finally:
        release.set()
        agent.close()

    assert first["execution_status"] == "timeout"
    assert second["execution_status"] == "failed"
    assert "처리 가능한 요청 수" in second["error"]


def test_domain_prompts_are_packaged_and_tax_prompt_blocks_numeric_generation() -> None:
    assert "search_documents" in load_policy_agent_prompt()
    assert "search_documents" in load_product_agent_prompt()
    tax_prompt = load_tax_payout_agent_prompt()
    assert "확정 세금, 금액, 세율, 한도를 생성하지 않는다" in tax_prompt
    assert "submit_domain_result" in tax_prompt
