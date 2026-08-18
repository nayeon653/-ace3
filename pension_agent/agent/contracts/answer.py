"""Main Supervisor의 최종 답변 계약."""

from pydantic import BaseModel, ConfigDict


class AgentAnswer(BaseModel):
    """Main LLM이 생성하는 최종 자연어 답변."""

    model_config = ConfigDict(extra="forbid")

    answer: str
