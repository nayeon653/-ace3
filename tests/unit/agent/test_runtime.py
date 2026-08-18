"""실제 런타임 팩토리의 조립 순서와 자원 정리를 검증한다."""

from dataclasses import dataclass
from typing import Any, cast

import pytest

from pension_agent.agent import runtime
from pension_agent.agent.orchestration.service import SupervisorRunner


@dataclass
class Closable:
    name: str
    closed: list[str]

    def close(self) -> None:
        self.closed.append(self.name)

    def __call__(self, request: Any) -> Any:
        raise AssertionError(request)


def test_runtime_uses_one_hcx_model_and_closes_resources_in_dependency_order(
    monkeypatch,
) -> None:
    closed: list[str] = []
    model = object()
    embedder = object()
    client = Closable("qdrant", closed)
    retriever = object()
    search_graph = object()
    search_adapter = Closable("search", closed)
    created: dict[str, Any] = {}

    monkeypatch.setattr(runtime, "create_chat_clovax", lambda **kwargs: model)
    monkeypatch.setattr(runtime, "create_clova_query_embedder", lambda **kwargs: embedder)
    monkeypatch.setattr(runtime, "create_qdrant_client", lambda connection: client)
    monkeypatch.setattr(
        runtime,
        "create_qdrant_retriever",
        lambda passed_client, *, connection: (
            created.update(client=passed_client, qdrant_connection=connection) or retriever
        ),
    )
    monkeypatch.setattr(
        runtime,
        "create_search_agent",
        lambda **kwargs: (
            created.update(search_model=kwargs["model"], embedder=kwargs["embedder"])
            or search_graph
        ),
    )
    monkeypatch.setattr(runtime, "SearchAgentAdapter", lambda graph: search_adapter)

    def domain_factory(name: str):
        def build(*, model: Any, search_adapter: Any) -> Closable:
            created[f"{name}_model"] = model
            created[f"{name}_search"] = search_adapter
            return Closable(name, closed)

        return build

    monkeypatch.setattr(runtime, "create_policy_agent", domain_factory("policy"))
    monkeypatch.setattr(runtime, "create_tax_payout_agent", domain_factory("tax_payout"))
    monkeypatch.setattr(runtime, "create_product_agent", domain_factory("product"))
    supervisor = cast(SupervisorRunner, object())

    def create_supervisor(*, model: Any, tools: Any) -> SupervisorRunner:
        created["supervisor_model"] = model
        created["tool_names"] = {tool.name for tool in tools}
        return supervisor

    monkeypatch.setattr(runtime, "create_main_supervisor", create_supervisor)

    service = runtime.build_runtime_answer_service()
    service.close()
    service.close()

    assert created["client"] is client
    assert created["search_model"] is model
    assert created["embedder"] is embedder
    assert created["policy_model"] is model
    assert created["tax_payout_model"] is model
    assert created["product_model"] is model
    assert created["policy_search"] is search_adapter
    assert created["supervisor_model"] is model
    assert created["tool_names"] == {
        "analyze_policy",
        "analyze_tax_payout",
        "analyze_product",
    }
    assert closed == ["policy", "tax_payout", "product", "search", "qdrant"]


def test_runtime_closes_partial_resources_when_domain_creation_fails(monkeypatch) -> None:
    closed: list[str] = []
    client = Closable("qdrant", closed)
    search_adapter = Closable("search", closed)
    policy = Closable("policy", closed)
    tax = Closable("tax_payout", closed)

    monkeypatch.setattr(runtime, "create_chat_clovax", lambda **kwargs: object())
    monkeypatch.setattr(runtime, "create_clova_query_embedder", lambda **kwargs: object())
    monkeypatch.setattr(runtime, "create_qdrant_client", lambda connection: client)
    monkeypatch.setattr(runtime, "create_qdrant_retriever", lambda *args, **kwargs: object())
    monkeypatch.setattr(runtime, "create_search_agent", lambda **kwargs: object())
    monkeypatch.setattr(runtime, "SearchAgentAdapter", lambda graph: search_adapter)
    monkeypatch.setattr(runtime, "create_policy_agent", lambda **kwargs: policy)
    monkeypatch.setattr(runtime, "create_tax_payout_agent", lambda **kwargs: tax)

    def fail_product(**kwargs):
        raise RuntimeError("provider secret")

    monkeypatch.setattr(runtime, "create_product_agent", fail_product)

    with pytest.raises(runtime.AgentRuntimeBuildError, match="Agent 런타임 초기화") as exc_info:
        runtime.build_runtime_answer_service()

    assert "provider secret" not in str(exc_info.value)
    assert closed == ["policy", "tax_payout", "search", "qdrant"]
