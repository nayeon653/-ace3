"""Agent 수직 경로가 공유하는 요청 실행 예산."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, TypeVar

_ResultT = TypeVar("_ResultT")

from langchain.agents.middleware import AgentMiddleware


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """동일 event loop의 monotonic clock으로 표현한 요청의 절대 마감 시각."""

    deadline: float


class AsyncConcurrencyLimiter:
    """프로세스 안의 비동기 작업 수를 명시된 상한으로 제한한다."""

    def __init__(self, max_concurrency: int) -> None:
        if max_concurrency < 1:
            raise ValueError("비동기 동시 실행 상한은 1 이상이어야 합니다.")
        self.max_concurrency = max_concurrency
        self._capacity = asyncio.Semaphore(max_concurrency)

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """취소와 예외에도 반환되는 실행 슬롯 하나를 대여한다."""

        async with self._capacity:
            yield


class ModelConcurrencyMiddleware(AgentMiddleware[Any, ExecutionContext, Any]):
    """여러 Agent graph가 공유하는 HCX 모델 호출 상한."""

    def __init__(self, limiter: AsyncConcurrencyLimiter) -> None:
        self._limiter = limiter

    async def awrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """모델의 native async 호출 전체를 공유 슬롯 안에서 실행한다."""

        async with self._limiter.slot():
            return await handler(request)

    async def arun(self, operation: Callable[[], Awaitable[_ResultT]]) -> _ResultT:
        """Agent Tool 내부의 직접 HCX 호출에도 같은 공유 상한을 적용한다."""

        async with self._limiter.slot():
            return await operation()


def effective_deadline(*, timeout_seconds: float, parent_deadline: float | None) -> float:
    """로컬 제한과 상위 요청의 남은 예산 중 먼저 끝나는 마감 시각을 반환한다."""

    local_deadline = asyncio.get_running_loop().time() + timeout_seconds
    if parent_deadline is None:
        return local_deadline
    return min(parent_deadline, local_deadline)
