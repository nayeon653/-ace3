"""네트워크 호출 없이 ChatClovaX Factory 계약을 검증한다."""

import asyncio

import pytest
from httpx import AsyncClient, Client
from langchain_naver import ChatClovaX
from pydantic import SecretStr

from pension_agent.agent.model_factory import (
    ChatClovaXFactoryError,
    create_chat_clovax,
)
from pension_agent.agent.orchestration import create_main_supervisor
from pension_agent.config import (
    DEFAULT_DOMAIN_AGENT_HCX_CONFIG,
    MAIN_SUPERVISOR_HCX_CONFIG,
    ClovaStudioConnection,
)


def test_factory_creates_configured_hcx_007_without_network_call() -> None:
    connection = ClovaStudioConnection(
        api_key=SecretStr("test-secret-key"),
        api_base_url="https://example.test/v1/openai",
    )

    model = create_chat_clovax(
        config=MAIN_SUPERVISOR_HCX_CONFIG,
        connection=connection,
    )

    assert isinstance(model, ChatClovaX)
    assert model.model_name == "HCX-007"
    assert model.max_tokens == 1024
    assert model.temperature == 0.1
    assert model.request_timeout == 30.0
    assert model.max_retries == 2
    assert model.reasoning_effort == "none"
    assert model.thinking == {"effort": "none"}
    assert "test-secret-key" not in repr(model)

    supervisor = create_main_supervisor(model=model, tools=[])

    assert supervisor.name == "main_supervisor"


def test_factory_omits_thinking_for_hcx_005_domain_model() -> None:
    connection = ClovaStudioConnection(
        api_key=SecretStr("test-secret-key"),
        api_base_url="https://example.test/v1/openai",
    )

    model = create_chat_clovax(
        config=DEFAULT_DOMAIN_AGENT_HCX_CONFIG,
        connection=connection,
    )

    assert model.model_name == "HCX-005"
    assert model.reasoning_effort is None
    assert model.thinking is None


def test_factory_reports_missing_api_key_without_secret_or_network() -> None:
    connection = ClovaStudioConnection(
        api_key=None,
        api_base_url="https://example.test/v1/openai",
    )

    with pytest.raises(ChatClovaXFactoryError) as error:
        create_chat_clovax(
            config=MAIN_SUPERVISOR_HCX_CONFIG,
            connection=connection,
        )

    assert str(error.value) == "CLOVASTUDIO_API_KEY가 설정되지 않았습니다."


def test_factory_sanitizes_provider_initialization_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "provider-secret-key"
    connection = ClovaStudioConnection(
        api_key=SecretStr(secret),
        api_base_url="https://example.test/v1/openai",
    )

    def fail_to_initialize(**_: object) -> None:
        raise RuntimeError(f"인증 실패: {secret}")

    monkeypatch.setattr("pension_agent.agent.model_factory.ChatClovaX", fail_to_initialize)

    with pytest.raises(ChatClovaXFactoryError) as error:
        create_chat_clovax(
            config=MAIN_SUPERVISOR_HCX_CONFIG,
            connection=connection,
        )

    assert str(error.value) == "ChatClovaX 모델 초기화에 실패했습니다."
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert secret not in str(error.value)


def test_factory_uses_runtime_owned_http_clients() -> None:
    connection = ClovaStudioConnection(
        api_key=SecretStr("test-secret-key"),
        api_base_url="https://example.test/v1/openai",
    )
    http_client = Client()
    http_async_client = AsyncClient()
    try:
        model = create_chat_clovax(
            config=MAIN_SUPERVISOR_HCX_CONFIG,
            connection=connection,
            http_client=http_client,
            http_async_client=http_async_client,
        )

        assert model.http_client is http_client
        assert model.http_async_client is http_async_client
    finally:
        http_client.close()
        asyncio.run(http_async_client.aclose())
