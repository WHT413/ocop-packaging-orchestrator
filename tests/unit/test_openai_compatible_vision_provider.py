from __future__ import annotations

import base64
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from ocop_pack.application.ports.vision_critic import CriticRequest
from ocop_pack.provenance.models import ProviderContext
from ocop_pack.providers.common.errors import ProviderAuthenticationError, ProviderSchemaError
from ocop_pack.providers.vision.openai_compatible import (
    OpenAICompatibleVisionCriticProvider,
    _extract_json_object,
    _parse_chat_completion,
)


class _FakeResponse:
    def __init__(self, payload: dict[str, Any] | str) -> None:
        self.payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        if isinstance(self.payload, str):
            return self.payload.encode("utf-8")
        return json.dumps(self.payload).encode("utf-8")


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCOP_VISION_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OCOP_VISION_MODEL", "vision-test")
    monkeypatch.setenv("OCOP_VISION_BASE_URL", "https://vision.invalid/v1")
    monkeypatch.setenv("OCOP_VISION_API_KEY", "test-key")


def _contact_sheet(tmp_path: Path) -> Path:
    path = tmp_path / "contact_sheet.png"
    path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
    )
    return path


def _request(contact_sheet_path: Path) -> CriticRequest:
    return CriticRequest(
        contact_sheet_path=contact_sheet_path,
        contact_sheet_hash="sheet-hash",
        candidate_ids=["C001"],
        candidate_hashes={"C001": "candidate-hash"},
        artwork_ids=["A01"],
        brand_summary="Tea brand",
        visual_direction="warm botanical",
        product_category="tea",
        layout_intent_summary="balanced layout",
        hard_constraint_summary="all hard constraints passed",
        prompt_id="visual_critic",
        prompt_version="v1",
        prompt_hash="prompt-hash",
        schema_version="v1",
        rubric_version="rubric-v1",
        request_hash="request-hash",
    )


def _decision_payload(status: str = "PASS") -> dict[str, Any]:
    selected = "C001" if status == "PASS" else None
    return {
        "schema_version": "v1",
        "status": status,
        "selected_candidate_id": selected,
        "candidate_scores": [
            {
                "candidate_id": "C001",
                "readability_hierarchy": 8,
                "balance_whitespace": 8,
                "brand_fit": 8,
                "artwork_relevance": 8,
                "distinctiveness": 8,
                "total_score": 8,
                "summary": "Strong candidate.",
            }
        ],
        "targeted_revision": None,
        "confidence": 0.9,
        "decision_summary": "Select C001.",
    }


def test_openai_vision_provider_sends_chat_completion_and_maps_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure(monkeypatch)
    captured: dict[str, Any] = {}
    provider_payload = {
        "id": "chatcmpl-vision",
        "choices": [{"message": {"content": json.dumps(_decision_payload())}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }

    def fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(provider_payload)

    monkeypatch.setattr(
        "ocop_pack.providers.vision.openai_compatible.urllib.request.urlopen", fake_urlopen
    )

    result = OpenAICompatibleVisionCriticProvider().evaluate(
        _request(_contact_sheet(tmp_path)),
        ProviderContext(run_id="run", thread_id="run", node="visual_critic"),
    )

    assert captured["url"] == "https://vision.invalid/v1/chat/completions"
    assert captured["payload"]["model"] == "vision-test"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["temperature"] == 0
    user_content = captured["payload"]["messages"][1]["content"]
    assert user_content[0]["type"] == "text"
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "test-key" not in json.dumps(captured["payload"])
    assert result.provider == "openai-compatible"
    assert result.model_id == "vision-test"
    assert result.decision.selected_candidate_id == "C001"
    assert result.usage.total_tokens == 18
    assert result.provenance is not None
    assert result.provenance.provider_request_id == "chatcmpl-vision"
    assert result.provenance.decision_hash


def test_openai_vision_provider_reports_schema_locations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure(monkeypatch)
    invalid_decision = _decision_payload() | {"candidate_scores": []}
    invalid_decision.pop("confidence")
    monkeypatch.setattr(
        "ocop_pack.providers.vision.openai_compatible.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(
            {"id": "bad", "choices": [{"message": {"content": json.dumps(invalid_decision)}}]}
        ),
    )

    with pytest.raises(ProviderSchemaError) as exc_info:
        OpenAICompatibleVisionCriticProvider().evaluate(
            _request(_contact_sheet(tmp_path)),
            ProviderContext(run_id="run", thread_id="run", node="visual_critic"),
        )

    message = str(exc_info.value)
    assert "vision critic returned invalid schema" in message
    assert "confidence" in message
    assert "raw_response_hash=" in message


def test_openai_vision_provider_parses_valid_sse_chunks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure(monkeypatch)
    decision = json.dumps(_decision_payload())
    raw = "\n".join(
        [
            'data: {"id":"sse-1","choices":[{"delta":{"content":"'
            + decision[:40].replace('"', '\\"')
            + '"}}]}',
            'data: {"id":"sse-1","choices":[{"delta":{"content":"'
            + decision[40:].replace('"', '\\"')
            + '"}}]}',
            "data: [DONE]",
        ]
    )
    monkeypatch.setattr(
        "ocop_pack.providers.vision.openai_compatible.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(raw),
    )

    result = OpenAICompatibleVisionCriticProvider().evaluate(
        _request(_contact_sheet(tmp_path)),
        ProviderContext(run_id="run", thread_id="run", node="visual_critic"),
    )

    assert result.decision.status == "PASS"
    assert result.provider_request_id == "sse-1"


def test_openai_vision_provider_rejects_empty_and_incomplete_sse() -> None:
    with pytest.raises(ProviderSchemaError) as empty:
        _parse_chat_completion("data: [DONE]")
    assert empty.value.code == "VISION_CONTENT_EMPTY"

    with pytest.raises(ProviderSchemaError) as incomplete:
        _parse_chat_completion('data: {"choices":[{"delta":{"content":"{}"}}]}')
    assert incomplete.value.code == "VISION_STREAM_INCOMPLETE"


def test_openai_vision_provider_extracts_markdown_wrapped_json() -> None:
    assert _extract_json_object('```json\n{"status":"PASS"}\n```') == '{"status":"PASS"}'


def test_openai_vision_provider_rejects_malformed_or_missing_json() -> None:
    with pytest.raises(ProviderSchemaError) as exc_info:
        _extract_json_object("no json here")
    assert exc_info.value.code == "VISION_JSON_NOT_FOUND"


def test_openai_vision_provider_ignores_reasoning_content() -> None:
    raw = "\n".join(
        [
            'data: {"choices":[{"delta":{"reasoning_content":"{bad}","content":"{\\"a\\":"}}]}',
            'data: {"choices":[{"delta":{"content":"1}"}}]}',
            "data: [DONE]",
        ]
    )
    parsed = _parse_chat_completion(raw)
    assert parsed["choices"][0]["message"]["content"] == '{"a":1}'


def test_openai_vision_provider_maps_auth_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure(monkeypatch)

    def raise_http_error(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.HTTPError("url", 401, "boom", {}, None)

    monkeypatch.setattr(
        "ocop_pack.providers.vision.openai_compatible.urllib.request.urlopen", raise_http_error
    )

    with pytest.raises(ProviderAuthenticationError):
        OpenAICompatibleVisionCriticProvider().evaluate(
            _request(_contact_sheet(tmp_path)),
            ProviderContext(run_id="run", thread_id="run", node="visual_critic"),
        )
