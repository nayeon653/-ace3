"""한투 30문항 Gold Answer의 저장소 내 구조를 검증한다."""

from pathlib import Path

from evals.harness.render_gold_markdown import render_gold_markdown
from evals.harness.validate_gold import validate_gold_dataset

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_PATH = _REPO_ROOT / "evals/gold/hantoo_selected_30.manifest.json"
_DATASET_PATH = _REPO_ROOT / "evals/gold/hantoo_selected_30.jsonl"
_MARKDOWN_PATH = _REPO_ROOT / "evals/gold/hantoo_selected_30.table.md"


def test_hantoo_gold_dataset_structure() -> None:
    """CI에서는 원문 전달물 없이 질문·레지스트리·정답셋 구조를 검증한다."""

    summary = validate_gold_dataset(
        repo_root=_REPO_ROOT,
        manifest_path=_MANIFEST_PATH,
        dataset_path=_DATASET_PATH,
        verify_corpus=False,
    )

    assert summary.questions == 30
    assert summary.evidence == 78
    assert summary.retrieval_links == 0
    assert summary.answerability == {
        "partial": 14,
        "supported": 9,
        "temporal_gap": 1,
        "unsupported": 6,
    }


def test_hantoo_gold_markdown_is_current() -> None:
    """사람용 Markdown 표가 정규 Gold JSONL과 정확히 일치한다."""

    rendered = render_gold_markdown(
        repo_root=_REPO_ROOT,
        manifest_path=_MANIFEST_PATH,
        dataset_path=_DATASET_PATH,
    )

    assert _MARKDOWN_PATH.read_text(encoding="utf-8") == rendered
    assert rendered.count("\n| PROD-") == 15
    assert rendered.count("\n| POLICY-") == 15
    assert "문서 내 정확한 근거 위치" in rendered
