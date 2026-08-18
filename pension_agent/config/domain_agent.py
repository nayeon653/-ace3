"""Domain Agent의 실행 상한 프로필."""

from pydantic import BaseModel, ConfigDict, Field


class DomainAgentConfig(BaseModel):
    """도메인별 품질 튜닝과 분리된 공통 실행 제한."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_model_calls: int = Field(default=5, ge=2, le=8)
    max_search_calls: int = Field(default=1, ge=1, le=1)
    max_submit_calls: int = Field(default=2, ge=1, le=3)
    timeout_seconds: float = Field(default=75.0, gt=0, le=300)


DEFAULT_DOMAIN_AGENT_CONFIG = DomainAgentConfig()
