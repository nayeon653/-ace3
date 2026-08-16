"""NormalizedDocument -> Chunk 정책을 검증한다."""

import hashlib

from pension_agent.core.documents import NormalizedBlock, NormalizedDocument
from pension_agent.retrieval.chunker import chunk_document

_METADATA = {"filename": "x", "ocr_profile": "docling-local-ocr-v1", "pages": 1}


def _doc(doc_id: str, doc_type: str, blocks: list[NormalizedBlock]) -> NormalizedDocument:
    return NormalizedDocument(doc_id=doc_id, doc_type=doc_type, metadata=_METADATA, blocks=blocks)


def test_heading_defines_section_path_and_merges_text_into_one_chunk() -> None:
    doc = _doc(
        "docA",
        "pdf",
        [
            NormalizedBlock(type="heading", text="제1장", level=1, page=1),
            NormalizedBlock(type="text", text="본문 첫 문단", page=1),
            NormalizedBlock(type="text", text="본문 두번째 문단", page=2),
        ],
    )

    chunks = chunk_document(doc)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.section_path == ["제1장"]
    assert chunk.text == "본문 첫 문단\n본문 두번째 문단"
    assert chunk.page_start == 1
    assert chunk.page_end == 2
    assert chunk.metadata["block_type"] == "text"


def test_long_section_splits_at_block_boundary_not_mid_block() -> None:
    long_block_text = ("예외 조건 나열 " * 200).strip()  # 단일 block인데 매우 길다
    doc = _doc(
        "docB",
        "pdf",
        [
            NormalizedBlock(type="heading", text="섹션", level=1),
            NormalizedBlock(type="text", text=long_block_text),
            NormalizedBlock(type="text", text="다음 문단"),
        ],
    )

    chunks = chunk_document(doc)

    assert len(chunks) == 2
    assert chunks[0].text == long_block_text  # 하나의 block은 절대 중간에서 안 잘린다
    assert chunks[1].text == "다음 문단"
    assert chunks[0].section_path == chunks[1].section_path == ["섹션"]


def test_table_block_is_independent_chunk_with_section_context() -> None:
    doc = _doc(
        "docC",
        "pdf",
        [
            NormalizedBlock(type="heading", text="표 섹션", level=1),
            NormalizedBlock(type="table", table_data=[["a", "b"], ["1", "2"]], page=3),
        ],
    )

    chunks = chunk_document(doc)

    assert len(chunks) == 1
    assert chunks[0].metadata["block_type"] == "table"
    assert chunks[0].section_path == ["표 섹션"]
    assert chunks[0].text.startswith("표 섹션")
    assert "a | b" in chunks[0].text
    assert chunks[0].page_start == chunks[0].page_end == 3


def test_faq_block_becomes_one_chunk_per_row() -> None:
    doc = _doc(
        "doc29",
        "xlsx",
        [
            NormalizedBlock(
                type="faq",
                table_data=[
                    ["질문", "답변"],
                    ["A인가요?", "네."],
                    ["B인가요?", "아니오."],
                ],
                page=1,
            )
        ],
    )

    chunks = chunk_document(doc)

    assert len(chunks) == 2
    assert chunks[0].metadata["block_type"] == "faq"
    assert chunks[0].text == "질문: A인가요?\n답변: 네."
    assert chunks[1].text == "질문: B인가요?\n답변: 아니오."


def test_faq_document_excludes_sibling_text_and_table_chunks_and_maps_only_cited_sources() -> None:
    doc = _doc(
        "doc29",
        "xlsx",
        [
            NormalizedBlock(type="text", text="시트 안내"),
            NormalizedBlock(
                type="table",
                table_data=[
                    ["SourceID", "설명", "URL"],
                    ["S1", "고용노동부 FAQ", "https://example.com/s1"],
                    ["S2", "근로자퇴직급여 보장법", "https://example.com/s2"],
                ],
            ),
            NormalizedBlock(
                type="faq",
                table_data=[
                    ["질문", "답변", "근거ID"],
                    ["A인가요?", "네.", "S1,S2"],
                    ["B인가요?", "아니오.", "S9"],  # 매핑 안 되는 ID는 무시
                ],
                page=1,
            ),
        ],
    )

    chunks = chunk_document(doc)

    assert len(chunks) == 2  # README 텍스트/Sources 표는 vector chunk로 안 나온다
    assert all(c.metadata["block_type"] == "faq" for c in chunks)
    assert chunks[0].metadata["sources"] == {
        "S1": {"설명": "고용노동부 FAQ", "URL": "https://example.com/s1"},
        "S2": {"설명": "근로자퇴직급여 보장법", "URL": "https://example.com/s2"},
    }
    assert "sources" not in chunks[1].metadata  # S9는 Sources 표에 없어 매핑되지 않는다


def test_doc7_returns_empty_pending_manual_normalization() -> None:
    doc = _doc("doc7", "pdf", [NormalizedBlock(type="text", text="본문")])

    assert chunk_document(doc) == []


def test_heading_level_is_trusted_as_is_regardless_of_text_shape() -> None:
    """normalize.py가 이미 계산해 보낸 block.level을 그대로 쓴다 — chunker는

    text를 정규식으로 재해석하지 않으므로, "제 2 부"(공백 있음)와 "제2부"(공백
    없음), "가."와 "가 ."(마침표 앞 공백) 둘 다 level만 맞으면 동일하게 heading
    으로 취급돼야 한다(예전엔 공백 없는 형태를 "표지 재인용"으로 오판해 강등시켰다).
    """

    doc = _doc(
        "prospectusA",
        "pdf",
        [
            NormalizedBlock(type="heading", text="제 2 부. 집합투자기구에 관한 사항", level=1),
            NormalizedBlock(type="text", text="본문1"),
        ],
    )
    chunks = chunk_document(doc)
    assert chunks[0].section_path == ["제 2 부. 집합투자기구에 관한 사항"]

    doc2 = _doc(
        "prospectusB",
        "pdf",
        [
            NormalizedBlock(
                type="heading", text="제2부. 집합투자기구에 관한 사항", level=1
            ),  # 공백 없음
            NormalizedBlock(type="text", text="본문1"),
        ],
    )
    chunks2 = chunk_document(doc2)
    assert chunks2[0].section_path == ["제2부. 집합투자기구에 관한 사항"]  # 더 이상 강등되지 않는다

    doc3 = _doc(
        "prospectusC",
        "pdf",
        [
            NormalizedBlock(type="heading", text="가. 일반위험", level=3),
            NormalizedBlock(type="text", text="본문1"),
        ],
    )
    chunks3 = chunk_document(doc3)
    assert chunks3[0].section_path == ["가. 일반위험"]

    doc4 = _doc(
        "prospectusD",
        "pdf",
        [
            NormalizedBlock(type="heading", text="나 . 특수위험", level=3),  # 마침표 앞 공백
            NormalizedBlock(type="text", text="본문1"),
        ],
    )
    chunks4 = chunk_document(doc4)
    assert chunks4[0].section_path == ["나 . 특수위험"]


def test_heading_stack_transitions_level1_to_level2_to_level3() -> None:
    doc = _doc(
        "prospectusE",
        "pdf",
        [
            NormalizedBlock(type="heading", text="제 2 부", level=1),
            NormalizedBlock(type="heading", text="9. 투자전략", level=2),
            NormalizedBlock(type="heading", text="가. 일반위험", level=3),
            NormalizedBlock(type="text", text="본문"),
        ],
    )

    chunks = chunk_document(doc)

    assert chunks[0].section_path == ["제 2 부", "9. 투자전략", "가. 일반위험"]


def test_heading_stack_sibling_level3_replaces_previous_level3() -> None:
    doc = _doc(
        "prospectusF",
        "pdf",
        [
            NormalizedBlock(type="heading", text="제 2 부", level=1),
            NormalizedBlock(type="heading", text="9. 투자전략", level=2),
            NormalizedBlock(type="heading", text="가. 일반위험", level=3),
            NormalizedBlock(type="text", text="일반위험 본문"),
            NormalizedBlock(type="heading", text="나. 특수위험", level=3),
            NormalizedBlock(type="text", text="특수위험 본문"),
        ],
    )

    chunks = chunk_document(doc)

    assert [c.section_path for c in chunks] == [
        ["제 2 부", "9. 투자전략", "가. 일반위험"],
        ["제 2 부", "9. 투자전략", "나. 특수위험"],
    ]


def test_heading_stack_new_level2_pops_previous_level3_and_level2() -> None:
    doc = _doc(
        "prospectusG",
        "pdf",
        [
            NormalizedBlock(type="heading", text="제 2 부", level=1),
            NormalizedBlock(type="heading", text="9. 투자전략", level=2),
            NormalizedBlock(type="heading", text="가. 일반위험", level=3),
            NormalizedBlock(type="text", text="일반위험 본문"),
            NormalizedBlock(type="heading", text="10. 투자위험", level=2),
            NormalizedBlock(type="text", text="투자위험 본문"),
        ],
    )

    chunks = chunk_document(doc)

    assert [c.section_path for c in chunks] == [
        ["제 2 부", "9. 투자전략", "가. 일반위험"],
        ["제 2 부", "10. 투자위험"],
    ]


def test_heading_stack_new_level1_pops_everything() -> None:
    doc = _doc(
        "prospectusH",
        "pdf",
        [
            NormalizedBlock(type="heading", text="제 2 부", level=1),
            NormalizedBlock(type="heading", text="9. 투자전략", level=2),
            NormalizedBlock(type="heading", text="가. 일반위험", level=3),
            NormalizedBlock(type="text", text="본문"),
            NormalizedBlock(type="heading", text="제 3 부", level=1),
            NormalizedBlock(type="text", text="새 부 본문"),
        ],
    )

    chunks = chunk_document(doc)

    assert [c.section_path for c in chunks] == [
        ["제 2 부", "9. 투자전략", "가. 일반위험"],
        ["제 3 부"],
    ]


def test_heading_then_table_inherits_full_3level_section_path() -> None:
    doc = _doc(
        "prospectusI",
        "pdf",
        [
            NormalizedBlock(type="heading", text="제 2 부", level=1),
            NormalizedBlock(type="heading", text="9. 투자전략", level=2),
            NormalizedBlock(type="heading", text="가. 일반위험", level=3),
            NormalizedBlock(
                type="table", table_data=[["구분", "위험"], ["원금손실", "있음"]], page=5
            ),
        ],
    )

    chunks = chunk_document(doc)

    assert len(chunks) == 1
    assert chunks[0].metadata["block_type"] == "table"
    assert chunks[0].section_path == ["제 2 부", "9. 투자전략", "가. 일반위험"]


def test_heading_only_and_empty_sections_produce_no_chunk() -> None:
    doc = _doc(
        "docD",
        "pdf",
        [
            NormalizedBlock(type="heading", text="빈 섹션", level=1),
            NormalizedBlock(type="heading", text="또 다른 섹션", level=1),
        ],
    )

    assert chunk_document(doc) == []


def test_doc34_excluded_from_vector_chunks() -> None:
    doc = _doc("doc34", "pdf", [NormalizedBlock(type="text", text="본문")])

    assert chunk_document(doc) == []


def test_doc55_allows_page_none_and_uses_section_path() -> None:
    doc = _doc(
        "doc55",
        "docx",
        [
            NormalizedBlock(type="heading", text="Ⅰ. 부담금", level=1, page=None),
            NormalizedBlock(type="text", text="본문", page=None),
        ],
    )

    chunks = chunk_document(doc)

    assert len(chunks) == 1
    assert chunks[0].page_start is None
    assert chunks[0].page_end is None
    assert chunks[0].section_path == ["Ⅰ. 부담금"]


def test_chunk_id_and_content_hash_are_deterministic() -> None:
    def build() -> NormalizedDocument:
        return _doc(
            "docE",
            "pdf",
            [
                NormalizedBlock(type="heading", text="섹션", level=1),
                NormalizedBlock(type="text", text="본문"),
            ],
        )

    chunks_1 = chunk_document(build())
    chunks_2 = chunk_document(build())

    assert [c.chunk_id for c in chunks_1] == [c.chunk_id for c in chunks_2]
    assert [c.content_hash for c in chunks_1] == [c.content_hash for c in chunks_2]
    assert chunks_1[0].content_hash == hashlib.sha256(chunks_1[0].text.encode("utf-8")).hexdigest()
