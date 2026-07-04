from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Any, cast

from pydantic import ValidationError

from ocop_pack.agents.visual_critic.prompt_registry import default_prompts
from ocop_pack.agents.visual_critic.schemas import CriticDecision
from ocop_pack.application.ports.vision_critic import CriticRequest, CriticResult
from ocop_pack.infrastructure.config import VisionSettings
from ocop_pack.provenance.models import CriticProvenance, ProviderContext, UsageRecord
from ocop_pack.providers.common.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

_MAX_RAW_CAPTURE = 200_000
_SECRET_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/-]+", re.I)
_URL_SECRET_RE = re.compile(r"([?&](?:key|token|signature|sig|X-Amz-Signature)=)[^&\s]+", re.I)
_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S | re.I)


class OpenAICompatibleVisionCriticProvider:
    provider = "openai-compatible"

    def __init__(self) -> None:
        settings = VisionSettings()
        self.base_url = (settings.base_url or "").rstrip("/")
        self.api_key = settings.api_key.get_secret_value() if settings.api_key else ""
        self.model = settings.model
        self.timeout = settings.timeout_seconds
        self.structured_output_mode = "prompt_json"
        if not self.base_url or not self.api_key or not self.model:
            raise ProviderConfigurationError("vision provider is not configured")

    def evaluate(self, request: CriticRequest, context: ProviderContext) -> CriticResult:
        started = monotonic()
        payload = self._build_payload(request)
        http_request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                raw = response.read(2_000_000).decode("utf-8")
        except TimeoutError as exc:
            raise ProviderTimeoutError("vision critic timed out") from exc
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderAuthenticationError("vision critic authentication failed") from exc
            if exc.code == 429:
                raise ProviderRateLimitError("vision critic rate limited") from exc
            if exc.code >= 500:
                raise ProviderUnavailableError("vision critic unavailable") from exc
            raise ProviderSchemaError(
                f"vision critic request failed: {exc.code}", code="VISION_TRANSPORT_INVALID"
            ) from exc
        except urllib.error.URLError as exc:
            raise ProviderUnavailableError("vision critic connection failed") from exc

        raw_response_hash = sha256(raw.encode("utf-8")).hexdigest()
        parsed = _parse_chat_completion(raw)
        content = _extract_assistant_content(parsed)
        json_text = _extract_json_object(content)
        try:
            decision = CriticDecision.model_validate_json(json_text)
        except ValidationError as exc:
            _write_debug_artifacts(context.run_id, raw, exc.errors())
            locations = [
                ".".join(str(part) for part in error["loc"]) or "<root>" for error in exc.errors()
            ]
            detail = ", ".join(locations[:12]) or "<root>"
            raise ProviderSchemaError(
                "vision critic returned invalid schema"
                f"; validation_locations={detail}; raw_response_hash={raw_response_hash}",
                code="CRITIC_SCHEMA_INVALID",
            ) from exc
        except ValueError as exc:
            _write_debug_artifacts(
                context.run_id,
                raw,
                [{"loc": ["<json>"], "msg": str(exc), "type": "value_error"}],
            )
            raise ProviderSchemaError(
                "vision critic returned malformed decision JSON; "
                f"raw_response_hash={raw_response_hash}",
                code="CRITIC_SCHEMA_INVALID",
            ) from exc
        usage = cast(dict[str, Any], parsed.get("usage", {}))
        decision_hash = sha256(decision.model_dump_json().encode("utf-8")).hexdigest()
        provenance = CriticProvenance(
            contact_sheet_hash=request.contact_sheet_hash,
            candidate_hashes=request.candidate_hashes,
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            prompt_hash=request.prompt_hash,
            rubric_version=request.rubric_version,
            schema_version=request.schema_version,
            provider=self.provider,
            model=self.model,
            provider_request_id=str(parsed.get("id", "")),
            usage=UsageRecord(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                total_tokens=int(usage.get("total_tokens", 0)),
            ),
            latency_ms=int((monotonic() - started) * 1000),
            decision_hash=decision_hash,
            raw_response_hash=raw_response_hash,
        )
        return CriticResult(
            decision=decision,
            provider=self.provider,
            model_id=self.model,
            provider_request_id=provenance.provider_request_id,
            contact_sheet_hash=request.contact_sheet_hash,
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            prompt_hash=request.prompt_hash,
            schema_version=request.schema_version,
            usage=provenance.usage,
            latency_ms=provenance.latency_ms,
            raw_response_hash=raw_response_hash,
            provenance=provenance,
        )

    def _build_payload(self, request: CriticRequest) -> dict[str, Any]:
        prompts = default_prompts()
        system_prompt = next(
            prompt.content for prompt in prompts if prompt.prompt_id.endswith("system")
        )
        critic_prompt = next(
            prompt.content for prompt in prompts if prompt.prompt_id.endswith("task")
        )
        return {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": critic_prompt
                    + "\n\nValid candidate IDs: "
                    + ", ".join(request.candidate_ids)
                    + "\nValid artwork IDs for targeted_revision: "
                    + ", ".join(request.artwork_ids)
                    + "\n\n<critic_request_json>\n"
                    + request.model_dump_json()
                    + "\n</critic_request_json>",
                },
            ],
        }


def _parse_chat_completion(raw: str) -> dict[str, Any]:
    stripped = raw.lstrip()
    if stripped.startswith("data:") or "\ndata:" in raw:
        return _parse_sse_chat_completion(raw)
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise ProviderSchemaError(
            "vision critic returned invalid JSON response", code="VISION_TRANSPORT_INVALID"
        ) from exc
    if not isinstance(parsed, dict):
        raise ProviderSchemaError(
            "vision critic returned non-object response", code="VISION_TRANSPORT_INVALID"
        )
    return parsed


def _parse_sse_chat_completion(raw: str) -> dict[str, Any]:
    chunks: list[dict[str, Any]] = []
    saw_done = False
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if not data:
            continue
        if data == "[DONE]":
            saw_done = True
            continue
        try:
            chunk = json.loads(data)
        except ValueError as exc:
            raise ProviderSchemaError(
                "vision critic stream chunk is invalid JSON", code="VISION_TRANSPORT_INVALID"
            ) from exc
        if not isinstance(chunk, dict):
            raise ProviderSchemaError(
                "vision critic stream chunk is non-object", code="VISION_TRANSPORT_INVALID"
            )
        chunks.append(chunk)
    if not chunks:
        raise ProviderSchemaError(
            "vision critic response stream is empty", code="VISION_CONTENT_EMPTY"
        )
    if not saw_done:
        raise ProviderSchemaError(
            "vision critic response stream did not finish", code="VISION_STREAM_INCOMPLETE"
        )
    content_parts: list[str] = []
    for chunk in chunks:
        for choice in cast(list[dict[str, Any]], chunk.get("choices", [])):
            delta = cast(dict[str, Any], choice.get("delta", {}))
            content_parts.extend(_content_strings(delta.get("content")))
    content = "".join(content_parts)
    final = chunks[-1]
    return {
        "id": final.get("id", chunks[0].get("id", "")),
        "choices": [{"message": {"content": content}}],
        "usage": final.get("usage", {}),
    }


def _extract_assistant_content(parsed: dict[str, Any]) -> str:
    choices = cast(list[dict[str, Any]], parsed.get("choices", []))
    if not choices:
        raise ProviderSchemaError(
            "vision critic response has no choices", code="VISION_CONTENT_EMPTY"
        )
    message = cast(dict[str, Any], choices[0].get("message", {}))
    content = "".join(_content_strings(message.get("content")))
    if not content:
        delta = cast(dict[str, Any], choices[0].get("delta", {}))
        content = "".join(_content_strings(delta.get("content")))
    if not content.strip():
        raise ProviderSchemaError(
            "vision critic assistant content is empty", code="VISION_CONTENT_EMPTY"
        )
    return content


def _content_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                for key in ("text", "json", "content"):
                    nested = item.get(key)
                    if isinstance(nested, str):
                        parts.append(nested)
                        break
                    if isinstance(nested, dict):
                        parts.append(json.dumps(nested))
                        break
        return parts
    if isinstance(value, dict):
        for key in ("text", "json", "content"):
            nested = value.get(key)
            if isinstance(nested, str):
                return [nested]
            if isinstance(nested, dict):
                return [json.dumps(nested)]
    return []


def _extract_json_object(content: str) -> str:
    text = content.strip()
    match = _CODE_FENCE_RE.match(text)
    if match:
        text = match.group(1).strip()
    decoder = json.JSONDecoder()
    try:
        _obj, end = decoder.raw_decode(text)
        if not text[end:].strip():
            return text[:end]
    except ValueError:
        pass
    found: list[str] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            _obj, end = decoder.raw_decode(text[index:])
        except ValueError:
            continue
        found.append(text[index : index + end])
    if len(found) != 1:
        raise ProviderSchemaError(
            "vision critic JSON object not found", code="VISION_JSON_NOT_FOUND"
        )
    return found[0]


def _write_debug_artifacts(run_id: str, raw: str, errors: Sequence[Any]) -> None:
    critic_dir = Path("runs") / run_id / "critic"
    critic_dir.mkdir(parents=True, exist_ok=True)
    redacted = _redact(raw)[:_MAX_RAW_CAPTURE]
    (critic_dir / "raw_response.redacted.txt").write_text(redacted, encoding="utf-8")
    validation_errors = [
        {
            "loc": list(error.get("loc", [])),
            "msg": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        for error in errors
    ]
    (critic_dir / "validation_error.json").write_text(
        json.dumps({"errors": validation_errors}, indent=2), encoding="utf-8"
    )


def _redact(text: str) -> str:
    return _URL_SECRET_RE.sub(r"\1[REDACTED]", _SECRET_RE.sub(r"\1[REDACTED]", text))
