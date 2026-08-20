"""온라인 Agent 런타임의 프로세스 단위 실행 예산."""

from pydantic import BaseModel, ConfigDict, Field


class AgentRuntimeConfig(BaseModel):
    """요청과 provider 호출에 적용하는 버전 관리 동시성·시간 상한."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_concurrent_answers: int = Field(default=4, ge=1, le=32)
    max_pending_answers: int = Field(default=64, ge=0, le=512)
    max_concurrent_hcx_calls: int = Field(default=4, ge=1, le=32)
    max_concurrent_embedding_calls: int = Field(default=4, ge=1, le=32)
    max_concurrent_qdrant_calls: int = Field(default=4, ge=1, le=32)
    answer_timeout_seconds: float = Field(default=180.0, gt=0, le=600)
    shutdown_timeout_seconds: float = Field(default=10.0, gt=0, le=60)


DEFAULT_AGENT_RUNTIME_CONFIG = AgentRuntimeConfig()
