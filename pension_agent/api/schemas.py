"""평가 API가 외부에 노출하는 HTTP 응답 스키마."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceChunkResponse(BaseModel):
    """최종 답변에 실제 사용된 하나의 문서 근거."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(description="근거 문서 청크의 고유 식별자")
    source_file_name: str = Field(description="근거가 포함된 원본 문서 파일명")
    title: str = Field(description="근거 구간의 제목")
    locator: str = Field(description="원문에서 근거 위치를 찾기 위한 표시")
    content: str = Field(description="최종 답변에 실제 사용한 근거 본문")


class AnswerResponse(BaseModel):
    """주최측 평가용 GET /answer 성공 응답."""

    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(description="요청받은 질의 고유 ID를 변경하지 않고 반환")
    question: str = Field(description="요청받은 자연어 질문 원문")
    retrieved_context: str = Field(
        description="최종 답변에 실제 사용한 근거 문서의 메타데이터와 본문을 연결한 문자열"
    )
    think_trace: str = Field(description="도메인 호출·판단·누락 조건을 요약한 안전한 실행 기록")
    answer: str = Field(description="Agent가 생성한 최종 자연어 답변")


class HealthResponse(BaseModel):
    """외부 의존성을 호출하지 않는 서버 생존 응답."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = Field(description="API 서버의 생존 상태")
    commit_sha: str = Field(description="현재 배포 버전을 식별하는 Git 커밋 SHA")


class ErrorResponse(BaseModel):
    """내부 정보를 제외한 공통 오류 응답."""

    model_config = ConfigDict(extra="forbid")

    detail: str = Field(description="내부 정보를 제외한 정제된 오류 설명")
