from ocop_pack.domain.dieline import load_dieline
from ocop_pack.engine.candidate_generator import generate_candidates


def test_manifest_snapshot_semantic(example_project):
    d = load_dieline(example_project.packaging.size_id)
    c = generate_candidates(example_project, d)[0]
    assert c.candidate_id == "C001"
    assert {e.element_id for e in c.elements} >= {"title", "qr", "ocop_lockup"}
    lockup = next(e for e in c.elements if e.element_id == "ocop_lockup")
    assert lockup.metadata["star_count"] == 3
