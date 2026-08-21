# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/drawing.py: the path generators (arc/catenary/helix) and the
renderers (stroke/dashed_stroke). The native primitives are mocked (see conftest), so the
render tests here only assert that geometry is produced; the geometry itself is checked against
the real app in pybosl2/tests/test_stl_render.py, and the generators are pinned to real-BOSL2
ground truth in tests/test_bosl2_reorient.py."""

import math

import numpy as np
import pytest

from pybosl2.caps import CapSpec, CapType, endcap_polys, endcap_trim, has_decorative_caps, normalize_one
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D
from pybosl2.regions import Region
from pybosl2.shapes2d import arc

# -- arc returns a Path2D -----------------------------------------------------------------


def test_arc_returns_open_path() -> None:
    a = arc(radius=16, start=0, angle=60)
    assert isinstance(a, Path2D)
    assert a.closed is False
    np.testing.assert_allclose(a[0], [16, 0], atol=1e-9)


def test_arc_wedge_is_closed_with_centre_first() -> None:
    w = arc(radius=10, angle=90, center=[2, 3], wedge=True)
    assert isinstance(w, Path2D)
    assert w.closed is True
    np.testing.assert_allclose(w[0], [2, 3], atol=1e-9)  # centre point prepended


def test_arc_angle_range_form() -> None:
    a = arc(count=5, radius=10, angle=[30, 90])
    np.testing.assert_allclose(
        a[0],
        [10 * math.cos(math.radians(30)), 10 * math.sin(math.radians(30))],
        atol=1e-9,
    )
    np.testing.assert_allclose(a[-1], [0, 10], atol=1e-9)


def test_arc_two_point_short_and_long() -> None:
    short = arc(count=7, center=[0, 0], points=[[10, 0], [0, 10]])
    long = arc(count=7, center=[0, 0], points=[[10, 0], [0, 10]], long=True)
    # both start/end at the same points, but the long one bulges the other way (negative x mid)
    np.testing.assert_allclose(short[0], [10, 0], atol=1e-9)
    np.testing.assert_allclose(long[0], [10, 0], atol=1e-9)
    assert short[len(short) // 2][0] > 0  # short arc stays in the +x/+y quadrant
    assert long[len(long) // 2][0] < 0  # long arc swings around through -x


def test_arc_corner_is_tangent_fillet() -> None:
    c = arc(corner=[[0, 10], [0, 0], [10, 0]], radius=3)
    assert isinstance(c, Path2D)
    # tangent points sit 3 up the y-leg and 3 along the x-leg
    np.testing.assert_allclose(
        sorted([c[0].tolist(), c[-1].tolist()]),
        sorted([[0.0, 3.0], [3.0, 0.0]]),
        atol=1e-9,
    )


def test_arc_collinear_points_raise() -> None:
    with pytest.raises(ValueError, match="collinear"):
        arc(count=5, points=[[0, 0], [1, 0], [2, 0]])


# -- catenary -----------------------------------------------------------------------------


def test_catenary_droop_hits_endpoints_and_midpoint() -> None:
    c = Path2D.catenary(width=80, droop=30, sides=21)
    assert isinstance(c, Path2D)
    assert c.closed is False
    np.testing.assert_allclose(c[0], [-40, 0], atol=1e-6)
    np.testing.assert_allclose(c[-1], [40, 0], atol=1e-6)
    np.testing.assert_allclose(c[10], [0, -30], atol=1e-6)  # middle droops by 30


def test_catenary_sign_flips_with_negative_droop() -> None:
    up = Path2D.catenary(width=50, droop=-15, sides=15)
    assert up[len(up) // 2][1] > 0  # negative droop hangs upward


def test_catenary_requires_exactly_one_of_droop_angle() -> None:
    with pytest.raises(ValueError, match=r"catenary\(\) needs exactly one of"):
        Path2D.catenary(width=10)
    with pytest.raises(ValueError, match=r"catenary\(\) needs exactly one of"):
        Path2D.catenary(width=10, droop=2, angle=30)


# -- helix --------------------------------------------------------------------------------


def test_helix_returns_path3d() -> None:
    height = Path3D.helix(turns=2, height=40, radius=10)
    assert isinstance(height, Path3D)  # the 3-D path object
    assert not isinstance(height, Path2D)
    assert len(height[0]) == 3
    np.testing.assert_allclose(height[0], [10, 0, 0], atol=1e-9)
    assert math.isclose(height[-1][2], 40, abs_tol=1e-9)  # ends at the full height


def test_helix_needs_exactly_two_params() -> None:
    with pytest.raises(ValueError, match="exactly two"):
        Path3D.helix(height=40, radius=10)  # only one of length/turns/angle


def test_helix_flat_spiral() -> None:
    height = Path3D.helix(height=0, radius1=50, radius2=25, length=0, turns=4)
    assert all(math.isclose(p[2], 0, abs_tol=1e-9) for p in height)  # flat: every z is 0


# -- stroke / dashed_stroke build geometry ------------------------------------------------


def test_stroke_2d_builds() -> None:
    """A stroked arc is a closed ribbon reaching half the width past the arc on each side."""
    path = arc(radius=30, angle=200)
    ribbon = path.stroke(width=3)
    assert isinstance(ribbon, Path2D)
    assert len(ribbon) > len(path)  # both sides of the ribbon, plus the caps
    box = ribbon.bounds()
    assert box.max_x - box.min_x == pytest.approx(2 * 30 + 3, abs=0.6)  # the arc, widened by the stroke


def test_stroke_3d_builds() -> None:
    """A 3-D stroke is one cylinder per segment with a sphere at every joint."""
    helix = Path3D.helix(turns=2, height=40, radius=20)
    program = repr(helix.stroke(width=3).shape)
    assert program.count("cylinder(") == len(helix) - 1
    assert program.count("sphere(") == len(helix)  # joints, plus a round cap at each end


def test_stroke_closed_path_defaults_from_flag() -> None:
    """A closed path strokes its closing segment too, without being told closed= again."""
    square = Path2D([[0, 0], [10, 0], [10, 10], [0, 10]], closed=True)
    closed_ribbon = square.stroke(width=1)
    open_ribbon = Path2D(list(square), closed=False).stroke(width=1)
    box = closed_ribbon.bounds()
    assert box.max_x - box.min_x == pytest.approx(11.0, abs=0.01)  # 10 plus half a width each side
    assert len(closed_ribbon) != len(open_ribbon)


def test_stroke_region_strokes_every_path() -> None:
    """Both the outline and the hole get their own ribbon, so the region keeps two paths."""
    reg = Region.with_holes([[0, 0], [40, 0], [40, 30], [0, 30]], [[10, 10], [30, 10], [30, 20], [10, 20]])  # type: ignore[arg-type]
    stroked = reg.stroke(width=2)
    assert len(stroked.paths) == len(reg.paths) == 2
    corners = stroked.bounds()
    assert [float(v) for v in corners[0]] == pytest.approx([-1.0, -1.0], abs=0.01)  # half a width out


def test_dashed_stroke_returns_paths() -> None:
    """A dashed circle comes back as many separate dashes, not one ribbon."""
    from pybosl2.regions import Region

    dashes = arc(radius=30, angle=360).dashed_stroke(dashpat=[6, 4], closed=True)
    assert isinstance(dashes, Region)
    # circumference 2*pi*30 = 188mm of 6-on/4-off, so roughly 19 dashes
    assert len(dashes.paths) == pytest.approx(19, abs=3)


def test_dashed_stroke_on_path_method() -> None:
    """100mm of 5-on/5-off is ten dashes, and they stay on the line they came from."""
    from pybosl2.regions import Region

    dashes = Path2D([[0, 0], [100, 0]], closed=False).dashed_stroke(dashpat=[5, 5])
    assert isinstance(dashes, Region)
    assert len(dashes.paths) == 10
    corners = dashes.bounds()
    # the pattern is fitted to the line, so the leftover is split evenly as a margin at each end
    assert float(corners[0][0]) == pytest.approx(100.0 - float(corners[1][0]), abs=0.01)
    assert float(corners[1][1]) == pytest.approx(1.0, abs=0.01)  # half the default stroke width


def test_dashed_stroke_region_flattens() -> None:
    """Every outline in the region contributes its dashes to one flat list of paths."""
    from pybosl2.regions import Region

    reg = Region([[[0, 0], [40, 0], [40, 40], [0, 40]]])
    dashes = reg.dashed_stroke(dashpat=[8, 4])
    assert isinstance(dashes, Region)
    assert len(dashes.paths) > 1  # the one outline became many dashes
    assert all(len(path) > 2 for path in dashes.paths)  # each dash is a ribbon, not a bare segment


def test_dashed_stroke_3d_yields_path3d() -> None:
    """The 3-D dashes are the same cylinders as a solid stroke, minus the joints, and fewer."""
    from pybosl2.shapes3d import Bosl2Solid

    helix = Path3D.helix(turns=2, height=40, radius=10)
    dashes = helix.dashed_stroke(dashpat=[6, 4])
    assert isinstance(dashes, Bosl2Solid)
    program = repr(dashes.shape)
    assert 0 < program.count("cylinder(") < len(helix) - 1
    assert program.count("sphere(") == 0  # no joints between separate dashes


# -- fancy endcaps generate directly (no fallback) ----------------------------------------

ALL_ENDCAPS = [
    CapType.ROUND,
    CapType.SQUARE,
    CapType.BUTT,
    CapType.NONE,
    CapType.DOT,
    CapType.BLOCK,
    CapType.DIAMOND,
    CapType.CHISEL,
    CapType.LINE,
    CapType.X,
    CapType.CROSS,
    CapType.ARROW,
    CapType.ARROW2,
    CapType.ARROW3,
    CapType.TAIL,
    CapType.TAIL2,
]


@pytest.mark.parametrize("style", ALL_ENDCAPS)
def test_every_endcap_style_builds_2d(style: object) -> None:
    """A closed path has no ends, so whatever the cap style, the ribbon is the same shape."""
    pts = [[0, 0], [20, 0], [20, 20], [0, 20]]
    ribbon = Path2D(pts, closed=True).stroke(width=3, endcap1=style, endcap2=style)  # type: ignore[arg-type]
    box = ribbon.bounds()
    assert (box.min_x, box.max_x) == pytest.approx((-1.5, 21.5))  # half a width past each side
    assert len(ribbon) > len(pts)


@pytest.mark.parametrize("style", ALL_ENDCAPS)
def test_every_endcap_style_builds_3d(style: object) -> None:
    """One straight segment is one cylinder, whatever is put on its ends."""
    tube = Path3D([[0, 0, 0], [40, 0, 0]]).stroke(width=3, endcap1=style, endcap2=style)  # type: ignore[arg-type]
    program = repr(tube.shape)
    assert program.count("cylinder(") == 1
    # whatever the cap draws, it draws the same at both ends -- an X is two crossed bars, so four
    decorations = program.count("sphere(") + program.count("rotate_extrude")
    assert decorations % 2 == 0, f"{style}: the two ends disagree"


def test_endcap_polys_shapes() -> None:
    # butt/false produce no polygon; x and cross are four triangles; arrow is one hexagon-ish poly
    assert endcap_polys(CapSpec(cap_type=CapType.BUTT), 1) == []
    assert endcap_polys(CapSpec(cap_type=CapType.NONE), 1) == []
    assert len(endcap_polys(CapSpec(cap_type=CapType.X), 1)) == 2
    assert len(endcap_polys(CapSpec(cap_type=CapType.CROSS), 1)) == 1
    assert len(endcap_polys(normalize_one(CapType.ARROW), 1)) == 1
    assert len(endcap_polys(normalize_one(CapType.ARROW), 1)[0]) == 5
    assert len(endcap_polys(normalize_one(CapType.ARROW3), 1)[0]) == 7


def test_endcap_polys_scale_with_linewidth() -> None:
    small = endcap_polys(CapSpec(cap_type=CapType.ARROW), 1)[0]
    big = endcap_polys(CapSpec(cap_type=CapType.ARROW), 2)[0]
    np.testing.assert_allclose(np.array(big), 2 * np.array(small), atol=1e-9)


def test_arrow_endcaps_trim_but_round_does_not() -> None:
    assert endcap_trim(normalize_one(CapType.ARROW), 3) > 0
    assert endcap_trim(normalize_one(CapType.ARROW3), 3) > 0
    assert endcap_trim(normalize_one(CapType.ARROW2), 3) > 0
    assert endcap_trim(normalize_one(CapType.ROUND), 3) == 0
    assert endcap_trim(normalize_one(CapType.SQUARE), 3) == 0
    assert endcap_trim(normalize_one(CapType.NONE), 3) == 0


def test_unknown_endcap_style_raises() -> None:
    with pytest.raises(ValueError, match="banana"):
        # CapType enums don't have string validation; passing a bad string would
        # fail at the CapType level, not inside stroke.
        CapType("banana")


def test_every_style_in_defaults_table() -> None:
    from pybosl2.caps import _DEFAULTS

    for style in CapType:
        assert style in _DEFAULTS


def test_endcap_defaults_are_structured() -> None:
    from pybosl2.caps import _DEFAULTS

    spec = _DEFAULTS[CapType.ARROW]
    assert isinstance(spec, CapSpec)
    assert (spec.length, spec.width, spec.extent) == (3.5, 0.4, 0.5)


def test_fancy_joint_style_builds() -> None:
    """A decorative joint still strokes the corner, reaching half a width past it."""
    ribbon = Path2D([[0, 0], [20, 0], [20, 20]]).stroke(width=3, joints=CapType.DIAMOND)
    box = ribbon.bounds()
    assert (box.min_x, box.min_y) == pytest.approx((-1.5, -1.5))
    assert (box.max_x, box.max_y) == pytest.approx((21.5, 21.5))


# -- decorative endcap geometry tests -------------------------------------------------------

from pybosl2._stroke3d import endcap_geometry_3d  # noqa: E402
from pybosl2.vnf import VNF  # noqa: E402


def test_endcap_geometry_3d_butt_returns_none() -> None:
    spec = normalize_one(CapType.BUTT)
    result = endcap_geometry_3d(spec, [0, 0, 0], [0, 0, 1], 2)
    assert result is None


def test_endcap_geometry_3d_round_returns_sphere() -> None:
    """A round cap is a sphere of the stroke's own radius -- half the width it was given."""
    from pybosl2.shapes3d import Bosl2Solid

    result = endcap_geometry_3d(normalize_one(CapType.ROUND), [1, 2, 3], [0, 0, 1], 4)
    assert isinstance(result, Bosl2Solid)
    assert "r = 2" in repr(result.shape)


def test_endcap_geometry_3d_dot_returns_larger_sphere() -> None:
    """A dot is the same sphere at twice the radius, so it stands proud of the stroke."""
    from pybosl2.shapes3d import Bosl2Solid

    dot = endcap_geometry_3d(normalize_one(CapType.DOT), [1, 2, 3], [0, 0, 1], 4)
    assert isinstance(dot, Bosl2Solid)
    assert "r = 4" in repr(dot.shape)
    assert "r = 2" in repr(endcap_geometry_3d(normalize_one(CapType.ROUND), [1, 2, 3], [0, 0, 1], 4).shape)


@pytest.mark.parametrize("style", [CapType.ARROW, CapType.DIAMOND], ids=["arrow", "diamond"])
def test_a_fancy_endcap_is_a_revolved_profile(style: CapType) -> None:
    """The decorative caps are revolved outlines, not primitives -- which is why the SDF backend
    cannot build them (it has no rotate_extrude) and falls back with a warning."""
    from pybosl2.shapes3d import Bosl2Solid

    result = endcap_geometry_3d(normalize_one(style), [1, 2, 3], [0, 0, 1], 4)
    assert isinstance(result, Bosl2Solid)
    program = repr(result.shape)
    assert "rotate_extrude" in program
    assert "sphere(" not in program


# -- endcap_polys for all cap types ---------------------------------------------------------


_SAFE_CAPS: list[CapType] = [ct for ct in CapType if ct not in (CapType.CIRCLE, CapType.CUSTOM)]


@pytest.mark.parametrize("style", _SAFE_CAPS)
def test_endcap_polys_each_cap_type_produces_polygons(style: CapType) -> None:
    """Every cap either draws something closed, or draws nothing at all -- never a stray point."""
    polygons = endcap_polys(normalize_one(style), 2)
    assert isinstance(polygons, list)
    if style in (CapType.NONE, CapType.BUTT, CapType.SPHERE):
        assert polygons == [], f"{style.value} adds no outline of its own"
        return
    assert polygons, f"{style.value} produced nothing to draw"
    for polygon in polygons:
        assert len(polygon) >= 2, f"{style.value}: a cap outline needs at least a segment"
        assert all(len(point) == 2 for point in polygon), f"{style.value}: 2-D points only"


# -- decorative caps on sweeps --------------------------------------------------------------


def test_has_decorative_caps_true_for_arrow() -> None:
    caps = [normalize_one(CapType.ARROW), normalize_one(CapType.ARROW)]
    assert has_decorative_caps(caps) is True


def test_has_decorative_caps_false_for_butt() -> None:
    caps = [normalize_one(CapType.BUTT), normalize_one(CapType.BUTT)]
    assert has_decorative_caps(caps) is False


def test_has_decorative_caps_false_for_round() -> None:
    caps = [normalize_one(CapType.ROUND), normalize_one(CapType.ROUND)]
    assert has_decorative_caps(caps) is False


def _tube_grid(rows: int, cols: int) -> list[list[list[float]]]:
    return [[[float(i), float(j), 0.0] for j in range(cols)] for i in range(rows)]


def test_vnf_with_decorative_caps_produces_bosl2solid() -> None:
    from pybosl2.caps import vnf_with_decorative_caps
    from pybosl2.shapes3d import Bosl2Solid

    grid = _tube_grid(3, 12)
    vnf = VNF.vertex_array(grid, col_wrap=True)
    caps = [normalize_one(CapType.ARROW), normalize_one(CapType.ARROW)]
    result = vnf_with_decorative_caps(
        vnf,
        caps,
        False,
        [[0.0, 5.5, 0.0], [2.0, 5.5, 0.0]],
        [[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        5.5,
    )
    assert isinstance(result, Bosl2Solid)
    # the tube's own mesh, plus a revolved arrow at each open end
    assert repr(result.shape).count("rotate_extrude") == 2


def test_vnf_with_decorative_caps_closed_skips_caps() -> None:
    from pybosl2.caps import vnf_with_decorative_caps
    from pybosl2.shapes3d import Bosl2Solid

    grid = _tube_grid(3, 12)
    vnf = VNF.vertex_array(grid, col_wrap=True)
    caps = [normalize_one(CapType.ARROW), normalize_one(CapType.ARROW)]
    result = vnf_with_decorative_caps(
        vnf,
        caps,
        True,
        [[0.0, 5.5, 0.0], [2.0, 5.5, 0.0]],
        [[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        5.5,
    )
    assert isinstance(result, Bosl2Solid)
    # a closed sweep has no ends to cap, so the arrows are dropped rather than buried inside
    assert "rotate_extrude" not in repr(result.shape)


# -- 2D decorative caps ---------------------------------------------------------------------


def test_2d_stroke_arrow_cap() -> None:
    result = Path2D([[0, 0], [30, 0]], closed=False).stroke(width=3, endcap1=CapType.ARROW, endcap2=CapType.ARROW)
    assert result is not None
    assert len(result) > 0


def test_2d_stroke_diamond_cap() -> None:
    result = Path2D([[0, 0], [30, 0]], closed=False).stroke(width=3, endcap1=CapType.DIAMOND, endcap2=CapType.DIAMOND)
    assert result is not None
    assert len(result) > 0


def test_2d_stroke_butt_cap() -> None:
    result = Path2D([[0, 0], [30, 0]], closed=False).stroke(width=3, endcap1=CapType.BUTT, endcap2=CapType.BUTT)
    assert result is not None
    assert len(result) > 0


# -- SDF endcap fallback --------------------------------------------------------------------


def test_sdf_stroke_arrow_falls_back_with_warning() -> None:
    from pybosl2._backend import use_backend
    from pybosl2._stroke3d import stroke_3d
    from pybosl2.caps import CapSpec

    with use_backend("sdf"):
        with pytest.warns(UserWarning, match="ARROW"):
            result = stroke_3d(
                [[0, 0, 0], [40, 0, 0]],
                width=3,
                closed=False,
                endcap1=CapSpec(cap_type=CapType.ARROW, length=3.5, width=0.4, extent=0.5),
                endcap2=CapSpec(cap_type=CapType.ARROW, length=3.5, width=0.4, extent=0.5),
            )
        # the arrow becomes a plain round cap: a decorative cap needs rotate_extrude, which the
        # SDF backend has no form for, so that one piece is built on CSG (announced, not silent)
        assert result is not None
        assert "rotate_extrude" not in repr(result.shape)
        assert "sphere(" in repr(result.shape)
