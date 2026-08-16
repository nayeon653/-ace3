"""DoclingDocument JSON -> NormalizedDocument 변환을 검증한다."""

import json
from pathlib import Path

from pension_agent.ingest.normalize import normalize_document

_MANIFEST = {
    "source": {"filename": "doc99.pdf", "extension": ".pdf"},
    "profile": {"id": "docling-local-ocr-v1"},
    "stats": {"pages": 3},
}


def _write_bundle(
    bundle_dir: Path, raw: dict, manifest: dict | None = None, markdown: str = ""
) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "document.docling.json").write_text(json.dumps(raw), encoding="utf-8")
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest or _MANIFEST), encoding="utf-8")
    (bundle_dir / "document.md").write_text(markdown, encoding="utf-8")


def test_generic_document_extracts_heading_text_table_with_page(tmp_path: Path) -> None:
    raw = {
        "body": {
            "children": [{"$ref": "#/texts/0"}, {"$ref": "#/texts/1"}, {"$ref": "#/tables/0"}]
        },
        "texts": [
            {"label": "section_header", "level": 2, "text": "제목", "prov": [{"page_no": 3}]},
            {"label": "text", "text": "본문", "prov": [{"page_no": 3}]},
        ],
        "tables": [
            {
                "data": {
                    "num_rows": 2,
                    "num_cols": 2,
                    "table_cells": [
                        {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "a"},
                        {"start_row_offset_idx": 0, "start_col_offset_idx": 1, "text": "b"},
                        {"start_row_offset_idx": 1, "start_col_offset_idx": 0, "text": "c"},
                        {"start_row_offset_idx": 1, "start_col_offset_idx": 1, "text": "d"},
                    ],
                },
                "prov": [{"page_no": 4}],
            }
        ],
        "groups": [],
    }
    _write_bundle(tmp_path, raw)

    doc = normalize_document(tmp_path)

    assert doc.doc_id == "doc99"
    assert doc.doc_type == "pdf"
    assert doc.metadata == {
        "filename": "doc99.pdf",
        "ocr_profile": "docling-local-ocr-v1",
        "pages": 3,
    }
    assert [b.type for b in doc.blocks] == ["heading", "text", "table"]
    assert doc.blocks[0].level == 2
    assert doc.blocks[0].page == 3
    assert doc.blocks[2].table_data == [["a", "b"], ["c", "d"]]
    assert doc.blocks[2].page == 4


def test_furniture_labels_are_dropped(tmp_path: Path) -> None:
    raw = {
        "body": {"children": [{"$ref": "#/texts/0"}, {"$ref": "#/texts/1"}]},
        "texts": [
            {"label": "page_header", "text": "무시", "prov": [{"page_no": 1}]},
            {"label": "text", "text": "본문", "prov": [{"page_no": 1}]},
        ],
        "tables": [],
        "groups": [],
    }
    _write_bundle(tmp_path, raw)

    doc = normalize_document(tmp_path)

    assert [b.type for b in doc.blocks] == ["text"]


def test_xlsx_sheet_group_marks_faq_vs_table(tmp_path: Path) -> None:
    raw = {
        "body": {"children": [{"$ref": "#/groups/0"}, {"$ref": "#/groups/1"}]},
        "texts": [],
        "tables": [
            {
                "data": {
                    "num_rows": 1,
                    "num_cols": 1,
                    "table_cells": [
                        {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "q&a"}
                    ],
                }
            },
            {
                "data": {
                    "num_rows": 1,
                    "num_cols": 1,
                    "table_cells": [
                        {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "readme"}
                    ],
                }
            },
        ],
        "groups": [
            {"label": "sheet", "name": "FAQ_100", "children": [{"$ref": "#/tables/0"}]},
            {"label": "sheet", "name": "README", "children": [{"$ref": "#/tables/1"}]},
        ],
    }
    manifest = {**_MANIFEST, "source": {"filename": "doc29.xlsx", "extension": ".xlsx"}}
    _write_bundle(tmp_path, raw, manifest=manifest)

    doc = normalize_document(tmp_path)

    assert [b.type for b in doc.blocks] == ["faq", "table"]


def test_picture_children_text_is_walked_into_blocks(tmp_path: Path) -> None:
    raw = {
        "body": {"children": [{"$ref": "#/texts/0"}, {"$ref": "#/pictures/0"}]},
        "texts": [
            {"label": "text", "text": "본문1", "prov": [{"page_no": 1}]},
            {
                "label": "section_header",
                "level": 1,
                "text": "그림 안 헤딩",
                "prov": [{"page_no": 2}],
            },
        ],
        "tables": [],
        "groups": [],
        "pictures": [
            {"label": "picture", "children": [{"$ref": "#/texts/1"}]},
        ],
    }
    _write_bundle(tmp_path, raw)

    doc = normalize_document(tmp_path)

    assert [b.type for b in doc.blocks] == ["text", "heading"]
    assert doc.blocks[1].text == "그림 안 헤딩"
    assert doc.blocks[1].page == 2


def test_walk_does_not_duplicate_node_reachable_via_two_paths(tmp_path: Path) -> None:
    raw = {
        "body": {"children": [{"$ref": "#/pictures/0"}, {"$ref": "#/groups/0"}]},
        "texts": [{"label": "text", "text": "공유 텍스트", "prov": [{"page_no": 1}]}],
        "tables": [],
        "groups": [{"label": "list", "children": [{"$ref": "#/texts/0"}]}],
        "pictures": [{"label": "picture", "children": [{"$ref": "#/texts/0"}]}],
    }
    _write_bundle(tmp_path, raw)

    doc = normalize_document(tmp_path)

    assert [b.text for b in doc.blocks] == ["공유 텍스트"]


def test_walk_tolerates_cyclic_picture_group_reference(tmp_path: Path) -> None:
    raw = {
        "body": {"children": [{"$ref": "#/pictures/0"}]},
        "texts": [{"label": "text", "text": "본문", "prov": [{"page_no": 1}]}],
        "tables": [],
        "groups": [
            {"label": "list", "children": [{"$ref": "#/pictures/0"}, {"$ref": "#/texts/0"}]}
        ],
        "pictures": [{"label": "picture", "children": [{"$ref": "#/groups/0"}]}],
    }
    _write_bundle(tmp_path, raw)

    doc = normalize_document(tmp_path)

    assert [b.text for b in doc.blocks] == ["본문"]


def _text(
    idx: int,
    label: str,
    text: str,
    page: int | None = None,
    marker: str | None = None,
    orig: str | None = None,
) -> dict:
    item = {
        "label": label,
        "text": text,
        "self_ref": f"#/texts/{idx}",
        "prov": [{"page_no": page}] if page else [],
    }
    if marker is not None:
        item["marker"] = marker
        item["enumerated"] = True
    if orig is not None:
        item["orig"] = orig
    return item


def test_prospectus_recovers_part_item_subitem_with_spacing_variation(tmp_path: Path) -> None:
    texts = [
        _text(0, "section_header", "제 1 부. 모집 또는 매출에 관한 사항", page=1),
        _text(1, "section_header", "1. 집합투자기구의 명칭", page=1),
        _text(2, "text", "본문1", page=1),
        _text(3, "section_header", "제2부. 집합투자기구에 관한 사항", page=5),
        _text(4, "section_header", "9. 투자전략", page=5),
        _text(5, "section_header", "가. 일반위험", page=5),
        _text(6, "text", "일반위험 본문", page=5),
        _text(7, "section_header", "나 . 특수위험", page=6),  # 마침표 앞 공백 변형
        _text(8, "text", "특수위험 본문", page=6),
    ]
    raw = {
        "body": {"children": [{"$ref": f"#/texts/{i}"} for i in range(len(texts))]},
        "texts": texts,
        "tables": [],
        "groups": [],
    }
    _write_bundle(tmp_path, raw)

    doc = normalize_document(tmp_path)

    headings = [(b.level, b.text) for b in doc.blocks if b.type == "heading"]
    assert headings == [
        (1, "제 1 부. 모집 또는 매출에 관한 사항"),
        (2, "1. 집합투자기구의 명칭"),
        (1, "제2부. 집합투자기구에 관한 사항"),
        (2, "9. 투자전략"),
        (3, "가. 일반위험"),
        (3, "나 . 특수위험"),
    ]


def test_prospectus_selects_real_part_over_cover_echo_by_monotonic_order(tmp_path: Path) -> None:
    texts = [
        _text(
            0, "section_header", "제3부. 집합투자기구의 재무 및 운용실적 등에 관한 사항", page=1
        ),  # 표지 echo
        _text(1, "section_header", "제1부. 모집 또는 매출에 관한 사항", page=1),  # 표지 echo
        _text(2, "text", "목차 요약", page=1),
        _text(3, "section_header", "제 1 부. 모집 또는 매출에 관한 사항", page=3),  # 실제 본문
        _text(4, "text", "본문1", page=3),
        _text(
            5, "section_header", "제 3 부. 집합투자기구의 재무 및 운용실적 등에 관한 사항", page=40
        ),  # 실제 본문
        _text(6, "text", "본문2", page=40),
    ]
    raw = {
        "body": {"children": [{"$ref": f"#/texts/{i}"} for i in range(len(texts))]},
        "texts": texts,
        "tables": [],
        "groups": [],
    }
    _write_bundle(tmp_path, raw)

    doc = normalize_document(tmp_path)

    l1 = [b.text for b in doc.blocks if b.type == "heading" and b.level == 1]
    assert l1 == [
        "제 1 부. 모집 또는 매출에 관한 사항",
        "제 3 부. 집합투자기구의 재무 및 운용실적 등에 관한 사항",
    ]
    # 표지 echo 2건은 heading이 아니라 본문 text로 접힌다
    text_values = [b.text for b in doc.blocks if b.type == "text"]
    assert "제3부. 집합투자기구의 재무 및 운용실적 등에 관한 사항" in text_values
    assert "제1부. 모집 또는 매출에 관한 사항" in text_values


def test_prospectus_splits_merged_parent_child_node(tmp_path: Path) -> None:
    texts = [
        _text(0, "section_header", "제 1 부. 모집 또는 매출에 관한 사항", page=1),
        _text(
            1,
            "list_item",
            "집합투자기구의 공시에 관한 사항 가. 정기 보고서",
            page=2,
            marker="3.",
            orig="3. 집합투자기구의 공시에 관한 사항 가. 정기 보고서",
        ),
    ]
    raw = {
        "body": {"children": [{"$ref": f"#/texts/{i}"} for i in range(len(texts))]},
        "texts": texts,
        "tables": [],
        "groups": [],
    }
    _write_bundle(tmp_path, raw)

    doc = normalize_document(tmp_path)

    headings = [(b.level, b.text) for b in doc.blocks if b.type == "heading"]
    assert headings == [
        (1, "제 1 부. 모집 또는 매출에 관한 사항"),
        (2, "3. 집합투자기구의 공시에 관한 사항"),
        (3, "가. 정기 보고서"),
    ]


def test_prospectus_recovers_list_item_number_from_marker_and_orig(tmp_path: Path) -> None:
    texts = [
        _text(0, "section_header", "제 2 부. 집합투자기구에 관한 사항", page=1),
        _text(
            1,
            "list_item",
            "집합투자기구의 투자위험",
            page=5,
            marker="10.",
            orig="10. 집합투자기구의 투자위험",
        ),
        _text(2, "text", "투자위험 본문", page=5),
    ]
    raw = {
        "body": {"children": [{"$ref": f"#/texts/{i}"} for i in range(len(texts))]},
        "texts": texts,
        "tables": [],
        "groups": [],
    }
    _write_bundle(tmp_path, raw)

    doc = normalize_document(tmp_path)

    headings = [(b.level, b.text) for b in doc.blocks if b.type == "heading"]
    assert headings == [
        (1, "제 2 부. 집합투자기구에 관한 사항"),
        (2, "10. 집합투자기구의 투자위험"),
    ]


def test_prospectus_does_not_promote_numbered_notice_before_real_part1(tmp_path: Path) -> None:
    """제1부 실제 본문 전의 법정 유의사항도 "1.", "13." 같은 번호를 쓴다 — 이걸

    heading으로 승격하면 실제 제1부가 나오기 전까지 이후 내용의 section_path가
    전부 그 안내문으로 오염된다(R2_KR5118420036 실사례). 본문 진입 전에는
    번호가 있어도 text로만 남아야 하고, 내용 자체는 보존돼야 한다.
    """

    texts = [
        _text(
            0, "section_header", "제1부. 모집 또는 매출에 관한 사항", page=1
        ),  # 표지 재인용(echo)
        _text(
            1,
            "list_item",
            "ESG집합투자기구의 경우...",
            page=1,
            marker="13.",
            orig="13. ESG집합투자기구의 경우...",
        ),
        _text(2, "text", "요약정보 본문", page=1),
        _text(3, "section_header", "제 1 부. 모집 또는 매출에 관한 사항", page=2),  # 실제 본문
        _text(4, "section_header", "1. 집합투자기구의 명칭", page=2),
        _text(5, "text", "본문1", page=2),
    ]
    raw = {
        "body": {"children": [{"$ref": f"#/texts/{i}"} for i in range(len(texts))]},
        "texts": texts,
        "tables": [],
        "groups": [],
    }
    _write_bundle(tmp_path, raw)

    doc = normalize_document(tmp_path)

    headings = [(b.level, b.text) for b in doc.blocks if b.type == "heading"]
    assert headings == [
        (1, "제 1 부. 모집 또는 매출에 관한 사항"),
        (2, "1. 집합투자기구의 명칭"),
    ]
    # "13. ESG..."는 heading으로 승격되지 않았지만 내용은 text로 보존된다
    text_values = [b.text for b in doc.blocks if b.type == "text"]
    assert "ESG집합투자기구의 경우..." in text_values
    assert "요약정보 본문" in text_values


def test_non_prospectus_document_keeps_old_label_based_behavior(tmp_path: Path) -> None:
    raw = {
        "body": {"children": [{"$ref": "#/texts/0"}, {"$ref": "#/texts/1"}]},
        "texts": [
            {
                "label": "section_header",
                "level": 2,
                "text": "3. 아무 제목",
                "prov": [{"page_no": 1}],
            },
            {"label": "text", "text": "본문", "prov": [{"page_no": 1}]},
        ],
        "tables": [],
        "groups": [],
    }
    _write_bundle(tmp_path, raw)

    doc = normalize_document(tmp_path)

    # "제N부" 패턴이 전혀 없는 문서는 기존처럼 label만 보고 판단(level은 JSON의 level 필드 그대로)
    assert [b.type for b in doc.blocks] == ["heading", "text"]
    assert doc.blocks[0].level == 2
    assert doc.blocks[0].text == "3. 아무 제목"


def test_doc55_uses_heading_recovery_not_json_level(tmp_path: Path) -> None:
    markdown = (
        "퇴직연금 사무담당자 업무 매뉴얼\n\n"
        "Ⅰ. 부담금 납입 업무\n\n"
        "**1. 부담금 종류**\n\n"
        "가. 제도별 프로세스\n"
    )
    raw = {
        "body": {"children": [{"$ref": "#/texts/0"}]},
        "texts": [{"label": "section_header", "level": 1, "text": "다른 텍스트", "prov": []}],
        "tables": [],
        "groups": [],
    }
    manifest = {**_MANIFEST, "source": {"filename": "doc55.docx", "extension": ".docx"}}
    _write_bundle(tmp_path, raw, manifest=manifest, markdown=markdown)

    doc = normalize_document(tmp_path)

    headings = [(b.level, b.text) for b in doc.blocks if b.type == "heading"]
    assert headings == [
        (1, "Ⅰ. 부담금 납입 업무"),
        (2, "1. 부담금 종류"),
        (3, "가. 제도별 프로세스"),
    ]
    assert "다른 텍스트" not in [b.text for b in doc.blocks]
    # doc55는 원본 JSON에 page provenance가 없다 — None을 허용하고, 대신
    # heading block 시퀀스(section_path)로 위치를 찾는다.
    assert all(b.page is None for b in doc.blocks)
