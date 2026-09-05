"""HCX의 구조화 의미 판별로 사용자 입력의 프롬프트 공격을 검사한다."""

from __future__ import annotations

import asyncio
import json
import math
from importlib import resources
from typing import Any, Literal, Protocol

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain.tools import tool
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict

from pension_agent.agent.execution import ModelConcurrencyMiddleware, effective_deadline
from pension_agent.config.hcx import INJECTION_GUARD_HCX_CONFIG

INJECTION_VERDICT_TOOL_NAME = "return_prompt_injection_verdict"
InjectionDecision = Literal["allow", "block"]
_CLASSIFICATION_ERROR = "HCX 프롬프트 보안 판별 응답을 확인할 수 없습니다."


class InjectionClassificationError(RuntimeError):
    """의미 판별 실패를 원본 입력이나 제공자 응답 없이 전달한다."""


class _InjectionVerdict(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    decision: InjectionDecision


@tool(INJECTION_VERDICT_TOOL_NAME, args_schema=_InjectionVerdict)
def _return_prompt_injection_verdict(decision: InjectionDecision) -> str:
    """입력의 프롬프트 공격 여부를 allow 또는 block으로만 반환한다."""

    del decision
    return ""


class PromptInjectionClassifier(Protocol):
    """미들웨어가 공유하는 비동기 의미 판별 계약."""

    async def classify(self, text: str, *, deadline: float) -> InjectionDecision: ...


class HCXPromptInjectionClassifier:
    """요청 예산과 HCX 공유 슬롯 안에서 단일 구조화 판정을 받는다."""

    def __init__(
        self,
        *,
        model: BaseChatModel,
        model_concurrency: ModelConcurrencyMiddleware | None = None,
        timeout_seconds: float = INJECTION_GUARD_HCX_CONFIG.timeout_seconds,
    ) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("프롬프트 보안 판별 제한 시간은 유한한 양수여야 합니다.")
        self._system_prompt = (
            resources.files("pension_agent.prompts")
            .joinpath("security", "injection-classifier.md")
            .read_text(encoding="utf-8")
            .strip()
        )
        self._model: Runnable[Any, AIMessage] = model.bind_tools(
            (_return_prompt_injection_verdict,),
            tool_choice=INJECTION_VERDICT_TOOL_NAME,
        )
        self._model_concurrency = model_concurrency
        self._timeout_seconds = timeout_seconds

    async def classify(self, text: str, *, deadline: float) -> InjectionDecision:
        """지시문으로 해석하지 않을 원문을 격리해 보내고 판정만 반환한다."""

        if not math.isfinite(deadline):
            raise InjectionClassificationError(_CLASSIFICATION_ERROR)
        deadline = effective_deadline(
            timeout_seconds=self._timeout_seconds,
            parent_deadline=deadline,
        )
        if deadline <= asyncio.get_running_loop().time():
            raise TimeoutError
        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(
                content=json.dumps(
                    {"untrusted_input": text},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
        ]

        async def invoke() -> AIMessage:
            if self._model_concurrency is None:
                return await self._model.ainvoke(messages)
            return await self._model_concurrency.arun(
                lambda: self._model.ainvoke(messages),
                deadline=deadline,
            )

        timed_out = False
        try:
            async with asyncio.timeout_at(deadline):
                response = await invoke()
                if (
                    not isinstance(response, AIMessage)
                    or response.content
                    or response.invalid_tool_calls
                    or len(response.tool_calls) != 1
                    or response.tool_calls[0]["name"] != INJECTION_VERDICT_TOOL_NAME
                ):
                    raise InjectionClassificationError(_CLASSIFICATION_ERROR)
                return _InjectionVerdict.model_validate(response.tool_calls[0]["args"]).decision
        except TimeoutError:
            timed_out = True
        except (
            AttributeError,
            KeyError,
            OpenAIError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ):
            pass
        if timed_out:
            raise TimeoutError
        raise InjectionClassificationError(_CLASSIFICATION_ERROR)
