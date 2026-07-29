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

from pybosl2.caps import CapSpec, CapType, _endcap_polys, _endcap_trim, _normalize_one
from pybosl2.geometry import general_line_intersection, line_normal
from pybosl2.math import lerp, lerpn
from pybosl2.paths import Path2D, Path3D
from pybosl2.shapes2d import _frag_count, _pick_radius, arc

# The stroke body is built from the backend-neutral facade, NOT pybosl2.shapes3d directly, so a
# 3-D stroke realizes on whichever backend is active: Bosl2Solids under the default csg backend,
# PyShapes under use_backend("sdf").
from pybosl2.solid import cyl as _cyl  # type: ignore[attr-defined]
from pybosl2.solid import sphere as _sphere  # type: ignore[attr-defined]
from pybosl2.vectors import unit

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "arc",
    "catenary",
    "helix",
    "turtle",
    "stroke",
    "dashed_stroke",
    "CapSpec",
]


# ---------------------------------------------------------------------------
# Section: 2-D helpers
# ---------------------------------------------------------------------------


def _rot2(deg: float, v: "Sequence[float] | np.ndarray") -> np.ndarray:
    """Rotate the 2-D vector *v* by *deg* degrees about the origin."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    x, y = float(v[0]), float(v[1])
    return np.array([c * x - s * y, s * x + c * y])


def _rot_pts(deg: float, pts):
    """Rotate a list of 2-D points by *deg* degrees about the origin."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [[c * p[0] - s * p[1], s * p[0] + c * p[1]] for p in pts]


# ---------------------------------------------------------------------------
# Section: Path2D generators
# ---------------------------------------------------------------------------


def catenary(
    width: float,
    droop: float | None = None,
    sides: int = 100,
    angle: float | None = None,
) -> Path2D:
    """The catenary (hanging-chain) curve of the given *width*, as a :class:`~pybosl2.paths.Path2D`.

    Give exactly one of *droop* (how far the middle hangs below the endpoints) or *angle* (the
    slope in degrees at the endpoints). The curve passes through ``[-width/2, 0]`` and
    ``[width/2, 0]`` and hangs downward (negative *droop*/*angle* flips it upward). This is BOSL2's
    ``catenary()``.

    Args:
        width: horizontal distance between the endpoints (> 0)
        droop: how far the midpoint hangs below the endpoints (give this or *angle*)
        sides:     number of points along the curve (default 100)
        angle: endpoint slope in degrees, ``0 < |angle| < 90`` (give this or *droop*)

    Examples:
        A hanging arch, stroked into a 2-mm ribbon and extruded into a wall:

        .. pythonscad-example::

            catenary(width=80, droop=30).stroke(width=2).linear_extrude(height=6).show()
    """
    assert (droop is None) != (angle is None), "catenary() needs exactly one of droop= or angle="
    assert width > 0, "catenary() needs width > 0."
    assert isinstance(sides, int) and sides > 0, "catenary() needs a positive integer sides."
    given = droop if droop is not None else angle
    assert given is not None
    sgn = int(math.copysign(1, given))
    droop_a = None if droop is None else abs(droop)
    angle_a = None if angle is None else abs(angle)
    assert angle_a is None or (0 < angle_a < 90), "catenary() angle must satisfy 0 < |angle| < 90."

    if droop_a is None:  # solve for the scale that gives the requested endpoint slope
        assert angle_a is not None

        def slope_fn(x):
            p1 = math.cosh(x - 0.001) - 1
            p2 = math.cosh(x + 0.001) - 1
            return math.degrees(math.atan2(p2 - p1, 0.002))

        target, f = angle_a, slope_fn
    else:  # solve for the scale that gives the requested droop

        def droop_fn(x):
            return (math.cosh(x) - 1) / x if x != 0 else 0.0

        target, f = droop_a / (width / 2), droop_fn

    # binary search on x for f(x) == target (f is monotonic increasing away from 0)
    x, inc = 0.0, 4.0
    while inc >= 1e-9:
        if f(x + inc) > target:
            inc /= 2
        else:
            x += inc
    scx = x
    sc = (width / 2) / scx
    droop_v = droop_a if droop_a is not None else (math.cosh(scx) - 1) * sc
    pts = []
    for xv in lerpn(-scx, scx, sides):
        xval = xv * sc
        yval = 0.0 if abs(abs(xv) - scx) < 1e-9 else (math.cosh(xv) - 1) * sc - droop_v
        pts.append([xval, yval])
    if sgn < 0:
        pts = [[p[0], -p[1]] for p in pts]
    return Path2D(pts, closed=False)


def helix(
    length: float | None = None,
    height: float | None = None,
    turns: float | None = None,
    angle: float | None = None,
    radius: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
) -> Path3D:
    """A 3-D helical path on a (possibly conical) surface -- BOSL2's ``helix()``.

    Returned as a :class:`~pybosl2.paths.Path3D` (the 3-D path object), so it carries the 3-D
    transforms/measurements and feeds straight into :func:`stroke` or ``path_sweep``. Give
    exactly two of *length*/*height* (length), *turns*, and *angle*; the third is derived. Positive *turns*
    is right-handed, negative left-handed. Start/end radii may differ for a conical helix (a flat
    spiral is ``height=0`` with a turn count).

    Args:
        length/height:     height of the helix (0 for a flat spiral)
        turns:   number of turns (positive = right-handed)
        angle:   helix angle in degrees (measured at the base radius)
        radius/diameter:     radius / diameter (constant helix)
        radius1/diameter1:   bottom radius / diameter
        radius2/diameter2:   top radius / diameter

    Examples:
        A 2.5-turn helix drawn as a tube:

        .. pythonscad-example::

            stroke(helix(turns=2.5, height=100, radius=30), width=3).show()
    """
    r1v = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    r2v = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)
    length = length if length is not None else height
    assert sum(v is not None for v in (length, turns, angle)) == 2, (
        "helix() needs exactly two of length/height, turns, and angle."
    )
    assert angle is None or length != 0, "helix() cannot take an angle with length 0."
    if angle is not None and length != 0:
        dz = 2 * math.pi * r1v * math.tan(math.radians(angle))
    else:
        assert length is not None and turns is not None  # else-branch only reached with both set
        dz = length / abs(turns)
    if turns is not None:
        maxtheta = 360.0 * turns
    else:
        assert length is not None
        maxtheta = 360.0 * length / dz
    nseg = _frag_count(max(r1v, r2v))
    count = max(3, math.ceil(abs(maxtheta) * nseg / 360))
    out = []
    for theta in lerpn(0, maxtheta, count):
        radius = lerp(r1v, r2v, theta / maxtheta) if maxtheta != 0 else r1v
        out.append(
            [
                radius * math.cos(math.radians(theta)),
                radius * math.sin(math.radians(theta)),
                abs(theta) / 360.0 * dz,
            ]
        )
    return Path3D(out, closed=False)


# --- turtle ----------------------------------------------------------------

_TURTLE_TWO_ARG = ("arcleft", "arcright", "arcleftto", "arcrightto")


def turtle(
    commands: Sequence,
    state: Sequence | None = None,
    full_state: bool = False,
    repeat: int = 1,
) -> Path2D | list:
    """Build a 2-D path from [turtle-graphics](https://en.wikipedia.org/wiki/Turtle_graphics)
    *commands* -- BOSL2's ``turtle()``.

    *commands* is a flat list of command names each optionally followed by a parameter, e.g.
    ``["move", 10, "left", 90, "move", 10]``. The turtle starts at the origin pointing along +X
    with a step length of 1. By default the computed path is returned as a
    :class:`~pybosl2.paths.Path2D`; set *full_state* to get ``[path, step_vector, angle, arcsteps]``
    instead. *repeat* runs the whole command list that many times.

    Supported commands: ``move``/``xmove``/``ymove``/``xymove``, ``jump``/``xjump``/``yjump``,
    ``untilx``/``untily``, ``left``/``turn``/``right``, ``angle``, ``setdir``, ``length``/
    ``scale``/``addlength``, ``arcsteps``, ``arcleft``/``arcright``, ``arcleftto``/``arcrightto``,
    and ``repeat`` (``["repeat", count, [subcommands]]``).

    Examples:
        A rounded-corner square drawn with arcs:

        .. pythonscad-example::

            path = turtle(["move", 40, "arcleft", 8, "move", 40, "arcleft", 8,
                           "move", 40, "arcleft", 8, "move", 40, "arcleft", 8])
            path.stroke(width=3, closed=True).linear_extrude(height=4).show()
    """
    state = [[[0.0, 0.0]], [1.0, 0.0], 90.0, 0.0] if state is None else list(state)
    result = _turtle_repeat(list(commands), state, True, repeat)
    return result if full_state else Path2D(result[0], closed=False)


def _turtle_repeat(commands, state, full_state, repeat):
    for _ in range(int(repeat)):
        state = _turtle(commands, state)
    return state if full_state else state[0]


def _turtle_command_len(commands, index) -> int:
    if commands[index] == "repeat":
        return 3
    if commands[index] in _TURTLE_TWO_ARG and len(commands) > index + 2 and not isinstance(commands[index + 2], str):
        return 3
    if index + 1 < len(commands) and isinstance(commands[index + 1], str):
        return 1
    if index + 1 >= len(commands):
        return 1
    return 2


def _turtle(commands, state, index: int = 0):
    while index < len(commands):
        parm = commands[index + 1] if index + 1 < len(commands) else None
        parm2 = commands[index + 2] if index + 2 < len(commands) else None
        state = _turtle_command(commands[index], parm, parm2, state, index)
        index += _turtle_command_len(commands, index)
    return state


def _turtle_command(command, parm, parm2, state, index):
    path_idx, step_idx, ang_idx, arcs_idx = 0, 1, 2, 3
    if command == "repeat":
        assert isinstance(parm, (int, float)), f'"repeat" needs a count at index {index}'
        assert isinstance(parm2, (list, tuple)), f'"repeat" needs a command list at index {index}'
        return _turtle_repeat(list(parm2), state, True, int(parm))

    parm = None if isinstance(parm, str) else parm
    parm2 = None if isinstance(parm2, str) else parm2
    lastpt = np.asarray(state[path_idx][-1], dtype=float)
    step = np.asarray(state[step_idx], dtype=float)

    def with_point(p):
        s = list(state)
        s[path_idx] = state[path_idx] + [[float(p[0]), float(p[1])]]
        return s

    def with_step(v):
        s = list(state)
        s[step_idx] = [float(v[0]), float(v[1])]
        return s

    if command == "move":
        return with_point((parm if parm is not None else 1) * step + lastpt)
    if command == "xmove":
        return with_point((parm if parm is not None else 1) * np.linalg.norm(step) * np.array([1, 0]) + lastpt)
    if command == "ymove":
        return with_point((parm if parm is not None else 1) * np.linalg.norm(step) * np.array([0, 1]) + lastpt)
    if command == "xymove":
        return with_point(lastpt + np.asarray(parm, dtype=float))
    if command == "jump":
        return with_point(parm)
    if command == "xjump":
        return with_point([parm, lastpt[1]])
    if command == "yjump":
        return with_point([lastpt[0], parm])
    if command == "untilx":
        res = general_line_intersection([lastpt, lastpt + step], [[parm, 0], [parm, 1]])
        assert res is not None, f'"untilx" never reaches the goal at index {index}'
        return with_point(res[0])
    if command == "untily":
        res = general_line_intersection([lastpt, lastpt + step], [[0, parm], [1, parm]])
        assert res is not None, f'"untily" never reaches the goal at index {index}'
        return with_point(res[0])
    if command in ("turn", "left"):
        return with_step(_rot2(parm if parm is not None else state[ang_idx], step))
    if command == "right":
        return with_step(_rot2(-(parm if parm is not None else state[ang_idx]), step))
    if command == "angle":
        s = list(state)
        s[ang_idx] = parm
        return s
    if command == "setdir":
        if isinstance(parm, (list, tuple, np.ndarray)):
            return with_step(np.linalg.norm(step) * unit([parm[0], parm[1]]))
        return with_step(np.linalg.norm(step) * np.array([math.cos(math.radians(parm)), math.sin(math.radians(parm))]))
    if command == "length":
        return with_step(parm * unit(step))
    if command == "scale":
        return with_step(parm * step)
    if command == "addlength":
        return with_step(step + unit(step) * parm)
    if command == "arcsteps":
        s = list(state)
        s[arcs_idx] = parm
        return s
    if command in ("arcleft", "arcright", "arcleftto", "arcrightto"):
        return _turtle_arc(command, parm, parm2, state, index)
    raise AssertionError(f'Unknown turtle command "{command}" at index {index}')


def _turtle_arc(command, parm, parm2, state, index):
    path_idx, step_idx, ang_idx, arcs_idx = 0, 1, 2, 3
    assert isinstance(parm, (int, float)), f'"{command}" needs a numeric radius at index {index}'
    lastpt = np.asarray(state[path_idx][-1], dtype=float)
    step = np.asarray(state[step_idx], dtype=float)
    lrsign = 1 if command in ("arcleft", "arcleftto") else -1
    steps = _frag_count(abs(parm)) if state[arcs_idx] == 0 else int(state[arcs_idx])

    if command in ("arcleft", "arcright"):
        myangle = parm2 if parm2 is not None else state[ang_idx]
        radius = parm * (1 if myangle >= 0 else -1)
        center = lastpt + lrsign * radius * line_normal([0, 0], step)
        turn = math.copysign(1, parm) * lrsign * myangle
        rot_step = _rot2(lrsign * myangle, step)
    else:  # arcleftto / arcrightto
        assert isinstance(parm2, (int, float)), f'"{command}" needs a numeric angle at index {index}'
        radius = parm
        center = lastpt + lrsign * radius * line_normal([0, 0], step)
        start_angle = math.degrees(math.atan2(step[1], step[0])) % 360
        end_angle = parm2 % 360
        if lrsign * end_angle < lrsign * start_angle:
            end_angle = end_angle + lrsign * 360
        delta = -start_angle + end_angle
        turn = math.copysign(1, radius) * delta
        rot_step = _rot2(delta, step)

    if turn == 0 or radius == 0:
        arcpath = []
    else:
        p_mid = _rot2(turn / 2, lastpt - center) + center
        p_end = _rot2(turn, lastpt - center) + center
        arcpath = list(arc(steps, points=[lastpt, p_mid, p_end]))[1:]  # drop the shared first point
    s = list(state)
    s[path_idx] = state[path_idx] + [[float(p[0]), float(p[1])] for p in arcpath]
    s[step_idx] = [float(rot_step[0]), float(rot_step[1])]
    return s


# ---------------------------------------------------------------------------
# Section: Path2D renderers
# ---------------------------------------------------------------------------


def _place(poly, theta_deg: float, at):
    """Rotate a local polygon by *theta_deg* and translate it to point *at*."""
    radius = math.radians(theta_deg)
    c, s = math.cos(radius), math.sin(radius)
    return [[c * p[0] - s * p[1] + at[0], s * p[0] + c * p[1] + at[1]] for p in poly]


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


def _trim_ends(body, trim1: float, trim2: float):
    """Shorten the open *body* path at each end by trim1/trim2 (clamped within the end segment)."""
    body = [list(map(float, p)) for p in body]
    if len(body) >= 2 and trim1 > 0:
        a, b = np.asarray(body[0]), np.asarray(body[1])
        seglen = float(np.linalg.norm(b - a)) or 1.0
        body[0] = list(a + (b - a) / seglen * min(trim1, 0.99 * seglen))
    if len(body) >= 2 and trim2 > 0:
        a, b = np.asarray(body[-1]), np.asarray(body[-2])
        seglen = float(np.linalg.norm(b - a)) or 1.0
        body[-1] = list(a + (b - a) / seglen * min(trim2, 0.99 * seglen))
    return body


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


def _oriented_to(shape, outdir, at):
    """Rotate a Z-up solid so +Z points along 3-D *outdir*, then translate it to *at*.

    Uses ``rotate(angle, axis)`` rather than a 4x4 ``multmatrix`` so it works on either backend's
    solid -- an SDF PyShape rotates its field in closed form, but has no multmatrix.
    """
    from pybosl2.transforms import rot_from_to

    angle, axis = rot_from_to([0, 0, 1], outdir)
    return shape.rotate(float(angle), [float(c) for c in axis]).translate([float(c) for c in at])


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
        return out  # type: ignore[return-value]

    raw = [list(map(float, p)) for p in path]
    # a 3-D path yields 3-D dashes (Path3D); a 2-D path yields Path2D
    wrap = Path3D if raw and len(raw[0]) == 3 else Path2D
    if closed:
        raw = raw + [raw[0]]
    dpat = list(dashpat) if len(dashpat) % 2 == 0 else list(dashpat) + [0]
    plen = wrap(raw).total_length(closed=False)
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
        return [wrap(raw, closed=False)]  # type: ignore[return-value]
    dashes = wrap(raw).path_cut(cuts, closed=False)
    dcnt = len(dashes)
    evens = []
    for i, dash in enumerate(dashes):
        if i % 2 != 0:
            continue
        if i < dcnt - 1 or wrap(dash).total_length(closed=False) > mindash:
            evens.append(wrap(dash, closed=False))
    return evens  # type: ignore[return-value]
