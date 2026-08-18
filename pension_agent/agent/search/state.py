"""Search Agent의 요청 단위 실행 상태."""

from langchain.agents import AgentState

from pension_agent.agent.contracts import AgentPermissions


class SearchAgentState(AgentState):
    """호출자가 주입한 문서 접근 권한을 포함하는 Search Agent 상태."""

    permissions: AgentPermissions
