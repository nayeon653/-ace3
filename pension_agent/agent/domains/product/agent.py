"""상품·운용 도메인 Agent 구현."""

from pension_agent.agent.schemas import DomainRequest, DomainResult

PRODUCT_TOOL_NAME = "analyze_product"
PRODUCT_TOOL_DESCRIPTION = "연금 상품의 특성, 비용, 위험과 유동성을 판단한다."


class ProductAgent:
    """상품·운용 Agent. 현재는 구현 전 상태를 명시하는 결과를 반환한다."""

    def __call__(self, request: DomainRequest) -> DomainResult:
        """도메인 구현 전에는 질문을 임의로 판단하지 않고 미확정 결과를 반환한다."""

        del request
        return {
            "domain": "product",
            "execution_status": "completed",
            "decision": {
                "status": "undetermined",
                "conclusion": (
                    "현재 상품·운용 도메인 Agent는 구현 전입니다. "
                    "해당 상품 판단은 도메인 Agent 구현 후 제공할 수 있습니다."
                ),
                "missing_conditions": ["상품·운용 도메인 Agent 구현"],
            },
            "evidence": [],
            "calculations": [],
            "warnings": ["현재 응답은 미구현 도메인을 표시하는 임시 결과입니다."],
        }
