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
    # a 45deg wedge of an r=8 disc: 8 across in X, 8*sin(45) in Y (PAR-5)
    "pie_slice": ((), {"height": 10, "radius": 8, "angle": 45}, [8, 5.657, 10], True),
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
    assert set(SHARED_SHAPES) == set(solid._SHARED_3D)  # type: ignore[attr-defined]


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


def test_2d_shape_constructors_refuse_on_another_backend() -> None:
    # A backend's own constructor no longer hands back a shape the surrounding block cannot use:
    # inside use_backend("sdf") it says so (SPEC C-1, B-4). The neutral facade is the way to build
    # on whichever backend is active, and use_backend("csg") is the explicit escape hatch.
    import pybosl2.shapes2d as s2
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.shapes2d import Bosl2Shape2D

    with use_backend("sdf"):
        with pytest.raises(UnsupportedByBackendError, match="csg"):
            s2.square(10)
        with use_backend("csg"):
            deliberate = s2.square(10)
    assert isinstance(deliberate, Bosl2Shape2D)
    assert deliberate.backend == "csg"


def test_a_csg_shape_built_inside_an_sdf_block_still_says_csg() -> None:
    # The tag records the producer, not the ambient selection, so the cross-backend guard fires
    # with a useful message instead of an AssertionError from inside the SDF backend (SPEC C-1).
    from pybosl2.exceptions import CrossBackendError
    from pybosl2.shapes3d import cuboid as csg_cuboid
    from pybosl2.solid import cuboid as neutral_cuboid

    with use_backend("sdf"):
        field = neutral_cuboid([10, 10, 10])
        with use_backend("csg"):
            csg = csg_cuboid([10, 10, 10])
        assert csg.backend == "csg"
        assert field.backend == "sdf"
        with pytest.raises(CrossBackendError):
            field - csg


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
    # It builds on csg and refuses on sdf, naming the explicit conversion: a 2-D shadow is not
    # derivable from a distance field, and meshing to answer it would cross backends silently.
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.shapes2d import Bosl2Shape2D

    shadow = solid.cuboid([30, 20, 10]).projection()  # type: ignore[attr-defined]
    assert isinstance(shadow, Bosl2Shape2D)
    # The shadow of a 30x20x10 box is its 30x20 footprint; extruding it back measures the outline.
    _, extents = shadow.linear_extrude(height=1).bounds()
    assert extents == pytest.approx([30.0, 20.0, 1.0])

    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError, match=r"\.to_csg\(\)"):
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


@pytest.mark.parametrize("width", [3, 6])
def test_stroke_of_a_2d_path_is_a_backend_free_outline(width: float) -> None:
    """A 2-D stroke is pure geometry: a closed outline half a width out from the open spine.

    It has no backend to dispatch on, so the active backend must not change the answer.
    """
    import numpy as np

    from pybosl2.path2d import Path2D

    flat = Path2D([[0, 0], [20, 0], [20, 20]], closed=False)
    outline = flat.stroke(width=width)
    assert isinstance(outline, Path2D)
    assert outline.closed  # the spine is open; its stroke is the closed boundary around it

    points = np.array(outline)
    np.testing.assert_allclose(points.min(axis=0), [-width / 2, -width / 2])
    np.testing.assert_allclose(points.max(axis=0), [20 + width / 2, 20 + width / 2])

    with use_backend("sdf"):
        under_sdf = np.array(flat.stroke(width=width))
    np.testing.assert_allclose(under_sdf, points)


def test_sdf_stroke_rejects_a_revolved_endcap() -> None:
    from pybosl2.caps import CapType
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [0, 0, 20]], closed=False)
    with use_backend("sdf"):
        assert spine.stroke(width=3, endcaps=CapType.ROUND).backend == "sdf"
        with pytest.warns(UserWarning, match="Decorative endcap"):
            result = spine.stroke(width=3, endcaps=CapType.ARROW)
        assert result.backend == "sdf"


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
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [20, 0, 0]], closed=False)
    with use_backend("sdf"), pytest.warns(UserWarning, match="Decorative endcap"):
        result = spine.stroke(width=2, endcaps=CapType.DIAMOND)
    assert result.backend == "sdf"


def test_sdf_stroke_chisel_cap_raises() -> None:
    from pybosl2.caps import CapType
    from pybosl2.path3d import Path3D

    spine = Path3D([[0, 0, 0], [20, 0, 0]], closed=False)
    with use_backend("sdf"), pytest.warns(UserWarning, match="Decorative endcap"):
        result = spine.stroke(width=2, endcaps=CapType.CHISEL)
    assert result.backend == "sdf"


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


def test_one_shape_contract_with_two_specialisations() -> None:
    """Flat and Solid extend one Shape contract rather than duplicating it (SPEC C-15, C-18)."""
    from pybosl2._backend import Shape, Solid
    from pybosl2.flat import Flat, circle
    from pybosl2.solid import cuboid

    assert Shape in Flat.__mro__
    assert Shape in Solid.__mro__

    flat_shape = circle(radius=5)
    solid_shape = cuboid([10, 10, 10])
    for shape in (flat_shape, solid_shape):
        assert isinstance(shape, Shape)
    assert isinstance(flat_shape, Flat)
    assert isinstance(solid_shape, Solid)

    # the shared surface is declared once: Flat adds only the way up into 3-D (SPEC C-17)
    own = set(vars(Flat)) - set(vars(Shape))
    assert {"linear_extrude"} <= own
    assert not {"translate", "scale", "mirror", "bounds", "show", "__or__"} & own


# ---------------------------------------------------------------------------
# B-9: the façade exposes the union, and refuses what a backend cannot honour
# ---------------------------------------------------------------------------


def test_an_argument_the_backend_cannot_honour_is_refused_not_dropped() -> None:
    """SPEC B-9. `spin=` is CSG-only, and the SDF backend used to silently ignore it.

    `for_backend()` filters the façade's arguments down to what the target constructor declares,
    which is right for a default the façade forwards on the caller's behalf and wrong for a value
    the caller asked for: `cube(10, spin=45)` came back unrotated on the SDF backend, with no
    error. Silence is the one outcome B-9 does not allow.
    """
    from pybosl2.exceptions import UnsupportedByBackendError

    with use_backend("csg"):
        assert solid.cube(10, spin=45).backend == "csg"  # type: ignore[attr-defined]

    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError, match="spin") as excinfo:
        solid.cube(10, spin=45)  # type: ignore[attr-defined]
    assert "use_backend" in str(excinfo.value)  # the message names the way forward


def test_a_facade_default_is_still_filtered_quietly() -> None:
    """B-3 still holds for the defaults the façade owns: only what was *asked for* is refused."""
    with use_backend("sdf"):
        # `spin` defaults to 0 in the façade and is forwarded to every backend; the SDF
        # constructors do not declare it, and that must stay silent.
        assert solid.cube(10).backend == "sdf"  # type: ignore[attr-defined]
        assert solid.cube(10, spin=0).backend == "sdf"  # type: ignore[attr-defined]


@pytest.mark.parametrize("kwargs", [{"fn": 64}, {"fa": 6}, {"fs": 0.5}])
def test_tessellation_arguments_are_accepted_and_ignored(kwargs: dict[str, object]) -> None:
    """B-9's carve-out: a backend with no facets is not missing a feature, so these stay silent.

    `realign` is on the same list but cannot be reached here yet: the façade does not carry it on
    `cyl` (one of the 146 parameters T14 phase 1 is widening), and where it does carry it -- on
    `regular_prism`, whose sides are exact either way -- the SDF constructor declares it, so it is
    honoured rather than ignored.
    """
    with use_backend("sdf"):
        shape = solid.cyl(height=10, radius=5, **kwargs)  # type: ignore[attr-defined]
    assert shape.backend == "sdf"
    for got, want in zip(shape.bounds()[1], [10, 10, 10], strict=False):
        assert abs(got - want) < TOL


def test_the_facade_carries_the_csg_only_taper_and_refuses_it_on_sdf() -> None:
    """The first widening under B-9: `regular_prism`'s taper, which cubetruss's feet need.

    The façade used to omit `radius1`/`radius2` entirely, so a part that tapers a prism could not
    be written against the façade at all -- it had to import the CSG constructor directly, which
    is what stops it building on either backend (TASKS T14).
    """
    from pybosl2.exceptions import UnsupportedByBackendError

    with use_backend("csg"):
        tapered = solid.regular_prism(6, height=10, radius1=8, radius2=4)  # type: ignore[attr-defined]
    _centre, size = tapered.bounds()
    assert size[0] == pytest.approx(16.0, abs=0.01)  # the wide end sets the envelope
    assert size[2] == pytest.approx(10.0, abs=0.01)

    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError, match="radius1"):
        solid.regular_prism(6, height=10, radius1=8, radius2=4)  # type: ignore[attr-defined]


def test_circumscribe_is_geometry_not_tessellation() -> None:
    """It decides whether the polygon encloses the circle, so it must not be quietly ignored."""
    from pybosl2.exceptions import UnsupportedByBackendError

    with use_backend("csg"):
        inscribed = solid.regular_prism(6, height=10, radius=8).bounds()[1]  # type: ignore[attr-defined]
        enclosing = solid.regular_prism(6, height=10, radius=8, circumscribe=True).bounds()[1]  # type: ignore[attr-defined]
    assert enclosing[1] > inscribed[1], "circumscribe changes the shape, so it is not tessellation"

    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError, match="circumscribe"):
        solid.regular_prism(6, height=10, radius=8, circumscribe=True)  # type: ignore[attr-defined]
