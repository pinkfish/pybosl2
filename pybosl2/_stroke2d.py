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
from typing import TYPE_CHECKING, Any

import numpy as np
import shapely as _shapely
from shapely.geometry import LineString

from pybosl2.caps import CapSpec, CapType, _normalize_one

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pybosl2.path2d import Path2D
    from pybosl2.regions import Region


def _ensure_closed(pts: Sequence[Sequence[float]], closed: bool | None, path_closed: bool) -> bool:
    if closed is not None:
        return closed
    if len(pts) < 2:
        return False
    return path_closed


def _cap_style(cap: CapSpec) -> str:
    if cap.cap_type == CapType.ROUND:
        return "round"
    if cap.cap_type == CapType.SQUARE:
        return "square"
    return "flat"  # BUTT, NONE, etc → flat


def stroke_2d(
    path: Any,
    width: float = 1,
    closed: bool | None = None,
    endcap1: CapType | CapSpec = CapType.ROUND,
    endcap2: CapType | CapSpec = CapType.ROUND,  # noqa: ARG001
    joints: CapType | CapSpec = CapType.ROUND,  # noqa: ARG001
) -> Path2D:
    """2-D stroke: buffer the polyline into a polygon outline.

    Returns:
        A :class:`Path2D` of the stroked polygon outline.
    """
    from pybosl2.path2d import Path2D

    pts = [list(map(float, p)) for p in path]
    assert len(pts) >= 2, "stroke(): need at least 2 points."
    is_closed = _ensure_closed(pts, closed, getattr(path, "closed", False))
    ec1 = endcap1 if isinstance(endcap1, CapSpec) else _normalize_one(endcap1)
    half = width / 2

    coords = [(float(p[0]), float(p[1])) for p in pts]
    if is_closed:
        ring = _shapely.LinearRing(coords)
        poly = ring.buffer(half, join_style="round")
        if isinstance(poly, _shapely.Polygon) and not poly.is_empty:
            return Path2D([list(c) for c in poly.exterior.coords], closed=True)
        return Path2D(pts, closed=True)

    line = LineString(coords)
    cs = _cap_style(ec1)
    poly = line.buffer(half, cap_style=cs, join_style="round", single_sided=False)
    if isinstance(poly, _shapely.Polygon) and not poly.is_empty:
        return Path2D([list(c) for c in poly.exterior.coords], closed=True)
    return Path2D(pts, closed=False)


def dashed_stroke_2d(
    path: Any,
    dashpat: Sequence[float] | None = None,
    closed: bool | None = None,
    fit: bool = True,
    mindash: float = 0.5,
) -> Region:
    """2-D dashed stroke: split the path into dash segments, buffer each.

    Returns:
        A :class:`Region` of dash-polygon outlines.
    """
    from pybosl2.regions import Region

    dpat = list(dashpat) if dashpat else [3.0, 3.0]
    if len(dpat) % 2 == 1:
        dpat = dpat + [0.0]

    pts = [list(map(float, p)) for p in path]
    assert len(pts) >= 2, "dashed_stroke(): need at least 2 points."
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
