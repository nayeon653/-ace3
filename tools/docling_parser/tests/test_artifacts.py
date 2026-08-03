from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import docling_team_parser.artifacts as artifacts_module
import pytest
from docling_team_parser.artifacts import parse_document
from docling_team_parser.errors import NaverOcrError, ParserError
from docling_team_parser.profiles import LOCAL_PROFILE_ID, NAVER_PROFILE_ID


class FakeDocument:
    def save_as_markdown(
        self,
        filename: Path,
        *,
        artifacts_dir: Path,
        **_kwargs: Any,
    ) -> None:
        asset_dir = filename.parent / artifacts_dir
        asset_dir.mkdir(parents=True, exist_ok=True)
        (asset_dir / "picture.png").write_bytes(b"png")
        filename.write_text("# Parsed\r\n\r\n![image](assets\\picture.png)", encoding="utf-8")

    def save_as_json(
        self,
        filename: Path,
        *,
        artifacts_dir: Path,
        **_kwargs: Any,
    ) -> None:
        assert artifacts_dir == Path("assets")
        filename.write_text(
            '{"image":{"uri":"assets\\\\picture.png"},"text":"assets\\\\literal"}',
            encoding="utf-8",
        )


@dataclass
class FakeEngineResult:
    document: Any = field(default_factory=FakeDocument)
    pages: int = 2
    pictures_found: int = 1
    office_pictures_ocrd: int = 1
    warnings: list[str] = field(default_factory=list)
    conversion_version: dict[str, Any] = field(default_factory=lambda: {"docling_version": "test"})


class SuccessfulEngine:
    def __init__(self, _profile: Any):
        pass

    def convert(self, _source: Path) -> FakeEngineResult:
        return FakeEngineResult()


def test_parse_document_publishes_complete_portable_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(artifacts_module, "DoclingEngine", SuccessfulEngine)
    source = tmp_path / "sample.docx"
    source.write_bytes(b"source")

    bundle = parse_document(source, tmp_path / "outputs", "local")

    assert bundle.profile_id == LOCAL_PROFILE_ID
    markdown = bundle.markdown_path.read_text(encoding="utf-8")
    assert markdown.endswith("\n")
    assert "\r" not in markdown
    assert "assets/picture.png" in markdown
    docling_json = json.loads(bundle.docling_json_path.read_text(encoding="utf-8"))
    assert docling_json["image"]["uri"] == "assets/picture.png"
    assert docling_json["text"] == "assets\\literal"
    assert (bundle.assets_dir / "picture.png").read_bytes() == b"png"
    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 3
    assert manifest["status"] == "success"
    assert manifest["bundle_id"] == bundle.bundle_id
    assert manifest["bundle_id"] != bundle.output_dir.name
    assert manifest["source"]["filename"] == source.name
    assert manifest["source"]["sha256"] == bundle.source_sha256
    assert "path" not in manifest["source"]
    assert manifest["profile"]["digest"] == bundle.profile_digest
    assert manifest["profile"]["options"]["ocr_provider"] == "local"
    assert manifest["artifacts"]["markdown"] == "document.md"


def test_parse_document_refuses_to_overwrite_existing_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(artifacts_module, "DoclingEngine", SuccessfulEngine)
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"source")
    output_dir = tmp_path / "outputs"
    parse_document(source, output_dir, "local")

    with pytest.raises(ParserError) as caught:
        parse_document(source, output_dir, "local")

    assert caught.value.code == "OUTPUT_EXISTS"


def test_unexpandable_source_path_is_returned_as_parser_error(tmp_path: Path) -> None:
    with pytest.raises(ParserError) as caught:
        parse_document(
            Path("~__ace3_missing_user__/sample.pdf"),
            tmp_path / "outputs",
            "local",
        )

    assert caught.value.code == "SOURCE_NOT_FOUND"


def test_source_symlink_is_rejected(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source")
    link = tmp_path / "linked.pdf"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("symlink를 만들 권한이 없습니다.")

    with pytest.raises(ParserError) as caught:
        parse_document(link, tmp_path / "outputs", "local")

    assert caught.value.code == "SOURCE_PATH_REDIRECTED"


def test_output_symlink_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(artifacts_module, "DoclingEngine", SuccessfulEngine)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source")
    outside = tmp_path / "outside"
    outside.mkdir()
    output_link = tmp_path / "outputs"
    try:
        output_link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink를 만들 권한이 없습니다.")

    with pytest.raises(ParserError) as caught:
        parse_document(source, output_link, "local")

    assert caught.value.code == "OUTPUT_PATH_REDIRECTED"
    assert not list(outside.iterdir())


def test_parse_failure_leaves_no_partial_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingEngine:
        def __init__(self, _profile: Any):
            pass

        def convert(self, _source: Path) -> FakeEngineResult:
            raise RuntimeError("synthetic failure")

    monkeypatch.setattr(artifacts_module, "DoclingEngine", FailingEngine)
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"source")
    output_dir = tmp_path / "outputs"

    with pytest.raises(ParserError) as caught:
        parse_document(source, output_dir, "local")

    assert caught.value.code == "PARSE_FAILED"
    assert not list(output_dir.glob("sample--*"))
    assert not list(output_dir.glob(".docling-parser-*"))


def test_source_read_error_is_returned_as_parser_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"source")
    monkeypatch.setattr(
        artifacts_module,
        "sha256_file",
        lambda _path: (_ for _ in ()).throw(OSError("read failed")),
    )

    with pytest.raises(ParserError) as caught:
        parse_document(source, tmp_path / "outputs", "local")

    assert caught.value.code == "SOURCE_UNAVAILABLE"


def test_naver_requires_confirmation_and_never_falls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingNaverEngine:
        def __init__(self, profile: Any):
            assert profile.id == NAVER_PROFILE_ID

        def convert(self, _source: Path) -> FakeEngineResult:
            raise NaverOcrError("NAVER OCR returned HTTP 503")

    monkeypatch.setattr(artifacts_module, "DoclingEngine", FailingNaverEngine)
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"source")
    output_dir = tmp_path / "outputs"

    with pytest.raises(ParserError) as not_confirmed:
        parse_document(source, output_dir, "naver")
    assert not_confirmed.value.code == "EXTERNAL_TRANSFER_NOT_CONFIRMED"

    with pytest.raises(ParserError) as failed:
        parse_document(
            source,
            output_dir,
            "naver",
            confirm_external_transfer=True,
        )
    assert failed.value.code == "NAVER_OCR_FAILED"
    assert not list(output_dir.glob("sample--*"))
