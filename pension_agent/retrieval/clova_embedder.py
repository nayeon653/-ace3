"""CLOVA Studio bge-m3 검색문 임베딩 Adapter."""

from langchain_naver import ClovaXEmbeddings  # type: ignore[import-untyped]
from openai import OpenAIError

from pension_agent.config import ClovaEmbeddingConfig, ClovaStudioConnection


class ClovaEmbeddingFactoryError(RuntimeError):
    """임베딩 모델을 안전하게 초기화하지 못한 경우."""


def create_clova_query_embedder(
    *,
    config: ClovaEmbeddingConfig,
    connection: ClovaStudioConnection,
) -> ClovaXEmbeddings:
    """고정 bge-m3 설정과 환경 연결 정보로 Query Embedder를 만든다."""

    if connection.api_key is None or not connection.api_key.get_secret_value().strip():
        raise ClovaEmbeddingFactoryError("CLOVASTUDIO_API_KEY가 설정되지 않았습니다.")
    if not connection.api_base_url:
        raise ClovaEmbeddingFactoryError("CLOVASTUDIO_API_BASE_URL이 설정되지 않았습니다.")
    try:
        return ClovaXEmbeddings(
            model=config.model,
            dimensions=config.dimensions,
            encoding_format="float",
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
            api_key=connection.api_key,
            base_url=connection.api_base_url,
        )
    except (ImportError, OpenAIError, RuntimeError, TypeError, ValueError):
        pass
    raise ClovaEmbeddingFactoryError("CLOVA Studio 임베딩 초기화에 실패했습니다.")
