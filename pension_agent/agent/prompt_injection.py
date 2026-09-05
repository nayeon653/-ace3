"""Main 실행 시작 시 사용자 입력의 프롬프트 인젝션을 한 번 검사한다."""

import json
import logging
import re
import unicodedata
from typing import Any

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, HumanMessage

from pension_agent.agent.execution import ExecutionContext
from pension_agent.agent.injection_classifier import (
    InjectionClassificationError,
    PromptInjectionClassifier,
)

logger = logging.getLogger(__name__)

INJECTION_REFUSAL = (
    "내부 지침 공개나 시스템 규칙 변경 요청은 처리할 수 없습니다. "
    "연금 제도·세금·상품에 관한 질문을 입력해 주세요."
)
INPUT_CHECK_UNAVAILABLE = (
    "질문의 안전성을 확인하지 못해 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요."
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


def _user_inputs(state: Any) -> list[str]:
    inputs: list[str] = [
        message.text for message in state.get("messages", []) if isinstance(message, HumanMessage)
    ]
    question = state.get("question")
    if isinstance(question, str):
        inputs.append(question)
    return list(dict.fromkeys(text for text in inputs if text.strip()))


def _end_with_message(content: str) -> dict[str, Any]:
    return {"messages": [AIMessage(content=content)], "jump_to": "end"}


class MainInputGuardMiddleware(AgentMiddleware[Any, ExecutionContext, Any]):
    """Main 실행 시작 시 정규식과 HCX로 사용자 입력을 한 번 검사한다."""

    def __init__(self, classifier: PromptInjectionClassifier | None) -> None:
        self._classifier = classifier

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if any(is_direct_prompt_injection(text) for text in _user_inputs(state)):
            return _end_with_message(INJECTION_REFUSAL)
        # 제품 런타임은 native async이며 동기 실행으로 HCX 검사를 우회하지 않는다.
        if self._classifier is not None:
            return _end_with_message(INPUT_CHECK_UNAVAILABLE)
        return None

    @hook_config(can_jump_to=["end"])
    async def abefore_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        inputs = _user_inputs(state)
        if any(is_direct_prompt_injection(text) for text in inputs):
            return _end_with_message(INJECTION_REFUSAL)
        if self._classifier is None:
            return None
        context = getattr(runtime, "context", None)
        if not inputs or not isinstance(context, ExecutionContext):
            return _end_with_message(INPUT_CHECK_UNAVAILABLE)
        text = (
            inputs[0]
            if len(inputs) == 1
            else json.dumps({"user_inputs": inputs}, ensure_ascii=False)
        )
        try:
            decision = await self._classifier.classify(text, deadline=context.deadline)
        except (InjectionClassificationError, TimeoutError) as error:
            logger.warning("입력 안전성 판별을 완료하지 못했습니다: %s", type(error).__name__)
            return _end_with_message(INPUT_CHECK_UNAVAILABLE)
        if decision == "block":
            return _end_with_message(INJECTION_REFUSAL)
        if decision != "allow":
            return _end_with_message(INPUT_CHECK_UNAVAILABLE)
        return None
