"""실험별 카탈로그 정보 동일성과 표시·매핑 스냅샷의 불변성을 확인한다."""

import json
from dataclasses import FrozenInstanceError

import pytest

from pension_agent.agent.product.catalog_query import load_product_catalog_query_prompt
from pension_agent.agent.product.catalog_selection import CatalogSelectionSnapshot
from pension_agent.retrieval import load_product_catalog


def test_catalog_display_variants_keep_all_product_fields_and_order() -> None:
    catalog = load_product_catalog()
    snapshots = {
        mode: CatalogSelectionSnapshot.from_catalog(catalog, mode=mode)
        for mode in ("compact_codes", "row_codes", "row_ids")
    }
    compact = snapshots["compact_codes"].catalog_text
    rows = snapshots["row_codes"].catalog_text
    selected = json.loads(snapshots["row_ids"].catalog_text)["products"]

    assert compact == catalog.to_prompt_json()
    assert json.loads(compact) == json.loads(rows)
    assert len(rows.splitlines()) == len(catalog.products) + 2
    assert [item.pop("row_id") for item in selected] == [
        f"P{index:03d}" for index in range(1, len(catalog.products) + 1)
    ]
    assert selected == json.loads(compact)["products"]


def test_row_codes_changes_only_catalog_whitespace_in_the_prompt() -> None:
    catalog = load_product_catalog()
    compact = load_product_catalog_query_prompt(catalog)
    rows = load_product_catalog_query_prompt(catalog, selection_mode="row_codes")
    snapshot = CatalogSelectionSnapshot.from_catalog(catalog, mode="row_codes")

    assert compact.replace(catalog.to_prompt_json(), snapshot.catalog_text) == rows
    assert "{{" not in rows


def test_row_selection_prompt_keeps_real_codes_as_input_metadata() -> None:
    catalog = load_product_catalog()
    prompt = load_product_catalog_query_prompt(catalog, selection_mode="row_ids")

    assert "{{" not in prompt
    assert "selected_row_id" in prompt
    assert "명시적인 상품 코드 질문" in prompt
    assert prompt.count('"row_id":"P001"') == 1
    assert all(f'"product_code":"{product.product_code}"' in prompt for product in catalog.products)


def test_catalog_snapshot_and_its_mapping_are_immutable() -> None:
    catalog = load_product_catalog()
    snapshot = CatalogSelectionSnapshot.from_catalog(catalog, mode="row_ids")

    with pytest.raises(FrozenInstanceError):
        snapshot.catalog_text = "다른 내용"  # type: ignore[misc]
    with pytest.raises(TypeError):
        snapshot.product_codes_by_row_id["P001"] = catalog.products[1].product_code  # type: ignore[index]

    assert snapshot.resolve_row_id("P001") == catalog.products[0].product_code
