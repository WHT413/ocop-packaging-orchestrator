from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Any, cast

from pydantic import ValidationError

from ocop_pack.agents.design_planner.agent import default_prompts
from ocop_pack.application.ports.planner import PlannerRequest, PlannerResult
from ocop_pack.infrastructure.config import PlannerSettings
from ocop_pack.provenance.models import PlannerProvenance, ProviderContext, UsageRecord
from ocop_pack.providers.common.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from ocop_pack.schemas.design_planner import DesignPlan

_FENCED_JSON_RE = re.compile(
    r"^\s*```(?:json)?\s*(?P<body>.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE
)


def _extract_json_object(content: str) -> str:
    match = _FENCED_JSON_RE.match(content)
    candidate = match.group("body") if match else content.strip()
    decoder = json.JSONDecoder()
    try:
        _parsed, end = decoder.raw_decode(candidate)
    except json.JSONDecodeError as exc:
        raise ProviderSchemaError(f"planner returned invalid JSON; location={exc.pos}") from exc
    if candidate[end:].strip():
        raise ProviderSchemaError("planner returned ambiguous JSON with trailing prose")
    if not candidate.lstrip().startswith("{"):
        raise ProviderSchemaError("planner returned JSON that is not an object")
    return candidate


def _response_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _response_shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_response_shape(value[0])] if value else []
    return type(value).__name__


def _write_diagnostic(
    context: ProviderContext,
    parsed: dict[str, Any],
    content: str,
    extracted_json: str | None,
    errors: list[dict[str, Any]],
) -> None:
    diagnostic = {
        "run_id": context.run_id,
        "node": context.node,
        "response_shape": _response_shape(parsed),
        "assistant_content": content,
        "extracted_json": extracted_json,
        "validation_errors": errors,
        "note": (
            "Sanitized planner diagnostic; request headers, API keys, and base URLs are not stored."
        ),
    }
    path = Path("data/runs_acceptance/planner_diagnostics") / f"{context.run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8")


class OpenAICompatiblePlannerProvider:
    provider = "openai-compatible"

    def __init__(self) -> None:
        settings = PlannerSettings()
        self.base_url = (settings.base_url or "").rstrip("/")
        self.api_key = settings.api_key.get_secret_value() if settings.api_key else ""
        self.model = settings.model
        self.timeout = settings.timeout_seconds
        self.max_output_tokens = settings.max_output_tokens
        if not self.base_url or not self.api_key or not self.model:
            raise ProviderConfigurationError("planner provider is not configured")

    def create_design_plan(
        self, request: PlannerRequest, context: ProviderContext
    ) -> PlannerResult:
        started = monotonic()
        prompts = default_prompts()
        system_prompt = next(
            prompt.content for prompt in prompts if prompt.prompt_id.endswith("system")
        )
        task_prompt = next(
            prompt.content for prompt in prompts if prompt.prompt_id.endswith("planner")
        )
        payload = {
            "model": self.model,
            "temperature": request.model_config_payload.get("temperature", 0),
            "max_tokens": self.max_output_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": task_prompt
                    + "\n\n<trusted_project_data_json>\n"
                    + request.planner_input.model_dump_json(exclude={"creative_brief_raw"})
                    + "\n</trusted_project_data_json>\n<untrusted_creative_brief_raw>\n"
                    + request.planner_input.creative_brief_raw
                    + "\n</untrusted_creative_brief_raw>",
                },
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                raw = response.read(2_000_000).decode("utf-8")
        except TimeoutError as exc:
            raise ProviderTimeoutError("planner timed out") from exc
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderAuthenticationError("planner authentication failed") from exc
            if exc.code == 429:
                raise ProviderRateLimitError("planner rate limited") from exc
            if exc.code >= 500:
                raise ProviderUnavailableError("planner unavailable") from exc
            raise ProviderSchemaError(f"planner request failed: {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ProviderUnavailableError("planner connection failed") from exc
        parsed = json.loads(raw)
        content = parsed["choices"][0]["message"]["content"]
        raw_response_hash = sha256(content.encode("utf-8")).hexdigest()
        json_content: str | None = None
        try:
            json_content = _extract_json_object(content)
            plan = DesignPlan.model_validate_json(json_content)
        except ValidationError as exc:
            validation_errors = [dict(error) for error in exc.errors()]
            _write_diagnostic(context, parsed, content, json_content, validation_errors)
            locations = [
                ".".join(str(part) for part in cast(tuple[object, ...], error["loc"]))
                for error in validation_errors
            ]
            messages = [
                f"{loc}: {error['msg']}"
                for loc, error in zip(locations, validation_errors, strict=False)
            ]
            detail = "; ".join(messages[:8])
            raise ProviderSchemaError(
                "planner returned invalid schema"
                f"; validation_locations={detail}; raw_response_hash={raw_response_hash}"
            ) from exc
        except ValueError as exc:
            _write_diagnostic(context, parsed, content, json_content, [])
            raise ProviderSchemaError(
                f"planner returned invalid schema; raw_response_hash={raw_response_hash}"
            ) from exc
        usage = parsed.get("usage", {})
        prov = PlannerProvenance(
            provider=self.provider,
            model=self.model,
            provider_request_id=str(parsed.get("id", "")),
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            prompt_hash=request.prompt_hash,
            schema_version=plan.schema_version,
            input_hash=request.input_hash,
            creative_brief_hash=request.creative_brief_hash,
            system_prompt_hash=request.system_prompt_hash,
            task_prompt_hash=request.task_prompt_hash,
            planner_policy_version=request.planner_policy_version,
            raw_response_hash=raw_response_hash,
            usage=UsageRecord(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                total_tokens=int(usage.get("total_tokens", 0)),
            ),
            latency_ms=int((monotonic() - started) * 1000),
        )
        return PlannerResult(design_plan=plan, provenance=prov)
