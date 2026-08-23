"""상품 카탈로그와 색인 문서 식별자 해석을 검증한다."""

import json

import pytest

from pension_agent.retrieval import ProductCatalog, ProductCatalogError, load_product_catalog


def _catalog_payload(*codes: str) -> dict[str, object]:
    return {
        "products": [
            {
                "product_code": code,
                "official_name": f"상품 {index}",
                "provider": "운용사",
                "aliases": [f"별칭 {index}"],
            }
            for index, code in enumerate(codes)
        ]
    }


def test_packaged_catalog_resolves_all_codes_to_indexed_document_names() -> None:
    catalog = load_product_catalog()

    assert len(catalog.products) == 100
    assert len({product.product_code for product in catalog.products}) == 100
    assert len(
        {catalog.resolve_source_file_name(product.product_code) for product in catalog.products}
    ) == 92
    assert catalog.resolve_source_file_name(" kr510902511m ") == "R2_KR510902511M.pdf"
    assert catalog.resolve_source_file_name("KR518102001M") == "R2_KR5153450009.pdf"


def test_prompt_catalog_preserves_only_the_minimum_product_fields() -> None:
    payload = json.loads(load_product_catalog().to_prompt_json())

    assert len(payload["products"]) == 100
    assert set(payload["products"][0]) == {
        "product_code",
        "official_name",
        "provider",
        "aliases",
    }


@pytest.mark.parametrize("product_code", ["", "KR123", "US510902511M", "KR9999999999"])
def test_catalog_rejects_invalid_or_unknown_product_code(product_code: str) -> None:
    with pytest.raises(ProductCatalogError):
        load_product_catalog().resolve_source_file_name(product_code)


def test_catalog_rejects_duplicate_codes_and_unknown_document_aliases() -> None:
    code = "KR510902511M"
    with pytest.raises(ProductCatalogError, match="중복"):
        ProductCatalog.from_payloads(_catalog_payload(code, code), {"aliases": {}})
    with pytest.raises(ProductCatalogError, match="카탈로그 코드"):
        ProductCatalog.from_payloads(
            _catalog_payload(code),
            {"aliases": {code: "KR510902773M"}},
        )
