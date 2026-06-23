from pathlib import Path

from ocop_pack.domain.dieline import load_dieline
from ocop_pack.domain.layout import LayoutManifest
from ocop_pack.engine.candidate_generator import generate_candidates
from ocop_pack.services.render_service import render_manifest
from ocop_pack.services.validation_service import load_project

p = load_project(Path("examples/projects/tea_basic/project.yaml"))
d = load_dieline(p.packaging.size_id)
c = generate_candidates(p, d)[0]
render_manifest(
    LayoutManifest(
        run_id="run_demo_001", project_id=p.project_id, dieline_version=d.version, candidate=c
    ),
    p,
    d,
    Path("runs/run_demo_001"),
)
