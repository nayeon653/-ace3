"""HyperCLOVA X 동작 설정과 연결 설정을 검증한다."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from pension_agent.config import (
    DEFAULT_DOMAIN_AGENT_HCX_CONFIG,
    MAIN_SUPERVISOR_HCX_CONFIG,
    POLICY_AGENT_HCX_CONFIG,
    PRODUCT_REACT_HCX_CONFIG,
    ChatClovaXConfig,
    ClovaStudioConnection,
)


def test_main_supervisor_config_is_versioned_and_immutable() -> None:
    assert MAIN_SUPERVISOR_HCX_CONFIG == ChatClovaXConfig(
        model="HCX-007",
        max_tokens=1024,
        temperature=0.1,
        timeout_seconds=30.0,
        max_retries=2,
        thinking_effort="none",
    )

    with pytest.raises(ValidationError, match="frozen"):
        MAIN_SUPERVISOR_HCX_CONFIG.model = "HCX-DASH-002"  # type: ignore[misc]


def test_role_configs_assign_models_by_runtime_responsibility() -> None:
    assert POLICY_AGENT_HCX_CONFIG.model == "HCX-007"
    assert POLICY_AGENT_HCX_CONFIG.thinking_effort == "none"
    assert PRODUCT_REACT_HCX_CONFIG.model == "HCX-007"
    assert PRODUCT_REACT_HCX_CONFIG.thinking_effort == "none"
    assert DEFAULT_DOMAIN_AGENT_HCX_CONFIG.model == "HCX-005"
    assert DEFAULT_DOMAIN_AGENT_HCX_CONFIG.thinking_effort is None


def test_function_calling_config_requires_at_least_1024_tokens() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 1024"):
        ChatClovaXConfig(
            model="HCX-005",
            max_tokens=1023,
            temperature=0.1,
            timeout_seconds=30.0,
            max_retries=2,
        )


def test_connection_reads_only_authentication_and_endpoint_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLOVASTUDIO_API_KEY", "test-secret-key")
    monkeypatch.setenv("CLOVASTUDIO_API_BASE_URL", "https://example.test/v1/openai")
    monkeypatch.setenv("HCX_MODEL_FUNCTION_CALLING", "HCX-DASH-002")

    connection = ClovaStudioConnection(_env_file=None)

    assert connection.api_key is not None
    assert connection.api_key.get_secret_value() == "test-secret-key"
    assert connection.api_base_url == "https://example.test/v1/openai"
    assert MAIN_SUPERVISOR_HCX_CONFIG.model == "HCX-007"
    assert "test-secret-key" not in repr(connection)


def test_connection_reads_dotenv_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLOVASTUDIO_API_KEY", raising=False)
    monkeypatch.delenv("CLOVASTUDIO_API_BASE_URL", raising=False)
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "CLOVASTUDIO_API_KEY=dotenv-secret-key\n"
        "CLOVASTUDIO_API_BASE_URL=https://dotenv.example/v1/openai\n",
        encoding="utf-8",
    )

    connection = ClovaStudioConnection(_env_file=dotenv_path)

    assert connection.api_key is not None
    assert connection.api_key.get_secret_value() == "dotenv-secret-key"
    assert connection.api_base_url == "https://dotenv.example/v1/openai"
    assert "dotenv-secret-key" not in repr(connection)
