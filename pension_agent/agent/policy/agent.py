"""업무·제도 도메인 Agent 구현."""

from pension_agent.agent.contracts import DomainRequest, DomainResult

POLICY_TOOL_NAME = "analyze_policy"
POLICY_TOOL_DESCRIPTION = "연금 가입, 이전, 해지, 수령 절차와 제도상 가능 여부를 판단한다."


class PolicyAgent:
    """업무·제도 Agent. 현재는 구현 전 상태를 명시하는 결과를 반환한다."""

    def __call__(self, request: DomainRequest) -> DomainResult:
        """도메인 구현 전에는 질문을 임의로 판단하지 않고 미확정 결과를 반환한다."""

        del request
        return {
            "domain": "policy",
            "execution_status": "completed",
            "decision": {
                "status": "undetermined",
                "conclusion": (
                    "현재 업무·제도 도메인 Agent는 구현 전입니다. "
                    "해당 업무 판단은 도메인 Agent 구현 후 제공할 수 있습니다."
                ),
                "missing_conditions": ["업무·제도 도메인 Agent 구현"],
            },
            "evidence": [],
            "calculations": [],
            "warnings": ["현재 응답은 미구현 도메인을 표시하는 임시 결과입니다."],
        }
