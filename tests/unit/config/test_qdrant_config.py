"""Qdrant 환경 설정을 검증한다."""

import pytest
from pydantic import SecretStr, ValidationError

from pension_agent.config import QdrantConnection


def test_qdrant_connection_normalizes_url_and_hides_api_key() -> None:
    connection = QdrantConnection(
        url="https://cluster.cloud.qdrant.io/",
        api_key=SecretStr("secret-token"),
        collection="documents",
    )

    assert connection.url == "https://cluster.cloud.qdrant.io"
    assert connection.cloud_inference_enabled is True
    assert "secret-token" not in repr(connection)


def test_qdrant_connection_rejects_non_http_url() -> None:
    with pytest.raises(ValidationError):
        QdrantConnection(url="file:///tmp/qdrant")
