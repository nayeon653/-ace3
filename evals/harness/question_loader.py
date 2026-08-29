"""버전 관리되는 Markdown 평가 질의셋을 구조화해 읽는다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_QUESTION_HEADERS = (
    "test_id",
    "source_id",
    "source_question",
    "adapted_question",
    "CAT",
    "question_type",
    "난이도",
    "적용가능성",
    "evaluation_focus",
    "required_fact_candidates",
    "evidence_candidate(검증필요)",
    "adaptation_note",
    "selection_reason",
)
_QUESTION_FIELDS = (
    "test_id",
    "source_id",
    "source_question",
    "adapted_question",
    "category",
    "question_type",
    "difficulty",
    "applicability",
    "evaluation_focus",
    "required_fact_candidates",
    "evidence_candidate",
    "adaptation_note",
    "selection_reason",
)
_EXPECTED_PREFIX_COUNTS = {"PROD": 15, "POLICY": 15}
_DEFAULT_QUESTION_PATH = Path(__file__).resolve().parents[1] / "questions" / "hantoo_selected_30.md"


@dataclass(frozen=True, slots=True)
class BenchmarkQuestion:
    """벤치마크의 질문 한 건과 평가용 메타데이터다."""

    test_id: str
    source_id: str
    source_question: str
    adapted_question: str
    category: str
    question_type: str
    difficulty: str
    applicability: str
    evaluation_focus: str
    required_fact_candidates: str
    evidence_candidate: str
    adaptation_note: str
    selection_reason: str


def load_hantoo_questions(path: Path | None = None) -> tuple[BenchmarkQuestion, ...]:
    """한투 기반 30개 평가 질의를 읽고 표 구조와 ID 유일성을 검증한다."""

    source_path = path or _DEFAULT_QUESTION_PATH
    lines = source_path.read_text(encoding="utf-8").splitlines()
    questions: list[BenchmarkQuestion] = []
    reading_question_table = False
    expecting_separator = False

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            reading_question_table = False
            expecting_separator = False
            continue

        cells = _split_markdown_row(line)
        if cells == _QUESTION_HEADERS:
            reading_question_table = True
            expecting_separator = True
            continue

        if not reading_question_table:
            continue

        if expecting_separator:
            if not _is_separator_row(cells):
                raise ValueError(f"{source_path}:{line_number} 표 구분선 형식이 올바르지 않습니다.")
            expecting_separator = False
            continue

        if not cells or not cells[0].startswith(("PROD-", "POLICY-")):
            reading_question_table = False
            continue
        if len(cells) != len(_QUESTION_FIELDS):
            raise ValueError(
                f"{source_path}:{line_number} 평가 질의는 {len(_QUESTION_FIELDS)}개 열이어야 "
                f"하지만 {len(cells)}개입니다."
            )

        values = dict(zip(_QUESTION_FIELDS, cells, strict=True))
        questions.append(BenchmarkQuestion(**values))

    _validate_questions(source_path, questions)
    return tuple(questions)


def _split_markdown_row(line: str) -> tuple[str, ...]:
    return tuple(cell.replace(r"\|", "|").strip() for cell in re.split(r"(?<!\\)\|", line[1:-1]))


def _is_separator_row(cells: tuple[str, ...]) -> bool:
    return len(cells) == len(_QUESTION_HEADERS) and all(
        len(cell.strip(":")) >= 3 and set(cell) <= {"-", ":"} for cell in cells
    )


def _validate_questions(source_path: Path, questions: list[BenchmarkQuestion]) -> None:
    expected_count = sum(_EXPECTED_PREFIX_COUNTS.values())
    if len(questions) != expected_count:
        raise ValueError(
            f"{source_path} 평가 질의는 {expected_count}건이어야 하지만 {len(questions)}건입니다."
        )

    test_ids = [question.test_id for question in questions]
    duplicate_ids = sorted({test_id for test_id in test_ids if test_ids.count(test_id) > 1})
    if duplicate_ids:
        raise ValueError(f"{source_path} test_id가 중복되었습니다: {', '.join(duplicate_ids)}")

    for prefix, expected_prefix_count in _EXPECTED_PREFIX_COUNTS.items():
        prefix_count = sum(test_id.startswith(f"{prefix}-") for test_id in test_ids)
        if prefix_count != expected_prefix_count:
            raise ValueError(
                f"{source_path} {prefix} 질의는 {expected_prefix_count}건이어야 하지만 "
                f"{prefix_count}건입니다."
            )
