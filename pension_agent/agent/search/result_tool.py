"""HCX 선택을 검증된 SearchResult로 변환하는 최종 제출 Tool."""

from typing import Annotated

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool
from langgraph.types import Command
from pydantic import Field

from pension_agent.agent.contracts import document_types_for_permission, validate_permission
from pension_agent.agent.execution import ExecutionContext
from pension_agent.agent.search.ports import ChunkRetriever
from pension_agent.agent.search.schemas import (
    SearchChunkPayload,
    SearchCoverage,
    SearchResult,
    SearchSelection,
    SearchToolErrorPayload,
)
from pension_agent.agent.search.state import SearchAgentState
from pension_agent.core import DocumentType, RetrievalError, RetrievedChunk

SUBMIT_SEARCH_RESULT_TOOL_NAME = "submit_search_result"


def create_search_result_tool(*, retriever: ChunkRetriever) -> BaseTool:
    """관찰한 후보 ID만 원본 재조회해 SearchResult로 제출하는 Tool을 만든다."""

    @tool(
        SUBMIT_SEARCH_RESULT_TOOL_NAME,
        description=(
            "최종 검색 결과 제출 Tool. 충족도, 실제로 관찰한 후보 chunk_id, "
            "검색 한계만 제출하며 본문과 메타데이터는 제출하지 않는다."
        ),
    )
    async def submit_search_result(
        coverage: Annotated[
            SearchCoverage,
            Field(description="근거 충족도: sufficient, partial, none 중 하나"),
        ],
        selected_chunk_ids: Annotated[
            list[str],
            Field(description="최종 근거로 선택한 관찰 후보 chunk_id 목록"),
        ],
        limitations: Annotated[
            list[str],
            Field(description="확인하지 못한 범위와 검색 한계"),
        ],
        runtime: ToolRuntime[ExecutionContext, SearchAgentState],
    ) -> Command | str:
        try:
            selection = SearchSelection(
                coverage=coverage,
                selected_chunk_ids=selected_chunk_ids,
                limitations=limitations,
            )
        except (TypeError, ValueError):
            return _error_payload("최종 검색 결과 제출 인자가 올바르지 않습니다.")

        state = runtime.state
        if not state.get("search_attempted", False):
            return _error_payload("검색 Tool을 성공적으로 호출한 후 결과를 제출해야 합니다.")

        observed_ids = {chunk.chunk_id for chunk in state.get("observed_chunks", [])}
        if any(chunk_id not in observed_ids for chunk_id in selection.selected_chunk_ids):
            return _error_payload("검색 Tool에서 관찰하지 않은 chunk_id를 선택할 수 없습니다.")

        try:
            permission = validate_permission(state.get("permission"))
            selected_chunks = [
                await _reload_chunk(
                    retriever,
                    chunk_id,
                    document_types=document_types_for_permission(permission),
                )
                for chunk_id in selection.selected_chunk_ids
            ]
        except RetrievalError:
            return _completed_command(
                runtime,
                SearchResult(
                    execution_status="failed",
                    error="선택한 검색 근거를 다시 확인하지 못했습니다.",
                ),
            )
        except Exception:  # noqa: BLE001
            return _completed_command(
                runtime,
                SearchResult(
                    execution_status="failed",
                    error="선택한 검색 근거를 처리하지 못했습니다.",
                ),
            )

        result = SearchResult(
            execution_status="completed",
            coverage=selection.coverage,
            selected_chunks=selected_chunks,
            limitations=selection.limitations,
        )
        return _completed_command(runtime, result)

    return submit_search_result


async def _reload_chunk(
    retriever: ChunkRetriever,
    chunk_id: str,
    *,
    document_types: frozenset[DocumentType],
) -> SearchChunkPayload:
    chunk = await retriever.get_chunk(chunk_id, document_types=document_types)
    if chunk is None or chunk.chunk_id != chunk_id:
        raise RetrievalError("선택한 청크를 원본에서 확인할 수 없습니다.")
    return _chunk_payload(chunk)


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


def _completed_command(
    runtime: ToolRuntime[ExecutionContext, SearchAgentState],
    result: SearchResult,
) -> Command:
    if runtime.tool_call_id is None:
        raise ValueError("최종 검색 결과 제출 Tool 호출 ID가 없습니다.")
    return Command(
        update={
            "search_result": result,
            "messages": [
                ToolMessage(
                    content=result.model_dump_json(),
                    tool_call_id=runtime.tool_call_id,
                    name=SUBMIT_SEARCH_RESULT_TOOL_NAME,
                )
            ],
        }
    )


def _error_payload(message: str) -> str:
    return SearchToolErrorPayload(error=message).model_dump_json()
