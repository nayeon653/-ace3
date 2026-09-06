"""비교 답안의 독립 입력, 실행 예산과 근거 선택 경로를 확인한다."""

import asyncio
import json
from collections.abc import Sequence
from typing import Any

import httpx
import pytest
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable
from openai import APIStatusError, OpenAIError
from pydantic import Field

from pension_agent.agent.contracts.comparison import ComparisonTarget
from pension_agent.agent.execution import AsyncConcurrencyLimiter, ModelConcurrencyMiddleware
from pension_agent.agent.product.comparison import ComparisonEvidenceResult, ProductEvidence
from pension_agent.agent.product.comparison_answer import (
    PRODUCT_COMPARISON_ANSWER_TOOL_NAME,
    ComparisonAnswerError,
    HCXProductComparisonAnswerWriter,
)
from pension_agent.agent.search import SearchChunkPayload, SearchResult
from pension_agent.core import DocumentType


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class RecordingModel(FakeMessagesListChatModel):
    """실제 모델 입력과 호출 횟수, 대기·제공자 실패를 재현한다."""

    received_messages: list[list[BaseMessage]] = Field(default_factory=list)
    bindings: list[dict[str, Any]] = Field(default_factory=list)
    delay_seconds: float = 0
    failures: list[Exception] = Field(default_factory=list)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.received_messages.append(list(messages))
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.failures:
            raise self.failures.pop(0)
        return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable[Any, AIMessage]:
        self.bindings.append({"tools": [item.name for item in tools], **kwargs})
        return self


def _chunk(
    chunk_id: str, *, content: str = "투자원금 손실이 발생할 수 있습니다."
) -> SearchChunkPayload:
    return SearchChunkPayload(
        chunk_id=chunk_id,
        source_file_name="비교상품설명서.pdf",
        document_type=DocumentType.FUND_PROSPECTUS,
        chunk_index=0,
        title="위험과 조건",
        locator="제2부 투자위험",
        content=content,
    )


def _comparison(*, with_evidence: bool = True, partial: bool = False) -> ComparisonEvidenceResult:
    targets: list[ComparisonTarget] = [
        {
            "target_id": f"target-{index}",
            "mention_parts": [name],
            "resolution_status": "single",
            "product_code": code,
            "official_name": name,
            "provider": "예시운용사",
        }
        for index, (code, name) in enumerate(
            [("KR0000000001", "비교상품 단기"), ("KR0000000002", "비교상품 장기")],
            start=1,
        )
    ]
    shared = _chunk(
        "00000000-0000-0000-0000-000000000001",
        content="문서 조건 및 예외를 생략하지 않은 전체 근거 " * 150,
    )
    first = [shared, _chunk("00000000-0000-0000-0000-000000000002")] if with_evidence else []
    second = [shared, _chunk("00000000-0000-0000-0000-000000000003")] if with_evidence else []
    second_attempt = (
        SearchResult(execution_status="timeout", error="일부 상품 검색 시간 초과")
        if partial
        else SearchResult(execution_status="completed", retrieved_chunks=second)
    )
    products = [
        ProductEvidence(
            product_code=target["product_code"],
            official_name=target["official_name"],
            provider=target["provider"],
            source_file_name="비교상품설명서.pdf",
            attempts=[
                SearchResult(execution_status="completed", retrieved_chunks=first)
                if index == 0
                else second_attempt
            ],
            evidence=first if index == 0 else second_attempt.retrieved_chunks,
        )
        for index, target in enumerate(targets)
    ]
    return ComparisonEvidenceResult(
        execution_status="completed",
        catalog_version="catalog-test-version",
        comparison_query="환헤지 방식과 외화 노출, 분배금 지급 주기를 비교해 주세요.",
        targets=targets,
        products=products,
        limitations=["일부 상품 검색 시간 초과"] if partial else [],
    )


def _response(**overrides: Any) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": PRODUCT_COMPARISON_ANSWER_TOOL_NAME,
                "args": {
                    "answer": "두 상품 모두 손실 위험이 있습니다. [비교상품설명서.pdf, 제2부 투자위험]",
                    "status": "determined",
                    "missing_conditions": [],
                    "warnings": [],
                    "evidence_chunk_ids": ["00000000-0000-0000-0000-000000000001"],
                    **overrides,
                },
                "id": "comparison-answer-call",
                "type": "tool_call",
            }
        ],
    )


async def _write(
    writer: HCXProductComparisonAnswerWriter,
    comparison: ComparisonEvidenceResult | None = None,
    *,
    deadline: float | None = None,
) -> dict[str, Any]:
    return await writer.write(
        question="비교상품 단기와 장기는 어떻게 달라요? 안정적인 걸 원해요.",
        objective="확정된 두 상품의 위험과 원금보장 비교",
        comparison=_comparison() if comparison is None else comparison,
        deadline=asyncio.get_running_loop().time() + 5 if deadline is None else deadline,
    )


@pytest.mark.anyio
async def test_writer_builds_fresh_input_with_full_deduplicated_evidence() -> None:
    model = RecordingModel(responses=[_response()])
    comparison = _comparison()
    writer = HCXProductComparisonAnswerWriter(model=model)

    result = await _write(writer, comparison)

    assert model.bindings == [
        {
            "tools": [PRODUCT_COMPARISON_ANSWER_TOOL_NAME],
            "tool_choice": PRODUCT_COMPARISON_ANSWER_TOOL_NAME,
        }
    ]
    assert len(model.received_messages) == 1
    messages = model.received_messages[0]
    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    context = json.loads(str(messages[1].content))
    assert context["question"] == "비교상품 단기와 장기는 어떻게 달라요? 안정적인 걸 원해요."
    assert context["objective"] == "확정된 두 상품의 위험과 원금보장 비교"
    assert context["targets"] == comparison.targets
    assert context["comparison_query"] == comparison.comparison_query
    assert [chunk["chunk_id"] for chunk in context["evidence"]] == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000003",
    ]
    assert context["evidence"][0]["content"] == comparison.products[0].evidence[0].content
    assert context["products"][0]["evidence_ids"] == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    ]
    assert context["products"][1]["evidence_ids"] == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000003",
    ]
    assert "attempts" not in str(messages[1].content)
    assert "retrieved_chunks" not in str(messages[1].content)
    assert result["comparison_answer"] == result["decision"]["conclusion"]
    assert "comparison_result" not in result


@pytest.mark.anyio
async def test_writer_preserves_answer_without_semantic_or_completeness_rejection() -> None:
    answer = "문서와 무관한 비교 결론을 그대로 보존하는 평가용 답안"
    model = RecordingModel(
        responses=[
            _response(
                answer=answer,
                status="determined",
                missing_conditions=["모델이 작성한 조건"],
                evidence_chunk_ids=[
                    "unknown",
                    "00000000-0000-0000-0000-000000000003",
                    "00000000-0000-0000-0000-000000000003",
                ],
            )
        ]
    )

    result = await _write(HCXProductComparisonAnswerWriter(model=model))

    assert len(model.received_messages) == 1
    assert result["comparison_answer"] == answer
    assert result["decision"] == {
        "conclusion": answer,
        "status": "determined",
        "missing_conditions": ["모델이 작성한 조건"],
    }
    assert [chunk["chunk_id"] for chunk in result["evidence"]] == [
        "00000000-0000-0000-0000-000000000003"
    ]


@pytest.mark.anyio
async def test_unknown_citations_do_not_add_documents_or_reject_the_answer() -> None:
    model = RecordingModel(responses=[_response(evidence_chunk_ids=["unknown"])])

    result = await _write(HCXProductComparisonAnswerWriter(model=model))

    assert result["execution_status"] == "completed"
    assert result["evidence"] == []
    assert len(model.received_messages) == 1


@pytest.mark.anyio
async def test_partial_search_preserves_limitations_in_context_and_result() -> None:
    comparison = _comparison(partial=True)
    model = RecordingModel(
        responses=[
            _response(
                status="conditional",
                missing_conditions=["장기 상품의 문서 근거"],
                warnings=["일부 상품 검색 시간 초과", "원금보장 여부 확인 필요"],
            )
        ]
    )

    result = await _write(HCXProductComparisonAnswerWriter(model=model), comparison)

    context = json.loads(str(model.received_messages[0][1].content))
    assert context["limitations"] == comparison.limitations
    assert context["products"][1]["evidence_ids"] == []
    assert context["products"][1]["last_search_status"] == "timeout"
    assert result["warnings"] == ["일부 상품 검색 시간 초과", "원금보장 여부 확인 필요"]
    assert result["decision"]["status"] == "conditional"


@pytest.mark.anyio
async def test_completed_search_without_evidence_returns_undetermined_without_model() -> None:
    model = RecordingModel(responses=[])

    result = await _write(
        HCXProductComparisonAnswerWriter(model=model), _comparison(with_evidence=False)
    )

    assert model.received_messages == []
    assert result["execution_status"] == "completed"
    assert result["decision"]["status"] == "undetermined"
    assert result["decision"]["missing_conditions"]
    assert result["comparison_answer"] == result["decision"]["conclusion"]
    assert result["evidence"] == []


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["failed", "timeout"])
async def test_search_failure_returns_without_model(status: str) -> None:
    model = RecordingModel(responses=[])
    comparison = ComparisonEvidenceResult.model_validate(
        {
            "execution_status": status,
            "catalog_version": "catalog-test-version",
            "targets": _comparison().targets,
            "comparison_query": "환헤지 방식 비교",
            "error": "상품 비교 문서 검색에 실패했습니다.",
            "limitations": ["상품 문서 검색 제한"],
        }
    )

    result = await _write(HCXProductComparisonAnswerWriter(model=model), comparison)

    assert model.received_messages == []
    assert result["execution_status"] == status
    assert result["error"] == comparison.error
    assert result["warnings"] == comparison.limitations
    assert result["evidence"] == []
    assert "decision" not in result
    assert "comparison_answer" not in result


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        AIMessage(content="구조화되지 않은 답변"),
        _response(answer=123),
        _response(evidence_chunk_ids="00000000-0000-0000-0000-000000000001"),
        _response(status="invalid"),
    ],
)
async def test_malformed_output_fails_without_correction_call(response: AIMessage) -> None:
    model = RecordingModel(responses=[response])

    with pytest.raises(ComparisonAnswerError):
        await _write(HCXProductComparisonAnswerWriter(model=model))

    assert len(model.received_messages) == 1


@pytest.mark.anyio
async def test_provider_error_is_sanitized_without_content_retry() -> None:
    model = RecordingModel(responses=[], failures=[OpenAIError("private provider payload")])

    with pytest.raises(
        ComparisonAnswerError, match="HCX 상품 비교 답안을 읽지 못했습니다"
    ) as caught:
        await _write(HCXProductComparisonAnswerWriter(model=model))

    assert "private" not in str(caught.value)
    assert len(model.received_messages) == 1


@pytest.mark.anyio
async def test_writer_preserves_shared_infrastructure_transient_retry() -> None:
    response = httpx.Response(
        429,
        headers={"retry-after": "0"},
        request=httpx.Request("POST", "https://example.test/chat/completions"),
    )
    failure = APIStatusError("rate limited", response=response, body={"code": "42901"})
    model = RecordingModel(responses=[_response()], failures=[failure])
    writer = HCXProductComparisonAnswerWriter(
        model=model,
        model_concurrency=ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1)),
    )

    result = await _write(writer)

    assert len(model.received_messages) == 2
    assert model.received_messages[0] == model.received_messages[1]
    assert result["execution_status"] == "completed"


@pytest.mark.anyio
async def test_deadline_cancels_model_and_does_not_retry() -> None:
    model = RecordingModel(responses=[_response()], delay_seconds=5)

    with pytest.raises(TimeoutError):
        await _write(
            HCXProductComparisonAnswerWriter(model=model),
            deadline=asyncio.get_running_loop().time() + 0.02,
        )

    assert len(model.received_messages) == 1


@pytest.mark.anyio
async def test_expired_deadline_does_not_invoke_model() -> None:
    model = RecordingModel(responses=[_response()])

    with pytest.raises(TimeoutError):
        await _write(
            HCXProductComparisonAnswerWriter(model=model),
            deadline=asyncio.get_running_loop().time() - 1,
        )

    assert model.received_messages == []


@pytest.mark.anyio
async def test_shared_concurrency_wait_is_included_in_deadline_and_releases_slot() -> None:
    model = RecordingModel(responses=[_response()])
    limiter = AsyncConcurrencyLimiter(1)
    writer = HCXProductComparisonAnswerWriter(
        model=model, model_concurrency=ModelConcurrencyMiddleware(limiter)
    )

    async with limiter.slot():
        with pytest.raises(TimeoutError):
            await _write(writer, deadline=asyncio.get_running_loop().time() + 0.02)
        assert model.received_messages == []

    result = await _write(writer)

    assert result["execution_status"] == "completed"
    assert len(model.received_messages) == 1
