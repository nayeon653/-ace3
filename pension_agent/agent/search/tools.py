"""Search Agent가 사용하는 결정론적 검색 Tool."""

from collections.abc import Callable
from typing import Annotated

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from pension_agent.agent.contracts import Permission, document_types_for_permission
from pension_agent.agent.search.ports import ChunkRetriever, QueryEmbedder
from pension_agent.agent.search.schemas import (
    GetChunkPayload,
    NeighborChunksPayload,
    SearchChunkPayload,
    SearchHitPayload,
    SearchHitsPayload,
    SearchToolErrorPayload,
)
from pension_agent.agent.search.state import SearchAgentState
from pension_agent.config import DEFAULT_SEARCH_AGENT_CONFIG, SearchAgentConfig
from pension_agent.core import (
    DocumentType,
    NeighborRequest,
    RetrievalError,
    RetrievedChunk,
    SearchFilters,
    SearchHit,
    SearchMode,
    SearchQuery,
)

_MAX_RESULT_LIMIT = 100


class QueryEmbeddingError(RuntimeError):
    """검색문 dense embedding을 안전하게 생성하지 못한 경우."""


class SearchToolInputError(ValueError):
    """모델이 만든 검색 Tool 인자가 공개 입력 계약을 위반한 경우."""


class SearchPermissionError(PermissionError):
    """Search Agent의 문서 접근 권한이 없거나 위반된 경우."""


class _SearchOperations:
    """Search Tool의 결정론적 실행부."""

    def __init__(self, *, embedder: QueryEmbedder, retriever: ChunkRetriever) -> None:
        self._embedder = embedder
        self._retriever = retriever

    def search_chunks(
        self,
        text: str,
        *,
        document_types: frozenset[DocumentType],
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 10,
    ) -> list[SearchHit]:
        _validate_limit(limit)
        hits = self._retriever.search_chunks(
            self._build_query(text, mode=mode),
            filters=SearchFilters(document_types=document_types),
            limit=limit,
        )
        _validate_authorized_hits(hits, document_types=document_types)
        return hits

    def search_within_document(
        self,
        text: str,
        *,
        source_file_name: str,
        document_types: frozenset[DocumentType],
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 10,
    ) -> list[SearchHit]:
        _validate_limit(limit)
        source_file_name = source_file_name.strip()
        if not source_file_name:
            raise SearchToolInputError("원본 파일명 필터는 비어 있을 수 없습니다.")
        hits = self._retriever.search_within_document(
            self._build_query(text, mode=mode),
            source_file_name=source_file_name,
            document_types=document_types,
            limit=limit,
        )
        _validate_authorized_hits(hits, document_types=document_types)
        return hits

    def get_neighbor_chunks(
        self,
        request: NeighborRequest,
        *,
        document_types: frozenset[DocumentType],
    ) -> list[RetrievedChunk]:
        chunks = self._retriever.get_neighbor_chunks(
            request,
            document_types=document_types,
        )
        _validate_authorized_chunks(chunks, document_types=document_types)
        return chunks

    def get_chunk(
        self,
        chunk_id: str,
        *,
        document_types: frozenset[DocumentType],
    ) -> RetrievedChunk | None:
        chunk = self._retriever.get_chunk(chunk_id, document_types=document_types)
        if chunk is not None:
            _validate_authorized_chunks([chunk], document_types=document_types)
        return chunk

    def _build_query(self, text: str, *, mode: SearchMode) -> SearchQuery:
        normalized_text = text.strip()
        if not normalized_text:
            raise SearchToolInputError("검색문은 비어 있을 수 없습니다.")
        if mode is SearchMode.SPARSE:
            return SearchQuery(text=normalized_text, mode=mode)

        provider_failed = False
        try:
            raw_dense = self._embedder.embed_query(normalized_text)
        # 외부 임베딩 구현마다 예외 계층이 달라 Provider 경계에서 한 번에 정제한다.
        except Exception:  # noqa: BLE001
            provider_failed = True
        if provider_failed:
            raise QueryEmbeddingError("검색문 임베딩 생성에 실패했습니다.")

        invalid_result = False
        try:
            query = SearchQuery(text=normalized_text, dense=tuple(raw_dense), mode=mode)
        # 지연 평가되는 Provider 반환값의 순회·변환 예외도 원문을 노출하지 않는다.
        except Exception:  # noqa: BLE001
            invalid_result = True
        if invalid_result:
            raise QueryEmbeddingError("검색문 임베딩 결과가 올바르지 않습니다.")
        return query


def create_search_tools(
    *,
    embedder: QueryEmbedder,
    retriever: ChunkRetriever,
    config: SearchAgentConfig = DEFAULT_SEARCH_AGENT_CONFIG,
    permission: Permission | None = None,
) -> tuple[BaseTool, ...]:
    """Search Agent가 선택해서 호출할 검색 Tool을 만든다."""

    operations = _SearchOperations(embedder=embedder, retriever=retriever)

    @tool("search_chunks", description="전체 제공 문서에서 검색어와 관련된 근거 청크를 찾는다.")
    def search_chunks(
        text: Annotated[str, Field(min_length=1, description="근거를 찾을 검색어")],
        mode: Annotated[
            SearchMode,
            Field(description="dense, sparse, hybrid 중 사용할 검색 방식"),
        ] = config.default_search_mode,
        document_type: Annotated[
            DocumentType | None,
            Field(description="검색 범위를 제한할 문서 유형"),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=_MAX_RESULT_LIMIT, strict=True, description="반환할 청크 수"),
        ] = config.default_result_limit,
        runtime: ToolRuntime[None, SearchAgentState] = None,  # type: ignore[assignment]
    ) -> str:
        def operation() -> SearchHitsPayload:
            resolved_permission = _resolve_permission(runtime, fallback=permission)
            document_types = _resolve_document_types(
                resolved_permission,
                requested=document_type,
            )
            return SearchHitsPayload(
                hits=[
                    _search_hit_payload(hit)
                    for hit in operations.search_chunks(
                        text,
                        document_types=document_types,
                        mode=mode,
                        limit=limit,
                    )
                ]
            )

        return _tool_payload(operation)

    @tool(
        "search_within_document",
        description="지정한 원본 문서 하나에서 검색어와 관련된 근거 청크를 찾는다.",
    )
    def search_within_document(
        text: Annotated[str, Field(min_length=1, description="근거를 찾을 검색어")],
        source_file_name: Annotated[
            str,
            Field(min_length=1, description="검색 범위를 제한할 원본 파일명"),
        ],
        mode: Annotated[
            SearchMode,
            Field(description="dense, sparse, hybrid 중 사용할 검색 방식"),
        ] = config.default_search_mode,
        limit: Annotated[
            int,
            Field(ge=1, le=_MAX_RESULT_LIMIT, strict=True, description="반환할 청크 수"),
        ] = config.default_result_limit,
        runtime: ToolRuntime[None, SearchAgentState] = None,  # type: ignore[assignment]
    ) -> str:
        def operation() -> SearchHitsPayload:
            resolved_permission = _resolve_permission(runtime, fallback=permission)
            document_types = document_types_for_permission(resolved_permission)
            return SearchHitsPayload(
                hits=[
                    _search_hit_payload(hit)
                    for hit in operations.search_within_document(
                        text,
                        source_file_name=source_file_name,
                        document_types=document_types,
                        mode=mode,
                        limit=limit,
                    )
                ]
            )

        return _tool_payload(operation)

    @tool(
        "get_neighbor_chunks",
        description="선택한 근거 청크와 같은 문서에서 앞뒤 문맥을 문서 순서로 조회한다.",
    )
    def get_neighbor_chunks(
        source_file_name: Annotated[str, Field(min_length=1, description="원본 파일명")],
        chunk_index: Annotated[int, Field(ge=0, strict=True, description="기준 청크 순서")],
        before: Annotated[
            int,
            Field(
                ge=0,
                le=99,
                strict=True,
                description="앞쪽 청크 수. before + after + 1은 100 이하여야 한다.",
            ),
        ] = config.default_neighbor_before,
        after: Annotated[
            int,
            Field(
                ge=0,
                le=99,
                strict=True,
                description="뒤쪽 청크 수. before + after + 1은 100 이하여야 한다.",
            ),
        ] = config.default_neighbor_after,
        runtime: ToolRuntime[None, SearchAgentState] = None,  # type: ignore[assignment]
    ) -> str:
        def operation() -> NeighborChunksPayload:
            resolved_permission = _resolve_permission(runtime, fallback=permission)
            invalid_request = False
            try:
                request = NeighborRequest(
                    source_file_name=source_file_name,
                    chunk_index=chunk_index,
                    before=before,
                    after=after,
                )
            except (TypeError, ValueError):
                invalid_request = True
            if invalid_request:
                raise SearchToolInputError("인접 청크 조회 범위가 올바르지 않습니다.")
            return NeighborChunksPayload(
                chunks=[
                    _chunk_payload(chunk)
                    for chunk in operations.get_neighbor_chunks(
                        request,
                        document_types=document_types_for_permission(resolved_permission),
                    )
                ]
            )

        return _tool_payload(operation)

    @tool("get_chunk", description="이미 알고 있는 UUID 청크 ID로 근거 하나를 다시 조회한다.")
    def get_chunk(
        chunk_id: Annotated[str, Field(min_length=1, description="조회할 UUID 청크 ID")],
        runtime: ToolRuntime[None, SearchAgentState] = None,  # type: ignore[assignment]
    ) -> str:
        def operation() -> GetChunkPayload:
            resolved_permission = _resolve_permission(runtime, fallback=permission)
            chunk = operations.get_chunk(
                chunk_id,
                document_types=document_types_for_permission(resolved_permission),
            )
            return GetChunkPayload(chunk=_chunk_payload(chunk) if chunk is not None else None)

        return _tool_payload(operation)

    return search_chunks, search_within_document, get_neighbor_chunks, get_chunk


def _tool_payload(operation: Callable[[], BaseModel]) -> str:
    unexpected_failure = False
    try:
        payload = operation()
    except (
        QueryEmbeddingError,
        RetrievalError,
        SearchPermissionError,
        SearchToolInputError,
    ) as exc:
        error = str(exc).strip() or "검색 Tool 실행에 실패했습니다."
        return SearchToolErrorPayload(error=error).model_dump_json()
    # 구현이 다른 Retriever의 원시 예외는 Search Agent의 ToolMessage에 노출하지 않는다.
    except Exception:  # noqa: BLE001
        unexpected_failure = True
    if unexpected_failure:
        return SearchToolErrorPayload(error="검색 Tool 실행에 실패했습니다.").model_dump_json()

    serialization_failed = False
    try:
        return payload.model_dump_json()
    # Tool 경계 밖으로 직렬화 대상이나 Provider의 원시 예외를 노출하지 않는다.
    except Exception:  # noqa: BLE001
        serialization_failed = True
    if serialization_failed:
        return SearchToolErrorPayload(
            error="검색 Tool 결과를 처리하지 못했습니다."
        ).model_dump_json()
    raise AssertionError("도달할 수 없는 검색 Tool 상태입니다.")


def _search_hit_payload(hit: SearchHit) -> SearchHitPayload:
    return SearchHitPayload(score=hit.score, chunk=_chunk_payload(hit.chunk))


def _chunk_payload(chunk: RetrievedChunk) -> SearchChunkPayload:
    return SearchChunkPayload(
        chunk_id=chunk.chunk_id,
        source_file_name=chunk.source_file_name,
        document_type=chunk.document_type,
        chunk_index=chunk.chunk_index,
        title=chunk.title,
        locator=chunk.locator,
        content=chunk.content,
    )


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not 1 <= limit <= _MAX_RESULT_LIMIT:
        raise SearchToolInputError(f"검색 결과 수는 1~{_MAX_RESULT_LIMIT} 사이여야 합니다.")


def _resolve_permission(
    runtime: ToolRuntime[None, SearchAgentState] | None,
    *,
    fallback: Permission | None,
) -> Permission:
    raw_permission = fallback if runtime is None else runtime.state.get("permission")
    if raw_permission is None:
        raise SearchPermissionError("검색 문서 접근 권한이 필요합니다.")
    try:
        return Permission(raw_permission)
    except (TypeError, ValueError):
        raise SearchPermissionError("검색 문서 접근 권한이 올바르지 않습니다.") from None


def _resolve_document_types(
    permission: Permission,
    *,
    requested: DocumentType | None,
) -> frozenset[DocumentType]:
    allowed = document_types_for_permission(permission)
    if requested is None:
        return allowed
    if requested not in allowed:
        raise SearchPermissionError("허용되지 않은 문서 유형입니다.")
    return frozenset({requested})


def _validate_authorized_hits(
    hits: list[SearchHit],
    *,
    document_types: frozenset[DocumentType],
) -> None:
    _validate_authorized_chunks(
        [hit.chunk for hit in hits],
        document_types=document_types,
    )


def _validate_authorized_chunks(
    chunks: list[RetrievedChunk],
    *,
    document_types: frozenset[DocumentType],
) -> None:
    if any(chunk.document_type not in document_types for chunk in chunks):
        raise SearchPermissionError("검색 결과가 문서 접근 권한을 위반했습니다.")
