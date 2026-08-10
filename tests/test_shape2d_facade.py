# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Test suite for the backend-neutral 2D shape facade (pybosl2/shape2d.py)."""

from pybosl2 import shape2d
from pybosl2._backend import current_backend, use_backend
from pybosl2.shape2d import Shape2D


def test_facade_defaults_to_csg() -> None:
    """Verify that shape2d defaults to csg backend."""
    s = shape2d.circle(radius=10)
    assert s.backend == "csg"
    assert type(s).__name__ == "CsgShape2D"
    assert isinstance(s, Shape2D)


def test_facade_obeys_use_backend_context() -> None:
    """Verify that use_backend changes the returned shape backend."""
    assert current_backend() == "csg"
    with use_backend("sdf"):
        s = shape2d.circle(radius=10)
        assert s.backend == "sdf"
        assert type(s).__name__ == "SdfShape2D"
    assert shape2d.square(5).backend == "csg"


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
