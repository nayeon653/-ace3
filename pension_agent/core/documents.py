"""ingest(정규화)와 retrieval(청킹)이 공유하는 문서 표현.

여기 있어야 하는 이유: 모듈 의존성 방향(PROJECT_RULES.md)상 retrieval은 ingest를
import할 수 없다. NormalizedDocument는 ingest가 만들고 retrieval이 소비하므로,
둘 다 import 가능한 core에 둔다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NormalizedBlock:
    type: str  # "heading" | "text" | "table" | "faq"
    text: str | None = None
    level: int | None = None
    page: int | None = None
    table_data: list[list[str]] | None = None


@dataclass
class NormalizedDocument:
    doc_id: str
    doc_type: str
    metadata: dict
    blocks: list[NormalizedBlock]
