"""실제 SDK를 모의 HTTP에 연결해 실험 관측이 재시도와 원문 응답을 보존하는지 확인한다."""

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from langsmith import tracing_context
from pydantic import BaseModel, SecretStr, ValidationError

from evals.catalog_selection.run import (
    HttpObserver,
    ModelObserver,
    exception_info,
    query_from_output,
)
from pension_agent.agent.execution import AsyncConcurrencyLimiter, ModelConcurrencyMiddleware
from pension_agent.agent.model_factory import create_chat_clovax
from pension_agent.agent.product.catalog_query import (
    CatalogQueryPlanError,
    HCXProductCatalogQueryPlanner,
)
from pension_agent.agent.product.catalog_selection import CatalogSelectionMode
from pension_agent.config import DEFAULT_DOMAIN_AGENT_HCX_CONFIG, ClovaStudioConnection
from pension_agent.retrieval import load_product_catalog


@pytest.mark.parametrize("mode", ["compact_codes", "row_codes", "row_ids"])
@pytest.mark.parametrize("retry", [False, True], ids=["first-success", "sdk-retry"])
def test_real_sdk_preserves_bound_callbacks_and_every_http_attempt(
    mode: CatalogSelectionMode, retry: bool, tmp_path: Path
) -> None:
    catalog = load_product_catalog()
    code = catalog.products[0].product_code
    key = "selected_row_id" if mode == "row_ids" else "product_code"
    query = {
        "route": "resolve_product",
        "resolution_status": "single",
        key: "P001" if mode == "row_ids" else code,
    }
    observer = HttpObserver()
    observer.directory = tmp_path
    requests: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if retry and len(requests) == 1:
            return httpx.Response(
                429,
                json={"error": {"code": "42901", "message": "rate limited"}},
                headers={"retry-after": "0.001"},
            )
        return httpx.Response(
            200,
            json={
                "id": "fake-completion",
                "object": "chat.completion",
                "created": 1,
                "model": "HCX-007",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "fake-tool-call",
                                    "type": "function",
                                    "function": {
                                        "name": "return_product_catalog_query",
                                        "arguments": json.dumps({"query": query}),
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 123, "completion_tokens": 17, "total_tokens": 140},
            },
        )

    async def invoke() -> None:
        with httpx.Client(transport=httpx.MockTransport(respond)) as sync_client:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(respond),
                event_hooks={"request": [observer.request], "response": [observer.response]},
            ) as async_client:
                model = create_chat_clovax(
                    config=DEFAULT_DOMAIN_AGENT_HCX_CONFIG,
                    connection=ClovaStudioConnection(
                        api_key=SecretStr("observer-test-key"),
                        api_base_url="https://hcx.invalid/v1/openai",
                        _env_file=None,
                    ),
                    http_client=sync_client,
                    http_async_client=async_client,
                )
                planner = HCXProductCatalogQueryPlanner(
                    model=model,
                    catalog=catalog,
                    selection_mode=mode,
                    model_concurrency=ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1)),
                )
                model_observer = ModelObserver()
                model.callbacks = [model_observer]
                with tracing_context(enabled=False):
                    plan = await planner.plan(
                        question=code,
                        objective="입력한 상품을 식별한다.",
                        deadline=asyncio.get_running_loop().time() + 75,
                    )

                assert plan.product_code == code
                assert len(model_observer.calls) == 1
                call = next(iter(model_observer.calls.values()))
                assert call["input"][1]["data"]["content"]
                assert query_from_output(call["output"]) == query
                assert call["output"]["usage_metadata"]["input_tokens"] == 123
                assert call["output"]["usage_metadata"]["output_tokens"] == 17

    asyncio.run(invoke())

    expected_statuses = [429, 200] if retry else [200]
    assert [attempt["status_code"] for attempt in observer.attempts] == expected_statuses
    assert all(attempt["response_complete"] for attempt in observer.attempts)
    assert len(requests) == len(expected_statuses)
    assert requests[0]["model"] == "HCX-007"
    assert requests[0]["tool_choice"]["function"]["name"] == "return_product_catalog_query"
    assert requests[0]["max_completion_tokens"] == 1024
    for index, status in enumerate(expected_statuses, start=1):
        assert (tmp_path / f"http-{index:02d}.request.json").is_file()
        assert (tmp_path / f"http-{index:02d}.response.txt").is_file()
    assert "observer-test-key" not in "".join(path.read_text() for path in tmp_path.iterdir())


@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, asyncio.CancelledError])
def test_response_status_survives_body_timeout_or_cancellation(
    error_type: type[BaseException], tmp_path: Path
) -> None:
    observer = HttpObserver()
    observer.directory = tmp_path

    class FailedBody(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"partial"
            raise error_type("connection details must not be recorded")

    async def invoke() -> None:
        request = httpx.Request("POST", "https://hcx.invalid", json={"messages": []})
        await observer.request(request)
        response = httpx.Response(200, request=request, stream=FailedBody())
        with pytest.raises(error_type):
            await observer.response(response)

    asyncio.run(invoke())

    attempt = json.loads((tmp_path / "http-attempts.json").read_text())[0]
    assert attempt["status_code"] == 200
    assert attempt["response_complete"] is False
    assert attempt["body_read_error"][0]["type"] == error_type.__name__
    assert attempt["latency_seconds"] >= attempt["headers_latency_seconds"]
    assert "connection details" not in json.dumps(attempt)


def test_exception_chain_preserves_validation_location_without_raw_input() -> None:
    class ExpectedQuery(BaseModel):
        selected_row_id: int

    with pytest.raises(ValidationError) as caught:
        ExpectedQuery.model_validate({"selected_row_id": "secret-invalid-value"})
    error = CatalogQueryPlanError("조회 계획 형식이 올바르지 않습니다.")
    error.__cause__ = caught.value

    details = exception_info(error)

    assert details[0]["message"] == "조회 계획 형식이 올바르지 않습니다."
    assert details[1]["validation_errors"] == [{"type": "int_parsing", "loc": ("selected_row_id",)}]
    assert "secret-invalid-value" not in json.dumps(details)


def test_unrecognized_exception_does_not_copy_connection_message() -> None:
    details = exception_info(ValueError("https://token-secret@hcx.invalid/request"))

    assert details[0]["type"] == "ValueError"
    assert "token-secret" not in json.dumps(details)
