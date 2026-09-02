"""실제 Qdrant Adapter를 통과하는 Agent/API 수직 경로를 검증한다."""

from collections.abc import Sequence
from typing import Any, ClassVar

import pytest
from langchain.messages import AIMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import Runnable
from qdrant_client import AsyncQdrantClient, models

from pension_agent.agent.orchestration import (
    AnswerService,
    create_domain_agent_tool,
    create_main_supervisor,
)
from pension_agent.agent.policy import (
    POLICY_TOOL_DESCRIPTION,
    POLICY_TOOL_NAME,
    create_policy_agent,
)
from pension_agent.agent.search import SearchService
from pension_agent.agent.tax_payout import (
    TAX_PAYOUT_TOOL_DESCRIPTION,
    TAX_PAYOUT_TOOL_NAME,
    create_tax_payout_agent,
)
from pension_agent.api.presentation import build_answer_response
from pension_agent.config import SearchServiceConfig
from pension_agent.core import SearchMode
from pension_agent.retrieval import AsyncQdrantChunkRetriever

CHUNK_ID = "550e8400-e29b-41d4-a716-446655440000"


class ToolCallingFakeModel(FakeMessagesListChatModel):
    bindings: ClassVar[list[tuple[list[str], dict[str, Any]]]] = []

    def bind_tools(
        self,
        tools: Sequence[Any],
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        self.bindings.append(([tool.name for tool in tools], kwargs))
        return self


class FakeEmbedder:
    async def aembed_query(self, text: str) -> list[float]:
        assert text == "IRP 이전 절차"
        return [1.0, 0.0]


async def _qdrant() -> AsyncQdrantClient:
    client = AsyncQdrantClient(":memory:")
    await client.create_collection(
        collection_name="pension_documents_v1",
        vectors_config={"dense": models.VectorParams(size=2, distance=models.Distance.COSINE)},
    )
    await client.upsert(
        collection_name="pension_documents_v1",
        points=[
            models.PointStruct(
                id=CHUNK_ID,
                vector={"dense": [1.0, 0.0]},
                payload={
                    "source_file_name": "pension-guide.pdf",
                    "source_format": "pdf",
                    "document_type": "pension_reference",
                    "chunk_index": 3,
                    "content": "IRP 계좌 이전은 접수 절차와 가입 유형 확인이 필요합니다.",
                    "embedding_content": "IRP 계좌 이전 접수 절차",
                    "heading_path": ["IRP 이전"],
                    "captions": [],
                    "element_types": ["text"],
                    "page_numbers": [4],
                },
            )
        ],
    )
    return client


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_main_domain_search_qdrant_to_five_field_response() -> None:
    client = await _qdrant()
    retriever = AsyncQdrantChunkRetriever(client, collection_name="pension_documents_v1")
    search_service = SearchService(
        embedder=FakeEmbedder(),
        retriever=retriever,
        config=SearchServiceConfig(
            default_search_mode=SearchMode.DENSE,
            candidate_limit=3,
            result_limit=3,
        ),
    )

    domain_model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "IRP 이전 절차"},
                        "id": "domain-search",
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
                            "conclusion": "IRP 이전은 접수 절차와 가입 유형 확인이 필요합니다.",
                            "missing_conditions": ["가입 유형"],
                            "warnings": [],
                            "evidence_chunk_ids": [CHUNK_ID],
                        },
                        "id": "domain-submit",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    policy_agent = create_policy_agent(model=domain_model, search_service=search_service)
    policy_tool = create_domain_agent_tool(
        name=POLICY_TOOL_NAME,
        description=POLICY_TOOL_DESCRIPTION,
        domain="policy",
        runner=policy_agent,
    )
    supervisor_model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "analyze_policy",
                        "args": {"objective": "IRP 이전 가능 조건과 절차 판단"},
                        "id": "policy-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="가입 유형을 확인한 뒤 IRP 이전 접수 절차를 진행하세요."),
        ]
    )
    service = AnswerService(create_main_supervisor(model=supervisor_model, tools=[policy_tool]))

    try:
        result = await service.run(
            question_id="Q-E2E-001",
            question="IRP 계좌를 이전하려면 어떻게 해야 하나요?",
        )
        response = build_answer_response(result).model_dump()
    finally:
        await service.aclose()
        await client.close()

    assert set(response) == {
        "question_id",
        "question",
        "retrieved_context",
        "think_trace",
        "answer",
    }
    assert response["question_id"] == "Q-E2E-001"
    assert response["question"] == "IRP 계좌를 이전하려면 어떻게 해야 하나요?"
    assert response["retrieved_context"] == [
        {
            "chunk_id": CHUNK_ID,
            "source_file_name": "pension-guide.pdf",
            "title": "IRP 이전",
            "locator": "4페이지",
            "content": "IRP 계좌 이전은 접수 절차와 가입 유형 확인이 필요합니다.",
        }
    ]
    assert "policy(완료)" in response["think_trace"]
    assert response["answer"] == "가입 유형을 확인한 뒤 IRP 이전 접수 절차를 진행하세요."


TAX_CHUNK_ID = "660e8400-e29b-41d4-a716-446655440099"


class TaxPayoutFakeEmbedder:
    async def aembed_query(self, text: str) -> list[float]:
        assert text == "연금수령한도 산식 확인"
        return [0.0, 1.0]


async def _qdrant_with_pension_limit_chunk() -> AsyncQdrantClient:
    client = AsyncQdrantClient(":memory:")
    await client.create_collection(
        collection_name="pension_documents_v1",
        vectors_config={"dense": models.VectorParams(size=2, distance=models.Distance.COSINE)},
    )
    await client.upsert(
        collection_name="pension_documents_v1",
        points=[
            models.PointStruct(
                id=TAX_CHUNK_ID,
                vector={"dense": [0.0, 1.0]},
                payload={
                    "source_file_name": "pension-guide.pdf",
                    "source_format": "pdf",
                    "document_type": "pension_reference",
                    "chunk_index": 5,
                    "content": "평가액 1천만원, 수령연차 1년차에 대한 산식입니다.",
                    "embedding_content": "연금수령한도 산식",
                    "heading_path": ["연금수령한도"],
                    "captions": [],
                    "element_types": ["text"],
                    "page_numbers": [7],
                },
            )
        ],
    )
    return client


@pytest.mark.anyio
async def test_main_domain_tax_payout_calculation_qdrant_vertical() -> None:
    client = await _qdrant_with_pension_limit_chunk()
    retriever = AsyncQdrantChunkRetriever(client, collection_name="pension_documents_v1")
    search_service = SearchService(
        embedder=TaxPayoutFakeEmbedder(),
        retriever=retriever,
        config=SearchServiceConfig(
            default_search_mode=SearchMode.DENSE,
            candidate_limit=3,
            result_limit=3,
        ),
    )

    domain_model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "연금수령한도 산식 확인"},
                        "id": "domain-search",
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
                        "id": "domain-calculation",
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
                        "id": "domain-submit",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    tax_payout_agent = create_tax_payout_agent(model=domain_model, search_service=search_service)
    tax_payout_tool = create_domain_agent_tool(
        name=TAX_PAYOUT_TOOL_NAME,
        description=TAX_PAYOUT_TOOL_DESCRIPTION,
        domain="tax_payout",
        runner=tax_payout_agent,
    )
    supervisor_model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": TAX_PAYOUT_TOOL_NAME,
                        "args": {"objective": "연금수령한도 계산"},
                        "id": "tax-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="연금수령한도 계산 결과를 확인했습니다."),
        ]
    )
    service = AnswerService(create_main_supervisor(model=supervisor_model, tools=[tax_payout_tool]))

    try:
        result = await service.run(
            question_id="Q-E2E-002",
            question="제 연금계좌 연금수령한도가 얼마인지 계산해 주세요.",
        )
        response = build_answer_response(result).model_dump()
    finally:
        await service.aclose()
        await client.close()

    assert set(response) == {
        "question_id",
        "question",
        "retrieved_context",
        "think_trace",
        "answer",
    }
    assert response["question_id"] == "Q-E2E-002"
    assert response["question"] == "제 연금계좌 연금수령한도가 얼마인지 계산해 주세요."
    assert response["retrieved_context"] == [
        {
            "chunk_id": TAX_CHUNK_ID,
            "source_file_name": "pension-guide.pdf",
            "title": "연금수령한도",
            "locator": "7페이지",
            "content": "평가액 1천만원, 수령연차 1년차에 대한 산식입니다.",
        }
    ]
    assert "tax_payout(완료)" in response["think_trace"]
    # 계산 도메인 결과가 있으면 `_stabilize_calculation_answer`가 LLM 표현을 검증된
    # Python 계산값으로 덮어쓴다(pension_agent/agent/orchestration/service.py). 따라서
    # 최종 답변은 스크립트로 지정한 supervisor 메시지가 아니라, 10,000,000 / (11-1) *
    # 1.2 = 1,200,000의 실제 계산 결과와 계산기의 고정 경고 문구여야 한다.
    assert response["answer"] == (
        "검증된 Python 계산 결과:\n"
        "- 연금수령한도: 1200000.0 KRW\n"
        "\n"
        "주의사항:\n"
        "- 출처에는 최종 지급 단위의 반올림·절사 규칙이 명시되지 않았습니다."
    )
