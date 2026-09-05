"""합성 질문으로 정규식 단독과 HCX를 추가한 판별의 동작을 비교한다."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import statistics
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from httpx import AsyncClient, Client
from pydantic import BaseModel, ConfigDict, Field

from pension_agent.agent.execution import AsyncConcurrencyLimiter, ModelConcurrencyMiddleware
from pension_agent.agent.injection_classifier import (
    HCXPromptInjectionClassifier,
    InjectionClassificationError,
    PromptInjectionClassifier,
)
from pension_agent.agent.model_factory import ChatClovaXFactoryError, create_chat_clovax
from pension_agent.agent.prompt_injection import is_direct_prompt_injection
from pension_agent.config import ClovaStudioConnection
from pension_agent.config.hcx import INJECTION_GUARD_HCX_CONFIG

_CASES_PATH = Path(__file__).resolve().parents[1] / "questions" / "prompt_injection_smoke.jsonl"


class SmokeCase(BaseModel):
    """실제 금융 정답셋과 분리된 합성 보안 판별 예시."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    id: str = Field(min_length=1)
    expected: Literal["allow", "block"]
    text: str = Field(min_length=1)


def load_cases() -> list[SmokeCase]:
    """고정 합성 질문셋의 구조와 ID 중복을 검증한다."""

    cases = [
        SmokeCase.model_validate_json(line)
        for line in _CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("합성 질문 ID가 중복되었습니다.")
    return cases


def _counts(rows: list[dict[str, Any]], method: str) -> dict[str, int]:
    return {
        "normal_allowed": sum(
            row["expected"] == "allow" and row[method] == "allow" for row in rows
        ),
        "normal_blocked": sum(
            row["expected"] == "allow" and row[method] == "block" for row in rows
        ),
        "attack_blocked": sum(
            row["expected"] == "block" and row[method] == "block" for row in rows
        ),
        "attack_allowed": sum(
            row["expected"] == "block" and row[method] == "allow" for row in rows
        ),
        "unavailable": sum(row[method] == "unavailable" for row in rows),
    }


async def evaluate_cases(
    cases: list[SmokeCase], classifier: PromptInjectionClassifier
) -> dict[str, Any]:
    """정규식 통과 사례만 순차 HCX 판별하고 원본 응답 없이 결과를 집계한다."""

    rows: list[dict[str, Any]] = []
    classifier_latencies: list[float] = []
    loop = asyncio.get_running_loop()
    for case in cases:
        started = loop.time()
        regex = "block" if is_direct_prompt_injection(case.text) else "allow"
        hybrid = regex
        route = "regex"
        if regex == "allow":
            route = "hcx"
            classifier_started = loop.time()
            try:
                hybrid = await classifier.classify(
                    case.text,
                    deadline=classifier_started + INJECTION_GUARD_HCX_CONFIG.timeout_seconds,
                )
                if hybrid not in ("allow", "block"):
                    hybrid = "unavailable"
            except (InjectionClassificationError, TimeoutError):
                hybrid = "unavailable"
            classifier_latencies.append(loop.time() - classifier_started)
        rows.append(
            {
                "id": case.id,
                "expected": case.expected,
                "regex": regex,
                "hybrid": hybrid,
                "route": route,
                "elapsed_seconds": round(loop.time() - started, 4),
            }
        )
    ordered = sorted(classifier_latencies)
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "model": INJECTION_GUARD_HCX_CONFIG.model,
        "model_config": INJECTION_GUARD_HCX_CONFIG.model_dump(),
        "cases_sha256": hashlib.sha256(_CASES_PATH.read_bytes()).hexdigest(),
        "classifier_prompt_sha256": hashlib.sha256(
            resources.files("pension_agent.prompts")
            .joinpath("security", "injection-classifier.md")
            .read_bytes()
        ).hexdigest(),
        "cases": rows,
        "summary": {
            "total": len(rows),
            "normal": sum(case.expected == "allow" for case in cases),
            "attack": sum(case.expected == "block" for case in cases),
            "regex": _counts(rows, "regex"),
            "hybrid": _counts(rows, "hybrid"),
            "classifier_calls": len(ordered),
            "classifier_latency_seconds": {
                "p50": round(statistics.median(ordered), 4) if ordered else None,
                "p95": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 4) if ordered else None,
            },
        },
    }


async def _run_live(cases: list[SmokeCase], env_file: Path) -> dict[str, Any]:
    connection = ClovaStudioConnection(_env_file=env_file)  # type: ignore[call-arg]
    with Client() as http_client:
        async with AsyncClient() as http_async_client:
            model = create_chat_clovax(
                config=INJECTION_GUARD_HCX_CONFIG,
                connection=connection,
                http_client=http_client,
                http_async_client=http_async_client,
            )
            classifier = HCXPromptInjectionClassifier(
                model=model,
                model_concurrency=ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1)),
            )
            return await evaluate_cases(cases, classifier)


def main() -> None:
    """명시적으로 실행한 CLI에서만 HCX를 호출하고 새 보고서 파일을 만든다."""

    parser = argparse.ArgumentParser(description="합성 프롬프트 공격 20개 예시를 HCX로 판별합니다.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    parser.add_argument(
        "--output", type=Path, default=Path(".cache") / f"prompt-injection-smoke-{timestamp}.json"
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("출력 파일이 이미 있습니다. 새 --output 경로를 지정해 주세요.")
    if not args.env_file.is_file():
        parser.error("--env-file에 읽을 수 있는 환경 설정 파일을 지정해 주세요.")
    try:
        cases = load_cases()
        report = asyncio.run(_run_live(cases, args.env_file))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write("\n")
    except (ChatClovaXFactoryError, OSError, ValueError):
        parser.error("판별 평가 준비 또는 보고서 저장에 실패했습니다. 설정과 경로를 확인해 주세요.")
    print(
        json.dumps({"output": str(args.output), "summary": report["summary"]}, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
