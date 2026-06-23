from ocop_pack.domain.dieline import load_dieline
from ocop_pack.domain.geometry import BoundingBox, float_eq


def test_size_profiles_and_panels():
    d = load_dieline("OCOP_130X150")
    assert d.vertical_folds_x_mm == [28.6, 101.4]
    widths = [p.bbox_mm.width_mm for p in d.panels()]
    assert all(float_eq(a, b) for a, b in zip(widths, [28.6, 72.8, 28.6], strict=True))
    d2 = load_dieline("OCOP_156X180")
    assert [round(p.bbox_mm.width_mm, 2) for p in d2.panels()] == [34.32, 87.36, 34.32]


def test_bbox_ops_and_fold_exclusion():
    a = BoundingBox(x_mm=0, y_mm=0, width_mm=10, height_mm=10)
    b = BoundingBox(x_mm=5, y_mm=5, width_mm=2, height_mm=2)
    assert a.contains(b) and a.intersects(b) and a.intersection_area(b) == 4
    d = load_dieline("OCOP_130X150")
    assert d.canvas().crosses_vertical_fold(BoundingBox(x_mm=27, y_mm=20, width_mm=4, height_mm=20))
