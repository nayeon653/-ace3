"""Domain 실행기의 공통 실행 보호 계층."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import cast

from pydantic import TypeAdapter, ValidationError

from pension_agent.agent.contracts import (
    DomainName,
    DomainRequest,
    DomainResult,
    DomainRunner,
    validate_domain_result,
)
from pension_agent.agent.execution import effective_deadline
from pension_agent.config import DEFAULT_DOMAIN_AGENT_CONFIG, DomainAgentConfig

_DOMAIN_RESULT_ADAPTER = TypeAdapter(DomainResult)


@dataclass(slots=True)
class GuardedDomainRunner:
    """구현체에 timeout·동시성·결과 검증과 오류 정제를 적용한다."""

    domain: DomainName
    implementation: DomainRunner
    config: DomainAgentConfig = DEFAULT_DOMAIN_AGENT_CONFIG
    max_concurrency: int | None = None
    _capacity: asyncio.Semaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_concurrency is None:
            self.max_concurrency = self.config.max_concurrency
        if self.max_concurrency < 1:
            raise ValueError("Domain Agent 동시 실행 상한은 1 이상이어야 합니다.")
        self._capacity = asyncio.Semaphore(self.max_concurrency)

    async def __call__(
        self,
        request: DomainRequest,
        *,
        deadline: float | None = None,
    ) -> DomainResult:
        """공통 실행 보호 안에서 도메인 구현체를 호출한다."""

        try:
            question = request["question"].strip()
            objective = request["objective"].strip()
        except (AttributeError, KeyError, TypeError):
            return failed_domain_result(self.domain, "도메인 판단 요청이 올바르지 않습니다.")
        if not question or not objective:
            return failed_domain_result(self.domain, "도메인 판단 요청이 올바르지 않습니다.")

        run_deadline = effective_deadline(
            timeout_seconds=self.config.timeout_seconds,
            parent_deadline=deadline,
        )
        if run_deadline <= asyncio.get_running_loop().time():
            return failed_domain_result(
                self.domain,
                "Domain Agent 실행 시간이 초과됐습니다.",
                execution_status="timeout",
            )
        normalized_request: DomainRequest = {
            "question": question,
            "objective": objective,
        }
        try:
            async with asyncio.timeout_at(run_deadline):
                await self._capacity.acquire()
                try:
                    raw_result = await self.implementation(
                        normalized_request,
                        deadline=run_deadline,
                    )
                finally:
                    self._capacity.release()
        except TimeoutError:
            return failed_domain_result(
                self.domain,
                "Domain Agent 실행 시간이 초과됐습니다.",
                execution_status="timeout",
            )
        except Exception:  # noqa: BLE001
            return failed_domain_result(self.domain, "Domain Agent 실행에 실패했습니다.")

        try:
            result = _DOMAIN_RESULT_ADAPTER.validate_python(raw_result)
            validate_domain_result(result)
        except (KeyError, TypeError, ValueError, ValidationError):
            return failed_domain_result(
                self.domain,
                "Domain Agent가 최종 판단 결과를 제출하지 못했습니다.",
            )
        if result["domain"] != self.domain:
            return failed_domain_result(
                self.domain,
                "Domain Agent 결과 도메인이 일치하지 않습니다.",
            )
        return result


def failed_domain_result(
    domain: DomainName,
    error: str,
    *,
    execution_status: str = "failed",
) -> DomainResult:
    """내부 예외 정보를 노출하지 않는 실패 결과를 만든다."""

    return cast(
        DomainResult,
        {
            "domain": domain,
            "execution_status": execution_status,
            "evidence": [],
            "calculations": [],
            "warnings": [],
            "error": error,
        },
    )
