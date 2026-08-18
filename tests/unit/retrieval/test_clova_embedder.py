"""CLOVA bge-m3 Query Embedder 팩토리를 검증한다."""

import pytest
from pydantic import SecretStr

from pension_agent.config import BGE_M3_EMBEDDING_CONFIG, ClovaStudioConnection
from pension_agent.retrieval.clova_embedder import (
    ClovaEmbeddingFactoryError,
    create_clova_query_embedder,
)


def test_embedding_profile_is_fixed_to_bge_m3() -> None:
    assert BGE_M3_EMBEDDING_CONFIG.model == "bge-m3"
    assert BGE_M3_EMBEDDING_CONFIG.dimensions == 1024


def test_embedder_factory_requires_credentials() -> None:
    with pytest.raises(ClovaEmbeddingFactoryError, match="CLOVASTUDIO_API_KEY"):
        create_clova_query_embedder(
            config=BGE_M3_EMBEDDING_CONFIG,
            connection=ClovaStudioConnection(api_key=None, api_base_url="https://example.com"),
        )


def test_connection_secret_repr_is_safe() -> None:
    connection = ClovaStudioConnection(
        api_key=SecretStr("secret-token"),
        api_base_url="https://example.com",
    )

    assert "secret-token" not in repr(connection)
