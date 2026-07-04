from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

from ocop_pack.application.ports.artwork_revision import (
    ArtworkRevisionRequest,
    RevisedArtworkArtifact,
)
from ocop_pack.provenance.models import ProviderContext, RevisionProvenance
from ocop_pack.services.validation_service import file_sha256


class FixtureArtworkRevisionProvider:
    provider = "fixture"
    model = "fixture-editor-v1"

    def revise(
        self, request: ArtworkRevisionRequest, context: ProviderContext, output_dir: Path
    ) -> RevisedArtworkArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{request.source_artwork_id}.rev1.png"
        with Image.open(request.source_artwork_path) as source:
            image = source.convert("RGB")
        image = ImageEnhance.Color(ImageOps.autocontrast(image)).enhance(0.7)
        image = ImageEnhance.Brightness(image).enhance(1.08)
        image.save(path, format="PNG")
        digest = file_sha256(path)
        instruction = request.targeted_revision.model_dump_json()
        provenance = RevisionProvenance(
            parent_artwork_id=request.source_artwork_id,
            parent_artwork_hash=request.source_artwork_hash,
            issue_code=request.targeted_revision.issue_code,
            instruction_hash=sha256(instruction.encode("utf-8")).hexdigest(),
            prohibited_content_hash=sha256(b"artwork-only").hexdigest(),
            provider=self.provider,
            model=self.model,
            provider_request_id=f"fixture-revision-{context.run_id}-{request.source_artwork_id}",
            result_hash=digest,
            width=image.width,
            height=image.height,
        )
        return RevisedArtworkArtifact(
            artifact_ref=str(path),
            artifact_id=request.source_artwork_id,
            sha256=digest,
            width=image.width,
            height=image.height,
            provider=self.provider,
            model=self.model,
            request_id=provenance.provider_request_id,
            provenance=provenance,
        )
