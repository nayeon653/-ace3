"""Router 기반 Search Service의 실행·검색 설정."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pension_agent.core import SearchMode


class SearchServiceConfig(BaseModel):
    """검색 경로와 후보 필터링에 적용하는 버전 관리 설정."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    max_concurrency: int = Field(default=4, ge=1, le=32)
    timeout_seconds: float = Field(default=45.0, gt=0, le=300)
    default_search_mode: SearchMode = SearchMode.HYBRID
    candidate_limit: int = Field(default=10, ge=1, le=100)
    result_limit: int = Field(default=5, ge=1, le=100)
    minimum_score: float | None = None
    neighbor_before: int = Field(default=1, ge=0, le=99)
    neighbor_after: int = Field(default=1, ge=0, le=99)

    @model_validator(mode="after")
    def validate_combined_limits(self) -> Self:
        """후보·최종 결과 수와 인접 문맥 범위를 함께 검증한다."""

        if self.result_limit > self.candidate_limit:
            raise ValueError("최종 검색 결과 수는 후보 검색 결과 수보다 클 수 없습니다.")
        if self.neighbor_before + self.neighbor_after + 1 > 100:
            raise ValueError("인접 청크 조회 수는 기준 청크를 포함해 100 이하여야 합니다.")
        return self


DEFAULT_SEARCH_SERVICE_CONFIG = SearchServiceConfig()
