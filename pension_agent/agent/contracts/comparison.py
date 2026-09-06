"""비교 요청의 상품 식별 결과를 공유한다."""

from typing import Literal, NotRequired

from pydantic import ConfigDict, with_config
from typing_extensions import TypedDict


@with_config(ConfigDict(extra="forbid", strict=True))
class ComparisonTarget(TypedDict):
    """원문에서 식별한 대상과 카탈로그의 확정 또는 미식별 결과."""

    target_id: str
    mention_parts: list[str]
    resolution_status: Literal["single", "ambiguous", "not_found"]
    product_code: NotRequired[str]
    official_name: NotRequired[str]
    provider: NotRequired[str]
