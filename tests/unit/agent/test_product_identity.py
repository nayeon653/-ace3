"""원문 조각으로 후보를 검증할 때 기간·번호·공통 표현이 섞이지 않는지 확인한다."""

import pytest

from pension_agent.agent.product.product_identity import resolve_mention_candidates
from pension_agent.retrieval import ProductCatalog, ProductCatalogError, load_product_catalog


@pytest.mark.parametrize(
    "duration,expected_code",
    [
        ("단기", "KR5153420063"),
        ("초단기", "KR5153450658"),
        ("중장기", "KR5153420079"),
        ("장기", "KR5153420105"),
    ],
)
def test_duration_matches_complete_modifier_only(duration: str, expected_code: str) -> None:
    candidates = resolve_mention_candidates(
        catalog=load_product_catalog(),
        mention_parts=["솔로몬", "국공채", duration],
        question=f"솔로몬 국공채 {duration}의 위험은?",
    )

    assert [candidate.product_code for candidate in candidates] == [expected_code]


@pytest.mark.parametrize("question", ["솔로몬 중장기", "솔로몬 중 장기"])
def test_mention_cannot_cut_longer_duration_even_with_spaces(question: str) -> None:
    with pytest.raises(ProductCatalogError, match="질문 원문"):
        resolve_mention_candidates(
            catalog=load_product_catalog(),
            mention_parts=["솔로몬", "장기"],
            question=question,
        )


def test_spacing_and_punctuation_normalization_preserve_raw_mention() -> None:
    candidates = resolve_mention_candidates(
        catalog=load_product_catalog(),
        mention_parts=["솔 로 몬", "국공채", "중·장·기"],
        question="솔 로 몬 국공채 중·장·기가 궁금해",
    )

    assert [candidate.product_code for candidate in candidates] == ["KR5153420079"]


def test_generic_provider_and_product_type_do_not_select_a_product() -> None:
    assert not resolve_mention_candidates(
        catalog=load_product_catalog(),
        mention_parts=["미래에셋", "단기", "국공채"],
        question="미래에셋 단기 국공채 위험은?",
    )


def _numbered_catalog() -> ProductCatalog:
    return ProductCatalog.from_payloads(
        {
            "products": [
                {
                    "product_code": code,
                    "official_name": f"테스트운용 새별투자 {number}호",
                    "provider": "테스트운용",
                    "aliases": [f"새별 {number}호"],
                }
                for code, number in [("KR0000000001", 1), ("KR0000000011", 11)]
            ]
        },
        {"aliases": {}},
    )


def test_number_is_not_a_substring_of_a_different_fund_number() -> None:
    candidates = resolve_mention_candidates(
        catalog=_numbered_catalog(),
        mention_parts=["새별", "1호"],
        question="새별 1호를 알려줘",
    )

    assert [candidate.product_code for candidate in candidates] == ["KR0000000001"]


def test_mention_cannot_cut_a_longer_number_in_the_question() -> None:
    with pytest.raises(ProductCatalogError, match="질문 원문"):
        resolve_mention_candidates(
            catalog=_numbered_catalog(),
            mention_parts=["새별", "1호"],
            question="새별 11호를 알려줘",
        )


def test_known_code_does_not_override_a_contradictory_name() -> None:
    assert not resolve_mention_candidates(
        catalog=load_product_catalog(),
        mention_parts=["KR5153420022", "솔로몬", "단기"],
        question="KR5153420022 솔로몬 단기",
    )
