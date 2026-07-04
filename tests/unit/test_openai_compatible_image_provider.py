from __future__ import annotations

import base64
import io
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from ocop_pack.application.ports.artwork_provider import ArtworkRequest
from ocop_pack.provenance.models import ProviderContext
from ocop_pack.providers.common.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
)
from ocop_pack.providers.image.openai_compatible import OpenAICompatibleImageProvider


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _png_b64(width: int = 32, height: int = 32) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "#88aa55").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _request(width: int = 32, height: int = 32) -> ArtworkRequest:
    return ArtworkRequest(
        concept_id="probe",
        prompt="single flat green square, no text",
        negative_prompt="Do not add text, logos, QR codes, labels, packaging mockups.",
        target_width_px=width,
        target_height_px=height,
        request_hash="probe-hash",
    )


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCOP_IMAGE_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OCOP_IMAGE_MODEL", "genImage")
    monkeypatch.setenv("OCOP_IMAGE_BASE_URL", "https://image.invalid/v1")
    monkeypatch.setenv("OCOP_IMAGE_API_KEY", "test-key")


def test_openai_image_provider_sends_minimal_generation_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure(monkeypatch)
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse({"id": "img-test", "data": [{"b64_json": _png_b64()}]})

    monkeypatch.setattr(
        "ocop_pack.providers.image.openai_compatible.urllib.request.urlopen", fake_urlopen
    )

    result = OpenAICompatibleImageProvider().generate(
        _request(), ProviderContext(run_id="run", thread_id="run", node="probe"), tmp_path
    )

    assert captured["url"] == "https://image.invalid/v1/images/generations"
    assert captured["payload"]["model"] == "genImage"
    assert captured["payload"]["n"] == 1
    assert captured["payload"]["size"] == "32x32"
    assert captured["payload"]["response_format"] == "b64_json"
    assert "test-key" not in json.dumps(captured["payload"])
    assert Path(result.artifact_ref).exists()
    assert result.request_id == "img-test"
    assert result.provenance is not None
    assert result.provenance.provider_request_id == "img-test"


def test_openai_image_provider_normalizes_bad_dimensions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(
        "ocop_pack.providers.image.openai_compatible.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(
            {"id": "img-test", "data": [{"b64_json": _png_b64(16, 16)}]}
        ),
    )

    result = OpenAICompatibleImageProvider().generate(
        _request(), ProviderContext(run_id="run", thread_id="run", node="probe"), tmp_path
    )

    with Image.open(result.artifact_ref) as image:
        assert image.size == (32, 32)
    assert result.provenance is not None
    assert result.provenance.original_width == 16
    assert result.provenance.original_height == 16
    assert result.provenance.normalization_policy == "contain_pad_white"
    assert "PROVIDER_DIMENSION_NORMALIZED" in result.provenance.warning_codes


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, ProviderAuthenticationError),
        (403, ProviderAuthenticationError),
        (429, ProviderRateLimitError),
    ],
)
def test_openai_image_provider_maps_http_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status: int,
    error_type: type[Exception],
) -> None:
    _configure(monkeypatch)

    def raise_http_error(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.HTTPError("url", status, "boom", {}, None)

    monkeypatch.setattr(
        "ocop_pack.providers.image.openai_compatible.urllib.request.urlopen", raise_http_error
    )

    with pytest.raises(error_type):
        OpenAICompatibleImageProvider().generate(
            _request(), ProviderContext(run_id="run", thread_id="run", node="probe"), tmp_path
        )
