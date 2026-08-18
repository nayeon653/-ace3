"""Qdrant 환경 설정과 Cloud 자동 판정을 검증한다."""

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from pension_agent.config import QdrantConnection


def test_qdrant_connection_normalizes_url_and_hides_api_key() -> None:
    connection = QdrantConnection(
        _env_file=None,
        url="https://cluster.cloud.qdrant.io/",
        api_key=SecretStr("secret-token"),
        collection="documents",
    )

    assert connection.url == "https://cluster.cloud.qdrant.io"
    assert connection.cloud_inference_enabled is True
    assert "secret-token" not in repr(connection)


def test_qdrant_connection_rejects_non_http_url() -> None:
    with pytest.raises(ValidationError):
        QdrantConnection(_env_file=None, url="file:///tmp/qdrant")


def test_explicit_cloud_inference_overrides_endpoint_detection() -> None:
    connection = QdrantConnection(
        _env_file=None,
        url="https://sample.cloud.qdrant.io",
        cloud_inference=False,
    )

    assert connection.cloud_inference_enabled is False


def test_empty_optional_value_in_dotenv_uses_auto_detection(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "QDRANT_URL=https://sample.cloud.qdrant.io\nQDRANT_CLOUD_INFERENCE=\n",
        encoding="utf-8",
    )

    connection = QdrantConnection(_env_file=dotenv_path)

    assert connection.cloud_inference is None
    assert connection.cloud_inference_enabled is True
