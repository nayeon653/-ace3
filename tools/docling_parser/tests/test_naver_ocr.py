from __future__ import annotations

from contextlib import nullcontext
from typing import Any

import httpx
import pytest
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling_core.types.doc import BoundingBox, CoordOrigin
from docling_team_parser.errors import NaverOcrError
from docling_team_parser.ocr import naver_plugin
from docling_team_parser.ocr.config import validate_naver_invoke_url
from docling_team_parser.ocr.naver_plugin import (
    NaverOcrModel,
    NaverOcrOptions,
    ocr_engines,
)
from PIL import Image

SECRET = "never-print-this-secret"
INVOKE_URL = "https://example.apigw.ntruss.com/custom/v1/domain-id/invoke-key/general"


def _success_payload(*, text: str = "연금", confidence: float = 0.98) -> dict[str, Any]:
    return {
        "version": "V2",
        "images": [
            {
                "inferResult": "SUCCESS",
                "fields": [
                    {
                        "inferText": text,
                        "inferConfidence": confidence,
                        "boundingPoly": {
                            "vertices": [
                                {"x": 4.0, "y": 6.0},
                                {"x": 24.0, "y": 6.0},
                                {"x": 24.0, "y": 26.0},
                                {"x": 4.0, "y": 26.0},
                            ]
                        },
                    }
                ],
            }
        ],
    }


def _make_model(
    monkeypatch: pytest.MonkeyPatch,
    handler: httpx.MockTransport,
    *,
    max_attempts: int = 3,
    enable_table_detection: bool = False,
) -> tuple[NaverOcrModel, httpx.Client]:
    client = httpx.Client(transport=handler)
    monkeypatch.setattr(naver_plugin.httpx, "Client", lambda **_: client)
    monkeypatch.setenv("NAVER_OCR_INVOKE_URL", INVOKE_URL)
    monkeypatch.setenv("NAVER_OCR_SECRET", SECRET)

    model = NaverOcrModel(
        enabled=True,
        artifacts_path=None,
        options=NaverOcrOptions(
            lang=["ko", "en"],
            scale=2.0,
            timeout_seconds=5.0,
            max_attempts=max_attempts,
            enable_table_detection=enable_table_detection,
        ),
        accelerator_options=AcceleratorOptions(),
    )
    monkeypatch.setattr(model, "_sleep_before_retry", lambda _attempt: None)
    return model, client


def test_plugin_contract_and_options_do_not_hold_credentials() -> None:
    options = NaverOcrOptions()

    assert NaverOcrOptions.kind == "naver_ocr"
    assert NaverOcrModel.get_options_type() is NaverOcrOptions
    assert ocr_engines() == {"ocr_engines": [NaverOcrModel]}
    assert options.lang == ["ko"]
    assert options.scale == 3.0
    assert NaverOcrOptions(scale=1.5).scale == 1.5
    assert "secret" not in options.model_dump()
    assert "invoke_url" not in options.model_dump()


def test_disabled_model_does_not_require_remote_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NAVER_OCR_INVOKE_URL", raising=False)
    monkeypatch.delenv("NAVER_OCR_SECRET", raising=False)

    model = NaverOcrModel(
        enabled=False,
        artifacts_path=None,
        options=NaverOcrOptions(),
        accelerator_options=AcceleratorOptions(),
    )

    assert model._client is None


def test_enabled_model_rejects_non_https_invoke_url_before_client_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "NAVER_OCR_INVOKE_URL",
        "http://example.apigw.ntruss.com/custom/v1/domain-id/invoke-key/general",
    )
    monkeypatch.setenv("NAVER_OCR_SECRET", SECRET)
    monkeypatch.setattr(
        naver_plugin.httpx,
        "Client",
        lambda **_: pytest.fail("HTTP client must not be created for an HTTP URL"),
    )

    with pytest.raises(NaverOcrError, match="absolute HTTPS URL"):
        NaverOcrModel(
            enabled=True,
            artifacts_path=None,
            options=NaverOcrOptions(),
            accelerator_options=AcceleratorOptions(),
        )


@pytest.mark.parametrize(
    ("invoke_url", "message"),
    [
        (
            "https://example.invalid/custom/v1/domain-id/invoke-key/general",
            "direct subdomain",
        ),
        (
            (
                "https://nested.example.apigw.ntruss.com/custom/v1/domain-id/"
                "invoke-key/general"
            ),
            "direct subdomain",
        ),
        (
            (
                "https://user@example.apigw.ntruss.com/custom/v1/domain-id/"
                "invoke-key/general"
            ),
            "user information",
        ),
        (
            (
                "https://example.apigw.ntruss.com:8443/custom/v1/domain-id/"
                "invoke-key/general"
            ),
            "default HTTPS port",
        ),
        (
            (
                "https://example.apigw.ntruss.com/custom/v1/domain-id/"
                "invoke-key/general?request=test"
            ),
            "query or fragment",
        ),
        (
            (
                "https://example.apigw.ntruss.com/custom/v1/domain-id/"
                "invoke-key/general#response"
            ),
            "query or fragment",
        ),
        (
            "https://example.apigw.ntruss.com/custom/v1/domain-id/invoke-key/infer",
            "path must end with /general",
        ),
    ],
)
def test_invoke_url_rejects_non_general_ocr_endpoints(
    invoke_url: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_naver_invoke_url(invoke_url)


def test_invoke_url_accepts_official_general_ocr_endpoint_shape() -> None:
    assert validate_naver_invoke_url(f"  {INVOKE_URL}  ") == INVOKE_URL


def test_general_v2_request_and_response_coordinate_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = request.read()
        assert request.headers["X-OCR-SECRET"] == SECRET
        assert SECRET.encode() not in body
        assert b'"version":"V2"' in body
        assert b'"lang":"ko"' in body
        assert b'"enableTableDetection":true' in body
        return httpx.Response(200, json=_success_payload())

    model, client = _make_model(
        monkeypatch,
        httpx.MockTransport(handler),
        enable_table_detection=True,
    )
    try:
        payload = model._request_ocr(Image.new("RGB", (80, 80), "white"))
        rect = BoundingBox.from_tuple(
            coord=(10.0, 20.0, 100.0, 120.0),
            origin=CoordOrigin.TOPLEFT,
        )
        cells = model._response_to_cells(payload, rect, start_index=7)
    finally:
        model.close()
        client.close()

    assert len(seen) == 1
    assert len(cells) == 1
    assert cells[0].index == 7
    assert cells[0].text == "연금"
    assert cells[0].orig == "연금"
    assert cells[0].confidence == pytest.approx(0.98)
    assert cells[0].from_ocr is True
    assert cells[0].rect.to_bounding_box().as_tuple() == pytest.approx(
        (12.0, 23.0, 22.0, 33.0)
    )


def test_retries_429_and_5xx_until_success(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = iter((500, 429, 200))
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        status = next(statuses)
        if status == 200:
            return httpx.Response(status, json=_success_payload())
        return httpx.Response(status, text="temporary")

    model, client = _make_model(
        monkeypatch,
        httpx.MockTransport(handler),
        max_attempts=3,
    )
    try:
        payload = model._request_ocr(Image.new("RGB", (16, 16), "white"))
    finally:
        model.close()
        client.close()

    assert payload["images"][0]["inferResult"] == "SUCCESS"
    assert seen == 3


def test_retries_documented_0025_rate_limit_in_http_400_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        if seen == 1:
            return httpx.Response(400, json={"code": "0025"})
        return httpx.Response(200, json=_success_payload())

    model, client = _make_model(
        monkeypatch,
        httpx.MockTransport(handler),
        max_attempts=2,
    )
    try:
        payload = model._request_ocr(Image.new("RGB", (16, 16), "white"))
    finally:
        model.close()
        client.close()

    assert payload["images"][0]["inferResult"] == "SUCCESS"
    assert seen == 2


def test_image_limits_are_enforced_before_remote_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        return httpx.Response(200, json=_success_payload())

    model, client = _make_model(monkeypatch, httpx.MockTransport(handler))
    model.options.max_image_edge = 8
    try:
        with pytest.raises(NaverOcrError, match="pixel edge limit"):
            model._request_ocr(Image.new("RGB", (9, 8), "white"))
    finally:
        model.close()
        client.close()

    assert seen == 0


def test_non_429_4xx_is_not_retried_and_body_is_not_exposed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        return httpx.Response(401, text=f"bad secret: {SECRET}")

    model, client = _make_model(
        monkeypatch,
        httpx.MockTransport(handler),
        max_attempts=5,
    )
    try:
        with pytest.raises(NaverOcrError) as exc_info:
            model._request_ocr(Image.new("RGB", (16, 16), "white"))
    finally:
        model.close()
        client.close()

    assert seen == 1
    assert "HTTP 401" in str(exc_info.value)
    assert SECRET not in str(exc_info.value)


def test_transport_failure_obeys_max_attempts_without_leaking_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        raise httpx.ReadTimeout(f"timeout with {SECRET}", request=request)

    model, client = _make_model(
        monkeypatch,
        httpx.MockTransport(handler),
        max_attempts=2,
    )
    try:
        with pytest.raises(NaverOcrError) as exc_info:
            model._request_ocr(Image.new("RGB", (16, 16), "white"))
    finally:
        model.close()
        client.close()

    assert seen == 2
    assert "ReadTimeout" in str(exc_info.value)
    assert SECRET not in str(exc_info.value)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"images": []},
        {"images": [{"inferResult": "FAILURE", "fields": []}]},
        {"images": [{"inferResult": "SUCCESS", "fields": "invalid"}]},
    ],
)
def test_invalid_or_failed_response_raises(
    payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, client = _make_model(
        monkeypatch,
        httpx.MockTransport(lambda _: httpx.Response(200, json={})),
    )
    rect = BoundingBox.from_tuple(
        coord=(0.0, 0.0, 100.0, 100.0),
        origin=CoordOrigin.TOPLEFT,
    )
    try:
        with pytest.raises(NaverOcrError):
            model._response_to_cells(payload, rect)
    finally:
        model.close()
        client.close()


def test_call_uses_high_resolution_crop_then_post_processes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, client = _make_model(
        monkeypatch,
        httpx.MockTransport(lambda _: httpx.Response(200, json={})),
    )
    rect = BoundingBox.from_tuple(
        coord=(10.0, 20.0, 100.0, 120.0),
        origin=CoordOrigin.TOPLEFT,
    )
    rendered_image = Image.new("RGB", (180, 200), "white")
    backend_calls: list[tuple[float, BoundingBox]] = []
    processed: list[Any] = []

    class FakeBackend:
        @staticmethod
        def is_valid() -> bool:
            return True

        @staticmethod
        def get_page_image(*, scale: float, cropbox: BoundingBox) -> Image.Image:
            backend_calls.append((scale, cropbox))
            return rendered_image

    class FakePage:
        _backend = FakeBackend()
        page_no = 1

    monkeypatch.setattr(naver_plugin, "TimeRecorder", lambda *_: nullcontext())
    monkeypatch.setattr(model, "get_ocr_rects", lambda _page: [rect])
    monkeypatch.setattr(model, "_request_ocr", lambda _image: _success_payload())
    monkeypatch.setattr(
        model,
        "post_process_cells",
        lambda cells, page, conv_res: processed.append((cells, page, conv_res)),
    )

    conversion_result = object()
    page = FakePage()
    try:
        output = list(model(conversion_result, [page]))  # type: ignore[arg-type]
    finally:
        model.close()
        client.close()

    assert output == [page]
    assert backend_calls == [(2.0, rect)]
    assert len(processed) == 1
    assert processed[0][0][0].text == "연금"
    with pytest.raises(ValueError):
        rendered_image.load()


def test_call_propagates_ocr_error_without_post_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, client = _make_model(
        monkeypatch,
        httpx.MockTransport(lambda _: httpx.Response(200, json={})),
    )
    rect = BoundingBox.from_tuple(
        coord=(0.0, 0.0, 10.0, 10.0),
        origin=CoordOrigin.TOPLEFT,
    )
    rendered_image = Image.new("RGB", (20, 20), "white")
    post_processed = False
    request_count = 0

    class FakeBackend:
        @staticmethod
        def is_valid() -> bool:
            return True

        @staticmethod
        def get_page_image(*, scale: float, cropbox: BoundingBox) -> Image.Image:
            return rendered_image

    class FakePage:
        _backend = FakeBackend()
        page_no = 1

    def fail_request(_image: Image.Image) -> dict[str, Any]:
        nonlocal request_count
        request_count += 1
        raise NaverOcrError("forced failure")

    def record_post_process(*_args: Any) -> None:
        nonlocal post_processed
        post_processed = True

    monkeypatch.setattr(naver_plugin, "TimeRecorder", lambda *_: nullcontext())
    monkeypatch.setattr(model, "get_ocr_rects", lambda _page: [rect])
    monkeypatch.setattr(model, "_request_ocr", fail_request)
    monkeypatch.setattr(model, "post_process_cells", record_post_process)

    try:
        with pytest.raises(NaverOcrError, match="forced failure"):
            list(model(object(), [FakePage()]))  # type: ignore[arg-type]
        with pytest.raises(NaverOcrError, match="forced failure"):
            list(model(object(), [FakePage()]))  # type: ignore[arg-type]
    finally:
        model.close()
        client.close()

    assert post_processed is False
    assert request_count == 1
    with pytest.raises(ValueError):
        rendered_image.load()
