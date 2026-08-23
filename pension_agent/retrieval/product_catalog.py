"""상품 카탈로그 로딩과 색인 문서 식별자 해석."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources
from types import MappingProxyType
from typing import Any

_PRODUCT_CODE_PATTERN = re.compile(r"KR[A-Z0-9]{10}\Z")


class ProductCatalogError(ValueError):
    """상품 카탈로그 또는 상품 코드가 올바르지 않은 경우."""


@dataclass(frozen=True, slots=True)
class ProductCatalogEntry:
    """Product Agent가 상품을 식별할 때 사용하는 최소 카탈로그 항목."""

    product_code: str
    official_name: str
    provider: str
    aliases: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """프롬프트에 넣을 JSON 호환 표현을 반환한다."""

        return {
            "product_code": self.product_code,
            "official_name": self.official_name,
            "provider": self.provider,
            "aliases": list(self.aliases),
        }


@dataclass(frozen=True, slots=True)
class ProductCatalog:
    """검증된 상품 코드와 색인 문서 alias를 보관한다."""

    products: tuple[ProductCatalogEntry, ...]
    _products_by_code: Mapping[str, ProductCatalogEntry]
    _document_aliases: Mapping[str, str]

    @classmethod
    def from_payloads(
        cls,
        catalog_payload: object,
        alias_payload: object,
    ) -> ProductCatalog:
        """JSON payload를 검증해 불변 카탈로그를 만든다."""

        catalog_object = _require_object(catalog_payload, label="상품 카탈로그")
        raw_products = catalog_object.get("products")
        if not isinstance(raw_products, list) or not raw_products:
            raise ProductCatalogError("상품 카탈로그 products는 비어 있지 않은 배열이어야 합니다.")

        products = tuple(_parse_product(item) for item in raw_products)
        products_by_code = {product.product_code: product for product in products}
        if len(products_by_code) != len(products):
            raise ProductCatalogError("상품 카탈로그 product_code는 중복될 수 없습니다.")

        alias_object = _require_object(alias_payload, label="상품 문서 alias")
        raw_aliases = alias_object.get("aliases")
        if not isinstance(raw_aliases, dict):
            raise ProductCatalogError("상품 문서 aliases는 객체여야 합니다.")
        document_aliases = _validate_document_aliases(raw_aliases, products_by_code)
        return cls(
            products=products,
            _products_by_code=MappingProxyType(products_by_code),
            _document_aliases=MappingProxyType(document_aliases),
        )

    def resolve_source_file_name(self, product_code: str) -> str:
        """카탈로그 상품 코드를 현재 색인의 대표 원본 파일명으로 변환한다."""

        normalized = _normalize_product_code(product_code)
        if normalized not in self._products_by_code:
            raise ProductCatalogError("카탈로그에 없는 상품 코드입니다.")
        primary_code = self._document_aliases.get(normalized, normalized)
        return f"R2_{primary_code}.pdf"

    def select_products(self, product_codes: list[str]) -> tuple[ProductCatalogEntry, ...]:
        """HCX가 선택한 상품 코드를 검증하고 카탈로그 원본 항목으로 반환한다."""

        normalized_codes = [_normalize_product_code(code) for code in product_codes]
        if len(normalized_codes) != len(set(normalized_codes)):
            raise ProductCatalogError("상품 후보 product_code는 중복될 수 없습니다.")
        try:
            return tuple(self._products_by_code[code] for code in normalized_codes)
        except KeyError:
            raise ProductCatalogError("카탈로그에 없는 상품 코드입니다.") from None

    def to_prompt_json(self) -> str:
        """HCX 컨텍스트용 최소 카탈로그 JSON을 반환한다."""

        return json.dumps(
            {"products": [product.to_dict() for product in self.products]},
            ensure_ascii=False,
            separators=(",", ":"),
        )


@cache
def load_product_catalog() -> ProductCatalog:
    """패키지 리소스에서 검증된 상품 카탈로그를 한 번 로드한다."""

    package = resources.files("pension_agent.retrieval")
    try:
        catalog_payload = json.loads(
            package.joinpath("product_catalog.json").read_text(encoding="utf-8")
        )
        alias_payload = json.loads(
            package.joinpath("product_document_aliases.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductCatalogError("상품 카탈로그 리소스를 읽을 수 없습니다.") from exc
    return ProductCatalog.from_payloads(catalog_payload, alias_payload)


def _parse_product(value: object) -> ProductCatalogEntry:
    item = _require_object(value, label="상품")
    if set(item) != {"product_code", "official_name", "provider", "aliases"}:
        raise ProductCatalogError("상품 카탈로그 항목의 필드가 올바르지 않습니다.")
    product_code = _normalize_product_code(item["product_code"])
    official_name = _require_text(item["official_name"], label="official_name")
    provider = _require_text(item["provider"], label="provider")
    raw_aliases = item["aliases"]
    if not isinstance(raw_aliases, list):
        raise ProductCatalogError("aliases는 문자열 배열이어야 합니다.")
    aliases = tuple(_require_text(alias, label="alias") for alias in raw_aliases)
    if len(aliases) != len(set(aliases)):
        raise ProductCatalogError("한 상품의 aliases는 중복될 수 없습니다.")
    return ProductCatalogEntry(
        product_code=product_code,
        official_name=official_name,
        provider=provider,
        aliases=aliases,
    )


def _validate_document_aliases(
    raw_aliases: dict[object, object],
    products_by_code: Mapping[str, ProductCatalogEntry],
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for raw_alias, raw_primary in raw_aliases.items():
        alias = _normalize_product_code(raw_alias)
        primary = _normalize_product_code(raw_primary)
        if alias == primary:
            raise ProductCatalogError("상품 문서 alias와 대표 코드는 같을 수 없습니다.")
        if alias not in products_by_code or primary not in products_by_code:
            raise ProductCatalogError("상품 문서 alias는 카탈로그 코드만 참조해야 합니다.")
        aliases[alias] = primary
    if any(primary in aliases for primary in aliases.values()):
        raise ProductCatalogError("상품 문서 alias는 다른 alias를 대표 코드로 참조할 수 없습니다.")
    return aliases


def _normalize_product_code(value: object) -> str:
    if not isinstance(value, str):
        raise ProductCatalogError("product_code는 문자열이어야 합니다.")
    normalized = value.strip().upper()
    if _PRODUCT_CODE_PATTERN.fullmatch(normalized) is None:
        raise ProductCatalogError("product_code 형식이 올바르지 않습니다.")
    return normalized


def _require_object(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ProductCatalogError(f"{label}는 객체여야 합니다.")
    return value


def _require_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductCatalogError(f"{label}은 비어 있지 않은 문자열이어야 합니다.")
    return value.strip()
