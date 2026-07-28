# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

#    Pure-Python port of the surface generators from BOSL2's skin.scad, building
#    VNFs (pybosl2/vnf.py) that render via polyhedron(). No osuse()/BOSL2 runtime
#    dependency.
#
#    Ported (function forms):
#      * sweep(shape, transforms)   -- skin a shape through a list of 4x4 transforms
#      * path_sweep(shape, path)    -- sweep along a 2-D/3-D path. Frame methods
#          "incremental" (rotation-minimizing frame via the double-reflection
#          algorithm), "manual" (caller normals) and "natural" (the curve's own
#          normal); twist, per-point/interpolated scale, open & closed paths,
#          flat caps on/off, user tangents, and the transforms=True mode.
#      * skin(profiles, slices)     -- blend a stack of profiles (methods "direct"
#          and "reindex")
#      * linear_sweep(region, h)    -- extrude an outline with twist/scale/shift
#      * rotate_sweep(shape, angle) -- revolve a profile around Z
#      * spiral_sweep(poly, h, r)   -- sweep a cross-section along a helix
#      * path_sweep2d(shape, path)  -- sweep a 2-D shape along a 2-D path
#      * rot_resample(rotlist, n)   -- resample a transform list along its screw motion
#      * subdivide_and_slice() / slice_profiles() -- the skin() profile helpers
#
#    NOT ported (they depend on machinery this pure-Python port does not
#    implement, and nothing in the toolkit needs them): the texture engine
#    (texture()/tex_* options), the attachment/anchor system (anchors,
#    sweep_attach()), rounded/chamfered "fancy" end caps, region shapes with
#    holes (use a native linear_extrude/CSG), the skin() "distance"/
#    "fast_distance"/"tangent" vertex-matching methods (and associate_vertices()),
#    and spiral_sweep()'s lead-in tapers.
#

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Sequence, Union

if TYPE_CHECKING:
    from pybosl2.paths import Path, Path3D

import numpy as np

from pybosl2._helpers import translate4, zrot4
from pybosl2.constants import Vec3
from pybosl2.transforms import apply as _apply
from pybosl2.transforms import rot_about_axis, rot_decode, rot_inverse
from pybosl2.vnf import VNF

UP = Vec3([0.0, 0.0, 1.0])
BACK = Vec3([0.0, 1.0, 0.0])


class Sweepable:
    """Mixin adding sweep methods to Path and Path3D."""

    def path_sweep(
        self: Path3D,
        shape: Path,
        method: str = "incremental",
        normal: Sequence[float] | Sequence[Sequence[float]] | None = None,
        closed: bool = False,
        twist: float = 0.0,
        twist_by_length: bool = True,
        scale: Any = (1.0, 1.0),
        scale_by_length: bool = True,
        symmetry: int = 1,
        last_normal: Sequence[float] | None = None,
        tangent: Sequence[Sequence[float]] | None = None,
        uniform: bool = True,
        relaxed: bool = False,
        caps: CapsSpec = None,
        style: str = "min_edge",
        transforms: bool = False,
    ) -> VNF | list[list[list[float]]]:
        """Sweep *shape* along this path (BOSL2 path_sweep())."""
        return _path_sweep(
            shape,
            self,
            method=method,
            normal=normal,
            closed=closed,
            twist=twist,
            twist_by_length=twist_by_length,
            scale=scale,
            scale_by_length=scale_by_length,
            symmetry=symmetry,
            last_normal=last_normal,
            tangent=tangent,
            uniform=uniform,
            relaxed=relaxed,
            caps=caps,
            style=style,
            transforms=transforms,
        )

    def path_sweep2d(
        self: Path,
        shape: Path,
        closed: bool = False,
        caps: CapsSpec = None,
        style: str = "min_edge",
    ) -> VNF:
        """Sweep 2-D *shape* along this 2-D path (BOSL2 path_sweep2d())."""
        return _path_sweep2d(shape, self, closed=closed, caps=caps, style=style)

    def linear_sweep(
        self: Path,
        height: float | None = None,
        twist: float = 0.0,
        scale: Any = 1,
        shift: Sequence[float] = (0.0, 0.0),
        slices: int | None = None,
        center: bool = False,
        caps: CapsSpec = None,
        style: str = "min_edge",
    ) -> VNF:
        """Extrude this 2-D profile linearly with optional twist/scale/shift (BOSL2 linear_sweep())."""
        return _linear_sweep(
            self,
            height=height,
            twist=twist,
            scale=scale,
            shift=shift,
            slices=slices,
            center=center,
            caps=caps,
            style=style,
        )

    def rotate_sweep(
        self: Path,
        angle: float = 360.0,
        caps: CapsSpec = None,
        closed: bool | None = None,
        style: str = "min_edge",
        start: float = 0.0,
    ) -> VNF:
        """Revolve this 2-D profile around the Z axis (BOSL2 rotate_sweep())."""
        return _rotate_sweep(
            self,
            angle=angle,
            caps=caps,
            closed=closed,
            style=style,
            start=start,
        )

    def spiral_sweep(
        self: Path,
        height: float,
        radius: float | None = None,
        turns: float = 1.0,
        radius1: float | None = None,
        radius2: float | None = None,
        diameter: float | None = None,
        diameter1: float | None = None,
        diameter2: float | None = None,
        center: bool = True,
        style: str = "min_edge",
    ) -> VNF:
        """Sweep this 2-D profile along a helix (BOSL2 spiral_sweep())."""
        return _spiral_sweep(
            self,
            height,
            radius=radius,
            turns=turns,
            radius1=radius1,
            radius2=radius2,
            diameter=diameter,
            diameter1=diameter1,
            diameter2=diameter2,
            center=center,
            style=style,
        )


def _u(v: Sequence[float]) -> np.ndarray:
    a = np.asarray(v, dtype=float)
    sides = float(np.linalg.norm(a))
    return a / sides if sides else a


def _u_nd(v: np.ndarray) -> np.ndarray:
    sides = float(np.linalg.norm(v))
    return v / sides if sides else v


def path3d(path: Sequence[Sequence[float]]) -> list[list[float]]:
    """Pad a 2-D (or 3-D) point list to 3-D with z=0.

    The coordinates are converted to plain Python floats, not left as whatever the input held: a
    numpy row in would otherwise leak ``np.float64`` scalars out of an annotation that promises
    ``float``, and those raise SystemError/TypeError at the native FFI boundary (see the note in
    pybosl2/paths.py).
    """
    return [[float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0] for p in path]


def clockwise_polygon(poly: Sequence[Sequence[float]]) -> list[Sequence[float]]:
    """*poly* wound clockwise (reversed if its signed area is positive/CCW)."""
    from pybosl2.paths import Path

    return list(poly) if Path._polygon_area(poly, signed=True) <= 0 else list(reversed(list(poly)))


# (imported from pybosl2._helpers as translate4, zrot4)


def _scale4(s: Sequence[float]) -> np.ndarray:
    m = np.eye(4)
    m[0, 0], m[1, 1] = s[0], s[1]
    if len(s) > 2:
        m[2, 2] = s[2]
    return m


def _xrot4(a: float) -> np.ndarray:
    radius = math.radians(a)
    c, s = math.cos(radius), math.sin(radius)
    m = np.eye(4)
    m[1, 1], m[1, 2], m[2, 1], m[2, 2] = c, -s, s, c
    return m


def _segs(radius: float) -> int:
    """
    OpenSCAD's default $fa=12/$fs=2 facet count for a circle of radius *radius* (BOSL2 segs()).
    """
    return max(5, math.ceil(min(360.0 / 12.0, (2 * math.pi * abs(radius)) / 2.0)))


def frame_map(
    x: Sequence[float] | None = None,
    y: Sequence[float] | None = None,
    z: Sequence[float] | None = None,
) -> np.ndarray:
    """The 4x4 rotation whose columns are the given orthonormal axes (BOSL2 frame_map()).

    Give any two of x/y/z (as 3-vectors); the third is filled in by the cross product.
    """
    xu = _u(x) if x is not None else None
    yu = _u(y) if y is not None else None
    zu = _u(z) if z is not None else None
    if xu is None:
        assert yu is not None and zu is not None
        xu = np.cross(yu, zu)
    elif yu is None:
        assert zu is not None and xu is not None
        yu = np.cross(zu, xu)
    elif zu is None:
        assert xu is not None and yu is not None
        zu = np.cross(xu, yu)
    assert xu is not None and yu is not None and zu is not None
    m = np.eye(4)
    m[:3, :3] = np.column_stack([xu, yu, zu])
    return m


#: A BOSL2 ``caps=`` argument: one bool for both ends, a ``[cap1, cap2]`` pair for each end
#: separately, or None to take the call's own default. Every sweep/skin entry point accepts all
#: three spellings, exactly as BOSL2 does -- see :func:`_norm_caps`.
CapsSpec = Union[bool, Sequence[bool], None]


def _norm_caps(caps: CapsSpec, closed: bool = False, default: bool = True) -> list[bool]:
    """Normalize a :data:`CapsSpec` to a plain ``[cap1, cap2]`` bool pair.

    A single bool (or numpy bool) caps both ends alike, a 2-sequence caps each end separately,
    and None falls back to *default*. A *closed* sweep loops back on itself and so has no ends to
    cap -- it is always uncapped, whatever was asked for.
    """
    if closed:
        return [False, False]
    if caps is None:
        return [default, default]
    if isinstance(caps, (list, tuple, np.ndarray)):
        return [bool(caps[0]), bool(caps[1])]
    return [bool(caps), bool(caps)]


def sweep(
    shape: Sequence[Sequence[float]],
    transforms: Sequence[Sequence[Sequence[float]]],
    closed: bool = False,
    caps: CapsSpec = None,
    style: str = "min_edge",
) -> VNF:
    """Apply each 4x4 transform to the 2-D *shape* and skin the resulting profiles into a VNF.

    Args:
        shape:      a 2-D polygon (list of [x, y] points)
        transforms: list of 4x4 matrices, one per cross section along the path
        closed:     the sweep loops back on itself (no caps)
        caps:       cap the open ends (default: True/True open, none closed); bool or [bool, bool]
        style:      vnf_vertex_array quad-subdivision style
    """
    shape3 = np.asarray(path3d(shape), dtype=float)
    assert len(shape3) >= 3, "shape must be a path of at least 3 points."
    flatcaps = _norm_caps(caps, closed=closed)
    ntrans = len(transforms)
    assert ntrans >= 2, "transforms must be length 2 or more."
    hi = ntrans - (0 if closed else 1)
    points = [np.asarray(_apply(transforms[i % ntrans], shape3), dtype=float) for i in range(hi + 1)]
    return VNF.vertex_array(points, cap1=flatcaps[0], cap2=flatcaps[1], col_wrap=True, style=style)


def _path_sweep(
    shape: Sequence[Sequence[float]],
    path: Sequence[Sequence[float]],
    method: str = "incremental",
    normal: Sequence[float] | Sequence[Sequence[float]] | None = None,
    closed: bool = False,
    twist: float = 0.0,
    twist_by_length: bool = True,
    scale: Any = (1.0, 1.0),
    scale_by_length: bool = True,
    symmetry: int = 1,
    last_normal: Sequence[float] | None = None,
    tangent: Sequence[Sequence[float]] | None = None,
    uniform: bool = True,
    relaxed: bool = False,
    caps: CapsSpec = None,
    style: str = "min_edge",
    transforms: bool = False,
):
    """Sweep the 2-D *shape* along the 2-D/3-D *path*, returning a VNF (or the transform list).

    *method* orients the cross section: "incremental" (rotation-minimizing frame), "manual"
    (using *normal* as a per-point normal list), or "natural" (the path's own normal). *twist*
    (degrees) and *scale* (scalar, 2-vector, per-point vector, or Nx2) are interpolated along the
    path. See BOSL2 path_sweep() for the full semantics.

    Examples:
        Sweeping a small square profile along a helical path into a solid:

        .. pythonscad-example::

            square = [[-3, -3], [3, -3], [3, 3], [-3, 3]]
            helix = [[10 * math.cos(t), 10 * math.sin(t), t * 3] for t in np.linspace(0, 3 * math.pi, 40)]
            Path3D(helix).path_sweep(square).polyhedron().show()
    """
    from pybosl2.paths import Path  # local: keep the import graph acyclic

    caps = _norm_caps(caps, closed=closed)  # a closed loop has no ends to cap
    patharr = np.asarray(path3d(path), dtype=float)
    npts = len(patharr)
    assert npts >= 2, "path must have at least 2 points."

    if tangent is not None:
        tangents = np.array([_u(t) for t in path3d(tangent)])
    else:
        tangents = np.asarray(Path._path_tangents(patharr, closed=closed, uniform=uniform), dtype=float)

    # Resolve the initial/per-point normal.
    if normal is not None:
        narr = np.asarray(normal, dtype=float)
        if narr.ndim == 2:
            normals = np.array([_u(n) for n in narr])
            normal_single = normals[0]
        else:
            normal_single = _u_nd(narr)
            normals = np.tile(normal_single, (npts, 1))
    else:
        normal_single = np.asarray(
            (BACK if (method == "incremental" and abs(tangents[0][2]) > 1 / math.sqrt(2)) else UP),
            dtype=float,
        )
        normals = np.tile(normal_single, (npts, 1))

    if twist_by_length:
        tpathfrac = np.asarray(Path._path_length_fractions(patharr, closed), dtype=float)
    else:
        tpathfrac = np.array([i / (npts - (0 if closed else 1)) for i in range(npts + 1)])
    if scale_by_length:
        spathfrac = np.asarray(Path._path_length_fractions(patharr, closed), dtype=float)
    else:
        spathfrac = np.array([i / (npts - (0 if closed else 1)) for i in range(npts + 1)])

    # Resolve the per-cross-section scale [sx, sy].
    if isinstance(scale, (int, float)) or (np.ndim(scale) == 1 and len(scale) == 2):
        s = [float(scale), float(scale)] if isinstance(scale, (int, float)) else [float(scale[0]), float(scale[1])]  # type: ignore[index]
        if not scale_by_length:
            scalevals = [
                [float(v) for v in ((1 - i / (npts - 1)) * np.array([1.0, 1.0]) + (i / (npts - 1)) * np.array(s))]
                for i in range(npts)
            ]
        else:
            scalevals = [
                [float(v) for v in ((1 - f) * np.array([1.0, 1.0]) + f * np.array(s))] for f in spathfrac[:npts]
            ]
    else:
        scalevals = [[float(x), float(x)] if isinstance(x, (int, float)) else [float(x[0]), float(x[1])] for x in scale]  # type: ignore[index]
    scale_list = [_scale4([sv[0], sv[1], 1.0]) for sv in scalevals]
    if closed:
        scale_list.append(_scale4([scalevals[0][0], scalevals[0][1], 1.0]))

    nprofiles = npts + (1 if closed else 0)

    if method == "incremental":
        t0 = tangents[0]
        radius = normal_single - (normal_single @ t0) * t0
        cur = frame_map(y=radius, z=t0)
        rotations = []
        for i in range(nprofiles):
            rotations.append(cur)
            if i < nprofiles - 1:
                v1 = patharr[(i + 1) % npts] - patharr[i % npts]
                c1 = float(v1 @ v1)
                refl_r = radius - 2 * (v1 @ radius) / c1 * v1
                refl_t = tangents[i % npts] - 2 * (v1 @ tangents[i % npts]) / c1 * v1
                v2 = tangents[(i + 1) % npts] - refl_t
                c2 = float(v2 @ v2)
                radius = refl_r - (2 / c2) * (v2 @ refl_r) * v2
                cur = frame_map(y=radius, z=tangents[(i + 1) % npts])
        if closed:
            reference = rotations[0]
        elif last_normal is None:
            reference = rotations[-1]
        else:
            lt = tangents[-1]
            ln = np.asarray(last_normal, dtype=float)
            reference = frame_map(y=ln - (ln @ lt) * lt, z=lt)
        mismatch = rotations[-1][:3, :3].T @ reference[:3, :3]
        correction_twist = math.degrees(math.atan2(mismatch[1][0], mismatch[0][0]))
        twistfix = correction_twist % (360 / symmetry)
        unscaled = [
            translate4(patharr[i]) @ rotations[i] @ zrot4((twistfix - twist) * tpathfrac[i]) for i in range(npts)
        ]
        if closed:
            unscaled.append(
                translate4(patharr[0])
                @ rotations[0]
                @ zrot4(-correction_twist + correction_twist % (360 / symmetry) - twist)
            )
    elif method == "manual":
        unscaled = []
        for i in range(nprofiles):
            ni, ti = normals[i % npts], tangents[i % npts]
            if relaxed:
                ynormal, znormal = ni, ti - (ni @ ti) * ni
            else:
                ynormal, znormal = ni - (ni @ ti) * ti, ti
            unscaled.append(
                translate4(patharr[i % npts]) @ frame_map(y=ynormal, z=znormal) @ zrot4(-twist * tpathfrac[i])
            )
    elif method == "natural":
        pathnormal = np.asarray(Path._path_normals(patharr, tangents, closed), dtype=float)
        unscaled = [
            translate4(patharr[i % npts])
            @ frame_map(x=pathnormal[i % npts], z=tangents[i % npts])
            @ zrot4(-twist * tpathfrac[i])
            for i in range(nprofiles)
        ]
    else:
        raise AssertionError(f"Unknown method {method!r} (use incremental/manual/natural).")

    transform_list = [unscaled[i] @ scale_list[i] for i in range(len(unscaled))]
    if transforms:
        return transform_list
    shp = clockwise_polygon(shape)
    return sweep(shp, transform_list, closed=False, caps=caps, style=style)


# ---------------------------------------------------------------------------------------------
# skin() -- blend a stack of profiles into a surface
# ---------------------------------------------------------------------------------------------


def _reindex_polygon(reference: Sequence[Sequence[float]], poly: Sequence[Sequence[float]]) -> list[list[float]]:
    """Circularly rotate *poly*'s vertices to best line up with *reference* (BOSL2 reindex_polygon).

    Both must be equal-length point lists. Picks the rotation minimizing the summed vertex
    distance. Winding is not adjusted here (the profiles skin() feeds in are already 3-D).
    """
    ref = np.asarray(reference, dtype=float)
    p = np.asarray(poly, dtype=float)
    sides = len(ref)
    best_k, best_val = 0, None
    for k in range(sides):
        val = float(np.sum(np.linalg.norm(ref - np.roll(p, -k, axis=0), axis=1)))
        if best_val is None or val < best_val:
            best_val, best_k = val, k
    return np.roll(p, -best_k, axis=0).tolist()


def slice_profiles(
    profiles: Sequence[Sequence[Sequence[float]]], slices: int, closed: bool = False
) -> list[list[list[float]]]:
    """Interpolate *slices* extra profiles between each consecutive pair (BOSL2 slice_profiles()).

    *slices* is a count (or a per-segment list). The profiles must all be equal-length point
    lists; the interpolation is vertex-by-vertex."""
    sides = len(profiles)
    nseg = sides - (0 if closed else 1)
    count = list(slices) if isinstance(slices, (list, tuple, np.ndarray)) else [slices] * nseg
    out = []
    for i in range(nseg):
        a = np.asarray(profiles[i], dtype=float)
        b = np.asarray(profiles[(i + 1) % sides], dtype=float)
        steps = int(count[i]) + 1
        for k in range(steps):  # lerpn(..., endpoint=False)
            out.append((a + (b - a) * (k / steps)).tolist())
    if not closed:
        out.append([list(p) for p in profiles[-1]])
    return out


def skin(
    profiles: Sequence[Sequence[Sequence[float]]],
    slices: int,
    refine: float = 1.0,
    method: str = "direct",
    sampling: str | None = None,
    caps: CapsSpec = None,
    closed: bool = False,
    style: str = "min_edge",
    z: Sequence[float] | None = None,
) -> VNF:
    """Blend a stack of 2-D/3-D profiles into a skinned surface, returning a VNF (BOSL2 skin()).

    Consecutive profiles are connected vertex-to-vertex; *slices* extra interpolated profiles are
    inserted between each pair to smooth the transition. Profiles of differing point counts are
    resampled up to the largest (via :meth:`Path._subdivide_path`).

    Args:
        profiles: list of >= 2 closed profiles (each a list of points). If 2-D, give matching *z*.
        slices:   number of interpolated profiles inserted between each pair (int or per-gap list)
        refine:   subdivide every profile by this factor before skinning (default 1)
        method:   "direct" (connect vertex i to vertex i) or "reindex" (rotate each profile to
                  best-align with the previous). The "distance"/"tangent" vertex-matching methods
                  are not ported.
        sampling: "length" or "segment" resampling (default "length")
        caps:     cap the ends (default: True for open, False for closed); bool or [bool, bool]
        closed:   the stack loops back to the first profile (default False)
        style:    vnf_vertex_array quad-subdivision style
        z:        per-profile Z heights, required when the profiles are 2-D

    Examples:
        Skinning a round profile up to a square one (a lofted transition):

        .. pythonscad-example::

            circle = [[6 * math.cos(t), 6 * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
            square = [[-8, -8], [8, -8], [8, 8], [-8, 8]]
            skin([circle, square], slices=20, method="reindex", z=[0, 25]).polyhedron().show()
    """
    profiles = [list(p) for p in profiles]
    sides = len(profiles)
    assert sides > 1, "skin() needs at least two profiles."
    profcount = sides - (0 if closed else 1)
    fullcaps = _norm_caps(caps, closed=closed)
    refine_list = list(refine) if isinstance(refine, (list, tuple)) else [refine] * sides
    method_list = list(method) if isinstance(method, (list, tuple)) else [method] * profcount
    for m in method_list:
        assert m in (
            "direct",
            "reindex",
        ), f"skin(): only the 'direct' and 'reindex' methods are ported (got {m!r})."
    sampling = sampling if sampling is not None else "length"

    dim = len(profiles[0][0])
    if dim == 2:
        assert z is not None and len(z) == sides, "skin(): 2-D profiles need a matching-length z list."
        profiles = [[[pt[0], pt[1], z[i]] for pt in profiles[i]] for i in range(sides)]

    from pybosl2.paths import Path  # local: keep the import graph acyclic

    maxlen = max(refine_list[i] * len(profiles[i]) for i in range(sides))
    resampled = [Path._subdivide_path(profiles[i], sides=maxlen, closed=True, method=sampling) for i in range(sides)]
    fixedprof = [resampled[0]]
    for i in range(1, sides):
        if method[i - 1] == "direct":
            fixedprof.append(resampled[i])
        else:
            fixedprof.append(_reindex_polygon(fixedprof[i - 1], resampled[i]))
    sliced = slice_profiles(fixedprof, slices, closed)
    grid = sliced if not closed else sliced + [sliced[0]]
    vnf = VNF.vertex_array(grid, cap1=fullcaps[0], cap2=fullcaps[1], col_wrap=True, style=style)
    return vnf if vnf.volume() >= 0 else vnf.reverse()


# ---------------------------------------------------------------------------------------------
# linear_sweep() / rotate_sweep() / spiral_sweep()
# ---------------------------------------------------------------------------------------------


def _linear_sweep(
    region: Sequence[Sequence[float]],
    height: float | None = None,
    twist: float = 0.0,
    scale=1,
    shift=(0.0, 0.0),
    slices: int | None = None,
    caps: CapsSpec = None,
    style: str = "default",
    center: bool | None = None,
) -> VNF:
    """Extrude a 2-D outline to *height* with optional twist / scale / shift (BOSL2 linear_sweep()).

    A single closed outline (a Path or point list) is supported -- for a region with holes use a
    native ``linear_extrude`` instead. The bottom sits on Z=0 unless *center* is True.

    Args:
        region: the 2-D outline to extrude (a closed path)
        height: extrusion height (aliases: *height*; default 1)
        twist:  total twist over the height, in degrees (default 0)
        scale:  scale of the top relative to the bottom (scalar or [x, y]; default 1)
        shift:  [x, y] offset of the top relative to the bottom (default [0, 0])
        slices: number of intermediate layers (default: enough for ~5 deg of twist each)
        caps:   cap the ends (default True); bool or [bool, bool]
        center: center the extrusion on Z (default False -> base on Z=0)
        style:  vnf_vertex_array quad-subdivision style

    Examples:
        A twisting, tapering square column:

        .. pythonscad-example::

            square = [[-10, -10], [10, -10], [10, 10], [-10, 10]]
            Path(square).linear_sweep(height=40, twist=120, scale=0.4).polyhedron().show()
    """
    hh = float(height if height is not None else (height if height is not None else 1))
    path = [[p[0], p[1]] for p in region]
    if slices is None:
        slices = max(1, math.ceil(abs(twist) / 5))
    sc = [float(scale), float(scale)] if isinstance(scale, (int, float)) else [float(scale[0]), float(scale[1])]
    sh = [float(shift[0]), float(shift[1])]
    fullcaps = _norm_caps(caps)
    z0 = -hh / 2 if center else 0.0
    base = np.asarray(path3d(path), dtype=float)
    verts = []
    for i in range(slices + 1):
        u = i / slices
        m = (
            translate4([sh[0] * u, sh[1] * u, z0 + hh * u])
            @ _scale4([1 + (sc[0] - 1) * u, 1 + (sc[1] - 1) * u, 1])
            @ zrot4(-twist * u)
        )
        verts.append(np.asarray(_apply(m, base), dtype=float))
    vnf = VNF.vertex_array(verts, cap1=fullcaps[0], cap2=fullcaps[1], col_wrap=True, style=style)
    return vnf if vnf.volume() >= 0 else vnf.reverse()


def _rotate_sweep(
    shape: Sequence[Sequence[float]],
    angle: float = 360.0,
    caps: CapsSpec = None,
    closed: bool | None = None,
    style: str = "min_edge",
    start: float = 0.0,
) -> VNF:
    """Revolve a 2-D *shape* (in the X+ half-plane, x=radius, y=height) around the Z axis (BOSL2 rotate_sweep()).

    A closed *shape* profile makes a solid of revolution; an open path with *caps* is first closed
    to the axis. A full 360-degree revolution loops seamlessly; a partial angle end-caps the sweep.

    Args:
        shape:  the 2-D profile to revolve (x >= 0)
        angle:  revolution angle in degrees, 0 < angle <= 360 (default 360)
        caps:   end-cap a partial revolution / close an open profile to the axis (default: angle < 360)
        closed: legacy inverse of *caps* (give one or the other)
        style:  vnf_vertex_array quad-subdivision style
        start:  starting angle in degrees (default 0)

    Examples:
        Revolving a rounded profile into a spool:

        .. pythonscad-example::

            profile = [[4, -10], [12, -10], [12, -6], [7, -2], [7, 2], [12, 6], [12, 10], [4, 10]]
            Path(profile).rotate_sweep(angle=360).polyhedron().show()
    """
    assert 0 < angle <= 360, "rotate_sweep(): angle must be in (0, 360]."
    # Default: cap a partial revolution / an explicitly-open profile, but never a full one.
    capv = _norm_caps(caps, default=(not closed) if closed is not None else (angle < 360))
    prof = [[p[0], p[1]] for p in shape]
    full = angle >= 360
    if any(capv) and not full:
        prof = [[0.0, prof[0][1]]] + prof + [[0.0, prof[-1][1]]]
    xmax = max(p[0] for p in prof)
    steps = math.ceil(_segs(xmax) * angle / 360) + (0 if full else 1)
    steps = max(steps, 3)
    if full:
        angs = [start + 360.0 * i / steps for i in range(steps)]
    else:
        angs = [start + angle * i / (steps - 1) for i in range(steps)]
    transforms = [zrot4(a) @ _xrot4(90) for a in angs]
    vnf = sweep(
        prof,
        transforms,
        closed=full,
        caps=[(not full) and capv[0], (not full) and capv[1]],
        style=style,
    )
    return vnf if vnf.volume() >= 0 else vnf.reverse()


def _spiral_sweep(
    poly: Sequence[Sequence[float]],
    height: float,
    radius: float | None = None,
    turns: float = 1.0,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    center: bool = True,
    style: str = "min_edge",
) -> VNF:
    """Sweep a 2-D cross-section *poly* along a helix (BOSL2 spiral_sweep(), without lead-in tapers).

    *poly*'s X is the radial offset from the helix radius and its Y is the vertical offset, so a
    small wire cross-section becomes a spring/thread. The lead-in taper options are not ported.

    Args:
        poly:  the 2-D wire cross-section (closed path)
        height:     total height of the spiral
        radius/diameter:   helix radius/diameter (or per-end radius1/radius2 / diameter1/diameter2 for a conical spiral)
        turns: number of turns (default 1)
        center: center the spiral on Z (default True)
        style: vnf_vertex_array quad-subdivision style

    Examples:
        A rectangular-section coil spring:

        .. pythonscad-example::

            section = [[-1.2, -1.2], [1.2, -1.2], [1.2, 1.2], [-1.2, 1.2]]
            Path(section).spiral_sweep(height=40, radius=12, turns=5).polyhedron().show()
    """
    assert height > 0 and turns != 0, "spiral_sweep(): need positive height and nonzero turns."
    rr1 = (
        radius1
        if radius1 is not None
        else (
            radius
            if radius is not None
            else (diameter1 / 2 if diameter1 is not None else (diameter / 2 if diameter is not None else 1))
        )
    )
    rr2 = (
        radius2
        if radius2 is not None
        else (
            radius
            if radius is not None
            else (diameter2 / 2 if diameter2 is not None else (diameter / 2 if diameter is not None else 1))
        )
    )
    poly = [[p[0], p[1]] for p in poly]
    nturns = abs(turns)
    sides = _segs(max(rr1, rr2))
    ang_step = 360.0 / sides
    total = 360.0 * nturns
    steps = math.ceil(total / ang_step)
    angs = [total * i / steps for i in range(steps + 1)]
    z0 = -height / 2 if center else 0.0
    transforms = []
    for a in angs:
        frac = a / total
        rad = rr1 + (rr2 - rr1) * frac
        z = z0 + height * frac
        transforms.append(
            translate4([0, 0, z]) @ zrot4(a * math.copysign(1, turns)) @ translate4([rad, 0, 0]) @ _xrot4(90)
        )
    vnf = sweep(poly, transforms, closed=False, caps=(True, True), style=style)
    return vnf if vnf.volume() >= 0 else vnf.reverse()


def subdivide_and_slice(
    profiles: Sequence[Sequence[Sequence[float]]],
    slices: int,
    numpoints=None,
    method: str = "length",
    closed: bool = False,
) -> list[list[list[float]]]:
    """Resample every profile up to *numpoints* then interpolate *slices* between them (BOSL2 subdivide_and_slice()).

    *numpoints* defaults to the largest profile's length; "lcm" uses the least common multiple of
    the profile lengths. Returns the stacked list of (equal-length) profiles."""
    from pybosl2.paths import Path

    maxsize = max(len(p) for p in profiles)
    if numpoints is None:
        numpoints = maxsize
    elif numpoints == "lcm":
        from functools import reduce

        numpoints = reduce(lambda a, b: a * b // math.gcd(a, b), [len(p) for p in profiles])
    numpoints = round(numpoints)
    assert numpoints >= maxsize, "subdivide_and_slice(): numpoints is smaller than the largest profile."
    fixed = [Path._subdivide_path(p, sides=numpoints, closed=True, method=method) for p in profiles]
    return slice_profiles(fixed, slices, closed)


# ---------------------------------------------------------------------------------------------
# os_circle() / offset_sweep() -- profile-based offset extrusion with rim roundovers
# (BOSL2 rounding.scad: os_circle, offset_sweep)
# ---------------------------------------------------------------------------------------------


class OSType(Enum):
    CIRCLE = "circle"
    SMOOTH = "smooth"
    TEARDROP = "teardrop"
    CHAMFER = "chamfer"
    FLAT = "flat"
    PROFILE = "profile"


@dataclass
class OSProfile:
    type: OSType
    radius: float = 0.0
    height: float = 0.0
    extra: float = 0.0
    cut: float = 0.0
    curvature: float = 0.5
    radius_sign: float = 1.0
    max_angle: float = 45.0
    width: float = 0.0
    points: list[list[float]] = field(default_factory=list)

    def get(self, key, default=None):
        if key == "type":
            return self.type.value
        mapping = {
            "r": "radius",
            "h": "height",
            "k": "curvature",
            "r_sign": "radius_sign",
        }
        attr = mapping.get(key, key)
        if hasattr(self, attr):
            return getattr(self, attr)
        return default

    def __getitem__(self, key):
        if key == "type":
            return self.type.value
        mapping = {
            "r": "radius",
            "h": "height",
            "k": "curvature",
            "r_sign": "radius_sign",
        }
        attr = mapping.get(key, key)
        if hasattr(self, attr):
            return getattr(self, attr)
        raise KeyError(key)

    def __contains__(self, key):
        mapping = {
            "r": "radius",
            "h": "height",
            "k": "curvature",
            "r_sign": "radius_sign",
        }
        attr = mapping.get(key, key)
        return hasattr(self, attr)


def os_circle(radius: float | None = None, height: float | None = None, extra: float = 0.0, **kwargs) -> OSProfile:
    """Circular roundover/flare profile for :func:`offset_sweep` (BOSL2 ``os_circle()``).

    Describes the treatment applied to one rim of the extruded shape:

    * ``radius > 0`` — inward roundover: the rim is eased in (material is *removed*
      from the corner, yielding a convex fillet).
    * ``radius < 0`` — outward flare: extra material is added outside the wall at
      the rim (a concave cove).
    * ``radius == 0`` — square / no treatment (same as passing ``None`` to
      :func:`offset_sweep`).

    Args:
        radius: Roundover radius (positive = roundover, negative = flare).
        height: Height of the rim treatment; defaults to ``abs(radius)``.  Should be
                less than half the extrusion height.
        extra:  Extra extension beyond the nominal arc (useful to close tiny gaps
                from floating-point rounding; default 0).

    Returns:
        A descriptor ``OSProfile`` consumed by :func:`offset_sweep`.
    """
    r_val = radius if radius is not None else kwargs.get("r")
    h_val = height if height is not None else kwargs.get("h")
    assert r_val is not None, "os_circle(): radius is required."
    h_res = float(h_val) if h_val is not None else abs(float(r_val))
    return OSProfile(type=OSType.CIRCLE, radius=float(r_val), height=h_res, extra=float(extra))


def os_smooth(
    cut: float | None = None,
    radius: float | None = None,
    curvature: float | None = None,
    extra: float = 0.0,
    **kwargs,
) -> OSProfile:
    """Continuous curvature (Bézier) profile for :func:`offset_sweep` (BOSL2 ``os_smooth()``).

    Uses a 4th-order Bézier curve to ease the transition between flat and curved edges,
    avoiding sudden changes in curvature.

    Args:
        cut:       Depth of the roundover/flare.
        radius:    Alternative to ``cut`` (aliases it).
        curvature: Smoothness/curvature match parameter between 0 and 1 (default 0.5).
        extra:     Extra extension beyond the nominal curve (default 0).

    Returns:
        A descriptor ``OSProfile`` consumed by :func:`offset_sweep`.
    """
    r_val = radius if radius is not None else kwargs.get("r")
    k_val = curvature if curvature is not None else kwargs.get("k", 0.5)
    val = float(cut) if cut is not None else (float(r_val) if r_val is not None else 1.0)
    sign = 1.0 if val >= 0 else -1.0
    return OSProfile(type=OSType.SMOOTH, cut=abs(val), curvature=float(k_val), radius_sign=sign, extra=float(extra))


def os_teardrop(
    radius: float | None = None,
    height: float | None = None,
    cut: float | None = None,
    max_angle: float = 45.0,
    extra: float = 0.0,
    **kwargs,
) -> OSProfile:
    """Teardrop profile for :func:`offset_sweep` to avoid overhangs in 3D printing (BOSL2 ``os_teardrop()``).

    Transitions from a 1/8th circle into a straight line at ``max_angle`` degrees
    relative to the vertical wall, allowing support-free printing.

    Args:
        radius:    Radius of the circular portion.
        height:    Total height of the treatment (defaults to ``abs(radius)``).
        cut:       Alternative to ``radius`` (aliases it).
        max_angle: Curvature transition angle relative to the wall (default 45.0).
        extra:     Extra extension beyond the nominal curve (default 0).

    Returns:
        A descriptor ``OSProfile`` consumed by :func:`offset_sweep`.
    """
    r_arg = radius if radius is not None else kwargs.get("r")
    h_arg = height if height is not None else kwargs.get("h")
    r_val = float(r_arg) if r_arg is not None else (float(cut) if cut is not None else 1.0)
    h_val = float(h_arg) if h_arg is not None else abs(r_val)
    return OSProfile(type=OSType.TEARDROP, radius=r_val, height=h_val, max_angle=float(max_angle), extra=float(extra))


def os_chamfer(
    width: float | None = None,
    height: float | None = None,
    angle: float | None = None,
    cut: float | None = None,
    extra: float = 0.0,
) -> OSProfile:
    """Chamfer/bevel profile for :func:`offset_sweep` (BOSL2 ``os_chamfer()``).

    Creates a flat bevel transition.

    Args:
        width:  Horizontal width of the chamfer.
        height: Vertical height of the chamfer (defaults to ``width``).
        angle:  Bevel angle in degrees. If given, overrides ``width``.
        cut:    Bevel size (aliases both ``width`` and ``height``).
        extra:  Extra extension beyond the nominal bevel (default 0).

    Returns:
        A descriptor ``OSProfile`` consumed by :func:`offset_sweep`.
    """
    if cut is not None:
        w = float(cut)
        h = float(cut)
    else:
        w = float(width) if width is not None else 1.0
        h = float(height) if height is not None else w
    if angle is not None:
        w = h * math.tan(math.radians(float(angle)))
    return OSProfile(type=OSType.CHAMFER, width=w, height=h, extra=float(extra))


def os_flat() -> OSProfile:
    """Flat end cap profile descriptor representing no treatment (BOSL2 ``os_flat()``)."""
    return OSProfile(type=OSType.FLAT, radius=0.0, height=0.0)


def os_profile(profile: Sequence[Sequence[float]], extra: float = 0.0) -> OSProfile:
    """Custom offset sweep profile descriptor (BOSL2 ``os_profile()``).

    Accepts a list of 2D points `[[x, y], ...]` defining the profile:
    - `x` is the inward radial offset (meaning `delta = -x`).
    - `y` is the height `z`.

    Args:
        profile: Sequence of ``[x, y]`` points. The first must be ``[0, 0]``.
        extra:   Extra extension (default 0).

    Returns:
        A descriptor ``OSProfile`` consumed by :func:`offset_sweep`.
    """
    pts = [[float(p[0]), float(p[1])] for p in profile]
    assert pts and pts[0] == [0.0, 0.0], "os_profile(): First point of the profile must be [0, 0]."
    return OSProfile(type=OSType.PROFILE, points=pts, extra=float(extra))


def _offset_sweep(
    path: Sequence[Sequence[float]],
    height: float,
    bottom=None,
    top=None,
    steps: int = 16,
    caps: CapsSpec = None,
    style: str = "min_edge",
) -> VNF:
    """Extrude a 2-D outline to *height* with optional edge treatments on each rim (BOSL2 ``offset_sweep()``).

    Stacks a sequence of radially-offset outlines along the Z axis. The transition
    from the vertical wall to the flat cap is determined by the *bottom* and *top*
    profiles.

    Supported profiles (offset specifiers):
    - ``os_circle()``: Circular roundover/flare.
    - ``os_smooth()``: Bezier-based continuous curvature G2 smoothing.
    - ``os_teardrop()``: Teardrop profile for support-free 3D printing.
    - ``os_chamfer()``: Straight bevel.
    - ``os_flat()``: Flat cap.
    - ``os_profile()``: User-defined custom 2D profile.

    Args:
        path:   The 2-D polygon to extrude (a closed path or point list).
        height: Total extrusion height (Z from 0 to height).
        bottom: Bottom-rim treatment descriptor (or ``None`` for square).
        top:    Top-rim treatment descriptor (or ``None`` for square).
        steps:  Number of slices/steps per rim treatment (default 16).
        caps:   Cap the flat top and bottom (default True); bool or [bool, bool].
        style:  ``vnf_vertex_array`` quad-subdivision style.

    Returns:
        A :class:`~pybosl2.vnf.VNF`.
    """
    from pybosl2.paths import Path as _Path

    assert height > 0, "offset_sweep(): height must be positive."
    fullcaps = _norm_caps(caps)

    base = [[float(p[0]), float(p[1])] for p in path]

    def _to_desc(j):
        if j is None:
            return None
        if isinstance(j, (dict, OSProfile)):
            return j
        return os_circle(float(j))

    bottom_desc = _to_desc(bottom)
    top_desc = _to_desc(top)

    # ---------------------------------------------------------------------------
    # Build (delta, z) pairs for each level of the stack.
    # ---------------------------------------------------------------------------

    def _arc_column(desc, n: int):
        """Return (deltas, zs) for one rim, length n+1."""
        if desc is None:
            return ([0.0], [0.0])
        t = desc.get("type", "circle")
        if t == "flat" or (t == "circle" and desc["r"] == 0.0):
            return ([0.0], [0.0])

        if t == "circle":
            r = desc["r"]
            h = abs(desc["h"])
            ar = abs(r)
            sign = -1.0 if r > 0 else 1.0
            angles = [math.pi / 2 * i / n for i in range(n + 1)]
            deltas = [sign * ar * (1.0 - math.cos(a)) for a in angles]
            zs = [h * math.sin(a) for a in angles]
            return (deltas, zs)

        elif t == "teardrop":
            r = desc["r"]
            h = abs(desc["h"])
            max_angle = desc.get("max_angle", 45.0)
            ar = abs(r)
            sign = -1.0 if r > 0 else 1.0
            max_a_rad = math.radians(max_angle)

            z_trans = ar * math.sin(max_a_rad)
            delta_trans = ar * (1.0 - math.cos(max_a_rad))

            if h <= z_trans:
                limit_a = math.asin(h / ar) if ar > 0 else 0.0
                angles = [limit_a * i / n for i in range(n + 1)]
                deltas = [sign * ar * (1.0 - math.cos(a)) for a in angles]
                zs = [h * math.sin(a) / math.sin(limit_a) if limit_a > 0 else 0.0 for a in angles]
                return (deltas, zs)
            else:
                n_circ = n // 2
                n_line = n - n_circ
                deltas = []
                zs = []
                for i in range(n_circ):
                    a = max_a_rad * i / n_circ
                    deltas.append(sign * ar * (1.0 - math.cos(a)))
                    zs.append(ar * math.sin(a))
                for i in range(n_line + 1):
                    curr_z = z_trans + (h - z_trans) * i / n_line
                    curr_delta = delta_trans + (curr_z - z_trans) * math.tan(max_a_rad)
                    deltas.append(sign * curr_delta)
                    zs.append(curr_z)
                return (deltas, zs)

        elif t == "smooth":
            cut = abs(desc["cut"])
            k = desc["k"]
            sign = -1.0 if desc["r_sign"] > 0 else 1.0
            deltas = []
            zs = []
            for i in range(n + 1):
                u = i / n
                xu = 4.0 * k * cut * (u**3) * (1.0 - u) + cut * (u**4)
                yu = cut * ((1.0 - u) ** 4) + 4.0 * k * cut * u * ((1.0 - u) ** 3)
                deltas.append(sign * xu)
                zs.append(cut - yu)
            return (deltas, zs)

        elif t == "chamfer":
            w = desc["width"]
            h = abs(desc["height"])
            deltas = [-w * i / n for i in range(n + 1)]
            zs = [h * i / n for i in range(n + 1)]
            return (deltas, zs)

        elif t == "profile":
            pts = desc["points"]
            pts_arr = np.asarray(pts, dtype=float)
            zs_in = pts_arr[:, 1]
            xs_in = pts_arr[:, 0]
            z_min, z_max = zs_in[0], zs_in[-1]
            zs = [z_min + (z_max - z_min) * i / n for i in range(n + 1)]
            deltas = [-float(np.interp(z, zs_in, xs_in)) for z in zs]
            return (deltas, zs)

        return ([0.0], [0.0])

    bot_deltas, bot_zs = _arc_column(bottom_desc, steps)
    top_deltas, top_zs = _arc_column(top_desc, steps)

    h_bot = bot_zs[-1]
    h_top = top_zs[-1]
    assert h_bot + h_top <= height, (
        "offset_sweep(): the sum of the bottom and top rim heights exceeds the extrusion height."
    )

    # Assemble (delta, z) pairs for the complete column, bottom → top.
    column: list[tuple[float, float]] = []

    # Bottom rim.
    for d, z in zip(bot_deltas, bot_zs, strict=False):
        column.append((d, z))

    # Middle straight wall (if there is room between the two rims).
    mid_z_bot = column[-1][1]
    mid_z_top = height - h_top
    if mid_z_top > mid_z_bot + 1e-9:
        column.append((column[-1][0], mid_z_top))

    # Top rim (arc in reverse: from height-h_top up to height).
    for d, z in zip(reversed(top_deltas), reversed(top_zs), strict=False):
        column.append((d, height - z))

    # De-duplicate consecutive identical entries.
    deduped: list[tuple[float, float]] = [column[0]]
    for pair in column[1:]:
        prev = deduped[-1]
        if abs(pair[0] - prev[0]) > 1e-12 or abs(pair[1] - prev[1]) > 1e-12:
            deduped.append(pair)

    # Build one 3-D ring per (delta, z) level.
    profiles_3d: list[list[list[float]]] = []
    for delta, z in deduped:
        if abs(delta) < 1e-12:
            ring: list[list[float]] = [[p[0], p[1], z] for p in base]
        else:
            off = list(_Path(base).offset(delta=delta))
            ring = [[float(p[0]), float(p[1]), z] for p in off]
        if ring:
            profiles_3d.append(ring)

    if len(profiles_3d) < 2:
        return VNF([], [])

    # Normalise all rings to the same vertex count.
    maxn = max(len(r) for r in profiles_3d)
    from pybosl2.paths import Path as _Path2

    norm = [_Path2._subdivide_path(row, sides=maxn, closed=True, method="length") for row in profiles_3d]

    vnf = VNF.vertex_array(norm, cap1=fullcaps[0], cap2=fullcaps[1], col_wrap=True, style=style)
    return vnf if vnf.volume() >= 0 else vnf.reverse()


def _convex_offset_extrude(
    path: Sequence[Sequence[float]],
    height: float,
    bottom=None,
    top=None,
    steps: int = 16,
    caps: CapsSpec = None,
    style: str = "min_edge",
) -> VNF:
    """Offset sweep/extrusion of a 2-D shape (BOSL2 convex_offset_extrude()).

    An alias for :func:`_offset_sweep` to match BOSL2's geometry-oriented name.
    """
    return _offset_sweep(path, height=height, bottom=bottom, top=top, steps=steps, caps=caps, style=style)


def _rounded_prism(
    bottom: Sequence[Sequence[float]],
    top: Sequence[Sequence[float]] | None = None,
    height: float | None = None,
    joint_top: float | dict | None = None,
    joint_bottom: float | dict | None = None,
    joint_sides: float | list[float] | None = None,
    curvature_sides: float | list[float] | None = None,
    steps: int = 16,
    caps: CapsSpec = None,
    style: str = "min_edge",
    **kwargs,
) -> VNF:
    """Loft/extrusion between two polygons with top, bottom, and side rounding (BOSL2 rounded_prism()).

    Args:
        bottom:          The bottom polygon path (2-D point sequence).
        top:         The top polygon path (defaults to *bottom*).
        height:      Prism height.
        joint_top:   Rounding radius or specifier for the top rim.
        joint_bottom: Rounding radius or specifier for the bottom rim.
        joint_sides: Rounding radius or specifier for the vertical side corners.
        curvature_sides: Continuous curvature parameter for side corners.
        steps:       Arc slices for top/bottom rim treatments.
        caps:        Cap bottom/top.
        style:       Subdivision style.

    Returns:
        A :class:`~pybosl2.vnf.VNF`.
    """
    from pybosl2.paths import Path as _Path

    joint_bot = joint_bottom if joint_bottom is not None else kwargs.get("joint_bot")
    k_sides = curvature_sides if curvature_sides is not None else kwargs.get("k_sides")

    # Coerce/normalize top and height
    if top is None:
        top = bottom

    bot_z = [float(p[2]) if len(p) > 2 else 0.0 for p in bottom]
    top_z = [float(p[2]) if len(p) > 2 else 0.0 for p in top]
    z_diff = abs(max(top_z) - min(bot_z))
    h_val = float(height) if height is not None else (z_diff if z_diff > 1e-9 else 1.0)

    b_2d = [[float(p[0]), float(p[1])] for p in bottom]
    t_2d = [[float(p[0]), float(p[1])] for p in top]

    # Pre-round the side corners if requested
    if joint_sides is not None:
        from pybosl2.rounding import _round_corners as _rc

        m_sides = "smooth" if k_sides is not None else "circle"
        kwargs_sides: dict[str, Any] = {"method": m_sides}
        if m_sides == "smooth":
            kwargs_sides["joint"] = joint_sides
            kwargs_sides["curvature"] = k_sides
        else:
            kwargs_sides["radius"] = joint_sides

        b_rounded = _rc(b_2d, **kwargs_sides)
        t_rounded = _rc(t_2d, **kwargs_sides)
    else:
        b_rounded = b_2d
        t_rounded = t_2d

    # Convert rim treatments to dict descriptors
    def _to_desc(j):
        if j is None:
            return None
        if isinstance(j, (dict, OSProfile)):
            return j
        return os_circle(float(j))

    desc_top = _to_desc(joint_top)
    desc_bot = _to_desc(joint_bot)

    # Re-use the (delta, z) levels calculation from offset_sweep
    def _arc_column(desc, n: int):
        if desc is None:
            return ([0.0], [0.0])
        t = desc.get("type", "circle")
        if t == "flat" or (t == "circle" and desc["r"] == 0.0):
            return ([0.0], [0.0])

        if t == "circle":
            r = desc["r"]
            h = abs(desc["h"])
            ar = abs(r)
            sign = -1.0 if r > 0 else 1.0
            angles = [math.pi / 2 * i / n for i in range(n + 1)]
            deltas = [sign * ar * (1.0 - math.cos(a)) for a in angles]
            zs = [h * math.sin(a) for a in angles]
            return (deltas, zs)

        elif t == "teardrop":
            r = desc["r"]
            h = abs(desc["h"])
            max_angle = desc.get("max_angle", 45.0)
            ar = abs(r)
            sign = -1.0 if r > 0 else 1.0
            max_a_rad = math.radians(max_angle)

            z_trans = ar * math.sin(max_a_rad)
            delta_trans = ar * (1.0 - math.cos(max_a_rad))

            if h <= z_trans:
                limit_a = math.asin(h / ar) if ar > 0 else 0.0
                angles = [limit_a * i / n for i in range(n + 1)]
                deltas = [sign * ar * (1.0 - math.cos(a)) for a in angles]
                zs = [h * math.sin(a) / math.sin(limit_a) if limit_a > 0 else 0.0 for a in angles]
                return (deltas, zs)
            else:
                n_circ = n // 2
                n_line = n - n_circ
                deltas = []
                zs = []
                for i in range(n_circ):
                    a = max_a_rad * i / n_circ
                    deltas.append(sign * ar * (1.0 - math.cos(a)))
                    zs.append(ar * math.sin(a))
                for i in range(n_line + 1):
                    curr_z = z_trans + (h - z_trans) * i / n_line
                    curr_delta = delta_trans + (curr_z - z_trans) * math.tan(max_a_rad)
                    deltas.append(sign * curr_delta)
                    zs.append(curr_z)
                return (deltas, zs)

        elif t == "smooth":
            cut = abs(desc["cut"])
            k = desc["k"]
            sign = -1.0 if desc["r_sign"] > 0 else 1.0
            deltas = []
            zs = []
            for i in range(n + 1):
                u = i / n
                xu = 4.0 * k * cut * (u**3) * (1.0 - u) + cut * (u**4)
                yu = cut * ((1.0 - u) ** 4) + 4.0 * k * cut * u * ((1.0 - u) ** 3)
                deltas.append(sign * xu)
                zs.append(cut - yu)
            return (deltas, zs)

        elif t == "chamfer":
            w = desc["width"]
            h = abs(desc["height"])
            deltas = [-w * i / n for i in range(n + 1)]
            zs = [h * i / n for i in range(n + 1)]
            return (deltas, zs)

        elif t == "profile":
            pts = desc["points"]
            pts_arr = np.asarray(pts, dtype=float)
            zs_in = pts_arr[:, 1]
            xs_in = pts_arr[:, 0]
            z_min, z_max = zs_in[0], zs_in[-1]
            zs = [z_min + (z_max - z_min) * i / n for i in range(n + 1)]
            deltas = [-float(np.interp(z, zs_in, xs_in)) for z in zs]
            return (deltas, zs)

        return ([0.0], [0.0])

    bot_deltas, bot_zs = _arc_column(desc_bot, steps)
    top_deltas, top_zs = _arc_column(desc_top, steps)

    h_bot = bot_zs[-1]
    h_top = top_zs[-1]
    assert h_bot + h_top <= h_val, (
        "rounded_prism(): the sum of the bottom and top rim heights exceeds the prism height."
    )

    column: list[tuple[float, float]] = []

    # Bottom rim.
    for d, z in zip(bot_deltas, bot_zs, strict=False):
        column.append((d, z))

    # Middle straight wall.
    mid_z_bot = column[-1][1]
    mid_z_top = h_val - h_top
    if mid_z_top > mid_z_bot + 1e-9:
        column.append((column[-1][0], mid_z_top))

    # Top rim.
    for d, z in zip(reversed(top_deltas), reversed(top_zs), strict=False):
        column.append((d, h_val - z))

    # De-duplicate consecutive identical entries.
    deduped: list[tuple[float, float]] = [column[0]]
    for pair in column[1:]:
        prev = deduped[-1]
        if abs(pair[0] - prev[0]) > 1e-12 or abs(pair[1] - prev[1]) > 1e-12:
            deduped.append(pair)

    # Build one 3-D ring per level
    profiles_3d = []
    b_arr = np.asarray(b_rounded, dtype=float)
    t_arr = np.asarray(t_rounded, dtype=float)
    assert len(b_arr) == len(t_arr), "rounded_prism(): bottom and top polygons must have the same number of vertices."

    for delta, z in deduped:
        frac = z / h_val
        base_z = (1.0 - frac) * b_arr + frac * t_arr
        if abs(delta) < 1e-12:
            ring = [[p[0], p[1], z] for p in base_z]
        else:
            off = list(_Path(base_z.tolist()).offset(delta=delta))
            ring = [[float(p[0]), float(p[1]), z] for p in off]
        if ring:
            profiles_3d.append(ring)

    if len(profiles_3d) < 2:
        return VNF([], [])

    # Normalise rings
    maxn = max(len(r) for r in profiles_3d)
    from pybosl2.paths import Path as _Path2

    norm = [_Path2._subdivide_path(row, sides=maxn, closed=True, method="length") for row in profiles_3d]
    fullcaps = _norm_caps(caps)

    vnf = VNF.vertex_array(norm, cap1=fullcaps[0], cap2=fullcaps[1], col_wrap=True, style=style)
    return vnf if vnf.volume() >= 0 else vnf.reverse()


def _join_prism(
    polygon: Sequence[Sequence[float]],
    height: float,
    fillet: float = 0.0,
    steps: int = 16,
    caps: CapsSpec = None,
    style: str = "min_edge",
) -> VNF:
    """Join an arbitrary prism to a base plane with a filleted transition (BOSL2 join_prism()).

    Uses :func:`_offset_sweep` with an outward bottom flare (os_circle(radius=-fillet))
    to create the rounded fillet joint.
    """
    bottom_desc = os_circle(radius=-fillet) if fillet > 0 else None
    return _offset_sweep(polygon, height=height, bottom=bottom_desc, steps=steps, caps=caps, style=style)


def _prism_connector(
    profile: Sequence[Sequence[float]],
    length: float,
    fillet: float = 0.0,
    fillet1: float | None = None,
    fillet2: float | None = None,
    steps: int = 16,
    caps: CapsSpec = None,
    style: str = "min_edge",
) -> VNF:
    """Construct a filleted prism connecting two objects (BOSL2 prism_connector()).

    Uses :func:`_offset_sweep` with outward flares at both ends (os_circle(radius=-fillet))
    to create the filleted joints.
    """
    f1 = fillet1 if fillet1 is not None else fillet
    f2 = fillet2 if fillet2 is not None else fillet
    bot_desc = os_circle(radius=-f1) if f1 > 0 else None
    top_desc = os_circle(radius=-f2) if f2 > 0 else None
    return _offset_sweep(profile, height=length, bottom=bot_desc, top=top_desc, steps=steps, caps=caps, style=style)


def _attach_prism(
    profile: Sequence[Sequence[float]],
    length: float,
    fillet: float = 0.0,
    rounding: float = 0.0,
    steps: int = 16,
    caps: CapsSpec = None,
    style: str = "min_edge",
) -> VNF:
    """Attach a filleted prism with optional rounded end (BOSL2 attach_prism()).

    Uses :func:`_offset_sweep` with a bottom flare (os_circle(radius=-fillet)) and top
    roundover (os_circle(radius=rounding)) to create the filleted joints.
    """
    bot_desc = os_circle(radius=-fillet) if fillet > 0 else None
    top_desc = os_circle(radius=rounding) if rounding > 0 else None
    return _offset_sweep(profile, height=length, bottom=bot_desc, top=top_desc, steps=steps, caps=caps, style=style)


def _bent_cutout_mask(
    radius: float,
    thickness: float,
    path: Sequence[Sequence[float]],
    style: str = "min_edge",
) -> VNF:
    """Create a mask to generate a round-edged cutout in a cylindrical shell (BOSL2 bent_cutout_mask()).

    Wraps a 2-D path around a cylinder of *radius* and extrudes it radially by *thickness*.

    Args:
        radius:    Radius of the cylinder to wrap around.
        thickness: Radial thickness of the mask.
        path:      2-D path/polygon defining the cutout profile.
        style:     Subdivision style.
    """
    pts = [list(map(float, p)) for p in path]
    if not pts:
        return VNF([], [])

    # Ensure closed loop
    if len(pts) > 1 and np.allclose(pts[0], pts[-1], atol=1e-9):
        pts.pop()

    inner_ring = []
    outer_ring = []

    r_in = radius - thickness / 2.0
    r_out = radius + thickness / 2.0

    for x, y in pts:
        theta = x / radius
        c = math.cos(theta)
        s = math.sin(theta)
        inner_ring.append([r_in * c, r_in * s, y])
        outer_ring.append([r_out * c, r_out * s, y])

    vnf = VNF.vertex_array([inner_ring, outer_ring], cap1=True, cap2=True, col_wrap=True, style=style)
    return vnf if vnf.volume() >= 0 else vnf.reverse()


# ---------------------------------------------------------------------------------------------
# path_sweep2d() -- sweep a 2-D shape along a 2-D path (creases allowed)
# ---------------------------------------------------------------------------------------------


def _path_sweep2d(
    shape: Sequence[Sequence[float]],
    path: Sequence[Sequence[float]],
    closed: bool = False,
    caps: CapsSpec = None,
    quality: int = 1,
    style: str = "min_edge",
) -> VNF:
    """Sweep a 2-D *shape* along a 2-D *path*, mapping the shape's Y to Z (BOSL2 path_sweep2d()).

    Both *shape* and *path* are 2-D :class:`~pybosl2.paths.Path` objects (coerced from point lists).
    Each shape point offsets the path by its X and lifts it to its Y, so a shape with a wide X
    range becomes a wall of varying width along the path. Unlike :func:`path_sweep`, moderate local
    concavity is handled by the offset (mitre joins); an offset large enough to collapse a feature
    of the path will still fold, so keep the shape's X extent below the path's tightest radius.

    Args:
        shape:  the 2-D cross-section (a closed path); its X is the offset from the path, its Y the height
        path:   the 2-D path to sweep along
        closed: the path is a closed loop (default False)
        caps:   cap the open ends (default: True for open, False for closed)
        quality: accepted for signature parity (unused -- the mitre offset needs no quality knob)
        style:  vnf_vertex_array quad-subdivision style

    Examples:
        A rounded bar swept along a wavy 2-D path:

        .. pythonscad-example::

            shape = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
            path = [[t, 8 * math.sin(t / 12)] for t in range(0, 90, 3)]
            Path(path).path_sweep2d(shape).polyhedron().show()
    """
    from pybosl2.paths import Path

    _ = quality
    shape = Path(shape)
    path = Path(path)
    fullcaps = _norm_caps(caps, closed=closed)
    profile = shape if not shape.is_clockwise() else shape.reversed_path()  # ccw_polygon
    flip = -1.0 if (closed and path.is_clockwise()) else 1.0
    pth = path if flip > 0 else path.reversed_path()

    # For each profile point, offset the path by -flip*x and lift the result to z=y.
    per_point = []
    for pt in profile:
        off = pth.offset(delta=-flip * pt[0])
        assert len(off) == len(pth), (
            "path_sweep2d(): the offset dropped points (the shape is too wide for the path here); "
            "reduce the shape's X extent."
        )
        per_point.append([[float(p[0]), float(p[1]), float(pt[1])] for p in off])
    # transpose: one grid row per path position, each a full cross-section
    grid = [[per_point[j][i] for j in range(len(profile))] for i in range(len(pth))]
    if closed:
        grid = grid + [grid[0]]
    vnf = VNF.vertex_array(grid, cap1=fullcaps[0], cap2=fullcaps[1], col_wrap=True, style=style)
    return vnf if vnf.volume() >= 0 else vnf.reverse()


# ---------------------------------------------------------------------------------------------
# rot_resample() -- resample a list of transforms to uniform screw-motion spacing
# ---------------------------------------------------------------------------------------------


def _closest_angle_array(alpha: float, beta: Sequence[float]) -> list[float]:
    """Congruent angle to *beta* nearest *alpha* (within +/-180 degrees); *beta* may be a list."""
    return [_closest_angle(alpha, b) for b in beta]


def _closest_angle(alpha: float, beta: float) -> float:
    """Congruent angle to *beta* nearest *alpha* (within +/-180 degrees); *beta* may be a list."""
    if beta - alpha > 180:
        return beta - math.ceil((beta - alpha - 180) / 360) * 360
    if beta - alpha < -180:
        return beta + math.ceil((alpha - beta - 180) / 360) * 360
    return beta


def _smooth(data: Sequence[float], length: int, closed: bool = False, angle: bool = False) -> list:
    """Moving-average smooth of *data* over a window of *length* (BOSL2 _smooth()).

    With *angle*, values are unwrapped to the nearest congruent angle before averaging so the mean
    does not jump across the +/-180 boundary. Ends are padded with the edge value (open case).
    """
    halfwidth = length // 2
    sides = len(data)
    out = []
    if closed:
        for i in range(sides):
            window = [data[(i + k) % sides] for k in range(-halfwidth, halfwidth + 1)]
            if angle:
                window = _closest_angle_array(data[i], window)
            out.append(sum(window) / len(window))
    else:
        for i in range(sides):
            lo, hi = max(i - halfwidth, 0), min(i + halfwidth, sides - 1)
            window = list(data[lo : hi + 1])
            pad = data[0] if (i - halfwidth) < 0 else data[-1]
            out.append((sum(window) + pad * (length - len(window))) / length)
    return out


def rot_resample(
    rotlist: Sequence[Sequence[float]],
    sides: int,
    twist=None,
    scale=None,
    smoothlen: int = 1,
    long=False,
    turns: float = 0,
    closed: bool = False,
    method: str = "length",
) -> list:
    """Resample a list of 4x4 transforms to uniform screw-motion spacing (BOSL2 rot_resample()).

    Interpolates between successive transforms along their screw motion (via :func:`rot_decode`),
    optionally adding *twist* and *scale* (smoothed over *smoothlen*). Handy for regularizing the
    transform list from ``path_sweep(..., transforms=True)`` before handing it to :func:`sweep`.

    Args:
        rotlist: list of 4x4 transform matrices
        sides:       number of output samples (method="length") or samples per gap (method="count")
        twist:   extra twist in degrees (scalar or per-gap list)
        scale:   extra scale (scalar or per-gap list, multiplied cumulatively)
        smoothlen: odd window length for smoothing the twist/scale (default 1 = none)
        long:    take the >180-degree rotation at a gap (scalar or per-gap list)
        turns:   extra full turns to add at a gap (scalar or per-gap list)
        closed:  the transform list forms a loop (default False)
        method:  "length" (uniform screw-distance) or "count" (fixed samples per gap)
    """
    rotlist_extra = [np.asarray(t, dtype=float) for t in rotlist]
    assert smoothlen > 0 and smoothlen % 2 == 1, "rot_resample(): smoothlen must be a positive odd integer."
    assert method in ("length", "count")
    m = len(rotlist_extra)
    tcount = m + (0 if closed else -1)
    if method == "length":
        count = (sides + 1) if closed else sides
    else:
        count = (sum(sides) if isinstance(sides, (list, tuple)) else tcount * sides) + 1
    long_l = list(long) if isinstance(long, (list, tuple)) else [long] * tcount
    turns_l = list(turns) if isinstance(turns, (list, tuple)) else [turns] * tcount

    steps = [rot_inverse(rotlist_extra[i]) @ rotlist_extra[(i + 1) % m] for i in range(tcount)]
    parms = []
    for i in range(tcount):
        tp = rot_decode(steps[i], long_l[i])
        parms.append(
            [
                tp[0] + turns_l[i] * 360,
                np.asarray(tp[1], dtype=float),
                np.asarray(tp[2], dtype=float),
                np.asarray(tp[3], dtype=float),
            ]
        )
    radius = [float(np.linalg.norm(p[2])) for p in parms]
    length = [
        math.hypot(
            float(np.linalg.norm(parms[i][3])),
            parms[i][0] / 360 * 2 * math.pi * radius[i],
        )
        for i in range(tcount)
    ]
    if method == "length":
        assert all(x > 0 for x in length), "rot_resample(): a repeated/origin rotation makes method='length' undefined."

    cumlen = [0.0]
    for x in length:
        cumlen.append(cumlen[-1] + x)
    totlen = cumlen[-1]
    stepsize = totlen / (count - 1) if count > 1 else totlen

    if method == "count":
        nlist = list(sides) if isinstance(sides, (list, tuple)) else [sides] * tcount
        samples = [[k / N for k in range(N)] for N in nlist]  # lerpn(0,1,N,endpoint=False)
    else:
        samples = []
        for i in range(tcount):
            remainder = cumlen[i] % stepsize
            offset = 0.0 if remainder == 0 else stepsize - remainder
            n = math.ceil((length[i] - offset) / stepsize)
            samples.append([(offset + k * stepsize) / length[i] for k in range(n)])

    twist_v = 0 if twist is None else twist
    scale_v = 1 if scale is None else scale
    lastsample = samples[-1][-1] if samples[-1] else 1.0
    needlast = abs(lastsample - 1.0) > 1e-9

    if isinstance(twist_v, (int, float)):
        sampletwist: list[float] = list(np.linspace(0, twist_v, count))
    else:
        cumtwist = [0.0]
        for t in twist_v:
            cumtwist.append(cumtwist[-1] + t)
        sampletwist = [cumtwist[i] + (cumtwist[i + 1] - cumtwist[i]) * u for i in range(tcount) for u in samples[i]]
        if needlast:
            sampletwist.append(cumtwist[-1])

    if isinstance(scale_v, (int, float)):
        samplescale: list[float] = [1 + (scale_v - 1) * u for u in np.linspace(0, 1, count)]
    else:
        cumscale = [1.0]
        for s in scale_v:
            cumscale.append(cumscale[-1] * s)
        samplescale = [cumscale[i] + (cumscale[i + 1] - cumscale[i]) * u for i in range(tcount) for u in samples[i]]
        if needlast:
            samplescale.append(cumscale[-1])

    smoothtwist = _smooth(
        sampletwist[:-1] if closed else sampletwist,
        smoothlen,
        closed=closed,
        angle=True,
    )
    smoothscale = _smooth(samplescale, smoothlen, closed=closed)

    interpolated = []
    for i in range(tcount):
        for u in samples[i]:
            mv = np.eye(4)
            mv[:3, 3] = u * parms[i][3]
            interpolated.append(rotlist[i] @ mv @ rot_about_axis(u * parms[i][0], parms[i][1], parms[i][2]))
    if needlast:
        interpolated.append(rotlist[-1])

    end = len(interpolated) - (1 if closed else 0)
    return [
        interpolated[i] @ zrot4(smoothtwist[i]) @ _scale4([smoothscale[i], smoothscale[i], 1.0]) for i in range(end)
    ]
