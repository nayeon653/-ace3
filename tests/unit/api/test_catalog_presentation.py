"""검증된 카탈로그 결과의 trace와 retrieved_context 직렬화를 확인한다."""

from langchain.messages import AIMessage

from pension_agent.agent.contracts import AgentAnswer, DomainResult
from pension_agent.agent.orchestration import AnswerServiceResult, SupervisorState
from pension_agent.api.presentation import build_answer_response


def test_catalog_result_is_in_trace_and_retrieved_context() -> None:
    evidence = {
        "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
        "source_file_name": "product_catalog.json",
        "title": "검증된 상품 카탈로그 조회 결과",
        "locator": "provider=미래에셋;catalog_version=v1",
        "content": '{"total_count":1}',
    }
    domain_result: DomainResult = {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "determined",
            "conclusion": "미래에셋 상품 1개를 조회했습니다.",
            "missing_conditions": [],
        },
        "evidence": [evidence],
        "calculations": [],
        "warnings": [],
        "catalog_result": {
            "route": "browse_catalog",
            "provider": "미래에셋",
            "return_mode": "count_and_items",
            "total_count": 1,
            "items": [
                {
                    "product_code": "KR510902511M",
                    "official_name": "미래에셋장기성장포커스",
                    "provider": "미래에셋",
                }
            ],
            "catalog_version": "v1",
        },
    }
    state: SupervisorState = {
        "messages": [AIMessage(content="검증된 답변")],
        "question_id": "Q-catalog",
        "question": "미래에셋 상품은 몇 개고 어떤 것들이 있나요?",
        "domain_results": [domain_result],
    }

    response = build_answer_response(
        AnswerServiceResult(answer=AgentAnswer(answer="검증된 답변"), state=state)
    ).model_dump()

    assert response["retrieved_context"] == [evidence]
    assert "route=browse_catalog" in response["think_trace"]
    assert "provider=미래에셋" in response["think_trace"]
    assert "total_count=1" in response["think_trace"]
    assert "catalog_version=v1" in response["think_trace"]
