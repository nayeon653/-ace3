"""원문의 상품 표현과 카탈로그 후보의 대응을 결정론적으로 검사한다."""

from __future__ import annotations

import re
import unicodedata

from pension_agent.retrieval import ProductCatalog, ProductCatalogEntry, ProductCatalogError

_DURATION_PATTERN = re.compile(r"초단기|중단기|중장기|단기|장기")
_NUMBER_PATTERN = re.compile(r"\d+")
_CODE_PATTERN = re.compile(r"kr[a-z0-9]{10}\Z")
_GENERIC_TERMS = (
    "증권전환형자투자신탁",
    "증권자투자신탁",
    "증권투자신탁",
    "투자신탁",
    "자산운용",
    "국공채",
    "퇴직연금",
    "연금",
    "펀드",
    "채권혼합",
    "주식혼합",
    "채권",
    "주식",
    "증권",
    "투자",
    "위험",
    "비용",
    "수수료",
    "환매",
    "호",
)


def _normalize(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).casefold()
        if character.isalnum()
    )


def _occurs_in_question(part: str, question: str) -> bool:
    folded_question = question.casefold()
    folded_part = part.casefold()
    normalized_question = _normalize(question)
    for occurrence in re.finditer(re.escape(folded_part), folded_question):
        start = len(_normalize(folded_question[: occurrence.start()]))
        end = start + len(_normalize(folded_part))
        if all(
            identifier.end() <= start
            or identifier.start() >= end
            or (start <= identifier.start() and identifier.end() <= end)
            for pattern in (_DURATION_PATTERN, _NUMBER_PATTERN)
            for identifier in pattern.finditer(normalized_question)
        ):
            return True
    return False


def _matches_name(part: str, name: str) -> bool:
    normalized_part = _normalize(part)
    normalized_name = _normalize(name)
    if not normalized_part:
        return False
    if not set(_DURATION_PATTERN.findall(normalized_part)).issubset(
        _DURATION_PATTERN.findall(normalized_name)
    ):
        return False
    if not set(_NUMBER_PATTERN.findall(normalized_part)).issubset(
        _NUMBER_PATTERN.findall(normalized_name)
    ):
        return False
    if normalized_part in normalized_name:
        return True
    # 공통 이름과 기간 수식어의 순서가 다른 경우에도 같은 이름 안에서만 대조한다.
    words = [_normalize(word) for word in re.findall(r"\w+", part)]
    return len(words) > 1 and all(word and word in normalized_name for word in words)


def _has_distinguishing_name(parts: list[str], catalog: ProductCatalog) -> bool:
    remaining = _normalize(" ".join(parts))
    common_terms = set(_GENERIC_TERMS) | {product.provider for product in catalog.products}
    for term in sorted((_normalize(term) for term in common_terms), key=len, reverse=True):
        remaining = remaining.replace(term, "")
    remaining = _DURATION_PATTERN.sub("", remaining)
    remaining = _NUMBER_PATTERN.sub("", remaining)
    return len(remaining) >= 2


def resolve_mention_candidates(
    *,
    catalog: ProductCatalog,
    mention_parts: list[str],
    question: str,
) -> tuple[ProductCatalogEntry, ...]:
    """원문에 실제 등장하는 구별 표현을 모두 만족하는 후보만 반환한다."""

    if any(not _occurs_in_question(part, question) for part in mention_parts):
        raise ProductCatalogError("상품 식별 표현이 질문 원문에 없습니다.")
    code_parts = {
        normalized.upper()
        for part in mention_parts
        if _CODE_PATTERN.fullmatch(normalized := _normalize(part))
    }
    name_parts = [part for part in mention_parts if not _CODE_PATTERN.fullmatch(_normalize(part))]
    if not code_parts and not _has_distinguishing_name(name_parts, catalog):
        return ()
    return tuple(
        product
        for product in catalog.products
        if (not code_parts or code_parts == {product.product_code})
        and any(
            all(_matches_name(part, name) for part in name_parts)
            for name in (product.official_name, *product.aliases)
        )
    )
