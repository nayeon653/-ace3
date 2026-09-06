"""카탈로그 표시 순서와 선택 ID 매핑을 같은 불변 스냅샷으로 묶는다."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from pension_agent.retrieval import ProductCatalog, ProductCatalogError

CatalogSelectionMode = Literal["compact_codes", "row_codes", "row_ids"]


@dataclass(frozen=True, slots=True)
class CatalogSelectionSnapshot:
    """한 Planner에 표시된 행과 그 행의 실제 상품 코드를 보관한다."""

    mode: CatalogSelectionMode
    catalog_text: str
    product_codes_by_row_id: Mapping[str, str]

    @classmethod
    def from_catalog(
        cls,
        catalog: ProductCatalog,
        *,
        mode: CatalogSelectionMode,
    ) -> CatalogSelectionSnapshot:
        """전체 필드와 상품 순서를 유지하며 표시 형식만 선택한다."""

        if mode not in {"compact_codes", "row_codes", "row_ids"}:
            raise ValueError("지원하지 않는 상품 카탈로그 선택 방식입니다.")
        codes_by_row_id = {
            f"P{index:03d}": product.product_code
            for index, product in enumerate(catalog.products, start=1)
        }
        if mode == "compact_codes":
            catalog_text = catalog.to_prompt_json()
        else:
            rows = []
            for row_id, product in zip(codes_by_row_id, catalog.products, strict=True):
                payload = product.to_dict()
                if mode == "row_ids":
                    payload = {"row_id": row_id, **payload}
                rows.append(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
            catalog_text = '{"products":[\n' + ",\n".join(rows) + "\n]}"
        return cls(
            mode=mode,
            catalog_text=catalog_text,
            product_codes_by_row_id=MappingProxyType(codes_by_row_id),
        )

    def resolve_row_id(self, row_id: str) -> str:
        """표시한 행 ID만 실제 코드로 연결하며 다른 상품을 대신 고르지 않는다."""

        try:
            return self.product_codes_by_row_id[row_id]
        except KeyError:
            raise ProductCatalogError("표시된 카탈로그에 없는 선택 ID입니다.") from None
