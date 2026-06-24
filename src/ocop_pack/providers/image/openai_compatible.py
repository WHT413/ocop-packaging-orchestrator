from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from hashlib import sha256
from pathlib import Path
from time import monotonic

from PIL import Image

from ocop_pack.application.ports.artwork_provider import ArtworkRequest, ArtworkResult
from ocop_pack.infrastructure.config import ImageSettings
from ocop_pack.provenance.models import ArtworkProvenance, ProviderContext
from ocop_pack.providers.common.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from ocop_pack.services.validation_service import file_sha256


class OpenAICompatibleImageProvider:
    provider = "openai-compatible"

    def __init__(self) -> None:
        settings = ImageSettings()
        self.base_url = (settings.base_url or "").rstrip("/")
        self.api_key = settings.api_key.get_secret_value() if settings.api_key else ""
        self.model = settings.model
        self.timeout = settings.timeout_seconds
        if not self.base_url or not self.api_key or not self.model:
            raise ProviderConfigurationError("image provider is not configured")

    def generate(
        self, request: ArtworkRequest, context: ProviderContext, output_dir: Path
    ) -> ArtworkResult:
        started = monotonic()
        payload = {
            "model": self.model,
            "prompt": request.prompt + "\n" + request.negative_prompt,
            "n": 1,
            "size": f"{request.target_width_px}x{request.target_height_px}",
            "response_format": "b64_json",
        }
        http_request = urllib.request.Request(
            f"{self.base_url}/images/generations",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                raw = response.read(8_000_000).decode("utf-8")
        except TimeoutError as exc:
            raise ProviderTimeoutError("image provider timed out") from exc
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderAuthenticationError("image authentication failed") from exc
            if exc.code == 429:
                raise ProviderRateLimitError("image rate limited") from exc
            if exc.code >= 500:
                raise ProviderUnavailableError("image unavailable") from exc
            raise ProviderSchemaError(f"image request failed: {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ProviderUnavailableError("image connection failed") from exc
        parsed = json.loads(raw)
        b64 = parsed["data"][0].get("b64_json")
        if not isinstance(b64, str):
            raise ProviderSchemaError("image response missing b64_json")
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{request.concept_id}.png"
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_bytes(base64.b64decode(b64, validate=True))
            with Image.open(tmp) as image:
                width, height = image.size
                if width != request.target_width_px or height != request.target_height_px:
                    raise ProviderSchemaError("image response dimensions do not match request")
                image.convert("RGB").save(path, format="PNG")
        except (ValueError, OSError) as exc:
            raise ProviderSchemaError("image response is corrupt") from exc
        tmp.unlink(missing_ok=True)
        digest = file_sha256(path)
        prompt_hash = sha256(request.prompt.encode("utf-8")).hexdigest()
        negative_hash = sha256(request.negative_prompt.encode("utf-8")).hexdigest()
        request_id = str(parsed.get("id", ""))
        provenance = ArtworkProvenance(
            artifact_id=request.concept_id,
            artifact_sha256=digest,
            provider=self.provider,
            model=self.model,
            provider_request_id=request_id,
            prompt_id="design_planner.artwork",
            prompt_version="v1",
            prompt_hash=prompt_hash,
            negative_prompt_hash=negative_hash,
            input_hash=request.request_hash,
            width=request.target_width_px,
            height=request.target_height_px,
            format="png",
            latency_ms=int((monotonic() - started) * 1000),
            warning_codes=["ARTWORK_CONTENT_NOT_VERIFIED"],
        )
        return ArtworkResult(
            artifact_ref=str(path),
            provider=self.provider,
            model=self.model,
            request_id=request_id,
            prompt_hash=prompt_hash,
            width=request.target_width_px,
            height=request.target_height_px,
            format="png",
            sha256=digest,
            latency_ms=provenance.latency_ms,
            provenance=provenance,
        )
