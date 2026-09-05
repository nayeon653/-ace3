"""직접 인젝션 차단과 모델 입력의 지시·데이터 경계 보강."""

import json
import re
import unicodedata
from collections.abc import Awaitable, Callable
from functools import lru_cache
from importlib import resources
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

INJECTION_REFUSAL = (
    "내부 지침 공개나 시스템 규칙 변경 요청은 처리할 수 없습니다. "
    "연금 제도·세금·상품에 관한 질문을 입력해 주세요."
)

# 일반적인 연금 규정의 제외·변경 요청과 구분하기 위해 지시 대상과 행위를 함께 검사한다.
_DIRECT_INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        (
            r"\b(?:ignore|disregard|forget|override|bypass)\s+"
            r"(?:(?:all|any|the|your)\s+){0,3}"
            r"(?:previous|prior|above|system|developer|safety|security)\s+"
            r"(?:(?:system|developer)\s+)?"
            r"(?:instructions?|prompts?|rules?|messages?|polic(?:y|ies))\b"
        ),
        (
            r"(?:이전|기존|상위|시스템|개발자|모든)\s*(?:의\s*)?"
            r"(?:시스템\s*)?(?:지침|지시|명령|프롬프트|규칙|정책)(?:들)?\s*"
            r"(?:을|를|은|는)?\s*(?:모두\s*|전부\s*)?"
            r"(?:(?:무시|폐기|우회)(?:해(?:\s*(?:줘|주세요|라))?|하라|하세요|하고)|"
            r"잊어(?:버려|줘)?|덮어써)(?![가-힣])"
        ),
        (
            r"\b(?:reveal|print|show|display|repeat|dump|leak|expose|output)\s+"
            r"(?:(?:me|all|the|your|full|entire|original|hidden|internal)\s+){0,5}"
            r"(?:system|developer)\s+(?:prompts?|instructions?|messages?)\b"
        ),
        (
            r"(?:시스템|개발자|숨겨진|내부)\s*(?:프롬프트|지침|지시|메시지)(?:의\s*원문)?\s*"
            r"(?:을|를|은|는)?\s*(?:그대로\s*|전부\s*|모두\s*)?"
            r"(?:(?:공개|출력|노출|유출|복사)(?:해(?:\s*(?:줘|주세요|라))?|하라|하세요|하고)|"
            r"보여\s*(?:줘|주세요)|알려\s*(?:줘|주세요))(?![가-힣])"
        ),
        r"<\|im_start\|>\s*(?:system|developer)\b",
        r"<\|start_header_id\|>\s*(?:system|developer)\s*<\|end_header_id\|>",
        r"^(?:</?(?:system|developer)>|\[(?:system|developer)\])",
    )
)


def is_direct_prompt_injection(text: str) -> bool:
    """알려진 명시적 공격 표현을 정규화한 복사본에서만 검사한다."""

    normalized = unicodedata.normalize("NFKC", text)
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Cf")
    normalized = " ".join(normalized.split())
    return any(pattern.search(normalized) for pattern in _DIRECT_INJECTION_PATTERNS)


@lru_cache(maxsize=1)
def _load_security_policy() -> str:
    return (
        resources.files("pension_agent.prompts")
        .joinpath("security", "input-trust-boundary.md")
        .read_text(encoding="utf-8")
        .strip()
    )


def protect_system_message(message: SystemMessage | None) -> SystemMessage:
    """단일 system 메시지에 공통 정책을 추가하고 기존 내용과 메타데이터를 보존한다."""

    policy = _load_security_policy()
    if message is None:
        return SystemMessage(content=policy)
    content = message.content
    if isinstance(content, str):
        protected_content: str | list[str | dict[str, Any]] = f"{content}\n\n{policy}"
    else:
        protected_content = [*content, {"type": "text", "text": policy}]
    return message.model_copy(update={"content": protected_content})


class PromptInjectionMiddleware(AgentMiddleware[Any, Any, Any]):
    """Main의 직접 공격을 차단하고 매 모델 호출에서 외부 Tool 텍스트를 격리한다."""

    def __init__(self, *, block_user_input: bool = False) -> None:
        self._block_user_input = block_user_input

    def _should_block(self, request: ModelRequest[Any]) -> bool:
        if not self._block_user_input:
            return False
        question = (request.state or {}).get("question", "")
        inputs: list[str] = [
            message.text for message in request.messages if isinstance(message, HumanMessage)
        ]
        if isinstance(question, str):
            inputs.append(question)
        return any(is_direct_prompt_injection(text) for text in inputs)

    def _protect_request(self, request: ModelRequest[Any]) -> ModelRequest[Any]:
        # state를 변경하면 근거 원문과 Tool 호출 이력까지 변하므로 요청 복사본만 감싼다.
        messages = [
            message.model_copy(
                update={
                    "content": json.dumps(
                        {"untrusted_tool_output": message.content},
                        ensure_ascii=False,
                    )
                }
            )
            if isinstance(message, ToolMessage)
            else message
            for message in request.messages
        ]
        return request.override(
            system_message=protect_system_message(request.system_message),
            messages=messages,
        )

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        if self._should_block(request):
            return ModelResponse(result=[AIMessage(content=INJECTION_REFUSAL)])
        return handler(self._protect_request(request))

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        if self._should_block(request):
            return ModelResponse(result=[AIMessage(content=INJECTION_REFUSAL)])
        return await handler(self._protect_request(request))
