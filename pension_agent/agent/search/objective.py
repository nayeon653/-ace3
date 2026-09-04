"""도메인 판단 범위를 보존하는 검색 목표 조합 규칙."""


def combine_search_objective(
    *,
    domain_objective: str,
    model_focus: str,
) -> str:
    """원래 판단 목표를 유지하고 모델의 검색 초점을 보조 문구로 덧붙인다."""

    if not isinstance(domain_objective, str) or not isinstance(model_focus, str):
        raise TypeError("검색 목표는 문자열이어야 합니다.")
    normalized_domain_objective = domain_objective.strip()
    normalized_model_focus = model_focus.strip()
    if not normalized_domain_objective:
        raise ValueError("원래 도메인 판단 목표가 없습니다.")
    if not normalized_model_focus:
        raise ValueError("모델 검색 초점이 없습니다.")
    if normalized_domain_objective == normalized_model_focus:
        return normalized_domain_objective
    return f"{normalized_domain_objective}\n{normalized_model_focus}"
