"""Main Supervisor가 호출하는 Domain 실행 계약."""

from collections.abc import Awaitable
from typing import Protocol

from pension_agent.agent.contracts.domain import DomainRequest, DomainResult


class DomainRunner(Protocol):
    """구현 방식과 무관한 비동기 Domain Agent 계약."""

    def __call__(
        self,
        request: DomainRequest,
        *,
        deadline: float | None = None,
    ) -> Awaitable[DomainResult]: ...
