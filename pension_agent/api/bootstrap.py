"""FastAPI 프로세스에서 사용할 애플리케이션 객체 조립."""

from pension_agent.agent.answer_service import AnswerService
from pension_agent.agent.assembly import create_default_main_supervisor
from pension_agent.agent.model_factory import create_chat_clovax
from pension_agent.config import MAIN_SUPERVISOR_HCX_CONFIG, ClovaStudioConnection


def build_answer_service() -> AnswerService:
    """환경 설정으로 프로세스 공용 Answer Service를 조립한다."""

    connection = ClovaStudioConnection()
    model = create_chat_clovax(
        config=MAIN_SUPERVISOR_HCX_CONFIG,
        connection=connection,
    )
    supervisor = create_default_main_supervisor(model=model)
    return AnswerService(supervisor)
