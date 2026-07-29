# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/rounding.py
#    Pure-Python port of the path-rounding core of BOSL2's rounding.scad: :func:`round_corners`
#    (round every corner of a path -- ``"circle"``, ``"smooth"`` or ``"chamfer"``, sized by
#    ``radius``/``cut``/``joint``/``width``) and :func:`smooth_path` (fit a continuous-curvature
#    bezier through a path). Both work on 2-D and 3-D paths and are exposed as methods on
#    :class:`~pybosl2.paths.Path2D` and :class:`~pybosl2.paths.Path3D`.
#
#    ``round_corners`` and ``smooth_path`` are pinned point-for-point to the real BOSL2 output in
#    tests/test_bosl2_reorient.py. The smooth/chamfer corners reuse the toolkit's
#    :class:`~pybosl2.beziers.Bezier`; the circle corners reuse :func:`~pybosl2.shapes2d.arc` (2-D) or a
#    slerp arc (3-D).
#
#

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Sequence, cast

if TYPE_CHECKING:
    from shapely.geometry import MultiPolygon

    from pybosl2.paths import Path2D, Path3D

import numpy as np

from pybosl2._helpers import is_num
from pybosl2.caps import CapType
from pybosl2.comparisons import approx

# Late imports to avoid circular dependencies
from pybosl2.vectors import unit

__all__ = [
    "Roundable",
]


# ---------------------------------------------------------------------------
# Section: corner builders
# ---------------------------------------------------------------------------


def _vector_angle3(a, b, c) -> float:
    """The angle in degrees at vertex *b* of the corner a-b-c (2-D or 3-D)."""
    va = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    vc = np.asarray(c, dtype=float) - np.asarray(b, dtype=float)
    cosv = float(np.dot(va, vc)) / (float(np.linalg.norm(va)) * float(np.linalg.norm(vc)))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosv))))


def _smooth_bez_fill(points, k):
    p0, p1, p2 = (np.asarray(p, dtype=float) for p in points)
    return [p0, p1 + (p0 - p1) * k, p1, p1 + (p2 - p1) * k, p2]


def _bezcorner(points, parm, fn=0, fs=2.0):
    """A continuous-curvature (bezier) corner (BOSL2 _bezcorner())."""
    from pybosl2.beziers import Bezier

    if isinstance(parm, (list, tuple, np.ndarray)):
        d, k = float(parm[0]), float(parm[1])
        p1 = np.asarray(points[1], dtype=float)
        prev = unit(np.asarray(points[0], dtype=float) - p1)
        nxt = unit(np.asarray(points[2], dtype=float) - p1)
        ctrl = [p1 + d * prev, p1 + k * d * prev, p1, p1 + k * d * nxt, p1 + d * nxt]
    else:
        ctrl = _smooth_bez_fill(points, float(parm))
    bez = Bezier([[float(c) for c in p] for p in ctrl])
    sides = max(3, fn if fn and fn > 0 else math.ceil(bez.arc_length() / fs))
    return [[float(c) for c in p] for p in bez.curve(sides, endpoint=True)]


def _chamfcorner(points, parm):
    """A straight chamfer across a corner (BOSL2 _chamfcorner())."""
    diameter = float(parm[0])
    p1 = np.asarray(points[1], dtype=float)
    prev = unit(np.asarray(points[0], dtype=float) - p1)
    nxt = unit(np.asarray(points[2], dtype=float) - p1)
    return [list(p1 + prev * diameter), list(p1 + nxt * diameter)]


def _arc3d(center, start, end, n):
    """
    *n* points along the short arc from *start* to *end* about *center* (slerp, any dimension).
    """
    c = np.asarray(center, dtype=float)
    v0, v1 = np.asarray(start, dtype=float) - c, np.asarray(end, dtype=float) - c
    angle = math.acos(
        max(
            -1.0,
            min(1.0, float(np.dot(v0, v1)) / (np.linalg.norm(v0) * np.linalg.norm(v1))),
        )
    )
    if angle < 1e-12:
        return [
            list(np.asarray(start, dtype=float)),
            list(np.asarray(end, dtype=float)),
        ]
    s = math.sin(angle)
    return [list(c + (math.sin((1 - t) * angle) * v0 + math.sin(t * angle) * v1) / s) for t in np.linspace(0, 1, n)]


def _circlecorner(points, parm, fn=None, fa=None, fs=None):
    """A circular-arc corner (BOSL2 _circlecorner())."""
    from pybosl2.shapes2d import _frag_count, arc

    angle = _vector_angle3(points[0], points[1], points[2]) / 2
    d, radius = float(parm[0]), float(parm[1])
    p1 = np.asarray(points[1], dtype=float)
    prev = unit(np.asarray(points[0], dtype=float) - p1)
    nxt = unit(np.asarray(points[2], dtype=float) - p1)
    start, end = p1 + prev * d, p1 + nxt * d
    if approx(angle, 90):
        return [list(start), list(end)]
    center = radius / math.sin(math.radians(angle)) * unit(prev + nxt) + p1
    sides = max(3, math.ceil((90 - angle) / 180 * _frag_count(radius, fn, fa, fs)))
    if len(points[1]) == 2:
        return [
            [float(c) for c in p]
            for p in arc(
                sides,
                center=[float(center[0]), float(center[1])],
                points=[
                    [float(start[0]), float(start[1])],
                    [float(end[0]), float(end[1])],
                ],
            )
        ]
    return _arc3d(center, start, end, sides)


# ---------------------------------------------------------------------------
# Section: round_corners
# ---------------------------------------------------------------------------


def _round_corners(
    path,
    method: str = "circle",
    radius: float | None = None,
    cut=None,
    joint=None,
    width: float | None = None,
    curvature: float | None = None,
    closed: bool = True,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    **kwargs,
):
    """Round every corner of *path* (BOSL2 round_corners()).

    *method* is ``"circle"`` (a constant-radius arc), ``"smooth"`` (a continuous-curvature bezier),
    or ``"chamfer"`` (a straight bevel). Size the roundover with exactly one of *radius*/*radius* (circle
    only), *cut* (depth toward the corner), *joint* (distance back from the corner along each edge),
    or *width* (chamfer only) -- each a scalar or a per-corner list. *curvature* (smooth only, 0..1) tunes
    how tight the curvature match is. Works on 2-D and 3-D paths.

    Returns:
        A :class:`~pybosl2.paths.Path2D` (2-D) or :class:`~pybosl2.paths.Path3D` (3-D).

    Examples:
        A rounded, smoothed and chamfered square (three copies):

        .. pythonscad-example::

            sq = [[0, 0], [40, 0], [40, 40], [0, 40]]
            round_corners(sq, method="smooth", joint=10).polygon().linear_extrude(height=4).show()
    """
    from pybosl2.paths import Path2D, Path3D

    k = curvature if curvature is not None else kwargs.get("k")

    assert method in (
        "circle",
        "smooth",
        "chamfer",
    ), 'method must be "circle", "smooth" or "chamfer".'
    given = [
        (m, v)
        for m, v in (
            ("radius", radius),
            ("cut", cut),
            ("joint", joint),
            ("width", width),
        )
        if v is not None
    ]
    assert len(given) == 1, "Must give exactly one of radius, cut, joint or width."
    measure, size = given[0]
    pts = [[float(c) for c in p] for p in path]
    sides = len(pts)
    assert sides > 2, f"Path2D has length {sides}. Length must be 3 or more."
    assert method == "circle" or measure != "radius", 'radius is allowed only with method="circle".'
    assert method == "chamfer" or measure != "width", 'width is allowed only with method="chamfer".'

    if is_num(size):
        parm = [float(size)] * sides
    elif isinstance(size, (list, tuple, np.ndarray)):
        parm = [0.0] + [float(v) for v in size] + [0.0] if len(size) < sides else [float(v) for v in size]
    if k is None:
        kv = [0.5] * sides
    elif is_num(k):
        assert method == "smooth", 'k is only allowed with method="smooth".'
        kv = [float(k)] * sides
    elif isinstance(k, (list, tuple, np.ndarray)):
        assert method == "smooth", 'k is only allowed with method="smooth".'
        kv = ([0.0] + [float(v) for v in k] + [0.0]) if len(k) < sides else [float(v) for v in k]
    assert all(v >= 0 for v in parm), f"{measure} must be nonnegative."
    assert all(0 <= v <= 1 for v in kv), "k must be in [0, 1]."

    # dk[i] = [joint distance, shape param] per corner (chamfer has just [distance])
    dk = []
    for i in range(sides):
        p0, p1, p2 = pts[(i - 1) % sides], pts[i], pts[(i + 1) % sides]
        if (not closed and (i == 0 or i == sides - 1)) or parm[i] == 0:
            dk.append([0.0])
            continue
        assert not (approx(p0, p1) or approx(p1, p2)), f"Repeated point in path at index {i} with nonzero rounding."
        angle = _vector_angle3(p0, p1, p2) / 2
        assert not approx(angle, 0), f"Path2D turns back on itself at index {i} with nonzero rounding."
        ar = math.radians(angle)
        if method == "chamfer":
            dk.append(
                [
                    (
                        parm[i]
                        if measure == "joint"
                        else (parm[i] / math.cos(ar) if measure == "cut" else parm[i] / math.sin(ar) / 2)
                    )
                ]
            )  # width
        elif method == "smooth":
            dk.append(
                [parm[i], kv[i]] if measure == "joint" else [8 * parm[i] / math.cos(ar) / (1 + 4 * kv[i]), kv[i]]
            )  # cut
        elif measure == "radius":
            dk.append([parm[i] / math.tan(ar), parm[i]])
        elif measure == "joint":
            dk.append([parm[i], parm[i] * math.tan(ar)])
        else:  # circle + cut
            if approx(angle, 90):
                dk.append([math.inf])
            else:
                cr = parm[i] / (1 / math.sin(ar) - 1)
                dk.append([cr / math.tan(ar), cr])

    lengths = [
        float(np.linalg.norm(np.asarray(pts[i % sides]) - np.asarray(pts[(i - 1) % sides]))) for i in range(sides + 1)
    ]
    scale = []
    for i in range(sides):
        if closed or (i != 0 and i != sides - 1):
            a = lengths[i] / (dk[(i - 1) % sides][0] + dk[i][0]) if (dk[(i - 1) % sides][0] + dk[i][0]) else math.inf
            b = (
                lengths[i + 1] / (dk[i][0] + dk[(i + 1) % sides][0])
                if (dk[i][0] + dk[(i + 1) % sides][0])
                else math.inf
            )
            scale.append(min(a, b))
    assert not scale or min(scale) >= 1 - 1e-9, "Roundovers are too big for the path (they overlap); reduce the sizes."

    out = []
    for i in range(sides):
        corner = [pts[(i - 1) % sides], pts[i], pts[(i + 1) % sides]]
        if dk[i][0] == 0:
            out.append(pts[i])
        elif method == "smooth":
            out += _bezcorner(corner, dk[i], fn=fn or 0, fs=fs or 2.0)
        elif method == "chamfer":
            out += _chamfcorner(corner, dk[i])
        else:
            out += _circlecorner(corner, dk[i], fn=fn, fa=fa, fs=fs)

    result = _dedup(out)
    dim = len(result[0])
    return (Path3D if dim == 3 else Path2D)(result, closed=closed)


def _dedup(pts, eps=1e-9):
    out = []
    for p in pts:
        if not out or not approx(out[-1], p, eps):
            out.append([float(c) for c in p])
    if len(out) > 1 and approx(out[0], out[-1], eps):
        out.pop()
    return out


# ---------------------------------------------------------------------------
# Section: smooth_path
# ---------------------------------------------------------------------------


def _smooth_path(
    path,
    tangents=None,
    size=None,
    relsize=None,
    splinesteps: int = 10,
    uniform: bool = False,
    closed: bool = False,
):
    """Fit a smooth continuous-curvature curve through *path* (BOSL2 smooth_path(), method="edges").

    Runs a cubic bezier through every point of *path*, matching the path's tangents, and samples it
    with *splinesteps* points per segment. *size* / *relsize* bound how far the curve may bow away
    from the straight path (relsize is a fraction of each segment, default 0.1). The BOSL2
    ``method="corners"`` variant is not ported.

    Returns:
        A :class:`~pybosl2.paths.Path2D` (2-D) or :class:`~pybosl2.paths.Path3D` (3-D).

    Examples:
        A wiggly control path smoothed into a flowing curve:

        .. pythonscad-example::

            pts = [[0, 0], [10, 30], [30, -10], [50, 20], [70, 0]]
            smooth_path(pts, relsize=0.4).stroke(width=2).linear_extrude(height=3).show()
    """
    from pybosl2.beziers import create_bezier
    from pybosl2.paths import Path2D, Path3D

    bez = create_bezier(
        path,
        closed=closed,
        tangents=tangents,
        size=size,
        relsize=relsize,
        uniform=uniform,
    )
    smoothed = [[float(c) for c in p] for p in bez.path_curve(splinesteps=splinesteps)]
    if closed and len(smoothed) > 1 and approx(smoothed[0], smoothed[-1]):
        smoothed = smoothed[:-1]
    dim = len(smoothed[0])
    return (Path3D if dim == 3 else Path2D)(smoothed, closed=closed)


# ---------------------------------------------------------------------------
# Section: Roundable mixin
# ---------------------------------------------------------------------------


class Roundable:
    """Mixin adding the rounding.scad path operators as methods on :class:`~pybosl2.paths.Path2D` and
    :class:`~pybosl2.paths.Path3D`."""

    def round_corners(  # type: ignore[misc]
        self: Path2D | Path3D,
        radius: float | None = None,
        method: str = "circle",
        cut=None,
        joint=None,
        width: float | None = None,
        curvature: float | None = None,
        closed: bool | None = None,
        **kwargs,
    ):
        """Round every corner of this path (see :func:`round_corners`)."""
        curv = curvature if curvature is not None else kwargs.get("k")
        return _round_corners(
            self,
            method=method,
            radius=radius,
            cut=cut,
            joint=joint,
            width=width,
            curvature=curv,
            closed=self.closed if closed is None else closed,  # type: ignore[attr-defined]
            **kwargs,
        )

    def smooth_path(  # type: ignore[misc]
        self: Path2D | Path3D,
        tangents=None,
        size=None,
        relsize=None,
        splinesteps: int = 10,
        uniform: bool = False,
        closed: bool | None = None,
    ):
        """Fit a smooth continuous-curvature curve through this path (see :func:`smooth_path`)."""
        return _smooth_path(
            self,
            tangents=tangents,
            size=size,
            relsize=relsize,
            splinesteps=splinesteps,
            uniform=uniform,
            closed=self.closed if closed is None else closed,  # type: ignore[attr-defined]
        )

    def offset_stroke(
        self,
        width: float = 1.0,
        closed: bool | None = None,
        endcap: CapType = CapType.ROUND,
        joint: CapType = CapType.ROUND,
    ):
        """Offset this 2-D path to create a thickened outline Region (BOSL2 offset_stroke())."""
        return _offset_stroke(
            self,
            width=width,
            closed=self.closed if closed is None else closed,  # type: ignore[attr-defined]
            endcap=endcap,
            joint=joint,
        )

    def offset_sweep(
        self,
        height: float,
        bottom=None,
        top=None,
        steps: int = 16,
        caps=CapType.BUTT,
        style: str = "min_edge",
    ):
        """Offset sweep/extrusion of this 2-D shape (BOSL2 offset_sweep())."""
        from pybosl2.skin import _offset_sweep as _os

        return _os(
            cast("Sequence[Sequence[float]]", self),
            height=height,
            bottom=bottom,
            top=top,
            steps=steps,
            caps=caps,
            style=style,
        )

    def convex_offset_extrude(
        self,
        height: float,
        bottom=None,
        top=None,
        steps: int = 16,
        caps=CapType.BUTT,
        style: str = "min_edge",
    ):
        """Offset sweep/extrusion of this 2-D shape (BOSL2 convex_offset_extrude())."""
        from pybosl2.skin import _convex_offset_extrude as _coe

        return _coe(
            cast("Sequence[Sequence[float]]", self),
            height=height,
            bottom=bottom,
            top=top,
            steps=steps,
            caps=caps,
            style=style,
        )

    def rounded_prism(
        self,
        top=None,
        height: float | None = None,
        joint_top=None,
        joint_bottom=None,
        joint_sides=None,
        curvature_sides=None,
        steps: int = 16,
        caps=CapType.BUTT,
        style: str = "min_edge",
        **kwargs,
    ):
        """Rounded prism between this path and a top path (BOSL2 rounded_prism())."""
        from pybosl2.skin import _rounded_prism as _rp

        j_bot = joint_bottom if joint_bottom is not None else kwargs.get("joint_bot")
        k_sides = curvature_sides if curvature_sides is not None else kwargs.get("k_sides")

        return _rp(
            cast("Sequence[Sequence[float]]", self),
            top=top,
            height=height,
            joint_top=joint_top,
            joint_bottom=j_bot,
            joint_sides=joint_sides,
            curvature_sides=k_sides,
            steps=steps,
            caps=caps,
            style=style,
            **kwargs,
        )

    def join_prism(
        self,
        height: float,
        fillet: float = 0.0,
        steps: int = 16,
        caps=CapType.BUTT,
        style: str = "min_edge",
    ):
        """Join this prism to a base plane with a filleted transition (BOSL2 join_prism())."""
        from pybosl2.skin import _join_prism as _jp

        return _jp(
            cast("Sequence[Sequence[float]]", self),
            height=height,
            fillet=fillet,
            steps=steps,
            caps=caps,
            style=style,
        )

    def prism_connector(
        self,
        length: float,
        fillet: float = 0.0,
        fillet1=None,
        fillet2=None,
        steps: int = 16,
        caps=CapType.BUTT,
        style: str = "min_edge",
    ):
        """Construct a filleted prism connecting two objects (BOSL2 prism_connector())."""
        from pybosl2.skin import _prism_connector as _pc

        return _pc(
            cast("Sequence[Sequence[float]]", self),
            length=length,
            fillet=fillet,
            fillet1=fillet1,
            fillet2=fillet2,
            steps=steps,
            caps=caps,
            style=style,
        )

    def attach_prism(
        self,
        length: float,
        fillet: float = 0.0,
        rounding: float = 0.0,
        steps: int = 16,
        caps=CapType.BUTT,
        style: str = "min_edge",
    ):
        """Attach a filleted prism with optional rounded end (BOSL2 attach_prism())."""
        from pybosl2.skin import _attach_prism as _ap

        return _ap(
            cast("Sequence[Sequence[float]]", self),
            length=length,
            fillet=fillet,
            rounding=rounding,
            steps=steps,
            caps=caps,
            style=style,
        )

    def bent_cutout_mask(
        self,
        radius: float,
        thickness: float,
        style: str = "min_edge",
    ):
        """Create a mask to generate a round-edged cutout in a cylindrical shell (BOSL2 bent_cutout_mask())."""
        from pybosl2.skin import _bent_cutout_mask as _bcm

        return _bcm(
            radius=radius,
            thickness=thickness,
            path=cast("Sequence[Sequence[float]]", self),
            style=style,
        )

    def path_join(
        self,
        other_paths,
        radius=None,
        cut=None,
        joint=None,
        curvature=None,
        relocate=True,
        closed: bool | None = None,
        **kwargs,
    ):
        """Join multiple paths to this path end-to-end (see :func:`path_join`)."""
        curv = curvature if curvature is not None else kwargs.get("k")
        return _path_join(
            [self] + list(other_paths),
            radius=radius,
            cut=cut,
            joint=joint,
            curvature=curv,
            relocate=relocate,
            closed=self.closed if closed is None else closed,  # type: ignore[attr-defined]
            **kwargs,
        )


def _path_join(
    paths: Sequence[Sequence[Sequence[float]]],
    radius: float | list[float] | None = None,
    cut: float | list[float] | None = None,
    joint: float | list[float] | None = None,
    curvature: float | list[float] | None = None,
    relocate: bool = True,
    closed: bool = False,
    **kwargs,
) -> Any:
    """Join multiple paths end-to-end with optional rounding at the joint connections (BOSL2 path_join()).

    Consecutive endpoints are merged if they are within a tolerance (and *relocate* is True).
    The joints between adjacent paths are rounded using the same options as
    :func:`round_corners`.

    Args:
        paths:     A sequence of 2-D or 3-D paths (each a sequence of points).
        radius:    Rounding radius at joints (mutually exclusive with cut/joint).
        cut:       Cut parameter for joint rounding.
        joint:     Joint parameter for joint rounding.
        curvature: Continuous curvature (smooth) parameter for joints.
        relocate:  Merge consecutive endpoints if they are close (default True).
        closed:    Close the resulting joined path (default False).

    Returns:
        A :class:`~pybosl2.paths.Path2D` or :class:`~pybosl2.paths.Path3D` depending on the input dimensions.
    """
    from pybosl2.paths import Path2D as _Path
    from pybosl2.paths import Path3D as _Path3D

    k = curvature if curvature is not None else kwargs.get("k")

    if not paths:
        return _Path([])

    # Concatenate paths
    pts = [list(map(float, pt)) for pt in paths[0]]
    joint_indices = []

    for p in paths[1:]:
        p_pts = [list(map(float, pt)) for pt in p]
        if not p_pts:
            continue
        if relocate and np.allclose(pts[-1], p_pts[0], atol=1e-9):
            joint_indices.append(len(pts) - 1)
            pts.extend(p_pts[1:])
        else:
            joint_indices.append(len(pts) - 1)
            pts.extend(p_pts)

    if closed and len(pts) > 2:
        if relocate and np.allclose(pts[-1], pts[0], atol=1e-9):
            pts.pop()
        joint_indices.append(len(pts) - 1)

    # Determine dimension
    dim = len(pts[0])
    cls = _Path3D if dim == 3 else _Path

    # If no rounding requested, return the joined path as-is
    given = [
        (m, v)
        for m, v in (
            ("radius", radius),
            ("cut", cut),
            ("joint", joint),
        )
        if v is not None
    ]
    if not given:
        return cls(pts, closed=closed)

    measure, size = given[0]
    # Build a per-corner size list
    sides = len(pts)
    size_list = [0.0] * sides

    # Map input size to joint indices
    if isinstance(size, (list, tuple, np.ndarray)):
        # Assign elements sequentially to the joints
        for i, idx in enumerate(joint_indices):
            if i < len(size):
                size_list[idx] = float(size[i])
    else:
        for idx in joint_indices:
            size_list[idx] = float(size)

    # Do the same for k if given
    k_list = None
    if k is not None:
        k_list = [0.5] * sides
        if isinstance(k, (list, tuple, np.ndarray)):
            for i, idx in enumerate(joint_indices):
                if i < len(k):
                    k_list[idx] = float(k[i])
        else:
            for idx in joint_indices:
                k_list[idx] = float(k)

    # Call round_corners with the per-corner sizes
    kwargs = {measure: size_list, "closed": closed}
    if k_list is not None:
        kwargs["k"] = k_list

    return _round_corners(pts, **kwargs)


def _from_shapely(geom: "MultiPolygon") -> list[Path2D]:
    """Extract paths (exterior + holes) from a shapely geometry.

    Handles ``Polygon`` and ``MultiPolygon`` by taking the largest polygon.

    Args:
        geom: A ``shapely.Polygon`` or ``shapely.MultiPolygon``.

    Returns:
        A list of :class:`~pybosl2.paths.Path2D` objects: outer ring, then holes.
    """
    from shapely.geometry import MultiPolygon, Polygon

    from pybosl2.paths import Path2D as _Path

    if geom.is_empty:
        return []
    if isinstance(geom, MultiPolygon):
        geom = max(geom.geoms, key=lambda g: g.area)
    if not isinstance(geom, Polygon):
        return []
    paths: list[_Path] = []
    exterior = list(geom.exterior.coords)[:-1]
    paths.append(_Path([[float(x), float(y)] for x, y in exterior]))
    for interior in geom.interiors:
        ring = list(interior.coords)[:-1]
        paths.append(_Path([[float(x), float(y)] for x, y in ring]))
    return paths


def _offset_stroke(
    path,
    width: float = 1.0,
    closed: bool = False,
    endcap: CapType = CapType.ROUND,
    joint: CapType = CapType.ROUND,
) -> Any:
    """Offset a 2-D path by *width* to create a thickened outline Region (BOSL2 offset_stroke()).

    If *closed* is True, the path is treated as a closed loop.
    When :mod:`shapely` is installed, returns a :class:`Region` containing the coordinates
    of the outline. Without shapely, falls back to PythonSCAD geometry (CSG shape).
    """
    from shapely.geometry import LineString

    from pybosl2.paths import Path2D as _Path
    from pybosl2.regions import Region

    # Coerce to Path2D
    p = path if isinstance(path, _Path) else _Path(path)

    pts = [(float(pt[0]), float(pt[1])) for pt in p]
    if not pts:
        return Region([])

    # Map endcap/join style to shapely integer constants
    cap_map: dict[CapType, int] = {CapType.ROUND: 1, CapType.BUTT: 2, CapType.SQUARE: 3, CapType.FLAT: 2}
    join_map: dict[CapType, int] = {CapType.ROUND: 1, CapType.SQUARE: 3}

    c_style = cap_map.get(endcap, 1)
    j_style = join_map.get(joint, 1)

    # For a closed loop, append first point to ensure it's closed
    line = LineString(pts + [pts[0]]) if closed and len(pts) > 1 and pts[0] != pts[-1] else LineString(pts)

    geom = line.buffer(width / 2.0, cap_style=c_style, join_style=j_style)
    return Region(_from_shapely(geom))
