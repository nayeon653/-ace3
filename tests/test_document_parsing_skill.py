"""문서 파싱 Skill이 중앙 운영 정책만 참조하는지 검증한다."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_RELATIVE_PATH = "docs/operations/document-parsing.md"


def test_canonical_document_parsing_policy_exists() -> None:
    assert (REPO_ROOT / POLICY_RELATIVE_PATH).is_file()
    assert (REPO_ROOT / "tools/docling_parser/scripts/parse_document.py").is_file()


def test_codex_and_claude_skill_entrypoints_match() -> None:
    for skill_name in ("parse-with-local-ocr", "parse-with-naver-ocr"):
        codex_skill = REPO_ROOT / ".agents/skills" / skill_name / "SKILL.md"
        claude_skill = REPO_ROOT / ".claude/skills" / skill_name / "SKILL.md"

        codex_text = codex_skill.read_text(encoding="utf-8")
        assert codex_text == claude_skill.read_text(encoding="utf-8")
        assert POLICY_RELATIVE_PATH in codex_text
        assert "uv run" not in codex_text
