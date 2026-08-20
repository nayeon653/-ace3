"""버전 관리되는 Agent 그래프 산출물의 최신 상태를 검증한다."""

from tools.render_agent_graphs import (
    DEFAULT_IMAGE_DIR,
    DEFAULT_MANIFEST,
    DEFAULT_OUTPUT,
    build_artifacts,
    render_document,
    render_manifest,
)


def test_agent_graph_document_matches_compiled_graphs() -> None:
    artifacts = build_artifacts()

    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_document(artifacts)
    assert DEFAULT_MANIFEST.read_text(encoding="utf-8") == render_manifest(artifacts)
    assert all((DEFAULT_IMAGE_DIR / artifact.image_name).is_file() for artifact in artifacts)


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
    assert "search_documents" in document
    assert "submit_domain_result" in document
    assert "get_graph(xray=True)" in document
