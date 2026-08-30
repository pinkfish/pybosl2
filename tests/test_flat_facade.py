# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Test suite for the backend-neutral flat shape facade (pybosl2/flat.py)."""

import pytest

from pybosl2 import Path2D, flat
from pybosl2._backend import current_backend, use_backend
from pybosl2.flat import Flat


def test_facade_defaults_to_csg() -> None:
    """Verify that flat facade defaults to csg backend."""
    s = flat.circle(radius=10)
    assert s.backend == "csg"
    assert type(s).__name__ == "CsgShape2D"
    assert isinstance(s, Flat)


def test_facade_obeys_use_backend_context() -> None:
    """Verify that use_backend changes the returned shape backend."""
    assert current_backend() == "csg"
    with use_backend("sdf"):
        s = flat.circle(radius=10)
        assert s.backend == "sdf"
        assert type(s).__name__ == "SdfShape2D"
    assert flat.square(5).backend == "csg"


def test_top_level_exports_obey_backend() -> None:
    """Verify that top-level lazy exports route through facade and respect active backend."""
    from pybosl2 import circle, rect, square

    c = circle(radius=10)
    assert c.backend == "csg"
    assert type(c).__name__ == "CsgShape2D"

    with use_backend("sdf"):
        c_sdf = circle(radius=10)
        assert c_sdf.backend == "sdf"
        assert type(c_sdf).__name__ == "SdfShape2D"

        sq_sdf = square(size=10)
        assert sq_sdf.backend == "sdf"

        r_sdf = rect(size=[20, 10])
        assert r_sdf.backend == "sdf"


def test_square_sdf_anchor_fallback() -> None:
    """SDF square() falls back to list(anchor) when resolve_anchor fails."""
    with use_backend("sdf"):
        s = flat.square(size=10, anchor=(1.0,))
        assert s.backend == "sdf"


def test_rect_sdf_anchor_fallback() -> None:
    """SDF rect() falls back to list(anchor) when resolve_anchor fails."""
    with use_backend("sdf"):
        r = flat.rect(size=[20, 10], anchor=(1.0,))
        assert r.backend == "sdf"


def test_rect_csg_path() -> None:
    """flat.rect() returns CSG shape on default backend."""
    r = flat.rect(size=[20, 10])
    assert r.backend == "csg"
    assert isinstance(r, Flat)


def test_polygon_sdf_path() -> None:
    """flat.polygon() returns SDF shape under SDF backend."""
    with use_backend("sdf"):
        p = flat.polygon(points=Path2D([[0, 0], [10, 0], [5, 10]]))
        assert p.backend == "sdf"


def test_polygon_csg_path() -> None:
    """flat.polygon() returns CSG shape on default backend."""
    p = flat.polygon(points=Path2D([[0, 0], [10, 0], [5, 10]]))
    assert p.backend == "csg"
    assert isinstance(p, Flat)


def test_text_sdf_raises() -> None:
    """flat.text() raises UnsupportedByBackendError on SDF backend."""
    from pybosl2.exceptions import UnsupportedByBackendError

    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError):
        flat.text("hello")


def test_text_csg_path() -> None:
    """flat.text() returns CSG shape on default backend."""
    t = flat.text("hello", size=5)
    assert t.backend == "csg"
    assert isinstance(t, Flat)


class TestShapeGeometry:
    """Verify actual geometry: bounds, extrusion, and cross-backend consistency."""

    # ---- circle ----

    def test_circle_centered_by_default(self) -> None:
        c = flat.circle(radius=10)
        _box = c.bounds()
        center = list(_box.center)
        assert center[0] == pytest.approx(0, abs=0.01)
        assert center[1] == pytest.approx(0, abs=0.01)

    def test_circle_diameter_param(self) -> None:
        c = flat.circle(diameter=20)
        _box = c.bounds()
        size = list(_box.size)
        assert size[0] == pytest.approx(20, abs=1.0)
        assert size[1] == pytest.approx(20, abs=1.0)

    def test_circle_csg_vs_sdf_same_size(self) -> None:
        csg = flat.circle(radius=10)
        with use_backend("sdf"):
            sdf = flat.circle(radius=10)
        _box = csg.bounds()
        s_csg = list(_box.size)
        _box = sdf.bounds()
        s_sdf = list(_box.size)
        assert s_sdf[0] == pytest.approx(s_csg[0], abs=1.0)
        assert s_sdf[1] == pytest.approx(s_csg[1], abs=1.0)

    # ---- square ----

    def test_square_is_square(self) -> None:
        s = flat.square(size=[20, 30])
        _box = s.bounds()
        size = list(_box.size)
        assert size[0] == pytest.approx(20, abs=0.01)
        assert size[1] == pytest.approx(30, abs=0.01)

    def test_square_sdf_exact_bounds(self) -> None:
        with use_backend("sdf"):
            s = flat.square(size=10)
            _box = s.bounds()
            center, size = list(_box.center), list(_box.size)
            assert size[0] == pytest.approx(10, abs=0.01)
            assert size[1] == pytest.approx(10, abs=0.01)
            assert center[0] == pytest.approx(0, abs=0.01)

    # ---- rect ----

    def test_rect_aspect_ratio(self) -> None:
        r = flat.rect(size=[20, 10])
        _box = r.bounds()
        size = list(_box.size)
        assert size[0] / size[1] == pytest.approx(2.0, abs=0.01)

    def test_rect_csg_vs_sdf_same_size(self) -> None:
        csg = flat.rect(size=[30, 15])
        with use_backend("sdf"):
            sdf = flat.rect(size=[30, 15])
        _box = csg.bounds()
        _, s_csg = list(_box.center), list(_box.size)
        _box = sdf.bounds()
        _, s_sdf = list(_box.center), list(_box.size)
        assert s_sdf[0] == pytest.approx(s_csg[0], abs=0.5)
        assert s_sdf[1] == pytest.approx(s_csg[1], abs=0.5)

    # ---- polygon ----

    def test_polygon_triangle_bounds(self) -> None:
        pts = [[0, 0], [8, 0], [4, 6]]
        p = flat.polygon(points=Path2D(pts))
        _box = p.bounds()
        size = list(_box.size)
        assert size[0] == pytest.approx(8, abs=0.01)
        assert size[1] == pytest.approx(6, abs=0.01)

    def test_polygon_csg_vs_sdf_same_bounds(self) -> None:
        pts = [[0, 0], [10, 0], [6, 8]]
        csg = flat.polygon(points=Path2D(pts))
        with use_backend("sdf"):
            sdf = flat.polygon(points=Path2D(pts))
        _box = csg.bounds()
        _, s_csg = list(_box.center), list(_box.size)
        _box = sdf.bounds()
        _, s_sdf = list(_box.center), list(_box.size)
        assert s_sdf[0] == pytest.approx(s_csg[0], abs=0.5)
        assert s_sdf[1] == pytest.approx(s_csg[1], abs=0.5)

    def test_polygon_concave_shape(self) -> None:
        pts = [[0, 0], [10, 0], [10, 5], [5, 2], [10, 10], [0, 10]]
        p = flat.polygon(points=Path2D(pts))
        _box = p.bounds()
        size = list(_box.size)
        assert size[0] == pytest.approx(10, abs=0.01)
        assert size[1] == pytest.approx(10, abs=0.01)

    # ---- extrusion to 3-D ----

    def test_square_extrudes_to_correct_height(self) -> None:
        s = flat.square(size=10)
        solid = s.linear_extrude(height=5)
        _box = solid.bounds()
        size3d = list(_box.size)
        assert size3d[2] == pytest.approx(5, abs=0.01)

    def test_square_sdf_extrudes_to_correct_height(self) -> None:
        with use_backend("sdf"):
            s = flat.square(size=10)
            solid = s.linear_extrude(height=5, center=True)
            _box = solid.bounds()
            size3d = list(_box.size)
            assert size3d[2] == pytest.approx(5, abs=0.01)

    def test_circle_extrudes_keeps_xy_bounds(self) -> None:
        c = flat.circle(radius=10)
        _box = c.bounds()
        size2d = list(_box.size)
        solid = c.linear_extrude(height=5)
        _box = solid.bounds()
        size3d = list(_box.size)
        assert size3d[0] == pytest.approx(size2d[0], abs=1.0)
        assert size3d[1] == pytest.approx(size2d[1], abs=1.0)

    # ---- text ----

    def test_text_has_nonzero_area(self) -> None:
        t = flat.text("Q", size=20)
        _box = t.bounds()
        size = list(_box.size)
        assert size[0] > 2
        assert size[1] > 2
