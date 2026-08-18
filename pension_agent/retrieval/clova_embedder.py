"""CLOVA Studio bge-m3 검색·문서 임베딩 Adapter."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic, sleep

from langchain_naver import ClovaXEmbeddings  # type: ignore[import-untyped]
from openai import OpenAIError

from pension_agent.config import ClovaEmbeddingConfig, ClovaStudioConnection


class ClovaEmbeddingFactoryError(RuntimeError):
    """임베딩 모델을 안전하게 초기화하지 못한 경우."""


@dataclass
class ClovaDocumentEmbedder:
    """단일 입력 API를 QPM 이하의 제한된 병렬 호출로 실행하는 임베더."""

    client: ClovaXEmbeddings
    max_workers: int = 4
    requests_per_minute: int = 55
    _request_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _next_request_at: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("임베딩 worker 수는 1 이상이어야 합니다.")
        if self.requests_per_minute < 1:
            raise ValueError("분당 임베딩 요청 수는 1 이상이어야 합니다.")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """입력 순서를 유지하면서 독립적인 임베딩 요청을 병렬 실행한다."""

        if not texts:
            return []
        worker_count = min(self.max_workers, len(texts))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            return list(executor.map(self._embed_query, texts))

    def _embed_query(self, text: str) -> list[float]:
        interval_seconds = 60.0 / self.requests_per_minute
        with self._request_lock:
            now = monotonic()
            wait_seconds = self._next_request_at - now
            if wait_seconds > 0:
                sleep(wait_seconds)
            self._next_request_at = monotonic() + interval_seconds
        return self.client.embed_query(text)


def create_clova_query_embedder(
    *,
    config: ClovaEmbeddingConfig,
    connection: ClovaStudioConnection,
) -> ClovaXEmbeddings:
    """고정 bge-m3 설정과 환경 연결 정보로 Query Embedder를 만든다."""

    return _create_clova_client(config=config, connection=connection)


def create_clova_document_embedder(
    *,
    config: ClovaEmbeddingConfig,
    connection: ClovaStudioConnection,
    max_workers: int = 4,
    requests_per_minute: int = 55,
) -> ClovaDocumentEmbedder:
    """rate limit을 지키는 오프라인 문서 임베더를 만든다."""

    return ClovaDocumentEmbedder(
        client=_create_clova_client(config=config, connection=connection),
        max_workers=max_workers,
        requests_per_minute=requests_per_minute,
    )


def _create_clova_client(
    *,
    config: ClovaEmbeddingConfig,
    connection: ClovaStudioConnection,
) -> ClovaXEmbeddings:
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
