"""doc55 헤딩 계층 규칙 기반 복원을 검증한다."""

import pytest

from pension_agent.ingest.heading_recovery import recover_doc55_heading_hierarchy

_SAMPLE = """퇴직연금 사무담당자 업무 매뉴얼

Ⅰ. 퇴직연금 부담금 납입 업무

**1. 부담금 종류**

가. 제도별 부담금 납입 프로세스

1) DB 부담금 납입 프로세스

① 미래에셋증권 업무담당자 혹은 관리직원에게 미리 이메일 등의 방법으로 입금예정일자와

**나. 확정급여형(DB) 가입자 명부**

다. 확정기여형(DC) 가입자 명부
"""


def test_roman_numeral_becomes_level1_heading() -> None:
    result = recover_doc55_heading_hierarchy(_SAMPLE)

    assert "# Ⅰ. 퇴직연금 부담금 납입 업무" in result.splitlines()


def test_bold_numbered_title_becomes_level2_heading() -> None:
    result = recover_doc55_heading_hierarchy(_SAMPLE)

    assert "## 1. 부담금 종류" in result.splitlines()


def test_plain_korean_letter_becomes_level3_heading() -> None:
    result = recover_doc55_heading_hierarchy(_SAMPLE)

    lines = result.splitlines()
    assert "### 가. 제도별 부담금 납입 프로세스" in lines
    assert "### 다. 확정기여형(DC) 가입자 명부" in lines


def test_bold_exception_line_becomes_level3_not_level2() -> None:
    result = recover_doc55_heading_hierarchy(_SAMPLE)

    lines = result.splitlines()
    assert "### 나. 확정급여형(DB) 가입자 명부" in lines
    assert "**나. 확정급여형(DB) 가입자 명부**" not in lines


def test_numbered_and_circled_items_stay_as_body_text() -> None:
    result = recover_doc55_heading_hierarchy(_SAMPLE)

    lines = result.splitlines()
    assert "1) DB 부담금 납입 프로세스" in lines
    assert any(line.startswith("① ") for line in lines)


def test_rejects_non_doc55_input() -> None:
    with pytest.raises(ValueError, match="doc55"):
        recover_doc55_heading_hierarchy("다른 문서 제목\n\n1. 아무 내용\n")
