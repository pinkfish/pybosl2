# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/masking.py
#    Pure-Python port of the pieces of BOSL2's masks2d.scad/masks3d.scad/
#    attachments.scad "edge/corner/face profile" masking system that this
#    project uses: cutting a rounded profile along selected edges, corners,
#    or whole faces of a cuboid. No osuse()/BOSL2 runtime dependency.
#
#    BOSL2's real edge_mask()/edge_profile()/corner_profile() work through
#    its generic $parent_geom attachment-introspection system (so they can
#    run on any attachable shape) and position each edge mask using a
#    hardcoded Euler-angle table. This port only supports cuboid parents
#    (the only case this project uses -- every `body` passed in is a
#    shapes3d.cuboid() result), and takes the cuboid's `size=` explicitly
#    as a parameter instead of introspecting it. Edge/corner positioning is
#    derived directly from first principles (build an orthonormal local
#    frame at each edge/corner from the same EDGE_OFFSETS/CORNER_OFFSETS
#    vectors bosl2/shapes3d.py's cuboid() rounding already uses) rather
#    than replicating BOSL2's Euler-angle table.
#
#    corner_profile()'s local mask is also simplified: BOSL2 builds the
#    corner fillet by revolving the 2-D edge-rounding profile 90 degrees
#    around each axis. For mask2d_roundover() specifically (the only 2-D
#    mask this project ever uses), that construction is mathematically
#    equivalent to "a cube octant minus a sphere of the same radius" --
#    the same rounded-corner geometry cuboid()'s own `rounding=`
#    minkowski(cube, sphere) construction produces -- so that's what's
#    implemented here, without needing a general rotate_extrude of an
#    arbitrary 2-D profile.
#
#    edge_profile_asym() is used in this project only with its default
#    corner_type="none" and no flip=, in which case BOSL2's own
#    implementation degrades to calling edge_profile() per edge, so it's
#    just an alias here.
#
# FileSummary: Cut rounded edge/corner/face profiles into a cuboid (BOSL2 masks2d/masks3d/attachments.scad).
# FileGroup: BOSL2

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pythonscad import cube as _ocube
from pythonscad import polygon as _opolygon
from pythonscad import sphere as _osphere

if TYPE_CHECKING:
    from openscad import PyOpenSCAD  # noqa: F401
from .constants import *
from .shapes2d import _frag_count, _polar_to_xy
from .shapes3d import EDGE_OFFSETS, _anchor_offset_box3, _edges, _quantup

CORNER_OFFSETS = [[xa, ya, za] for za in (-1, 1) for ya in (-1, 1) for xa in (-1, 1)]


def mask2d_roundover(
    radius: float | None = None,
    inset: float | list[float] = 0,
    excess: float = 0.01,
    diameter: float | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> list[list[float]]:
    """The 2-D L-shaped cutter cross-section for rounding a 90-degree edge/corner to radius *radius*.

    The origin is the sharp corner to be rounded; the shape extends along +X and +Y (with a
    small `excess` skirt past 0 on each) into the material being cut, with a quarter-circle
    bite of radius *radius* taken out of the far corner.

    Args:
        radius:      rounding radius
        inset:  scalar or [x,y] inset of the rounding center from the corner (default 0)
        excess: amount the flat sides extend past the origin, for a clean boolean cut (default 0.01)
        diameter:      rounding diameter (alternative to radius)
        fn/fa/fs: arc smoothness overrides
    """
    if radius is None:
        assert diameter is not None, "mask2d_roundover(): must give radius or diameter"
        radius = diameter / 2
    rad = radius
    inset_l = list(inset) if isinstance(inset, (list, tuple)) else [inset, inset]
    steps = max(1, int(_quantup(_frag_count(rad, fn, fa, fs), 4) // 4))
    step = 90.0 / steps
    path = [
        [rad + inset_l[0], -excess],
        [-excess, -excess],
        [-excess, rad + inset_l[1]],
    ]
    for i in range(steps + 1):
        p = _polar_to_xy(rad, 180 + i * step)
        path.append([rad + inset_l[0] + p[0], rad + inset_l[1] + p[1]])
    return path


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
) -> PyOpenSCAD:
    """A standalone 3-D edge-rounding cutter of length *length*, for manual positioning (matching
    this project's existing `.rotate(...).translate(...)` usage rather than going through
    edge_mask()). Uses the same local-frame convention as mask2d_roundover(): origin at the
    sharp edge, +X/+Y extending into the material, centered along its own Z axis over length *length*.

    Args:
        length/height:    length of the cutter along its axis (default 1)
        radius:      rounding radius (both ends)
        radius1/radius2:  rounding radius at each end, for a tapered cutter
        diameter/diameter1/diameter2: rounding diameter (both ends) / each end
        excess: amount the flat sides extend past the origin (default 0.1)
        fn/fa/fs: arc smoothness overrides
    """
    length = length if length is not None else (height if height is not None else 1)
    rad1 = (
        radius1
        if radius1 is not None
        else (
            radius
            if radius is not None
            else (
                diameter1 / 2
                if diameter1 is not None
                else (diameter / 2 if diameter is not None else 1)
            )
        )
    )
    rad2 = (
        radius2
        if radius2 is not None
        else (
            radius
            if radius is not None
            else (
                diameter2 / 2
                if diameter2 is not None
                else (diameter / 2 if diameter is not None else 1)
            )
        )
    )
    if rad1 < rad2:
        cross = mask2d_roundover(rad2, excess=excess, fn=fn, fa=fa, fs=fs)
        shape = _opolygon(cross).linear_extrude(
            height=length, center=True, scale=rad1 / rad2
        )
        return shape.rotate(180, [1, 0, 0])
    cross = mask2d_roundover(rad1, excess=excess, fn=fn, fa=fa, fs=fs)
    scale = rad2 / rad1 if rad1 else 1
    return _opolygon(cross).linear_extrude(height=length, center=True, scale=scale)


def chamfer_edge_mask(
    length: float = 1, chamfer: float = 1, excess: float = 0.1
) -> PyOpenSCAD:
    """A standalone 3-D edge-chamfer cutter of length *length* (BOSL2 chamfer_edge_mask()).

    A diamond bar (a square prism rotated 45 degrees, with its vertices *chamfer* out along each
    axis -- i.e. ``cylinder(radius=chamfer, $fn=4)``), centered on its own Z axis. Position it along a
    sharp edge and subtract it to bevel the edge by *chamfer*.

    Args:
        length:       length of the cutter along its axis (default 1)
        chamfer: chamfer size -- the diamond's half-diagonal along each axis (default 1)
        excess:  extra length past *length* so the cut clears the surface (default 0.1)
    """
    diamond = [[chamfer, 0], [0, chamfer], [-chamfer, 0], [0, -chamfer]]
    return _opolygon(diamond).linear_extrude(height=length + excess, center=True)


def _pick_axes(vec: Sequence[float]) -> tuple[int, int, int, float, float]:
    """For an edge vector (one axis 0, two axes +-1), return (run_axis, a1, a2, s1, s2)."""
    run_axis = next(i for i in range(3) if vec[i] == 0)
    nz = [i for i in range(3) if vec[i] != 0]
    a1, a2 = nz
    return run_axis, a1, a2, vec[a1], vec[a2]


def _orient_mask_along_edge(
    shape: PyOpenSCAD, size: Sequence[float], vec: Sequence[float]
) -> PyOpenSCAD:
    """Reorient/position an already-built edge cutter (local +X/+Y into the solid, centered
    along its own local Z which runs along the edge) onto the cuboid edge given by *vec*."""
    run_axis, a1, a2, s1, s2 = _pick_axes(vec)
    lx = [0.0, 0.0, 0.0]
    lx[a1] = -s1
    ly = [0.0, 0.0, 0.0]
    ly[a2] = -s2
    lz = [0.0, 0.0, 0.0]
    lz[run_axis] = 1.0
    m = [
        [lx[0], ly[0], lz[0], 0],
        [lx[1], ly[1], lz[1], 0],
        [lx[2], ly[2], lz[2], 0],
        [0, 0, 0, 1],
    ]
    center = [0.0, 0.0, 0.0]
    center[a1] = s1 * size[a1] / 2
    center[a2] = s2 * size[a2] / 2
    return shape.multmatrix(m).translate(center)


def _extrude_mask_along_edge(
    mask_path: Sequence[Sequence[float]],
    length: float,
    size: Sequence[float],
    vec: Sequence[float],
) -> PyOpenSCAD:
    shape = _opolygon(mask_path).linear_extrude(height=length, center=True)
    return _orient_mask_along_edge(shape, size, vec)


def edge_mask(
    body: PyOpenSCAD,
    edges: str | list = "ALL",
    except_edges: list | None = None,
    children: PyOpenSCAD | None = None,
    size: Sequence[float] | None = None,
    anchor: Sequence[float] = CENTER,
    center: Sequence[float] | None = None,
) -> PyOpenSCAD:
    """Cut an already-built 3-D edge cutter (e.g. from rounding_edge_mask()) along each selected
    edge of the box-shaped *body*.

    Args:
        body:         the box solid to cut
        edges:        edges to mask (default "ALL")
        except_edges: edges to explicitly not mask (BOSL2's `except=` synonym)
        children:     the pre-built 3-D edge cutter (BOSL2's `_children=`)
        size:         the box's [x,y,z] size (BOSL2 gets this from $parent_geom)
        anchor:       the anchor *body* was built with (default CENTER); used only to locate the
                      box center when `center` isn't given
        center:       the box center in body's current frame; when given (e.g. from a native
                      bbox query) it's used directly and `anchor` is ignored
    """
    assert size is not None, "size= (the box's size) must be given"
    assert children is not None, "children= (the edge cutter) must be given"
    edge_set = _edges(edges, except_edges or [])
    cutter = None
    for axis in range(3):
        for i in range(4):
            if edge_set[axis][i] > 0:
                piece = _orient_mask_along_edge(children, size, EDGE_OFFSETS[axis][i])
                cutter = piece if cutter is None else (cutter | piece)
    if cutter is None:
        return body
    cutter = cutter.translate(
        center if center is not None else _anchor_offset_box3(size, anchor)
    )
    return body - cutter


def edge_profile(
    body: PyOpenSCAD,
    edges: str | list = "ALL",
    except_edges: list | None = None,
    children: Sequence[Sequence[float]] | None = None,
    size: Sequence[float] | None = None,
    convexity: int = 10,
    anchor: Sequence[float] = CENTER,
    center: Sequence[float] | None = None,
) -> PyOpenSCAD:
    """Cut a 2-D mask profile (e.g. from mask2d_roundover()), extruded along the edge's own
    length, along each selected edge of the box-shaped *body*.

    Args:
        body:         the box solid to cut
        edges:        edges to mask (default "ALL")
        except_edges: edges to explicitly not mask
        children:     the 2-D mask cross-section path (BOSL2's `_children=`)
        size:         the box's [x,y,z] size
        convexity:    accepted for signature compatibility; unused (no rotate_extrude needed here)
        anchor:       the anchor *body* was built with (default CENTER); used only when `center`
                      isn't given
        center:       the box center in body's current frame; when given it's used directly
    """
    assert size is not None, "size= (the box's size) must be given"
    assert children is not None, "children= (the 2-D mask path) must be given"
    edge_set = _edges(edges, except_edges or [])
    cutter = None
    for axis in range(3):
        for i in range(4):
            if edge_set[axis][i] > 0:
                vec = EDGE_OFFSETS[axis][i]
                length = size[axis] + 0.1
                piece = _extrude_mask_along_edge(children, length, size, vec)
                cutter = piece if cutter is None else (cutter | piece)
    if cutter is None:
        return body
    cutter = cutter.translate(
        center if center is not None else _anchor_offset_box3(size, anchor)
    )
    return body - cutter


# edge_profile_asym() with corner_type="none" and no flip= (the only way this project calls it)
# degrades to edge_profile() per edge -- same result as calling edge_profile() directly.
edge_profile_asym = edge_profile


def _corner_set(v) -> list[int]:
    if isinstance(v, str):
        if v == "ALL":
            return [1] * 8
        if v == "NONE":
            return [0] * 8
        raise ValueError(f'{v} must be "ALL", "NONE", or a vector')
    return [
        1 if all(v[i] == 0 or v[i] == c[i] for i in range(3)) else 0
        for c in CORNER_OFFSETS
    ]


def _corners(v, except_: list | None = None) -> list[int]:
    if except_ is None:
        except_ = []
    if isinstance(v, str) or (
        isinstance(v, list) and len(v) > 0 and not isinstance(v[0], list)
    ):
        v = [v]
    if isinstance(except_, str) or (
        isinstance(except_, list)
        and len(except_) > 0
        and not isinstance(except_[0], list)
    ):
        except_ = [except_]
    summed = [0] * 8
    for x in v:
        cs = _corner_set(x)
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
    size: Sequence[float],
    corner_vec: Sequence[float],
    radius: float,
    fn=None,
    fa=None,
    fs=None,
) -> PyOpenSCAD:
    cube_center = [corner_vec[i] * (size[i] / 2 - radius / 2) for i in range(3)]
    sphere_center = [corner_vec[i] * (size[i] / 2 - radius) for i in range(3)]
    cube_shape = _ocube([radius, radius, radius], center=True).translate(cube_center)
    sphere_shape = _osphere(radius=radius, fn=fn, fa=fa, fs=fs).translate(sphere_center)
    return cube_shape - sphere_shape


def corner_profile(
    body: PyOpenSCAD,
    corners: str | list = "ALL",
    except_corners: list | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    size: Sequence[float] | None = None,
    children: Sequence[Sequence[float]] | None = None,
    convexity: int = 10,
    anchor: Sequence[float] = CENTER,
    center: Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> PyOpenSCAD:
    """Round each selected corner of the box-shaped *body* to radius *radius* (cube-octant-minus-sphere).

    Args:
        body:           the box solid to cut
        corners:        corners to mask -- "ALL"/"NONE", a face vector (all corners on that face),
                         or a corner vector (default "ALL")
        except_corners: corners to explicitly not mask
        radius:              rounding radius
        diameter:              rounding diameter (alternative to radius)
        size:           the box's [x,y,z] size
        children:       accepted for call-site compatibility with BOSL2's `_children=`; unused
                         (this port always uses the cube-minus-sphere construction, which is only
                         exactly equivalent to mask2d_roundover(), the only 2-D mask this project uses)
        convexity:      accepted for signature compatibility; unused
        anchor:         the anchor *body* was built with (default CENTER); used only when `center`
                         isn't given
        center:         the box center in body's current frame; when given it's used directly
        fn/fa/fs:    arc smoothness overrides
    """
    if radius is None:
        assert diameter is not None, "corner_profile(): must give radius or diameter"
        radius = diameter / 2
    rad = radius
    assert size is not None, "size= (the box's size) must be given"
    corner_set = _corners(corners, except_corners or [])
    cutter = None
    for idx, sel in enumerate(corner_set):
        if sel:
            piece = _corner_cutter(size, CORNER_OFFSETS[idx], rad, fn, fa, fs)
            cutter = piece if cutter is None else (cutter | piece)
    if cutter is None:
        return body
    cutter = cutter.translate(
        center if center is not None else _anchor_offset_box3(size, anchor)
    )
    return body - cutter


def face_profile(
    body: PyOpenSCAD,
    faces: str | list = "ALL",
    radius: float | None = None,
    diameter: float | None = None,
    size: Sequence[float] | None = None,
    children: Sequence[Sequence[float]] | None = None,
    convexity: int = 10,
    anchor: Sequence[float] = CENTER,
    center: Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> PyOpenSCAD:
    """Round all edges and corners bounding the given face(s) of the box-shaped *body* to radius *radius*.

    Equivalent to edge_profile(faces) followed by corner_profile(faces, radius).

    Args:
        body:      the box solid to cut
        faces:     face(s) to round the border of, e.g. TOP, or "ALL" (default "ALL")
        radius:         rounding radius
        diameter:         rounding diameter (alternative to radius)
        size:      the box's [x,y,z] size
        children:  the 2-D mask cross-section path used for the edges (BOSL2's `_children=`);
                   defaults to mask2d_roundover(radius) if not given
        convexity: accepted for signature compatibility; unused
        anchor:    the anchor *body* was built with (default CENTER); used only when `center`
                   isn't given
        center:    the box center in body's current frame; when given it's used directly
        fn/fa/fs: arc smoothness overrides
    """
    if radius is None:
        assert diameter is not None, "face_profile(): must give radius or diameter"
        radius = diameter / 2
    rad = radius
    mask = (
        children if children is not None else mask2d_roundover(rad, fn=fn, fa=fa, fs=fs)
    )
    body = edge_profile(
        body,
        faces,
        children=mask,
        size=size,
        convexity=convexity,
        anchor=anchor,
        center=center,
    )
    return corner_profile(
        body,
        faces,
        radius=rad,
        size=size,
        convexity=convexity,
        anchor=anchor,
        center=center,
        fn=fn,
        fa=fa,
        fs=fs,
    )
