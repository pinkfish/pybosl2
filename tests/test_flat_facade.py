# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Test suite for the backend-neutral flat shape facade (pybosl2/flat.py)."""

import pytest

from pybosl2 import flat
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
        p = flat.polygon(points=[[0, 0], [10, 0], [5, 10]])
        assert p.backend == "sdf"


def test_polygon_csg_path() -> None:
    """flat.polygon() returns CSG shape on default backend."""
    p = flat.polygon(points=[[0, 0], [10, 0], [5, 10]])
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


class TestShapeBounds:
    """Verify that flat facade shapes produce correct geometry bounds."""

    def test_circle_csg_bounds(self) -> None:
        c = flat.circle(radius=10)
        center, size = c.bounds()
        assert size[0] == pytest.approx(20, abs=1.0)
        assert size[1] == pytest.approx(20, abs=1.0)

    def test_circle_sdf_bounds(self) -> None:
        with use_backend("sdf"):
            c = flat.circle(radius=10)
            center, size = c.bounds()
            assert size[0] == pytest.approx(20, abs=0.01)
            assert size[1] == pytest.approx(20, abs=0.01)

    def test_square_csg_bounds(self) -> None:
        s = flat.square(size=10)
        center, size = s.bounds()
        assert size[0] == pytest.approx(10, abs=0.01)
        assert size[1] == pytest.approx(10, abs=0.01)

    def test_square_sdf_bounds(self) -> None:
        with use_backend("sdf"):
            s = flat.square(size=10)
            center, size = s.bounds()
            assert size[0] == pytest.approx(10, abs=0.01)
            assert size[1] == pytest.approx(10, abs=0.01)

    def test_square_scalar_shortcut(self) -> None:
        """flat.square(5) is shorthand for size=[5, 5]."""
        s = flat.square(5)
        center, size = s.bounds()
        assert size[0] == pytest.approx(5, abs=0.01)
        assert size[1] == pytest.approx(5, abs=0.01)

    def test_rect_csg_bounds(self) -> None:
        r = flat.rect(size=[20, 10])
        center, size = r.bounds()
        assert size[0] == pytest.approx(20, abs=0.01)
        assert size[1] == pytest.approx(10, abs=0.01)

    def test_rect_sdf_bounds(self) -> None:
        with use_backend("sdf"):
            r = flat.rect(size=[20, 10])
            center, size = r.bounds()
            assert size[0] == pytest.approx(20, abs=0.01)
            assert size[1] == pytest.approx(10, abs=0.01)

    def test_polygon_csg_bounds(self) -> None:
        p = flat.polygon(points=[[0, 0], [10, 0], [5, 10]])
        center, size = p.bounds()
        assert size[0] == pytest.approx(10, abs=0.01)
        assert size[1] == pytest.approx(10, abs=0.01)

    def test_polygon_sdf_bounds(self) -> None:
        with use_backend("sdf"):
            p = flat.polygon(points=[[0, 0], [10, 0], [5, 10]])
            center, size = p.bounds()
            assert size[0] == pytest.approx(10, abs=0.01)
            assert size[1] == pytest.approx(10, abs=0.01)

    def test_text_csg_has_positive_bounds(self) -> None:
        t = flat.text("hello", size=5)
        center, size = t.bounds()
        assert size[0] > 0
        assert size[1] > 0
