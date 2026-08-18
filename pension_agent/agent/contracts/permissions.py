"""Agent가 사용할 수 있는 데이터와 기능의 접근 권한 계약."""

from pydantic import BaseModel, ConfigDict, Field

from pension_agent.core import DocumentType


class AgentPermissions(BaseModel):
    """Agent 실행 중 변경할 수 없는 문서 접근 권한."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    readable_document_types: frozenset[DocumentType] = Field(min_length=1)
