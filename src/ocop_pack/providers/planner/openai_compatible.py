from __future__ import annotations

import json
import urllib.error
import urllib.request
from hashlib import sha256
from time import monotonic

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
                    "content": task_prompt + "\n\n<project_data_json>\n"
                    + request.planner_input.model_dump_json()
                    + "\n</project_data_json>",
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
        try:
            plan = DesignPlan.model_validate_json(content)
        except ValueError as exc:
            raise ProviderSchemaError("planner returned invalid schema") from exc
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
            raw_response_hash=sha256(content.encode("utf-8")).hexdigest(),
            usage=UsageRecord(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                total_tokens=int(usage.get("total_tokens", 0)),
            ),
            latency_ms=int((monotonic() - started) * 1000),
        )
        return PlannerResult(design_plan=plan, provenance=prov)
