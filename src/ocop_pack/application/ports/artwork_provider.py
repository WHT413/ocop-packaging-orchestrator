from __future__ import annotations

from typing import Protocol

from ocop_pack.domain.project import ProjectSpec


class ArtworkProvider(Protocol):
    def load_artwork(self, project: ProjectSpec) -> dict[str, object]: ...
