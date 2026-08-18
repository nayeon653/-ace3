"""Qdrant 런타임 연결 설정."""

from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class QdrantConnection(BaseSettings):
    """환경에서 주입하는 Qdrant 인증·연결 설정."""

    model_config = SettingsConfigDict(
        env_prefix="QDRANT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        str_strip_whitespace=True,
        env_ignore_empty=True,
    )

    url: str = "http://127.0.0.1:6333"
    api_key: SecretStr | None = Field(default=None, repr=False)
    collection: str = Field(default="pension_documents_v1", min_length=1)
    timeout_seconds: int = Field(default=30, gt=0)
    prefetch_limit: int = Field(default=30, ge=1, le=100)
    cloud_inference: bool | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """HTTP(S) endpoint만 허용하고 마지막 슬래시를 제거한다."""

        normalized = value.rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("QDRANT_URL은 유효한 HTTP(S) 주소여야 합니다.")
        return normalized

    @property
    def cloud_inference_enabled(self) -> bool:
        """명시값이 없으면 Qdrant Cloud hostname에서 자동 판정한다."""

        if self.cloud_inference is not None:
            return self.cloud_inference
        hostname = urlparse(self.url).hostname or ""
        return hostname.endswith(".cloud.qdrant.io")
