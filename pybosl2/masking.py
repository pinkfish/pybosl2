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
# FileSummary: Masking
# DocCategory: Foundational
# FileGroup: BOSL2

"""Cut rounded edge/corner/face profiles into a cuboid (BOSL2 masks2d/masks3d)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from pybosl2._edges_lang import CORNER_OFFSETS, Anchor, EdgeAtom, _is_plain_vector
from pybosl2._native import native
from pybosl2.points import Point

if TYPE_CHECKING:
    from pybosl2._backend import Solid
    from pybosl2.path2d import Path2D
    from pybosl2.shapes3d.base import Bosl2Solid

from pybosl2._helpers import frag_count as _frag_count
from pybosl2._helpers import pick_radius as _pick_radius
from pybosl2._helpers import polar_to_xy as _polar_to_xy
from pybosl2._helpers import quantup
from pybosl2.exceptions import Bosl2ValueError

from ._edges_lang import EDGE_OFFSETS
from ._edges_lang import edges as resolve_edges
from .constants import CENTER
from .shapes3d.base import _anchor_offset_box3

__all__ = [
    "Mask2D",
    "Mask3D",
    "chamfer_edge_mask",
    "corner_profile",
    "edge_mask",
    "edge_profile",
    "face_profile",
    "mask2d_chamfer",
    "mask2d_cove",
    "mask2d_groove",
    "mask2d_roundover",
    "mask2d_step",
    "mask2d_tear",
    "mask3d_chamfer",
    "mask3d_groove",
    "mask3d_roundover",
    "rounding_edge_mask",
]

_ocube = native("cube")
_opolygon = native("polygon")
_osphere = native("sphere")


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
    """Return a standalone 3-D edge-rounding cutter of length *length*, for manual positioning.

    Args:
        length: Length of the cutter along its axis (default 1).
        height: Length of the cutter along its axis (default 1).
        radius: Rounding radius (both ends).
        radius1: Rounding radius at the first end, for a tapered cutter.
        radius2: Rounding radius at the second end, for a tapered cutter.
        diameter: Rounding diameter (both ends).
        diameter1: Rounding diameter at the first end.
        diameter2: Rounding diameter at the second end.
        excess: Amount the flat sides extend past the origin (default 0.1).
        fn: Arc smoothness overrides.
        fa: Arc smoothness overrides.
        fs: Arc smoothness overrides.

    Returns:
        A :class:`~pybosl2.shapes3d.Bosl2Solid` cutter.

    """
    length = length if length is not None else (height if height is not None else 1.0)
    rad1 = _pick_radius(
        radius1=radius1,
        diameter1=diameter1,
        radius=radius,
        diameter=diameter,
        dflt=1.0,
    )
    rad2 = _pick_radius(
        radius2=radius2,
        diameter2=diameter2,
        radius=radius,
        diameter=diameter,
        dflt=1.0,
    )
    from pybosl2.shapes3d import Bosl2Solid

    # Wrapped, for the same reason _extrude_mask_along_edge() wraps: the native polygon()/
    # linear_extrude() pair hands back a bare native handle, which has no bounds() and no backend
    # tag, and will not compose with a Bosl2Solid on the right of a boolean.
    if rad1 < rad2:
        cross = mask2d_roundover(rad2, excess=excess, fn=fn, fa=fa, fs=fs)
        shape = Bosl2Solid(_opolygon(cross).linear_extrude(height=length, center=True, scale=rad1 / rad2))
        return shape.rotate(180, [1, 0, 0])
    cross = mask2d_roundover(rad1, excess=excess, fn=fn, fa=fa, fs=fs)
    scale = rad2 / rad1 if rad1 else 1.0
    return Bosl2Solid(_opolygon(cross).linear_extrude(height=length, center=True, scale=scale))


def chamfer_edge_mask(length: float = 1.0, chamfer: float = 1.0, excess: float = 0.1) -> "Solid":
    """Return a standalone 3-D edge-chamfer cutter of length *length*, on the active backend.

    A diamond bar centred on its own Z axis: a square prism of side ``chamfer * sqrt(2)``, turned
    45 degrees, so it reaches *chamfer* along each axis.

    It is built as a turned prism rather than an extruded diamond polygon so that it works on
    either backend -- ``polygon().linear_extrude()`` is a CSG-only construction, and this cutter is
    what `cubetruss` and `tripod_mounts` chamfer with, so it was the thing keeping them CSG-only
    (TASKS T14). The two forms were checked to give the same solid and the same cut.

    Args:
        length: Length of the cutter along its axis (default 1).
        chamfer: Chamfer size (the diamond's half-diagonal along each axis, default 1).
        excess: Extra length past *length* so the cut clears the surface (default 0.1).

    Returns:
        The cutter, built by whichever backend is active.

    """
    from pybosl2.solid import cuboid

    side = chamfer * math.sqrt(2)
    return cuboid([side, side, length + excess]).rotate(45, [0, 0, 1])


def _pick_axes(vec: Point) -> tuple[int, int, int, float, float]:
    """For an edge vector (one axis 0, two axes ±1), return ``(run_axis, a1, a2, s1, s2)``."""
    run_axis = next(i for i in range(3) if vec[i] == 0)
    nz = [i for i in range(3) if vec[i] != 0]
    a1, a2 = nz
    return run_axis, a1, a2, float(vec[a1]), float(vec[a2])


def _orient_mask_along_edge(
    shape: "Solid",
    size: tuple[float, float, float],
    vec: Point,
) -> "Solid":
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
    return shape.multmatrix(m).translate(center)


def _extrude_mask_along_edge(
    mask_path: "Path2D",
    length: float,
    size: tuple[float, float, float],
    vec: Point,
) -> "Solid":
    from pybosl2.shapes3d import Bosl2Solid

    # Wrapped, not the bare native handle the native polygon()/linear_extrude() pair hands back:
    # edge_profile()'s cutter is combined with corner_profile()'s (a real Bosl2Solid) in
    # face_profile(), and the native ``|`` rejects a wrapper on its right-hand side.
    shape = Bosl2Solid(_opolygon(mask_path).linear_extrude(height=length, center=True))
    return _orient_mask_along_edge(shape, size, vec)


def edge_mask(
    body: "Bosl2Solid",
    edges: EdgeAtom | list[EdgeAtom] = Anchor.ALL,
    except_edges: list[EdgeAtom] | None = None,
    mask: "Solid | None" = None,
    size: tuple[float, float, float] | None = None,
    anchor: Anchor | Point = CENTER,
    center: Point | None = None,
    return_cutter: bool = False,
) -> "Solid | None":
    """Cut a 3-D edge cutter along each selected edge of the box-shaped *body*.

    Args:
        body: The box solid to cut.
        edges: Edges to mask — an :class:`EdgePlane`, a string, a vector, or a list thereof (default ``"ALL"``).
        except_edges: Edges to explicitly not mask.
        mask: The 3-D edge cutter to apply.
        size: The box's ``(x, y, z)`` size.
        anchor: The anchor *body* was built with (default ``CENTER``).
        center: The box center in body's current frame.
        return_cutter: If True, returns the generated cutter shape instead of cutting it.

    """
    if not (size is not None):
        raise Bosl2ValueError("size= (the box's size) must be given")
    if not (mask is not None):
        raise Bosl2ValueError("mask= (the edge cutter) must be given")
    edge_set = resolve_edges(edges, except_edges or [])
    cutter: "Solid | None" = None
    for axis in range(3):
        for i in range(4):
            if edge_set[axis][i] > 0:
                piece = _orient_mask_along_edge(mask, size, Point(EDGE_OFFSETS[axis][i]))
                cutter = piece if cutter is None else (cutter | piece)
    if cutter is None:
        return None if return_cutter else body
    cutter = cutter.translate(list(center) if center is not None else _anchor_offset_box3(size, anchor))
    if return_cutter:
        return cutter
    return body - cutter


def edge_profile(
    body: "Bosl2Solid",
    edges: EdgeAtom | list[EdgeAtom] = Anchor.ALL,
    except_edges: list[EdgeAtom] | None = None,
    mask: "Path2D | None" = None,
    size: tuple[float, float, float] | None = None,
    convexity: int = 10,
    anchor: Anchor | Point = CENTER,
    center: Point | None = None,
    return_cutter: bool = False,
) -> "Solid | None":
    """Cut a 2-D mask profile extruded along each selected edge of the box-shaped *body*.

    Args:
        body: The box solid to cut.
        edges: Edges to mask (default ``"ALL"``).
        except_edges: Edges to explicitly not mask.
        mask: The 2-D mask cross-section, as a :class:`~pybosl2.path2d.Path2D`.
        size: The box's ``(x, y, z)`` size.
        convexity: Accepted for signature compatibility; unused.
        anchor: The anchor *body* was built with (default ``CENTER``).
        center: The box center in body's current frame.
        return_cutter: If True, returns the generated cutter shape instead of cutting it.

    """
    _ = convexity
    if not (size is not None):
        raise Bosl2ValueError("size= (the box's size) must be given")
    if not (mask is not None):
        raise Bosl2ValueError("mask= (the 2-D mask path) must be given")
    edge_set = resolve_edges(edges, except_edges or [])
    cutter: "Solid | None" = None
    for axis in range(3):
        for i in range(4):
            if edge_set[axis][i] > 0:
                vec = EDGE_OFFSETS[axis][i]
                length = size[axis] + 0.1
                piece = _extrude_mask_along_edge(mask, length, size, Point(vec))
                cutter = piece if cutter is None else (cutter | piece)
    if cutter is None:
        return None if return_cutter else body
    cutter = cutter.translate(list(center) if center is not None else _anchor_offset_box3(size, anchor))
    if return_cutter:
        return cutter
    return body - cutter


def _corner_set(v: list[int] | Anchor | Point) -> list[int]:
    """Resolve one corner selector to an 8-long 0/1 corner array.

    A corner is selected when, on EVERY axis, the selector is either 0 (don't care) or matches
    that corner's sign -- BOSL2's ``all([for (i=[0:2]) !v[i] || (v[i]==v2[i])])``. Note this is
    an AND over per-axis ORs: written as a flat ``a or b and c or d`` chain Python's precedence
    turns it into an OR of the axes instead, which selects every corner that agrees on any one
    axis (e.g. ``[-1,-1,-1]`` would also pick up ``[1,1,-1]``).
    """
    if isinstance(v, Anchor):
        return v.to_corner_set()
    if isinstance(v, str):  # pragma: no cover
        # defensive: _corners(), the only caller, rejects the string form for both its arguments
        # before it gets here.
        raise Bosl2ValueError(f"Legacy string corner selection is not allowed: {v!r}")
    arr = np.asarray(v, dtype=int)
    return [1 if all(arr[i] == 0 or arr[i] == c[i] for i in range(3)) else 0 for c in CORNER_OFFSETS]


def _corners(
    v: Anchor | list[int] | list[list[int]] | list[Anchor],
    except_: list | None = None,  # type: ignore[type-arg]
) -> list[int]:
    if except_ is None:
        except_ = []
    if isinstance(v, str):
        raise Bosl2ValueError(f"Legacy string corner selection is not allowed: {v!r}")
    if isinstance(except_, str):
        raise Bosl2ValueError(f"Legacy string corner selection is not allowed: {except_!r}")
    # Wrap a SINGLE selector; leave a list of selectors alone. This has to use the same test
    # the edge language uses, not "is v[0] a list": `Anchor.BOTTOM + Anchor.FRONT + Anchor.LEFT`
    # is a Point, so `[that]` looked like a bare selector here and got wrapped a second time,
    # and the bare Point looked like a list of three scalar selectors.
    if isinstance(v, Anchor) or _is_plain_vector(v):
        v = [v]  # type: ignore[assignment]
    if isinstance(except_, Anchor) or _is_plain_vector(except_):
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
    if radius <= 0:
        raise Bosl2ValueError(f"corner_profile(): radius/diameter must be positive, got {radius}.")
    # The cutter is the material a fillet leaves behind: the radius-sided block filling the very
    # corner, minus the sphere the rounded surface follows. The sphere sits at the *inner* point,
    # one radius in from the corner along each axis.
    #
    # This used to build a 2*radius block and put the sphere on the body's corner instead, which
    # inverted the cut: subtracting it scooped out the inside of the solid and left the corner
    # standing. Nothing caught it because the only tests asserted `result is not None`.
    from pybosl2.shapes3d import cuboid, sphere

    corner_pt = [size[i] / 2 * corner_vec[i] for i in range(3)]
    inner_pt = [corner_pt[i] - corner_vec[i] * radius for i in range(3)]

    block = cuboid([radius, radius, radius]).translate(Point([(corner_pt[i] + inner_pt[i]) / 2 for i in range(3)]))
    sph = sphere(radius=radius, fn=fn, fa=fa, fs=fs).translate(Point(inner_pt))
    return block - sph


def _corner_chamfer_cutter(
    size: tuple[float, float, float],
    corner_vec: list[float],
    chamfer: float,
) -> "Bosl2Solid":
    """Return the material a corner chamfer of size *chamfer* removes from a *size* box.

    The kept surface is the one ``cuboid(size, chamfer=chamfer)`` produces: each of the three
    edges meeting at this corner is cut by its own 45 degree plane, and the three planes meet at
    a point. So the cutter is the corner block intersected with the union of the three edge
    chamfer bars -- everything inside the block that at least one of the three planes shaves off.
    """
    if chamfer <= 0:
        raise Bosl2ValueError(f"Mask3D.chamfer(): chamfer must be positive, got {chamfer}.")
    from pybosl2.shapes3d import cuboid

    corner_pt = [size[i] / 2 * corner_vec[i] for i in range(3)]
    inner_pt = [corner_pt[i] - corner_vec[i] * chamfer for i in range(3)]
    block = cuboid([chamfer, chamfer, chamfer]).translate(Point([(corner_pt[i] + inner_pt[i]) / 2 for i in range(3)]))

    wedges: "Solid | None" = None
    for run_axis in range(3):
        edge_vec = list(corner_vec)
        edge_vec[run_axis] = 0.0
        bar = chamfer_edge_mask(length=size[run_axis], chamfer=chamfer)
        bar = _orient_mask_along_edge(bar, size, Point(edge_vec))
        wedges = bar if wedges is None else (wedges | bar)
    assert wedges is not None, "three edges meet at every corner"
    return block & wedges


def corner_profile(
    body: "Bosl2Solid",
    corners: Anchor = Anchor.ALL,
    except_corners: list[Anchor] | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    size: tuple[float, float, float] | None = None,
    mask: "Path2D | None" = None,
    convexity: int = 10,
    anchor: Anchor | Point = CENTER,
    center: Point | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    return_cutter: bool = False,
) -> "Solid | None":
    """Round each selected corner of the box-shaped *body* to radius *radius*.

    Args:
        body: The box solid to cut.
        corners: Corners to mask — ``"ALL"``/``"NONE"``, a face vector, or a corner vector.
        except_corners: Corners to explicitly not mask.
        radius: Rounding radius.
        diameter: Rounding diameter (alternative to *radius*).
        size: The box's ``(x, y, z)`` size.
        mask: Accepted for call-site compatibility; unused -- corner_profile always rounds.
        convexity: Accepted for signature compatibility; unused.
        anchor: The anchor *body* was built with (default ``CENTER``).
        center: The box center in body's current frame.
        fn: Arc smoothness overrides.
        fa: Arc smoothness overrides.
        fs: Arc smoothness overrides.
        return_cutter: If True, returns the generated cutter shape instead of cutting it.

    """
    _ = (mask, convexity)
    if radius is None:
        if not (diameter is not None):
            raise Bosl2ValueError("corner_profile(): must give radius or diameter")
        radius = diameter / 2
    rad = float(radius)
    if not (size is not None):
        raise Bosl2ValueError("size= (the box's size) must be given")
    corner_set = _corners(corners, except_corners or [])
    cutter: "Solid | None" = None
    for idx, sel in enumerate(corner_set):
        if sel:
            piece = _corner_cutter(size, CORNER_OFFSETS[idx], rad, fn, fa, fs)
            cutter = piece if cutter is None else (cutter | piece)
    if cutter is None:
        return None if return_cutter else body
    cutter = cutter.translate(list(center) if center is not None else _anchor_offset_box3(size, anchor))
    if return_cutter:
        return cutter
    return body - cutter


def face_profile(
    body: "Bosl2Solid",
    faces: Anchor | list[Anchor] = Anchor.ALL,
    radius: float | None = None,
    diameter: float | None = None,
    size: tuple[float, float, float] | None = None,
    mask: "Path2D | None" = None,
    convexity: int = 10,
    anchor: Anchor | Point = CENTER,
    center: Point | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    return_cutter: bool = False,
) -> "Solid | None":
    """Round all edges and corners bounding the given face(s) of the box-shaped *body*.

    Args:
        body: The box solid to cut.
        faces: Face(s) to round, e.g. ``TOP``, or ``"ALL"`` (default).
        radius: Rounding radius.
        diameter: Rounding diameter (alternative to *radius*).
        size: The box's ``(x, y, z)`` size.
        mask: The 2-D mask cross-section, as a :class:`~pybosl2.path2d.Path2D`;
            defaults to ``Mask2D.roundover(radius)``.
        convexity: Accepted for signature compatibility; unused.
        anchor: The anchor *body* was built with (default ``CENTER``).
        center: The box center in body's current frame.
        fn: Arc smoothness overrides.
        fa: Arc smoothness overrides.
        fs: Arc smoothness overrides.
        return_cutter: If True, returns the generated cutter shape instead of cutting it.

    """
    if radius is None:
        if not (diameter is not None):
            raise Bosl2ValueError("face_profile(): must give radius or diameter")
        radius = diameter / 2
    rad = float(radius)
    profile = mask if mask is not None else Mask2D.roundover(rad, fn=fn, fa=fa, fs=fs)
    if return_cutter:
        edge_c = edge_profile(
            body,
            faces,
            mask=profile,
            size=size,
            convexity=convexity,
            anchor=anchor,
            center=center,
            return_cutter=True,
        )
        corner_c = corner_profile(
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
            return_cutter=True,
        )
        if edge_c is None:
            return corner_c
        if corner_c is None:
            return edge_c
        return edge_c | corner_c

    body = edge_profile(body, faces, mask=profile, size=size, convexity=convexity, anchor=anchor, center=center)  # type: ignore[assignment]
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


class Mask2D:
    """The 2-D cutter cross-sections (BOSL2's ``mask2d_*`` family), as factories returning a Path2D.

    Each returns the profile you sweep along an edge to cut it -- pass one as the *mask* of
    :meth:`~pybosl2.shapes3d.base.Bosl2Solid.edge_profile` /
    :meth:`~pybosl2.shapes3d.base.Bosl2Solid.corner_profile`, or extrude it yourself. The BOSL2 spellings
    (``mask2d_roundover`` and friends) remain as aliases of these.

    Examples:
        .. pythonscad-example::

            from pybosl2 import Anchor, Mask2D, cuboid

            cuboid([30, 30, 20]).edge_profile(edges=[Anchor.TOP], mask=Mask2D.roundover(4)).show()

    """

    @staticmethod
    def roundover(
        radius: float | None = None,
        inset: float | tuple[float, float] = 0.0,
        excess: float = 0.01,
        diameter: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Path2D":
        """Return the 2-D L-shaped cutter cross-section for rounding a 90-degree edge/corner to radius *radius*.

        Args:
            radius: Rounding radius.
            inset: Scalar or ``(x, y)`` inset of the rounding center from the corner (default 0).
            excess: Amount the flat sides extend past the origin, for a clean boolean cut (default 0.01).
            diameter: Rounding diameter (alternative to *radius*).
            fn: Arc smoothness overrides.
            fa: Arc smoothness overrides.
            fs: Arc smoothness overrides.

        Returns:
            A :class:`~pybosl2.path2d.Path2D` of the 2-D cutter cross-section.

        """
        from pybosl2.path2d import Path2D

        if radius is None:
            if not (diameter is not None):
                raise Bosl2ValueError("Mask2D.roundover(): must give radius or diameter")
            radius = diameter / 2
        rad = float(radius)
        inset_x, inset_y = inset if isinstance(inset, tuple) else (float(inset), float(inset))
        steps = max(1, int(quantup(_frag_count(rad, fn, fa, fs), 4) // 4))
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

    @staticmethod
    def chamfer(
        width: float,
        height: float | None = None,
        excess: float = 0.01,
    ) -> "Path2D":
        """Return the 2-D L-shaped cutter cross-section for chamfering a 90-degree edge.

        A symmetric chamfer needs one number; give *height* only for an asymmetric one. These were
        spelled ``x`` and ``y``, which named the axes rather than the thing being described
        (SPEC S-26c).

        Args:
            width: Chamfer width, measured back along the first face.
            height: Chamfer height, measured back along the second face (default: *width*, a
                symmetric 45-degree chamfer).
            excess: Amount the flat sides extend past the origin, for a clean cut (default 0.01).

        Returns:
            A :class:`~pybosl2.path2d.Path2D` of the 2-D cutter cross-section.

        Raises:
            Bosl2ValueError: If *width* or a given *height* is not positive.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Anchor, Mask2D, cuboid

                cuboid([30, 30, 20]).edge_profile(edges=[Anchor.TOP], mask=Mask2D.chamfer(4)).show()

        """
        from pybosl2.path2d import Path2D

        if not (width > 0):
            raise Bosl2ValueError(f"Mask2D.chamfer(): width must be positive, got {width}.")
        y_val = width if height is None else float(height)
        if not (y_val > 0):
            raise Bosl2ValueError(f"Mask2D.chamfer(): height must be positive, got {height}.")
        pts = [
            [width, -excess],
            [-excess, -excess],
            [-excess, y_val],
            [0.0, y_val],
            [width, 0.0],
        ]
        return Path2D(pts, closed=True)

    @staticmethod
    def cove(
        radius: float,
        excess: float = 0.01,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Path2D":
        """Return the 2-D L-shaped cutter cross-section for a concave corner fillet (cove).

        Args:
            radius: Cove radius.
            excess: Amount the flat sides extend past the origin, for a clean cut (default 0.01).
            fn: Arc smoothness overrides.
            fa: Arc smoothness overrides.
            fs: Arc smoothness overrides.

        """
        from pybosl2.path2d import Path2D

        steps = max(1, int(quantup(_frag_count(radius, fn, fa, fs), 4) // 4))
        path = [
            [radius, -excess],
            [-excess, -excess],
            [-excess, radius],
            [0.0, radius],
        ]
        for i in range(steps + 1):
            ang = math.radians(180.0 + (90.0 * i / steps))
            path.append(
                [
                    radius + radius * math.cos(ang),
                    radius + radius * math.sin(ang),
                ]
            )
        path.append([radius, 0.0])
        return Path2D(path, closed=True)

    @staticmethod
    def tear(
        r: float,
        maxgap: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Path2D":
        """Return the 2-D L-shaped cutter cross-section with a teardrop-shaped profile.

        Args:
            r: Radius of the teardrop circle.
            maxgap: Maximum gap height (unused, kept for compatibility).
            fn: Arc smoothness overrides.
            fa: Arc smoothness overrides.
            fs: Arc smoothness overrides.

        """
        from pybosl2.path2d import Path2D

        _ = maxgap
        excess = 0.01
        path = [
            [r, -excess],
            [-excess, -excess],
            [-excess, r],
        ]
        steps = max(1, int(quantup(_frag_count(r, fn, fa, fs), 4) // 4))
        for i in range(steps + 1):
            ang = math.radians(180.0 + (135.0 * i / steps))
            path.append(
                [
                    r + r * math.cos(ang),
                    r + r * math.sin(ang),
                ]
            )
        tip = [r * (1.0 - math.sqrt(2.0)), r * (1.0 - math.sqrt(2.0))]
        path.append(tip)
        return Path2D(path, closed=True)

    @staticmethod
    def step(
        width: float,
        height: float | None = None,
        excess: float = 0.01,
    ) -> "Path2D":
        """Return the 2-D cutter cross-section for cutting a step profile in a corner.

        A square step needs one number; give *height* only for a rectangular one. It used to
        require both, which SPEC D-2 allows only with a written justification and there is none:
        a step as deep as it is wide is the ordinary case.

        Args:
            width: Step width. The one thing no default can invent.
            height: Step height (default: *width*, a square step).
            excess: Amount the flat sides extend past the origin, for a clean cut (default 0.01).

        Returns:
            A :class:`~pybosl2.path2d.Path2D` of the 2-D cutter cross-section.

        Raises:
            Bosl2ValueError: If *width* or a given *height* is not positive.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Anchor, Mask2D, cuboid

                cuboid([30, 30, 20]).edge_profile(edges=[Anchor.TOP], mask=Mask2D.step(4)).show()

        """
        if not (width > 0):
            raise Bosl2ValueError(f"Mask2D.step(): width must be positive, got {width}.")
        height = width if height is None else float(height)
        if not (height > 0):
            raise Bosl2ValueError(f"Mask2D.step(): height must be positive, got {height}.")
        from pybosl2.path2d import Path2D

        # The rectangular notch this cuts out of the corner, extended by `excess` on the two outer
        # sides so the boolean is clean.
        #
        # This traced (width, -excess) -> (-excess, -excess) -> (-excess, height) -> (0, height)
        # -> (0, 0) -> (width, 0), which returns along the notch's *own* edges and so encloses only
        # an L-shaped sliver `excess` thick: a 4 x 4 step enclosed 0.08 mm^2 instead of 16, and cut
        # nothing at all. Nothing caught it because the test asserted the point count and not the
        # area (PLAN X-8).
        pts = [
            [-excess, -excess],
            [width, -excess],
            [width, height],
            [-excess, height],
        ]
        return Path2D(pts, closed=True)

    @staticmethod
    def groove(
        width: float,
        depth: float | None = None,
        chamfer: float = 0.0,
        round_radius: float = 0.0,
        excess: float = 0.01,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Path2D":
        """Return the 2-D cutter cross-section for cutting a slot or groove.

        Only *width* is required (SPEC D-2, P-3): half the width is the depth that reads as a
        groove rather than a slot, so that is what it derives when you do not say.

        Args:
            width: Groove width. The one thing no default can invent.
            depth: Groove depth (default: half the width).
            chamfer: Groove chamfer offset (unused, kept for compatibility).
            round_radius: Groove corner rounding radius (unused, kept for compatibility).
            excess: Amount the flat sides extend past the origin, for a clean cut (default 0.01).
            fn: Arc smoothness override -- fixed fragment count.
            fa: Arc smoothness override -- minimum fragment angle.
            fs: Arc smoothness override -- minimum fragment size.

        Returns:
            A :class:`~pybosl2.path2d.Path2D` of the 2-D cutter cross-section.

        Raises:
            Bosl2ValueError: If *width* or a given *depth* is not positive.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Anchor, Mask2D, cuboid

                cuboid([30, 30, 20]).edge_profile(edges=[Anchor.TOP], mask=Mask2D.groove(4)).show()

        """
        if not (width > 0):
            raise Bosl2ValueError(f"Mask2D.groove(): width must be positive, got {width}.")
        depth = width / 2 if depth is None else float(depth)
        if not (depth > 0):
            raise Bosl2ValueError(f"Mask2D.groove(): depth must be positive, got {depth}.")
        from pybosl2.path2d import Path2D

        _ = (chamfer, round_radius, fn, fa, fs)
        half_w = width / 2.0
        pts = [
            [half_w + excess, -excess],
            [-half_w - excess, -excess],
            [-half_w - excess, depth + excess],
            [-half_w, depth + excess],
            [-half_w, 0.0],
            [half_w, 0.0],
            [half_w, depth + excess],
            [half_w + excess, depth + excess],
        ]
        return Path2D(pts, closed=True)


class Mask3D:
    """The ready-made 3-D cutter solids (BOSL2's ``mask3d_*`` family), as factories.

    Unlike :class:`Mask2D`, these are whole solids: subtract one from your shape to cut every
    selected edge or corner at once. The BOSL2 spellings remain as aliases of these.

    Examples:
        .. pythonscad-example::

            from pybosl2 import Mask3D, cuboid

            (cuboid([30, 30, 30]) - Mask3D.roundover(4, size=(30, 30, 30))).show()

    """

    @staticmethod
    def roundover(
        radius: float | None = None,
        *,
        size: tuple[float, float, float],
        diameter: float | None = None,
        corners: Anchor = Anchor.ALL,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Solid":
        """Return the 3-D cutter that rounds the corners and edges of a box of the given size.

        `size` is the box being cut, so it is only ever needed when you build the cutter yourself.
        Reaching for :meth:`~pybosl2.shapes3d.base.CsgSolid.round_edges` instead is both shorter
        and safer -- the solid already knows its own box and fills this in (SPEC S-26a, S-26b)::

            solid.round_edges(Anchor.TOP, radius=3)

        Args:
            radius: Rounding radius.
            size: Size of the box being cut, ``(x, y, z)``. Keyword-only, because it describes the
                *parent*, not the treatment.
            diameter: Rounding diameter (alternative to *radius*; giving both is an error).
            corners: Corners to select.
            fn: Arc smoothness override -- fixed fragment count.
            fa: Arc smoothness override -- minimum fragment angle.
            fs: Arc smoothness override -- minimum fragment size.

        Returns:
            The cutter solid; subtract it from the box to round it.

        Raises:
            Bosl2ValueError: If neither radius nor diameter is given, if both are, or if *corners*
                selects nothing.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Mask3D, cuboid

                (cuboid([30, 30, 30]) - Mask3D.roundover(4, size=(30, 30, 30))).show()

        """
        from pybosl2.shapes3d import cuboid

        r = _pick_radius(radius=radius, diameter=diameter)
        if r is None:
            raise Bosl2ValueError("Mask3D.roundover(): give radius= or diameter=.")
        body = cuboid(size)
        cutter = corner_profile(
            body,
            corners=corners,
            radius=r,
            size=size,
            fn=fn,
            fa=fa,
            fs=fs,
            return_cutter=True,
        )
        if cutter is None:
            raise Bosl2ValueError(
                "Mask3D.roundover(): corners= selected no corners, so there is nothing to round; "
                "pass an Anchor naming at least one corner."
            )
        return cutter

    @staticmethod
    def chamfer(
        chamfer: float,
        *,
        size: tuple[float, float, float],
        corners: Anchor = Anchor.ALL,
    ) -> "Solid":
        """Return the 3-D cutter that chamfers the corners and edges of a box of the given size.

        As with :meth:`roundover`, `size` describes the box being cut;
        :meth:`~pybosl2.shapes3d.base.CsgSolid.chamfer_edges` fills it in for you (SPEC S-26a).

        Args:
            chamfer: Chamfer distance.
            size: Size of the box being cut, ``(x, y, z)``. Keyword-only -- it describes the
                *parent*, not the treatment.
            corners: Corners to select.

        Returns:
            The cutter solid; subtract it from the box to chamfer it.

        Raises:
            Bosl2ValueError: If *corners* selects nothing.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Mask3D, cuboid

                (cuboid([30, 30, 30]) - Mask3D.chamfer(4, size=(30, 30, 30))).show()

        """
        # NOT corner_profile(mask=Mask2D.chamfer(...)): corner_profile ignores mask= and
        # always rounds, which used to make this factory return the roundover cutter verbatim.
        cutter: "Solid | None" = None
        for idx, sel in enumerate(_corners(corners, [])):
            if sel:
                piece = _corner_chamfer_cutter(size, CORNER_OFFSETS[idx], chamfer)
                cutter = piece if cutter is None else (cutter | piece)
        if cutter is None:
            raise Bosl2ValueError(
                "Mask3D.chamfer(): corners= selected no corners, so there is nothing to chamfer; "
                "pass an Anchor naming at least one corner."
            )
        return cutter

    @staticmethod
    def groove(
        width: float,
        *,
        depth: float | None = None,
        length: float | None = None,
        chamfer: float = 0.0,
        size: tuple[float, float, float] | None = None,
    ) -> "Solid":
        """Return the 3-D cutter for a slot or groove of the given width.

        Only *width* is required (SPEC D-2): a groove's depth follows from its width unless you
        say otherwise -- half the width is the proportion that reads as a groove rather than a
        slot -- and its length is however long the thing being grooved is, which *size* supplies
        when you pass it and :meth:`~pybosl2.shapes3d.base.CsgSolid.groove_edges` supplies for you
        (SPEC P-3, S-26a). This took three required positionals, which SPEC D-2 says is never
        acceptable.

        Args:
            width: Groove width. The one thing no default can invent.
            depth: Groove depth (default: half the width).
            length: Groove length (default: the longest side of *size*, or ten times the width if
                no size is given either).
            chamfer: Groove chamfer offset.
            size: Size of the thing being grooved, ``(x, y, z)``, used to derive *length*.

        Returns:
            The cutter solid, extruded along Z and centred.

        Raises:
            Bosl2ValueError: If *width* is not positive, or a given *depth* is not positive.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Mask3D, cuboid

                (cuboid([40, 40, 12]) - Mask3D.groove(6, length=60)).show()

        """
        if not (width > 0):
            raise Bosl2ValueError(f"Mask3D.groove(): width must be positive, got {width}.")
        cut_depth = width / 2 if depth is None else float(depth)
        if not (cut_depth > 0):
            raise Bosl2ValueError(f"Mask3D.groove(): depth must be positive, got {depth}.")
        if length is not None:
            cut_length = float(length)
        elif size is not None:
            cut_length = max(float(v) for v in size)
        else:
            cut_length = width * 10
        g2d = Mask2D.groove(width, cut_depth, chamfer=chamfer)
        return g2d.linear_extrude(height=cut_length, center=True)


# The BOSL2 spellings, kept as aliases of the factories above (SPEC P-6). New code should use the
# classes -- these stay for one release.
mask2d_roundover = Mask2D.roundover
mask2d_chamfer = Mask2D.chamfer
mask2d_cove = Mask2D.cove
mask2d_tear = Mask2D.tear
mask2d_step = Mask2D.step
mask2d_groove = Mask2D.groove
mask3d_roundover = Mask3D.roundover
mask3d_chamfer = Mask3D.chamfer
mask3d_groove = Mask3D.groove
