"""FastAPI와 Agent 런타임 조립 경계."""

from pension_agent.agent.orchestration import AnswerService
from pension_agent.agent.runtime import build_runtime_answer_service


def build_answer_service() -> AnswerService:
    """Agent 계층이 조립한 프로세스 공용 Answer Service를 반환한다."""

    return build_runtime_answer_service()
