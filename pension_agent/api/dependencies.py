"""FastAPI 요청에 애플리케이션 의존성을 제공한다."""

import os
from typing import cast

from fastapi import HTTPException, Request, status

from pension_agent.agent.answer_service import AnswerService

PUBLIC_INTERNAL_ERROR = "답변을 생성하지 못했습니다."


def get_answer_service(request: Request) -> AnswerService:
    """lifespan에서 조립한 프로세스 공용 Answer Service를 반환한다."""

    try:
        return cast(AnswerService, request.app.state.answer_service)
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=PUBLIC_INTERNAL_ERROR,
        ) from None


def get_deployment_commit_sha() -> str:
    """배포 환경이 주입한 Git 커밋 SHA를 반환한다."""

    return os.getenv("DEPLOY_COMMIT_SHA", "unknown").strip() or "unknown"
