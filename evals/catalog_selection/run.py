"""고정된 카탈로그 선택 실험을 실제 HCX에 순차 실행하고 모든 시도를 보존한다."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import random
import statistics
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv
from httpx import AsyncClient, Request, Response
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import messages_to_dict
from langsmith import trace
from pydantic import ValidationError

from evals.catalog_selection.scoring import score_plan
from pension_agent.agent.execution import AsyncConcurrencyLimiter, ModelConcurrencyMiddleware
from pension_agent.agent.model_factory import create_chat_clovax
from pension_agent.agent.product.catalog_query import (
    CatalogQueryPlanError,
    HCXProductCatalogQueryPlanner,
    load_product_catalog_query_prompt,
)
from pension_agent.agent.product.catalog_selection import (
    CatalogSelectionMode,
    CatalogSelectionSnapshot,
)
from pension_agent.config import DEFAULT_DOMAIN_AGENT_HCX_CONFIG, ClovaStudioConnection
from pension_agent.retrieval import ProductCatalog, ProductCatalogError, load_product_catalog

MODES: tuple[CatalogSelectionMode, ...] = ("compact_codes", "row_codes", "row_ids")
ORDERS = ("original", "shuffled")


def save(path: Path, value: Any) -> None:
    """원자료를 읽기 가능한 JSON으로 저장한다."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def exception_info(error: BaseException) -> list[dict[str, Any]]:
    """인증 헤더나 연결 설정 없이 오류 종류와 제공자 상태를 남긴다."""
    chain = []
    current: BaseException | None = error
    while current is not None and len(chain) < 8:
        detail = {
            "type": type(current).__name__,
            "status_code": getattr(current, "status_code", None),
            "body": getattr(current, "body", None),
            "retryable": getattr(current, "retryable", None),
            "submitted_query": getattr(current, "submitted_query", None),
        }
        if isinstance(current, ValidationError):
            detail["validation_errors"] = [
                {"type": item["type"], "loc": item["loc"]}
                for item in current.errors(
                    include_input=False, include_context=False, include_url=False
                )
            ]
        elif isinstance(current, (CatalogQueryPlanError, ProductCatalogError)):
            detail["message"] = str(current)
        chain.append(detail)
        current = current.__cause__
    return chain


class ModelObserver(BaseCallbackHandler):
    """모델 호출과 원시 구조화 응답을 SDK의 물리 요청과 별도로 남긴다."""

    def __init__(self) -> None:
        self.calls: dict[str, dict[str, Any]] = {}

    def on_chat_model_start(
        self, serialized: Any, messages: Any, *, run_id: Any, **kwargs: Any
    ) -> None:
        self.calls[str(run_id)] = {"input": messages_to_dict(messages[0])}

    def on_llm_end(self, response: Any, *, run_id: Any, **kwargs: Any) -> None:
        message = response.generations[0][0].message
        self.calls.setdefault(str(run_id), {})["output"] = message.model_dump(mode="json")

    def on_llm_error(self, error: BaseException, *, run_id: Any, **kwargs: Any) -> None:
        self.calls.setdefault(str(run_id), {})["error"] = exception_info(error)


class HttpObserver:
    """SDK 내부 재시도를 포함한 물리 요청을 기록하고 인증 헤더는 저장하지 않는다."""

    def __init__(self) -> None:
        self.directory: Path | None = None
        self.attempts: list[dict[str, Any]] = []

    async def request(self, request: Request) -> None:
        assert self.directory is not None
        number = len(self.attempts) + 1
        request.extensions["catalog_eval_attempt"] = number
        self.attempts.append({"number": number, "started_monotonic": time.monotonic()})
        save(self.directory / "http-attempts.json", self.attempts)
        try:
            body = await request.aread()
        except BaseException as error:
            self.attempts[-1].update(
                request_read_error=exception_info(error),
                latency_seconds=time.monotonic() - self.attempts[-1]["started_monotonic"],
            )
            save(self.directory / "http-attempts.json", self.attempts)
            raise
        (self.directory / f"http-{number:02d}.request.json").write_bytes(body)

    async def response(self, response: Response) -> None:
        assert self.directory is not None
        number = response.request.extensions["catalog_eval_attempt"]
        attempt = self.attempts[number - 1]
        attempt.update(
            status_code=response.status_code,
            headers_latency_seconds=time.monotonic() - attempt["started_monotonic"],
            response_complete=False,
        )
        save(self.directory / "http-attempts.json", self.attempts)
        try:
            body = await response.aread()
        except BaseException as error:
            attempt.update(
                body_read_error=exception_info(error),
                latency_seconds=time.monotonic() - attempt["started_monotonic"],
            )
            save(self.directory / "http-attempts.json", self.attempts)
            raise
        attempt.update(
            response_complete=True,
            latency_seconds=time.monotonic() - attempt["started_monotonic"],
        )
        (self.directory / f"http-{number:02d}.response.txt").write_bytes(body)
        save(self.directory / "http-attempts.json", self.attempts)


def query_from_output(output: dict[str, Any] | None) -> dict[str, Any] | None:
    if not output:
        return None
    calls = output.get("tool_calls", [])
    if not isinstance(calls, list) or len(calls) != 1 or not isinstance(calls[0], dict):
        return None
    if calls[0].get("name") != "return_product_catalog_query":
        return None
    args = calls[0].get("args")
    if not isinstance(args, dict):
        return None
    query = args.get("query")
    return query if isinstance(query, dict) else None


def identifier_counts(
    query: dict[str, Any] | None, catalog: ProductCatalog, mode: CatalogSelectionMode
) -> dict[str, int]:
    """반환된 식별자의 존재만 세고 상품의 의미 정답과 분리한다."""
    if not query:
        return {"returned": 0, "valid": 0}
    targets = query.get("targets", []) if query.get("route") == "resolve_products" else [query]
    if not isinstance(targets, list):
        return {"returned": 0, "valid": 0}
    key = "selected_row_id" if mode == "row_ids" else "product_code"
    allowed = (
        set(CatalogSelectionSnapshot.from_catalog(catalog, mode=mode).product_codes_by_row_id)
        if mode == "row_ids"
        else {product.product_code for product in catalog.products}
    )
    values = [target[key] for target in targets if isinstance(target, dict) and key in target]
    return {
        "returned": len(values),
        "valid": sum(isinstance(v, str) and v in allowed for v in values),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """선택 의미·실행 완료·인프라 실패를 각 분모와 함께 집계한다."""
    summary = {}
    for mode in MODES:
        selected = [row for row in rows if row["mode"] == mode]
        completed = [row for row in selected if row["execution_status"] == "completed"]
        latency = [row["latency_seconds"] for row in selected]
        usage = [row["prompt_tokens"] for row in selected if row["prompt_tokens"] is not None]
        summary[mode] = {
            "logical_calls": len(selected),
            "completed": len(completed),
            "whole_query_correct": sum(row["score"]["correct"] for row in selected),
            "target_correct": sum(sum(row["score"]["targets_correct"]) for row in selected),
            "target_total": sum(row["score"]["expected_targets"] for row in selected),
            "failure_kinds": dict(
                Counter(row["failure_kind"] for row in selected if row["failure_kind"])
            ),
            "identifiers_returned": sum(row["identifiers"]["returned"] for row in selected),
            "identifiers_valid": sum(row["identifiers"]["valid"] for row in selected),
            "http_attempts": sum(len(row["http_attempts"]) for row in selected),
            "http_errors": sum(
                attempt.get("status_code", 599) >= 400
                for row in selected
                for attempt in row["http_attempts"]
            ),
            "http_body_failures": sum(
                "body_read_error" in attempt for row in selected for attempt in row["http_attempts"]
            ),
            "median_seconds": statistics.median(latency) if latency else None,
            "mean_prompt_tokens": statistics.mean(usage) if usage else None,
            "usage_available": len(usage),
            "by_order": {
                order: {
                    "total": sum(row["order"] == order for row in selected),
                    "correct": sum(
                        row["order"] == order and row["score"]["correct"] for row in selected
                    ),
                }
                for order in ORDERS
            },
        }
    return summary


async def run(args: argparse.Namespace) -> None:
    load_dotenv(args.env_file)
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_TRACING_SAMPLING_RATE"] = "1.0"
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=False)
    logging.basicConfig(
        level=logging.WARNING, handlers=[logging.FileHandler(output / "execution.log")]
    )
    cases = json.loads(args.cases.read_text())
    catalog = load_product_catalog()
    original = [entry.to_dict() for entry in catalog.products]
    shuffled = list(original)
    random.Random(args.seed).shuffle(shuffled)
    aliases = json.loads(
        resources.files("pension_agent.retrieval")
        .joinpath("product_document_aliases.json")
        .read_text(encoding="utf-8")
    )
    catalogs = {
        order: ProductCatalog.from_payloads({"products": entries}, aliases)
        for order, entries in zip(ORDERS, (original, shuffled), strict=True)
    }
    jobs = []
    for order_index, order in enumerate(ORDERS):
        for index, case in enumerate(cases):
            offset = (index + order_index) % len(MODES)
            for mode in MODES[offset:] + MODES[:offset]:
                jobs.append({"case_id": case["id"], "order": order, "mode": mode})
    save(output / "cases.json", cases)
    save(output / "schedule.json", jobs)
    manifest = {
        "started_at": datetime.now(UTC).isoformat(),
        "base_commit": (
            await asyncio.to_thread(
                subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True
            )
        ).strip(),
        "working_diff": await asyncio.to_thread(
            subprocess.check_output, ["git", "diff", "--stat"], text=True
        ),
        "catalog_version": catalog.version,
        "cases_sha256": digest(args.cases.read_bytes()),
        "model_config": DEFAULT_DOMAIN_AGENT_HCX_CONFIG.model_dump(),
        "seed": args.seed,
        "interval_seconds": args.interval_seconds,
        "cooldown_after_429_seconds": 30,
        "deadline_seconds": 75,
        "tracing": True,
        "planned_calls": len(jobs),
        "note": "순서 조건 2개에서 각 1회이며 독립 확률 반복 2회가 아니다.",
        "source_sha256": {
            str(path): digest(path.read_bytes())
            for path in (
                Path("evals/catalog_selection/run.py"),
                Path("evals/catalog_selection/scoring.py"),
                Path("evals/catalog_selection/README.md"),
                Path("pension_agent/agent/product/catalog_query.py"),
                Path("pension_agent/agent/product/catalog_selection.py"),
                Path("pension_agent/prompts/domain/product-catalog-query-planner.md"),
                Path("pension_agent/prompts/domain/product-catalog-selection.json"),
                Path("pension_agent/retrieval/product_document_aliases.json"),
            )
        },
    }
    for order, selected_catalog in catalogs.items():
        save(
            output / f"catalog-{order}.json", [item.to_dict() for item in selected_catalog.products]
        )
        for mode in MODES:
            prompt = load_product_catalog_query_prompt(selected_catalog, selection_mode=mode)
            (output / f"prompt-{order}-{mode}.md").write_text(prompt)
            manifest[f"prompt_{order}_{mode}_sha256"] = digest(prompt.encode())
    save(output / "manifest.json", manifest)
    observer = HttpObserver()
    rows: list[dict[str, Any]] = []
    async with AsyncClient(
        event_hooks={"request": [observer.request], "response": [observer.response]}
    ) as client:
        model = create_chat_clovax(
            config=DEFAULT_DOMAIN_AGENT_HCX_CONFIG,
            connection=ClovaStudioConnection(),
            http_async_client=client,
        )
        planners = {
            (order, mode): HCXProductCatalogQueryPlanner(
                model=model,
                catalog=selected_catalog,
                selection_mode=mode,
                model_concurrency=ModelConcurrencyMiddleware(AsyncConcurrencyLimiter(1)),
            )
            for order, selected_catalog in catalogs.items()
            for mode in MODES
        }
        for (order, mode), planner in planners.items():
            # 실행 전에 실제 바인딩된 Tool schema도 고정한다.
            schema_path = output / f"tools-{order}-{mode}.json"
            save(schema_path, planner._model.kwargs.get("tools"))  # type: ignore[attr-defined]
            manifest[f"tools_{order}_{mode}_sha256"] = digest(schema_path.read_bytes())
        save(output / "manifest.json", manifest)
        cases_by_id = {case["id"]: case for case in cases}
        for index, job in enumerate(jobs):
            case = cases_by_id[job["case_id"]]
            mode = cast(CatalogSelectionMode, job["mode"])
            order = job["order"]
            directory = output / f"{index + 1:03d}-{case['id']}-{order}-{mode}"
            directory.mkdir()
            observer.directory = directory
            observer.attempts = []
            model_observer = ModelObserver()
            model.callbacks = [model_observer]
            started = time.monotonic()
            row: dict[str, Any] = {
                **job,
                "directory": directory.name,
                "execution_status": "completed",
                "failure_kind": None,
            }
            save(
                directory / "input.json",
                {"question": case["question"], "objective": case["objective"]},
            )
            with trace(
                "catalog_selection_eval",
                inputs={"question": case["question"], "objective": case["objective"]},
                metadata=job,
            ) as traced:
                try:
                    plan = await planners[(order, mode)].plan(
                        question=case["question"],
                        objective=case["objective"],
                        deadline=asyncio.get_running_loop().time() + 75,
                    )
                    row["plan"] = plan.model_dump(exclude_none=True)
                    traced.end(outputs={"plan": row["plan"]})
                except Exception as error:  # noqa: BLE001
                    row["plan"] = None
                    row["execution_status"] = (
                        "timeout" if isinstance(error, TimeoutError) else "failed"
                    )
                    row["errors"] = exception_info(error)
                    if isinstance(error, TimeoutError):
                        row["failure_kind"] = "timeout"
                    elif getattr(error, "retryable", False):
                        row["failure_kind"] = "catalog_selection"
                    elif (
                        model_observer.calls and "output" in list(model_observer.calls.values())[-1]
                    ):
                        row["failure_kind"] = "output_format"
                    elif any(item["status_code"] is not None for item in row["errors"]):
                        row["failure_kind"] = "provider_http"
                    else:
                        row["failure_kind"] = "provider_or_connection"
                    traced.end(outputs={"failure_kind": row["failure_kind"]})
                row["trace_id"] = str(traced.id)
            row["latency_seconds"] = round(time.monotonic() - started, 4)
            row["http_attempts"] = observer.attempts
            row["model_calls"] = list(model_observer.calls.values())
            outputs = [call["output"] for call in row["model_calls"] if "output" in call]
            row["first_model_output"] = outputs[0] if outputs else None
            row["final_model_output"] = outputs[-1] if outputs else None
            row["raw_query"] = query_from_output(row["final_model_output"])
            row["identifiers"] = identifier_counts(row["raw_query"], catalogs[order], mode)
            row["score"] = score_plan(case, row["plan"])
            usages = [message.get("usage_metadata") for message in outputs]
            row["prompt_tokens"] = (
                sum(u["input_tokens"] for u in usages if u) if any(usages) else None
            )
            row["completion_tokens"] = (
                sum(u["output_tokens"] for u in usages if u) if any(usages) else None
            )
            save(directory / "result.json", row)
            rows.append(row)
            with (output / "results.jsonl").open("a") as stream:
                stream.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            save(output / "summary.json", summarize(rows))
            print(
                f"{index + 1}/{len(jobs)} {case['id']} {order} {mode}: {row['execution_status']} correct={row['score']['correct']} {row['latency_seconds']:.1f}s http={len(observer.attempts)}",
                flush=True,
            )
            if index + 1 < len(jobs):
                delay = max(0, args.interval_seconds - (time.monotonic() - started))
                if any(attempt.get("status_code") == 429 for attempt in observer.attempts):
                    delay = max(delay, 30)
                await asyncio.sleep(delay)
    manifest["finished_at"] = datetime.now(UTC).isoformat()
    save(output / "manifest.json", manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=Path("evals/catalog_selection/cases.json"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--seed", type=int, default=169)
    parser.add_argument("--interval-seconds", type=float, default=10)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
