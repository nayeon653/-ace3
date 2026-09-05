"""상품 비교 검색과 최종 제출의 불변 실행 예산."""

from pydantic import BaseModel, ConfigDict, Field

MAX_PRODUCT_COMPARISON_CRITERIA = 3


class ProductComparisonConfig(BaseModel):
    """상품별 최초 검색과 제한된 보완 검색의 상한."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    max_targets: int = Field(default=5, ge=2, le=5, strict=True)
    max_criteria: int = Field(
        default=MAX_PRODUCT_COMPARISON_CRITERIA,
        ge=1,
        le=MAX_PRODUCT_COMPARISON_CRITERIA,
        strict=True,
    )
    max_supplement_calls: int = Field(default=2, ge=0, le=2, strict=True)
    max_supplements_per_product: int = Field(default=1, ge=0, le=1, strict=True)
    search_timeout_seconds: float = Field(default=30.0, gt=0, le=30)
    submission_reserve_seconds: float = Field(default=30.0, gt=0, le=300)


DEFAULT_PRODUCT_COMPARISON_CONFIG = ProductComparisonConfig()
