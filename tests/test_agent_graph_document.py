"""버전 관리되는 Agent 그래프 산출물의 최신 상태를 검증한다."""

from pathlib import Path

import pytest

import tools.render_agent_graphs as graph_renderer
from tools.render_agent_graphs import (
    DEFAULT_IMAGE_DIR,
    DEFAULT_MANIFEST,
    DEFAULT_OUTPUT,
    PNG_SIGNATURE,
    build_artifacts,
    outputs_are_current,
    render_document,
    render_manifest,
)


def test_agent_graph_document_matches_compiled_graphs() -> None:
    artifacts = build_artifacts()

    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_document(artifacts)
    assert DEFAULT_MANIFEST.read_text(encoding="utf-8") == render_manifest(artifacts)
    assert all((DEFAULT_IMAGE_DIR / artifact.image_name).is_file() for artifact in artifacts)
    assert outputs_are_current(artifacts)


def test_agent_graph_check_rejects_modified_and_extra_images(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = build_artifacts()
    image_dir = tmp_path / "generated"
    image_dir.mkdir()
    monkeypatch.setattr(graph_renderer, "DEFAULT_OUTPUT", tmp_path / "agent-graphs.md")
    monkeypatch.setattr(graph_renderer, "DEFAULT_IMAGE_DIR", image_dir)
    monkeypatch.setattr(graph_renderer, "DEFAULT_MANIFEST", image_dir / "manifest.json")

    graph_renderer.DEFAULT_OUTPUT.write_text(render_document(artifacts), encoding="utf-8")
    image_contents = {
        artifact.image_name: PNG_SIGNATURE + artifact.image_name.encode() for artifact in artifacts
    }
    for image_name, content in image_contents.items():
        (image_dir / image_name).write_bytes(content)
    graph_renderer.DEFAULT_MANIFEST.write_text(render_manifest(artifacts), encoding="utf-8")
    assert outputs_are_current(artifacts)

    first_image_name = artifacts[0].image_name
    (image_dir / first_image_name).write_bytes(PNG_SIGNATURE + b"modified")
    assert not outputs_are_current(artifacts)

    (image_dir / first_image_name).write_bytes(image_contents[first_image_name])
    (image_dir / "stale.png").write_bytes(PNG_SIGNATURE + b"stale")
    assert not outputs_are_current(artifacts)


def test_agent_graph_document_covers_runtime_boundaries() -> None:
    document = render_document(build_artifacts())

    assert "Main Supervisor · CompiledStateGraph" in document
    assert "Policy Agent" in document
    assert "Tax/Payout Agent" in document
    assert "Product Agent" in document
    assert "SearchService" in document
    assert "analyze_policy" in document
    assert "analyze_tax_payout" in document
    assert "analyze_product" in document
    assert "lookup_product_codes" in document
    assert "상품 카탈로그" in document
    assert "search_documents" in document
    assert "submit_domain_result" in document
    assert "get_graph(xray=True)" in document
