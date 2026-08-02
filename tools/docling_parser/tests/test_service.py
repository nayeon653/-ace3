from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import docling_team_parser.docling_engine as engine_module
import docling_team_parser.service as service_module
from docling_team_parser.errors import NaverOcrError, ParserError
from docling_team_parser.models import (
    BatchRequest,
    ConflictPolicy,
    FailurePolicy,
    ParseRequest,
)
from docling_team_parser.profiles import LOCAL_PROFILE_ID, NAVER_PROFILE_ID, get_profile
from docling_team_parser.service import ParserService
from docling_team_parser.settings import RuntimeSettings


class FakeDocument:
    def save_as_markdown(
        self,
        filename: Path,
        *,
        artifacts_dir: Path,
        **_kwargs: Any,
    ) -> None:
        assert artifacts_dir == Path("assets")
        asset_dir = filename.parent / artifacts_dir
        asset_dir.mkdir(parents=True, exist_ok=True)
        (asset_dir / "picture.png").write_bytes(b"png")
        filename.write_text(
            "# Parsed\r\n\r\n![image](assets/picture.png)", encoding="utf-8"
        )

    def save_as_json(
        self,
        filename: Path,
        *,
        artifacts_dir: Path,
        **_kwargs: Any,
    ) -> None:
        assert artifacts_dir == Path("assets")
        filename.write_text('{"schema_name":"DoclingDocument"}', encoding="utf-8")


@dataclass
class FakeEngineResult:
    document: Any = field(default_factory=FakeDocument)
    pages: int = 2
    pictures_found: int = 1
    office_pictures_ocrd: int = 1
    warnings: list[str] | None = None
    conversion_version: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.warnings = self.warnings or []
        self.conversion_version = self.conversion_version or {"docling_version": "test"}


class SuccessfulEngine:
    def __init__(self, _profile: Any):
        pass

    def convert(self, _source: Path) -> FakeEngineResult:
        return FakeEngineResult()


def service_for(root: Path) -> ParserService:
    return ParserService(
        RuntimeSettings(
            allowed_roots=(root.resolve(),),
            default_output_root=(root / "outputs").resolve(),
        )
    )


def test_parse_publishes_complete_artifacts_and_reuses_by_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine_module, "DoclingEngine", SuccessfulEngine)
    source = tmp_path / "sample.docx"
    source.write_bytes(b"source")
    service = service_for(tmp_path)

    first = service.parse(ParseRequest(source_path=source, profile_id=LOCAL_PROFILE_ID))

    assert first.status == "success"
    assert first.markdown_path.read_text(encoding="utf-8").endswith("\n")
    assert "\r" not in first.markdown_path.read_text(encoding="utf-8")
    assert (first.assets_dir / "picture.png").read_bytes() == b"png"
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["source"]["sha256"] == first.source_sha256
    assert manifest["profile"]["digest"] == first.profile_digest
    assert manifest["profile"]["effective_options"]["ocr_provider"] == "local"
    assert manifest["runtime"]["packages"]["docling"]
    assert manifest["runtime"]["packages"]["torch"]

    reused = service.parse(
        ParseRequest(
            source_path=source,
            profile_id=LOCAL_PROFILE_ID,
            conflict_policy=ConflictPolicy.REUSE_IDENTICAL,
        )
    )
    assert reused.status == "reused"
    assert reused.run_id == first.run_id


def test_profile_objects_are_frozen() -> None:
    profile = get_profile(LOCAL_PROFILE_ID)

    with pytest.raises(ValidationError):
        profile.images_scale = 9.0  # type: ignore[misc]


def test_reuse_rejects_corrupt_manifest_as_output_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine_module, "DoclingEngine", SuccessfulEngine)
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"source")
    service = service_for(tmp_path)
    first = service.parse(ParseRequest(source_path=source, profile_id=LOCAL_PROFILE_ID))
    first.manifest_path.write_text("{broken", encoding="utf-8")

    with pytest.raises(ParserError, match="OUTPUT_CONFLICT"):
        service.parse(
            ParseRequest(
                source_path=source,
                profile_id=LOCAL_PROFILE_ID,
                conflict_policy=ConflictPolicy.REUSE_IDENTICAL,
            )
        )


def test_failure_only_publishes_failure_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingEngine:
        def __init__(self, _profile: Any):
            pass

        def convert(self, _source: Path) -> FakeEngineResult:
            raise RuntimeError("synthetic failure")

    monkeypatch.setattr(engine_module, "DoclingEngine", FailingEngine)
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"pdf")
    service = service_for(tmp_path)

    with pytest.raises(ParserError) as caught:
        service.parse(ParseRequest(source_path=source, profile_id=LOCAL_PROFILE_ID))

    assert caught.value.code == "PARSE_FAILED"
    assert caught.value.failure_manifest_path is not None
    failure_manifest = json.loads(
        caught.value.failure_manifest_path.read_text(encoding="utf-8")
    )
    assert failure_manifest["status"] == "failed"
    assert failure_manifest["artifacts"] == {}
    assert not list((tmp_path / "outputs").glob("sample--*"))
    assert not list((tmp_path / "outputs").glob(".docling-parser-*"))


def test_failure_manifest_write_error_does_not_mask_parse_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingEngine:
        def __init__(self, _profile: Any):
            pass

        def convert(self, _source: Path) -> FakeEngineResult:
            raise RuntimeError("original parse failure")

    monkeypatch.setattr(engine_module, "DoclingEngine", FailingEngine)
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"pdf")
    service = service_for(tmp_path)
    monkeypatch.setattr(
        service,
        "_write_failure_manifest",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(ParserError) as caught:
        service.parse(ParseRequest(source_path=source, profile_id=LOCAL_PROFILE_ID))

    assert caught.value.code == "PARSE_FAILED"
    assert caught.value.message == "original parse failure"
    assert caught.value.failure_manifest_path is None


def test_failure_manifest_does_not_follow_redirected_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingEngine:
        def __init__(self, _profile: Any):
            pass

        def convert(self, _source: Path) -> FakeEngineResult:
            raise RuntimeError("original parse failure")

    monkeypatch.setattr(engine_module, "DoclingEngine", FailingEngine)
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"pdf")
    output_root = tmp_path / "outputs"
    outside = tmp_path / "outside"
    output_root.mkdir()
    outside.mkdir()
    (output_root / "failures").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ParserError) as caught:
        service_for(tmp_path).parse(
            ParseRequest(source_path=source, profile_id=LOCAL_PROFILE_ID)
        )

    assert caught.value.code == "PARSE_FAILED"
    assert caught.value.failure_manifest_path is None
    assert not list(outside.iterdir())


def test_naver_failure_is_document_atomic_and_has_no_local_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingNaverEngine:
        def __init__(self, profile: Any):
            assert profile.id == NAVER_PROFILE_ID

        def convert(self, _source: Path) -> FakeEngineResult:
            raise NaverOcrError("NAVER OCR returned HTTP 503 after 3 attempt(s)")

    monkeypatch.setattr(engine_module, "DoclingEngine", FailingNaverEngine)
    monkeypatch.setenv("DOCLING_PARSER_ENABLE_NAVER_OCR", "true")
    monkeypatch.setenv(
        "NAVER_OCR_INVOKE_URL",
        "https://example.apigw.ntruss.com/custom/v1/domain-id/invoke-key/general",
    )
    monkeypatch.setenv("NAVER_OCR_SECRET", "not-a-real-secret")
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"pdf")
    service = service_for(tmp_path)

    with pytest.raises(ParserError) as caught:
        service.parse(
            ParseRequest(
                source_path=source,
                profile_id=NAVER_PROFILE_ID,
                confirm_external_transfer=True,
            )
        )

    assert caught.value.code == "NAVER_OCR_FAILED"
    assert not list((tmp_path / "outputs").glob("sample--*"))
    payload = caught.value.failure_manifest_path.read_text(encoding="utf-8")
    assert "not-a-real-secret" not in payload


def test_external_transfer_must_be_confirmed_before_parsing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCLING_PARSER_ENABLE_NAVER_OCR", "true")
    monkeypatch.setenv(
        "NAVER_OCR_INVOKE_URL",
        "https://example.apigw.ntruss.com/custom/v1/domain-id/invoke-key/general",
    )
    monkeypatch.setenv("NAVER_OCR_SECRET", "secret")
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"pdf")

    with pytest.raises(ParserError, match="EXTERNAL_TRANSFER_NOT_CONFIRMED"):
        service_for(tmp_path).parse(
            ParseRequest(source_path=source, profile_id=NAVER_PROFILE_ID)
        )


def test_source_symlink_cannot_escape_allowed_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"pdf")
    link = allowed / "linked.pdf"
    link.symlink_to(outside)
    service = service_for(allowed)

    with pytest.raises(ParserError, match="PATH_OUTSIDE_ALLOWED_ROOT"):
        service.parse(ParseRequest(source_path=link, profile_id=LOCAL_PROFILE_ID))


def test_source_symlink_loop_returns_stable_source_error(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.symlink_to(second)
    second.symlink_to(first)

    with pytest.raises(ParserError) as caught:
        service_for(tmp_path).parse(
            ParseRequest(source_path=first, profile_id=LOCAL_PROFILE_ID)
        )

    assert caught.value.code == "SOURCE_NOT_FOUND"


def test_batch_stop_keeps_completed_document_and_stops_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SelectiveEngine:
        def __init__(self, _profile: Any):
            pass

        def convert(self, source: Path) -> FakeEngineResult:
            if source.name == "b.pdf":
                raise RuntimeError("fail b")
            return FakeEngineResult()

    monkeypatch.setattr(engine_module, "DoclingEngine", SelectiveEngine)
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        (tmp_path / name).write_bytes(name.encode())
    service = service_for(tmp_path)

    result = service.parse_batch(
        BatchRequest(
            profile_id=LOCAL_PROFILE_ID,
            source_paths=tuple(tmp_path / name for name in ("c.pdf", "b.pdf", "a.pdf")),
            failure_policy=FailurePolicy.STOP,
        )
    )

    assert result.status == "partial_success"
    assert [item.source_path.name for item in result.items] == [
        "a.pdf",
        "b.pdf",
        "c.pdf",
    ]
    assert [item.status for item in result.items] == [
        "success",
        "failed",
        "skipped",
    ]
    assert result.succeeded == 1
    assert result.reused == 0
    assert result.failed == 1
    assert result.skipped == 1
    assert result.profile_digest == get_profile(LOCAL_PROFILE_ID).digest
    assert result.total == 3
    assert result.total == (
        result.succeeded + result.reused + result.failed + result.skipped
    )
    assert result.batch_manifest_path.is_file()
    manifest = json.loads(result.batch_manifest_path.read_text(encoding="utf-8"))
    assert manifest["skipped"] == 1
    assert [item["status"] for item in manifest["items"]] == [
        "success",
        "failed",
        "skipped",
    ]


def test_batch_stop_first_failure_is_failed_and_remaining_sources_are_skipped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine_module, "DoclingEngine", SuccessfulEngine)
    missing = tmp_path / "a-missing.pdf"
    unattempted = tmp_path / "b-unattempted.pdf"
    unattempted.write_bytes(b"pdf")

    result = service_for(tmp_path).parse_batch(
        BatchRequest(
            profile_id=LOCAL_PROFILE_ID,
            source_paths=(unattempted, missing),
            failure_policy=FailurePolicy.STOP,
        )
    )

    assert result.status == "failed"
    assert [item.source_path.name for item in result.items] == [
        "a-missing.pdf",
        "b-unattempted.pdf",
    ]
    assert [item.status for item in result.items] == ["failed", "skipped"]
    assert result.succeeded == 0
    assert result.reused == 0
    assert result.failed == 1
    assert result.skipped == 1
    assert result.total == 2
    assert not list((tmp_path / "outputs").glob("b-unattempted--*"))


def test_batch_manifest_does_not_follow_redirected_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine_module, "DoclingEngine", SuccessfulEngine)
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"pdf")
    output_root = tmp_path / "outputs"
    outside = tmp_path / "outside"
    output_root.mkdir()
    outside.mkdir()
    (output_root / "batches").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ParserError) as caught:
        service_for(tmp_path).parse_batch(
            BatchRequest(
                profile_id=LOCAL_PROFILE_ID,
                source_paths=(source,),
            )
        )

    assert caught.value.code == "OUTPUT_CONFLICT"
    assert not list(outside.iterdir())


def test_batch_continue_reports_bad_explicit_path_and_parses_good_item(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine_module, "DoclingEngine", SuccessfulEngine)
    good = tmp_path / "good.pdf"
    missing = tmp_path / "missing.pdf"
    good.write_bytes(b"pdf")

    result = service_for(tmp_path).parse_batch(
        BatchRequest(
            profile_id=LOCAL_PROFILE_ID,
            source_paths=(missing, good),
            failure_policy=FailurePolicy.CONTINUE,
        )
    )

    assert result.status == "partial_success"
    assert result.succeeded == 1
    assert result.failed == 1
    assert result.skipped == 0
    by_name = {item.source_path.name: item for item in result.items}
    assert by_name["missing.pdf"].error_code == "SOURCE_NOT_FOUND"
    assert by_name["good.pdf"].status == "success"


def test_batch_continue_survives_source_hash_read_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine_module, "DoclingEngine", SuccessfulEngine)
    bad = tmp_path / "bad.pdf"
    good = tmp_path / "good.pdf"
    bad.write_bytes(b"bad")
    good.write_bytes(b"good")
    real_sha256_file = service_module.sha256_file

    def selective_hash(path: Path) -> str:
        if path == bad:
            raise PermissionError("synthetic read failure")
        return real_sha256_file(path)

    monkeypatch.setattr(service_module, "sha256_file", selective_hash)

    result = service_for(tmp_path).parse_batch(
        BatchRequest(
            profile_id=LOCAL_PROFILE_ID,
            source_paths=(bad, good),
            failure_policy=FailurePolicy.CONTINUE,
        )
    )

    assert result.status == "partial_success"
    assert result.succeeded == 1
    assert result.failed == 1
    assert result.skipped == 0
    by_name = {item.source_path.name: item for item in result.items}
    assert by_name["bad.pdf"].error_code == "SOURCE_UNAVAILABLE"
    assert by_name["good.pdf"].status == "success"


def test_doctor_reports_credential_presence_without_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "NAVER_OCR_INVOKE_URL",
        "https://example.apigw.ntruss.com/custom/v1/domain-id/invoke-key/general",
    )
    monkeypatch.setenv("NAVER_OCR_SECRET", "sensitive-secret")

    payload = service_for(tmp_path).doctor()
    serialized = json.dumps(payload)

    assert payload["naver_environment"]["invoke_url_present"] is True
    assert payload["naver_environment"]["secret_present"] is True
    assert "example.apigw.ntruss.com" not in serialized
    assert "sensitive-secret" not in serialized


def test_doctor_rejects_invalid_url_when_naver_is_explicitly_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCLING_PARSER_ENABLE_NAVER_OCR", "true")
    monkeypatch.setenv(
        "NAVER_OCR_INVOKE_URL",
        "http://example.apigw.ntruss.com/custom/v1/domain-id/invoke-key/general",
    )
    monkeypatch.setenv("NAVER_OCR_SECRET", "secret")

    payload = service_for(tmp_path).doctor()
    naver_profile = next(
        profile for profile in payload["profiles"] if profile["ocr_provider"] == "naver"
    )

    assert payload["ok"] is False
    assert naver_profile["available"] is False
    assert naver_profile["unavailable_reason"] == (
        "NAVER_OCR_INVOKE_URL must be an absolute HTTPS URL"
    )


def test_doctor_rejects_default_output_outside_allowed_roots(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    service = ParserService(
        RuntimeSettings(
            allowed_roots=(allowed.resolve(),),
            default_output_root=(tmp_path / "outside-output").resolve(),
        )
    )

    payload = service.doctor()

    assert payload["ok"] is False
    assert payload["output_configuration_valid"] is False
    assert payload["output_configuration_error"]["code"] == (
        "PATH_OUTSIDE_ALLOWED_ROOT"
    )


def test_doctor_rejects_output_below_an_existing_file(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("blocker", encoding="utf-8")
    service = ParserService(
        RuntimeSettings(
            allowed_roots=(tmp_path.resolve(),),
            default_output_root=blocker / "outputs",
        )
    )

    payload = service.doctor()

    assert payload["ok"] is False
    assert payload["output_parent_is_directory"] is False
    assert payload["output_configuration_error"]["code"] == "OUTPUT_NOT_DIRECTORY"
