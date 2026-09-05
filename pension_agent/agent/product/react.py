"""Product 도메인의 ReAct 구현."""

from __future__ import annotations

import json
import operator
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Annotated, Any, NotRequired, Protocol, cast
from uuid import UUID

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelCallResult,
    ModelRequest,
    ModelResponse,
    ToolCallLimitMiddleware,
    hook_config,
)
from langchain.messages import AIMessage, HumanMessage, ToolCall, ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Command
from pydantic import Field, ValidationError

from pension_agent.agent.calculation import (
    calculation_evidence_chunk_ids,
    create_fund_deferred_sales_fee_tool,
    create_fund_frontend_sales_fee_tool,
    create_fund_redemption_fee_tool,
    create_fund_reported_var_risk_tool,
    create_fund_standard_price_tool,
    create_fund_var_risk_tool,
    format_calculation_summary,
)
from pension_agent.agent.contracts import (
    CalculationResult,
    ComparisonCriterion,
    ComparisonTarget,
    DecisionStatus,
    DomainRequest,
    DomainResult,
    EvidenceChunk,
    Permission,
    validate_domain_result,
)
from pension_agent.agent.domain_runner import failed_domain_result
from pension_agent.agent.execution import ExecutionContext, ModelConcurrencyMiddleware
from pension_agent.agent.product.comparison import (
    ComparisonEvidenceResult,
    ProductComparisonService,
)
from pension_agent.agent.product.comparison_answer import HCXProductComparisonAnswerWriter
from pension_agent.agent.product.comparison_submission import (
    unresolved_comparison_result,
)
from pension_agent.agent.search import SearchRequest, SearchResult, SearchRunner
from pension_agent.config import DomainAgentConfig
from pension_agent.config.product_comparison import MAX_PRODUCT_COMPARISON_CRITERIA

SEARCH_DOCUMENTS_TOOL_NAME = "search_documents"
COMPARE_PRODUCTS_TOOL_NAME = "compare_products"
SUBMIT_DOMAIN_RESULT_TOOL_NAME = "submit_domain_result"
_NOT_APPLICABLE_CONCLUSION = "이 질문에는 해당 도메인 판단이 적용되지 않습니다."
_NO_EVIDENCE_CONCLUSION = "제공 문서에서 관련 근거를 확인하지 못해 판단할 수 없습니다."
_VAR_QUESTION_PATTERN = re.compile(r"(?:VaR|최대손실예상액|위험등급)", re.IGNORECASE)
_CLASS_PATTERN = re.compile(
    r"(?:클래스|class)\s*([A-Z](?:-[A-Za-z]+)?)|([A-Z](?:-[A-Za-z]+)?)\s*(?:클래스|class)",
    re.IGNORECASE,
)
_TARGET_FUND_MISSING_CONDITION = "대상 펀드 확인 필요"
_FUND_CLASS_MISSING_CONDITION = "펀드 클래스 확인 필요"
_LATEST_DISCLOSURE_MISSING_CONDITION = "최신 공시 기준일 확인 필요"
_ANNUALIZED_VAR_MISSING_CONDITION = "연환산 VaR 확인 필요"
ProductCodeResolver = Callable[[str], str]


class ProductAgentState(AgentState):
    """Product ReAct의 카탈로그·검색·결과 상태."""

    question: NotRequired[str]
    objective: NotRequired[str]
    product_candidate_codes: NotRequired[list[str]]
    product_scoped_search_completed: NotRequired[bool]
    product_scoped_source_file_name: NotRequired[str]
    product_catalog_result: NotRequired[DomainResult]
    search_result: NotRequired[SearchResult]
    comparison_targets: NotRequired[list[ComparisonTarget]]
    comparison_criteria: NotRequired[list[ComparisonCriterion]]
    comparison_catalog_version: NotRequired[str]
    comparison_evidence: NotRequired[ComparisonEvidenceResult]
    calculations: NotRequired[Annotated[list[CalculationResult], operator.add]]
    domain_result: NotRequired[DomainResult]


class ProductGraph(Protocol):
    """Domain Agent 실행기가 사용하는 최소 Graph 계약."""

    async def ainvoke(
        self,
        input: dict[str, Any],
        /,
        *,
        context: ExecutionContext,
    ) -> Mapping[str, Any]:
        """초기 상태로 Domain Agent를 실행한다."""


class CompleteProductResult(AgentMiddleware[Any, Any, Any]):
    """완성된 DomainResult가 있으면 추가 모델 호출 없이 종료한다."""

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("domain_result") is None:
            return None
        return {"jump_to": "end"}

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


class RequireProductTool(AgentMiddleware[Any, Any, Any]):
    """Product 결과가 제출될 때까지 단계에 맞는 Tool 호출을 강제한다."""

    def __init__(
        self,
        *,
        max_search_calls: int,
        calculation_tool_names: tuple[str, ...],
    ) -> None:
        self._max_search_calls = max_search_calls
        self._calculation_tool_names = calculation_tool_names

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("domain_result") is not None:
            return None
        last_message = state.get("messages", [])[-1]
        if isinstance(last_message, AIMessage) and not last_message.tool_calls:
            instruction = _product_next_tool_instruction(
                state,
                max_search_calls=self._max_search_calls,
                calculation_tool_names=self._calculation_tool_names,
            )
            return {
                "jump_to": "model",
                "messages": [
                    HumanMessage(content=f"자유 형식 답변은 사용하지 않습니다. {instruction}")
                ],
            }
        return None

    @hook_config(can_jump_to=["model"])
    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


class ProductComparisonToolAvailabilityMiddleware(AgentMiddleware[Any, Any, Any]):
    """복수 상품 비교에서만 필요한 Tool schema와 명시적 Tool 선택을 적용한다."""

    def __init__(self, *, lookup_tool_name: str, max_search_calls: int) -> None:
        self._lookup_tool_name = lookup_tool_name
        self._max_search_calls = max_search_calls

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelCallResult[Any]:
        state = request.state or {}
        if not state.get("comparison_targets"):
            return await handler(request)
        allowed_names = set(
            _allowed_product_tools(
                state,
                lookup_tool_name=self._lookup_tool_name,
                max_search_calls=self._max_search_calls,
                calculation_tool_names=(),
            )
        )
        selected_names = allowed_names | _product_historical_tool_names(request.messages)
        available_tools = list(request.tools or [])
        available_names = [_product_model_tool_name(model_tool) for model_tool in available_tools]
        if any(name is None for name in available_names) or any(
            available_names.count(name) != 1 for name in selected_names
        ):
            raise RuntimeError("Product 비교 상태별 Tool 구성이 올바르지 않습니다.")
        selected_tools = [
            model_tool
            for model_tool, name in zip(available_tools, available_names, strict=True)
            if name in selected_names
        ]
        return await handler(
            request.override(tools=selected_tools, tool_choice=COMPARE_PRODUCTS_TOOL_NAME)
        )


def _product_model_tool_name(model_tool: Any) -> str | None:
    """LangChain·provider 형식의 Tool에서 이름을 읽는다."""

    name = getattr(model_tool, "name", None)
    if isinstance(name, str):
        return name
    if not isinstance(model_tool, Mapping):
        return None
    name = model_tool.get("name")
    if isinstance(name, str):
        return name
    function = model_tool.get("function")
    if not isinstance(function, Mapping):
        return None
    name = function.get("name")
    return name if isinstance(name, str) else None


def _product_historical_tool_names(messages: list[Any]) -> set[str]:
    """HCX가 과거 Tool 메시지를 해석하는 데 필요한 schema 이름을 보존한다."""

    names: set[str] = set()
    for message in messages:
        if isinstance(message, AIMessage):
            names.update(call["name"] for call in message.tool_calls)
        elif isinstance(message, ToolMessage) and isinstance(message.name, str):
            names.add(message.name)
    return names


class EnforceProductToolSequence(AgentMiddleware[Any, Any, Any]):
    """Product Agent의 검색 우선·코드 식별·결과 제출 단계를 안전하게 제한한다."""

    def __init__(
        self,
        *,
        lookup_tool_name: str,
        max_search_calls: int,
        calculation_tool_names: tuple[str, ...],
    ) -> None:
        self._lookup_tool_name = lookup_tool_name
        self._max_search_calls = max_search_calls
        self._calculation_tool_names = calculation_tool_names

    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        last_message = state.get("messages", [])[-1]
        if not isinstance(last_message, AIMessage) or state.get("domain_result") is not None:
            return None
        if not last_message.tool_calls:
            return None
        allowed_tools = _allowed_product_tools(
            state,
            lookup_tool_name=self._lookup_tool_name,
            max_search_calls=self._max_search_calls,
            calculation_tool_names=self._calculation_tool_names,
        )
        allowed_calls = [
            call
            for call in last_message.tool_calls
            if _product_tool_call_is_allowed(call, state=state, allowed_tools=allowed_tools)
        ]
        if not allowed_calls:
            return {
                "messages": [last_message.model_copy(update={"tool_calls": []})],
            }
        calculation_calls = [
            call for call in allowed_calls if call["name"] in self._calculation_tool_names
        ]
        kept_call = calculation_calls[0] if calculation_calls else allowed_calls[0]
        if last_message.tool_calls == [kept_call]:
            return None
        return {
            "messages": [last_message.model_copy(update={"tool_calls": [kept_call]})],
        }

    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


class ProductModelCallLimit(ModelCallLimitMiddleware):
    """모델 호출 상한에서 자유 형식 결과 생성 없이 종료한다."""

    def __init__(self, *, max_model_calls: int) -> None:
        super().__init__(run_limit=max_model_calls, exit_behavior="end")
        self._max_model_calls = max_model_calls

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        if state.get("run_model_call_count", 0) < self._max_model_calls:
            return None
        return {
            "jump_to": "end",
            "messages": [AIMessage(content="Product Agent 호출 한도에 도달했습니다.")],
        }

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return self.before_model(state, runtime)


@dataclass(slots=True)
class ProductReactAgent:
    """Product CompiledStateGraph를 공통 Domain 계약으로 노출한다."""

    graph: ProductGraph

    async def __call__(
        self,
        request: DomainRequest,
        *,
        deadline: float | None = None,
    ) -> DomainResult:
        if deadline is None:
            raise ValueError("Product Agent 실행 deadline이 없습니다.")
        state = await self.graph.ainvoke(
            {
                "question": request["question"],
                "objective": request["objective"],
                "calculations": [],
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"질문 원문: {request['question']}\n판단 목표: {request['objective']}"
                        ),
                    }
                ],
            },
            context=ExecutionContext(deadline=deadline),
        )
        result = state.get("domain_result")
        if result is None and state.get("comparison_targets"):
            return unresolved_comparison_result(
                targets=state["comparison_targets"],
                criteria=state["comparison_criteria"],
                catalog_version=state["comparison_catalog_version"],
                limitation="상품 비교 답안 생성을 완료하지 못했습니다.",
            )
        return cast(DomainResult, result)


def create_product_react_agent(
    *,
    model: BaseChatModel,
    search_service: SearchRunner,
    system_prompt: str,
    config: DomainAgentConfig,
    model_concurrency: ModelConcurrencyMiddleware | None,
    product_code_resolver: ProductCodeResolver,
    product_lookup_tool: BaseTool,
    comparison_service: ProductComparisonService,
    comparison_answer_writer: HCXProductComparisonAnswerWriter,
) -> ProductReactAgent:
    """Product 패키지가 소유하는 ReAct graph를 만든다."""

    search_tool = _create_product_search_tool(
        search_service=search_service,
        product_code_resolver=product_code_resolver,
        max_search_calls=config.max_search_calls,
    )
    comparison_tool = _create_compare_products_tool(comparison_service, comparison_answer_writer)
    calculation_tools = (
        create_fund_standard_price_tool(),
        create_fund_reported_var_risk_tool(),
        create_fund_var_risk_tool(),
        create_fund_frontend_sales_fee_tool(),
        create_fund_deferred_sales_fee_tool(),
        create_fund_redemption_fee_tool(),
    )
    calculation_tool_names = tuple(tool.name for tool in calculation_tools)
    result_tool = _create_product_result_tool()
    graph = create_agent(
        model=model,
        tools=(product_lookup_tool, comparison_tool, search_tool, *calculation_tools, result_tool),
        system_prompt=system_prompt,
        state_schema=ProductAgentState,
        context_schema=ExecutionContext,
        middleware=(
            *((model_concurrency,) if model_concurrency is not None else ()),
            CompleteProductResult(),
            ProductComparisonToolAvailabilityMiddleware(
                lookup_tool_name=product_lookup_tool.name,
                max_search_calls=config.max_search_calls,
            ),
            RequireProductTool(
                max_search_calls=config.max_search_calls,
                calculation_tool_names=calculation_tool_names,
            ),
            ProductModelCallLimit(max_model_calls=config.max_model_calls),
            ToolCallLimitMiddleware(
                tool_name=SEARCH_DOCUMENTS_TOOL_NAME,
                run_limit=config.max_search_calls,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=product_lookup_tool.name,
                run_limit=1,
                exit_behavior="continue",
            ),
            ToolCallLimitMiddleware(
                tool_name=COMPARE_PRODUCTS_TOOL_NAME,
                run_limit=1,
                exit_behavior="continue",
            ),
            *(
                ToolCallLimitMiddleware(
                    tool_name=calculation_tool.name,
                    run_limit=1,
                    exit_behavior="continue",
                )
                for calculation_tool in calculation_tools
            ),
            ToolCallLimitMiddleware(
                tool_name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                run_limit=config.max_submit_calls,
                exit_behavior="continue",
            ),
            EnforceProductToolSequence(
                lookup_tool_name=product_lookup_tool.name,
                max_search_calls=config.max_search_calls,
                calculation_tool_names=calculation_tool_names,
            ),
        ),
        name="product_agent",
    )
    return ProductReactAgent(graph=cast(ProductGraph, graph))


def _create_product_search_tool(
    *,
    search_service: SearchRunner,
    product_code_resolver: ProductCodeResolver,
    max_search_calls: int,
) -> Any:
    @tool(
        SEARCH_DOCUMENTS_TOOL_NAME,
        description="상품 문서 전체 또는 검증된 단일 상품에서 제공 문서 근거를 검색한다.",
    )
    async def search_documents(
        objective: Annotated[
            str,
            Field(min_length=1, description="하나의 구체적인 근거 검색 목표"),
        ],
        runtime: ToolRuntime[ExecutionContext, ProductAgentState],
        product_code: Annotated[
            str | None,
            Field(
                description=(
                    "lookup_product_codes가 반환한 단일 상품 코드. "
                    "상품 식별 전 전체 검색에서는 생략"
                )
            ),
        ] = None,
        expand_neighbors: Annotated[
            bool,
            Field(description="기준 청크의 앞뒤 문맥이 필요한지 여부"),
        ] = False,
    ) -> Command:
        if runtime.tool_call_id is None:
            raise ValueError("Search Service Tool 호출 ID가 없습니다.")
        candidate_codes = runtime.state.get("product_candidate_codes", [])
        scoped_search = bool(candidate_codes)
        try:
            source_file_name = None
            if scoped_search:
                if product_code is None:
                    raise ValueError("검증된 상품 코드가 필요합니다.")
                normalized_code = product_code.strip().upper()
                if normalized_code not in candidate_codes:
                    raise ValueError("상품 코드 식별 결과에 없는 코드입니다.")
                source_file_name = product_code_resolver(normalized_code)
            elif product_code is not None:
                raise ValueError("상품 식별 전에는 상품 코드를 검색 조건으로 사용할 수 없습니다.")
            request = SearchRequest(
                objective=objective,
                source_file_name=source_file_name,
                expand_neighbors=expand_neighbors,
            )
        except (TypeError, ValueError, ValidationError):
            result = SearchResult(
                execution_status="failed",
                error="검색 요청이 올바르지 않습니다.",
            )
        else:
            result = await search_service.search(
                request,
                permission=Permission.PRODUCT,
                deadline=runtime.context.deadline,
            )
        search_call_count = _search_call_count(runtime.state) + 1
        previous_result = None
        if scoped_search and runtime.state.get("product_scoped_search_completed"):
            previous_result = runtime.state.get("search_result")
        accumulated_result = _merge_completed_search_results(
            previous_result,
            result,
        )
        terminal_result = None
        if result.execution_status != "completed" or search_call_count >= max_search_calls:
            terminal_result = _terminal_product_result_from_search(accumulated_result)
        update: dict[str, Any] = {
            "search_result": accumulated_result,
            "product_scoped_search_completed": scoped_search,
            "messages": [
                ToolMessage(
                    content=result.model_dump_json(),
                    tool_call_id=runtime.tool_call_id,
                    name=SEARCH_DOCUMENTS_TOOL_NAME,
                )
            ],
        }
        if terminal_result is not None:
            update["domain_result"] = terminal_result
        if scoped_search and source_file_name is not None:
            update["product_scoped_source_file_name"] = source_file_name
        return Command(update=update)

    return search_documents


def _create_compare_products_tool(
    comparison_service: ProductComparisonService,
    answer_writer: HCXProductComparisonAnswerWriter,
) -> BaseTool:
    @tool(
        COMPARE_PRODUCTS_TOOL_NAME,
        description=(
            "카탈로그에서 확정된 비교 대상의 문서 근거를 병렬 검색하고 비교 답안까지 작성한다. "
            "상품 코드와 비교 항목은 lookup_product_codes 결과 그대로 전달한다. "
            "완료되면 Product 분석이 종료된다."
        ),
    )
    async def compare_products(
        product_codes: Annotated[list[str], Field(min_length=2, max_length=5)],
        criteria: Annotated[
            list[ComparisonCriterion],
            Field(min_length=1, max_length=MAX_PRODUCT_COMPARISON_CRITERIA),
        ],
        runtime: ToolRuntime[ExecutionContext, ProductAgentState],
    ) -> Command:
        if runtime.tool_call_id is None:
            raise ValueError("상품 비교 Tool 호출 ID가 없습니다.")
        compared = await comparison_service.compare(
            product_codes=product_codes,
            criteria=criteria,
            targets=runtime.state.get("comparison_targets", []),
            expected_criteria=runtime.state.get("comparison_criteria", []),
            deadline=runtime.context.deadline,
        )
        result = await answer_writer.write(
            question=runtime.state["question"],
            objective=runtime.state["objective"],
            comparison=compared,
            deadline=runtime.context.deadline,
        )
        return Command(
            update={
                "comparison_evidence": compared,
                "domain_result": result,
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {"execution_status": result["execution_status"]}, ensure_ascii=False
                        ),
                        name=COMPARE_PRODUCTS_TOOL_NAME,
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    return compare_products


def _search_call_count(state: Mapping[str, Any]) -> int:
    """현재 실행에서 완료된 문서 검색 Tool 호출 수를 센다."""

    return sum(
        isinstance(message, ToolMessage) and message.name == SEARCH_DOCUMENTS_TOOL_NAME
        for message in state.get("messages", [])
    )


def _allowed_product_tools(
    state: Mapping[str, Any],
    *,
    lookup_tool_name: str,
    max_search_calls: int,
    calculation_tool_names: tuple[str, ...],
) -> tuple[str, ...]:
    """현재 Product Agent 상태에서 실행 가능한 다음 Tool 이름을 반환한다."""

    search_call_count = _search_call_count(state)
    if state.get("domain_result") is not None:
        return ()
    if state.get("comparison_targets"):
        return (COMPARE_PRODUCTS_TOOL_NAME,) if state.get("comparison_evidence") is None else ()
    if state.get("product_catalog_result") is not None:
        return (SUBMIT_DOMAIN_RESULT_TOOL_NAME,)
    if not state.get("product_candidate_codes"):
        if search_call_count == 0:
            return (
                lookup_tool_name,
                SEARCH_DOCUMENTS_TOOL_NAME,
                SUBMIT_DOMAIN_RESULT_TOOL_NAME,
            )
        return (lookup_tool_name,)
    if not state.get("product_scoped_search_completed"):
        return (SEARCH_DOCUMENTS_TOOL_NAME,)
    unused_calculation_tools = tuple(
        name for name in calculation_tool_names if not _tool_was_called(state, name)
    )
    if search_call_count >= max_search_calls:
        return (*unused_calculation_tools, SUBMIT_DOMAIN_RESULT_TOOL_NAME)
    search_result = state.get("search_result")
    if search_result is not None and not search_result.retrieved_chunks:
        return (SEARCH_DOCUMENTS_TOOL_NAME,)
    return (
        *unused_calculation_tools,
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
        SEARCH_DOCUMENTS_TOOL_NAME,
    )


def _tool_was_called(state: Mapping[str, Any], tool_name: str) -> bool:
    """현재 실행 메시지에 완료된 특정 Tool 호출이 있는지 확인한다."""

    return any(
        isinstance(message, ToolMessage) and message.name == tool_name
        for message in state.get("messages", [])
    )


def _product_tool_call_is_allowed(
    call: ToolCall,
    *,
    state: Mapping[str, Any],
    allowed_tools: tuple[str, ...],
) -> bool:
    """상품 식별 단계에 맞는 product_code를 가진 검색 호출만 허용한다."""

    if call["name"] not in allowed_tools:
        return False
    if state.get("comparison_targets"):
        if call["name"] == COMPARE_PRODUCTS_TOOL_NAME:
            return (
                set(call["args"]) == {"product_codes", "criteria"}
                and call["args"].get("product_codes") == state.get("product_candidate_codes")
                and call["args"].get("criteria") == state.get("comparison_criteria")
            )
        return False
    if call["name"] == SUBMIT_DOMAIN_RESULT_TOOL_NAME and _is_initial_not_applicable_submit_call(
        call, state
    ):
        return True
    if call["name"] == SUBMIT_DOMAIN_RESULT_TOOL_NAME and not state.get("product_candidate_codes"):
        if state.get("product_catalog_result") is not None:
            return _is_product_catalog_submit_call(call)
        return False
    if call["name"] == "calculate_fund_reported_var_risk":
        return _reported_var_call_missing_condition(call, state) is None
    if call["name"] == "calculate_fund_var_risk" and _has_reported_var_evidence(state):
        return False
    if call["name"] != SEARCH_DOCUMENTS_TOOL_NAME:
        return True
    candidate_codes = state.get("product_candidate_codes", [])
    product_code = call["args"].get("product_code")
    if not candidate_codes:
        return product_code is None
    if not isinstance(product_code, str):
        return False
    return product_code.strip().upper() in candidate_codes


def _is_initial_not_applicable_submit_call(
    call: ToolCall,
    state: Mapping[str, Any],
) -> bool:
    """검색·카탈로그 조회 전 범위 밖 판단만 조기 제출하도록 허용한다."""

    return (
        call["args"].get("status") == "not_applicable"
        and state.get("search_result") is None
        and state.get("product_catalog_result") is None
        and not state.get("product_candidate_codes")
    )


def _is_product_catalog_submit_call(call: ToolCall) -> bool:
    """카탈로그 조회 후에는 검증값을 보존하는 확정 제출만 허용한다."""

    args = call["args"]
    return (
        args.get("status") == "determined"
        and args.get("missing_conditions") == []
        and args.get("evidence_chunk_ids") == []
    )


def _product_next_tool_instruction(
    state: Mapping[str, Any],
    *,
    max_search_calls: int,
    calculation_tool_names: tuple[str, ...],
) -> str:
    """Product Agent의 현재 단계에 맞는 다음 Tool 안내를 만든다."""

    search_call_count = _search_call_count(state)
    if state.get("comparison_targets"):
        return _comparison_instructions()["search"]
    if state.get("product_catalog_result") is not None:
        return "검증된 상품 개수·목록을 determined로 최종 결과 제출 Tool에 제출하세요."
    if not state.get("product_candidate_codes"):
        if search_call_count == 0:
            return (
                "판단 목표가 상품·운용 범위 밖이면 not_applicable로 최종 결과를 "
                "제출하세요. 그 외에는 lookup_product_codes Tool로 상품을 식별하거나 "
                "product_code 없이 search_documents Tool로 상품 문서를 먼저 검색하세요."
            )
        return "lookup_product_codes Tool로 검색 대상 상품 코드를 식별하세요."
    if not state.get("product_scoped_search_completed"):
        return "검증된 product_code로 search_documents Tool을 호출하세요."
    search_result = state.get("search_result")
    if (
        search_result is not None
        and not search_result.retrieved_chunks
        and search_call_count < max_search_calls
    ):
        return "검색 목표를 다르게 재작성해 search_documents Tool을 호출하세요."
    unused_calculation_tools = [
        name for name in calculation_tool_names if not _tool_was_called(state, name)
    ]
    if unused_calculation_tools:
        return (
            "질문에 해당하는 계산이 있으면 그 계산 하나에 맞는 Calculation Tool만 호출하고, "
            "그 외에는 최종 도메인 판단 결과 제출 Tool로 결과를 제출하세요."
        )
    return "최종 도메인 판단 결과 제출 Tool로 결과를 제출하세요."


def _merge_completed_search_results(
    previous: SearchResult | None,
    current: SearchResult,
) -> SearchResult:
    """완료된 검색 근거를 청크 ID 기준으로 누적하고 중복을 제거한다."""

    if (
        previous is None
        or previous.execution_status != "completed"
        or current.execution_status != "completed"
    ):
        return current
    chunks_by_id = {
        chunk.chunk_id: chunk for chunk in (*previous.retrieved_chunks, *current.retrieved_chunks)
    }
    limitations = []
    if not chunks_by_id:
        limitations = list(dict.fromkeys((*previous.limitations, *current.limitations)))
    return SearchResult(
        execution_status="completed",
        retrieved_chunks=list(chunks_by_id.values()),
        limitations=limitations,
    )


def _create_product_result_tool() -> Any:
    @tool(
        SUBMIT_DOMAIN_RESULT_TOOL_NAME,
        description=(
            "최종 도메인 판단 결과 제출 Tool. 검증된 검색 근거에서 도출한 "
            "판단, 누락 조건과 경고만 제출한다."
        ),
    )
    async def submit_domain_result(
        status: Annotated[
            DecisionStatus,
            Field(description="determined, conditional, undetermined, not_applicable 중 하나"),
        ],
        conclusion: Annotated[str, Field(min_length=1, description="근거에서 도출한 결론")],
        missing_conditions: Annotated[
            list[str],
            Field(description="조건부 또는 미확정 판단에 필요한 누락 조건"),
        ],
        warnings: Annotated[list[str], Field(description="이용자가 알아야 할 제한과 주의사항")],
        evidence_chunk_ids: Annotated[
            list[str],
            Field(description="결론에 실제 사용한 SearchResult 청크 UUID 목록"),
        ],
        runtime: ToolRuntime[ExecutionContext, ProductAgentState],
    ) -> Command | str:
        tool_call_id = runtime.tool_call_id
        if tool_call_id is None:
            raise ValueError("최종 Product Agent 결과 제출 Tool 호출 ID가 없습니다.")
        if status == "not_applicable":
            return Command(
                update={
                    "domain_result": _not_applicable_product_result(),
                    "messages": [
                        ToolMessage(
                            content=json.dumps({"status": "accepted"}, ensure_ascii=False),
                            tool_call_id=tool_call_id,
                            name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                        )
                    ],
                }
            )
        search_result = runtime.state.get("search_result")
        if search_result is None:
            try:
                catalog_result = runtime.state.get("product_catalog_result")
                if catalog_result is None:
                    raise ValueError("검증된 카탈로그 결과가 없습니다.")
                if status != "determined" or missing_conditions or evidence_chunk_ids:
                    raise ValueError("확정 카탈로그 결과의 제출 인자가 올바르지 않습니다.")
                result = catalog_result
                validate_domain_result(result)
            except (TypeError, ValueError):
                return json.dumps(
                    {"error": "상품 카탈로그 결과가 공통 계약을 위반했습니다."},
                    ensure_ascii=False,
                )
            return Command(
                update={
                    "domain_result": result,
                    "messages": [
                        ToolMessage(
                            content=json.dumps({"status": "accepted"}, ensure_ascii=False),
                            tool_call_id=tool_call_id,
                            name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                        )
                    ],
                }
            )
        if not runtime.state.get("product_scoped_search_completed"):
            return json.dumps(
                {"error": "검증된 product_code로 search_documents Tool을 호출해야 합니다."},
                ensure_ascii=False,
            )
        try:
            result = _build_product_result(
                search_result=search_result,
                calculations=list(runtime.state.get("calculations", [])),
                status=status,
                conclusion=conclusion,
                missing_conditions=missing_conditions,
                warnings=warnings,
                evidence_chunk_ids=evidence_chunk_ids,
                enforced_missing_conditions=_product_var_missing_conditions(runtime.state),
            )
            validate_domain_result(result)
        except (KeyError, TypeError, ValueError):
            return json.dumps(
                {"error": "최종 도메인 판단 결과가 공통 계약을 위반했습니다."},
                ensure_ascii=False,
            )
        return Command(
            update={
                "domain_result": result,
                "messages": [
                    ToolMessage(
                        content=json.dumps({"status": "accepted"}, ensure_ascii=False),
                        tool_call_id=tool_call_id,
                        name=SUBMIT_DOMAIN_RESULT_TOOL_NAME,
                    )
                ],
            }
        )

    return submit_domain_result


@cache
def _comparison_instructions() -> dict[str, str]:
    """비교 실행 단계별 보완 지시를 버전 관리 리소스에서 읽는다."""

    return json.loads(
        resources.files("pension_agent.prompts")
        .joinpath("domain", "product-comparison-guidance.json")
        .read_text(encoding="utf-8")
    )


def _not_applicable_product_result() -> DomainResult:
    return {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "not_applicable",
            "conclusion": _NOT_APPLICABLE_CONCLUSION,
            "missing_conditions": [],
        },
        "evidence": [],
        "calculations": [],
        "warnings": [],
    }


def _build_product_result(
    *,
    search_result: SearchResult,
    calculations: list[CalculationResult],
    status: DecisionStatus,
    conclusion: str,
    missing_conditions: list[str],
    warnings: list[str],
    evidence_chunk_ids: list[str],
    enforced_missing_conditions: tuple[str, ...] = (),
) -> DomainResult:
    if search_result.execution_status != "completed":
        return failed_domain_result(
            "product",
            search_result.error or "검색을 완료하지 못했습니다.",
            execution_status=search_result.execution_status,
        )

    required_evidence_ids = calculation_evidence_chunk_ids(calculations)
    selected_chunks = _select_evidence_chunks(
        search_result=search_result,
        evidence_chunk_ids=list(dict.fromkeys([*evidence_chunk_ids, *required_evidence_ids])),
    )
    normalized_missing = [value.strip() for value in missing_conditions if value.strip()]
    normalized_missing = list(dict.fromkeys([*normalized_missing, *enforced_missing_conditions]))
    normalized_warnings = [value.strip() for value in warnings if value.strip()]
    normalized_limitations = list(search_result.limitations)
    normalized_conclusion = conclusion.strip()
    if normalized_missing and status == "determined":
        status = "conditional"
    if calculations:
        normalized_conclusion = "검증된 Python 계산 결과:\n" + format_calculation_summary(
            calculations
        )
        normalized_warnings.extend(
            warning for calculation in calculations for warning in calculation["warnings"]
        )
    if not selected_chunks and status != "not_applicable":
        status = "undetermined"
        normalized_conclusion = _NO_EVIDENCE_CONCLUSION
        normalized_missing = ["제공 문서의 관련 근거"]
        normalized_warnings.append("검색된 원문 청크 중 결론에 사용한 근거가 제출되지 않았습니다.")
        calculations = []

    if status == "not_applicable":
        normalized_conclusion = _NOT_APPLICABLE_CONCLUSION
        normalized_missing = []
        normalized_warnings = []
        normalized_limitations = []
        calculations = []

    normalized_warnings.extend(normalized_limitations)
    evidence = [_evidence_from_chunk(chunk) for chunk in selected_chunks]
    if status == "not_applicable":
        evidence = []
    return {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": status,
            "conclusion": normalized_conclusion,
            "missing_conditions": normalized_missing,
        },
        "evidence": evidence,
        "calculations": calculations,
        "warnings": list(dict.fromkeys(normalized_warnings)),
    }


def _reported_var_call_missing_condition(
    call: ToolCall,
    state: Mapping[str, Any],
) -> str | None:
    """공시 VaR Tool 호출이 현재 상품·클래스·최신성 경계를 만족하는지 확인한다."""

    candidate_codes = state.get("product_candidate_codes", [])
    if len(candidate_codes) != 1 or not state.get("product_scoped_search_completed"):
        return _TARGET_FUND_MISSING_CONDITION
    source = call["args"].get("annualized_var_source")
    if not isinstance(source, str) or not source.strip():
        return _ANNUALIZED_VAR_MISSING_CONDITION
    matching_chunks = _chunks_containing_source(state, source)
    expected_file = state.get("product_scoped_source_file_name")
    question = str(state.get("question", ""))
    source_is_question = source in question
    if not isinstance(expected_file, str):
        return _TARGET_FUND_MISSING_CONDITION
    if not source_is_question and not matching_chunks:
        return _TARGET_FUND_MISSING_CONDITION
    if matching_chunks and any(
        chunk.source_file_name != expected_file for chunk in matching_chunks
    ):
        return _TARGET_FUND_MISSING_CONDITION
    question_classes = _class_tokens(question)
    if question_classes and not question_classes.intersection(_class_tokens(source)):
        return _FUND_CLASS_MISSING_CONDITION
    if _requests_latest_disclosure(question):
        return _LATEST_DISCLOSURE_MISSING_CONDITION
    if not _is_reported_annualized_var_text(source):
        return _ANNUALIZED_VAR_MISSING_CONDITION
    return None


def _product_var_missing_conditions(state: Mapping[str, Any]) -> tuple[str, ...]:
    """VaR 질문에서 Python이 확정하지 못한 선택 조건을 반환한다."""

    question = str(state.get("question", ""))
    if not _VAR_QUESTION_PATTERN.search(question) or state.get("calculations"):
        return ()
    missing: list[str] = []
    if len(state.get("product_candidate_codes", [])) != 1 or not state.get(
        "product_scoped_search_completed"
    ):
        missing.append(_TARGET_FUND_MISSING_CONDITION)
    question_classes = _class_tokens(question)
    evidence_text = "\n".join(_search_chunk_contents(state))
    if question_classes and not question_classes.intersection(_class_tokens(evidence_text)):
        missing.append(_FUND_CLASS_MISSING_CONDITION)
    if _requests_latest_disclosure(question):
        missing.append(_LATEST_DISCLOSURE_MISSING_CONDITION)
    if not _has_reported_var_evidence(state):
        missing.append(_ANNUALIZED_VAR_MISSING_CONDITION)
    return tuple(dict.fromkeys(missing))


def _has_reported_var_evidence(state: Mapping[str, Any]) -> bool:
    return any(_is_reported_annualized_var_text(value) for value in _search_chunk_contents(state))


def _is_reported_annualized_var_text(value: str) -> bool:
    normalized = value.replace(" ", "").lower()
    return "연환산" in value and (
        "97.5%var" in normalized or ("일간수익률" in normalized and "최대손실예상액" in normalized)
    )


def _search_chunk_contents(state: Mapping[str, Any]) -> list[str]:
    search_result = state.get("search_result")
    if search_result is None:
        return []
    return [chunk.content for chunk in search_result.retrieved_chunks]


def _chunks_containing_source(state: Mapping[str, Any], source: str) -> list[Any]:
    search_result = state.get("search_result")
    if search_result is None:
        return []
    return [chunk for chunk in search_result.retrieved_chunks if source in chunk.content]


def _class_tokens(value: str) -> set[str]:
    return {
        (first or second).upper()
        for first, second in _CLASS_PATTERN.findall(value)
        if first or second
    }


def _requests_latest_disclosure(question: str) -> bool:
    return any(label in question for label in ("현재", "최신", "최근 공시"))


def _select_evidence_chunks(
    *,
    search_result: SearchResult,
    evidence_chunk_ids: list[str],
) -> list[Any]:
    """Domain 모델이 명시한 검증된 SearchResult 부분집합만 반환한다."""

    try:
        normalized_ids = [str(UUID(value.strip())) for value in evidence_chunk_ids]
    except (AttributeError, TypeError, ValueError):
        raise ValueError("근거 청크 ID는 UUID 형식이어야 합니다.") from None
    if len(normalized_ids) != len(set(normalized_ids)):
        raise ValueError("근거 청크 ID는 중복될 수 없습니다.")
    chunks_by_id = {chunk.chunk_id: chunk for chunk in search_result.retrieved_chunks}
    if any(chunk_id not in chunks_by_id for chunk_id in normalized_ids):
        raise ValueError("SearchResult에 없는 청크를 근거로 제출할 수 없습니다.")
    return [chunks_by_id[chunk_id] for chunk_id in normalized_ids]


def _terminal_product_result_from_search(search_result: SearchResult) -> DomainResult | None:
    """검색 실패나 빈 결과는 모델 재호출 없이 안전하게 종료한다."""

    if search_result.execution_status != "completed":
        return failed_domain_result(
            "product",
            search_result.error or "검색을 완료하지 못했습니다.",
            execution_status=search_result.execution_status,
        )
    if search_result.retrieved_chunks:
        return None
    return {
        "domain": "product",
        "execution_status": "completed",
        "decision": {
            "status": "undetermined",
            "conclusion": _NO_EVIDENCE_CONCLUSION,
            "missing_conditions": ["제공 문서의 관련 근거"],
        },
        "evidence": [],
        "calculations": [],
        "warnings": list(
            dict.fromkeys(
                [
                    *search_result.limitations,
                    "제공 문서에서 관련 근거를 확인하지 못했습니다.",
                ]
            )
        ),
    }


def _hint_is_present_in_question(state: ProductAgentState, hint: str) -> bool:
    """모델이 생성한 힌트 대신 사용자 원문에 있는 힌트만 허용한다."""

    question = state.get("question", "")
    return hint.strip() in question


def _evidence_from_chunk(chunk: Any) -> EvidenceChunk:
    return {
        "chunk_id": chunk.chunk_id,
        "source_file_name": chunk.source_file_name,
        "title": chunk.title,
        "locator": chunk.locator,
        "content": chunk.content,
    }
