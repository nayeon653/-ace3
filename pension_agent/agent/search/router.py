"""검색 요청 형태를 bounded 실행 계획으로 변환하는 규칙 Router."""

from dataclasses import dataclass

from pension_agent.agent.search.schemas import SearchPlan, SearchRequest
from pension_agent.config import SearchServiceConfig
from pension_agent.core import DocumentType


@dataclass(frozen=True, slots=True)
class SearchRouter:
    """LLM 호출 없이 하나의 최초 검색 경로만 선택한다."""

    config: SearchServiceConfig

    def route(
        self,
        request: SearchRequest,
        *,
        document_types: frozenset[DocumentType],
    ) -> SearchPlan:
        """신뢰 가능한 요청 힌트를 우선하고 일반 요청은 Hybrid 전체 검색으로 보낸다."""

        if request.chunk_id is not None:
            return SearchPlan(
                route="chunk_lookup",
                chunk_id=request.chunk_id,
                document_types=document_types,
                candidate_limit=self.config.candidate_limit,
                expand_neighbors=request.expand_neighbors,
                neighbor_before=self.config.neighbor_before,
                neighbor_after=self.config.neighbor_after,
            )
        if request.source_file_name is not None:
            return SearchPlan(
                route="within_document",
                query=request.objective,
                mode=self.config.default_search_mode,
                source_file_name=request.source_file_name,
                document_types=document_types,
                candidate_limit=self.config.candidate_limit,
                expand_neighbors=request.expand_neighbors,
                neighbor_before=self.config.neighbor_before,
                neighbor_after=self.config.neighbor_after,
            )
        return SearchPlan(
            route="global",
            query=request.objective,
            mode=self.config.default_search_mode,
            document_types=document_types,
            candidate_limit=self.config.candidate_limit,
            expand_neighbors=request.expand_neighbors,
            neighbor_before=self.config.neighbor_before,
            neighbor_after=self.config.neighbor_after,
        )
