# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/distributors.py
#    Pure-Python port of BOSL2's distributors.scad: the "copiers" that duplicate a shape into a
#    line/grid/ring/arc/sphere/path pattern, plus the reflected-copy helpers. Each copier is a
#    module-level function that returns a list of 4x4 transformation matrices (BOSL2's function
#    form without a ``p=`` argument), and a matching method on the :class:`Distributable` mixin
#    that applies those matrices to the object.
#
#    The mixin is inherited by :class:`~pybosl2.shapes3d.Bosl2Solid`, :class:`~pybosl2.paths.Path2D`,
#    and :class:`~pybosl2.paths.Path3D`, each of which implements ``_distribute(mats)`` to say what
#    "a list of copies" means for it:
#      * Bosl2Solid  -> the UNION of the transformed geometry copies (a new Bosl2Solid).
#      * Path2D / Path3D -> a plain ``list`` of transformed path copies (BOSL2's function form).
#        A 2-D Path2D only supports the in-plane copiers; one that would lift it out of the XY plane
#        raises, directing you to Path3D.
#
#    Only matrix math and pybosl2.transforms/constants are imported at load time (so paths.py can
#    pull in the mixin during its own import without a cycle); Path2D/Region/point-in-polygon are
#    imported lazily inside the few functions that need them.
#
# FileSummary: Distributors: line/grid/ring/arc/sphere/path copiers and reflected copies.
# DocCategory: Foundational
# FileGroup: BOSL2

"""Return Distributors: line/grid/ring/arc/sphere/path copiers and reflected copies."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, TypeVar

import numpy as np

from pybosl2._helpers import is_num, rot_from_to4, translate4
from pybosl2.constants import BACK, RIGHT, UP
from pybosl2.enums import StaggerMode
from pybosl2.points import Point
from pybosl2.transforms import axis_angle_matrix

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pybosl2._edges_lang import Anchor
    from pybosl2._shape import BaseShape as BaseShape

_CopyType = TypeVar("_CopyType", bound="Distributable")


__all__ = [
    "xdistribute",
    "ydistribute",
    "zdistribute",
    "Distributable",
    "DistributableMatrix",
]


# ---------------------------------------------------------------------------
# Section: matrix helpers
# ---------------------------------------------------------------------------


# (imported from pybosl2._helpers as rot_from_to4)


def _vec3(v: Any, fill: float = 0.0) -> np.ndarray:
    if is_num(v):
        return np.array([float(v), float(fill), float(fill)])
    arr = np.asarray(v, dtype=float)
    if arr.shape[0] == 1:
        return np.array([float(arr[0]), float(fill), float(fill)])
    out = np.zeros(3)
    n = min(arr.shape[0], 3)
    out[:n] = arr[:n]
    out[n:] = float(fill)
    return out


# ---------------------------------------------------------------------------
# Section: copier matrix generators (BOSL2 function form, returning matrices)
# ---------------------------------------------------------------------------


def line_copies(
    spacing: float | np.ndarray | None = None,
    length: float | np.ndarray | None = None,
    p1: Point | None = None,
    p2: Point | None = None,
    num_copies: int | None = None,
) -> list[np.ndarray]:
    """Return translation matrices evenly spread along a line."""
    if length is not None:
        ll = _vec3(length, 0.0)
    elif spacing is not None and num_copies is not None:
        ll = (num_copies - 1) * _vec3(spacing, 0.0)
    elif p1 is not None and p2 is not None:
        ll = np.asarray(p2, dtype=float) - np.asarray(p1, dtype=float)
    else:
        ll = None
    if num_copies is not None:
        cnt = int(num_copies)
    elif spacing is not None and ll is not None:
        cnt = int(math.floor(np.linalg.norm(ll) / np.linalg.norm(_vec3(spacing, 0.0)) + 1.000001))
    else:
        cnt = 2
    if cnt <= 1:
        spc = np.zeros(3)
    elif spacing is None and ll is not None or is_num(spacing) and ll is not None:
        spc = ll / (cnt - 1)
    else:
        spc = _vec3(spacing, 0.0)
    spos = _vec3(p1, 0.0) if p1 is not None else -(cnt - 1) / 2 * spc
    return [translate4(i * spc + spos) for i in range(cnt)]


def _axis_copies(
    direction: Point,
    spacing: float | Sequence[float] | np.ndarray | None,
    length: float | None,
    start_pos: float | Point | None,
    num_copies: int | None = None,
) -> list[np.ndarray]:
    dirv = np.asarray(direction, dtype=float)
    sp_pt: Point | None = None
    if is_num(start_pos):
        sp_pt = Point(
            float(start_pos * dirv[0]),
            float(start_pos * dirv[1]),
            float(start_pos * dirv[2]),
        )
    elif start_pos is not None:
        arr = np.asarray(start_pos, dtype=float)
        sp_pt = Point(float(arr[0]), float(arr[1]), float(arr[2]) if arr.shape[0] > 2 else None)
    if isinstance(spacing, (list, tuple, np.ndarray)):  # explicit positions along the axis
        base = sp_pt if sp_pt is not None else np.zeros(3)
        return [translate4(base + float(s) * dirv) for s in spacing]
    lv = (length * dirv) if length is not None else None
    spv = (spacing * dirv) if spacing is not None else None
    return line_copies(spacing=spv, num_copies=num_copies, length=lv, p1=sp_pt)


def xcopies(
    spacing: float | None = None,
    length: float | None = None,
    start_pos: float | Point | None = None,
    num_copies: int | None = None,
) -> list[np.ndarray]:
    """Return copies spread along the X axis."""
    return _axis_copies(
        RIGHT.vector,
        spacing,
        length,
        start_pos,
        num_copies=num_copies,
    )


def ycopies(
    spacing: float | None = None,
    length: float | None = None,
    start_pos: float | Point | None = None,
    num_copies: int | None = None,
) -> list[np.ndarray]:
    """Return copies spread along the Y axis."""
    return _axis_copies(BACK.vector, spacing, num_copies=num_copies, length=length, start_pos=start_pos)


def zcopies(
    spacing: float | None = None,
    length: float | None = None,
    start_pos: float | Point | None = None,
    num_copies: int | None = None,
) -> list[np.ndarray]:
    """Return copies spread along the Z axis."""
    return _axis_copies(UP.vector, spacing, num_copies=num_copies, length=length, start_pos=start_pos)


def grid_copies(
    spacing: float | Sequence[float] | np.ndarray | None = None,
    size: float | Sequence[float] | np.ndarray | None = None,
    stagger: bool | StaggerMode = False,
    inside: Sequence[Sequence[float]] | np.ndarray | None = None,
    nonzero: bool | None = None,
    axes: str = "xy",
    num_copies: int | Sequence[int] | np.ndarray | None = None,
) -> list[np.ndarray]:
    """Return copies laid out in a square or staggered (hex) grid."""
    assert stagger in (
        False,
        True,
        StaggerMode.ALT,
    ), "grid_copies(): stagger must be False, True or 'alt'."
    assert len(axes) == 2, "grid_copies(): invalid axes."
    assert axes[0] in "xyz", "grid_copies(): invalid axes."
    assert axes[1] in "xyz", "grid_copies(): invalid axes."
    assert axes[0] != axes[1], "grid_copies(): invalid axes."
    ai: dict[str, int] = {"x": 0, "y": 1, "z": 2}

    def permax(pt: Sequence[float]) -> np.ndarray:
        out: list[float] = [0.0, 0.0, 0.0]
        out[ai[axes[0]]] = pt[0]
        out[ai[axes[1]]] = pt[1]
        return np.array(out)

    bounds: tuple[np.ndarray, np.ndarray] | None = None
    if inside is not None:
        arr = np.asarray(inside, dtype=float)
        bounds = (arr.min(axis=0), arr.max(axis=0))

    if size is not None:
        size = [float(size), float(size)] if is_num(size) else [float(size[0]), float(size[1])]  # type: ignore[arg-type,index]
    elif bounds is not None:
        size = [2 * max(abs(bounds[0][i]), abs(bounds[1][i])) for i in range(2)]

    if is_num(spacing):
        from pybosl2.transforms import polar_to_xy

        spacing = polar_to_xy(spacing, 60) if stagger is not False else [spacing, spacing]  # type: ignore[arg-type,list-item]
    elif isinstance(spacing, (list, tuple, np.ndarray)):
        spacing = [float(spacing[0]), float(spacing[1])]
    elif size is not None:
        if is_num(num_copies):
            spacing = [size[0] / (num_copies - 1), size[1] / (num_copies - 1)]  # type: ignore[operator,list-item]
        elif isinstance(num_copies, (list, tuple, np.ndarray)):
            spacing = [size[0] / (num_copies[0] - 1), size[1] / (num_copies[1] - 1)]
        else:
            div = [1, 1] if stagger is False else [2, 2]
            spacing = [size[0] / div[0], size[1] / div[1]]

    if is_num(num_copies):
        num_copies = [int(num_copies), int(num_copies)]  # type: ignore[arg-type]
    elif isinstance(num_copies, (list, tuple, np.ndarray)):
        num_copies = [int(num_copies[0]), int(num_copies[1])]
    elif size is not None and spacing is not None:
        num_copies = [
            int(math.floor(size[0] / spacing[0])) + 1,  # type: ignore[index]
            int(math.floor(size[1] / spacing[1])) + 1,  # type: ignore[index]
        ]
    else:
        num_copies = [2, 2]

    spacing = np.asarray(spacing, dtype=float)
    offset = spacing * (np.asarray(num_copies) - 1) / 2

    def keep(pos: np.ndarray) -> bool:
        if inside is None:
            return True
        from pybosl2.path2d import Path2D
        from pybosl2.points import Point

        return (
            Path2D.point_in_polygon(
                Point(float(pos[0]), float(pos[1])),
                Path2D(inside) if not isinstance(inside, Path2D) else inside,
                nonzero=bool(nonzero),
            )
            >= 0
        )

    mats: list[np.ndarray] = []
    if stagger is False:
        for row in range(num_copies[1]):
            for col in range(num_copies[0]):
                pos = np.array([col, row]) * spacing - offset
                if keep(pos):
                    mats.append(translate4(permax(pos)))
    else:
        staggermod: int = 1 if stagger == StaggerMode.ALT else 0
        cols1 = math.ceil(num_copies[0] / 2)
        cols2 = num_copies[0] - cols1
        for row in range(num_copies[1]):
            rowcols = cols1 if (row % 2) == staggermod else cols2
            for col in range(rowcols):
                rowdx = spacing[0] if (row % 2) != staggermod else 0.0
                pos = np.array([2 * col, row]) * spacing + np.array([rowdx, 0.0]) - offset
                if keep(pos):
                    mats.append(translate4(permax(pos)))
    return mats


def rot_copies(
    rots: Sequence[float] | None = None,
    v: Point | None = None,
    center: bool | Sequence[float] = (0, 0, 0),
    sa: float = 0,
    offset: float = 0,
    delta: Sequence[float] = (0, 0, 0),
    subrot: bool = True,
    num_copies: int | None = None,
) -> list[np.ndarray]:
    """Return rotated copies about an axis, optionally offset into a ring."""
    assert subrot or np.linalg.norm(_vec3(delta, 0.0)) > 0, (
        "rot_copies(): subrot can only be False when delta is nonzero."
    )
    sang = sa + offset
    if num_copies is not None:
        angs = [] if num_copies <= 0 else [i / num_copies * 360 + sang for i in range(num_copies)]
    elif rots:
        angs = [float(a) for a in rots]
    else:
        angs = []
    cen = _vec3(center, 0.0)
    deltav = _vec3(delta, 0.0)
    mats = []
    for angle in angs:
        rot_m = np.eye(4)
        rot_m[:3, :3] = axis_angle_matrix(angle, UP.vector if v is None else v)
        rot_rev = np.eye(4)
        rev_ang = 0 if subrot else -angle
        rot_rev[:3, :3] = axis_angle_matrix(rev_ang, UP.vector if v is None else v)
        m = translate4(cen) @ rot_m @ translate4(deltav) @ rot_rev @ translate4(-cen)
        mats.append(m)
    return mats


def xrot_copies(
    rots: Sequence[float] | None = None,
    center: bool | Sequence[float] = (0, 0, 0),
    sa: float = 0,
    radius: float | None = None,
    diameter: float | None = None,
    subrot: bool = True,
    num_copies: int | None = None,
) -> list[np.ndarray]:
    """Return rotated copies around the X axis, optionally into a ring of radius *radius*."""
    rr = radius if radius is not None else (diameter / 2 if diameter is not None else 0)
    return rot_copies(
        rots=rots,
        v=RIGHT.vector,
        center=center,
        num_copies=num_copies,
        sa=sa,
        delta=[0, rr, 0],
        subrot=subrot,
    )


def yrot_copies(
    rots: Sequence[float] | None = None,
    center: bool | Sequence[float] = (0, 0, 0),
    sa: float = 0,
    radius: float | None = None,
    diameter: float | None = None,
    subrot: bool = True,
    num_copies: int | None = None,
) -> list[np.ndarray]:
    """Return rotated copies around the Y axis, optionally into a ring of radius *radius*."""
    rr = radius if radius is not None else (diameter / 2 if diameter is not None else 0)
    return rot_copies(
        rots=rots,
        v=BACK.vector,
        center=center,
        num_copies=num_copies,
        sa=sa,
        delta=[-rr, 0, 0],
        subrot=subrot,
    )


def zrot_copies(
    rots: Sequence[float] | None = None,
    center: bool | Sequence[float] = (0, 0, 0),
    sa: float = 0,
    radius: float | None = None,
    diameter: float | None = None,
    subrot: bool = True,
    num_copies: int | None = None,
) -> list[np.ndarray]:
    """Return rotated copies around the Z axis, optionally into a ring of radius *radius*."""
    rr: float = radius if radius is not None else (diameter / 2 if diameter is not None else 0)
    return rot_copies(
        rots=rots,
        v=UP.vector,
        center=center,
        sa=sa,
        delta=[rr, 0, 0],
        subrot=subrot,
        num_copies=num_copies,
    )


def arc_copies(
    radius: float | None = None,
    radius_x: float | None = None,
    radius_y: float | None = None,
    diameter: float | None = None,
    diameter_x: float | None = None,
    diameter_y: float | None = None,
    sa: float = 0,
    ea: float = 360,
    rot: bool = True,
    num_copies: int = 6,
) -> list[np.ndarray]:
    """Return copies spread along an (elliptical) arc in the XY plane."""
    rxv = (
        radius_x
        if radius_x is not None
        else (
            diameter_x / 2
            if diameter_x is not None
            else (radius if radius is not None else (diameter / 2 if diameter is not None else 1))
        )
    )
    ryv = (
        radius_y
        if radius_y is not None
        else (
            diameter_y / 2
            if diameter_y is not None
            else (radius if radius is not None else (diameter / 2 if diameter is not None else 1))
        )
    )
    sa, ea = sa % 360, ea % 360
    extra_n = 1 if abs(ea - sa) < 0.01 else 0
    delt = ((360.0 if ea <= sa else 0) + ea - sa) / (num_copies - 1 + extra_n)
    mats = []
    for i in range(num_copies):
        angle = sa + i * delt
        pos = [
            rxv * math.cos(math.radians(angle)),
            ryv * math.sin(math.radians(angle)),
            0,
        ]
        ang2 = (
            math.degrees(
                math.atan2(
                    ryv * math.sin(math.radians(angle)),
                    rxv * math.cos(math.radians(angle)),
                )
            )
            if rot
            else 0
        )
        rot_mat = np.eye(4)
        rot_mat[:3, :3] = axis_angle_matrix(ang2, UP.vector)
        mats.append(translate4(pos) @ rot_mat)
    return mats


def sphere_copies(
    num_copies: int = 100,
    radius: float | None = None,
    diameter: float | None = None,
    cone_ang: float = 90,
    scale: Sequence[float] = (1, 1, 1),
    perp: bool = True,
) -> list[np.ndarray]:
    """Return copies spread over a sphere/ellipsoid by the golden-spiral method."""
    rr = radius if radius is not None else (diameter / 2 if diameter is not None else 50)
    cnt = math.ceil(num_copies / (cone_ang / 180))
    scalev = _vec3(scale, 1.0)
    mats = []
    for x in range(num_copies):
        theta = (180 * (1 + math.sqrt(5)) * (x + 0.5)) % 360
        phi = math.degrees(math.acos(1 - 2 * (x + 0.5) / cnt))
        th, ph = math.radians(theta), math.radians(phi)
        xyz = np.array(
            [
                rr * math.sin(ph) * math.cos(th),
                rr * math.sin(ph) * math.sin(th),
                rr * math.cos(ph),
            ]
        )
        pos = xyz * scalev
        m = translate4(pos) @ (rot_from_to4(UP, xyz) if perp else np.eye(4))
        mats.append(m)
    return mats


def path_copies(
    path: Sequence[Sequence[float]],
    spacing: float | None = None,
    start_pos: float | None = None,
    dist: Sequence[float] | None = None,
    rotate_children: bool = True,
    closed: bool | None = None,
    num_copies: int | None = None,
) -> list[np.ndarray]:
    """Return copies placed along *path*, oriented to it."""
    from pybosl2.path2d import Path2D
    from pybosl2.path3d import Path3D

    pts = [list(map(float, p)) for p in path]
    closed = bool(getattr(path, "closed", False)) if closed is None else closed
    dim = len(pts[0]) if pts else 2
    length = (Path3D(pts) if dim == 3 else Path2D(pts)).perimeter()
    if dist is not None:
        distances = sorted(float(x) for x in dist)
    elif start_pos is not None:
        if num_copies is not None and spacing is not None:
            distances = [start_pos + i * spacing for i in range(num_copies)]
        elif num_copies is not None:
            distances = list(np.linspace(start_pos, length, num_copies))
        else:
            distances = list(np.arange(start_pos, length, spacing))
    elif num_copies is not None and spacing is None:
        distances = list(np.linspace(0, length, num_copies, endpoint=not closed))
    else:
        assert spacing is not None
        cnt = num_copies if num_copies is not None else int(math.floor(length / spacing)) + (0 if closed else 1)
        ptlist = [i * spacing for i in range(cnt)]
        center = sum(ptlist) / len(ptlist)
        if closed:
            distances = sorted((e - center) % length for e in ptlist)
        else:
            distances = [e + length / 2 - center for e in ptlist]
    assert min(distances) >= -1e-9, "path_copies(): copies don't fit on the path."
    assert max(distances) <= length + 1e-9, "path_copies(): copies don't fit on the path."
    distances = [min(max(dst, 0.0), length) for dst in distances]
    cutlist = (Path3D(pts) if dim == 3 else Path2D(pts)).cut_points(distances, closed=closed, direction=True)
    planar = len(pts[0]) == 2
    mats = []
    for cp in cutlist:
        base = translate4(cp.point)
        if not rotate_children:
            rotm = np.eye(4)
        elif planar:
            rotm = rot_from_to4([0, 1, 0], _vec3(cp.normal, 0.0))
        else:
            xv = np.asarray(cp.direction, dtype=float)
            n = float(np.linalg.norm(xv))
            xv = xv / n if n else xv
            zv = np.asarray(cp.normal, dtype=float)
            n = float(np.linalg.norm(zv))
            zv = zv / n if n else zv
            yv = np.cross(zv, xv)
            n = float(np.linalg.norm(yv))
            yv = yv / n if n else yv
            rotm = np.eye(4)
            rotm[:3, 0], rotm[:3, 1], rotm[:3, 2] = xv, yv, zv
        mats.append(base @ rotm)
    return mats


def mirror_copy(
    v: Sequence[float] = (0, 0, 1),
    offset: float = 0,
    center: bool | list[float] | None = None,
) -> list[np.ndarray]:
    """Return the original plus a mirrored copy across the plane with normal *v*."""
    nv = np.asarray(v, dtype=float)
    nv_norm = float(np.linalg.norm(nv))
    nv = nv / nv_norm if nv_norm else nv
    cen = (
        _vec3(center, 0.0)
        if center is not None and not is_num(center)
        else (center * nv if is_num(center) else np.zeros(3))  # type: ignore[operator]
    )
    off = nv * offset
    mirror_m = np.eye(4)
    mirror_m[:3, :3] = np.eye(3) - 2 * np.outer(nv, nv)
    return [
        translate4(off),
        translate4(np.asarray(cen)) @ mirror_m @ translate4(-np.asarray(cen)) @ translate4(off),
    ]


def xflip_copy(offset: float = 0, x: float = 0) -> list[np.ndarray]:
    """Return the original plus a copy mirrored across the X=*x* plane."""
    return mirror_copy(v=[1, 0, 0], offset=offset, center=[x, 0, 0])


def yflip_copy(offset: float = 0, y: float = 0) -> list[np.ndarray]:
    """Return the original plus a copy mirrored across the Y=*y* plane."""
    return mirror_copy(v=[0, 1, 0], offset=offset, center=[0, y, 0])


def zflip_copy(offset: float = 0, z: float = 0) -> list[np.ndarray]:
    """Return the original plus a copy mirrored across the Z=*z* plane."""
    return mirror_copy(v=[0, 0, 1], offset=offset, center=[0, 0, z])


# ---------------------------------------------------------------------------
# Section: Distributable mixin
# ---------------------------------------------------------------------------


class DistributableMatrix:
    """Return Matrix-generating copiers -- each returns ``list[np.ndarray]`` (4x4 matrices)."""

    line_copies = staticmethod(line_copies)  # -> list[np.ndarray]
    xcopies = staticmethod(xcopies)  # -> list[np.ndarray]
    ycopies = staticmethod(ycopies)  # -> list[np.ndarray]
    zcopies = staticmethod(zcopies)  # -> list[np.ndarray]
    grid_copies = staticmethod(grid_copies)  # -> list[np.ndarray]
    rot_copies = staticmethod(rot_copies)  # -> list[np.ndarray]
    xrot_copies = staticmethod(xrot_copies)  # -> list[np.ndarray]
    yrot_copies = staticmethod(yrot_copies)  # -> list[np.ndarray]
    zrot_copies = staticmethod(zrot_copies)  # -> list[np.ndarray]
    arc_copies = staticmethod(arc_copies)  # -> list[np.ndarray]
    sphere_copies = staticmethod(sphere_copies)  # -> list[np.ndarray]
    path_copies = staticmethod(path_copies)  # -> list[np.ndarray]
    mirror_copy = staticmethod(mirror_copy)  # -> list[np.ndarray]
    xflip_copy = staticmethod(xflip_copy)  # -> list[np.ndarray]
    yflip_copy = staticmethod(yflip_copy)  # -> list[np.ndarray]
    zflip_copy = staticmethod(zflip_copy)  # -> list[np.ndarray]


class Distributable(ABC):
    """Return Mixin adding the distributors.scad copiers as methods.

    Inherited by :class:`~pybosl2.shapes3d.Bosl2Solid`, :class:`~pybosl2.paths.Path2D`, and
    :class:`~pybosl2.paths.Path3D`. Each copier returns a ``list`` of positioned copies;
    callers union, hull, or combine them as needed.
    """

    @abstractmethod
    def _distribute(self, mats: list[np.ndarray]) -> list[_CopyType]:  # pragma: no cover
        raise NotImplementedError("Distributable subclasses must implement _distribute().")

    # -- instance methods ------------------------------------------------------

    def move_and_copy(self, vectors: list[Point] | None = None) -> list[_CopyType]:
        """Copy to each offset in *vectors* (BOSL2 move_copies).

        Args:
            vectors: A list of :class:`~pybosl2.points.Point` offsets, or ``None``
                for a single copy at the origin.

        Returns:
            The union (or list for paths) of copies at each offset.

        """
        offsets = vectors if vectors is not None else [Point(0, 0, 0)]
        return self._distribute([translate4(pos) for pos in offsets])

    def line_copies(
        self,
        spacing: float | None = None,
        length: float | None = None,
        p1: Point | None = None,
        p2: Point | None = None,
        num_copies: int | None = None,
    ) -> list[_CopyType]:
        """Return copies spread along a line."""
        return self._distribute(line_copies(spacing, length, p1, p2, num_copies=num_copies))

    def xcopies(
        self,
        spacing: float | None = None,
        length: float | None = None,
        start_pos: float | Point | None = None,
        num_copies: int | None = None,
    ) -> list[_CopyType]:
        """Return copies spread along the X axis."""
        return self._distribute(_axis_copies(RIGHT.vector, spacing, length, start_pos, num_copies=num_copies))

    def ycopies(
        self,
        spacing: float | None = None,
        length: float | None = None,
        start_pos: float | Point | None = None,
        num_copies: int | None = None,
    ) -> list[_CopyType]:
        """Return copies spread along the Y axis."""
        return self._distribute(_axis_copies(BACK.vector, spacing, length, start_pos, num_copies=num_copies))

    def zcopies(
        self,
        spacing: float | None = None,
        length: float | None = None,
        start_pos: float | Point | None = None,
        num_copies: int | None = None,
    ) -> list[_CopyType]:
        """Return copies spread along the Z axis."""
        return self._distribute(_axis_copies(UP.vector, spacing, length, start_pos, num_copies=num_copies))

    def grid_copies(
        self,
        spacing: float | Sequence[float] | np.ndarray | None = None,
        size: float | Sequence[float] | np.ndarray | None = None,
        stagger: bool | StaggerMode = False,
        inside: Sequence[Sequence[float]] | np.ndarray | None = None,
        nonzero: bool | None = None,
        axes: str = "xy",
        num_copies: int | Sequence[int] | np.ndarray | None = None,
    ) -> list[_CopyType]:
        """Return copies in a square or staggered (hex) grid."""
        return self._distribute(grid_copies(spacing, size, stagger, inside, nonzero, axes, num_copies))

    def rot_copies(
        self,
        rots: Sequence[float] | None = None,
        v: Point | None = None,
        center: bool | Sequence[float] = (0, 0, 0),
        sa: float = 0,
        offset: float = 0,
        delta: Sequence[float] = (0, 0, 0),
        subrot: bool = True,
        num_copies: int | None = None,
    ) -> list[_CopyType]:
        """Rotated copies about an axis (optionally into a ring via *delta*)."""
        return self._distribute(rot_copies(rots, v, center, sa, offset, delta, subrot, num_copies=num_copies))

    def xrot_copies(
        self,
        rots: Sequence[float] | None = None,
        center: bool | Sequence[float] = (0, 0, 0),
        sa: float = 0,
        radius: float | None = None,
        diameter: float | None = None,
        subrot: bool = True,
        num_copies: int | None = None,
    ) -> list[_CopyType]:
        """Rotated copies around the X axis."""
        return self._distribute(xrot_copies(rots, center, sa, radius, diameter, subrot, num_copies=num_copies))

    def yrot_copies(
        self,
        rots: Sequence[float] | None = None,
        center: bool | Sequence[float] = (0, 0, 0),
        sa: float = 0,
        radius: float | None = None,
        diameter: float | None = None,
        subrot: bool = True,
        num_copies: int | None = None,
    ) -> list[_CopyType]:
        """Rotated copies around the Y axis."""
        return self._distribute(yrot_copies(rots, center, sa, radius, diameter, subrot, num_copies=num_copies))

    def zrot_copies(
        self,
        rots: Sequence[float] | None = None,
        center: bool | Sequence[float] = (0, 0, 0),
        sa: float = 0,
        radius: float | None = None,
        diameter: float | None = None,
        subrot: bool = True,
        num_copies: int | None = None,
    ) -> list[_CopyType]:
        """Rotated copies around the Z axis."""
        return self._distribute(zrot_copies(rots, center, sa, radius, diameter, subrot, num_copies=num_copies))

    def arc_copies(
        self,
        radius: float | None = None,
        radius_x: float | None = None,
        radius_y: float | None = None,
        diameter: float | None = None,
        diameter_x: float | None = None,
        diameter_y: float | None = None,
        sa: float = 0,
        ea: float = 360,
        rot: bool = True,
        num_copies: int = 6,
    ) -> list[_CopyType]:
        """Return copies spread along an (elliptical) arc in the XY plane."""
        return self._distribute(
            arc_copies(
                radius,
                radius_x,
                radius_y,
                diameter,
                diameter_x,
                diameter_y,
                sa,
                ea,
                rot,
                num_copies=num_copies,
            )
        )

    def sphere_copies(
        self,
        num_copies: int = 100,
        radius: float | None = None,
        diameter: float | None = None,
        cone_ang: float = 90,
        scale: Sequence[float] = (1, 1, 1),
        perp: bool = True,
    ) -> list[_CopyType]:
        """Return copies spread over a sphere/ellipsoid surface."""
        return self._distribute(sphere_copies(num_copies, radius, diameter, cone_ang, scale, perp))

    def path_copies(
        self,
        path: Sequence[Sequence[float]],
        spacing: float | None = None,
        start_pos: float | None = None,
        dist: Sequence[float] | None = None,
        rotate_children: bool = True,
        closed: bool | None = None,
        num_copies: int | None = None,
    ) -> list[_CopyType]:
        """Return copies placed along *path*, oriented to it."""
        return self._distribute(
            path_copies(
                path,
                spacing,
                start_pos,
                dist,
                rotate_children,
                closed,
                num_copies=num_copies,
            )
        )

    def mirror_copy(
        self,
        v: Sequence[float] = (0, 0, 1),
        offset: float = 0,
        center: bool | list[float] | None = None,
    ) -> list[_CopyType]:
        """Return this object plus a copy mirrored across the plane with normal *v*."""
        return self._distribute(mirror_copy(v, offset, center))

    def xflip_copy(self, offset: float = 0, x: float = 0) -> list[_CopyType]:
        """Return This object plus a copy mirrored across the X=*x* plane."""
        return self._distribute(xflip_copy(offset, x))

    def yflip_copy(self, offset: float = 0, y: float = 0) -> list[_CopyType]:
        """Return This object plus a copy mirrored across the Y=*y* plane."""
        return self._distribute(yflip_copy(offset, y))

    def zflip_copy(self, offset: float = 0, z: float = 0) -> list[_CopyType]:
        """Return This object plus a copy mirrored across the Z=*z* plane."""
        return self._distribute(zflip_copy(offset, z))

    # ---------------------------------------------------------------------------
    # Section: distributing a list of distinct children
    # ---------------------------------------------------------------------------

    @staticmethod
    def distribute(
        children: list[BaseShape],
        spacing: float | None = None,
        sizes: list[float] | None = None,
        dir: Anchor | Point = RIGHT,  # noqa: A002
        length: float | None = None,
    ) -> BaseShape:
        """Space a list of distinct objects along *dir* so they don't overlap.

        Unlike the copiers, this lays out several different children.
        *sizes* gives each child's extent along *dir*; auto-computed from bounding boxes if omitted.

        Args:
            children: Objects with ``translate()``, ``bounds()``, and CSG operators.
            spacing: Gap between adjacent children.
            sizes: Per-child extent along *dir*.
            dir: Direction vector (default +X).
            length: Total length to fill.

        Returns:
            The union of all positioned children.

        """
        children = list(children)
        dir_arr = _vec3(dir, 0.0) if is_num(dir) else np.asarray(dir, dtype=float)
        dir_norm = float(np.linalg.norm(dir_arr))
        dirv = dir_arr / dir_norm if dir_norm else dir_arr
        cnt = len(children)
        assert cnt >= 1, "distribute(): needs at least one child."
        if sizes is None:
            extents = [
                abs(float(np.dot(np.asarray(c.bounds()[1]), dirv) - np.dot(np.asarray(c.bounds()[0]), dirv)))
                for c in children
            ]
        else:
            extents = [float(s) for s in sizes]
        gaps = [0.0] if cnt < 2 else [extents[i] / 2 + extents[i + 1] / 2 for i in range(cnt - 1)]
        spc = (
            ((length - sum(gaps)) / (cnt - 1))
            if (length is not None and cnt > 1)
            else (spacing if spacing is not None else 10)
        )
        gaps2 = [g + spc for g in gaps]
        positions = np.cumsum([0.0] + gaps2)
        start = -sum(gaps2) / 2 * dirv
        placed = [c.translate((start + positions[i] * dirv).tolist()) for i, c in enumerate(children)]
        out = placed[0]
        for c in placed[1:]:
            out = out | c
        return out


# -- module-level convenience wrappers for the static distribute ---------------
#    (the full implementation is on Distributable, above)


def xdistribute(
    children: list[BaseShape],
    spacing: float | None = None,
    sizes: list[float] | None = None,
    length: float | None = None,
) -> BaseShape:
    """Distribute distinct children along the X axis.

    Examples:
        .. pythonscad-example::

            from pybosl2.solid import cuboid
            from pybosl2.distributors import xdistribute

            xdistribute(spacing=15, children=[cuboid([5, 5, 20]) for _ in range(5)]).show()

    """
    return Distributable.distribute(children, spacing=spacing, sizes=sizes, dir=RIGHT, length=length)


def ydistribute(
    children: list[BaseShape],
    spacing: float | None = None,
    sizes: list[float] | None = None,
    length: float | None = None,
) -> BaseShape:
    """Distribute distinct children along the Y axis."""
    return Distributable.distribute(children, spacing=spacing, sizes=sizes, dir=BACK, length=length)


def zdistribute(
    children: list[BaseShape],
    spacing: float | None = None,
    sizes: list[float] | None = None,
    length: float | None = None,
) -> BaseShape:
    """Distribute distinct children along the Z axis."""
    return Distributable.distribute(children, spacing=spacing, sizes=sizes, dir=UP, length=length)
