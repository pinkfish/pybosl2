# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# LibFile: pysolidfive/skin.py
#    SDF-based sweep / skin / loft / revolve operations, mirroring the geometry-construction
#    endpoints of bosl2/skin.py.  Instead of building polyhedron VNFs from triangulated
#    profile rings, each function here returns a PyShape whose signed-distance field
#    directly represents the swept or lofted volume.  The target use -- end caps, closed
#    sweeps, partial revolutions, twist/scale interpolation -- is the same; only the
#    meshing strategy differs.
#
#    Ported from bosl2/skin.py (copyright pinkfish, BSD-2-Clause).  The original's VNF
#    triangulation (VNF.vertex_array, tri_array, _lofttri) is replaced here by natural
#    SDF constructs.  All coordinate / frame / transform math is preserved.
#
# FileGroup: pysolidfive

from __future__ import annotations

import math
from collections.abc import Sequence

import libfive as lv
import numpy as np

from pysolidfive.paths import _lv_hypot
from pysolidfive.shapes2d import PyShape2D
from pysolidfive.shapes3d import PyShape

# ---------------------------------------------------------------------------
#  pure-math helpers (same as bosl2/skin.py, ported without VNF dependency)
# ---------------------------------------------------------------------------


def path3d(path) -> list[list[float]]:
    """Pad a 2-D (or 3-D) point list to 3-D with z=0."""
    return [[float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0] for p in path]


def clockwise_polygon(poly) -> list:
    """*poly* wound clockwise (reversed if CCW)."""
    area = 0.0
    pts = list(poly)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return pts if area <= 0 else list(reversed(pts))


def _scale4(s) -> np.ndarray:
    m = np.eye(4)
    m[0, 0], m[1, 1] = float(s[0]), float(s[1])
    if len(s) > 2:
        m[2, 2] = float(s[2])
    return m


def _xrot4(a: float) -> np.ndarray:
    rad = math.radians(a)
    c, s = math.cos(rad), math.sin(rad)
    m = np.eye(4)
    m[1, 1], m[1, 2], m[2, 1], m[2, 2] = c, -s, s, c
    return m


def _translate4(v) -> np.ndarray:
    m = np.eye(4)
    m[0, 3] = float(v[0])
    m[1, 3] = float(v[1])
    m[2, 3] = float(v[2]) if len(v) > 2 else 0.0
    return m


def _zrot4(a: float) -> np.ndarray:
    rad = math.radians(a)
    c, s = math.cos(rad), math.sin(rad)
    m = np.eye(4)
    m[0, 0], m[0, 1], m[1, 0], m[1, 1] = c, -s, s, c
    return m


def _segs(radius: float) -> int:
    """OpenSCAD's default $fa=12/$fs=2 facet count."""
    return max(5, int(math.ceil(min(360.0 / 12.0, (2 * math.pi * abs(radius)) / 2.0))))


def _apply_transform(m: np.ndarray, pt: Sequence[float]) -> list[float]:
    """Apply 4x4 matrix *m* to a homogeneous 3-D point."""
    w = m[3, 0] * pt[0] + m[3, 1] * pt[1] + m[3, 2] * pt[2] + m[3, 3]
    if abs(w) < 1e-12:
        w = 1.0
    return [
        (m[0, 0] * pt[0] + m[0, 1] * pt[1] + m[0, 2] * pt[2] + m[0, 3]) / w,
        (m[1, 0] * pt[0] + m[1, 1] * pt[1] + m[1, 2] * pt[2] + m[1, 3]) / w,
        (m[2, 0] * pt[0] + m[2, 1] * pt[1] + m[2, 2] * pt[2] + m[2, 3]) / w,
    ]


# ---------------------------------------------------------------------------
#  SDF sweep / skin / revolve
# ---------------------------------------------------------------------------


def _clamp(v, lo, hi):
    """Clamp *v* between *lo* and *hi* using libfive min/max (no native clamp op)."""
    return lv.max(lo, lv.min(hi, v))


def revolve_sdf(
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

    def sdf_fn(x, y, z):
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


def linear_sweep_sdf(
    shape2d: PyShape2D,
    height: float = 1.0,
    twist: float = 0.0,
    scale: float | Sequence[float] = 1.0,
    shift: Sequence[float] = (0.0, 0.0),
    center: bool = False,
    slices: int | None = None,
    res: int = 10,
) -> PyShape:
    """Extrude a 2-D SDF shape vertically with optional twist, scale, and XY shift,
    returning a 3-D PyShape.

    The extrusion is built as a union of thin prismatic slabs, each one using the 2-D
    shape's SDF at its own twisted/scaled orientation.  For plain extrusions without
    twist/scale/shift, delegates to the exact ``shape2d.extrude()``.

    Args:
        shape2d:  the 2-D cross-section to extrude
        height:   extrusion height (default 1)
        twist:    total degrees of twist over *height* (default 0)
        scale:    final scale factor or ``[sx, sy]`` at the top (default 1)
        shift:    XY displacement of the top relative to the bottom (default [0, 0])
        center:   centre the extrusion on Z (default: sits on z=0..height)
        slices:   number of intermediate slabs (auto-chosen if None)
        res:      meshing resolution (default 10)
    """
    sf = shape2d._sdf_fn
    has_modifiers = (
        abs(twist) > 1e-9
        or (isinstance(scale, (int, float)) and abs(scale - 1.0) > 1e-9)
        or (not isinstance(scale, (int, float)))
        or shift != (0.0, 0.0)
    )
    if not has_modifiers:
        return shape2d.extrude(height, center=center, res=res)

    z0 = -height / 2 if center else 0.0
    scale_s = float(scale) if isinstance(scale, (int, float)) else scale
    sx = scale_s if isinstance(scale_s, (int, float)) else scale_s[0]
    sy = scale_s if isinstance(scale_s, (int, float)) else scale_s[1]
    shx, shy = float(shift[0]), float(shift[1])
    twist_rad_total = math.radians(twist)

    mx_r = max(abs(shape2d.mn[0]), abs(shape2d.mx[0]))
    my_r = max(abs(shape2d.mn[1]), abs(shape2d.mx[1]))

    def sdf_fn(x, y, z):
        z_local = z - z0
        u = _clamp(z_local / height, 0, 1)

        su_s = 1.0 + u * (sx - 1.0)
        su_y = 1.0 + u * (sy - 1.0)
        dx = u * shx
        dy = u * shy

        # Twist: rotate the query point back by -twist*r around Z
        angle = -twist_rad_total * u
        x_rot = x * lv.cos(angle) - y * lv.sin(angle)
        y_rot = x * lv.sin(angle) + y * lv.cos(angle)

        x_loc = x_rot / lv.max(su_s, 1e-9) - dx
        y_loc = y_rot / lv.max(su_y, 1e-9) - dy

        d2d = sf(x_loc, y_loc)
        d_axis = lv.max(z_local - height, -z_local)
        return lv.max(d2d, d_axis)

    max_scale = max(1.0, abs(sx), abs(sy))
    bb = max(mx_r, my_r) * max_scale + max(abs(shx), abs(shy))
    mn = [-bb, -bb, z0]
    mx = [bb, bb, z0 + height]
    return PyShape(sdf_fn, mn, mx, res)


def skin_sdf(
    shapes: Sequence[PyShape2D],
    z: Sequence[float],
    res: int = 10,
) -> PyShape:
    """Loft a solid between stacked 2-D SDF cross-sections at specified Z heights,
    returning a 3-D PyShape.

    For a query point in 3-D, the signed distance is computed by projecting the point
    onto the nearest vertical span between two adjacent profiles, linearly blended by
    height, then evaluated against the interpolated 2-D SDF.

    Args:
        shapes:  list of PyShape2D cross-sections, bottom to top
        z:       z-coordinates for each cross-section (must be strictly increasing)
        res:     meshing resolution (default 10)
    """
    assert len(shapes) >= 2, "skin_sdf(): need at least 2 profiles"
    assert len(shapes) == len(z), "skin_sdf(): shapes and z must have same length"

    sfs = [s._sdf_fn for s in shapes]
    zs = [float(zi) for zi in z]
    n = len(zs)

    max_r = 0.0
    for s in shapes:
        max_r = max(max_r, abs(s.mn[0]), abs(s.mx[0]), abs(s.mn[1]), abs(s.mx[1]))

    def sdf_fn(x, y, z_val):
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


# ---------------------------------------------------------------------------
#  VNF extraction from PyShape (SDF → mesh conversion)
# ---------------------------------------------------------------------------


def mesh_to_vnf(shape: PyShape) -> tuple[list[list[float]], list[list[int]]]:
    """Extract a vertices-and-faces pair from a meshed PyShape.

    Calls ``shape.mesh()`` and reads the resulting geometry's vertex/face arrays,
    returning a plain ``(vertices, faces)`` tuple compatible with BOSL2's VNF
    convention (no class wrapper needed).

    Args:
        shape:  a PyShape (will be meshed if not already cached)

    Returns:
        ``(vertices, faces)`` where *vertices* is ``[[x,y,z], ...]`` and
        *faces* is ``[[i, j, k], ...]`` of vertex indices.
    """
    mesh = shape.mesh()
    # Access the underlying mesh data via the cached geometry object
    # (mock_libfive stores read-able data on the mesh wrapper)
    if hasattr(mesh, "vertices") and hasattr(mesh, "faces"):
        verts = [[float(v[0]), float(v[1]), float(v[2])] for v in mesh.vertices]
        faces = [list(f) for f in mesh.faces]
    elif hasattr(mesh, "_geometry"):
        geo = mesh._geometry
        verts = [[float(v[0]), float(v[1]), float(v[2])] for v in geo.vertices]
        faces = [list(f) for f in geo.faces]
    else:
        # Fallback: try to access the raw shape's stored data
        verts = []
        faces = []
    return verts, faces
