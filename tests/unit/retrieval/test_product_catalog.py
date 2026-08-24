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
    assert (
        len(
            {catalog.resolve_source_file_name(product.product_code) for product in catalog.products}
        )
        == 92
    )
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


def test_catalog_validates_hcx_candidate_codes_before_returning_entries() -> None:
    catalog = load_product_catalog()

    selected = catalog.select_products([" kr510902511m ", "KR510902773M"])

    assert [product.product_code for product in selected] == [
        "KR510902511M",
        "KR510902773M",
    ]
    with pytest.raises(ProductCatalogError, match="중복"):
        catalog.select_products(["KR510902511M", "kr510902511m"])
    with pytest.raises(ProductCatalogError, match="카탈로그에 없는"):
        catalog.select_products(["KR9999999999"])


def test_catalog_queries_provider_count_and_items_deterministically() -> None:
    catalog = load_product_catalog()

    result = catalog.query(provider=" 미래에셋 ", return_mode="count_and_items")

    assert result.provider == "미래에셋"
    assert result.total_count == 25
    assert len(result.items) == 25
    assert [product.product_code for product in result.items] == sorted(
        product.product_code for product in catalog.products if product.provider == "미래에셋"
    )
    assert result.catalog_version == catalog.version
    assert len(result.catalog_version) == 64


def test_catalog_count_query_omits_items_without_changing_total() -> None:
    result = load_product_catalog().query(provider="미래에셋", return_mode="count")

    assert result.total_count == 25
    assert result.items == ()


def test_catalog_query_without_provider_covers_the_full_snapshot() -> None:
    result = load_product_catalog().query(provider=None, return_mode="items")

    assert result.total_count == 100
    assert len(result.items) == 100
    assert result.provider is None


def test_catalog_query_rejects_unknown_provider_and_return_mode() -> None:
    catalog = load_product_catalog()

    with pytest.raises(ProductCatalogError, match="없는 운용사"):
        catalog.query(provider="없는운용사", return_mode="count")
    with pytest.raises(ProductCatalogError, match="반환 방식"):
        catalog.query(provider="미래에셋", return_mode="all")  # type: ignore[arg-type]


def test_catalog_version_changes_with_validated_catalog_content() -> None:
    first = ProductCatalog.from_payloads(
        _catalog_payload("KR510902511M"),
        {"aliases": {}},
    )
    second_payload = _catalog_payload("KR510902511M")
    products = second_payload["products"]
    assert isinstance(products, list)
    products[0]["official_name"] = "변경된 상품명"
    second = ProductCatalog.from_payloads(second_payload, {"aliases": {}})

    assert first.version != second.version


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
