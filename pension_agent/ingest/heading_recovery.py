"""doc55(퇴직연금 사무담당자 업무 매뉴얼) Docling 출력의 헤딩 계층을 규칙 기반으로 복원한다.

Docling 로컬 OCR 결과는 원본의 Ⅰ~Ⅳ / N. / 가·나·다 번호 체계를 마크다운 헤딩(#)이 아닌
평문·굵은 글씨로만 남긴다. 이 모듈은 doc55.docx 파싱 산출물에서 확인된 이 3단계 번호
패턴만 헤딩으로 되돌린다. N)과 ①②③은 본문 나열과 소제목이 뒤섞여 있어 대상에서 뺀다.
다른 문서에는 적용하지 않는다 — 원본 Docling bundle도 직접 수정하지 않는다.
"""

from __future__ import annotations

import re

_DOC55_TITLE = "퇴직연금 사무담당자 업무 매뉴얼"

_LEVEL1_ROMAN = re.compile(r"^[ⅠⅡⅢⅣ]\. .+$")
_LEVEL2_BOLD_NUMBER = re.compile(r"^\*\*\d+\. .+\*\*$")
_LEVEL3_KOREAN = re.compile(r"^[가나다라마]\. .+$")

# doc55.docx에서 유일하게 레벨3 항목이 레벨2와 같은 굵은 글씨로 렌더링된 예외.
_LEVEL3_BOLD_EXCEPTION = "**나. 확정급여형(DB) 가입자 명부**"


def recover_doc55_heading_hierarchy(markdown: str) -> str:
    """doc55 document.md 텍스트에 Ⅰ~Ⅳ/N./가나다 헤딩 레벨을 붙여 새 텍스트로 반환한다."""

    if not markdown.lstrip().startswith(_DOC55_TITLE):
        raise ValueError("doc55.docx 파싱 결과가 아닌 문서에는 적용할 수 없다")

    lines: list[str] = []
    for line in markdown.splitlines():
        if line == _LEVEL3_BOLD_EXCEPTION:
            lines.append(f"### {line.strip('*')}")
        elif _LEVEL1_ROMAN.match(line):
            lines.append(f"# {line}")
        elif _LEVEL2_BOLD_NUMBER.match(line):
            lines.append(f"## {line.strip('*')}")
        elif _LEVEL3_KOREAN.match(line):
            lines.append(f"### {line}")
        else:
            lines.append(line)
    return "\n".join(lines)
