# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Milestone 7 of the CSG/SDF merge: the unified backend test matrix.

Every shared 3-D constructor in the ``pybosl2.solid`` facade is exercised against BOTH backends from a
single parameter table, so the shared surface is tested once rather than per backend. Construction
and ``bounds()`` are FFI-free on both backends (the SDF side reads the distance field's domain, not a
mesh), so this whole matrix runs without libfive installed -- no skips.

A coverage guard asserts the table matches ``solid._SHARED_3D`` exactly, so adding a shared
constructor without a matrix row (or vice-versa) fails loudly instead of silently going untested.
"""

import pytest

from pybosl2 import solid
from pybosl2._backend import Solid, use_backend

# name -> (args, kwargs, expected_size, agree)
#   expected_size: nominal [x, y, z] bounding size both backends should produce (None = don't assert)
#   agree:         whether the two backends' bounds() must match each other (False for shapes whose
#                  SDF bounds() reports a conservative construction domain rather than the tight bbox)
SHARED_SHAPES = {
    "cube": ((10,), {}, [10, 10, 10], True),
    "cuboid": (([12, 8, 6],), {}, [12, 8, 6], True),
    "cyl": ((), {"height": 20, "radius": 5}, [10, 10, 20], True),
    "cylinder": ((), {"height": 20, "radius": 5}, [10, 10, 20], True),
    "octahedron": ((10,), {}, [10, 10, 10], True),
    "onion": ((), {"radius": 10}, None, True),
    "pie_slice": ((), {"height": 10, "radius": 8, "angle": 45}, None, False),  # SDF bounds = full disc
    "prismoid": ((), {"size1": [10, 10], "size2": [6, 6], "height": 8}, [10, 10, 8], True),
    "rect_tube": ((), {"height": 10, "size": [20, 20], "wall": 2}, [20, 20, 10], True),
    "regular_prism": ((6,), {"height": 10, "radius": 8}, None, False),
    "sphere": ((), {"radius": 10}, [20, 20, 20], True),
    "spheroid": ((), {"radius": 10}, [20, 20, 20], True),
    "teardrop": ((), {"height": 10, "radius": 8}, None, True),
    "torus": ((), {"major_radius": 20, "minor_radius": 5}, [50, 50, 10], True),
    "tube": ((), {"height": 10, "outer_radius": 10, "inner_radius": 6}, [20, 20, 10], True),
    "wedge": (([10, 8, 6],), {}, [10, 8, 6], True),
    "xcyl": ((), {"length": 20, "radius": 5}, [20, 10, 10], True),
    "ycyl": ((), {"length": 20, "radius": 5}, [10, 20, 10], True),
    "zcyl": ((), {"length": 20, "radius": 5}, [10, 10, 20], True),
}

TOL = 0.8  # CSG faceting makes sizes fall slightly short of nominal


def test_matrix_covers_every_shared_constructor() -> None:
    """Guard against drift: the matrix must exercise exactly the facade's shared 3-D surface."""
    assert set(SHARED_SHAPES) == set(solid._SHARED_3D)


@pytest.mark.parametrize("backend", ["csg", "sdf"])
@pytest.mark.parametrize("name", list(SHARED_SHAPES))
def test_shared_constructor_builds_on_backend(name, backend) -> None:  # type: ignore[no-untyped-def]
    args, kwargs, expected, _ = SHARED_SHAPES[name]
    with use_backend(backend):
        s = getattr(solid, name)(*args, **kwargs)  # type: ignore[arg-type]
    assert s.backend == backend
    assert isinstance(s, Solid)
    size = s.bounds()[1]
    assert len(size) == 3, f"{name} on {backend}: degenerate bounds {size}"
    assert all(v > 0 for v in size), f"{name} on {backend}: degenerate bounds {size}"
    if expected is not None:
        for got, want in zip(size, expected, strict=False):
            assert abs(got - want) < TOL, f"{name} on {backend}: size {size} != nominal {expected}"


@pytest.mark.parametrize("name", list(SHARED_SHAPES))
def test_both_backends_agree_on_bounds(name) -> None:  # type: ignore[no-untyped-def]
    args, kwargs, _, agree = SHARED_SHAPES[name]
    csg = getattr(solid, name)(*args, **kwargs)  # type: ignore[arg-type]
    with use_backend("sdf"):
        sdf = getattr(solid, name)(*args, **kwargs)  # type: ignore[arg-type]
    assert csg.backend == "csg"
    assert sdf.backend == "sdf"
    if not agree:
        return  # bounds() legitimately differ (SDF reports a conservative construction domain)
    for c, s in zip(csg.bounds()[1], sdf.bounds()[1], strict=False):
        assert abs(c - s) < TOL, f"{name}: backends disagree on bounds ({c} vs {s})"


@pytest.mark.parametrize("backend", ["csg", "sdf"])
@pytest.mark.parametrize("op", ["union", "difference", "intersection"])
def test_boolean_ops_dispatch_on_active_backend(backend, op) -> None:  # type: ignore[no-untyped-def]
    with use_backend(backend):
        a = solid.cube(10)  # type: ignore[attr-defined]
        b = solid.sphere(radius=6)  # type: ignore[attr-defined]
        result = getattr(solid, op)(a, b)
    assert result.backend == backend
    assert isinstance(result, Solid)


# ---------------------------------------------------------------------------
# 2-D -> 3-D: Path2D/Region extrude on either backend
# ---------------------------------------------------------------------------

SQUARE = [[0, 0], [20, 0], [20, 12], [0, 12]]


@pytest.mark.parametrize("backend", ["csg", "sdf"])
def test_path_linear_extrude_dispatches_on_active_backend(backend) -> None:  # type: ignore[no-untyped-def]
    from pybosl2.path2d import Path2D

    with use_backend(backend):
        s = Path2D(SQUARE).linear_extrude(height=5)
    assert s.backend == backend
    assert isinstance(s, Solid)
    for got, want in zip(s.bounds()[1], [20, 12, 5], strict=False):
        assert abs(got - want) < TOL, f"path extrude on {backend}: size {s.bounds()[1]}"


@pytest.mark.parametrize("backend", ["csg", "sdf"])
def test_path_linear_extrude_center_lands_on_the_origin(backend) -> None:  # type: ignore[no-untyped-def]
    from pybosl2.path2d import Path2D

    with use_backend(backend):
        s = Path2D(SQUARE).linear_extrude(height=5, center=True)
    assert abs(s.bounds()[0][2]) < TOL, "center=True should straddle z=0 on both backends"


@pytest.mark.parametrize("backend", ["csg", "sdf"])
def test_single_outline_region_extrudes_on_both_backends(backend) -> None:  # type: ignore[no-untyped-def]
    from pybosl2.regions import Region

    with use_backend(backend):
        s = Region([SQUARE]).linear_extrude(height=5)
    assert s.backend == backend
    for got, want in zip(s.bounds()[1], [20, 12, 5], strict=False):
        assert abs(got - want) < TOL


def test_region_with_holes_extrudes_only_on_csg() -> None:
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.regions import Region

    plate = Region.with_holes(SQUARE, [[5, 3], [15, 3], [15, 9], [5, 9]])  # type: ignore[arg-type]
    assert plate.linear_extrude(height=5).backend == "csg"
    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError):
        plate.linear_extrude(height=5)


def test_sdf_extrude_rejects_the_profile_shearing_options() -> None:
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.path2d import Path2D

    for kw in ({"twist": 45}, {"scale": 2}, {"slices": 8}):
        with use_backend("sdf"), pytest.raises(UnsupportedByBackendError):
            Path2D(SQUARE).linear_extrude(height=5, **kw)
    # ...but the CSG backend takes them all
    for kw in ({"twist": 45}, {"scale": 2}, {"slices": 8}):
        assert Path2D(SQUARE).linear_extrude(height=5, **kw).backend == "csg"


def test_sdf_extrude_takes_the_rim_roundings() -> None:
    from pybosl2.path2d import Path2D

    with use_backend("sdf"):
        s = Path2D(SQUARE).linear_extrude(height=5, rounding_top=1, rounding_bottom=1)
    assert s.backend == "sdf"


# ---------------------------------------------------------------------------
# 2-D geometry is a csg-only notion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("call", ["polygon", "geometry", "fill", "rotate_extrude"])
def test_path_2d_geometry_is_csg_only(call) -> None:  # type: ignore[no-untyped-def]
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.path2d import Path2D

    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError):
        getattr(Path2D(SQUARE), call)()


def test_2d_shape_constructors_stay_on_csg() -> None:
    # shapes2d builds exact 2-D geometry, which has no SDF counterpart -- it does NOT silently
    # change meaning inside a use_backend("sdf") block.
    import pybosl2.shapes2d as s2
    from pybosl2.shapes2d import Bosl2Shape2D

    with use_backend("sdf"):
        shape = s2.square(10)
    assert isinstance(shape, Bosl2Shape2D)
    assert shape.backend == "csg"


# ---------------------------------------------------------------------------
# hull() / projection() on the 3-D object, per backend
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend", ["csg", "sdf"])
def test_solid_hull_dispatches_on_active_backend(backend) -> None:  # type: ignore[no-untyped-def]
    with use_backend(backend):
        capsule = solid.cube(10).hull(solid.cube(10).translate([0, 0, 30]))  # type: ignore[attr-defined]
    assert capsule.backend == backend
    for got, want in zip(capsule.bounds()[1], [10, 10, 40], strict=False):
        assert abs(got - want) < TOL, f"hull on {backend}: size {capsule.bounds()[1]}"


def test_projection_is_csg_only() -> None:
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.shapes2d import Bosl2Shape2D

    assert isinstance(solid.cuboid([30, 20, 10]).projection(), Bosl2Shape2D)  # type: ignore[attr-defined]
    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError):
        solid.cuboid([30, 20, 10]).projection()  # type: ignore[attr-defined]


def test_fill_is_csg_only_on_a_solid() -> None:
    from pybosl2.exceptions import UnsupportedByBackendError

    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError):
        solid.cube(10).fill()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# stroke(): a 3-D stroke follows the active backend, a 2-D one is csg-only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend", ["csg", "sdf"])
def test_stroke_of_a_3d_path_follows_the_active_backend(backend) -> None:  # type: ignore[no-untyped-def]
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [0, 0, 20], [10, 0, 30]], closed=False)
    with use_backend(backend):
        tube = spine.stroke(width=3)
    assert tube.backend == backend, "stroke() must not force everything onto csg"
    assert isinstance(tube, Solid)


def test_stroke_of_a_2d_path_is_csg_only() -> None:
    from pybosl2.path2d import Path2D

    flat = Path2D([[0, 0], [20, 0], [20, 20]], closed=False)
    assert isinstance(flat.stroke(width=3), Path2D)


def test_sdf_stroke_rejects_a_revolved_endcap() -> None:
    from pybosl2.caps import CapType
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [0, 0, 20]], closed=False)
    with use_backend("sdf"):
        assert spine.stroke(width=3, endcaps=CapType.ROUND).backend == "sdf"  # sphere caps are shared
        with pytest.raises(UnsupportedByBackendError):
            spine.stroke(width=3, endcaps=CapType.ARROW)


# -- SDF stroke native tests --------------------------------------------------


def test_sdf_stroke_basic_open_path() -> None:
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0]], closed=False)
    with use_backend("sdf"):
        tube = spine.stroke(width=2)
    assert tube.backend == "sdf"


def test_sdf_stroke_closed_loop() -> None:
    from pybosl2.path3d import Path3D

    loop = Path3D([[10, 0, 0], [0, 10, 0], [-10, 0, 0], [0, -10, 0]], closed=True)
    with use_backend("sdf"):
        tube = loop.stroke(width=1.5)
    assert tube.backend == "sdf"


def test_sdf_stroke_two_point_segment() -> None:
    from pybosl2.path3d import Path3D

    line = Path3D([[0, 0, 0], [0, 0, 50]], closed=False)
    with use_backend("sdf"):
        tube = line.stroke(width=5)
    assert tube.backend == "sdf"


def test_sdf_stroke_zero_length_segment_is_skipped() -> None:
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [0, 0, 0], [10, 0, 0]], closed=False)
    with use_backend("sdf"):
        tube = spine.stroke(width=1)
    assert tube.backend == "sdf"


def test_sdf_stroke_butt_endcaps() -> None:
    from pybosl2.caps import CapType
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [20, 0, 0], [20, 0, 20]], closed=False)
    with use_backend("sdf"):
        tube = spine.stroke(width=2, endcaps=CapType.BUTT)
    assert tube.backend == "sdf"


def test_sdf_stroke_dot_endcaps() -> None:
    from pybosl2.caps import CapType
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [20, 0, 0]], closed=False)
    with use_backend("sdf"):
        tube = spine.stroke(width=2, endcaps=CapType.DOT)
    assert tube.backend == "sdf"


def test_sdf_stroke_diamond_cap_raises() -> None:
    from pybosl2.caps import CapType
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [20, 0, 0]], closed=False)
    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError):
        spine.stroke(width=2, endcaps=CapType.DIAMOND)


def test_sdf_stroke_chisel_cap_raises() -> None:
    from pybosl2.caps import CapType
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [20, 0, 0]], closed=False)
    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError):
        spine.stroke(width=2, endcaps=CapType.CHISEL)


def test_sdf_stroke_none_cap_skipped() -> None:
    from pybosl2.caps import CapType
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [20, 0, 0]], closed=False)
    with use_backend("sdf"):
        tube = spine.stroke(width=2, endcaps=CapType.NONE)
    assert tube.backend == "sdf"


def test_sdf_stroke_3d_diagonal() -> None:
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [10, 10, 10], [20, 0, 20]], closed=False)
    with use_backend("sdf"):
        tube = spine.stroke(width=1)
    assert tube.backend == "sdf"
