from __future__ import annotations

from pathlib import Path

import pytest

from ocop_pack.application.ports.artwork_provider import ArtworkRequest
from ocop_pack.provenance.models import ProviderContext
from ocop_pack.providers.common.errors import ProviderSchemaError
from ocop_pack.providers.image.openai_compatible import OpenAICompatibleImageProvider


@pytest.mark.provider_sandbox
def test_genimage_single_artwork_probe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    if not bool(__import__("os").environ.get("OCOP_RUN_GENIMAGE_PROBE")):
        pytest.skip("Set OCOP_RUN_GENIMAGE_PROBE=1 to spend exactly one image generation call.")

    monkeypatch.setenv("OCOP_IMAGE_PROVIDER", "openai-compatible")
    request = ArtworkRequest(
        concept_id="genimage_probe",
        prompt=(
            "Create a square 1:1 image at 1024x1024 pixels. Small plain botanical "
            "background texture, green tea leaves, centered composition, seamless full-frame "
            "artwork background, no text, no logo, no packaging, no label, no QR code."
        ),
        negative_prompt=(
            "No words, letters, numbers, logos, labels, QR codes, packaging mockups. "
            "Do not use portrait or landscape aspect ratio; square 1:1 only."
        ),
        target_width_px=1024,
        target_height_px=1024,
        request_hash="genimage-probe-v1",
    )

    try:
        result = OpenAICompatibleImageProvider().generate(
            request,
            ProviderContext(
                run_id="genimage_probe", thread_id="genimage_probe", node="sandbox_probe"
            ),
            tmp_path,
        )
    except ProviderSchemaError as exc:
        if "404" in str(exc):
            pytest.xfail(
                "Configured genImage endpoint does not expose OpenAI /images/generations; "
                "use the provider's native Gemini image endpoint or add a compatible adapter."
            )
        raise

    assert result.provider == "openai-compatible"
    assert result.model
    assert result.width == 1024
    assert result.height == 1024
    assert Path(result.artifact_ref).exists()
    assert result.provenance is not None
    if result.provenance.normalization_policy != "none":
        assert "PROVIDER_DIMENSION_NORMALIZED" in result.provenance.warning_codes
