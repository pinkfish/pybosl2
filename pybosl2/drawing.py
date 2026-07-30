# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/drawing.py
#    Pure-Python port of BOSL2's drawing.scad: the path *generators*
#    (:func:`arc`, :func:`catenary`, :func:`helix`, :func:`turtle`) and the path
#    *renderers* (:func:`stroke`, :func:`dashed_stroke`). The generators return a
#    :class:`~pybosl2.paths.Path2D` (2-D) or a plain list of 3-D points (``helix``); the
#    renderers turn a path into native geometry (``stroke``) or a list of dash
#    sub-paths (``dashed_stroke``).
#
#    ``arc`` itself lives in pybosl2/shapes2d.py (it shares that module's $fn/$fa/$fs
#    and 3-point-circle helpers) and is re-exported here so the whole drawing API is
#    reachable as ``pybosl2.drawing``. :func:`stroke`/:func:`dashed_stroke` are also
#    attached as methods on :class:`~pybosl2.paths.Path2D` and
#    :class:`~pybosl2.regions.Region`, so a built path can be drawn directly
#    (``path.stroke(width=2)``).
#
# FileSummary: Path2D generators (arc/catenary/helix/turtle) and renderers (stroke/dashed_stroke).
# FileGroup: BOSL2

from __future__ import annotations

import math
import operator
from functools import reduce
from typing import TYPE_CHECKING, Any

import numpy as np

from pybosl2.caps import (
    CapSpec,
    CapType,
    _endcap_polys,
    _endcap_trim,
    _normalize_one,
    _oriented_to,
    _place,
    _trim_ends,
)
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D

# The stroke body is built from the backend-neutral facade, NOT pybosl2.shapes3d directly, so a
# 3-D stroke realizes on whichever backend is active: Bosl2Solids under the default csg backend,
# PyShapes under use_backend("sdf").
from pybosl2.solid import cyl as _cyl  # type: ignore[attr-defined]
from pybosl2.solid import sphere as _sphere  # type: ignore[attr-defined]

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "stroke",
    "dashed_stroke",
]


# ---------------------------------------------------------------------------
# Section: 2-D helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Section: Path2D generators
# ---------------------------------------------------------------------------


def _endcap_geometry_2d(spec: CapSpec, at, outdir, width: float):
    """2-D geometry for endcap/joint *style* at *at*, with local +Y rotated onto *outdir*.

    Returns a :class:`~pybosl2.shapes2d.Bosl2Shape2D`, matching what the rest of the 2-D stroke
    builds, so the pieces combine without leaking a raw native handle into the reduce()."""
    from pythonscad import polygon as _opolygon

    from pybosl2.shapes2d import Bosl2Shape2D

    polys = _endcap_polys(spec, width)
    if not polys:
        return None
    theta = math.degrees(math.atan2(outdir[1], outdir[0])) - 90.0  # BACK (+Y) -> outdir
    geos = [Bosl2Shape2D(_opolygon(_place(p.tolist(), theta, at))) for p in polys]
    return reduce(operator.or_, geos)


def _stroke2d(pts, width, closed, endcap1: CapSpec, endcap2: CapSpec, joints: CapSpec):
    """A 2-D stroke, as a :class:`~pybosl2.shapes2d.Bosl2Shape2D`.

    2-D geometry only exists on the CSG backend, so this raises under ``use_backend("sdf")``
    rather than quietly building a CSG shape that could not then be combined with the SDF solids
    around it. A 3-D path strokes on either backend -- see :func:`_stroke3d`.
    """
    from pybosl2._backend import current_backend
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.shapes2d import circle as _circle
    from pybosl2.shapes2d import square as _square

    if current_backend() != "csg":
        raise UnsupportedByBackendError(
            "stroke (2-D path)",
            current_backend(),
            hint="a 2-D stroke is 2-D geometry, which only the csg backend has. Stroke a Path3D "
            "for a solid tube on either backend, or draw the 2-D stroke under the default (csg) "
            "backend.",
        )
    shapes = []
    sides = len(pts)
    # Pull the body back under arrow endcaps; endcaps still sit at the original endpoints.
    body = list(pts)
    if not closed and sides >= 2:
        body = _trim_ends(body, _endcap_trim(endcap1, width), _endcap_trim(endcap2, width))
    nb = len(body)
    for i in range(nb) if closed else range(nb - 1):
        a, b = body[i], body[(i + 1) % nb]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1e-9:
            continue
        angle = math.degrees(math.atan2(dy, dx))
        mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
        shapes.append(_square([length, width]).rotate([0, 0, angle]).translate(mid))
    # Joints: round/square fill the corner with a centred blob; other styles use the oriented shape.
    for i in range(nb) if closed else range(1, nb - 1):
        at = body[i]
        if joints.cap_type == CapType.ROUND:
            shapes.append(_circle(diameter=width).translate([at[0], at[1]]))
        elif joints.cap_type == CapType.SQUARE:
            shapes.append(_square([width, width]).translate([at[0], at[1]]))
        else:
            incoming = [body[i][0] - body[i - 1][0], body[i][1] - body[i - 1][1]]
            blob = _endcap_geometry_2d(joints, at, incoming, width)
            if blob is not None:
                shapes.append(blob)
    if not closed and sides >= 2:
        for cap, end, ref in ((endcap1, pts[0], pts[1]), (endcap2, pts[-1], pts[-2])):
            outdir = [end[0] - ref[0], end[1] - ref[1]]
            blob = _endcap_geometry_2d(cap, end, outdir, width)
            if blob is not None:
                shapes.append(blob)
    assert shapes, "stroke(): path has no drawable segments."
    return reduce(operator.or_, shapes)


def _endcap_geometry_3d(spec: CapSpec, at, outdir, width: float):
    """3-D endcap for *style*: a sphere for round/dot, else the profile revolved to a solid.

    The sphere caps come from the backend-neutral facade, so they realize on whichever backend is
    active. The revolved caps (arrow/diamond/tail/...) are built by ``rotate_extrude()``, which
    only the csg backend has, so they raise :class:`~pybosl2.exceptions.UnsupportedByBackendError` under
    ``use_backend("sdf")``.
    """
    from pybosl2._backend import current_backend
    from pybosl2.exceptions import UnsupportedByBackendError

    if spec.cap_type in (CapType.NONE, CapType.BUTT):
        return None
    if spec.cap_type == CapType.ROUND:
        return _sphere(radius=width / 2).translate([float(c) for c in at])
    if spec.cap_type == CapType.DOT:
        return _sphere(radius=width).translate([float(c) for c in at])
    polys = _endcap_polys(spec, width)
    if not polys:
        return None
    if current_backend() != "csg":
        raise UnsupportedByBackendError(
            f"stroke(endcap={spec.cap_type!r})",
            current_backend(),
            hint="the revolved endcaps need rotate_extrude(), which the sdf backend has no "
            "equivalent for. Use endcap='round'/'dot'/'butt' there, or stroke on the csg backend.",
        )
    from pythonscad import polygon as _opolygon
    from pythonscad import rotate_extrude as _orotate_extrude
    from pythonscad import square as _osquare

    from pybosl2.shapes3d import Bosl2Solid

    big = max(abs(v) for poly in polys for p in poly for v in p) * 4 + width
    right = _osquare([big, big], center=True).translate([big / 2, 0])
    solids = [_orotate_extrude((_opolygon(poly.tolist()) & right)) for poly in polys]
    return _oriented_to(Bosl2Solid(reduce(operator.or_, solids)), outdir, at)


def _stroke3d(pts, width, closed, endcap1: CapSpec, endcap2: CapSpec):
    """A 3-D stroke -- a tube following *pts* -- on whichever backend is active.

    Every piece comes from the backend-neutral facade (:mod:`pybosl2.solid`), so this yields
    Bosl2Solids under the default csg backend and PyShapes under ``use_backend("sdf")``.
    """
    radius = width / 2
    shapes = []
    sides = len(pts)
    for i in range(sides) if closed else range(sides - 1):
        a = np.asarray(pts[i], dtype=float)
        b = np.asarray(pts[(i + 1) % sides], dtype=float)
        diameter = b - a
        length = float(np.linalg.norm(diameter))
        if length < 1e-9:
            continue
        seg = _oriented_to(
            _cyl(height=length, radius=radius).translate([0, 0, length / 2]),
            diameter,
            a,
        )
        shapes.append(seg)
    for i in range(sides) if closed else range(1, sides - 1):
        shapes.append(_sphere(radius=radius).translate([float(c) for c in pts[i]]))
    if not closed and sides >= 2:
        for cap, end, ref in ((endcap1, pts[0], pts[1]), (endcap2, pts[-1], pts[-2])):
            outdir = [end[j] - ref[j] for j in range(3)]
            blob = _endcap_geometry_3d(cap, end, outdir, width)
            if blob is not None:
                shapes.append(blob)
    assert shapes, "stroke(): path has no drawable segments."
    return reduce(operator.or_, shapes)


def stroke(
    path,
    width: float = 1,
    closed: bool | None = None,
    endcaps: CapType | CapSpec = CapType.ROUND,
    endcap1: CapType | CapSpec = CapType.ROUND,
    endcap2: CapType | CapSpec = CapType.ROUND,
    joints: CapType | CapSpec = CapType.ROUND,
    dots=False,
    color=None,
):
    """Render *path* as a solid line of the given *width* -- BOSL2's ``stroke()``.

    Works on a 2-D or 3-D point list, a :class:`~pybosl2.paths.Path2D`, a :class:`~pybosl2.paths.Path3D`,
    or a :class:`~pybosl2.regions.Region` (each of its paths is stroked closed). A 2-D stroke is a
    union of segment rectangles with joints and endcaps; a 3-D stroke is a tube of cylinders with
    spherical joints and revolved endcaps. Returns native geometry.

    Every BOSL2 endcap/joint style is generated directly via :class:`CapType`:
    ``ROUND`` (default), ``SQUARE``, ``BUTT``, ``DOT``, ``BLOCK``, ``DIAMOND``,
    ``CHISEL``, ``LINE``, ``X``, ``CROSS``, ``ARROW``, ``ARROW2``, ``ARROW3``,
    ``TAIL``, and ``TAIL2``. Arrow endcaps trim the line back so it doesn't poke
    through the tip.

    Args:
        path:     a point list, :class:`~pybosl2.paths.Path2D`/:class:`~pybosl2.paths.Path3D`, or
        :class:`~pybosl2.regions.Region`
        width:    line width (default 1)
        closed:   close the path into a loop (default: the path's own ``closed`` flag, or True for a Region)
        endcaps:  style for both ends (``endcap1``/``endcap2`` override per end)
        joints:   style for the interior corners (default ``ROUND``)
        dots:     mark every vertex with a round dot
        color:    optional colour applied to the whole stroke

    Examples:
        An arc drawn as a 3-mm ribbon with round ends, extruded into a curved wall:

        .. pythonscad-example::

            arc(radius=30, angle=200).stroke(width=3).linear_extrude(height=5).show()

        A line with a fancy endcap on each end (arrow one way, tail the other):

        .. pythonscad-example::

            from pybosl2.caps import CapType
            stroke([[0, 0], [50, 0]], width=3, endcap1=CapType.TAIL, endcap2=CapType.ARROW) \
                .linear_extrude(height=3).show()

        A 3-D arrow: the endcap is a revolved cone on the tube:

        .. pythonscad-example::

            stroke([[0, 0, 0], [40, 0, 0]], width=4, endcaps='arrow').show()
    """
    from pybosl2.regions import Region

    if isinstance(path, Region) or (
        isinstance(path, (list, tuple))
        and len(path)
        and isinstance(path[0], (Path2D, Path3D))
        and not isinstance(path, (Path2D, Path3D))
    ):
        parts = [stroke(p, width=width, closed=True, joints=joints, dots=dots) for p in path]
        shape = reduce(operator.or_, parts)
        return shape.color(color) if color is not None else shape

    pts = [list(map(float, p)) for p in path]
    assert len(pts) >= 1, "stroke(): empty path."
    is_closed = closed if closed is not None else getattr(path, "closed", False)
    # Normalize styles to CapSpec for all internal calls
    # endcaps acts as a fallback when endcap1/endcap2 are at their defaults
    ec1_raw: CapType | CapSpec = endcap1
    ec2_raw: CapType | CapSpec = endcap2
    if endcaps != CapType.ROUND:
        if endcap1 == CapType.ROUND:
            ec1_raw = endcaps
        if endcap2 == CapType.ROUND:
            ec2_raw = endcaps
    ec1 = ec1_raw if isinstance(ec1_raw, CapSpec) else _normalize_one(ec1_raw)
    ec2 = ec2_raw if isinstance(ec2_raw, CapSpec) else _normalize_one(ec2_raw)
    jnt = joints if isinstance(joints, CapSpec) else _normalize_one(joints)
    if dots:
        jnt = _normalize_one(CapType.DOT)
        ec1 = _normalize_one(CapType.DOT)
        ec2 = _normalize_one(CapType.DOT)

    dim = len(pts[0])
    result: Any = (
        _stroke2d(pts, width, is_closed, ec1, ec2, jnt) if dim == 2 else _stroke3d(pts, width, is_closed, ec1, ec2)
    )
    return result.color(color) if color is not None else result


def dashed_stroke(
    path,
    dashpat: Sequence[float] = (3, 3),
    closed: bool = False,
    fit: bool = True,
    mindash: float = 0.5,
) -> "list[Path2D | Path3D]":
    """Break *path* into dashes -- BOSL2's ``dashed_stroke()`` function form.

    Returns the list of "on" dash sub-paths (each a :class:`~pybosl2.paths.Path2D`); stroke or extrude
    them to draw a dashed line. *dashpat* alternates dash/gap lengths. With *fit* (the default) the
    pattern is scaled slightly so a whole number of repeats fills the path exactly.

    Args:
        path:    a point list, :class:`~pybosl2.paths.Path2D`, or :class:`~pybosl2.regions.Region`
        dashpat: alternating [dash, gap, ...] lengths (default ``(3, 3)``)
        closed:  treat the path as a closed loop
        fit:     scale the pattern to fit a whole number of repeats (default True)
        mindash: drop a trailing dash shorter than this (default 0.5)

    Examples:
        A dashed circle outline, the dashes unioned and extruded into little tiles:

        .. pythonscad-example::

            dashes = dashed_stroke(arc(radius=30, angle=360), dashpat=[6, 4], closed=True)
            ring = reduce(lambda a, b: a | b, (d.stroke(width=1.5) for d in dashes))
            ring.linear_extrude(height=3).show()
    """
    from pybosl2.regions import Region

    if isinstance(path, Region):
        out: list[Any] = []
        for p in path:
            out.extend(dashed_stroke(list(p), dashpat, closed=True, fit=fit, mindash=mindash))
        return out

    raw = [list(map(float, p)) for p in path]
    # a 3-D path yields 3-D dashes (Path3D); a 2-D path yields Path2D
    wrap = Path3D if raw and len(raw[0]) == 3 else Path2D
    if closed:
        raw = raw + [raw[0]]
    dpat = list(dashpat) if len(dashpat) % 2 == 0 else list(dashpat) + [0]
    plen = Path2D(raw, closed=False).perimeter() if wrap == Path2D else Path3D(raw, closed=False).perimeter()
    dlen = sum(dpat)
    doff = list(np.cumsum(dpat))
    freps = plen / dlen
    reps = max(1, round(freps) if fit else math.floor(freps))
    tlen = plen if not fit else reps * dlen + (0 if closed else dpat[0])
    sc = plen / tlen
    cuts = []
    for i in range(reps + 1):
        for off in doff:
            x = i * dlen * sc + off * sc
            if 0 < x < plen - 1e-9:
                cuts.append(x)
    cuts = sorted(c for c in cuts)
    if not cuts:
        return [wrap(raw, closed=False)]
    dashes = wrap(raw).cut(cuts, closed=False)
    dcnt = len(dashes)
    evens = []
    for i, dash in enumerate(dashes):
        if i % 2 != 0:
            continue
        if i < dcnt - 1 or wrap(dash.array, closed=False).perimeter() > mindash:
            evens.append(wrap(dash, closed=False))  # type: ignore[arg-type]
    return evens
