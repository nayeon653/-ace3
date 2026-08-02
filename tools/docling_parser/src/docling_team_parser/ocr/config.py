"""Shared validation for NAVER OCR runtime configuration."""

from __future__ import annotations

import re

import httpx

_NAVER_APIGW_HOST = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.apigw\.ntruss\.com",
    re.IGNORECASE | re.ASCII,
)


def validate_naver_invoke_url(value: str) -> str:
    """Return a validated General OCR Invoke URL or raise a safe error."""

    invoke_url = value.strip()
    try:
        parsed_url = httpx.URL(invoke_url)
    except (TypeError, ValueError, httpx.InvalidURL):
        raise ValueError("NAVER_OCR_INVOKE_URL is invalid") from None
    if parsed_url.scheme != "https" or not parsed_url.host:
        raise ValueError("NAVER_OCR_INVOKE_URL must be an absolute HTTPS URL")
    if parsed_url.userinfo:
        raise ValueError("NAVER_OCR_INVOKE_URL must not include user information")
    if parsed_url.port is not None:
        raise ValueError("NAVER_OCR_INVOKE_URL must use the default HTTPS port")
    if _NAVER_APIGW_HOST.fullmatch(parsed_url.host) is None:
        raise ValueError(
            "NAVER_OCR_INVOKE_URL host must be a direct subdomain of apigw.ntruss.com"
        )
    if "?" in invoke_url or "#" in invoke_url:
        raise ValueError("NAVER_OCR_INVOKE_URL must not include a query or fragment")
    if not parsed_url.path.endswith("/general"):
        raise ValueError("NAVER_OCR_INVOKE_URL path must end with /general")
    return invoke_url


__all__ = ["validate_naver_invoke_url"]
