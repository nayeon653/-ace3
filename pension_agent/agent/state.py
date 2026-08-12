"""Main Supervisor의 요청 단위 실행 상태."""

import operator
from typing import Annotated

from langchain.agents import AgentState

from pension_agent.agent.schemas import AgentAnswer, DomainResult


class SupervisorState(AgentState[AgentAnswer]):
    """질문과 실행된 도메인의 전체 결과를 누적한다."""

    question_id: str
    question: str
    domain_results: Annotated[list[DomainResult], operator.add]
