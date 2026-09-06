"""보존된 카탈로그 선택 실험을 읽어 Markdown과 독립 HTML 보고서를 만든다."""

from __future__ import annotations

import argparse
import html
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

MODES = ("compact_codes", "row_codes", "row_ids")
LABELS = dict(zip(MODES, ("A · 기존 JSON", "B · 상품별 행 + 코드", "C · 상품별 행 + 선택 ID")))


def ratio(correct: int, total: int) -> str:
    """분모가 없으면 성공률을 만들지 않는다."""
    return f"{correct}/{total} ({correct / total:.1%})" if total else "— (0/0)"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class Document:
    """같은 본문과 표를 두 형식에 기록하고 HTML 데이터는 이스케이프한다."""

    def __init__(self) -> None:
        self.markdown: list[str] = []
        self.html: list[str] = []

    def heading(self, text: str, level: int = 2) -> None:
        self.markdown.append(f"{'#' * level} {text}\n")
        self.html.append(f"<h{level}>{html.escape(text)}</h{level}>")

    def paragraph(self, text: str) -> None:
        self.markdown.append(text + "\n")
        self.html.append(f"<p>{html.escape(text)}</p>")

    def table(self, headers: list[str], rows: list[list[Any]]) -> None:
        def cell(value: Any) -> str:
            return str(value).replace("|", "\\|").replace("\n", "<br>")

        self.markdown.extend(
            [
                "| " + " | ".join(map(cell, headers)) + " |",
                "| " + " | ".join("---" for _ in headers) + " |",
            ]
            + ["| " + " | ".join(map(cell, row)) + " |" for row in rows]
            + [""]
        )
        self.html.append(
            '<div class="scroll"><table><thead><tr>'
            + "".join(f"<th>{html.escape(item)}</th>" for item in headers)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>" + "".join(f"<td>{html.escape(str(item))}</td>" for item in row) + "</tr>"
                for row in rows
            )
            + "</tbody></table></div>"
        )

    def code(self, value: Any) -> None:
        text = json.dumps(value, ensure_ascii=False, indent=2)
        self.markdown.append(f"```json\n{text}\n```\n")
        self.html.append(f"<pre>{html.escape(text)}</pre>")

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "report.md").write_text("\n".join(self.markdown), encoding="utf-8")
        style = """
        body{font:15px/1.65 system-ui,sans-serif;color:#172337;background:#f5f7fb;margin:0}
        main{max-width:1320px;margin:auto;padding:32px}h1{font-size:30px}h2{margin-top:40px}
        h3{margin-top:28px}.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;
        background:white;margin:12px 0}td,th{text-align:left;padding:10px;border:1px solid #dce2ec;
        vertical-align:top;min-width:80px}th{background:#eaf0f8}pre{white-space:pre-wrap;
        overflow-wrap:anywhere;background:#eaf0f8;padding:16px;border-radius:8px}
        details{border:1px solid #dce2ec;padding:12px 18px;margin:12px 0;background:white}
        summary{font-weight:600;cursor:pointer}p{max-width:1100px}
        """
        (directory / "report.html").write_text(
            '<!doctype html><html lang="ko"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>카탈로그 선택 실험</title><style>{style}</style><main>"
            + "\n".join(self.html)
            + "</main></html>",
            encoding="utf-8",
        )


def has_limit_code(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            (key == "code" and str(item) == "42901") or has_limit_code(item)
            for key, item in value.items()
        )
    return isinstance(value, list) and any(has_limit_code(item) for item in value)


def stats(rows: list[dict[str, Any]]) -> list[str]:
    complete = [row for row in rows if row["execution_status"] == "completed"]
    return [
        ratio(sum(row["score"]["correct"] for row in rows), len(rows)),
        ratio(sum(row["score"]["correct"] for row in complete), len(complete)),
        ratio(
            sum(sum(row["score"]["targets_correct"]) for row in rows),
            sum(row["score"]["expected_targets"] for row in rows),
        ),
        ratio(
            sum(row["identifiers"]["valid"] for row in rows),
            sum(row["identifiers"]["returned"] for row in rows),
        ),
    ]


def pivot(doc: Document, title: str, groups: dict[str, list[dict[str, Any]]]) -> None:
    doc.heading(title)
    doc.table(
        ["구분", *LABELS.values()],
        [
            [name] + [stats([row for row in rows if row["mode"] == mode])[0] for mode in MODES]
            for name, rows in groups.items()
        ],
    )


def targets(plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not plan:
        return []
    value = plan.get("targets", []) if plan.get("route") == "resolve_products" else [plan]
    return value if isinstance(value, list) else []


def raw_target_scores(
    case: dict[str, Any], row: dict[str, Any], catalog: list[dict[str, Any]]
) -> tuple[list[bool], list[str | None]]:
    """원문 선택을 대상별로 관측하되 수용된 계획의 사전 점수는 바꾸지 않는다."""
    query = row.get("raw_query")
    actual = (
        targets(query)
        if isinstance(query, dict)
        and query.get("route")
        in {"resolve_product", "resolve_products", "product_ambiguous", "product_not_found"}
        else []
    )
    by_id = {f"P{index:03d}": item["product_code"] for index, item in enumerate(catalog, 1)}
    known_codes = set(by_id.values())
    codes: list[str | None] = []
    for target in actual:
        code = None
        if isinstance(target, dict):
            selector = target.get("selected_row_id" if row["mode"] == "row_ids" else "product_code")
            if isinstance(selector, str):
                code = by_id.get(selector) if row["mode"] == "row_ids" else selector
        codes.append(code if code in known_codes else None)
    scores = []
    for index, expected in enumerate(case["expected"]["targets"]):
        target = actual[index] if index < len(actual) else None
        correct = isinstance(target, dict) and target.get("resolution_status") == expected["status"]
        if correct:
            if expected["status"] == "single":
                correct = codes[index] in expected["acceptable_codes"]
            else:
                correct = "product_code" not in target and "selected_row_id" not in target
        scores.append(correct)
    return scores, codes


def result_label(row: dict[str, Any] | None) -> str:
    if row is None:
        return "미실행"
    if row["execution_status"] != "completed":
        return "실행 실패 · " + str(row.get("failure_kind") or row["execution_status"])
    return "정답" if row["score"]["correct"] else "오답"


def failures(
    doc: Document,
    rows: list[dict[str, Any]],
    cases: dict[str, Any],
    products: dict[str, Any],
) -> None:
    doc.heading("실패·오답의 선택 경로")
    wrong = [row for row in rows if not row["score"]["correct"]]
    if not wrong:
        doc.paragraph(
            "실행된 요청에서 실패나 오답이 없습니다. 미실행 요청은 이 판정에 포함하지 않습니다."
        )
    for row in wrong:
        case = cases[row["case_id"]]
        title = f"{row['case_id']} · {row['order']} · {LABELS[row['mode']]} · {result_label(row)}"
        doc.html.append(f"<details><summary>{html.escape(title)}</summary>")
        doc.heading(title, 3)
        doc.paragraph(case["question"])
        doc.paragraph("정답 근거: " + case["rationale"])
        expected = case["expected"]["targets"]
        raw = targets(row.get("raw_query"))
        plan = targets(row.get("plan"))
        values = []
        for index in range(max(len(expected), len(raw), len(plan))):
            gold = expected[index] if index < len(expected) else {}
            output = raw[index] if index < len(raw) and isinstance(raw[index], dict) else {}
            actual = plan[index] if index < len(plan) and isinstance(plan[index], dict) else {}
            code = actual.get("product_code")
            raw_code = (
                row["raw_target_codes"][index] if index < len(row["raw_target_codes"]) else None
            )
            values.append(
                [
                    index + 1,
                    gold.get("status", "추가 대상"),
                    " / ".join(
                        f"{item} · {products.get(item, {}).get('official_name', '미등록 코드')}"
                        for item in gold.get("acceptable_codes", [])
                    )
                    or "코드 없음",
                    json.dumps(output["mention_parts"], ensure_ascii=False)
                    if "mention_parts" in output
                    else "별도 표현 없음",
                    output.get("selected_row_id", output.get("product_code", "코드/ID 없음")),
                    f"{raw_code} · {products[raw_code]['official_name']}" if raw_code else "—",
                    row["raw_targets_correct"][index]
                    if index < len(row["raw_targets_correct"])
                    else "추가 대상",
                    actual.get("resolution_status", "내부 계획 없음"),
                    code or "—",
                    products.get(code, {}).get("official_name", "—"),
                ]
            )
        doc.table(
            [
                "순서",
                "기대 상태",
                "기대 코드·공식명",
                "모델 원문 표현",
                "모델 선택",
                "원문 선택의 코드·공식명 (보조)",
                "원문 대상 정답 (보조)",
                "내부 상태",
                "연결 코드",
                "연결 공식명",
            ],
            values,
        )
        doc.code(
            {
                "expected_route": case["expected"]["route"],
                "raw_query": row.get("raw_query"),
                "internal_plan": row.get("plan"),
                "errors": row.get("errors", []),
            }
        )
        doc.html.append("</details>")


def generate_report(source: Path, output: Path | None = None) -> None:
    """기존 원자료만 읽으며 실험을 다시 실행하거나 정답을 변경하지 않는다."""
    manifest = load(source / "manifest.json")
    cases = {case["id"]: case for case in load(source / "cases.json")}
    products = {item["product_code"]: item for item in load(source / "catalog-original.json")}
    rows = [
        json.loads(line) for line in (source / "results.jsonl").read_text().splitlines() if line
    ]
    catalogs = {
        order: load(source / f"catalog-{order}.json")
        for order in dict.fromkeys(row["order"] for row in rows)
    }
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (row["case_id"], row["order"], row["mode"])
        if key in seen:
            raise ValueError(f"중복 실행을 임의로 합칠 수 없습니다: {key}")
        seen.add(key)
        row["raw_targets_correct"], row["raw_target_codes"] = raw_target_scores(
            cases[row["case_id"]], row, catalogs[row["order"]]
        )
        row["limit_responses"] = 0
        for attempt in row["http_attempts"]:
            path = source / row["directory"] / f"http-{attempt['number']:02d}.response.txt"
            if path.exists():
                try:
                    row["limit_responses"] += has_limit_code(load(path))
                except json.JSONDecodeError:
                    pass
    doc = Document()
    doc.heading("카탈로그 선택 실험", 1)
    doc.paragraph(
        f"예정 {manifest['planned_calls']}회 중 {len(rows)}회 실행. "
        f"상품 {len(products)}개, 질문 {len(cases)}개, 순서 섞기 seed={manifest['seed']}. "
        "기본 순서와 섞은 순서에서 각각 한 번 실행했으며 독립 반복 실험 2회가 아닙니다."
    )
    doc.paragraph(
        f"실행 시작: {manifest['started_at']} / 종료: {manifest.get('finished_at', '진행 중')}. "
        f"기준 커밋: {manifest['base_commit']}. 카탈로그: {manifest['catalog_version']}."
    )
    doc.paragraph(
        "전체 실행 정답률에는 호출 실패도 포함합니다. 완료 정답률은 실행 완료 요청만 대상으로 합니다. "
        "질문 정답은 route·대상 수·순서·각 상태·코드가 모두 일치해야 합니다. "
        "유효한 식별자를 반환해도 다른 상품이면 오답입니다. 미실행 요청은 정답률 분모에서 제외합니다."
    )
    doc.table(
        ["방식", "전체 실행 정답", "완료 실행 정답", "수용된 계획의 대상 정답", "반환 식별자 유효"],
        [[LABELS[mode], *stats([row for row in rows if row["mode"] == mode])] for mode in MODES],
    )
    doc.paragraph(
        "수용된 계획의 대상 정답은 Python이 전체 계획을 수용했을 때만 인정합니다. "
        "하나의 잘못된 식별자 때문에 계획이 거절되면 다른 대상의 원문 선택이 맞아도 이 점수는 0입니다."
    )
    doc.heading("모델 원문에서 관측한 대상 정답 (사후 보조 집계)")
    doc.paragraph(
        "각 원문 대상의 상태와 실제 코드를 기대 순서대로 따로 비교합니다. A/B는 출력 코드를 그대로, "
        "C는 해당 순서의 카탈로그에서 P001부터 부여한 행 ID를 코드로 연결합니다. 식별자를 보정하지 않으며 "
        "알 수 없는 값·null·필수 식별자 누락은 오답입니다. 응답이 없는 호출도 대상 분모에 포함합니다. "
        "이 사후 관측은 전체 계획의 유효성 검증을 대신하지 않으며 원래 점수와 사전 채택 기준을 바꾸지 않습니다."
    )
    values = []
    for mode in MODES:
        rates = []
        for order in (None, "original", "shuffled"):
            selected = [
                row
                for row in rows
                if row["mode"] == mode and (order is None or row["order"] == order)
            ]
            rates.append(
                ratio(
                    sum(sum(row["raw_targets_correct"]) for row in selected),
                    sum(row["score"]["expected_targets"] for row in selected),
                )
            )
        values.append([LABELS[mode], *rates])
    doc.table(["방식", "원문 관측 대상 전체", "원래 순서", "섞은 순서"], values)
    doc.heading("호출·토큰·지연")
    values = []
    for mode in MODES:
        selected = [row for row in rows if row["mode"] == mode]
        attempts = [attempt for row in selected for attempt in row["http_attempts"]]
        delays = sorted(row["latency_seconds"] for row in selected)
        usage = [row for row in selected if row.get("prompt_tokens") is not None]
        completed_usage = [row for row in selected if row.get("completion_tokens") is not None]
        values.append(
            [
                LABELS[mode],
                len(selected),
                len(attempts),
                sum(attempt.get("status_code") == 429 for attempt in attempts),
                sum(row["limit_responses"] for row in selected),
                sum(row["execution_status"] == "timeout" for row in selected),
                f"{statistics.median(delays):.2f}s / {delays[math.ceil(len(delays) * 0.95) - 1]:.2f}s"
                if delays
                else "—",
                f"{sum(row['prompt_tokens'] for row in usage):,} / {sum(row['completion_tokens'] for row in completed_usage):,}",
                f"입력 {len(usage)}/{len(selected)}, 출력 {len(completed_usage)}/{len(selected)}",
                json.dumps(
                    dict(
                        Counter(row["failure_kind"] for row in selected if row.get("failure_kind"))
                    ),
                    ensure_ascii=False,
                ),
            ]
        )
    doc.table(
        [
            "방식",
            "논리 호출",
            "HTTP 시도",
            "HTTP 429",
            "42901 응답",
            "타임아웃",
            "지연 중앙값 / p95",
            "입력 / 출력 토큰 합계",
            "토큰 기록 범위",
            "실패 유형",
        ],
        values,
    )
    doc.paragraph(
        "HTTP 시도는 SDK 재시도를 포함합니다. HTTP 429와 42901은 같은 응답에서 함께 집계될 수 있습니다. "
        "토큰은 usage가 기록된 응답만 합산하며 누락된 호출의 비용을 0으로 가정하지 않습니다. "
        "지연에는 성공·실패·재시도를 모두 포함합니다."
    )
    pivot(
        doc,
        "카탈로그 순서별 질문 정답",
        {
            order: [row for row in rows if row["order"] == order]
            for order in ("original", "shuffled")
        },
    )
    pivot(
        doc,
        "조회 유형별 질문 정답",
        {
            route: [row for row in rows if cases[row["case_id"]]["expected"]["route"] == route]
            for route in (
                "resolve_product",
                "resolve_products",
                "product_ambiguous",
                "product_not_found",
            )
        },
    )
    pivot(
        doc,
        "질문 범주별 정답",
        {
            category: [row for row in rows if cases[row["case_id"]]["category"] == category]
            for category in dict.fromkeys(case["category"] for case in cases.values())
        },
    )
    doc.heading("수용된 계획의 확정·모호·미등록 대상별 정답")
    values = []
    for status in ("single", "ambiguous", "not_found"):
        rates = []
        for mode in MODES:
            scores = [
                correct
                for row in rows
                if row["mode"] == mode
                for target, correct in zip(
                    cases[row["case_id"]]["expected"]["targets"],
                    row["score"]["targets_correct"],
                    strict=True,
                )
                if target["status"] == status
            ]
            rates.append(ratio(sum(scores), len(scores)))
        values.append([status, *rates])
    doc.table(["기대 상태", *LABELS.values()], values)
    indexed = {(row["case_id"], row["order"], row["mode"]): row for row in rows}
    doc.heading("사전 기준을 확인하는 완료 쌍의 차이")
    doc.paragraph(
        "사전 기준은 A 대비 질문·대상 정답 개선, 두 순서 각각의 대상 정답 비악화, "
        "코드 직접 입력과 모호·미등록 판별의 새 회귀 없음입니다. B와 C가 같으면 B를 우선하고, "
        "작은 차이·순서 간 상반·인프라 실패로 불명확하면 보류합니다. 아래는 수치이며 채택 판정은 아닙니다."
    )
    values = []
    for baseline, candidate in ((MODES[0], MODES[1]), (MODES[0], MODES[2]), (MODES[1], MODES[2])):
        for order in ("original", "shuffled"):
            pairs = [
                (
                    cases[case_id],
                    indexed[(case_id, order, baseline)],
                    indexed[(case_id, order, candidate)],
                )
                for case_id in cases
                if all(
                    indexed.get((case_id, order, mode), {}).get("execution_status") == "completed"
                    for mode in (baseline, candidate)
                )
            ]
            query_delta = sum(
                int(b["score"]["correct"]) - int(a["score"]["correct"]) for _, a, b in pairs
            )
            target_delta = sum(
                sum(b["score"]["targets_correct"]) - sum(a["score"]["targets_correct"])
                for _, a, b in pairs
            )
            code_regressions = sum(
                case["category"] == "explicit_code"
                and a["score"]["correct"]
                and not b["score"]["correct"]
                for case, a, b in pairs
            )
            unresolved_regressions = sum(
                target["status"] != "single" and before and not after
                for case, a, b in pairs
                for target, before, after in zip(
                    case["expected"]["targets"],
                    a["score"]["targets_correct"],
                    b["score"]["targets_correct"],
                    strict=True,
                )
            )
            values.append(
                [
                    f"{LABELS[baseline][0]} → {LABELS[candidate][0]}",
                    order,
                    f"{len(pairs)}/{len(cases)}",
                    f"{query_delta:+d}",
                    f"{target_delta:+d}",
                    code_regressions,
                    unresolved_regressions,
                ]
            )
    doc.table(
        [
            "비교",
            "순서",
            "완료 쌍 / 예정 쌍",
            "질문 정답 수 Δ",
            "수용된 계획의 대상 정답 수 Δ",
            "코드 문항 새 회귀",
            "모호·미등록 대상 새 회귀",
        ],
        values,
    )
    doc.heading("같은 질문·같은 순서에서의 A/B/C 비교")
    doc.table(
        ["문항", "질문", "범주", "순서", *LABELS.values()],
        [
            [
                case_id,
                case["question"],
                case["category"],
                order,
                *[result_label(indexed.get((case_id, order, mode))) for mode in MODES],
            ]
            for case_id, case in cases.items()
            for order in ("original", "shuffled")
        ],
    )
    failures(doc, rows, cases, products)
    doc.heading("재현 정보")
    doc.code(
        {
            key: manifest[key]
            for key in (
                "cases_sha256",
                "model_config",
                "interval_seconds",
                "deadline_seconds",
                "note",
            )
            if key in manifest
        }
    )
    doc.save(output or source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    generate_report(args.input, args.output)


if __name__ == "__main__":
    main()
