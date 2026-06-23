from __future__ import annotations

from ocop_pack.domain.project import ProjectSpec


class FixtureArtworkProvider:
    def load_artwork(self, project: ProjectSpec) -> dict[str, object]:
        logos = [
            {"asset_id": logo.asset_id, "path": str(logo.path)} for logo in project.branding.logos
        ]
        return {
            "provider": "fixture",
            "logos": logos,
            "ocop_logo": str(project.branding.ocop.logo_path),
        }
