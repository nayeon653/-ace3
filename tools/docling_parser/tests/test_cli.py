from __future__ import annotations

import json
from pathlib import Path

import pytest

from docling_team_parser.cli import main
from docling_team_parser.errors import ParserError
from docling_team_parser.models import ConflictPolicy, FailurePolicy
from docling_team_parser.profiles import LOCAL_PROFILE_ID, NAVER_PROFILE_ID


class FakeService:
    def __init__(self) -> None:
        self.parse_requests = []
        self.batch_requests = []

    def list_profiles(self):
        return {"profiles": [{"id": LOCAL_PROFILE_ID}]}

    def doctor(self):
        return {"ok": True, "python": "3.11"}

    def parse(self, request):
        self.parse_requests.append(request)
        return {
            "status": "success",
            "markdown_path": "/artifacts/document.md",
            "stats": {"pages": 1},
        }

    def parse_batch(self, request):
        self.batch_requests.append(request)
        source_paths = request.source_paths or (Path("/documents/from-directory.pdf"),)
        return {
            "status": "success",
            "batch_manifest_path": "/artifacts/batches/batch.json",
            "total": len(source_paths),
            "succeeded": len(source_paths),
            "reused": 0,
            "failed": 0,
            "skipped": 0,
            "items": [
                {"source_path": str(source_path), "status": "success"}
                for source_path in source_paths
            ],
        }


def test_profiles_prints_machine_readable_json(capsys) -> None:
    assert main(["profiles"], service_factory=FakeService) == 0

    assert json.loads(capsys.readouterr().out) == {
        "profiles": [{"id": LOCAL_PROFILE_ID}]
    }


def test_doctor_prints_machine_readable_json(capsys) -> None:
    assert main(["doctor"], service_factory=FakeService) == 0

    assert json.loads(capsys.readouterr().out) == {"ok": True, "python": "3.11"}


def test_batch_failure_status_returns_nonzero_after_printing_json(capsys) -> None:
    class FailedBatchService(FakeService):
        def parse_batch(self, request):
            return {
                "status": "partial_success",
                "batch_manifest_path": "/artifacts/batches/batch.json",
                "total": 2,
                "succeeded": 1,
                "reused": 0,
                "failed": 1,
                "skipped": 0,
                "items": [],
            }

    exit_code = main(
        [
            "batch-local",
            "--source-dir",
            "/documents",
            "--output-dir",
            "/artifacts",
        ],
        service_factory=FailedBatchService,
    )

    assert exit_code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "partial_success"


def test_doctor_prints_failed_check_to_stdout_and_returns_nonzero(capsys) -> None:
    class UnhealthyService(FakeService):
        def doctor(self):
            return {"ok": False, "python": "3.11"}

    assert main(["doctor"], service_factory=UnhealthyService) == 1

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"ok": False, "python": "3.11"}
    assert captured.err == ""


def test_parse_local_pins_local_profile_and_maps_options(capsys) -> None:
    fake = FakeService()

    exit_code = main(
        [
            "parse-local",
            "/documents/report.pptx",
            "--output-dir",
            "/artifacts",
            "--conflict-policy",
            "reuse_identical",
        ],
        service_factory=lambda: fake,
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["markdown_path"] == "/artifacts/document.md"
    request = fake.parse_requests[0]
    assert request.source_path == Path("/documents/report.pptx")
    assert request.profile_id == LOCAL_PROFILE_ID
    assert request.output_dir == Path("/artifacts")
    assert request.conflict_policy is ConflictPolicy.REUSE_IDENTICAL
    assert request.confirm_external_transfer is False


def test_parse_naver_pins_naver_profile_after_explicit_confirmation(capsys) -> None:
    fake = FakeService()

    exit_code = main(
        [
            "parse-naver",
            "/documents/report.pdf",
            "--confirm-external-transfer",
            "--output-dir",
            "/artifacts",
        ],
        service_factory=lambda: fake,
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "success"
    request = fake.parse_requests[0]
    assert request.profile_id == NAVER_PROFILE_ID
    assert request.confirm_external_transfer is True


def test_batch_local_accepts_repeated_paths_and_maps_all_policies(capsys) -> None:
    fake = FakeService()

    exit_code = main(
        [
            "batch-local",
            "--source-path",
            "/documents/a.pdf",
            "--source-path",
            "/documents/b.docx",
            "--output-dir",
            "/artifacts",
            "--failure-policy",
            "stop",
            "--conflict-policy",
            "reuse_identical",
        ],
        service_factory=lambda: fake,
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["total"] == 2
    assert output["skipped"] == 0
    assert [item["status"] for item in output["items"]] == ["success", "success"]
    request = fake.batch_requests[0]
    assert request.profile_id == LOCAL_PROFILE_ID
    assert request.source_paths == (
        Path("/documents/a.pdf"),
        Path("/documents/b.docx"),
    )
    assert request.source_dir is None
    assert request.output_dir == Path("/artifacts")
    assert request.failure_policy is FailurePolicy.STOP
    assert request.conflict_policy is ConflictPolicy.REUSE_IDENTICAL
    assert request.confirm_external_transfer is False


def test_batch_cli_prints_skipped_items_and_accounting(capsys) -> None:
    class StoppedService(FakeService):
        def parse_batch(self, request):
            self.batch_requests.append(request)
            return {
                "status": "failed",
                "batch_manifest_path": "/artifacts/batches/batch.json",
                "total": 2,
                "succeeded": 0,
                "reused": 0,
                "failed": 1,
                "skipped": 1,
                "items": [
                    {"source_path": "/documents/a.pdf", "status": "failed"},
                    {"source_path": "/documents/b.pdf", "status": "skipped"},
                ],
            }

    exit_code = main(
        [
            "batch-local",
            "--source-path",
            "/documents/a.pdf",
            "--source-path",
            "/documents/b.pdf",
            "--failure-policy",
            "stop",
            "--output-dir",
            "/artifacts",
        ],
        service_factory=StoppedService,
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["total"] == (
        output["succeeded"] + output["reused"] + output["failed"] + output["skipped"]
    )
    assert [item["status"] for item in output["items"]] == ["failed", "skipped"]


def test_batch_local_defaults_to_continue(capsys) -> None:
    fake = FakeService()

    assert (
        main(
            [
                "batch-local",
                "--source-dir",
                "/documents",
                "--output-dir",
                "/artifacts",
            ],
            service_factory=lambda: fake,
        )
        == 0
    )

    capsys.readouterr()
    assert fake.batch_requests[0].failure_policy is FailurePolicy.CONTINUE


def test_batch_naver_uses_directory_recursion_and_defaults_to_stop(capsys) -> None:
    fake = FakeService()

    exit_code = main(
        [
            "batch-naver",
            "--source-dir",
            "/documents",
            "--recursive",
            "--confirm-external-transfer",
            "--output-dir",
            "/artifacts",
        ],
        service_factory=lambda: fake,
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "success"
    request = fake.batch_requests[0]
    assert request.profile_id == NAVER_PROFILE_ID
    assert request.source_paths == ()
    assert request.source_dir == Path("/documents")
    assert request.recursive is True
    assert request.failure_policy is FailurePolicy.STOP
    assert request.confirm_external_transfer is True


def test_batch_naver_allows_explicit_continue_policy(capsys) -> None:
    fake = FakeService()

    assert (
        main(
            [
                "batch-naver",
                "--source-path",
                "/documents/a.xlsx",
                "--failure-policy",
                "continue",
                "--confirm-external-transfer",
                "--output-dir",
                "/artifacts",
            ],
            service_factory=lambda: fake,
        )
        == 0
    )

    capsys.readouterr()
    assert fake.batch_requests[0].failure_policy is FailurePolicy.CONTINUE


@pytest.mark.parametrize(
    "argv",
    [
        [
            "parse-naver",
            "/documents/report.pdf",
            "--output-dir",
            "/artifacts",
        ],
        [
            "batch-naver",
            "--source-dir",
            "/documents",
            "--output-dir",
            "/artifacts",
        ],
    ],
)
def test_naver_commands_require_external_transfer_flag(argv, capsys) -> None:
    with pytest.raises(SystemExit) as caught:
        main(argv, service_factory=lambda: pytest.fail("service must not be created"))

    assert caught.value.code == 2
    assert "--confirm-external-transfer" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["batch-local", "--output-dir", "/artifacts"],
        [
            "batch-local",
            "--source-path",
            "/documents/a.pdf",
            "--source-dir",
            "/documents",
            "--output-dir",
            "/artifacts",
        ],
    ],
)
def test_batch_requires_exactly_one_source_kind(argv, capsys) -> None:
    with pytest.raises(SystemExit) as caught:
        main(argv, service_factory=lambda: pytest.fail("service must not be created"))

    assert caught.value.code == 2
    assert "--source-path" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["parse", "/documents/a.pdf"],
        [
            "parse-local",
            "/documents/a.pdf",
            "--profile",
            NAVER_PROFILE_ID,
            "--output-dir",
            "/artifacts",
        ],
    ],
)
def test_cli_does_not_expose_arbitrary_profile_selection(argv, capsys) -> None:
    with pytest.raises(SystemExit) as caught:
        main(argv, service_factory=lambda: pytest.fail("service must not be created"))

    assert caught.value.code == 2
    assert capsys.readouterr().err


def test_cli_parser_errors_are_structured_and_go_to_stderr(capsys) -> None:
    class FailingService(FakeService):
        def parse(self, request):
            raise ParserError("TEST_FAILURE", "expected failure")

    exit_code = main(
        [
            "parse-local",
            "/documents/report.xlsx",
            "--output-dir",
            "/artifacts",
        ],
        service_factory=FailingService,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert exit_code == 2
    assert json.loads(captured.err)["error"] == {
        "code": "TEST_FAILURE",
        "failure_manifest_path": None,
        "message": "expected failure",
    }


def test_unexpected_cli_errors_are_structured_and_go_to_stderr(capsys) -> None:
    class BrokenService(FakeService):
        def doctor(self):
            raise RuntimeError("synthetic failure")

    exit_code = main(["doctor"], service_factory=BrokenService)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert exit_code == 1
    assert json.loads(captured.err) == {
        "error": {"code": "INTERNAL_ERROR", "message": "synthetic failure"}
    }


@pytest.mark.parametrize(
    "argv",
    [
        ["parse-local", "/documents/report.pdf"],
        ["batch-local", "--source-dir", "/documents"],
    ],
)
def test_parse_commands_require_output_dir(argv, capsys) -> None:
    with pytest.raises(SystemExit) as caught:
        main(argv, service_factory=lambda: pytest.fail("service must not be created"))

    assert caught.value.code == 2
    assert "--output-dir" in capsys.readouterr().err
