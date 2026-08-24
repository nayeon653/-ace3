"""HyperCLOVA X 모델 동작과 연결 설정."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatClovaXConfig(BaseModel):
    """Git에서 버전 관리하는 ChatClovaX 동작 설정."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    model: str = Field(min_length=1)
    max_tokens: int = Field(ge=1024)
    temperature: float = Field(ge=0, le=1)
    timeout_seconds: float = Field(gt=0)
    max_retries: int = Field(ge=0)
    thinking_effort: Literal["none", "low", "mid", "high"] | None = None


class ClovaEmbeddingConfig(BaseModel):
    """Git에서 버전 관리하는 CLOVA Studio 임베딩 설정."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    model: str = Field(min_length=1)
    dimensions: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0)
    max_retries: int = Field(ge=0)


class ClovaStudioConnection(BaseSettings):
    """환경에서 주입하는 CLOVA Studio 인증·연결 설정."""

    model_config = SettingsConfigDict(
        env_prefix="CLOVASTUDIO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        str_strip_whitespace=True,
    )

    api_key: SecretStr | None = Field(default=None, repr=False)
    api_base_url: str = ""


# 역할별 모델 선택과 생성 설정은 코드 리뷰와 Git 이력에서 함께 관리한다.
MAIN_SUPERVISOR_HCX_CONFIG = ChatClovaXConfig(
    model="HCX-007",
    max_tokens=1024,
    temperature=0.1,
    timeout_seconds=30.0,
    max_retries=2,
    thinking_effort="none",
)

PRODUCT_REACT_HCX_CONFIG = ChatClovaXConfig(
    model="HCX-007",
    max_tokens=1024,
    temperature=0.1,
    timeout_seconds=30.0,
    max_retries=2,
    thinking_effort="none",
)

DEFAULT_DOMAIN_AGENT_HCX_CONFIG = ChatClovaXConfig(
    model="HCX-005",
    max_tokens=1024,
    temperature=0.1,
    timeout_seconds=30.0,
    max_retries=2,
)

BGE_M3_EMBEDDING_CONFIG = ClovaEmbeddingConfig(
    model="bge-m3",
    dimensions=1024,
    timeout_seconds=30.0,
    max_retries=2,
)

BGE_M3_INDEXING_CONFIG = ClovaEmbeddingConfig(
    model="bge-m3",
    dimensions=1024,
    timeout_seconds=90.0,
    max_retries=5,
)
