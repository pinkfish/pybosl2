# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/masking.py
#    Pure-Python port of BOSL2's edge/corner/face profile masking system.
#    Cuts rounded/chamfered profiles along selected edges, corners, or whole
#    faces of a cuboid.  Only cuboid parents are supported; edge and corner
#    positioning is derived from first principles using the same offset vectors
#    as cuboid()'s own rounding.
#
# FileSummary: Cut rounded edge/corner/face profiles into a cuboid (BOSL2 masks2d/masks3d).
# DocCategory: Foundational
# FileGroup: BOSL2

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from pybosl2._edges_lang import CORNER_OFFSETS
from pybosl2._native import native
from pybosl2.points import Point, Vector

if TYPE_CHECKING:
    from pybosl2._edges_lang import CornerPlane, EdgePlane

if TYPE_CHECKING:
    from pybosl2.path2d import Path2D
    from pybosl2.shapes2d import Bosl2Shape2D
    from pybosl2.shapes3d import Bosl2Solid

from ._edges_lang import EDGE_OFFSETS, _edges
from .constants import CENTER
from .shapes2d import _frag_count, _polar_to_xy
from .shapes3d import _anchor_offset_box3, _quantup

_ocube = native("cube")
_opolygon = native("polygon")
_osphere = native("sphere")


def mask2d_roundover(
    radius: float | None = None,
    inset: float | tuple[float, float] = 0.0,
    excess: float = 0.01,
    diameter: float | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> "Path2D":
    """The 2-D L-shaped cutter cross-section for rounding a 90-degree edge/corner to radius *radius*.

    Args:
        radius: Rounding radius.
        inset: Scalar or ``(x, y)`` inset of the rounding center from the corner (default 0).
        excess: Amount the flat sides extend past the origin, for a clean boolean cut (default 0.01).
        diameter: Rounding diameter (alternative to *radius*).
        fn/fa/fs: Arc smoothness overrides.

    Returns:
        A :class:`~pybosl2.path2d.Path2D` of the 2-D cutter cross-section.
    """
    from pybosl2.path2d import Path2D

    if radius is None:
        assert diameter is not None, "mask2d_roundover(): must give radius or diameter"
        radius = diameter / 2
    rad = float(radius)
    inset_x, inset_y = inset if isinstance(inset, tuple) else (float(inset), float(inset))
    steps = max(1, int(_quantup(_frag_count(rad, fn, fa, fs), 4) // 4))
    step = 90.0 / steps
    path = [
        [rad + inset_x, -excess],
        [-excess, -excess],
        [-excess, rad + inset_y],
    ]
    for i in range(steps + 1):
        p = _polar_to_xy(rad, 180 + i * step)
        path.append([rad + inset_x + p[0], rad + inset_y + p[1]])
    return Path2D(path, closed=True)


def rounding_edge_mask(
    length: float | None = None,
    radius: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    height: float | None = None,
    excess: float = 0.1,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> "Bosl2Solid":
    """A standalone 3-D edge-rounding cutter of length *length*, for manual positioning.

    Args:
        length/height: Length of the cutter along its axis (default 1).
        radius: Rounding radius (both ends).
        radius1/radius2: Rounding radius at each end, for a tapered cutter.
        diameter/diameter1/diameter2: Rounding diameter (both ends) / each end.
        excess: Amount the flat sides extend past the origin (default 0.1).
        fn/fa/fs: Arc smoothness overrides.

    Returns:
        A :class:`~pybosl2.shapes3d.Bosl2Solid` cutter.
    """
    length = length if length is not None else (height if height is not None else 1.0)
    rad1 = (
        radius1
        if radius1 is not None
        else (
            radius
            if radius is not None
            else (diameter1 / 2 if diameter1 is not None else (diameter / 2 if diameter is not None else 1.0))
        )
    )
    rad2 = (
        radius2
        if radius2 is not None
        else (
            radius
            if radius is not None
            else (diameter2 / 2 if diameter2 is not None else (diameter / 2 if diameter is not None else 1.0))
        )
    )
    if rad1 < rad2:
        cross = mask2d_roundover(rad2, excess=excess, fn=fn, fa=fa, fs=fs)
        shape = _opolygon(cross).linear_extrude(height=length, center=True, scale=rad1 / rad2)
        return shape.rotate(180, [1, 0, 0])  # type: ignore[no-any-return]
    cross = mask2d_roundover(rad1, excess=excess, fn=fn, fa=fa, fs=fs)
    scale = rad2 / rad1 if rad1 else 1.0
    return _opolygon(cross).linear_extrude(height=length, center=True, scale=scale)  # type: ignore[no-any-return]


def chamfer_edge_mask(length: float = 1.0, chamfer: float = 1.0, excess: float = 0.1) -> "Bosl2Solid":
    """A standalone 3-D edge-chamfer cutter of length *length*.

    A diamond bar (square prism rotated 45°) centered on its own Z axis.

    Args:
        length: Length of the cutter along its axis (default 1).
        chamfer: Chamfer size (the diamond's half-diagonal along each axis, default 1).
        excess: Extra length past *length* so the cut clears the surface (default 0.1).

    Returns:
        A :class:`~pybosl2.shapes3d.Bosl2Solid` cutter.
    """
    diamond = [[chamfer, 0.0], [0.0, chamfer], [-chamfer, 0.0], [0.0, -chamfer]]
    return _opolygon(diamond).linear_extrude(height=length + excess, center=True)  # type: ignore[no-any-return]


def _pick_axes(vec: Vector) -> tuple[int, int, int, float, float]:
    """For an edge vector (one axis 0, two axes ±1), return ``(run_axis, a1, a2, s1, s2)``."""
    run_axis = next(i for i in range(3) if vec[i] == 0)
    nz = [i for i in range(3) if vec[i] != 0]
    a1, a2 = nz
    return run_axis, a1, a2, float(vec[a1]), float(vec[a2])


def _orient_mask_along_edge(
    shape: "Bosl2Solid | Bosl2Shape2D",
    size: tuple[float, float, float],
    vec: Vector,
) -> "Bosl2Solid":
    """Reorient an already-built edge cutter onto the cuboid edge given by *vec*."""
    run_axis, a1, a2, s1, s2 = _pick_axes(vec)
    lx = [0.0, 0.0, 0.0]
    lx[a1] = -s1
    ly = [0.0, 0.0, 0.0]
    ly[a2] = -s2
    lz = [0.0, 0.0, 0.0]
    lz[run_axis] = 1.0
    m = [
        [lx[0], ly[0], lz[0], 0.0],
        [lx[1], ly[1], lz[1], 0.0],
        [lx[2], ly[2], lz[2], 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    center = [0.0, 0.0, 0.0]
    center[a1] = s1 * size[a1] / 2
    center[a2] = s2 * size[a2] / 2
    return shape.multmatrix(m).translate(center)  # type: ignore[return-value]


def _extrude_mask_along_edge(
    mask_path: "Path2D",
    length: float,
    size: tuple[float, float, float],
    vec: Vector,
) -> "Bosl2Solid":
    shape = _opolygon(mask_path).linear_extrude(height=length, center=True)
    return _orient_mask_along_edge(shape, size, vec)


def edge_mask(
    body: "Bosl2Solid",
    edges: EdgePlane | str | list[int | str] = "ALL",
    except_edges: list[int | str] | None = None,
    children: "Bosl2Solid | None" = None,
    size: tuple[float, float, float] | None = None,
    anchor: Vector | Point = CENTER,
    center: Point | None = None,
) -> "Bosl2Solid":
    """Cut a 3-D edge cutter along each selected edge of the box-shaped *body*.

    Args:
        body: The box solid to cut.
        edges: Edges to mask — an :class:`EdgePlane`, a string, a vector, or a list thereof (default ``"ALL"``).
        except_edges: Edges to explicitly not mask.
        children: The pre-built 3-D edge cutter.
        size: The box's ``(x, y, z)`` size.
        anchor: The anchor *body* was built with (default ``CENTER``).
        center: The box center in body's current frame.
    """
    assert size is not None, "size= (the box's size) must be given"
    assert children is not None, "children= (the edge cutter) must be given"
    edge_set = _edges(edges, except_edges or [])
    cutter: "Bosl2Solid | None" = None
    for axis in range(3):
        for i in range(4):
            if edge_set[axis][i] > 0:
                piece = _orient_mask_along_edge(children, size, Vector(EDGE_OFFSETS[axis][i]))
                cutter = piece if cutter is None else (cutter | piece)
    if cutter is None:
        return body
    cutter = cutter.translate(center if center is not None else _anchor_offset_box3(size, anchor))  # type: ignore[arg-type]
    return body - cutter


def edge_profile(
    body: "Bosl2Solid",
    edges: EdgePlane | str | list[int | str] = "ALL",
    except_edges: list[int | str] | None = None,
    children: "Path2D | None" = None,
    size: tuple[float, float, float] | None = None,
    convexity: int = 10,
    anchor: Vector = CENTER,
    center: Point | None = None,
) -> "Bosl2Solid":
    """Cut a 2-D mask profile extruded along each selected edge of the box-shaped *body*.

    Args:
        body: The box solid to cut.
        edges: Edges to mask (default ``"ALL"``).
        except_edges: Edges to explicitly not mask.
        children: The 2-D mask cross-section :class:`~pybosl2.path2d.Path2D`.
        size: The box's ``(x, y, z)`` size.
        convexity: Accepted for signature compatibility; unused.
        anchor: The anchor *body* was built with (default ``CENTER``).
        center: The box center in body's current frame.
    """
    _ = convexity
    assert size is not None, "size= (the box's size) must be given"
    assert children is not None, "children= (the 2-D mask path) must be given"
    edge_set = _edges(edges, except_edges or [])
    cutter: "Bosl2Solid | None" = None
    for axis in range(3):
        for i in range(4):
            if edge_set[axis][i] > 0:
                vec = EDGE_OFFSETS[axis][i]
                length = size[axis] + 0.1
                piece = _extrude_mask_along_edge(children, length, size, Vector(vec))
                cutter = piece if cutter is None else (cutter | piece)
    if cutter is None:
        return body
    cutter = cutter.translate(center if center is not None else _anchor_offset_box3(size, anchor))  # type: ignore[arg-type]
    return body - cutter


def _corner_set(v: str | list[int]) -> list[int]:
    if isinstance(v, str):
        if v == "ALL":
            return [1] * 8
        if v == "NONE":
            return [0] * 8
        raise ValueError(f'{v} must be "ALL", "NONE", or a vector')
    arr = np.asarray(v, dtype=int)
    return [
        1 if arr[0] == 0 or arr[0] == c[0] and arr[1] == 0 or arr[1] == c[1] and arr[2] == 0 or arr[2] == c[2] else 0
        for c in CORNER_OFFSETS
    ]


def _corners(
    v: str | list[int] | list[str] | list[list[int]] | list[list[str]],
    except_: list | None = None,  # type: ignore[type-arg]
) -> list[int]:
    if except_ is None:
        except_ = []
    if isinstance(v, str) or (isinstance(v, list) and len(v) > 0 and not isinstance(v[0], list)):
        v = [v]  # type: ignore[assignment]
    if isinstance(except_, str) or (
        isinstance(except_, list) and len(except_) > 0 and not isinstance(except_[0], list)
    ):
        except_ = [except_]
    summed = [0] * 8
    for x in v:
        cs = _corner_set(x)  # type: ignore[arg-type]
        summed = [summed[i] + cs[i] for i in range(8)]
    normed = [1 if s > 0 else 0 for s in summed]
    if not except_:
        return normed
    exc = [0] * 8
    for x in except_:
        cs = _corner_set(x)
        exc = [exc[i] + cs[i] for i in range(8)]
    return [1 if (normed[i] - (1 if exc[i] > 0 else 0)) > 0 else 0 for i in range(8)]


def _corner_cutter(
    size: tuple[float, float, float],
    corner_vec: list[float],
    radius: float,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> "Bosl2Solid":
    cube_center = [corner_vec[i] * (size[i] / 2 - radius / 2) for i in range(3)]
    sphere_center = [corner_vec[i] * (size[i] / 2 - radius) for i in range(3)]
    cube_shape = _ocube([radius, radius, radius], center=True).translate(cube_center)
    sphere_shape = _osphere(r=radius, fn=fn, fa=fa, fs=fs).translate(sphere_center)
    return cube_shape - sphere_shape  # type: ignore[no-any-return]


def corner_profile(
    body: "Bosl2Solid",
    corners: CornerPlane | str | list[int | str] = "ALL",
    except_corners: list[int | str] | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    size: tuple[float, float, float] | None = None,
    children: "Path2D | None" = None,
    convexity: int = 10,
    anchor: Vector = CENTER,
    center: Point | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> "Bosl2Solid":
    """Round each selected corner of the box-shaped *body* to radius *radius*.

    Args:
        body: The box solid to cut.
        corners: Corners to mask — ``"ALL"``/``"NONE"``, a face vector, or a corner vector.
        except_corners: Corners to explicitly not mask.
        radius: Rounding radius.
        diameter: Rounding diameter (alternative to *radius*).
        size: The box's ``(x, y, z)`` size.
        children: Accepted for call-site compatibility; unused.
        convexity: Accepted for signature compatibility; unused.
        anchor: The anchor *body* was built with (default ``CENTER``).
        center: The box center in body's current frame.
        fn/fa/fs: Arc smoothness overrides.
    """
    _ = (children, convexity)
    if radius is None:
        assert diameter is not None, "corner_profile(): must give radius or diameter"
        radius = diameter / 2
    rad = float(radius)
    assert size is not None, "size= (the box's size) must be given"
    corner_set = _corners(corners, except_corners or [])  # type: ignore[arg-type]
    cutter: "Bosl2Solid | None" = None
    for idx, sel in enumerate(corner_set):
        if sel:
            piece = _corner_cutter(size, CORNER_OFFSETS[idx], rad, fn, fa, fs)
            cutter = piece if cutter is None else (cutter | piece)
    if cutter is None:
        return body
    cutter = cutter.translate(center if center is not None else _anchor_offset_box3(size, anchor))  # type: ignore[arg-type]
    return body - cutter


def face_profile(
    body: "Bosl2Solid",
    faces: str | list[str] = "ALL",
    radius: float | None = None,
    diameter: float | None = None,
    size: tuple[float, float, float] | None = None,
    children: "Path2D | None" = None,
    convexity: int = 10,
    anchor: Vector = CENTER,
    center: Point | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> "Bosl2Solid":
    """Round all edges and corners bounding the given face(s) of the box-shaped *body*.

    Args:
        body: The box solid to cut.
        faces: Face(s) to round, e.g. ``TOP``, or ``"ALL"`` (default).
        radius: Rounding radius.
        diameter: Rounding diameter (alternative to *radius*).
        size: The box's ``(x, y, z)`` size.
        children: The 2-D mask cross-section :class:`~pybosl2.path2d.Path2D`;
            defaults to ``mask2d_roundover(radius)``.
        convexity: Accepted for signature compatibility; unused.
        anchor: The anchor *body* was built with (default ``CENTER``).
        center: The box center in body's current frame.
        fn/fa/fs: Arc smoothness overrides.
    """
    if radius is None:
        assert diameter is not None, "face_profile(): must give radius or diameter"
        radius = diameter / 2
    rad = float(radius)
    mask = children if children is not None else mask2d_roundover(rad, fn=fn, fa=fa, fs=fs)
    body = edge_profile(body, faces, children=mask, size=size, convexity=convexity, anchor=anchor, center=center)  # type: ignore[arg-type]
    return corner_profile(
        body,
        faces,  # type: ignore[arg-type]
        radius=rad,
        size=size,
        convexity=convexity,
        anchor=anchor,
        center=center,
        fn=fn,
        fa=fa,
        fs=fs,
    )
