"""비교 검색 결과만 담은 독립 입력으로 HCX가 완성 답안을 작성한다."""

from __future__ import annotations

import asyncio
import json
from importlib import resources
from typing import Any

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain.tools import tool
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langsmith import traceable
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pension_agent.agent.contracts.domain import DecisionStatus, DomainResult, EvidenceChunk
from pension_agent.agent.execution import ModelConcurrencyMiddleware
from pension_agent.agent.product.comparison import ComparisonEvidenceResult

PRODUCT_COMPARISON_ANSWER_TOOL_NAME = "submit_comparison_answer"


class ComparisonAnswerError(RuntimeError):
    """비교 답안 모델 호출 또는 구조화 응답을 읽지 못한 오류."""


class _ComparisonAnswerSubmission(BaseModel):
    """답안의 의미를 판정하지 않고 출력 필드의 자료형만 읽는다."""

    model_config = ConfigDict(extra="forbid", strict=True)

    answer: str = Field(min_length=1)
    status: DecisionStatus
    missing_conditions: list[str]
    warnings: list[str]
    evidence_chunk_ids: list[str]


@tool(PRODUCT_COMPARISON_ANSWER_TOOL_NAME, args_schema=_ComparisonAnswerSubmission)
def _submit_comparison_answer(
    answer: str,
    status: DecisionStatus,
    missing_conditions: list[str],
    warnings: list[str],
    evidence_chunk_ids: list[str],
) -> str:
    """상품 비교 답안과 실제 사용한 근거 청크 ID를 반환한다."""

    del answer, status, missing_conditions, warnings, evidence_chunk_ids
    return ""


class HCXProductComparisonAnswerWriter:
    """상품 검색 이력과 분리된 한 번의 작성 요청을 기존 실행 예산 안에서 수행한다."""

    def __init__(
        self,
        *,
        model: BaseChatModel,
        model_concurrency: ModelConcurrencyMiddleware | None = None,
    ) -> None:
        self._system_prompt = (
            resources.files("pension_agent.prompts")
            .joinpath("domain", "product-comparison-answer.md")
            .read_text(encoding="utf-8")
        )
        self._model: Runnable[Any, AIMessage] = model.bind_tools(
            (_submit_comparison_answer,),
            tool_choice=PRODUCT_COMPARISON_ANSWER_TOOL_NAME,
        )
        self._model_concurrency = model_concurrency

    @traceable(name="product_comparison_answer", run_type="chain")
    async def write(
        self,
        *,
        question: str,
        objective: str,
        comparison: ComparisonEvidenceResult,
        deadline: float,
    ) -> DomainResult:
        """검색 실패·빈 근거는 직접 반환하고 나머지는 전용 HCX 입력으로 작성한다."""

        if comparison.execution_status != "completed":
            return {
                "domain": "product",
                "execution_status": comparison.execution_status,
                "evidence": [],
                "calculations": [],
                "warnings": list(comparison.limitations),
                "error": comparison.error or "상품 비교 문서 검색에 실패했습니다.",
            }

        evidence = _collect_evidence(comparison)
        if not evidence:
            return _no_evidence_result(comparison)
        if deadline <= asyncio.get_running_loop().time():
            raise TimeoutError

        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(
                content=json.dumps(
                    _model_input(
                        question=question,
                        objective=objective,
                        comparison=comparison,
                        evidence=evidence,
                    ),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
        ]

        async def invoke_model() -> AIMessage:
            return await self._model.ainvoke(messages)

        async def invoke() -> AIMessage:
            if self._model_concurrency is None:
                return await invoke_model()
            return await self._model_concurrency.arun(invoke_model, deadline=deadline)

        try:
            async with asyncio.timeout_at(deadline):
                response = await invoke()
            submission = _parse_submission(response)
        except TimeoutError:
            raise
        except ComparisonAnswerError:
            raise
        except (
            AttributeError,
            KeyError,
            OpenAIError,
            RuntimeError,
            TypeError,
            ValidationError,
            ValueError,
        ):
            raise ComparisonAnswerError("HCX 상품 비교 답안을 읽지 못했습니다.") from None

        selected_ids = set(submission.evidence_chunk_ids)
        return {
            "domain": "product",
            "execution_status": "completed",
            "decision": {
                "status": submission.status,
                "conclusion": submission.answer,
                "missing_conditions": submission.missing_conditions,
            },
            "comparison_answer": submission.answer,
            "evidence": [chunk for chunk in evidence if chunk["chunk_id"] in selected_ids],
            "calculations": [],
            "warnings": list(dict.fromkeys([*comparison.limitations, *submission.warnings])),
        }


def _parse_submission(response: AIMessage) -> _ComparisonAnswerSubmission:
    calls = response.tool_calls
    if len(calls) != 1 or calls[0]["name"] != PRODUCT_COMPARISON_ANSWER_TOOL_NAME:
        raise ComparisonAnswerError("HCX 상품 비교 답안의 구조화 출력이 올바르지 않습니다.")
    return _ComparisonAnswerSubmission.model_validate(calls[0]["args"])


def _collect_evidence(comparison: ComparisonEvidenceResult) -> list[EvidenceChunk]:
    evidence: dict[str, EvidenceChunk] = {}
    for product in comparison.products:
        for chunk in product.evidence:
            evidence.setdefault(
                chunk.chunk_id,
                {
                    "chunk_id": chunk.chunk_id,
                    "source_file_name": chunk.source_file_name,
                    "title": chunk.title,
                    "locator": chunk.locator,
                    "content": chunk.content,
                },
            )
    return list(evidence.values())


def _model_input(
    *,
    question: str,
    objective: str,
    comparison: ComparisonEvidenceResult,
    evidence: list[EvidenceChunk],
) -> dict[str, Any]:
    return {
        "question": question,
        "objective": objective,
        "catalog_version": comparison.catalog_version,
        "targets": comparison.targets,
        "criteria": comparison.criteria,
        "products": [
            {
                "product_code": product.product_code,
                "official_name": product.official_name,
                "provider": product.provider,
                "source_file_name": product.source_file_name,
                "evidence_ids": [chunk.chunk_id for chunk in product.evidence],
                "last_search_status": product.attempts[-1].execution_status,
                "last_search_error": product.attempts[-1].error,
            }
            for product in comparison.products
        ],
        "evidence": evidence,
        "limitations": comparison.limitations,
    }


def _no_evidence_result(comparison: ComparisonEvidenceResult) -> DomainResult:
    answer = "상품 비교에 사용할 문서 근거를 찾지 못해 차이와 적합성을 판단할 수 없습니다."
    conditions = comparison.limitations or ["비교할 상품 문서의 근거가 필요합니다."]
    return {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "undetermined",
            "conclusion": answer,
            "missing_conditions": list(conditions),
        },
        "comparison_answer": answer,
        "evidence": [],
        "calculations": [],
        "warnings": list(comparison.limitations),
    }
