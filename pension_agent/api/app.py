"""FastAPI 애플리케이션 진입점."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pension_agent.agent.orchestration import AnswerService
from pension_agent.api.bootstrap import build_answer_service
from pension_agent.api.routes import router

_INVALID_REQUEST_ERROR = "요청 파라미터가 올바르지 않습니다."
_INTERNAL_SERVER_ERROR = "서버 내부 오류가 발생했습니다."

AnswerServiceFactory = Callable[[], Awaitable[AnswerService]]


def create_app(
    *,
    answer_service_factory: AnswerServiceFactory = build_answer_service,
) -> FastAPI:
    """라우트와 정제된 오류 변환이 등록된 앱을 생성한다."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.answer_service = await answer_service_factory()
        try:
            yield
        finally:
            close = getattr(application.state.answer_service, "aclose", None)
            if callable(close):
                await close()
            del application.state.answer_service

    application = FastAPI(
        title="Pension Agent API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(router)

    @application.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        del request, error
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": _INVALID_REQUEST_ERROR},
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        error: Exception,
    ) -> JSONResponse:
        del request, error
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": _INTERNAL_SERVER_ERROR},
        )

    return application


app = create_app()
