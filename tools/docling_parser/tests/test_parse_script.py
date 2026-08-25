from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from docling_team_parser.errors import ParserError

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "parse_document.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("parse_document_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_maps_local_arguments_and_prints_success_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script()
    captured: dict[str, Any] = {}

    def fake_parse(
        source_path: Path,
        output_dir: Path,
        ocr_provider: str,
        *,
        confirm_external_transfer: bool,
    ) -> SimpleNamespace:
        captured.update(
            source_path=source_path,
            output_dir=output_dir,
            ocr_provider=ocr_provider,
            confirm_external_transfer=confirm_external_transfer,
        )
        return SimpleNamespace(to_dict=lambda: {"profile_id": "local-profile"})

    monkeypatch.setattr(module, "parse_document", fake_parse)
    source = tmp_path / "sample.pdf"
    output = tmp_path / "outputs"

    exit_code = module.main([str(source), "--ocr", "local", "--output-dir", str(output)])

    assert exit_code == 0
    assert captured == {
        "source_path": source,
        "output_dir": output,
        "ocr_provider": "local",
        "confirm_external_transfer": False,
    }
    assert json.loads(capsys.readouterr().out) == {
        "status": "success",
        "bundle": {"profile_id": "local-profile"},
    }


def test_script_passes_naver_transfer_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script()
    captured: dict[str, Any] = {}

    def fake_parse(
        _source_path: Path,
        _output_dir: Path,
        ocr_provider: str,
        *,
        confirm_external_transfer: bool,
    ) -> SimpleNamespace:
        captured.update(
            ocr_provider=ocr_provider,
            confirm_external_transfer=confirm_external_transfer,
        )
        return SimpleNamespace(to_dict=dict)

    monkeypatch.setattr(module, "parse_document", fake_parse)

    exit_code = module.main(
        [
            str(tmp_path / "sample.pdf"),
            "--ocr",
            "naver",
            "--confirm-external-transfer",
            "--output-dir",
            str(tmp_path / "outputs"),
        ]
    )

    assert exit_code == 0
    assert captured == {
        "ocr_provider": "naver",
        "confirm_external_transfer": True,
    }


def test_script_accepts_no_ocr_formula_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script()
    captured: dict[str, Any] = {}

    def fake_parse(
        _source_path: Path,
        _output_dir: Path,
        ocr_provider: str,
        *,
        confirm_external_transfer: bool,
    ) -> SimpleNamespace:
        captured.update(
            ocr_provider=ocr_provider,
            confirm_external_transfer=confirm_external_transfer,
        )
        return SimpleNamespace(to_dict=dict)

    monkeypatch.setattr(module, "parse_document", fake_parse)

    exit_code = module.main(
        [
            str(tmp_path / "sample.pdf"),
            "--ocr",
            "none",
            "--output-dir",
            str(tmp_path / "outputs"),
        ]
    )

    assert exit_code == 0
    assert captured == {
        "ocr_provider": "none",
        "confirm_external_transfer": False,
    }


def test_script_prints_parser_error_as_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script()

    def fake_parse(*_args: Any, **_kwargs: Any) -> None:
        raise ParserError("SYNTHETIC_ERROR", "synthetic failure")

    monkeypatch.setattr(module, "parse_document", fake_parse)

    exit_code = module.main(
        [str(tmp_path / "sample.pdf"), "--output-dir", str(tmp_path / "outputs")]
    )

    streams = capsys.readouterr()
    assert exit_code == 1
    assert streams.out == ""
    assert json.loads(streams.err) == {
        "status": "failed",
        "error": {"code": "SYNTHETIC_ERROR", "message": "synthetic failure"},
    }
