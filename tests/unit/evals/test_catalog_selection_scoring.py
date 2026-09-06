"""카탈로그 정답 채점에서 잘못된 대상 대응과 누락을 숨기지 않는다."""

from copy import deepcopy
from typing import Any

import pytest

from evals.catalog_selection.scoring import score_plan

_MULTIPLE_CASE = {
    "expected": {
        "route": "resolve_products",
        "targets": [
            {"status": "single", "acceptable_codes": ["CODE_A", "CODE_A_CLASS"]},
            {"status": "single", "acceptable_codes": ["CODE_B"]},
        ],
    }
}
_MULTIPLE_PLAN = {
    "route": "resolve_products",
    "targets": [
        {"resolution_status": "single", "product_code": "CODE_A"},
        {"resolution_status": "single", "product_code": "CODE_B"},
    ],
}


def test_single_product_requires_the_expected_code_and_status() -> None:
    case = {
        "expected": {
            "route": "resolve_product",
            "targets": [{"status": "single", "acceptable_codes": ["CODE_A"]}],
        }
    }
    plan = {
        "route": "resolve_product",
        "resolution_status": "single",
        "product_code": "CODE_A",
    }

    assert score_plan(case, plan) == {
        "route_correct": True,
        "targets_correct": [True],
        "correct": True,
        "expected_targets": 1,
    }


@pytest.mark.parametrize("code", ["CODE_A", "CODE_A_CLASS"])
def test_accepts_each_predefined_code_without_changing_gold(code: str) -> None:
    plan = deepcopy(_MULTIPLE_PLAN)
    plan["targets"][0]["product_code"] = code

    assert score_plan(_MULTIPLE_CASE, plan) == {
        "route_correct": True,
        "targets_correct": [True, True],
        "correct": True,
        "expected_targets": 2,
    }


@pytest.mark.parametrize(
    ("codes", "targets_correct"),
    [
        (["CODE_B", "CODE_A"], [False, False]),
        (["CODE_A", "CODE_A"], [True, False]),
        (["CODE_A"], [True, False]),
        (["CODE_A", "CODE_B", "CODE_A"], [True, True]),
    ],
    ids=["wrong-order", "duplicate", "missing", "extra"],
)
def test_rejects_wrong_order_duplicates_missing_and_extra_targets(
    codes: list[str], targets_correct: list[bool]
) -> None:
    plan = {
        "route": "resolve_products",
        "targets": [{"resolution_status": "single", "product_code": code} for code in codes],
    }

    score = score_plan(_MULTIPLE_CASE, plan)

    assert score["route_correct"] is True
    assert score["targets_correct"] == targets_correct
    assert score["correct"] is False


@pytest.mark.parametrize("status", ["ambiguous", "not_found"])
def test_unresolved_targets_require_matching_status_without_identifier(status: str) -> None:
    case = {
        "expected": {
            "route": f"product_{status}",
            "targets": [{"status": status, "acceptable_codes": []}],
        }
    }
    plan = {"route": f"product_{status}", "resolution_status": status}

    assert score_plan(case, plan)["correct"] is True
    for key in ("product_code", "selected_row_id"):
        for value in (None, "", "CODE_A"):
            assert score_plan(case, {**plan, key: value})["targets_correct"] == [False]


def test_unresolved_status_mismatch_is_incorrect() -> None:
    case = {
        "expected": {
            "route": "product_ambiguous",
            "targets": [{"status": "ambiguous", "acceptable_codes": []}],
        }
    }
    plan = {"route": "product_not_found", "resolution_status": "not_found"}

    assert score_plan(case, plan) == {
        "route_correct": False,
        "targets_correct": [False],
        "correct": False,
        "expected_targets": 1,
    }


def test_compares_resolved_and_unresolved_targets_in_the_same_plan() -> None:
    case = {
        "expected": {
            "route": "resolve_products",
            "targets": [
                {"status": "single", "acceptable_codes": ["CODE_A"]},
                {"status": "not_found", "acceptable_codes": []},
            ],
        }
    }
    plan = {
        "route": "resolve_products",
        "targets": [
            {"resolution_status": "single", "product_code": "CODE_A"},
            {"resolution_status": "not_found"},
        ],
    }

    assert score_plan(case, plan)["correct"] is True


def test_reports_target_accuracy_separately_from_wrong_route() -> None:
    case = {
        "expected": {
            "route": "resolve_product",
            "targets": [{"status": "single", "acceptable_codes": ["CODE_A"]}],
        }
    }
    plan = {
        "route": "resolve_products",
        "targets": [{"resolution_status": "single", "product_code": "CODE_A"}],
    }

    assert score_plan(case, plan) == {
        "route_correct": False,
        "targets_correct": [True],
        "correct": False,
        "expected_targets": 1,
    }


@pytest.mark.parametrize(
    "plan", [None, {}, {"route": "browse_all_catalog"}, {"route": "resolve_products"}]
)
def test_missing_failed_or_unrelated_plans_do_not_omit_gold_targets(
    plan: dict[str, Any] | None,
) -> None:
    score = score_plan(_MULTIPLE_CASE, plan)

    assert score["targets_correct"] == [False, False]
    assert score["correct"] is False
    assert score["expected_targets"] == 2


@pytest.mark.parametrize(
    "target",
    [
        None,
        {"resolution_status": "single"},
        {"resolution_status": "single", "product_code": "WRONG_CODE"},
        {"resolution_status": "ambiguous", "product_code": "CODE_A"},
    ],
)
def test_invalid_or_wrong_target_is_a_false_score(target: Any) -> None:
    plan = deepcopy(_MULTIPLE_PLAN)
    plan["targets"][0] = target

    assert score_plan(_MULTIPLE_CASE, plan)["targets_correct"] == [False, True]
