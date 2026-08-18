"""Search Agent의 버전 관리 동작 설정 스키마."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pension_agent.core import SearchMode


class SearchAgentConfig(BaseModel):
    """검색 품질과 실행 비용을 조정하는 Search Agent 설정."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_model_calls: int = Field(ge=2, le=10)
    max_tool_calls: int = Field(ge=1, le=9)
    timeout_seconds: float = Field(default=45.0, gt=0, le=300)
    default_search_mode: SearchMode
    default_result_limit: int = Field(ge=1, le=100)
    default_neighbor_before: int = Field(ge=0, le=99)
    default_neighbor_after: int = Field(ge=0, le=99)

    @model_validator(mode="after")
    def validate_combined_limits(self) -> Self:
        """순차 Tool 실행과 인접 조회가 공통 실행 계약 안에 있는지 검증한다."""

        if self.max_model_calls < self.max_tool_calls + 1:
            raise ValueError("모델 호출 상한은 Tool 호출 상한보다 최소 1 커야 합니다.")
        if self.default_neighbor_before + self.default_neighbor_after + 1 > 100:
            raise ValueError("기본 인접 청크 조회 수는 기준 청크를 포함해 100 이하여야 합니다.")
        return self
