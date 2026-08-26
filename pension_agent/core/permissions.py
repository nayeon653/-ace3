"""Domain Agent가 결정론적 서비스에 전달하는 권한 계약."""

from enum import StrEnum


class Permission(StrEnum):
    """신뢰된 호출 경계에서 주입하는 Domain Agent 권한."""

    POLICY = "policy"
    TAX_PAYOUT = "tax_payout"
    PRODUCT = "product"
