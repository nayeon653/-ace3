"""상품 비교 검색과 답안 생성의 불변 실행 예산."""

from pydantic import BaseModel, ConfigDict, Field


class ProductComparisonConfig(BaseModel):
    """비교 대상 수와 검색·생성 시간의 상한."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    max_targets: int = Field(default=5, ge=2, le=5, strict=True)
    search_timeout_seconds: float = Field(default=30.0, gt=0, le=30)
    submission_reserve_seconds: float = Field(default=30.0, gt=0, le=300)


DEFAULT_PRODUCT_COMPARISON_CONFIG = ProductComparisonConfig()
