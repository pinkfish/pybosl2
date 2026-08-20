# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The exclusive-feature lists must match the implementations (SPEC PAR-3, PLAN B-P4).

A name listed as exclusive to one backend but implemented on the other is worse than no list at
all: the refusal never fires, and the two records of what a backend can do disagree.
"""

from __future__ import annotations

import inspect

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
from pybosl2._backend import CSG_ONLY_FEATURES, SDF_ONLY_FEATURES
from pybosl2.sdf.shapes3d import SdfSolid
from pybosl2.shapes3d.base import CsgSolid


def test_csg_only_features_are_absent_from_the_sdf_shape() -> None:
    implemented = sorted(f for f in CSG_ONLY_FEATURES if inspect.getattr_static(SdfSolid, f, None) is not None)
    assert not implemented, "listed as CSG-only but implemented on SdfSolid, so the refusal never fires: " + ", ".join(
        implemented
    )


def test_sdf_only_features_are_absent_from_the_csg_shape() -> None:
    implemented = sorted(f for f in SDF_ONLY_FEATURES if inspect.getattr_static(CsgSolid, f, None) is not None)
    assert not implemented, "listed as SDF-only but implemented on CsgSolid: " + ", ".join(implemented)


def test_the_refusal_names_the_explicit_conversion() -> None:
    import pytest

    from pybosl2._backend import use_backend
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
        with pytest.raises(UnsupportedByBackendError, match=r"\.to_csg\(\)"):
            shape.projection()


def test_sdf_shapes_keep_their_backend_through_moves_and_colour() -> None:
    """Modelling operations stay in the field instead of meshing behind the caller's back.

    `up()` and `color()` used to fall through to `getattr(self.mesh(), name)`, which returned a
    raw native handle with no backend tag (SPEC C-1, B-5, PLAN E-P6).
    """
    from pybosl2._backend import use_backend
    from pybosl2.color import Color
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        moved = cuboid([10, 10, 10]).up(5).right(2).fwd(1)
        assert isinstance(moved, SdfSolid)
        assert moved.backend == "sdf"
        assert moved.bounds() == ([2.0, -1.0, 5.0], [10.0, 10.0, 10.0])

        coloured = cuboid([10, 10, 10]).color(Color("red")).ghost()
        assert isinstance(coloured, SdfSolid)
        assert coloured.backend == "sdf"
        # the appearance rides along with the field rather than forcing an early mesh
        assert coloured.bounds() == cuboid([10, 10, 10]).bounds()


def test_an_unknown_operation_refuses_instead_of_meshing() -> None:
    """The fallback no longer converts a field to a mesh to answer a name it does not know."""
    import pytest

    from pybosl2._backend import use_backend
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
        with pytest.raises(UnsupportedByBackendError, match=r"\.to_csg\(\)"):
            shape.no_such_operation()
