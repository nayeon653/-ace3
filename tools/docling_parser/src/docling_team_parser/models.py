"""요청, 결과, 프로필 및 매니페스트 계약."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx", ".pptx", ".xlsx"})


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OcrProvider(StrEnum):
    LOCAL = "local"
    NAVER = "naver"


class ConflictPolicy(StrEnum):
    ERROR = "error"
    REUSE_IDENTICAL = "reuse_identical"


class FailurePolicy(StrEnum):
    CONTINUE = "continue"
    STOP = "stop"


class ParserProfile(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    version: int = 1
    description: str
    ocr_provider: OcrProvider
    external_data_transfer: bool
    ocr_mode: Literal[
        "full_page", "layout_regions", "pdf_aware_layout_regions", "default"
    ]
    office_picture_ocr_mode: Literal["full_page"] = "full_page"
    office_picture_image_scale: float = Field(default=1.0, gt=0)
    languages: tuple[str, ...] = ("ko", "en")
    accelerator_device: Literal["cpu", "auto"] = "cpu"
    accelerator_threads: int = Field(default=4, ge=1, le=64)
    images_scale: float = Field(default=2.0, gt=0)
    table_mode: Literal["accurate", "fast"] = "accurate"
    layout_model_repo_id: str
    layout_model_revision: str
    do_table_structure: bool = True
    generate_picture_images: bool = True
    export_images: bool = True
    traverse_pictures: bool = True
    local_confidence_threshold: float | None = Field(default=None, ge=0, le=1)
    local_image_scale: float | None = Field(default=None, gt=0)
    naver_api_version: Literal["V2"] | None = None
    naver_image_scale: float | None = Field(default=None, gt=0)
    naver_timeout_seconds: float | None = Field(default=None, gt=0)
    naver_max_attempts: int | None = Field(default=None, ge=1, le=5)
    naver_enable_table_detection: bool | None = None
    naver_max_image_edge: int | None = Field(default=None, ge=1)
    naver_max_image_bytes: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_provider_fields(self) -> ParserProfile:
        if self.ocr_provider is OcrProvider.NAVER:
            if not self.external_data_transfer:
                raise ValueError("NAVER profiles must declare external data transfer")
            required = (
                self.naver_api_version,
                self.naver_image_scale,
                self.naver_timeout_seconds,
                self.naver_max_attempts,
                self.naver_enable_table_detection,
                self.naver_max_image_edge,
                self.naver_max_image_bytes,
            )
            if any(value is None for value in required):
                raise ValueError("NAVER profiles require all NAVER request settings")
        elif self.external_data_transfer:
            raise ValueError("local profiles cannot declare external data transfer")
        elif self.local_confidence_threshold is None or self.local_image_scale is None:
            raise ValueError(
                "local profiles require confidence threshold and image scale"
            )
        return self

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"


class ParseRequest(StrictModel):
    source_path: Path
    profile_id: str
    output_dir: Path | None = None
    conflict_policy: ConflictPolicy = ConflictPolicy.ERROR
    confirm_external_transfer: bool = False


class BatchRequest(StrictModel):
    profile_id: str
    source_paths: tuple[Path, ...] = ()
    source_dir: Path | None = None
    recursive: bool = False
    output_dir: Path | None = None
    failure_policy: FailurePolicy = FailurePolicy.CONTINUE
    conflict_policy: ConflictPolicy = ConflictPolicy.ERROR
    confirm_external_transfer: bool = False

    @model_validator(mode="after")
    def exactly_one_source(self) -> BatchRequest:
        if bool(self.source_paths) == bool(self.source_dir):
            raise ValueError("provide exactly one of source_paths or source_dir")
        return self


class ParseStats(StrictModel):
    pages: int = 0
    pictures_found: int = 0
    office_pictures_ocrd: int = 0
    elapsed_ms: int = 0


class ParseResult(StrictModel):
    status: Literal["success", "reused"]
    run_id: str
    source_path: Path
    source_sha256: str
    profile_id: str
    profile_digest: str
    output_dir: Path
    markdown_path: Path
    docling_json_path: Path
    manifest_path: Path
    assets_dir: Path
    markdown_sha256: str
    docling_json_sha256: str
    assets_sha256: str
    warnings: tuple[str, ...] = ()
    stats: ParseStats


class BatchItemResult(StrictModel):
    source_path: Path
    status: Literal["success", "reused", "failed", "skipped"]
    result: ParseResult | None = None
    error_code: str | None = None
    error_message: str | None = None
    failure_manifest_path: Path | None = None


class BatchResult(StrictModel):
    status: Literal["success", "partial_success", "failed"]
    batch_id: str
    profile_id: str
    profile_digest: str
    total: int
    succeeded: int
    reused: int
    failed: int
    skipped: int
    items: tuple[BatchItemResult, ...]
    batch_manifest_path: Path

    @model_validator(mode="after")
    def validate_accounting(self) -> BatchResult:
        expected_counts = {
            status: sum(item.status == status for item in self.items)
            for status in ("success", "reused", "failed", "skipped")
        }
        actual_counts = {
            "success": self.succeeded,
            "reused": self.reused,
            "failed": self.failed,
            "skipped": self.skipped,
        }
        if actual_counts != expected_counts:
            raise ValueError("batch counters must match item statuses")
        if self.total != len(self.items):
            raise ValueError("batch total must match the number of items")
        return self


class RunManifest(StrictModel):
    schema_version: Literal[2] = 2
    status: Literal["success", "failed"]
    run_id: str
    source: dict[str, Any]
    profile: dict[str, Any]
    runtime: dict[str, Any]
    artifacts: dict[str, Any]
    stats: dict[str, Any]
    warnings: list[str]
    error: dict[str, Any] | None = None
    started_at: datetime
    finished_at: datetime
