"""사전 확정 정답과 카탈로그 조회 계획을 순서대로 비교한다."""

from typing import Any


def score_plan(case: dict[str, Any], plan: dict[str, Any] | None) -> dict[str, Any]:
    """상품 선택과 미식별 상태를 채점하며 누락·중복 대상을 그대로 드러낸다."""

    expected = case["expected"]
    expected_targets = expected["targets"]
    route_correct = plan is not None and plan.get("route") == expected["route"]
    actual_targets = _plan_targets(plan)
    targets_correct = [
        index < len(actual_targets) and _target_correct(target, actual_targets[index])
        for index, target in enumerate(expected_targets)
    ]
    return {
        "route_correct": route_correct,
        "targets_correct": targets_correct,
        "correct": (
            route_correct and len(actual_targets) == len(expected_targets) and all(targets_correct)
        ),
        "expected_targets": len(expected_targets),
    }


def _plan_targets(plan: dict[str, Any] | None) -> list[Any]:
    if plan is None:
        return []
    if plan.get("route") == "resolve_products":
        targets = plan.get("targets")
        return targets if isinstance(targets, list) else []
    if plan.get("route") in {"resolve_product", "product_ambiguous", "product_not_found"}:
        return [plan]
    return []


def _target_correct(expected: dict[str, Any], actual: Any) -> bool:
    if not isinstance(actual, dict) or actual.get("resolution_status") != expected["status"]:
        return False
    if expected["status"] == "single":
        return actual.get("product_code") in expected["acceptable_codes"]
    return "product_code" not in actual and "selected_row_id" not in actual
