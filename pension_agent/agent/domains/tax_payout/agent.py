"""세제·수령 도메인 Agent 구현."""

from pension_agent.agent.schemas import DomainRequest, DomainResult

TAX_PAYOUT_TOOL_NAME = "analyze_tax_payout"
TAX_PAYOUT_TOOL_DESCRIPTION = "연금 세액공제, 과세와 수령 조건을 판단한다."


class TaxPayoutAgent:
    """세제·수령 Agent. 현재는 구현 전 상태를 명시하는 결과를 반환한다."""

    def __call__(self, request: DomainRequest) -> DomainResult:
        """도메인 구현 전에는 질문을 임의로 판단하지 않고 미확정 결과를 반환한다."""

        del request
        return {
            "domain": "tax_payout",
            "execution_status": "completed",
            "decision": {
                "status": "undetermined",
                "conclusion": (
                    "현재 세제·수령 도메인 Agent는 구현 전입니다. "
                    "해당 세제·수령 판단은 도메인 Agent 구현 후 제공할 수 있습니다."
                ),
                "missing_conditions": ["세제·수령 도메인 Agent 구현"],
            },
            "evidence": [],
            "calculations": [],
            "warnings": ["현재 응답은 미구현 도메인을 표시하는 임시 결과입니다."],
        }
