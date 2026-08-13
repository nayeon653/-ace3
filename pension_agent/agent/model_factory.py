"""Main Supervisor용 ChatClovaX 모델 Factory."""

from langchain_naver import ChatClovaX  # type: ignore[import-untyped]
from openai import OpenAIError

from pension_agent.config import ChatClovaXConfig, ClovaStudioConnection


class ChatClovaXFactoryError(RuntimeError):
    """ChatClovaX를 안전하게 초기화하지 못한 경우."""


def create_chat_clovax(
    *,
    config: ChatClovaXConfig,
    connection: ClovaStudioConnection,
) -> ChatClovaX:
    """동작 설정과 인증·연결 설정을 주입받아 ChatClovaX를 만든다."""

    if connection.api_key is None or not connection.api_key.get_secret_value().strip():
        raise ChatClovaXFactoryError("CLOVASTUDIO_API_KEY가 설정되지 않았습니다.")
    if not connection.api_base_url:
        raise ChatClovaXFactoryError("CLOVASTUDIO_API_BASE_URL이 설정되지 않았습니다.")

    # Provider 예외가 정제 오류의 __context__에 남아 시크릿을 노출하지 않게 분리한다.
    try:
        return ChatClovaX(
            model=config.model,
            max_completion_tokens=config.max_tokens,
            temperature=config.temperature,
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
            api_key=connection.api_key,
            base_url=connection.api_base_url,
        )
    except (ImportError, OpenAIError, RuntimeError, TypeError, ValueError):
        pass

    raise ChatClovaXFactoryError("ChatClovaX 모델 초기화에 실패했습니다.")
