# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/sdf/skin.py
#    SDF-based sweep / skin / loft / revolve operations, mirroring the geometry-construction
#    endpoints of pybosl2/skin.py.
#

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pybosl2.exceptions import Bosl2ValueError
from pybosl2.sdf._libfive import lv
from pybosl2.sdf.paths import _lv_hypot
from pybosl2.sdf.shapes3d import PyShape

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pybosl2.sdf.shapes2d import PyShape2D

# ---------------------------------------------------------------------------
#  SDF sweep / skin / revolve
# ---------------------------------------------------------------------------


def _clamp(v: float, lo: float, hi: float) -> float:
    """Clamp *v* between *lo* and *hi* using libfive min/max (no native clamp op)."""
    return lv.max(lo, lv.min(hi, v))  # type: ignore[no-any-return]


def _revolve_sdf(
    shape2d: PyShape2D,
    angle: float = 360,
    _fn: int | None = None,
    res: int = 10,
) -> PyShape:
    """Revolve a 2-D SDF profile around the Z axis, returning a 3-D PyShape.

    The 2-D profile is evaluated with its X coordinate as the radial distance from
    the Z axis and its Y coordinate as the height.  A full 360° revolution produces
    a watertight solid; a partial revolution is end-capped to the axis.

    This is the SDF analogue of bosl2.skin.rotate_sweep(): the revolved volume is
    represented directly as a signed-distance field rather than as a triangulated mesh.

    Args:
        shape2d:  a PyShape2D whose SDF is ``f(radius, z)``
        angle:    degrees to revolve (default 360 for full solid of revolution)
        _fn:      facet count for circular sampling (auto if None)
        res:      meshing resolution (default 10)

    """
    sf = shape2d._sdf_fn
    full_rev = abs(angle - 360.0) < 1e-9
    half_angle = math.radians(angle) / 2

    def sdf_fn(x, y, z):  # type: ignore[no-untyped-def]
        r = _lv_hypot(x, y)
        d2d = sf(r, z)

        if full_rev:
            return d2d

        # Partial revolution: cap at the two radial planes that bound the arc.
        # For a revolve from -half_angle to +half_angle (centred on XZ plane),
        # points outside this wedge are capped.
        theta = lv.atan2(y, x)
        d_ang0 = lv.max(-theta - half_angle, theta - half_angle)
        d_cap = lv.max(d_ang0 * r, 0)
        return lv.max(d2d, d_cap)

    mn = shape2d.mn
    mx = shape2d.mx
    max_r = max(abs(mn[0]), abs(mx[0]))
    max_z = max(abs(mn[1]), abs(mx[1]))
    return PyShape(sdf_fn, [-max_r, -max_r, -max_z], [max_r, max_r, max_z], res)


def _linear_sweep_sdf(
    shape2d: PyShape2D,
    height: float = 1.0,
    twist: float = 0.0,
    scale: float | Sequence[float] = 1.0,
    shift: Sequence[float] = (0.0, 0.0),
    center: bool = False,
    slices: int | None = None,
    res: int = 10,
) -> PyShape:
    """Extrude a 2-D SDF shape vertically with optional twist, scale, and XY shift,.

    returning a 3-D PyShape.

    The result is one continuous field: a query point is mapped back through the sweep's own
    transform at its height and tested against the 2-D profile, so the twist and taper are exact
    rather than stepped.  A plain extrusion, with no twist/scale/shift, delegates to
    ``shape2d.extrude()``.

    Args:
        shape2d:  the 2-D cross-section to extrude
        height:   extrusion height (default 1)
        twist:    total degrees of twist over *height* (default 0)
        scale:    final scale factor or ``[sx, sy]`` at the top (default 1)
        shift:    XY displacement of the top relative to the bottom (default [0, 0])
        center:   centre the extrusion on Z (default: sits on z=0..height)
        slices:   ignored -- the field is continuous, so there is nothing to subdivide
                  (accepted so the signature matches the CSG sweep)
        res:      meshing resolution (default 10)

    """
    _ = slices  # the field is continuous, so there are no slices to choose
    sf = shape2d._sdf_fn
    sx = float(scale) if isinstance(scale, (int, float)) else float(scale[0])
    sy = float(scale) if isinstance(scale, (int, float)) else float(scale[1])
    shx, shy = float(shift[0]), float(shift[1])

    # Compared numerically: `shift != (0.0, 0.0)` read the default *list* [0, 0] as a request and
    # took the swept path for what is a plain extrusion.
    has_modifiers = (
        abs(twist) > 1e-9 or abs(sx - 1.0) > 1e-9 or abs(sy - 1.0) > 1e-9 or abs(shx) > 1e-9 or abs(shy) > 1e-9
    )
    if not has_modifiers:
        return shape2d.extrude(height, center=center, res=res)

    z0 = -height / 2 if center else 0.0
    twist_rad_total = math.radians(twist)

    mx_r = max(abs(shape2d.mn[0]), abs(shape2d.mx[0]))
    my_r = max(abs(shape2d.mn[1]), abs(shape2d.mx[1]))

    def sdf_fn(x, y, z):  # type: ignore[no-untyped-def]
        z_local = z - z0
        u = _clamp(z_local / height, 0, 1)

        su_s = 1.0 + u * (sx - 1.0)
        su_y = 1.0 + u * (sy - 1.0)

        # The CSG sweep (pybosl2/skin.py:_linear_sweep) maps a profile point q to
        # ``translate(u*shift) @ scale(su) @ zrot(-twist*u) @ q``, so getting back to the profile
        # means undoing that in reverse: unshift, unscale, then unrotate. Applying them in the
        # written order instead put the top face at ``scale * shift`` rather than ``shift``, and
        # turned the twist the opposite way to the CSG backend for the same twist= argument.
        x_sh = x - u * shx
        y_sh = y - u * shy

        x_sc = x_sh / lv.max(su_s, 1e-9)
        y_sc = y_sh / lv.max(su_y, 1e-9)

        angle = twist_rad_total * u
        x_loc = x_sc * lv.cos(angle) - y_sc * lv.sin(angle)
        y_loc = x_sc * lv.sin(angle) + y_sc * lv.cos(angle)

        d2d = sf(x_loc, y_loc)
        d_axis = lv.max(z_local - height, -z_local)
        return lv.max(d2d, d_axis)

    # A twist turns the profile about Z, so a corner can swing onto either axis: the bound is the
    # profile's circumscribed radius, not its half-width, or the mesh clips off the swept corners
    # (a 10x10 square twisted 45 degrees reaches 7.07, well outside the +/-5 this used to claim).
    if abs(twist) > 1e-9:
        mx_r = my_r = math.hypot(mx_r, my_r)
        max_scale_x = max_scale_y = max(1.0, abs(sx), abs(sy))
    else:
        max_scale_x, max_scale_y = max(1.0, abs(sx)), max(1.0, abs(sy))
    bbx = mx_r * max_scale_x + abs(shx)
    bby = my_r * max_scale_y + abs(shy)
    mn = [-bbx, -bby, z0]
    mx = [bbx, bby, z0 + height]
    return PyShape(sdf_fn, mn, mx, res)


def skin_sdf(
    shapes: Sequence[PyShape2D],
    z: Sequence[float],
    res: int = 10,
) -> PyShape:
    """Loft a solid between stacked 2-D SDF cross-sections at specified Z heights,.

    returning a 3-D PyShape.

    For a query point in 3-D, the signed distance is computed by projecting the point
    onto the nearest vertical span between two adjacent profiles, linearly blended by
    height, then evaluated against the interpolated 2-D SDF.

    Args:
        shapes:  list of PyShape2D cross-sections, bottom to top
        z:       z-coordinates for each cross-section (must be strictly increasing)
        res:     meshing resolution (default 10)

    """
    if not (len(shapes) >= 2):
        raise Bosl2ValueError("skin_sdf(): need at least 2 profiles")
    if not (len(shapes) == len(z)):
        raise Bosl2ValueError("skin_sdf(): shapes and z must have same length")

    sfs = [s._sdf_fn for s in shapes]
    zs = [float(zi) for zi in z]
    n = len(zs)

    max_r = 0.0
    for s in shapes:
        max_r = max(max_r, abs(s.mn[0]), abs(s.mx[0]), abs(s.mn[1]), abs(s.mx[1]))

    def sdf_fn(x, y, z_val):  # type: ignore[no-untyped-def]
        # Clamp z between bottom and top
        z_clamped = lv.max(zs[0], lv.min(zs[-1], z_val))

        # Find the two profiles to blend between.
        # Build a piecewise blend using min/max: for each segment i, the contribution is
        #   (z_clamped - zs[i]) * (diameter1 - d0) / (zs[i+1] - zs[i]) + d0
        # We take the result from the segment that z_clamped falls into by using
        # a weighted combination that collapses to the right segment.
        d_result = None
        for i in range(n - 1):
            dz = zs[i + 1] - zs[i]
            t = (z_clamped - zs[i]) / dz
            # Clamp t to [0, 1] for this segment
            t = lv.max(0, lv.min(1, t))
            d0 = sfs[i](x, y)
            diameter1 = sfs[i + 1](x, y)
            d_seg = d0 + t * (diameter1 - d0)
            # Only this segment contributes where z is actually in [zs[i], zs[i+1]]
            in_seg = -lv.max(zs[i] - z_val, z_val - zs[i + 1])
            d_seg = lv.max(d_seg, in_seg)
            d_result = d_seg if d_result is None else lv.min(d_result, d_seg)

        assert d_result is not None
        # Add vertical caps
        d_result = lv.max(d_result, zs[0] - z_val)
        d_result = lv.max(d_result, z_val - zs[-1])
        return d_result

    return PyShape(sdf_fn, [-max_r, -max_r, zs[0]], [max_r, max_r, zs[-1]], res)


def mesh_to_vnf(shape: PyShape) -> tuple[list[list[float]], list[list[int]]]:
    """Extract a vertices-and-faces pair from a meshed PyShape.

    Meshes *shape* and reads the triangles back out of the native solid
    (``solid.mesh()``), returning a plain ``(vertices, faces)`` tuple in BOSL2's
    VNF convention -- wound counter-clockwise seen from outside, the way
    :class:`~pybosl2.vnf.VNF` wants them (:meth:`~pybosl2.vnf.VNF.polyhedron`
    reverses them again on the way back to native geometry).

    Args:
        shape:  a PyShape (will be meshed if not already cached)

    Returns:
        ``(vertices, faces)`` where *vertices* is ``[[x,y,z], ...]`` and
        *faces* is ``[[i, j, k], ...]`` of vertex indices.

    Note:
        Under the numeric test mock there is no mesher, so its stand-in returns sampled
        interior points and no faces; real topology needs the PythonSCAD app.

    """
    verts, faces = shape.mesh().mesh()
    return (
        [[float(v[0]), float(v[1]), float(v[2])] for v in verts],
        [[int(i) for i in f] for f in faces],
    )
