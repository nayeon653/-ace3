"""평가와 운영 확인을 위한 FastAPI 라우트."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from pension_agent.agent.orchestration import AnswerService
from pension_agent.api.dependencies import (
    PUBLIC_INTERNAL_ERROR,
    get_answer_service,
    get_deployment_commit_sha,
)
from pension_agent.api.presentation import build_answer_response
from pension_agent.api.schemas import AnswerResponse, ErrorResponse, HealthResponse

router = APIRouter()

_INVALID_REQUEST_ERROR = "요청 파라미터가 올바르지 않습니다."
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "model": ErrorResponse,
        "description": "필수 파라미터 누락 또는 빈 값",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorResponse,
        "description": "Agent 초기화·실행 또는 응답 조립 오류",
    },
}


@router.get(
    "/answer",
    response_model=AnswerResponse,
    responses=_ERROR_RESPONSES,
    summary="연금 질문에 답변",
    description="질문을 Main Supervisor에 전달하고 평가용 5개 필드로 반환합니다.",
)
async def answer(
    question_id: Annotated[
        str,
        Query(min_length=1, description="주최측 평가셋의 질의 고유 ID"),
    ],
    question: Annotated[
        str,
        Query(min_length=1, description="연금 관련 자연어 질문 원문"),
    ],
    service: Annotated[AnswerService, Depends(get_answer_service)],
) -> AnswerResponse:
    """질문을 Main Supervisor에 전달하고 평가 응답으로 변환한다."""

    if not question_id.strip() or not question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_INVALID_REQUEST_ERROR,
        )

    try:
        result = await service.run(question_id=question_id, question=question)
        return build_answer_response(result)
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=PUBLIC_INTERNAL_ERROR,
        ) from None


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="API 서버 상태 확인",
    description="LLM과 검색 시스템을 호출하지 않고 서버 상태와 배포 버전을 반환합니다.",
)
async def health(
    commit_sha: Annotated[str, Depends(get_deployment_commit_sha)],
) -> HealthResponse:
    """LLM과 검색 시스템을 호출하지 않고 서버 생존 상태를 반환한다."""

    return HealthResponse(status="ok", commit_sha=commit_sha)
