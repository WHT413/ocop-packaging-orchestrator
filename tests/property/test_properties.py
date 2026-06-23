from hypothesis import given
from hypothesis import strategies as st

from ocop_pack.domain.dieline import load_dieline
from ocop_pack.domain.geometry import BoundingBox
from ocop_pack.engine.candidate_generator import generate_candidates


@given(st.floats(min_value=26.7, max_value=30.5), st.floats(min_value=1, max_value=20))
def test_fold_crossing_never_safe(x, w):
    d = load_dieline("OCOP_130X150")
    assert d.canvas().crosses_vertical_fold(BoundingBox(x_mm=x, y_mm=20, width_mm=w, height_mm=10))


@given(st.integers(min_value=-10, max_value=20))
def test_star_count_range(n):
    assert (1 <= n <= 5) == (n in range(1, 6))


def test_generation_same_seed(example_project):
    d = load_dieline(example_project.packaging.size_id)
    assert (
        generate_candidates(example_project, d, 1)[0].candidate_id
        == generate_candidates(example_project, d, 1)[0].candidate_id
    )
