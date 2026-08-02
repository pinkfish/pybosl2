# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""3-D stroke implementation: tubes, joints, and revolved endcaps.

Called directly by :meth:`Path3D.stroke` and :meth:`Path3D.dashed_stroke`.
Returns :class:`~pybosl2.shapes3d.Bosl2Solid` unions.
"""

# LibFile: pybosl2/_stroke3d.py
# FileGroup: BOSL2

from __future__ import annotations

import math
import operator
from functools import reduce
from typing import TYPE_CHECKING, Any

from pybosl2.caps import CapSpec, CapType, _endcap_polys, _oriented_to
from pybosl2.shapes3d import cyl as _cyl
from pybosl2.shapes3d import sphere as _sphere

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pybosl2.shapes3d import Bosl2Solid


def _endcap_geometry_3d(spec: CapSpec, at: Sequence[float], outdir: Sequence[float], width: float) -> Any:
    import warnings

    from pybosl2._backend import current_backend

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
        warnings.warn(
            f"Decorative endcap {spec.cap_type!r} not supported on SDF backend; falling back to ROUND sphere",
            stacklevel=2,
        )
        return _sphere(radius=width / 2).translate([float(c) for c in at])
    from pythonscad import polygon as _opolygon
    from pythonscad import rotate_extrude as _orotate_extrude
    from pythonscad import square as _osquare

    from pybosl2.shapes3d import Bosl2Solid

    big = max(abs(v) for poly in polys for p in poly for v in p) * 4 + width
    right = _osquare([big, big], center=True).translate([big / 2, 0])
    solids = [_orotate_extrude((_opolygon(poly) & right)) for poly in polys]
    return _oriented_to(Bosl2Solid(reduce(operator.or_, solids)), outdir, at)


def stroke_3d(
    path: Any,
    width: float = 1,
    closed: bool | None = None,
    endcap1: CapSpec | None = None,
    endcap2: CapSpec | None = None,
) -> Bosl2Solid:
    """3-D stroke: a tube along *path* as a :class:`Bosl2Solid` union."""
    from pybosl2.shapes3d import Bosl2Solid

    pts = [list(map(float, p)) for p in path]
    assert len(pts) >= 2, "stroke(): need at least 2 points."
    is_closed = closed if closed is not None else getattr(path, "closed", False)
    ec1 = endcap1 if endcap1 is not None else CapSpec(cap_type=CapType.ROUND)
    ec2 = endcap2 if endcap2 is not None else CapSpec(cap_type=CapType.ROUND)

    radius = width / 2
    shapes = []
    sides = len(pts)
    for i in range(sides) if is_closed else range(sides - 1):
        ax, ay, az = float(pts[i][0]), float(pts[i][1]), float(pts[i][2])
        bx, by, bz = float(pts[(i + 1) % sides][0]), float(pts[(i + 1) % sides][1]), float(pts[(i + 1) % sides][2])
        dx, dy, dz = bx - ax, by - ay, bz - az
        length = math.hypot(math.hypot(dx, dy), dz)
        if length < 1e-9:
            continue
        seg = _oriented_to(
            _cyl(height=length, radius=radius).translate([0, 0, length / 2]),
            [dx, dy, dz],
            [ax, ay, az],
        )
        shapes.append(seg)
    for i in range(sides) if is_closed else range(1, sides - 1):
        shapes.append(_sphere(radius=radius).translate([float(c) for c in pts[i]]))
    if not is_closed and sides >= 2:
        for cap, end, ref in ((ec1, pts[0], pts[1]), (ec2, pts[-1], pts[-2])):
            outdir = [end[j] - ref[j] for j in range(3)]
            blob = _endcap_geometry_3d(cap, end, outdir, width)
            if blob is not None:
                shapes.append(blob)
    assert shapes, "stroke(): path has no drawable segments."
    return Bosl2Solid(reduce(operator.or_, shapes))


def dashed_stroke_3d(
    path: Any,
    dashpat: Sequence[float] | None = None,
    closed: bool | None = None,
    fit: bool = True,
    mindash: float = 0.5,  # noqa: ARG001
) -> Bosl2Solid:
    """3-D dashed stroke: dashes along *path*, each stroked and unioned.

    Returns:
        A :class:`Bosl2Solid` union of all dash tubes.
    """
    from pybosl2.shapes3d import Bosl2Solid

    dpat = list(dashpat) if dashpat else [3, 3]
    if len(dpat) % 2 == 1:
        dpat = dpat + [0]

    pts = [list(map(float, p)) for p in path]
    assert len(pts) >= 2, "dashed_stroke(): need at least 2 points."
    is_closed = closed if closed is not None else getattr(path, "closed", False)
    raw = pts + [pts[0]] if is_closed else pts

    plen = _path_length_3d(raw)
    dlen = sum(dpat)
    if dlen < 1e-12:
        return Bosl2Solid(None)
    doff: list[float] = []
    s = 0.0
    for x in dpat:
        s += float(x)
        doff.append(s)
    freps = plen / dlen
    reps = max(1, round(freps) if fit else math.floor(freps))
    tlen = plen if not fit else reps * dlen + (0 if is_closed else dpat[0])
    sc = plen / tlen
    cuts = []
    for i in range(reps + 1):
        for off in doff:
            x = i * dlen * sc + off * sc
            if 0 < x < plen - 1e-9:
                cuts.append(x)
    cuts = sorted(set(cuts))

    if not cuts:
        return stroke_3d(path, width=1, closed=is_closed)

    segments = _cut_path_3d(raw, cuts, is_closed)
    shapes = []
    for seg in segments:
        if len(seg) >= 2:
            seg_solid = stroke_3d(
                seg,
                width=1,
                closed=False,
                endcap1=CapSpec(cap_type=CapType.BUTT),
                endcap2=CapSpec(cap_type=CapType.BUTT),
            )
            if seg_solid is not None:
                shapes.append(seg_solid)

    if not shapes:
        return Bosl2Solid(None)
    return Bosl2Solid(reduce(operator.or_, shapes))


def _path_length_3d(pts: list[list[float]]) -> float:
    total = 0.0
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        dz = pts[i + 1][2] - pts[i][2]
        total += math.hypot(math.hypot(dx, dy), dz)
    return total


def _cut_path_3d(
    pts: list[list[float]],
    cuts: list[float],
    closed: bool,  # noqa: ARG001
) -> list[list[list[float]]]:
    """Split a 3-D path at cut distances, returning dash segments."""
    seg_lengths = []
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        dz = pts[i + 1][2] - pts[i][2]
        seg_lengths.append(math.hypot(math.hypot(dx, dy), dz))

    total = 0.0
    cut_starts = [0.0]
    for seg in seg_lengths:
        total += seg
        cut_starts.append(total)

    dashes = []
    for ci in range(0, len(cuts) - 1, 2):
        if cuts[ci] >= total - 1e-9:
            break
        c1 = cuts[ci]
        c2 = cuts[min(ci + 1, len(cuts) - 1)]
        dash = [_point_at_3d(pts, seg_lengths, cut_starts, c1)]
        dash.append(_point_at_3d(pts, seg_lengths, cut_starts, c2))
        dashes.append(dash)
    return dashes


def _point_at_3d(
    pts: list[list[float]],
    seg_lengths: list[float],
    cut_starts: list[float],
    dist: float,
) -> list[float]:
    for i, seg_len in enumerate(seg_lengths):
        seg_start = cut_starts[i]
        seg_end = cut_starts[i + 1]
        if seg_start <= dist <= seg_end:
            t = (dist - seg_start) / seg_len if seg_len > 0 else 0
            ax, ay, az = float(pts[i][0]), float(pts[i][1]), float(pts[i][2])
            bx, by, bz = float(pts[i + 1][0]), float(pts[i + 1][1]), float(pts[i + 1][2])
            return [ax + (bx - ax) * t, ay + (by - ay) * t, az + (bz - az) * t]
    return list(pts[-1])
