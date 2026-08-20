"""평가와 운영 확인을 위한 FastAPI 라우트."""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from pension_agent.agent.orchestration import (
    AnswerService,
    AnswerServiceOverloadedError,
    AnswerServiceResult,
)
from pension_agent.api.dependencies import (
    PUBLIC_INTERNAL_ERROR,
    get_answer_service,
    get_deployment_commit_sha,
)
from pension_agent.api.presentation import build_answer_response
from pension_agent.api.schemas import AnswerResponse, ErrorResponse, HealthResponse

router = APIRouter()

_INVALID_REQUEST_ERROR = "요청 파라미터가 올바르지 않습니다."
_CLIENT_DISCONNECTED_ERROR = "클라이언트 연결이 종료됐습니다."
_SERVICE_OVERLOADED_ERROR = "현재 처리 가능한 요청 수를 초과했습니다."
_CLIENT_CLOSED_REQUEST_STATUS = 499
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "model": ErrorResponse,
        "description": "필수 파라미터 누락 또는 빈 값",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorResponse,
        "description": "Agent 초기화·실행 또는 응답 조립 오류",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": ErrorResponse,
        "description": "프로세스의 bounded 요청 대기열 포화",
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
    request: Request,
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
        result = await _run_until_disconnect(
            request=request,
            service=service,
            question_id=question_id,
            question=question,
        )
        return build_answer_response(result)
    except _ClientDisconnected:
        raise HTTPException(
            status_code=_CLIENT_CLOSED_REQUEST_STATUS,
            detail=_CLIENT_DISCONNECTED_ERROR,
        ) from None
    except AnswerServiceOverloadedError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_SERVICE_OVERLOADED_ERROR,
        ) from None
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


class _ClientDisconnected(RuntimeError):
    """응답 조립 전에 ASGI client 연결이 끊긴 경우."""


async def _run_until_disconnect(
    *,
    request: Request,
    service: AnswerService,
    question_id: str,
    question: str,
) -> AnswerServiceResult:
    """답변과 연결 종료를 경쟁시키고 끊긴 요청의 Agent task를 회수한다."""

    answer_task = asyncio.create_task(
        service.run(question_id=question_id, question=question),
        name="answer-request",
    )
    disconnect_task = asyncio.create_task(
        _wait_for_disconnect(request),
        name="answer-disconnect-watcher",
    )
    tasks = (answer_task, disconnect_task)
    try:
        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        if answer_task in done:
            return await answer_task

        answer_task.cancel()
        raise _ClientDisconnected
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
            task.add_done_callback(_consume_task_outcome)


async def _wait_for_disconnect(request: Request) -> None:
    """GET body 이벤트를 비운 뒤 실제 ASGI disconnect까지 기다린다."""

    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            return


def _consume_task_outcome(task: asyncio.Task[Any]) -> None:
    """분리된 취소 task가 늦게 끝나도 미조회 예외 경고를 남기지 않는다."""

    if not task.cancelled():
        task.exception()
