"""Docling OCR plugin backed by NAVER CLOVA General OCR V2."""

from __future__ import annotations

import json
import math
import os
import threading
import time
import uuid
from collections.abc import Iterable
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from typing import Any, ClassVar, Literal

import httpx
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import Page
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import OcrOptions
from docling.datamodel.settings import settings
from docling.models.base_ocr_model import BaseOcrModel
from docling.utils.profiling import TimeRecorder
from docling_core.types.doc import BoundingBox, CoordOrigin
from docling_core.types.doc.page import BoundingRectangle, TextCell
from PIL import Image
from pydantic import Field

from docling_team_parser.errors import NaverOcrError
from docling_team_parser.ocr.config import validate_naver_invoke_url

_RETRY_BACKOFF_SECONDS = 0.25
_SUPPORTED_REQUEST_LANGUAGES = frozenset({"ko", "ja", "zh-TW"})


class NaverOcrOptions(OcrOptions):
    """Configuration exposed to Docling's OCR factory.

    The invoke URL and secret deliberately are not option fields. They are read from
    the process environment only when an enabled model is initialized.
    """

    kind: ClassVar[Literal["naver_ocr"]] = "naver_ocr"
    lang: list[str] = Field(default_factory=lambda: ["ko"])
    scale: float = Field(default=3.0, gt=0.0)
    timeout_seconds: float = Field(default=60.0, gt=0.0)
    max_attempts: int = Field(default=3, ge=1, le=5)
    enable_table_detection: bool = False
    max_image_edge: int = Field(default=7_900, ge=1, le=7_999)
    max_image_bytes: int = Field(default=49_000_000, ge=1, le=50_000_000)


class NaverOcrModel(BaseOcrModel):
    """Synchronous NAVER CLOVA General OCR V2 adapter for Docling."""

    def __init__(
        self,
        enabled: bool,
        artifacts_path: Path | None,
        options: NaverOcrOptions,
        accelerator_options: AcceleratorOptions,
    ) -> None:
        super().__init__(
            enabled=enabled,
            artifacts_path=artifacts_path,
            options=options,
            accelerator_options=accelerator_options,
        )
        self.options: NaverOcrOptions
        self._invoke_url: str | None = None
        self._secret: str | None = None
        self._client: httpx.Client | None = None
        self._fatal_error_message: str | None = None
        self._request_lock = threading.Lock()

        if self.enabled:
            invoke_url = os.environ.get("NAVER_OCR_INVOKE_URL", "")
            secret = os.environ.get("NAVER_OCR_SECRET", "").strip()
            if not invoke_url:
                raise NaverOcrError("NAVER_OCR_INVOKE_URL is not configured")
            if not secret:
                raise NaverOcrError("NAVER_OCR_SECRET is not configured")
            try:
                invoke_url = validate_naver_invoke_url(invoke_url)
            except ValueError as exc:
                raise NaverOcrError(str(exc)) from None

            self._invoke_url = invoke_url
            self._secret = secret
            self._client = httpx.Client(
                timeout=self.options.timeout_seconds,
                follow_redirects=False,
            )

    def __call__(
        self,
        conv_res: ConversionResult,
        page_batch: Iterable[Page],
    ) -> Iterable[Page]:
        if not self.enabled:
            yield from page_batch
            return

        for page in page_batch:
            assert page._backend is not None
            if not page._backend.is_valid():
                yield page
                continue

            with TimeRecorder(conv_res, "ocr"):
                ocr_rects = self.get_ocr_rects(page)
                all_ocr_cells: list[TextCell] = []

                for ocr_rect in ocr_rects:
                    if ocr_rect.area() == 0:
                        continue

                    with self._request_lock:
                        if self._fatal_error_message is not None:
                            raise NaverOcrError(self._fatal_error_message)

                    image = page._backend.get_page_image(
                        scale=self.options.scale,
                        cropbox=ocr_rect,
                    )
                    try:
                        with self._request_lock:
                            if self._fatal_error_message is not None:
                                raise NaverOcrError(self._fatal_error_message)
                            try:
                                payload = self._request_ocr(image)
                                cells = self._response_to_cells(
                                    payload,
                                    ocr_rect,
                                    start_index=len(all_ocr_cells),
                                )
                            except NaverOcrError as exc:
                                # Docling's threaded stage records page failures and
                                # may continue with later batches. Latch the first
                                # fatal remote failure so later batches make no more
                                # billable requests for a doomed document.
                                self._fatal_error_message = str(exc)
                                raise
                        all_ocr_cells.extend(cells)
                    finally:
                        image.close()

                # Deliberately run this only after every request and response has
                # succeeded. Any NaverOcrError escapes and fails the conversion.
                self.post_process_cells(all_ocr_cells, page, conv_res)

            if settings.debug.visualize_ocr:
                self.draw_ocr_rects_and_cells(conv_res, page, ocr_rects)

            yield page

    def _request_ocr(self, image: Image.Image) -> dict[str, Any]:
        if self._client is None or self._invoke_url is None or self._secret is None:
            raise NaverOcrError("NAVER OCR client is not initialized")

        if max(image.size) > self.options.max_image_edge:
            raise NaverOcrError(
                "NAVER OCR image exceeds the configured pixel edge limit"
            )

        image_buffer = BytesIO()
        rgb_image = image.convert("RGB")
        try:
            rgb_image.save(image_buffer, format="PNG")
        finally:
            rgb_image.close()
        image_bytes = image_buffer.getvalue()
        if len(image_bytes) > self.options.max_image_bytes:
            raise NaverOcrError(
                "NAVER OCR image exceeds the configured request byte limit"
            )

        message: dict[str, Any] = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "images": [{"format": "png", "name": "docling-crop"}],
            "enableTableDetection": self.options.enable_table_detection,
        }
        request_languages = [
            lang for lang in self.options.lang if lang in _SUPPORTED_REQUEST_LANGUAGES
        ]
        if request_languages:
            message["lang"] = ",".join(request_languages)

        encoded_message = json.dumps(
            message,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        last_transport_error: str | None = None
        for attempt in range(1, self.options.max_attempts + 1):
            try:
                response = self._client.post(
                    self._invoke_url,
                    headers={"X-OCR-SECRET": self._secret},
                    data={"message": encoded_message},
                    files={"file": ("docling-crop.png", image_bytes, "image/png")},
                )
            except httpx.RequestError as exc:
                # Do not include the exception text: it can contain request details.
                last_transport_error = type(exc).__name__
                if attempt < self.options.max_attempts:
                    self._sleep_before_retry(attempt)
                    continue
                raise NaverOcrError(
                    "NAVER OCR transport failed after "
                    f"{attempt} attempt(s): {last_transport_error}"
                ) from None

            if 200 <= response.status_code < 300:
                try:
                    payload = response.json()
                except ValueError:
                    raise NaverOcrError("NAVER OCR returned invalid JSON") from None
                if not isinstance(payload, dict):
                    raise NaverOcrError("NAVER OCR returned an invalid response object")
                return payload

            naver_error_code = self._bounded_error_code(response)
            rate_limited = response.status_code == 429 or naver_error_code == "0025"
            retryable = rate_limited or response.status_code >= 500
            if retryable and attempt < self.options.max_attempts:
                self._sleep_before_retry(attempt)
                continue

            # Response bodies are intentionally excluded. They are remote-controlled
            # data and may echo sensitive request information.
            if rate_limited:
                raise NaverOcrError(
                    f"NAVER OCR rate limit exceeded after {attempt} attempt(s)"
                )
            raise NaverOcrError(f"NAVER OCR returned HTTP {response.status_code}")

        # The loop always returns or raises. This guard keeps type checkers honest.
        raise NaverOcrError(
            "NAVER OCR transport failed"
            + (f": {last_transport_error}" if last_transport_error else "")
        )

    def _response_to_cells(
        self,
        payload: dict[str, Any],
        ocr_rect: BoundingBox,
        *,
        start_index: int = 0,
    ) -> list[TextCell]:
        images = payload.get("images")
        if not isinstance(images, list) or len(images) != 1:
            raise NaverOcrError("NAVER OCR response must contain exactly one image")

        image_result = images[0]
        if not isinstance(image_result, dict):
            raise NaverOcrError("NAVER OCR image result is invalid")
        if image_result.get("inferResult") != "SUCCESS":
            raise NaverOcrError("NAVER OCR image inference failed")

        fields = image_result.get("fields", [])
        if not isinstance(fields, list):
            raise NaverOcrError("NAVER OCR fields are invalid")

        cells: list[TextCell] = []
        for field in fields:
            if not isinstance(field, dict):
                raise NaverOcrError("NAVER OCR field is invalid")

            text = field.get("inferText")
            if not isinstance(text, str):
                raise NaverOcrError("NAVER OCR field text is invalid")
            text = text.strip()
            if not text:
                continue

            confidence = self._finite_number(
                field.get("inferConfidence"),
                "field confidence",
            )
            if not 0.0 <= confidence <= 1.0:
                raise NaverOcrError("NAVER OCR field confidence is out of range")

            bounding_poly = field.get("boundingPoly")
            if not isinstance(bounding_poly, dict):
                raise NaverOcrError("NAVER OCR field bounding polygon is invalid")
            vertices = bounding_poly.get("vertices")
            if not isinstance(vertices, list) or len(vertices) < 2:
                raise NaverOcrError("NAVER OCR field vertices are invalid")

            xs: list[float] = []
            ys: list[float] = []
            for vertex in vertices:
                if not isinstance(vertex, dict):
                    raise NaverOcrError("NAVER OCR field vertex is invalid")
                xs.append(self._finite_number(vertex.get("x"), "vertex x"))
                ys.append(self._finite_number(vertex.get("y"), "vertex y"))

            left = max(ocr_rect.l, (min(xs) / self.options.scale) + ocr_rect.l)
            top = max(ocr_rect.t, (min(ys) / self.options.scale) + ocr_rect.t)
            right = min(ocr_rect.r, (max(xs) / self.options.scale) + ocr_rect.l)
            bottom = min(ocr_rect.b, (max(ys) / self.options.scale) + ocr_rect.t)
            if right <= left or bottom <= top:
                raise NaverOcrError("NAVER OCR field bounding box has no area")

            bbox = BoundingBox.from_tuple(
                coord=(left, top, right, bottom),
                origin=CoordOrigin.TOPLEFT,
            )
            cells.append(
                TextCell(
                    index=start_index + len(cells),
                    text=text,
                    orig=text,
                    confidence=confidence,
                    from_ocr=True,
                    rect=BoundingRectangle.from_bounding_box(bbox),
                )
            )

        return cells

    @staticmethod
    def _finite_number(value: Any, field_name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise NaverOcrError(f"NAVER OCR {field_name} is invalid")
        number = float(value)
        if not math.isfinite(number):
            raise NaverOcrError(f"NAVER OCR {field_name} is invalid")
        return number

    @staticmethod
    def _sleep_before_retry(attempt: int) -> None:
        time.sleep(min(_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)), 2.0))

    @staticmethod
    def _bounded_error_code(response: httpx.Response) -> str | None:
        """Read only the documented error code from a small JSON response."""

        if len(response.content) > 64 * 1024:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        if not isinstance(payload, dict):
            return None
        code = payload.get("code")
        return code if isinstance(code, str) else None

    @classmethod
    def get_options_type(cls) -> type[OcrOptions]:
        return NaverOcrOptions

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __del__(self) -> None:
        with suppress(Exception):
            self.close()


def ocr_engines() -> dict[str, list[type[NaverOcrModel]]]:
    """Docling setuptools entrypoint contract."""

    return {"ocr_engines": [NaverOcrModel]}


__all__ = ["NaverOcrModel", "NaverOcrOptions", "ocr_engines"]
