# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A transcription of BOSL2's ``_cyl_path()`` (shapes3d.scad), used as an external oracle.

**Every rim instrument before this one compared the two backends to each other.** T42's profile
probe asked whether the field is zero on the polygon CSG revolves; T126 and T127 sharpened it and
T128 asked it of the whole family. They were all sound, and none of them could see a rim both
backends got wrong -- which is what had happened: T42 read the fillet centre off `cyl_profile`,
recorded it as BOSL2's rule, and the SDF backend was then matched to it. Two backends agreeing is
not evidence about BOSL2 (SPEC B2-1).

So this file is not a reimplementation to compare against; it is a *transcription*, kept
deliberately close to the ``.scad`` it comes from -- same names, same order, same formulas -- so
that reading the two side by side is the check on the check. Only the vertex geometry is
reproduced: an arc comes back as its two endpoints and its centre, which determine it exactly, so
nothing here depends on how either library chooses to facet one.

Source: https://github.com/BelfrySCAD/BOSL2 ``shapes3d.scad``, ``_cyl_path()``.
"""

from __future__ import annotations

import math

#: ``(radial, axial)`` in the profile half-plane, as BOSL2's paths are written.
Point = tuple[float, float]


def law_of_sines(a: float, big_a: float, big_b: float) -> float:
    """BOSL2 ``law_of_sines(a=, A=, B=)`` -- the side facing *B*, given the side facing *A*.

    Args:
        a: The known side.
        big_a: The angle facing *a*, in degrees.
        big_b: The angle facing the side to return, in degrees.

    Returns:
        The side facing *big_b*.

    """
    return a * math.sin(math.radians(big_b)) / math.sin(math.radians(big_a))


def corner_arc(r: float, a: Point, b: Point, c: Point) -> tuple[Point, Point, Point]:
    """BOSL2 ``arc(r=, corner=[A, B, C])`` -- the arc of radius *r* tangent to ``BA`` and ``BC``.

    Args:
        r: The arc radius.
        a: The first corner point; ``BA`` is the leg the arc starts tangent to.
        b: The corner itself.
        c: The last corner point; ``BC`` is the leg the arc ends tangent to.

    Returns:
        ``(start, end, centre)``.

    """
    ux, uy = (a[0] - b[0], a[1] - b[1])
    vx, vy = (c[0] - b[0], c[1] - b[1])
    ul, vl = math.hypot(ux, uy), math.hypot(vx, vy)
    ux, uy, vx, vy = ux / ul, uy / ul, vx / vl, vy / vl
    half = math.acos(max(-1.0, min(1.0, ux * vx + uy * vy))) / 2.0
    tangent = r / math.tan(half)
    bx, by = ux + vx, uy + vy
    bl = math.hypot(bx, by)
    reach = r / math.sin(half)
    return (
        (b[0] + ux * tangent, b[1] + uy * tangent),
        (b[0] + vx * tangent, b[1] + vy * tangent),
        (b[0] + bx / bl * reach, b[1] + by / bl * reach),
    )


def _first(*values: float | bool | None) -> float | bool:
    """BOSL2 ``first_defined()``.

    Args:
        values: The candidates, in priority order.

    Returns:
        The first that is not None.

    """
    for value in values:
        if value is not None:
            return value
    raise AssertionError("first_defined() with nothing defined")


def _rim(
    radius: float,
    other: float,
    length: float,
    chamfer: float,
    rounding: float,
    chamfang: float | None,
    from_end: bool,
    scale: float,
    unscale: float,
    vang: float,
    *,
    top: bool,
) -> dict[str, object]:
    """One rim, transcribed from the ``bottom =``/``top =`` branches of ``_cyl_path``.

    Args:
        radius: This end's radius.
        other: The far end's radius.
        length: The cylinder length.
        chamfer: The chamfer size, 0 for none.
        rounding: The rounding radius, 0 for none.
        chamfang: The chamfer angle in degrees, or None for BOSL2's default.
        from_end: BOSL2's ``from_end``.
        scale: ``cos(180/n)`` when a facet count is given, else 1.
        unscale: ``scale`` when ``noscale``, else 1.
        vang: The wall angle BOSL2 computes.
        top: Describe the top rim rather than the bottom.

    Returns:
        ``{"points": [...]}`` and, for a rounding, ``"centre"`` and ``"r"``.

    """
    lean = -vang if top else vang
    end = length / 2 if top else -length / 2
    sign = math.copysign(1.0, chamfer) if chamfer else 0.0
    ang = float(_first(chamfang, 45 + sign * lean / 2))
    opposite = 180 - ang - (90 - sign * lean)
    if chamfer:
        radial = unscale * (law_of_sines(chamfer, ang, opposite) if from_end else chamfer)
        leg = abs(chamfer) if from_end else abs(law_of_sines(chamfer, opposite, ang))
        along = math.radians((270.0 if top else 90.0) + vang)
        on_wall = (radius + math.cos(along) * leg / scale, end + math.sin(along) * leg)
        inner = (radius - radial / scale, end)
        return {"points": [on_wall, inner] if top else [inner, on_wall]}
    if rounding:
        reach = rounding / math.tan(math.radians(45 - lean / 2))
        corner = (radius * scale, end)
        inward = (radius * scale - 2 * reach, end)
        far = (other * scale, -end)
        legs = (far, corner, inward) if top else (inward, corner, far)
        start, finish, centre = corner_arc(abs(rounding * unscale), *legs)
        return {
            "points": [(start[0] / scale, start[1]), (finish[0] / scale, finish[1])],
            "centre": (centre[0] / scale, centre[1]),
            "r": abs(rounding * unscale),
        }
    return {"points": [(radius, end)]}


def cyl_path(
    r1: float,
    r2: float,
    l: float,  # noqa: E741 -- BOSL2's own name for the length; this file keeps its spellings
    *,
    chamfer1: float = 0.0,
    chamfer2: float = 0.0,
    chamfang1: float | None = None,
    chamfang2: float | None = None,
    rounding1: float = 0.0,
    rounding2: float = 0.0,
    from_end1: bool = False,
    from_end2: bool = False,
    n: int | None = None,
    noscale: bool = False,
) -> dict[str, dict[str, object]]:
    """Return the bottom and top rim geometry BOSL2's ``_cyl_path()`` builds.

    Args:
        r1: Radius at the bottom.
        r2: Radius at the top.
        l: The length.
        chamfer1: Bottom chamfer size.
        chamfer2: Top chamfer size.
        chamfang1: Bottom chamfer angle in degrees, or None for BOSL2's default.
        chamfang2: Top chamfer angle in degrees, or None for BOSL2's default.
        rounding1: Bottom rounding radius.
        rounding2: Top rounding radius.
        from_end1: BOSL2's ``from_end1``.
        from_end2: BOSL2's ``from_end2``.
        n: The facet count the profile will be revolved with, if the rim is stated against faces.
        noscale: BOSL2's ``noscale``; scales the treatment amounts as well as the frame.

    Returns:
        ``{"bottom": ..., "top": ...}``, each as :func:`_rim` returns.

    """
    scale = math.cos(math.pi / n) if n is not None else 1.0
    unscale = scale if noscale else 1.0
    vang = math.degrees(math.atan2(scale * (r1 - r2), l))
    return {
        "bottom": _rim(r1, r2, l, chamfer1, rounding1, chamfang1, from_end1, scale, unscale, vang, top=False),
        "top": _rim(r2, r1, l, chamfer2, rounding2, chamfang2, from_end2, scale, unscale, vang, top=True),
    }
