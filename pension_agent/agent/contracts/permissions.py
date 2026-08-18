"""Domain Agent의 검색 권한 계약."""

from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pension_agent.core import DocumentType


class Permission(StrEnum):
    """Search Agent에 전달하는 Domain Agent 식별자."""

    POLICY = "policy"
    TAX_PAYOUT = "tax_payout"
    PRODUCT = "product"


_DOCUMENT_TYPES_BY_PERMISSION: Final = MappingProxyType(
    {
        Permission.POLICY: frozenset({DocumentType.PENSION_REFERENCE}),
        Permission.TAX_PAYOUT: frozenset({DocumentType.PENSION_REFERENCE}),
        Permission.PRODUCT: frozenset({DocumentType.FUND_PROSPECTUS}),
    }
)


def document_types_for_permission(permission: Permission) -> frozenset[DocumentType]:
    """Domain permission에 허용된 문서 유형을 반환한다."""

    return _DOCUMENT_TYPES_BY_PERMISSION[permission]


def validate_permission(permission: object) -> Permission:
    """외부 상태의 permission을 검증해 도메인 enum으로 반환한다."""

    if permission is None:
        raise ValueError("검색 문서 접근 권한이 필요합니다.")
    if not isinstance(permission, str):
        raise TypeError("검색 문서 접근 권한이 올바르지 않습니다.")
    try:
        return Permission(permission)
    except ValueError:
        raise ValueError("검색 문서 접근 권한이 올바르지 않습니다.") from None
