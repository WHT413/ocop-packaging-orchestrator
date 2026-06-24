from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageDraw

from ocop_pack.application.ports.artwork_provider import ArtworkRequest, ArtworkResult
from ocop_pack.provenance.models import ArtworkProvenance, ProviderContext
from ocop_pack.services.validation_service import file_sha256


class FixtureArtworkProvider:
    provider = "fixture"
    model = "fixture-v1"

    def generate(
        self, request: ArtworkRequest, context: ProviderContext, output_dir: Path
    ) -> ArtworkResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{request.concept_id}.png"
        if not path.exists():
            image = Image.new("RGB", (request.target_width_px, request.target_height_px), "#f5f0dc")
            draw = ImageDraw.Draw(image)
            for i in range(0, request.target_width_px, 80):
                draw.ellipse(
                    (i, i % request.target_height_px, i + 120, i % request.target_height_px + 50),
                    fill="#7f9f68",
                )
            image.save(path, format="PNG")
        digest = file_sha256(path)
        prompt_hash = sha256(request.prompt.encode("utf-8")).hexdigest()
        negative_hash = sha256(request.negative_prompt.encode("utf-8")).hexdigest()
        prov = ArtworkProvenance(
            artifact_id=request.concept_id,
            artifact_sha256=digest,
            provider=self.provider,
            model=self.model,
            provider_request_id=f"fixture-{context.run_id}-{request.concept_id}",
            prompt_id="design_planner.artwork",
            prompt_version="v1",
            prompt_hash=prompt_hash,
            negative_prompt_hash=negative_hash,
            input_hash=request.request_hash,
            width=request.target_width_px,
            height=request.target_height_px,
            format="png",
            warning_codes=["ARTWORK_CONTENT_NOT_VERIFIED"],
        )
        return ArtworkResult(
            artifact_ref=str(path),
            provider=self.provider,
            model=self.model,
            request_id=prov.provider_request_id,
            prompt_hash=prompt_hash,
            width=request.target_width_px,
            height=request.target_height_px,
            format="png",
            sha256=digest,
            provenance=prov,
        )
