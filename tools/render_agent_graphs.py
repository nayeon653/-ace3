"""전체 Agent 그래프 문서와 PNG 이미지를 생성한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain.messages import AIMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import Runnable
from langchain_core.runnables.graph import MermaidDrawMethod
from langchain_core.runnables.graph_mermaid import draw_mermaid_png

from pension_agent.agent.execution import AsyncConcurrencyLimiter, ModelConcurrencyMiddleware
from pension_agent.agent.orchestration import create_domain_agent_tool, create_main_supervisor
from pension_agent.agent.runtime import DomainAgentSpec, domain_agent_specs
from pension_agent.config import (
    BGE_M3_EMBEDDING_CONFIG,
    DEFAULT_AGENT_RUNTIME_CONFIG,
    MAIN_SUPERVISOR_HCX_CONFIG,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "docs" / "architecture" / "agent-graphs.md"
DEFAULT_IMAGE_DIR = REPOSITORY_ROOT / "docs" / "architecture" / "generated"
DEFAULT_MANIFEST = DEFAULT_IMAGE_DIR / "manifest.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True, slots=True)
class GraphArtifact:
    """하나의 Mermaid 그래프와 PNG 산출물 정보."""

    name: str
    title: str
    mermaid: str

    @property
    def image_name(self) -> str:
        return f"{self.name}.png"

    @property
    def source_sha256(self) -> str:
        return hashlib.sha256(self.mermaid.encode()).hexdigest()


class _OfflineSearchService:
    """그래프 조립 중 실제 검색 실행을 허용하지 않는 대체 객체."""

    async def search(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("그래프 생성 중에는 SearchService를 실행할 수 없습니다.")


class _GraphFakeModel(FakeMessagesListChatModel):
    """그래프 조립에 필요한 Tool binding만 지원하는 오프라인 모델."""

    def bind_tools(
        self,
        tools: Sequence[Any],
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        del tools, kwargs
        return self


def _domain_node_id(spec: DomainAgentSpec) -> str:
    return f"domain_{spec.slug.replace('-', '_')}"


def _system_overview(specs: tuple[DomainAgentSpec, ...]) -> str:
    """런타임 Domain 등록 정보에서 전체 호출 경계 Mermaid를 만든다."""

    lines = [
        "flowchart TB",
        '    question["GET /answer 질문"] --> supervisor',
        "",
        '    subgraph main["Main Supervisor · CompiledStateGraph"]',
        (
            f'        supervisor["{MAIN_SUPERVISOR_HCX_CONFIG.model} model"] '
            '<--> domain_tools["Domain Agent tools"]'
        ),
        "    end",
        "",
    ]
    lines.extend(
        f"    domain_tools -->|{spec.tool_name}| {_domain_node_id(spec)}" for spec in specs
    )
    lines.extend(
        (
            "",
            '    subgraph domains["Domain Agents · 각각 CompiledStateGraph"]',
        )
    )
    lines.extend(f'        {_domain_node_id(spec)}["{spec.display_name} Agent"]' for spec in specs)
    lines.extend(("    end", ""))
    for spec in specs:
        node_id = _domain_node_id(spec)
        lines.extend(
            (
                f"    {node_id} --> domain_tools",
                f"    {node_id} --> search_tools",
            )
        )
    product_node = _domain_node_id(next(spec for spec in specs if spec.domain == "product"))
    lines.extend(
        (
            "",
            '    subgraph catalog["HCX 카탈로그 Query 계획 · Python 조회"]',
            (
                '        catalog_lookup["lookup_product_codes"] --> '
                f'catalog_hcx["{MAIN_SUPERVISOR_HCX_CONFIG.model} model"]'
            ),
            '        product_catalog["상품 카탈로그"] --> catalog_hcx',
            '        catalog_hcx --> catalog_query["검증된 CatalogQueryPlan"]',
            '        catalog_query --> catalog_execute["Python 정확 조회"]',
            '        product_catalog --> catalog_execute',
            '        catalog_execute --> catalog_result["CatalogResult"]',
            "    end",
            f"    {product_node} --> catalog_lookup",
            f"    catalog_result --> {product_node}",
        )
    )
    lines.extend(
        (
            "",
            '    subgraph search["공용 검색 경로"]',
            '        search_tools["search_documents"] --> search_service["SearchService"]',
            (
                '        search_service --> embedding["CLOVA '
                f'{BGE_M3_EMBEDDING_CONFIG.model} query embedding"]'
            ),
            '        search_service --> qdrant["Qdrant hybrid retrieval"]',
            "    end",
            "",
            '    supervisor --> answer["최종 답변"]',
        )
    )
    return "\n".join(lines)


def _quote_mermaid_node_labels(mermaid: str) -> str:
    """Mermaid.ink가 대괄호 포함 node label을 파싱하도록 따옴표로 감싼다."""

    normalized: list[str] = []
    for line in mermaid.splitlines():
        stripped = line.strip()
        if (
            not stripped.endswith(")")
            or ":::" in stripped
            or "-->" in stripped
            or "-.->" in stripped
            or "(" not in stripped
        ):
            normalized.append(line)
            continue
        prefix, label = line.split("(", maxsplit=1)
        escaped_label = label[:-1].replace('"', '\\"')
        normalized.append(f'{prefix}("{escaped_label}")')
    return "\n".join(normalized)


def build_artifacts() -> tuple[GraphArtifact, ...]:
    """제품 런타임과 같은 등록 정보·Factory·middleware로 그래프를 조립한다."""

    specs = domain_agent_specs()
    model = _GraphFakeModel(responses=[])
    search_service = _OfflineSearchService()
    model_concurrency = ModelConcurrencyMiddleware(
        AsyncConcurrencyLimiter(DEFAULT_AGENT_RUNTIME_CONFIG.max_concurrent_hcx_calls)
    )
    domain_agents = {
        spec.slug: spec.factory(
            model=model,
            search_service=search_service,
            model_concurrency=model_concurrency,
        )
        for spec in specs
    }
    domain_tools = tuple(
        create_domain_agent_tool(
            name=spec.tool_name,
            description=spec.tool_description,
            domain=spec.domain,
            runner=domain_agents[spec.slug],
        )
        for spec in specs
    )
    supervisor = create_main_supervisor(
        model=model,
        tools=domain_tools,
        model_concurrency=model_concurrency,
    )
    compiled_graphs = {
        "main-supervisor": supervisor,
        **{spec.slug: domain_agents[spec.slug].graph for spec in specs},
    }
    titles = {
        "main-supervisor": "Main Supervisor 컴파일 그래프",
        **{spec.slug: f"{spec.display_name} Domain Agent 컴파일 그래프" for spec in specs},
    }
    return (
        GraphArtifact(
            name="agent-system",
            title="전체 호출 구조",
            mermaid=_system_overview(specs),
        ),
        *(
            GraphArtifact(
                name=name,
                title=titles[name],
                mermaid=_quote_mermaid_node_labels(
                    graph.get_graph(xray=True).draw_mermaid().rstrip()
                ),
            )
            for name, graph in compiled_graphs.items()
        ),
    )


def render_document(artifacts: tuple[GraphArtifact, ...] | None = None) -> str:
    """PNG와 원본 Mermaid를 함께 보여주는 GitHub 문서를 만든다."""

    artifacts = artifacts or build_artifacts()
    sections = [
        "# Agent 전체 그래프",
        "",
        "<!-- 이 파일은 tools/render_agent_graphs.py로 생성됩니다. 직접 수정하지 마세요. -->",
        "",
        (
            "`make agent-graph`로 현재 코드에서 PNG와 함께 다시 생성합니다. 컴파일 그래프는 "
            "LangGraph의 `get_graph(xray=True)` 결과를 사용합니다."
        ),
    ]
    for artifact in artifacts:
        sections.extend(
            (
                "",
                f"## {artifact.title}",
                "",
                f"![{artifact.title}](generated/{artifact.image_name})",
                "",
                "<details>",
                "<summary>Mermaid 원본 보기</summary>",
                "",
                "```mermaid",
                artifact.mermaid,
                "```",
                "",
                "</details>",
            )
        )
    return "\n".join(sections) + "\n"


def render_manifest(artifacts: tuple[GraphArtifact, ...] | None = None) -> str:
    """이미지가 어떤 Mermaid 원본에서 생성됐는지 기록한다."""

    artifacts = artifacts or build_artifacts()
    image_hashes = {
        artifact.image_name: _file_sha256(DEFAULT_IMAGE_DIR / artifact.image_name)
        for artifact in artifacts
    }
    return _render_manifest(artifacts, image_hashes=image_hashes)


def _render_manifest(
    artifacts: tuple[GraphArtifact, ...],
    *,
    image_hashes: Mapping[str, str],
) -> str:
    """Mermaid 원본과 생성된 PNG의 해시 manifest를 만든다."""

    payload = {
        "version": 1,
        "renderer": "langchain-core MermaidDrawMethod.API",
        "artifacts": {
            artifact.image_name: {
                "image_sha256": image_hashes[artifact.image_name],
                "mermaid_sha256": artifact.source_sha256,
            }
            for artifact in artifacts
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _file_sha256(path: Path) -> str:
    """파일 전체 내용의 SHA-256을 반환한다."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def outputs_are_current(artifacts: tuple[GraphArtifact, ...]) -> bool:
    """문서·manifest·PNG 집합이 현재 그래프와 일치하는지 확인한다."""

    if not DEFAULT_OUTPUT.is_file() or DEFAULT_OUTPUT.read_text(
        encoding="utf-8"
    ) != render_document(artifacts):
        return False
    expected_image_names = {artifact.image_name for artifact in artifacts}
    actual_image_names = {path.name for path in DEFAULT_IMAGE_DIR.glob("*.png")}
    if actual_image_names != expected_image_names:
        return False
    if not all(
        (image_path := DEFAULT_IMAGE_DIR / artifact.image_name).is_file()
        and image_path.read_bytes()[: len(PNG_SIGNATURE)] == PNG_SIGNATURE
        for artifact in artifacts
    ):
        return False
    return DEFAULT_MANIFEST.is_file() and DEFAULT_MANIFEST.read_text(
        encoding="utf-8"
    ) == render_manifest(artifacts)


def _previous_image_names() -> set[str]:
    if not DEFAULT_MANIFEST.is_file():
        return set()
    try:
        payload = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        return set(payload.get("artifacts", {}))
    except (AttributeError, json.JSONDecodeError, TypeError):
        return set()


def write_outputs(artifacts: tuple[GraphArtifact, ...]) -> None:
    """Mermaid.ink로 PNG를 모두 렌더링한 뒤 산출물을 교체한다."""

    DEFAULT_IMAGE_DIR.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".agent-graphs-",
        dir=DEFAULT_IMAGE_DIR.parent,
    ) as temporary_directory:
        temporary_path = Path(temporary_directory)
        for artifact in artifacts:
            image_path = temporary_path / artifact.image_name
            image = draw_mermaid_png(
                mermaid_syntax=artifact.mermaid,
                output_file_path=str(image_path),
                draw_method=MermaidDrawMethod.API,
                max_retries=3,
            )
            if not image.startswith(PNG_SIGNATURE):
                raise RuntimeError(f"올바르지 않은 PNG 응답입니다: {artifact.image_name}")

        image_hashes = {
            artifact.image_name: _file_sha256(temporary_path / artifact.image_name)
            for artifact in artifacts
        }
        manifest = _render_manifest(artifacts, image_hashes=image_hashes)
        previous_names = _previous_image_names()
        DEFAULT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        for artifact in artifacts:
            (temporary_path / artifact.image_name).replace(DEFAULT_IMAGE_DIR / artifact.image_name)
        current_names = {artifact.image_name for artifact in artifacts}
        for stale_name in previous_names - current_names:
            stale_path = DEFAULT_IMAGE_DIR / stale_name
            if stale_path.parent == DEFAULT_IMAGE_DIR and stale_path.is_file():
                stale_path.unlink()

    DEFAULT_OUTPUT.write_text(render_document(artifacts), encoding="utf-8")
    DEFAULT_MANIFEST.write_text(manifest, encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="전체 Agent 그래프와 PNG를 생성합니다.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="외부 연결 없이 기존 산출물이 현재 그래프와 일치하는지만 확인",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    artifacts = build_artifacts()
    if args.check:
        if not outputs_are_current(artifacts):
            print("Agent 그래프 산출물이 최신 상태가 아닙니다. make agent-graph를 실행하세요.")
            return 1
        print(f"Agent 그래프 산출물이 최신 상태입니다: {DEFAULT_OUTPUT}")
        return 0

    write_outputs(artifacts)
    print(f"Agent 그래프 문서와 PNG {len(artifacts)}개를 생성했습니다: {DEFAULT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
