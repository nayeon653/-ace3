"""FastAPI 평가 응답과 오류 계약을 검증한다."""

from collections.abc import Iterator
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from pension_agent.agent.contracts import AgentAnswer, DomainResult
from pension_agent.agent.orchestration import (
    AnswerService,
    AnswerServiceOverloadedError,
    AnswerServiceResult,
    SupervisorState,
)
from pension_agent.api.app import create_app
from pension_agent.api.dependencies import get_deployment_commit_sha

REQUIRED_KEYS = {
    "question_id",
    "question",
    "retrieved_context",
    "think_trace",
    "answer",
}


class FakeAnswerService:
    """고정 결과 또는 오류를 반환하는 HTTP 테스트용 서비스."""

    def __init__(
        self,
        *,
        result: AnswerServiceResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, str]] = []
        self.close_calls = 0

    async def run(self, *, question_id: str, question: str) -> AnswerServiceResult:
        self.calls.append({"question_id": question_id, "question": question})
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result

    async def aclose(self) -> None:
        self.close_calls += 1


def _evidence(chunk_id: str, content: str) -> dict[str, str]:
    return {
        "chunk_id": chunk_id,
        "source_file_name": "policy.pdf",
        "title": "연금계좌 업무 지침",
        "locator": "3쪽",
        "content": content,
    }


def _completed_result() -> DomainResult:
    return {
        "domain": "policy",
        "execution_status": "completed",
        "decision": {
            "status": "conditional",
            "conclusion": "가입 유형에 따라 이전할 수 있습니다.",
            "missing_conditions": ["가입 유형"],
        },
        "evidence": [_evidence("CH-001", "가입 유형에 따라 이전 범위가 달라집니다.")],
        "calculations": [],
        "warnings": [],
    }


def _not_applicable_result() -> DomainResult:
    return {
        "domain": "tax_payout",
        "execution_status": "completed",
        "decision": {
            "status": "not_applicable",
            "conclusion": "세금 판단이 필요한 질문이 아닙니다.",
            "missing_conditions": [],
        },
        "evidence": [_evidence("CH-EXCLUDED", "답변에 사용하지 않은 세금 근거")],
        "calculations": [],
        "warnings": [],
    }


def _failed_result() -> DomainResult:
    return {
        "domain": "product",
        "execution_status": "failed",
        "evidence": [],
        "calculations": [],
        "warnings": [],
        "error": "provider 내부 오류와 /internal/path",
    }


def _answer_result() -> AnswerServiceResult:
    state: SupervisorState = {
        "messages": [AIMessage(content="조건을 확인하세요.")],
        "question_id": "Q-001",
        "question": "연금계좌를 이전할 수 있나요?",
        "domain_results": [
            _completed_result(),
            _not_applicable_result(),
            _failed_result(),
        ],
    }
    return AnswerServiceResult(
        answer=AgentAnswer(answer="가입 유형을 확인한 뒤 이전 가능 여부를 판단하세요."),
        state=state,
    )


@pytest.fixture
def service() -> FakeAnswerService:
    return FakeAnswerService(result=_answer_result())


@pytest.fixture
def factory_calls() -> list[None]:
    return []


@pytest.fixture
def application(
    service: FakeAnswerService,
    factory_calls: list[None],
) -> FastAPI:
    async def service_factory() -> AnswerService:
        factory_calls.append(None)
        return cast(AnswerService, service)

    return create_app(answer_service_factory=service_factory)


@pytest.fixture
def client(application: FastAPI) -> Iterator[TestClient]:
    """lifespan을 실행하고 각 테스트 뒤 override를 정리한다."""

    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def test_answer_response_has_exact_five_fields_and_preserves_request(
    client: TestClient,
    service: FakeAnswerService,
) -> None:
    response = client.get(
        "/answer",
        params={
            "question_id": "Q-001",
            "question": "연금계좌를 이전할 수 있나요?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == REQUIRED_KEYS
    assert body["question_id"] == "Q-001"
    assert body["question"] == "연금계좌를 이전할 수 있나요?"
    assert body["answer"] == "가입 유형을 확인한 뒤 이전 가능 여부를 판단하세요."
    assert body["retrieved_context"] == [
        _evidence("CH-001", "가입 유형에 따라 이전 범위가 달라집니다.")
    ]
    assert service.calls == [
        {
            "question_id": "Q-001",
            "question": "연금계좌를 이전할 수 있나요?",
        }
    ]


def test_think_trace_uses_safe_state_summary(client: TestClient) -> None:
    response = client.get(
        "/answer",
        params={
            "question_id": "Q-001",
            "question": "연금계좌를 이전할 수 있나요?",
        },
    )

    trace = response.json()["think_trace"]
    assert "policy(완료)" in trace
    assert "가입 유형" in trace
    assert "tax_payout(완료)" in trace
    assert "product(실패)" in trace
    assert "provider 내부 오류" not in trace
    assert "/internal/path" not in trace


@pytest.mark.parametrize(
    "params",
    [
        {"question": "질문"},
        {"question_id": "Q-001"},
        {"question_id": " ", "question": "질문"},
        {"question_id": "Q-001", "question": "\n\t"},
    ],
)
def test_invalid_query_returns_sanitized_bad_request(
    client: TestClient,
    service: FakeAnswerService,
    params: dict[str, str],
) -> None:
    response = client.get("/answer", params=params)

    assert response.status_code == 400
    assert response.json() == {"detail": "요청 파라미터가 올바르지 않습니다."}
    assert service.calls == []


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("stack trace와 모델 내부 메시지"),
        ValueError("/internal/path"),
    ],
)
def test_answer_failure_returns_sanitized_internal_error(
    client: TestClient,
    service: FakeAnswerService,
    error: Exception,
) -> None:
    service.error = error

    response = client.get(
        "/answer",
        params={"question_id": "Q-001", "question": "질문"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "답변을 생성하지 못했습니다."}
    assert str(error) not in response.text


def test_answer_overload_returns_sanitized_service_unavailable(
    client: TestClient,
    service: FakeAnswerService,
) -> None:
    service.error = AnswerServiceOverloadedError("내부 대기열 상태")

    response = client.get(
        "/answer",
        params={"question_id": "Q-001", "question": "질문"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "현재 처리 가능한 요청 수를 초과했습니다."}
    assert "내부 대기열 상태" not in response.text


def test_health_returns_commit_without_running_answer_service(
    client: TestClient,
    application: FastAPI,
    service: FakeAnswerService,
) -> None:
    async def deployment_commit_sha() -> str:
        return "abc123def456"

    application.dependency_overrides[get_deployment_commit_sha] = deployment_commit_sha

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "commit_sha": "abc123def456"}
    assert service.calls == []


def test_lifespan_builds_one_service_and_reuses_it(
    client: TestClient,
    service: FakeAnswerService,
    factory_calls: list[None],
) -> None:
    params = {
        "question_id": "Q-001",
        "question": "연금계좌를 이전할 수 있나요?",
    }

    first_response = client.get("/answer", params=params)
    second_response = client.get("/answer", params=params)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert len(factory_calls) == 1
    assert len(service.calls) == 2


def test_lifespan_awaits_service_close(
    application: FastAPI,
    service: FakeAnswerService,
) -> None:
    with TestClient(application):
        assert service.close_calls == 0

    assert service.close_calls == 1


def test_openapi_describes_public_contract(client: TestClient) -> None:
    openapi = client.get("/openapi.json").json()
    answer_operation = openapi["paths"]["/answer"]["get"]
    parameters = {parameter["name"]: parameter for parameter in answer_operation["parameters"]}
    answer_properties = openapi["components"]["schemas"]["AnswerResponse"]["properties"]

    assert answer_operation["summary"] == "연금 질문에 답변"
    assert parameters["question_id"]["description"]
    assert parameters["question"]["description"]
    assert all(answer_properties[field]["description"] for field in REQUIRED_KEYS)
    assert answer_operation["responses"]["400"]["description"]
    assert answer_operation["responses"]["500"]["description"]
    assert answer_operation["responses"]["503"]["description"]
