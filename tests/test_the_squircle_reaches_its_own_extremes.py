# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The squircle reaches its own extremes instead of its centre.

PLAN S-4a (degrees are the angular unit -- and the conversion is not free), SPEC B2-1 (the same
shapes BOSL2 builds), S-55 (export refuses to write nonsense), DOC-3, PLAN E-P4.

T134 found a chamfered cone published as not watertight, fixed the measurement that said so, and
recorded what was left over: `shapes2d-squircle` still had **one real bad edge** after the
degenerate slivers were dropped. That edge turns out to be the only visible symptom of a wrong
shape, not a mesh artifact.

BOSL2 writes the Fong-Garcia radius as

    s2a = abs(squareness * sin(2*angle));
    s2a > 0 ? r*sqrt(2)/s2a*sqrt(1 - sqrt(1 - s2a*s2a)) : r

and the port copied it line for line. In OpenSCAD `sin()` takes degrees and returns **exactly** 0
at every multiple of 180, so on the axes the guard fires and the quotient is never evaluated. In
Python `math.sin(math.radians(2 * angle))` is 1.2e-16 at 90 degrees — not 0 — so the guard misses,
and the quotient is evaluated at a point where it cannot survive: `1 - s2a*s2a` rounds to exactly
1.0, its square root is 1.0, and the subtraction leaves exactly 0.0. The radius came back **zero
on all four axes**, so the path ran through the centre of the squircle four times instead of
reaching (±r, 0) and (0, ±r).

Measured on `squircle(30, squareness=0.6).linear_extrude(height=2)`, the spec-sheet part:

| | before | after |
|---|---|---|
| bounding box | 29.866 x 29.866 x 2 | **30 x 30 x 2** |
| volume | 1,128.72 | **1,701.51** |
| mesh edges with the wrong face count | 1 (eight incident faces) | **0** |
| watertight | False | **True** |

A third of the solid was missing, and every test the squircle had passed. They asserted bounds,
which a wedge taken out *near* the axis barely moves because the neighbouring sample points still
reach almost the full radius; or they used `squareness=0`, the one value where `s2a` is exactly
zero because it is a product with zero, so the guard fires correctly and the function is right.
Nothing measured the area. A bounding box cannot see a hole in the middle.

The fix multiplies through by `1 + sqrt(1-x*x)`: `1 - sqrt(1-x*x) == x*x/(1 + sqrt(1-x*x))`, so the
whole expression is `sqrt(2)/sqrt(1 + sqrt(1-x*x))` — the same function, with no subtraction of
near-equal numbers, no division by `s2a`, and therefore no special case on the axes at all. The
identity is checked below in 60-digit arithmetic rather than asserted.
"""

import ast
import math
import pathlib
from decimal import Decimal, getcontext

import pytest

import pybosl2.shapes2d.curves as curves
from pybosl2 import shapes2d as s2
from pybosl2.shapes2d.curves import _linearize_squareness, _squircle_fg_path, squircle_radius_fg

#: Squareness values swept by every shape-level probe. 0 is the value the old tests used and the
#: one value the defect could not reach; the rest all triggered it.
SQUARENESS = (0.0, 0.05, 0.1, 0.25, 0.5, 0.6, 0.75, 0.9, 0.99, 1.0)

#: Facet counts. `None` is the ambient default (32 for a 30-unit squircle). `astep` is
#: `90/round(fn/4)`, which always divides 90, so the axis angles are always sampled exactly --
#: there is no resolution at which the defect was absent.
FACETS = (None, 12, 16, 24, 32, 36, 64, 128)

#: The axis angles, where `sin(2*angle)` is mathematically zero and numerically is not.
AXES = (0.0, 90.0, 180.0, 270.0, 360.0, 450.0, -90.0, -180.0, 720.0)


def _literal_bosl2_radius(squareness: float, radius: float, angle: float) -> float:
    """The BOSL2 expression ported literally -- the form that shipped before T141.

    Kept here as the control. Every probe in this file is run against it too, so each one is known
    to be able to fail; a probe that passes against both forms is measuring nothing.
    """
    s2a = abs(squareness * math.sin(math.radians(2 * angle)))
    if s2a > 0:
        return radius * math.sqrt(2) / s2a * math.sqrt(1 - math.sqrt(1 - s2a * s2a))
    return radius


def _polygon_area(pts: list[list[float]]) -> float:
    """The shoelace area of a closed path."""
    total = 0.0
    for i, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(i + 1) % len(pts)]
        total += x0 * y1 - x1 * y0
    return abs(total) / 2.0


def _curve_area(squareness: float, radius: float, steps: int = 20000) -> float:
    """The area the squircle *curve* encloses, by midpoint polar integration of its radius.

    Independent of how `_squircle_fg_path` chooses its sample angles, so a polygon area can be
    compared against the shape rather than against another sampling of it.
    """
    sq = _linearize_squareness(squareness)
    step = 360.0 / steps
    total = 0.0
    for i in range(steps):
        r = squircle_radius_fg(sq, radius, (i + 0.5) * step)
        total += r * r
    return 0.5 * total * math.radians(step)


# -- the radius function ------------------------------------------------------------------------


@pytest.mark.parametrize("squareness", SQUARENESS)
@pytest.mark.parametrize("angle", AXES)
def test_the_radius_on_the_axes_is_the_half_size(squareness: float, angle: float) -> None:
    """On the axes the squircle touches its bounding box, whatever its squareness."""
    sq = _linearize_squareness(squareness)
    assert squircle_radius_fg(sq, 15.0, angle) == pytest.approx(15.0, abs=1e-12)


@pytest.mark.parametrize("angle", AXES)
def test_the_literal_port_collapses_on_the_axes(angle: float) -> None:
    """The control: the literal BOSL2 form returns zero wherever `sin(2*angle)` is not exactly 0."""
    sq = _linearize_squareness(0.6)
    sine = math.sin(math.radians(2 * angle))
    got = _literal_bosl2_radius(sq, 15.0, angle)
    if sine == 0.0:
        assert got == 15.0, "with an exactly-zero sine the guard fires and the form is correct"
    else:
        assert got == 0.0, f"sin(2*{angle}) is {sine:+.3e}, so the guard misses and the form cancels"


@pytest.mark.parametrize("squareness", SQUARENESS)
def test_the_radius_never_leaves_the_annulus(squareness: float) -> None:
    """A squircle lies between its inscribed circle and the corner of its square: r .. r*sqrt(2)."""
    sq = _linearize_squareness(squareness)
    radii = [squircle_radius_fg(sq, 15.0, a / 4.0) for a in range(4 * 360)]
    assert min(radii) == pytest.approx(15.0, abs=1e-12)
    assert max(radii) <= 15.0 * math.sqrt(2) + 1e-12
    assert min(radii) >= 15.0 - 1e-12, "the old form's zero on the axes lands here"


def test_the_corners_are_where_the_two_limits_put_them() -> None:
    """At 45 degrees a circle is still r and a square is r*sqrt(2); nothing in between escapes.

    The square's corner is held to 2e-8 rather than machine precision, and that is the
    parametrisation's floor, not slack -- see
    `test_the_corner_is_as_exact_as_the_parametrisation_allows`.
    """
    assert squircle_radius_fg(_linearize_squareness(0.0), 10.0, 45.0) == pytest.approx(10.0)
    assert squircle_radius_fg(_linearize_squareness(1.0), 10.0, 45.0) == pytest.approx(10.0 * math.sqrt(2), rel=2e-8)


def test_the_corner_is_as_exact_as_the_parametrisation_allows() -> None:
    """Why the corner is held to 2e-8: `sqrt(1-x*x)` has an infinite derivative at x = 1.

    `_linearize_squareness(1.0)` is 0.9999999999999998, half an ulp below 1 -- and no spelling of
    that formula is exact there, because `2/(d*d)` with `d` the float nearest `sqrt(2)` gives
    `2/2.0000000000000004`. With `eps = 1 - s2a` the radius is `r*sqrt(2)/sqrt(1 + sqrt(2*eps))`,
    so the shortfall is `sqrt(2*eps)/2` -- a half-ulp input error, 2.2e-16, comes out as 1.05e-8.
    That is a property of the Fong-Garcia parametrisation at its square endpoint and bounds what
    any implementation of it can promise, so it is measured here rather than hidden inside a loose
    tolerance somewhere else.
    """
    s2a = _linearize_squareness(1.0)
    eps = 1.0 - s2a
    assert eps == pytest.approx(2.2e-16, rel=0.5), f"squareness 1 linearises to {s2a!r}"
    corner = squircle_radius_fg(s2a, 15.0, 45.0)
    shortfall = (15.0 * math.sqrt(2) - corner) / (15.0 * math.sqrt(2))
    predicted = math.sqrt(2.0 * eps) / 2.0
    assert shortfall == pytest.approx(predicted, rel=0.05), (
        f"the corner is {shortfall:.3e} short; sqrt(2*eps)/2 predicts {predicted:.3e}"
    )
    assert shortfall < 2e-8, "and that floor is 3e-7 mm on a 30mm squircle"


def test_the_shipped_form_is_the_bosl2_form() -> None:
    """The two expressions are the same function, checked in 60-digit arithmetic, not asserted."""
    getcontext().prec = 60
    worst = Decimal(0)
    for i in range(1, 2001):
        x = Decimal(i) / Decimal(2000)
        root = (Decimal(1) - x * x).sqrt()
        literal = Decimal(2).sqrt() / x * (Decimal(1) - root).sqrt()
        shipped = Decimal(2).sqrt() / (Decimal(1) + root).sqrt()
        worst = max(worst, abs(literal - shipped) / shipped)
    assert worst < Decimal("1e-50"), f"the two forms differ by {worst} -- not an identity"


@pytest.mark.parametrize("squareness", [0.05, 0.5, 0.9])
def test_the_shipped_form_beats_the_literal_one_where_both_run(squareness: float) -> None:
    """Away from the axes both forms evaluate; the shipped one is the accurate one.

    The literal form's error grows without bound as the angle approaches an axis -- at 1e-6
    degrees it is already 4.8e-3 relative, five decimal digits gone -- while the shipped form
    stays at machine precision everywhere.
    """
    getcontext().prec = 60
    sq = _linearize_squareness(squareness)
    for angle in (1e-6, 1e-4, 0.001, 0.01, 1.0, 10.0, 45.0):
        s2a = Decimal(abs(sq * math.sin(math.radians(2 * angle))))
        exact = Decimal(15) * Decimal(2).sqrt() / (Decimal(1) + (Decimal(1) - s2a * s2a).sqrt()).sqrt()
        shipped = abs(Decimal(squircle_radius_fg(sq, 15.0, angle)) - exact) / exact
        literal = abs(Decimal(_literal_bosl2_radius(sq, 15.0, angle)) - exact) / exact
        assert shipped < Decimal("1e-15"), f"angle={angle}: shipped form off by {shipped}"
        assert literal >= shipped, f"angle={angle}: the literal form is not the worse one"


# -- the path -----------------------------------------------------------------------------------


@pytest.mark.parametrize("squareness", SQUARENESS)
@pytest.mark.parametrize("fn", FACETS)
def test_the_path_never_reaches_the_centre(squareness: float, fn: int | None) -> None:
    """No sample point sits at the origin -- the whole symptom, at every resolution."""
    pts = _squircle_fg_path([30.0, 30.0], squareness, fn, None, None)
    closest = min(math.hypot(x, y) for x, y in pts)
    assert closest == pytest.approx(15.0, rel=0.26), f"nearest point to the centre is {closest:.6f}"


@pytest.mark.parametrize("squareness", SQUARENESS)
@pytest.mark.parametrize("fn", FACETS)
def test_the_path_has_no_repeated_point(squareness: float, fn: int | None) -> None:
    """A path that visits one place twice is not a simple curve, whatever that place is."""
    pts = _squircle_fg_path([30.0, 30.0], squareness, fn, None, None)
    unique = {(round(x, 9), round(y, 9)) for x, y in pts}
    assert len(unique) == len(pts), f"{len(pts) - len(unique)} of {len(pts)} points are repeats"


@pytest.mark.parametrize("squareness", SQUARENESS)
@pytest.mark.parametrize("fn", FACETS)
@pytest.mark.parametrize("size", [[30.0, 30.0], [40.0, 20.0], [12.0, 25.0]])
def test_the_path_fills_its_nominal_size(squareness: float, fn: int | None, size: list[float]) -> None:
    """`size` is the bounding box, exactly, because the axis points are on it."""
    pts = _squircle_fg_path(size, squareness, fn, None, None)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    assert max(xs) - min(xs) == pytest.approx(size[0], abs=1e-9)
    assert max(ys) - min(ys) == pytest.approx(size[1], abs=1e-9)


@pytest.mark.parametrize("squareness", SQUARENESS)
def test_the_path_winds_once_around_the_centre(squareness: float) -> None:
    """Polar angle is monotone along the path, so the curve is simple and star-shaped.

    `theta = a + sq*sin(4a)*30/pi` has derivative `1 + sq*cos(4a)*2/3` with respect to `a`, which
    is positive for every `sq <= 1` -- so the perturbation reorders nothing. A point at the origin
    has no polar angle at all, which is how the old path broke this.
    """
    pts = _squircle_fg_path([30.0, 30.0], squareness, 64, None, None)
    angles = [math.degrees(math.atan2(y, x)) % 360.0 for x, y in pts]
    steps = [(angles[i] - angles[i + 1]) % 360.0 for i in range(len(angles) - 1)]
    assert min(steps) > 0.1, f"smallest angular step is {min(steps):.6f} degrees"
    assert sum(steps) < 360.0, "the path must not wind round more than once"


# -- the area the path encloses -----------------------------------------------------------------


@pytest.mark.parametrize("squareness", SQUARENESS)
def test_the_enclosed_area_converges_to_the_curve(squareness: float) -> None:
    """The polygon is inscribed in the squircle, so its area approaches the curve's from below."""
    reference = _curve_area(squareness, 15.0)
    coarse = _polygon_area(_squircle_fg_path([30.0, 30.0], squareness, 32, None, None))
    fine = _polygon_area(_squircle_fg_path([30.0, 30.0], squareness, 128, None, None))
    # The slack is the midpoint rule's, not the shape's: at squareness 1 the radius function has
    # a kink at every 45 degrees, so the integral converges at O(1/n) there and reads 1.3e-5 low.
    slack = reference * 1e-6
    assert coarse <= reference + slack, f"{coarse:.4f} exceeds the curve's {reference:.4f}"
    assert fine <= reference + slack
    assert fine >= coarse, "more facets must not enclose less"
    assert (reference - fine) / reference < 0.001, f"128 facets still {reference - fine:.4f} short"


@pytest.mark.parametrize("squareness", SQUARENESS)
@pytest.mark.parametrize("fn", FACETS)
def test_the_enclosed_area_is_at_least_the_inscribed_circle(squareness: float, fn: int | None) -> None:
    """A squircle contains its inscribed circle; the old shape was smaller than one.

    Compared at matched resolution, since both polygons are inscribed: the circle at the same
    facet count is the floor. At `fn=128` the old shape cleared this bar and only the coarser
    counts caught it, which is the same blindness the old tests had -- hence the sweep.
    """
    area = _polygon_area(_squircle_fg_path([30.0, 30.0], squareness, fn, None, None))
    circle = _polygon_area(_squircle_fg_path([30.0, 30.0], 0.0, fn, None, None))
    assert area >= circle - 1e-9, f"area {area:.4f} is below the inscribed circle's {circle:.4f}"
    assert area <= 900.0 + 1e-9, f"area {area:.4f} exceeds the 30x30 square it sits in"


def test_the_area_grows_with_squareness() -> None:
    """Squareness interpolates from the circle to the square, so the area is monotone in it."""
    areas = [_polygon_area(_squircle_fg_path([30.0, 30.0], sq, 128, None, None)) for sq in SQUARENESS]
    assert areas == sorted(areas), f"not monotone: {[round(a, 2) for a in areas]}"
    assert areas[0] == pytest.approx(math.pi * 225.0, rel=5e-4), "squareness 0 is a circle"
    assert areas[-1] == pytest.approx(900.0, abs=1e-6), "squareness 1 is a 30x30 square"


def test_a_full_squareness_is_a_square() -> None:
    """At squareness 1 every point lies on the square's perimeter: max(|x|, |y|) is the half-size.

    To 2e-8, the parametrisation's floor at that endpoint.
    """
    pts = _squircle_fg_path([30.0, 30.0], 1.0, 128, None, None)
    extents = [max(abs(x), abs(y)) for x, y in pts]
    assert min(extents) == pytest.approx(15.0, rel=2e-8)
    assert max(extents) == pytest.approx(15.0, rel=2e-8)


def test_a_zero_squareness_is_exactly_a_circle() -> None:
    """At squareness 0 every point is at the half-size from the centre."""
    radii = [math.hypot(x, y) for x, y in _squircle_fg_path([30.0, 30.0], 0.0, 128, None, None)]
    assert min(radii) == pytest.approx(15.0, abs=1e-9)
    assert max(radii) == pytest.approx(15.0, abs=1e-9)


# -- the mesh the shape builds ------------------------------------------------------------------


@pytest.mark.parametrize("squareness", SQUARENESS)
def test_the_extruded_squircle_is_watertight(squareness: float) -> None:
    """The symptom T134 recorded: the extruded mesh closes, and its volume is the path's."""
    mesh = s2.squircle(30, squareness=squareness).linear_extrude(height=2).vnf()
    expected = 2.0 * _polygon_area(_squircle_fg_path([30.0, 30.0], squareness, None, None, None))
    assert mesh.is_watertight(), "an extruded 2-D shape bounds a solid"
    assert mesh.volume() == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize("squareness", SQUARENESS)
def test_an_extruded_squircle_can_be_exported(squareness: float, tmp_path: pathlib.Path) -> None:
    """SPEC S-55: `export()` validates watertightness and refuses. It was refusing.

    This is the sharpest statement of what the defect cost. `export()` is the one place the
    library checks a mesh before handing it over, and it was doing its job -- so a caller could
    not write a squircle to a file at all, at any squareness above zero:

        export(): the mesh is not watertight -- 24 edge(s) are not shared by exactly two faces,
        starting at (5, 6). Pass check=False to write it anyway ...

    The shape was unusable for the thing a shape is for, and the error named the mesh rather than
    the squircle, so nothing pointed back here.
    """
    out = tmp_path / "squircle.stl"
    s2.squircle(30, squareness=squareness).linear_extrude(height=2).export(str(out))
    assert out.stat().st_size > 1000, "an STL of 124 triangles is about 6kB"


def test_the_spec_sheet_part_is_the_size_it_claims() -> None:
    """`squircle(30, squareness=0.6).linear_extrude(height=2)` -- the part on the spec page."""
    solid = s2.squircle(30, squareness=0.6).linear_extrude(height=2)
    assert [float(v) for v in solid.bounds().size] == pytest.approx([30.0, 30.0, 2.0], abs=1e-6)
    assert solid.vnf().volume() == pytest.approx(1701.5075, abs=1e-3)


# -- the controls -------------------------------------------------------------------------------


def test_the_probes_can_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every shape-level probe above must fail against the literal form. Restore it and see.

    `_squircle_fg_path` looks `squircle_radius_fg` up as a module global, so replacing the module
    attribute replaces what the path builder calls.
    """
    monkeypatch.setattr(curves, "squircle_radius_fg", _literal_bosl2_radius)
    pts = _squircle_fg_path([30.0, 30.0], 0.6, None, None, None)
    assert min(math.hypot(x, y) for x, y in pts) == 0.0, "the centre visit should be back"
    assert len({(round(x, 9), round(y, 9)) for x, y in pts}) == len(pts) - 3, "and the repeats"
    xs = [p[0] for p in pts]
    assert max(xs) - min(xs) == pytest.approx(29.8655, abs=1e-3), "and the short bounding box"
    assert _polygon_area(pts) == pytest.approx(564.361, abs=1e-2), "and a third of the area gone"
    mesh = s2.squircle(30, squareness=0.6).linear_extrude(height=2).vnf()
    assert not mesh.is_watertight(), "and the open mesh T134 recorded"
    assert mesh.volume() == pytest.approx(1128.7227, abs=1e-3)


def test_the_axis_angles_are_always_sampled(monkeypatch: pytest.MonkeyPatch) -> None:
    """There is no resolution that dodged the defect, because `astep` always divides 90.

    Recorded as a probe rather than a comment: if `_squircle_fg_path` ever stops landing on the
    axes exactly, the bug above would have been resolution-dependent and this file's sweep over
    `FACETS` would be measuring luck.
    """
    seen: list[float] = []
    monkeypatch.setattr(
        curves,
        "squircle_radius_fg",
        lambda sq, r, angle: seen.append(angle) or squircle_radius_fg(sq, r, angle),
    )
    for fn in FACETS:
        seen.clear()
        _squircle_fg_path([30.0, 30.0], 1.0, fn, None, None)
        on_axis = [a for a in seen if min((a % 90.0), 90.0 - (a % 90.0)) < 1e-9]
        assert len(on_axis) == 4, f"fn={fn}: {len(on_axis)} axis samples, not 4"


# -- the defect class, scanned for ------------------------------------------------------------


#: The package, located from this file rather than from the working directory.
PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "pybosl2"

#: `sin`, `cos`, `tan`. The hazard is specific to degree trig evaluated through `math.radians`,
#: and those are the three whose OpenSCAD counterparts return exact zeros and ones on the axes.
_TRIG = frozenset({"sin", "cos", "tan"})


def _has_trig(node: ast.AST) -> bool:
    """True when *node* contains a call to one of `_TRIG`, by whatever module alias."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in _TRIG:
                return True
    return False


def _against_zero(node: ast.Compare) -> bool:
    """True when *node* compares its left side against a literal zero."""
    return any(isinstance(c, ast.Constant) and c.value in (0, 0.0) for c in node.comparators)


def _guarded_divisors(tree: ast.AST) -> list[str]:
    """Locals assigned from a trig call that are *both* compared against zero and divided by.

    That conjunction is the shape of the defect, and it is what makes it quiet rather than loud. A
    division by a near-zero sine on its own is visible -- it returns 1e16, or raises -- so it is
    not this class. A zero guard around a division is a port of `x > 0 ? f(x) : limit`, written
    because the author knew `f` is undefined at zero, and in OpenSCAD the guard is reliable
    because its `sin()` is exactly zero on the axes. In Python it is not, so the guard misses by
    1.2e-16 and `f` is evaluated exactly where the author knew it must not be.
    """
    found: list[str] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        tainted = {
            target.id
            for node in ast.walk(fn)
            if isinstance(node, ast.Assign) and _has_trig(node.value)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        if not tainted:
            continue
        guarded, divided = set(), set()
        for node in ast.walk(fn):
            is_cmp = isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
            if is_cmp and node.left.id in tainted and _against_zero(node):
                guarded.add(node.left.id)
            is_div = isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
            if is_div and isinstance(node.right, ast.Name) and node.right.id in tainted:
                divided.add(node.right.id)
        found += [f"{fn.name}(): {name}" for name in sorted(guarded & divided)]
    return found


def test_no_other_call_guards_a_trig_divisor_against_zero() -> None:
    """A ratchet on the defect class, not just the one instance of it.

    Run against the commit before this one, this finds exactly `squircle_radius_fg(): s2a` and
    nothing else -- so the squircle was the only place in the package where an OpenSCAD
    `sin(x) > 0 ? ... : limit` guard had been ported literally. The next one would land here.
    """
    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        for hit in _guarded_divisors(ast.parse(path.read_text())):
            offenders.append(f"{path.relative_to(PACKAGE.parent)}:{hit}")
    assert offenders == [], (
        "a value built from sin/cos/tan is both guarded against zero and used as a divisor:\n  "
        + "\n  ".join(offenders)
        + "\nIn Python that guard misses by ~1e-16 on the axes. Rewrite the expression so the "
        "division is not there (T141)."
    )


def test_the_ratchet_can_fail() -> None:
    """The control for the scan above: the shape it looks for, in a string it is handed."""
    literal_port = (
        "import math\n"
        "def f(squareness, radius, angle):\n"
        "    s2a = abs(squareness * math.sin(math.radians(2 * angle)))\n"
        "    return radius / s2a * math.sqrt(1 - math.sqrt(1 - s2a * s2a)) if s2a > 0 else radius\n"
    )
    assert _guarded_divisors(ast.parse(literal_port)) == ["f(): s2a"]
    shipped = (
        "import math\n"
        "def f(squareness, radius, angle):\n"
        "    s2a = abs(squareness * math.sin(math.radians(2 * angle)))\n"
        "    return radius * math.sqrt(2) / math.sqrt(1.0 + math.sqrt(1.0 - s2a * s2a))\n"
    )
    assert _guarded_divisors(ast.parse(shipped)) == []
