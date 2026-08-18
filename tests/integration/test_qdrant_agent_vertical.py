"""실제 Qdrant Adapter를 통과하는 Agent/API 수직 경로를 검증한다."""

from collections.abc import Sequence
from typing import Any, ClassVar

from langchain.messages import AIMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import Runnable
from qdrant_client import QdrantClient, models

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
from pension_agent.agent.search import SearchAgentAdapter, create_search_agent
from pension_agent.api.presentation import build_answer_response
from pension_agent.retrieval import QdrantChunkRetriever

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
    def embed_query(self, text: str) -> list[float]:
        assert text == "IRP 이전 절차"
        return [1.0, 0.0]


def _qdrant() -> QdrantClient:
    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name="pension_documents_v1",
        vectors_config={"dense": models.VectorParams(size=2, distance=models.Distance.COSINE)},
    )
    client.upsert(
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


def test_main_domain_search_qdrant_to_five_field_response() -> None:
    client = _qdrant()
    retriever = QdrantChunkRetriever(client, collection_name="pension_documents_v1")
    search_model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_chunks",
                        "args": {
                            "text": "IRP 이전 절차",
                            "mode": "dense",
                            "limit": 3,
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
                        "name": "submit_search_result",
                        "args": {
                            "coverage": "sufficient",
                            "selected_chunk_ids": [CHUNK_ID],
                            "limitations": [],
                        },
                        "id": "search-submit",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    search_graph = create_search_agent(
        model=search_model,
        embedder=FakeEmbedder(),
        retriever=retriever,
    )
    search_adapter = SearchAgentAdapter(search_graph)

    domain_model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"objective": "IRP 이전 절차의 문서 근거 확인"},
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
                        },
                        "id": "domain-submit",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    policy_agent = create_policy_agent(model=domain_model, search_adapter=search_adapter)
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
        result = service.run(
            question_id="Q-E2E-001",
            question="IRP 계좌를 이전하려면 어떻게 해야 하나요?",
        )
        response = build_answer_response(result).model_dump()
    finally:
        policy_agent.close()
        search_adapter.close()
        client.close()

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
