# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""2-D stroke implementation: produces polygon outlines via Shapely buffer.

Called directly by :meth:`Path2D.stroke` and :meth:`Path2D.dashed_stroke`.
"""

# LibFile: pybosl2/_stroke2d.py
# FileGroup: BOSL2

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import shapely as _shapely
from shapely.geometry import LineString

from pybosl2._backend import builds_with
from pybosl2.caps import CapSpec, CapType, endcap_polys, endcap_trim, normalize_one, place, trim_ends
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.path2d import Path2D

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pybosl2.paths import PathLike
    from pybosl2.regions import Region


def _ensure_closed(pts: Sequence[Sequence[float]], closed: bool | None, path_closed: bool) -> bool:
    if closed is not None:
        return closed
    if len(pts) < 2:
        return False
    return path_closed


def _needs_decorative_cap(cap: CapSpec) -> bool:
    """Return True if this cap type produces a decorative polygon rather than a simple buffer end style."""
    ct = cap.cap_type
    # CIRCLE is deliberately absent: it has no buffer style, so leaving it here made it fall
    # through to `_cap_style`'s "flat" default and render as BUTT with no warning. It is
    # decorative as far as this gate is concerned, which routes it to `endcap_polys` and its
    # refusal -- the same answer the 3-D stroke and the sweep already gave.
    return ct not in (CapType.NONE, CapType.BUTT, CapType.ROUND, CapType.SQUARE, CapType.SPHERE)


def _cap_style(cap: CapSpec) -> str:
    # SPHERE is documented as a synonym of ROUND and is one on the sweep path; it reached this
    # function's "flat" default instead, so a sphere-capped 2-D stroke came out butt-ended.
    if cap.cap_type in (CapType.ROUND, CapType.SPHERE):
        return "round"
    if cap.cap_type == CapType.SQUARE:
        return "square"
    return "flat"  # BUTT, NONE, etc → flat


def _place_and_union(
    body: _shapely.Polygon | _shapely.MultiPolygon,
    cap_spec: CapSpec,
    width: float,
    at: Sequence[float],
    tangent: Sequence[float],
) -> _shapely.Polygon | _shapely.MultiPolygon:
    """Place endcap polygon(s) at a point and union them with the body geometry.

    Args:
        body: The buffered stroke body geometry.
        cap_spec: The resolved cap specification.
        width: The stroke line width.
        at: The endpoint position ``[x, y]``.
        tangent: The outward tangent direction ``[dx, dy]`` at the endpoint.

    Returns:
        The unioned shapely geometry.

    """
    angle = math.degrees(math.atan2(tangent[1], tangent[0]))
    half = width / 2

    for ep_poly in endcap_polys(cap_spec, width):
        placed = place(Path2D(ep_poly), angle, at)
        if len(placed) < 2:
            continue
        coords: list[tuple[float, float]] = [(float(p[0]), float(p[1])) for p in placed]
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        if len(coords) < 4:
            geom: _shapely.Polygon | _shapely.GeometryCollection = LineString(coords).buffer(half, cap_style="flat")
        else:
            geom = _shapely.Polygon(coords)
            if not geom.is_valid:
                from shapely import make_valid

                geom = make_valid(geom)
        if geom.is_empty:
            continue
        body = body.union(geom)
    return body


def _shapely_to_path2d(geom: _shapely.Polygon | _shapely.MultiPolygon, fallback_pts: list[list[float]]) -> Path2D:
    """Convert a shapely geometry back to :class:`Path2D`.

    For MultiPolygon results, the largest polygon by area is used.
    """
    if isinstance(geom, _shapely.Polygon) and not geom.is_empty:
        return Path2D([list(c) for c in geom.exterior.coords], closed=True)
    if isinstance(geom, _shapely.MultiPolygon) and not geom.is_empty:
        largest = max(geom.geoms, key=lambda g: g.area)
        return Path2D([list(c) for c in largest.exterior.coords], closed=True)
    return Path2D(fallback_pts, closed=False)


@builds_with("csg")
def stroke_2d(
    path: "PathLike",
    width: float = 1,
    closed: bool | None = None,
    endcap1: CapType | CapSpec = CapType.ROUND,
    endcap2: CapType | CapSpec = CapType.ROUND,
    joints: CapType | CapSpec = CapType.ROUND,  # noqa: ARG001
) -> Path2D:
    """2-D stroke: buffer the polyline into a polygon outline.

    For decorative endcaps (arrows, diamonds, dots, etc.), the cap polygons are
    generated, placed at the endpoints, and unioned with the buffered body.


    Args:
        path: The path to draw.
        width: Width of the drawn line.
        closed: Join the last point back to the first.
        endcap1: Treatment for the start of the line.
        endcap2: Treatment for the end.
        joints: Treatment at each interior corner.

    Returns:
        A :class:`Path2D` of the stroked polygon outline.

    """
    pts = [list(map(float, p)) for p in path]
    if not (len(pts) >= 2):
        raise Bosl2ValueError("stroke(): need at least 2 points.")
    is_closed = _ensure_closed(pts, closed, getattr(path, "closed", False))
    ec1 = endcap1 if isinstance(endcap1, CapSpec) else normalize_one(endcap1)
    ec2 = endcap2 if isinstance(endcap2, CapSpec) else normalize_one(endcap2)
    half = width / 2

    coords = [(float(p[0]), float(p[1])) for p in pts]
    if is_closed:
        ring = _shapely.LinearRing(coords)
        poly = ring.buffer(half, join_style="round")
        if isinstance(poly, _shapely.Polygon) and not poly.is_empty:
            return Path2D([list(c) for c in poly.exterior.coords], closed=True)
        return Path2D(pts, closed=True)

    has_dec1 = _needs_decorative_cap(ec1)
    has_dec2 = _needs_decorative_cap(ec2)

    trim1 = endcap_trim(ec1, width) if has_dec1 else 0.0
    trim2 = endcap_trim(ec2, width) if has_dec2 else 0.0
    work_pts = trim_ends(pts, trim1, trim2) if (trim1 or trim2) else pts

    cs = "flat" if (has_dec1 or has_dec2) else _cap_style(ec1)
    work_coords = [(float(p[0]), float(p[1])) for p in work_pts]
    line = LineString(work_coords)
    body: _shapely.Polygon | _shapely.MultiPolygon = line.buffer(
        half, cap_style=cs, join_style="round", single_sided=False
    )

    if has_dec1 and len(work_pts) >= 2:
        tangent = [work_pts[0][0] - work_pts[1][0], work_pts[0][1] - work_pts[1][1]]
        body = _place_and_union(body, ec1, width, work_pts[0], tangent)

    if has_dec2 and len(work_pts) >= 2:
        tangent = [work_pts[-1][0] - work_pts[-2][0], work_pts[-1][1] - work_pts[-2][1]]
        body = _place_and_union(body, ec2, width, work_pts[-1], tangent)

    return _shapely_to_path2d(body, work_pts)


@builds_with("csg")
def dashed_stroke_2d(
    path: "PathLike",
    dashpat: Sequence[float] | None = None,
    closed: bool | None = None,
    fit: bool = True,
    mindash: float = 0.5,
) -> Region:
    """2-D dashed stroke: split the path into dash segments, buffer each.

    Args:
        path: The path to draw.
        dashpat: The dash pattern, as alternating on and off lengths.
        closed: Join the last point back to the first.
        fit: Stretch the pattern so a whole number of dashes fits the path.
        mindash: Shortest dash to keep; anything shorter is dropped.

    Returns:
        A :class:`Region` of dash-polygon outlines.

    """
    from pybosl2.regions import Region

    dpat = list(dashpat) if dashpat else [3.0, 3.0]
    if len(dpat) % 2 == 1:
        dpat = dpat + [0.0]

    pts = [list(map(float, p)) for p in path]
    if not (len(pts) >= 2):
        raise Bosl2ValueError("dashed_stroke(): need at least 2 points.")
    is_closed = _ensure_closed(pts, closed, getattr(path, "closed", False))
    raw = pts + [pts[0]] if is_closed else pts
    cuts = _dash_cuts(raw, dpat, is_closed, fit, mindash)

    if not cuts:
        return Region([])

    segments = _cut_path(raw, cuts, is_closed)
    half = 1.0  # stroke width — caller applies via Region

    polygons: list[_shapely.Polygon] = []
    for seg in segments:
        if len(seg) < 2:
            continue
        coords = [(float(p[0]), float(p[1])) for p in seg]
        line = LineString(coords)
        poly = line.buffer(half, cap_style="flat", join_style="round")
        if isinstance(poly, _shapely.Polygon) and not poly.is_empty:
            polygons.append(poly)

    if not polygons:
        return Region([])
    from shapely.ops import unary_union

    merged = unary_union(polygons)
    return Region(merged)


def _dash_cuts(
    raw: list[list[float]],
    dpat: list[float],
    closed: bool,
    fit: bool,
    mindash: float,  # noqa: ARG001
) -> list[float]:
    """Compute cut distances along the path for dash pattern."""
    plen = _path_length(raw)
    dlen = sum(dpat)
    if dlen < 1e-12:
        return []
    doff = list(np.cumsum(np.array(dpat, dtype=float)))
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
    return sorted(set(cuts))


def _path_length(pts: list[list[float]]) -> float:
    total = 0.0
    for i in range(len(pts) - 1):
        total += float(np.linalg.norm(np.asarray(pts[i + 1]) - np.asarray(pts[i])))
    return total


def _cut_path(
    pts: list[list[float]],
    cuts: list[float],
    closed: bool,  # noqa: ARG001
) -> list[list[list[float]]]:
    """Split a path at cut distances. Returns pairs of points as dash segments."""
    if not cuts:
        return [pts]

    seg_lengths = []
    for i in range(len(pts) - 1):
        seg_lengths.append(float(np.linalg.norm(np.asarray(pts[i + 1]) - np.asarray(pts[i]))))

    total = 0.0
    cut_starts = [0.0]
    for seg in seg_lengths:
        total += seg
        cut_starts.append(total)

    dashes: list[list[list[float]]] = []
    for ci in range(0, len(cuts) - 1, 2):
        if cuts[ci] >= total - 1e-9:
            break
        c1 = cuts[ci]
        c2 = cuts[min(ci + 1, len(cuts) - 1)]
        dash: list[list[float]] = [_point_at(pts, seg_lengths, cut_starts, c1)]
        dash.append(_point_at(pts, seg_lengths, cut_starts, c2))
        dashes.append(dash)
    return dashes


def _point_at(
    pts: list[list[float]],
    seg_lengths: list[float],
    cut_starts: list[float],
    dist: float,
) -> list[float]:
    """Find the point at distance dist along the path."""
    for i, seg_len in enumerate(seg_lengths):
        seg_start = cut_starts[i]
        seg_end = cut_starts[i + 1]
        if seg_start <= dist <= seg_end:
            t = (dist - seg_start) / seg_len if seg_len > 0 else 0
            a = np.asarray(pts[i], dtype=float)
            b = np.asarray(pts[i + 1], dtype=float)
            return (a + (b - a) * t).tolist()  # type: ignore[no-any-return]
    return list(pts[-1])
