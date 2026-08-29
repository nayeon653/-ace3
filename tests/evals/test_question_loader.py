"""버전 관리되는 평가 질의셋의 로딩 계약을 검증한다."""

from pathlib import Path

from evals.harness import BenchmarkQuestion, load_hantoo_questions

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_QUESTION_PATH = _PROJECT_ROOT / "evals" / "questions" / "hantoo_selected_30.md"


def test_hantoo_questions_load_as_thirty_unique_records() -> None:
    questions = load_hantoo_questions()

    assert len(questions) == 30
    assert all(isinstance(question, BenchmarkQuestion) for question in questions)
    assert len({question.test_id for question in questions}) == 30
    assert sum(question.test_id.startswith("PROD-") for question in questions) == 15
    assert sum(question.test_id.startswith("POLICY-") for question in questions) == 15
    assert all(question.adapted_question for question in questions)


def test_hantoo_questions_have_one_canonical_markdown_source() -> None:
    question_files = sorted(_QUESTION_PATH.parent.glob("hantoo_selected_30*.md"))
    legacy_question_files = sorted((_PROJECT_ROOT / "tests").rglob("hantoo_selected_30*.md"))
    markdown = _QUESTION_PATH.read_text(encoding="utf-8")

    assert question_files == [_QUESTION_PATH]
    assert legacy_question_files == []
    assert markdown.startswith("# 미래에셋 연금 Agent 벤치마크")
    assert "\n| test_id | source_id |" in markdown
    assert r"\| test\_id" not in markdown
