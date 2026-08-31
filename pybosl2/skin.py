# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: Paths, regions & surfaces

"""Surface generators: sweep, path_sweep, skin, linear_sweep, rotate_sweep, spiral_sweep (BOSL2 skin.scad)."""

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
#          flat caps on/off, user tangents, and the frames path_sweep_transforms() returns.
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
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Sequence, cast

if TYPE_CHECKING:
    from pybosl2._backend import Solid
    from pybosl2.path2d import Path2D
    from pybosl2.path3d import Path3D
    from pybosl2.paths import Path, PathLike

import numpy as np

from pybosl2._helpers import frag_count as _segs
from pybosl2._helpers import pick_radius as _pick_radius
from pybosl2._helpers import scale4 as _scale4
from pybosl2._helpers import translate4, zrot4
from pybosl2._helpers import xrot4 as _xrot4
from pybosl2.caps import CapsSpec, CapType, has_decorative_caps, norm_caps, vnf_with_decorative_caps
from pybosl2.defaults import resolve_facets
from pybosl2.enums import ResampleMethod, RoundingMethod, SamplingType, SkinMethod, SweepMethod, VNFStyle
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.paths import require_path, require_paths
from pybosl2.points import Point
from pybosl2.transforms import apply as _apply
from pybosl2.transforms import rot_about_axis, rot_decode, rot_inverse
from pybosl2.vnf import VNF

UP = Point([0.0, 0.0, 1.0])
BACK = Point([0.0, 1.0, 0.0])


def _as_solid(mesh: "VNF | Solid") -> "Solid":
    """Realize a sweep's mesh as a solid on the active backend, keeping the mesh reachable.

    SPEC S-19a: a sweep returns a `Solid`, so its result composes with `-`/`|`/`&` and the
    transforms like any other shape and a caller never appends `.polyhedron()` to a call that
    already said "sweep this into a solid". The mesh stays available as `.vnf()` for measuring,
    joining or exporting with no CAD runtime (SPEC C-8), which is why it is stashed rather than
    discarded.

    A member that already built a Solid -- the decorative-cap path unions real geometry -- passes
    straight through.
    """
    if not isinstance(mesh, VNF):
        return mesh
    solid = mesh.polyhedron()
    # Stashed for `Solid.vnf()` to hand back: meshing it again would be both slower and lossier than
    # keeping the one the sweep already built.
    object.__setattr__(solid, "_vnf", mesh)
    return solid


class Sweepable:
    """Mixin adding sweep methods to Path2D and Path3D."""

    def path_sweep(
        self,
        shape: "PathLike",
        method: SweepMethod = SweepMethod.INCREMENTAL,
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
        caps: CapsSpec = CapType.BUTT,
        style: VNFStyle = VNFStyle.MIN_EDGE,
    ) -> "Solid":
        """Sweep *shape* along this path.

        *method* orients the cross section: "incremental" (rotation-minimizing frame), "manual"
        (using *normal* as a per-point normal list), or "natural" (the path's own normal). *twist*
        (degrees) and *scale* (scalar, 2-vector, per-point vector, or Nx2) are interpolated along the
        path. See BOSL2 path_sweep() for the full semantics.

        Examples:
            Sweeping a small square profile along a helical path into a solid:

            .. pythonscad-example::

                import math
                import numpy as np
                from pybosl2 import Path3D

                square = [[-3, -3], [3, -3], [3, 3], [-3, 3]]
                helix = [[10 * math.cos(t), 10 * math.sin(t), t * 3] for t in np.linspace(0, 3 * math.pi, 40)]
                Path3D(helix).path_sweep(square).show()

        """
        mesh = _path_sweep(
            shape,
            cast("Path2D | Path3D", self),
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
            transforms=False,
        )
        return _as_solid(cast("VNF", mesh))

    def path_sweep_transforms(
        self,
        method: SweepMethod = SweepMethod.INCREMENTAL,
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
    ) -> list[list[list[float]]]:
        """Return the 4x4 transforms :meth:`path_sweep` would place its cross sections with.

        This used to be ``path_sweep(..., transforms=True)``, which made the return type depend on
        an argument: every caller of the ordinary case paid for the flag with a union they could
        not narrow, and the documented one-liner stopped type-checking. A flag that changes the
        return type is a second function, so here it is (SPEC S-19b, PLAN T-6d).

        The parameters are :meth:`path_sweep`'s, minus the ones that only affect the skin
        (``caps``, ``style``) and the profile itself -- a transform list does not have a profile.

        Args:
            method: how the cross section is oriented along the path.
            normal: per-point normals, for ``SweepMethod.MANUAL``.
            closed: the path loops back on itself.
            twist: degrees of twist along the path.
            twist_by_length: distribute the twist by arc length rather than by point index.
            scale: scalar, 2-vector, per-point vector or Nx2 scaling along the path.
            scale_by_length: distribute the scaling by arc length rather than by point index.
            symmetry: rotational symmetry order of the profile.
            last_normal: normal to land on at the far end.
            tangent: explicit per-point tangents.
            uniform: resample the path uniformly first.
            relaxed: relax the frame rather than holding the normal exactly.

        Returns:
            One 4x4 matrix per cross section, as plain nested lists.

        Examples:
            Placing your own geometry at each station along a path::

                from pybosl2 import Path3D, cuboid

                path = Path3D([[0, 0, 0], [0, 0, 10], [5, 0, 20]])
                for matrix in path.path_sweep_transforms():
                    cuboid([2, 2, 1]).multmatrix(matrix)

        """
        placed = _path_sweep(
            [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]],  # a placeholder profile: only the frames are read
            cast("Path2D | Path3D", self),
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
            transforms=True,
        )
        return cast("list[list[list[float]]]", placed)

    def path_sweep2d(
        self,
        shape: "PathLike",
        closed: bool = False,
        caps: CapsSpec = CapType.BUTT,
        style: VNFStyle = VNFStyle.MIN_EDGE,
    ) -> "Solid":
        """Sweep 2-D *shape* along this 2-D path.

        For each point on the profile, the path is offset by its X coordinate and lifted to Z = Y,
        producing a stack of profiles that are skinned into the final surface. Closed paths are
        reversed automatically to maintain the same winding.

        Examples:
            A rounded bar swept along a wavy 2-D path:

            .. pythonscad-example::

                import math
                from pybosl2 import Path2D

                shape = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
                path = [[t, 8 * math.sin(t / 12)] for t in range(0, 90, 3)]
                Path2D(path).path_sweep2d(shape).show()

        """
        return _as_solid(_path_sweep2d(shape, cast("Path2D", self), closed=closed, caps=caps, style=style))

    def linear_sweep(
        self,
        height: float | None = None,
        twist: float = 0.0,
        scale: Any = 1,
        shift: Sequence[float] = (0.0, 0.0),
        slices: int | None = None,
        center: bool = False,
        caps: CapsSpec = CapType.BUTT,
        style: VNFStyle = VNFStyle.MIN_EDGE,
    ) -> "Solid":
        """Extrude this 2-D profile linearly with optional twist/scale/shift.

        The profile is duplicated at *slices* positions along the Z axis; at each level the points
        are twisted (rotation around Z, degrees) and scaled (uniform scalar or 2-vector), then
        shifted in XY. The slices are skinned into a VNF.

        Examples:
            A twisting, tapering square column:

            .. pythonscad-example::

                from pybosl2 import Path2D

                square = [[-10, -10], [10, -10], [10, 10], [-10, 10]]
                Path2D(square).linear_sweep(height=40, twist=120, scale=0.4).show()

        """
        return _as_solid(
            _linear_sweep(
                cast("Path2D", self),
                height=height,
                twist=twist,
                scale=scale,
                shift=shift,
                slices=slices,
                center=center,
                caps=caps,
                style=style,
            )
        )

    def rotate_sweep(
        self,
        angle: float = 360.0,
        caps: CapsSpec = CapType.BUTT,
        _closed: bool | None = None,
        style: VNFStyle = VNFStyle.MIN_EDGE,
        start: float = 0.0,
    ) -> "Solid":
        """Revolve this 2-D profile around the Z axis.

        The profile is swept through *angle* degrees (default 360) around Z, starting at
        *start* degrees. When *angle* < 360 the profile is capped at both ends.

        Examples:
            Revolving a rounded profile into a spool:

            .. pythonscad-example::

                from pybosl2 import Path2D

                profile = [[4, -10], [12, -10], [12, -6], [7, -2], [7, 2], [12, 6], [12, 10], [4, 10]]
                Path2D(profile).rotate_sweep(angle=360).show()

        """
        return _as_solid(
            _rotate_sweep(
                cast("Path2D", self),
                angle=angle,
                caps=caps,
                style=style,
                start=start,
            )
        )

    def spiral_sweep(
        self,
        height: float,
        radius: float | None = None,
        turns: float = 1.0,
        radius1: float | None = None,
        radius2: float | None = None,
        diameter: float | None = None,
        diameter1: float | None = None,
        diameter2: float | None = None,
        center: bool = True,
        style: VNFStyle = VNFStyle.MIN_EDGE,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Solid":
        """Sweep this 2-D profile along a helix.

        The profile follows a helical path of *height* and *radius* (or separate start/end radii)
        over *turns* revolutions. Unlike rotate_sweep, the profile also gains height, producing
        a coil.

        Args:
            height: Overall height of the coil.
            radius: Helix radius; use radius1/radius2 for a taper.
            turns: Number of revolutions.
            radius1: Radius at the start.
            radius2: Radius at the end.
            diameter: Helix diameter, instead of radius.
            diameter1: Diameter at the start.
            diameter2: Diameter at the end.
            center: Centre the coil on the origin.
            style: Quad-subdivision style for the mesh.
            fn: Fixed fragment count per turn; ambient default when omitted.
            fa: Minimum fragment angle per turn.
            fs: Minimum fragment size per turn.

        Returns:
            The swept coil.

        Examples:
            A rectangular-section coil spring:

            .. pythonscad-example::

                from pybosl2 import Path2D

                section = [[-1.2, -1.2], [1.2, -1.2], [1.2, 1.2], [-1.2, 1.2]]
                Path2D(section).spiral_sweep(height=40, radius=12, turns=5).show()

        """
        return _as_solid(
            _spiral_sweep(
                cast("Path2D", self),
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
                fn=fn,
                fa=fa,
                fs=fs,
            )
        )

    def sweep(
        self,
        transforms: Sequence[Sequence[Sequence[float]]],
        closed: bool = False,
        caps: CapsSpec = CapType.BUTT,
        style: VNFStyle = VNFStyle.MIN_EDGE,
    ) -> "Solid":
        """Apply each 4x4 transform to this 2-D shape and skin the resulting profiles into a VNF.

        or Bosl2Solid (BOSL2 sweep()).
        """
        return _as_solid(
            _sweep(
                [list(p) for p in cast("Path2D", self)],
                transforms,
                closed=closed,
                caps=caps,
                style=style,
            )
        )


def _u(v: Sequence[float]) -> np.ndarray:
    a = np.asarray(v, dtype=float)
    sides = float(np.linalg.norm(a))
    return a / sides if sides else a


def _u_nd(v: np.ndarray) -> np.ndarray:
    sides = float(np.linalg.norm(v))
    return v / sides if sides else v


def path3d(path: Sequence[Sequence[float]] | Path | np.ndarray | Sequence[np.ndarray]) -> list[list[float]]:
    """Pad a 2-D (or 3-D) point list to 3-D with z=0.

    The coordinates are converted to plain Python floats, not left as whatever the input held: a
    numpy row in would otherwise leak ``np.float64`` scalars out of an annotation that promises
    ``float``, and those raise SystemError/TypeError at the native FFI boundary (see the note in
    pybosl2/paths.py).
    """
    return [[float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0] for p in path]


def clockwise_polygon(poly: Sequence[Sequence[float]] | Path2D) -> list[Sequence[float]]:
    """*poly* wound clockwise (reversed if its signed area is positive/CCW)."""
    from pybosl2.path2d import Path2D

    return list(poly) if Path2D.polygon_area(poly, signed=True) <= 0 else list(reversed(list(poly)))  # type: ignore[arg-type]


def frame_map(
    x: Sequence[float] | None = None,
    y: Sequence[float] | None = None,
    z: Sequence[float] | None = None,
) -> np.ndarray:
    """Return the 4x4 rotation whose columns are the given orthonormal axes.

    Give any two of x/y/z (as 3-vectors); the third is filled in by the cross product.
    """
    xu = _u(x) if x is not None else None
    yu = _u(y) if y is not None else None
    zu = _u(z) if z is not None else None
    if xu is None:
        assert yu is not None
        assert zu is not None
        xu = np.cross(yu, zu)
    elif yu is None:
        assert zu is not None
        assert xu is not None
        yu = np.cross(zu, xu)
    elif zu is None:
        assert xu is not None
        assert yu is not None
        zu = np.cross(xu, yu)
    assert xu is not None
    assert yu is not None
    assert zu is not None
    m = np.eye(4)
    m[:3, :3] = np.column_stack([xu, yu, zu])
    return m


def _sweep(
    shape: Sequence[Sequence[float]],
    transforms: Sequence[Sequence[Sequence[float]]],
    closed: bool = False,
    caps: CapsSpec = CapType.BUTT,
    style: VNFStyle = VNFStyle.MIN_EDGE,
) -> VNF | "Solid":
    """Apply each 4x4 transform to the 2-D *shape* and skin the resulting profiles into a VNF or Bosl2Solid.

    Decorative cap types (ARROW, DIAMOND, DOT, etc.) produce a :class:`~pybosl2.shapes3d.Bosl2Solid`
    with the endcap geometry unioned to the swept body. Basic caps (NONE, BUTT, ROUND, SPHERE)
    are handled inline by :class:`VNF.vertex_array`.

    Args:
        shape:      a 2-D polygon (list of [x, y] points)
        transforms: list of 4x4 matrices, one per cross section along the path
        closed:     the sweep loops back on itself (no caps)
        caps:       cap the open ends (default: BUTT); supports decorative cap types
        style:      vnf_vertex_array quad-subdivision style

    """
    shape3 = np.asarray(path3d(shape), dtype=float)
    if not (len(shape3) >= 3):
        raise Bosl2ValueError("shape must be a path of at least 3 points.")
    cap_specs = norm_caps(caps, closed=closed)
    ntrans = len(transforms)
    if not (ntrans >= 2):
        raise Bosl2ValueError("transforms must be length 2 or more.")
    hi = ntrans - (0 if closed else 1)
    points = [np.asarray(_apply(transforms[i % ntrans], shape3), dtype=float) for i in range(hi + 1)]

    if has_decorative_caps(cap_specs):
        vnf = VNF.vertex_array(points, col_wrap=True, style=style)
        vnf = vnf if vnf.volume() >= 0 else vnf.reverse()
        center1 = list(np.mean(points[0], axis=0))
        center2 = list(np.mean(points[-1], axis=0))
        radius = float(max(np.linalg.norm(np.asarray(p[:2]) - np.asarray(center1[:2])) for p in points[0]))
        outdir1 = [center1[i] - center2[i] for i in range(3)]
        outdir2 = [center2[i] - center1[i] for i in range(3)]
        return vnf_with_decorative_caps(vnf, cap_specs, closed, [center1, center2], [outdir1, outdir2], radius)

    vnf = VNF.vertex_array(
        points[:-1] if closed else points,
        caps=cap_specs,
        col_wrap=True,
        row_wrap=closed,
        style=style,
    )
    # SPEC S-19c: every sweep hands back outward-facing normals. Whether vertex_array() winds this
    # way depends on the direction the transform list runs, so it is normalised here -- the one
    # exit `path_sweep`, `sweep` and `spiral_sweep` all leave through. Without it `path_sweep`
    # produced the mirror of what `linear_sweep` produced for the same box (volume -1000 against
    # +1000), and an inside-out mesh handed to polyhedron() *adds* material where it should cut.
    return vnf if vnf.volume() >= 0 else vnf.reverse()


def _path_sweep(
    shape: "PathLike",
    path: Sequence[Sequence[float]] | Path2D | Path3D,
    method: SweepMethod = SweepMethod.INCREMENTAL,
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
    caps: CapsSpec = CapType.BUTT,
    style: VNFStyle = VNFStyle.MIN_EDGE,
    transforms: bool = False,
) -> VNF | "Solid" | list[list[list[float]]]:
    """Sweep the 2-D *shape* along the 2-D/3-D *path* (internal implementation).

    Public API: use :meth:`Sweepable.path_sweep` instead of calling this directly.
    """
    from pybosl2.path3d import Path3D

    patharr = np.asarray(path3d(path), dtype=float)
    npts = len(patharr)
    if not (npts >= 2):
        raise Bosl2ValueError("path must have at least 2 points.")

    if tangent is not None:
        tangents = np.array([_u(t) for t in path3d(tangent)])
    else:
        tangents = np.asarray(Path3D(patharr).tangents(closed=closed, uniform=uniform), dtype=float)

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
            (BACK if (method == SweepMethod.INCREMENTAL and abs(tangents[0][2]) > 1 / math.sqrt(2)) else UP),
            dtype=float,
        )
        normals = np.tile(normal_single, (npts, 1))

    if twist_by_length:
        tpathfrac = np.asarray(Path3D(patharr).length_fractions(closed=closed), dtype=float)
    else:
        tpathfrac = np.array([i / (npts - (0 if closed else 1)) for i in range(npts + 1)])
    if scale_by_length:
        spathfrac = np.asarray(Path3D(patharr).length_fractions(closed=closed), dtype=float)
    else:
        spathfrac = np.array([i / (npts - (0 if closed else 1)) for i in range(npts + 1)])

    # Resolve the per-cross-section scale [sx, sy].
    if isinstance(scale, (int, float)) or (np.ndim(scale) == 1 and len(scale) == 2):
        s = [float(scale), float(scale)] if isinstance(scale, (int, float)) else [float(scale[0]), float(scale[1])]
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
        scalevals = [[float(x), float(x)] if isinstance(x, (int, float)) else [float(x[0]), float(x[1])] for x in scale]
    scale_list = [_scale4([sv[0], sv[1], 1.0]) for sv in scalevals]
    if closed:
        scale_list.append(_scale4([scalevals[0][0], scalevals[0][1], 1.0]))

    nprofiles = npts + (1 if closed else 0)

    if method == SweepMethod.INCREMENTAL:
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
    elif method == SweepMethod.MANUAL:
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
    elif method == SweepMethod.NATURAL:
        pathnormal = np.asarray(Path3D(patharr).normals(tangents=tangents, closed=closed), dtype=float)  # type: ignore[arg-type,type-var]
        unscaled = [
            translate4(patharr[i % npts])
            @ frame_map(x=pathnormal[i % npts], z=tangents[i % npts])
            @ zrot4(-twist * tpathfrac[i])
            for i in range(nprofiles)
        ]
    else:
        raise Bosl2ValueError(f"path_sweep(): unknown method {method!r}; use incremental, manual or natural.")

    transform_list = [unscaled[i] @ scale_list[i] for i in range(len(unscaled))]
    if transforms:
        return transform_list
    shp = clockwise_polygon(cast("Sequence[Sequence[float]] | Path2D", shape))
    return _sweep(shp, transform_list, closed=closed, caps=caps, style=style)


# ---------------------------------------------------------------------------------------------
# skin() -- blend a stack of profiles into a surface
# ---------------------------------------------------------------------------------------------


def _reindex_polygon(reference: "PathLike", poly: "PathLike") -> list[list[float]]:
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
    result: list[list[float]] = np.roll(p, -best_k, axis=0).tolist()
    return result


def slice_profiles(profiles: "Sequence[Path2D | Path3D]", slices: int, closed: bool = False) -> list[list[list[float]]]:
    """Interpolate *slices* extra profiles between each consecutive pair.

    *slices* is a count (or a per-segment list). The profiles must all be equal-length point
    lists; the interpolation is vertex-by-vertex.
    """
    profiles = require_paths(profiles, "profiles", "slice_profiles")  # type: ignore[assignment]
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


def _skin(
    profiles: Sequence[PathLike],
    slices: int,
    refine: float = 1.0,
    method: SkinMethod = SkinMethod.DIRECT,
    sampling: SamplingType | None = None,
    caps: CapsSpec = CapType.BUTT,
    closed: bool = False,
    style: VNFStyle = VNFStyle.MIN_EDGE,
    z: Sequence[float] | None = None,
) -> VNF | "Solid":
    """Blend a stack of 2-D/3-D profiles into a skinned surface (internal implementation).

    Public API: use :meth:`VNF.from_skin` instead of calling this directly.
    """
    profiles = [np.asarray(p, dtype=float).tolist() for p in profiles]
    sides = len(profiles)
    if not (sides > 1):
        raise Bosl2ValueError("skin() needs at least two profiles.")
    profcount = sides - (0 if closed else 1)
    cap_specs = norm_caps(caps, closed=closed)
    refine_list = list(refine) if isinstance(refine, (list, tuple)) else [refine] * sides
    method_list = list(method) if isinstance(method, (list, tuple)) else [method] * profcount
    for m in method_list:
        if not (isinstance(m, SkinMethod)):
            raise Bosl2ValueError(f"skin(): only the 'direct' and 'reindex' methods are ported (got {m!r}).")
    sampling = sampling if sampling is not None else SamplingType.LENGTH

    dim = len(profiles[0][0])
    if dim == 2:
        if not (z is not None):
            raise Bosl2ValueError("skin(): 2-D profiles need a matching-length z list.")
        if not (len(z) == sides):
            raise Bosl2ValueError("skin(): 2-D profiles need a matching-length z list.")
        profiles = [[[pt[0], pt[1], z[i]] for pt in profiles[i]] for i in range(sides)]

    from pybosl2.path3d import Path3D

    maxlen = max(refine_list[i] * len(profiles[i]) for i in range(sides))
    resampled = [Path3D(profiles[i]).subdivide_path(points=int(maxlen), closed=True) for i in range(sides)]
    fixedprof = [resampled[0]]
    for i in range(1, sides):
        if method[i - 1] == SkinMethod.DIRECT:
            fixedprof.append(resampled[i])
        else:
            fixedprof.append(Path3D(_reindex_polygon(fixedprof[i - 1], resampled[i])))
    sliced = slice_profiles(fixedprof, slices, closed)
    grid = sliced if not closed else sliced + [sliced[0]]

    if has_decorative_caps(cap_specs):
        vnf = VNF.vertex_array(grid, col_wrap=True, style=style)
        vnf = vnf if vnf.volume() >= 0 else vnf.reverse()
        grid_arr = np.asarray(grid, dtype=float)
        center1 = list(grid_arr[0].mean(axis=0))
        center2 = list(grid_arr[-1].mean(axis=0))
        radius = float(max(np.linalg.norm(p[:2] - np.asarray(center1[:2])) for p in grid_arr[0]))
        outdir1 = [center1[i] - center2[i] for i in range(3)]
        outdir2 = [center2[i] - center1[i] for i in range(3)]
        return vnf_with_decorative_caps(vnf, cap_specs, closed, [center1, center2], [outdir1, outdir2], radius)

    vnf = VNF.vertex_array(
        grid[:-1] if closed else grid,
        caps=cap_specs,
        col_wrap=True,
        row_wrap=closed,
        style=style,
    )
    return vnf if vnf.volume() >= 0 else vnf.reverse()


# ---------------------------------------------------------------------------------------------
# linear_sweep() / rotate_sweep() / spiral_sweep()
# ---------------------------------------------------------------------------------------------


def _linear_sweep(
    region: Sequence[Sequence[float]] | Path2D,
    height: float | None = None,
    twist: float = 0.0,
    scale: float = 1,
    shift: Sequence[float] = (0.0, 0.0),
    slices: int | None = None,
    caps: CapsSpec = CapType.BUTT,
    style: VNFStyle = VNFStyle.DEFAULT,
    center: bool | None = None,
) -> VNF | "Solid":
    """Extrude a 2-D outline to *height* with optional twist / scale / shift (internal implementation).

    Public API: use :meth:`Sweepable.linear_sweep` instead of calling this directly.
    """
    hh = float(height if height is not None else (height if height is not None else 1))
    path = [[p[0], p[1]] for p in region]
    if slices is None:
        slices = max(1, math.ceil(abs(twist) / 5))
    sc = [float(scale), float(scale)] if isinstance(scale, (int, float)) else [float(scale[0]), float(scale[1])]
    sh = [float(shift[0]), float(shift[1])]
    cap_specs = norm_caps(caps)
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

    if has_decorative_caps(cap_specs):
        vnf = VNF.vertex_array(verts, col_wrap=True, style=style)
        vnf = vnf if vnf.volume() >= 0 else vnf.reverse()
        center1 = list(verts[0].mean(axis=0).tolist())
        center2 = list(verts[-1].mean(axis=0).tolist())
        radius = float(max(np.linalg.norm(p[:2] - np.asarray(center1[:2])) for p in verts[0]))
        outdir1 = [0.0, 0.0, -1.0]
        outdir2 = [0.0, 0.0, 1.0]
        return vnf_with_decorative_caps(vnf, cap_specs, False, [center1, center2], [outdir1, outdir2], radius)

    vnf = VNF.vertex_array(
        verts,
        caps=cap_specs,
        col_wrap=True,
        style=style,
    )
    return vnf if vnf.volume() >= 0 else vnf.reverse()


def _rotate_sweep(
    shape: Sequence[Sequence[float]] | Path2D,
    angle: float = 360.0,
    caps: CapsSpec = CapType.BUTT,
    _closed: bool | None = None,
    style: VNFStyle = VNFStyle.MIN_EDGE,
    start: float = 0.0,
) -> VNF | "Solid":
    """Revolve a 2-D *shape* around the Z axis (internal implementation).

    Public API: use :meth:`Sweepable.rotate_sweep` instead of calling this directly.
    """
    if not (0 < angle <= 360):
        raise Bosl2ValueError("rotate_sweep(): angle must be in (0, 360].")
    cap_specs = norm_caps(caps)
    prof = [[p[0], p[1]] for p in shape]
    full = angle >= 360
    if any(s.cap_type != CapType.NONE for s in cap_specs) and not full:
        prof = [[0.0, prof[0][1]]] + prof + [[0.0, prof[-1][1]]]
    xmax = max(p[0] for p in prof)
    steps = math.ceil(_segs(xmax) * angle / 360) + (0 if full else 1)
    steps = max(steps, 3)
    if full:
        angs = [start + 360.0 * i / steps for i in range(steps)]
    else:
        angs = [start + angle * i / (steps - 1) for i in range(steps)]
    transforms = [zrot4(a) @ _xrot4(90) for a in angs]
    cap_list: CapsSpec = [CapType.NONE, CapType.NONE] if full else cap_specs
    result = _sweep(
        prof,
        transforms,
        closed=full,
        caps=cap_list,
        style=style,
    )
    if isinstance(result, VNF):
        return result if result.volume() >= 0 else result.reverse()
    return result


def _spiral_sweep(
    poly: Sequence[Sequence[float]] | Path2D,
    height: float,
    radius: float | None = None,
    turns: float = 1.0,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    center: bool = True,
    style: VNFStyle = VNFStyle.MIN_EDGE,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> VNF | "Solid":
    """Sweep a 2-D cross-section *poly* along a helix (internal implementation).

    Public API: use :meth:`Sweepable.spiral_sweep` instead of calling this directly.
    """
    if not (height > 0):
        raise Bosl2ValueError("spiral_sweep(): need positive height and nonzero turns.")
    if not (turns != 0):
        raise Bosl2ValueError("spiral_sweep(): need positive height and nonzero turns.")
    rr1 = _pick_radius(
        radius1=radius1,
        diameter1=diameter1,
        radius=radius,
        diameter=diameter,
        dflt=1,
    )
    rr2 = _pick_radius(
        radius2=radius2,
        diameter2=diameter2,
        radius=radius,
        diameter=diameter,
        dflt=1,
    )
    poly = [[p[0], p[1]] for p in poly]

    from pybosl2._backend import current_backend

    if current_backend() == "sdf":
        # A helical sweep has an exact distance-field form: the profile's own 2-D field, read in
        # the frame the helix carries it through (TASKS T14). A taper has none, so it refuses
        # rather than quietly sweeping a constant radius.
        from pybosl2.exceptions import UnsupportedByBackendError
        from pybosl2.path2d import Path2D as _Path2D
        from pybosl2.sdf.shapes3d import spiral_sweep as _sdf_spiral_sweep

        if abs(rr1 - rr2) > 1e-12:
            raise UnsupportedByBackendError(
                "spiral_sweep(radius1=, radius2=)",
                "sdf",
                hint="a helix of changing radius has no closed-form distance field here; build it "
                'inside `with use_backend("csg")` and bring it over with .to_csg().',
            )
        return _sdf_spiral_sweep(_Path2D(poly), height=height, radius=rr1, turns=turns, center=center)

    nturns = abs(turns)
    sides = _segs(max(rr1, rr2), fn, fa, fs)
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
    result = _sweep(poly, transforms, closed=False, caps=[CapType.BUTT, CapType.BUTT], style=style)
    if isinstance(result, VNF):
        return result if result.volume() >= 0 else result.reverse()
    return result


def subdivide_and_slice(
    profiles: "Sequence[Path2D | Path3D]",
    slices: int,
    numpoints: int | str | None = None,
    method: ResampleMethod = ResampleMethod.LENGTH,  # noqa: ARG001
    closed: bool = False,
) -> list[list[list[float]]]:
    """Resample every profile up to *numpoints* then interpolate *slices* between them.

    *numpoints* defaults to the largest profile's length; "lcm" uses the least common multiple of
    the profile lengths. Returns the stacked list of (equal-length) profiles.
    """
    from pybosl2.path2d import Path2D
    from pybosl2.path3d import Path3D

    def _wrap(prof: PathLike) -> Path2D | Path3D:
        pts = np.asarray(prof, dtype=float)
        return Path3D(pts) if len(pts) and pts.shape[1] == 3 else Path2D(pts)

    maxsize = max(len(p) for p in profiles)
    if numpoints is None:
        numpoints = maxsize
    elif numpoints == "lcm":
        from functools import reduce

        numpoints = reduce(lambda a, b: a * b // math.gcd(a, b), [len(p) for p in profiles])
    if not (isinstance(numpoints, int)):
        raise Bosl2ValueError("numpoints must be int after resolution")
    numpoints = round(numpoints)
    if not (numpoints >= maxsize):
        raise Bosl2ValueError("subdivide_and_slice(): numpoints is smaller than the largest profile.")
    fixed = [_wrap(p).subdivide_path(points=numpoints, closed=True) for p in profiles]
    return slice_profiles(fixed, slices, closed)


# ---------------------------------------------------------------------------------------------
# os_circle() / offset_sweep() -- profile-based offset extrusion with rim roundovers
# (BOSL2 rounding.scad: os_circle, offset_sweep)
# ---------------------------------------------------------------------------------------------


class OSType(StrEnum):
    """Offset sweep profile type."""

    CIRCLE = "circle"
    SMOOTH = "smooth"
    TEARDROP = "teardrop"
    CHAMFER = "chamfer"
    FLAT = "flat"
    PROFILE = "profile"


@dataclass
class OSProfile:
    """Descriptor for an offset-sweep rim treatment profile (BOSL2 ``os_profile()``).

    Holds the parameters that define how one rim of an extruded shape is treated
    by :func:`offset_sweep` — roundover, flare, teardrop, chamfer, flat, or a
    custom point profile.
    """

    type: OSType
    radius: float = 0.0
    height: float = 0.0
    extra: float = 0.0
    cut: float = 0.0
    curvature: float = 0.5
    radius_sign: float = 1.0
    max_angle: float = 45.0
    width: float = 0.0
    points: list[list[float]] = field(default_factory=list[list[float]])

    def get(self, key: str, default: object = None) -> object:
        """Return the value for key or a default."""
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

    def __getitem__(self, key: str) -> object:
        """Return the item for key."""
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

    def __contains__(self, key: str) -> bool:
        """Return whether key is in this object."""
        mapping = {
            "r": "radius",
            "h": "height",
            "k": "curvature",
            "r_sign": "radius_sign",
        }
        attr = mapping.get(key, key)
        return hasattr(self, attr)


def os_circle(
    radius: float | None = None,
    height: float | None = None,
    extra: float = 0.0,
) -> OSProfile:
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
    r_val = radius
    h_val = height
    if not (r_val is not None):
        raise Bosl2ValueError("os_circle(): radius is required.")
    h_res = float(h_val) if h_val is not None else abs(float(r_val))
    return OSProfile(type=OSType.CIRCLE, radius=float(r_val), height=h_res, extra=float(extra))


def os_smooth(
    cut: float | None = None,
    radius: float | None = None,
    curvature: float = 0.5,
    extra: float = 0.0,
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
    r_val = radius
    k_val = curvature
    val = float(cut) if cut is not None else (float(r_val) if r_val is not None else 1.0)
    sign = 1.0 if val >= 0 else -1.0
    return OSProfile(type=OSType.SMOOTH, cut=abs(val), curvature=float(k_val), radius_sign=sign, extra=float(extra))


def os_teardrop(
    radius: float | None = None,
    height: float | None = None,
    cut: float | None = None,
    max_angle: float = 45.0,
    extra: float = 0.0,
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
    r_arg = radius
    h_arg = height
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


def os_profile(profile: "Path2D", extra: float = 0.0) -> OSProfile:
    """Return a custom offset sweep profile descriptor (BOSL2 ``os_profile()``).

    Accepts a list of 2D points `[[x, y], ...]` defining the profile:
    - `x` is the inward radial offset (meaning `delta = -x`).
    - `y` is the height `z`.

    Args:
        profile: Sequence of ``[x, y]`` points. The first must be ``[0, 0]``.
        extra:   Extra extension (default 0).

    Returns:
        A descriptor ``OSProfile`` consumed by :func:`offset_sweep`.

    """
    from pybosl2.path2d import Path2D as _Path2D

    profile = cast("Path2D", require_path(profile, "profile", "os_profile", _Path2D))
    pts = [[float(p[0]), float(p[1])] for p in profile]
    if not (pts):
        raise Bosl2ValueError("os_profile(): First point of the profile must be [0, 0].")
    if not (pts[0] == [0.0, 0.0]):
        raise Bosl2ValueError("os_profile(): First point of the profile must be [0, 0].")
    return OSProfile(type=OSType.PROFILE, points=pts, extra=float(extra))


def _offset_sweep(
    path: Sequence[Sequence[float]],
    height: float,
    bottom: object = None,
    top: object = None,
    steps: int | None = None,
    caps: CapsSpec = CapType.BUTT,
    style: VNFStyle = VNFStyle.MIN_EDGE,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> VNF | "Solid":
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
        steps:  Number of slices per rim treatment; resolved from the rim radius and the
                ambient facet controls when omitted (SPEC R-1).
        fn:     Fixed fragment count for the rim arcs; ambient default when omitted.
        fa:     Minimum fragment angle for the rim arcs.
        fs:     Minimum fragment size for the rim arcs.
        caps:   Cap the flat top and bottom (default True); bool or [bool, bool].
        style:  ``vnf_vertex_array`` quad-subdivision style.

    Returns:
        A :class:`~pybosl2.vnf.VNF`.

    """
    from pybosl2.path2d import Path2D as _Path

    if not (height > 0):
        raise Bosl2ValueError("offset_sweep(): height must be positive.")
    cap_specs = norm_caps(caps)

    base = [[float(p[0]), float(p[1])] for p in path]

    def _to_desc(j: object) -> "OSProfile | dict[str, object] | None":
        if j is None:
            return None
        if isinstance(j, (dict, OSProfile)):
            return j
        return os_circle(cast("float", j))

    bottom_desc = _to_desc(bottom)
    top_desc = _to_desc(top)

    # ---------------------------------------------------------------------------
    # Build (delta, z) pairs for each level of the stack.
    # ---------------------------------------------------------------------------

    def _arc_column(desc: Any, n: int) -> tuple[list[float], list[float]]:
        """Return (deltas, zs) for one rim, length n+1."""
        if desc is None:
            return ([0.0], [0.0])
        t = desc.get("type", "circle")
        if t == OSType.FLAT or (t == OSType.CIRCLE and desc["r"] == 0.0):
            return ([0.0], [0.0])

        if t == OSType.CIRCLE:
            r = desc["r"]
            h = abs(desc["h"])
            ar = abs(r)
            sign = -1.0 if r > 0 else 1.0
            angles = [math.pi / 2 * i / n for i in range(n + 1)]
            deltas = [sign * ar * (1.0 - math.cos(a)) for a in angles]
            zs = [h * math.sin(a) for a in angles]
            return (deltas, zs)

        elif t == OSType.TEARDROP:
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

        elif t == OSType.SMOOTH:
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

        elif t == OSType.CHAMFER:
            w = desc["width"]
            h = abs(desc["height"])
            deltas = [-w * i / n for i in range(n + 1)]
            zs = [h * i / n for i in range(n + 1)]
            return (deltas, zs)

        elif t == OSType.PROFILE:
            pts = desc["points"]
            pts_arr = np.asarray(pts, dtype=float)
            zs_in = pts_arr[:, 1]
            xs_in = pts_arr[:, 0]
            z_min, z_max = zs_in[0], zs_in[-1]
            zs = [z_min + (z_max - z_min) * i / n for i in range(n + 1)]
            deltas = [-float(np.interp(z, zs_in, xs_in)) for z in zs]
            return (deltas, zs)

        return ([0.0], [0.0])

    def _rim_steps(desc: Any) -> int:
        """Slices for one rim treatment.

        What the caller asked for, else the facet count implied by the rim's radius when any
        resolution was set (explicitly or ambiently), else BOSL2's own default of 16. Deriving
        unconditionally would COARSEN a small rim -- a 2 mm roundover is 4 segments at $fa=12 --
        so the derived value is used only when someone actually asked for a resolution (R-5).
        """
        if steps is not None:
            return int(steps)
        resolved_fn, resolved_fa, resolved_fs = resolve_facets(fn, fa, fs)
        if resolved_fn is None and resolved_fa is None and resolved_fs is None:
            return 16
        radius = abs(float(desc.get("r", 0.0) or desc.get("h", 0.0) or 0.0)) if desc else 0.0
        if not radius:
            return 16
        return max(4, _segs(radius, resolved_fn, resolved_fa, resolved_fs) // 4)

    bot_deltas, bot_zs = _arc_column(bottom_desc, _rim_steps(bottom_desc))
    top_deltas, top_zs = _arc_column(top_desc, _rim_steps(top_desc))

    h_bot = bot_zs[-1]
    h_top = top_zs[-1]
    if not (h_bot + h_top <= height):
        raise Bosl2ValueError("offset_sweep(): the sum of the bottom and top rim heights exceeds the extrusion height.")

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
    from pybosl2.path3d import Path3D as _Path3D

    norm = [_Path3D(row).subdivide_path(points=maxn, closed=True) for row in profiles_3d]

    if has_decorative_caps(cap_specs):
        vnf = VNF.vertex_array(norm, col_wrap=True, style=style)
        vnf = vnf if vnf.volume() >= 0 else vnf.reverse()
        norm_arr = np.asarray(norm, dtype=float)
        center1 = list(norm_arr[0].mean(axis=0))
        center2 = list(norm_arr[-1].mean(axis=0))
        radius = float(max(np.linalg.norm(p[:2] - np.asarray(center1[:2])) for p in norm_arr[0]))
        outdir1 = [center1[i] - center2[i] for i in range(3)]
        outdir2 = [center2[i] - center1[i] for i in range(3)]
        return vnf_with_decorative_caps(vnf, cap_specs, False, [center1, center2], [outdir1, outdir2], radius)

    vnf = VNF.vertex_array(
        norm,
        caps=cap_specs,
        col_wrap=True,
        style=style,
    )
    return vnf if vnf.volume() >= 0 else vnf.reverse()


def _convex_offset_extrude(
    path: Sequence[Sequence[float]],
    height: float,
    bottom: object = None,
    top: object = None,
    steps: int = 16,
    caps: CapsSpec = CapType.BUTT,
    style: VNFStyle = VNFStyle.MIN_EDGE,
) -> VNF | "Solid":
    """Offset sweep/extrusion of a 2-D shape (BOSL2 convex_offset_extrude()).

    An alias for :func:`_offset_sweep` to match BOSL2's geometry-oriented name.
    """
    return _offset_sweep(path, height=height, bottom=bottom, top=top, steps=steps, caps=caps, style=style)


def _rounded_prism(
    bottom: Sequence[Sequence[float]],
    top: Sequence[Sequence[float]] | None = None,
    height: float | None = None,
    joint_top: float | dict[str, object] | None = None,
    joint_bottom: float | dict[str, object] | None = None,
    joint_sides: float | list[float] | None = None,
    curvature_sides: float | list[float] | None = None,
    steps: int = 16,
    caps: CapsSpec = CapType.BUTT,
    style: VNFStyle = VNFStyle.MIN_EDGE,
    joint_bot: float | dict[str, object] | None = None,
    k_sides: float | list[float] | None = None,
) -> VNF | "Solid":
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
        joint_bot:   Alias for *joint_bottom*, provided for BOSL2 compatibility.
        k_sides:     Alias for *curvature_sides*, provided for BOSL2 compatibility.

    Returns:
        A :class:`~pybosl2.vnf.VNF`.

    """
    from pybosl2.path2d import Path2D as _Path

    # joint_bot / k_sides are BOSL2's names for joint_bottom / curvature_sides
    joint_bot = joint_bottom if joint_bottom is not None else joint_bot
    k_sides = curvature_sides if curvature_sides is not None else k_sides

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

        if k_sides is not None:  # a curvature turns the side rounding into a smooth join
            b_rounded = _rc(b_2d, method=RoundingMethod.SMOOTH, joint=joint_sides, curvature=k_sides)
            t_rounded = _rc(t_2d, method=RoundingMethod.SMOOTH, joint=joint_sides, curvature=k_sides)
        else:
            b_rounded = _rc(b_2d, method=RoundingMethod.CIRCLE, radius=joint_sides)
            t_rounded = _rc(t_2d, method=RoundingMethod.CIRCLE, radius=joint_sides)
    else:
        b_rounded = b_2d
        t_rounded = t_2d

    # Convert rim treatments to dict descriptors
    def _to_desc(j: object) -> "OSProfile | dict[str, object] | None":
        if j is None:
            return None
        if isinstance(j, (dict, OSProfile)):
            return j
        return os_circle(cast("float", j))

    desc_top = _to_desc(joint_top)
    desc_bot = _to_desc(joint_bot)

    # Re-use the (delta, z) levels calculation from offset_sweep
    def _arc_column(desc: Any, n: int) -> tuple[list[float], list[float]]:
        if desc is None:
            return ([0.0], [0.0])
        t = desc.get("type", "circle")
        if t == OSType.FLAT or (t == OSType.CIRCLE and desc["r"] == 0.0):
            return ([0.0], [0.0])

        if t == OSType.CIRCLE:
            r = desc["r"]
            h = abs(desc["h"])
            ar: float = abs(r)
            sign = -1.0 if r > 0 else 1.0
            angles = [math.pi / 2 * i / n for i in range(n + 1)]
            deltas = [sign * ar * (1.0 - math.cos(a)) for a in angles]
            zs = [h * math.sin(a) for a in angles]
            return (deltas, zs)

        elif t == OSType.TEARDROP:
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

        elif t == OSType.SMOOTH:
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

        elif t == OSType.CHAMFER:
            w = desc["width"]
            h = abs(desc["height"])
            deltas = [-w * i / n for i in range(n + 1)]
            zs = [h * i / n for i in range(n + 1)]
            return (deltas, zs)

        elif t == OSType.PROFILE:
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
    if not (h_bot + h_top <= h_val):
        raise Bosl2ValueError("rounded_prism(): the sum of the bottom and top rim heights exceeds the prism height.")

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
    if not (len(b_arr) == len(t_arr)):
        raise Bosl2ValueError("rounded_prism(): bottom and top polygons must have the same number of vertices.")

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
    from pybosl2.path3d import Path3D as _Path3D

    norm = [_Path3D(row).subdivide_path(points=maxn, closed=True) for row in profiles_3d]
    cap_specs = norm_caps(caps)

    if has_decorative_caps(cap_specs):
        vnf = VNF.vertex_array(norm, col_wrap=True, style=style)
        vnf = vnf if vnf.volume() >= 0 else vnf.reverse()
        norm_arr = np.asarray(norm, dtype=float)
        center1 = list(norm_arr[0].mean(axis=0))
        center2 = list(norm_arr[-1].mean(axis=0))
        radius = float(max(np.linalg.norm(p[:2] - np.asarray(center1[:2])) for p in norm_arr[0]))
        outdir1 = [center1[i] - center2[i] for i in range(3)]
        outdir2 = [center2[i] - center1[i] for i in range(3)]
        return vnf_with_decorative_caps(vnf, cap_specs, False, [center1, center2], [outdir1, outdir2], radius)

    vnf = VNF.vertex_array(
        norm,
        caps=cap_specs,
        col_wrap=True,
        style=style,
    )
    return vnf if vnf.volume() >= 0 else vnf.reverse()


def _join_prism(
    polygon: Sequence[Sequence[float]],
    height: float,
    fillet: float = 0.0,
    steps: int = 16,
    caps: CapsSpec = CapType.BUTT,
    style: VNFStyle = VNFStyle.MIN_EDGE,
) -> VNF | "Solid":
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
    steps: int | None = None,
    caps: CapsSpec = CapType.BUTT,
    style: VNFStyle = VNFStyle.MIN_EDGE,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> VNF | "Solid":
    """Construct a filleted prism connecting two objects (BOSL2 prism_connector()).

    Uses :func:`_offset_sweep` with outward flares at both ends (os_circle(radius=-fillet))
    to create the filleted joints.
    """
    f1 = fillet1 if fillet1 is not None else fillet
    f2 = fillet2 if fillet2 is not None else fillet
    bot_desc = os_circle(radius=-f1) if f1 > 0 else None
    top_desc = os_circle(radius=-f2) if f2 > 0 else None
    return _offset_sweep(
        profile,
        height=length,
        bottom=bot_desc,
        top=top_desc,
        steps=steps,
        caps=caps,
        style=style,
        fn=fn,
        fa=fa,
        fs=fs,
    )


def _attach_prism(
    profile: Sequence[Sequence[float]],
    length: float,
    fillet: float = 0.0,
    rounding: float = 0.0,
    steps: int | None = None,
    caps: CapsSpec = CapType.BUTT,
    style: VNFStyle = VNFStyle.MIN_EDGE,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> VNF | "Solid":
    """Attach a filleted prism with optional rounded end (BOSL2 attach_prism()).

    Uses :func:`_offset_sweep` with a bottom flare (os_circle(radius=-fillet)) and top
    roundover (os_circle(radius=rounding)) to create the filleted joints.
    """
    bot_desc = os_circle(radius=-fillet) if fillet > 0 else None
    top_desc = os_circle(radius=rounding) if rounding > 0 else None
    return _offset_sweep(
        profile,
        height=length,
        bottom=bot_desc,
        top=top_desc,
        steps=steps,
        caps=caps,
        style=style,
        fn=fn,
        fa=fa,
        fs=fs,
    )


def _bent_cutout_mask(
    radius: float,
    thickness: float,
    path: Sequence[Sequence[float]],
    style: VNFStyle = VNFStyle.MIN_EDGE,
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

    vnf = VNF.vertex_array([inner_ring, outer_ring], caps=CapType.BUTT, col_wrap=True, style=style)
    return vnf if vnf.volume() >= 0 else vnf.reverse()


# ---------------------------------------------------------------------------------------------
# path_sweep2d() -- sweep a 2-D shape along a 2-D path (creases allowed)
# ---------------------------------------------------------------------------------------------


def _path_sweep2d(
    shape: "PathLike",
    path: Sequence[Sequence[float]] | Path2D,
    closed: bool = False,
    caps: CapsSpec = CapType.BUTT,
    quality: int = 1,
    style: VNFStyle = VNFStyle.MIN_EDGE,
) -> VNF | "Solid":
    """Sweep a 2-D *shape* along a 2-D *path* (internal implementation).

    Public API: use :meth:`Sweepable.path_sweep2d` instead of calling this directly.
    """
    from pybosl2.path2d import Path2D

    _ = quality
    shp: Path2D = shape if isinstance(shape, Path2D) else Path2D(shape)
    p: Path2D = path if isinstance(path, Path2D) else Path2D(path)
    cap_specs = norm_caps(caps, closed=closed)
    profile = shp if not shp.is_clockwise() else shp.reverse()  # ccw_polygon
    flip = -1.0 if (closed and p.is_clockwise()) else 1.0
    pth = p if flip > 0 else p.reverse()

    # For each profile point, offset the path by -flip*x and lift the result to z=y.
    per_point = []
    for pt in profile:
        off = pth.offset(delta=-flip * pt[0], same_length=True)
        if not (len(off) == len(pth)):  # pragma: no cover
            # defensive: offset(same_length=True) returns the raw per-corner
            # construction, one point per input point, so the lengths cannot disagree here.
            raise Bosl2ValueError(
                "path_sweep2d(): the offset dropped points (the shape is too wide for the path "
                "here); reduce the shape's X extent."
            )
        per_point.append([[float(p[0]), float(p[1]), float(pt[1])] for p in off])
    # transpose: one grid row per path position, each a full cross-section
    grid = [[per_point[j][i] for j in range(len(profile))] for i in range(len(pth))]
    if closed:
        grid = grid + [grid[0]]

    if has_decorative_caps(cap_specs):
        vnf = VNF.vertex_array(grid, col_wrap=True, style=style)
        vnf = vnf if vnf.volume() >= 0 else vnf.reverse()
        grid_arr = np.asarray(grid, dtype=float)
        center1 = list(grid_arr[0].mean(axis=0))
        center2 = list(grid_arr[-1].mean(axis=0))
        radius = float(max(np.linalg.norm(p[:2] - np.asarray(center1[:2])) for p in grid_arr[0]))
        outdir1 = [center1[i] - center2[i] for i in range(3)]
        outdir2 = [center2[i] - center1[i] for i in range(3)]
        return vnf_with_decorative_caps(vnf, cap_specs, closed, [center1, center2], [outdir1, outdir2], radius)

    vnf = VNF.vertex_array(
        grid,
        caps=cap_specs,
        col_wrap=True,
        style=style,
    )
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


def _smooth(data: Sequence[float], length: int, closed: bool = False, angle: bool = False) -> list[float]:
    """Moving-average smooth of *data* over a window of *length*.

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
    num_copies: int | Sequence[int],
    twist: float | Sequence[float] | None = None,
    scale: float | Sequence[float] | None = None,
    smoothlen: int = 1,
    long: bool = False,
    turns: float = 0,
    closed: bool = False,
    method: ResampleMethod = ResampleMethod.LENGTH,
) -> list[list[list[float]]]:
    """Resample a list of 4x4 transforms to uniform screw-motion spacing.

    Interpolates between successive transforms along their screw motion (via :func:`rot_decode`),
    optionally adding *twist* and *scale* (smoothed over *smoothlen*). Handy for regularizing the
    transform list from :meth:`Sweepable.path_sweep_transforms` before handing it to :func:`sweep`.

    Args:
        rotlist: list of 4x4 transform matrices
        num_copies: number of output samples (method="length") or samples per gap (method="count")
        twist:   extra twist in degrees (scalar or per-gap list)
        scale:   extra scale (scalar or per-gap list, multiplied cumulatively)
        smoothlen: odd window length for smoothing the twist/scale (default 1 = none)
        long:    take the >180-degree rotation at a gap (scalar or per-gap list)
        turns:   extra full turns to add at a gap (scalar or per-gap list)
        closed:  the transform list forms a loop (default False)
        method:  "length" (uniform screw-distance) or "count" (fixed samples per gap)

    """
    rotlist_extra = [np.asarray(t, dtype=float) for t in rotlist]
    if not (smoothlen > 0):
        raise Bosl2ValueError("rot_resample(): smoothlen must be a positive odd integer.")
    if not (smoothlen % 2 == 1):
        raise Bosl2ValueError("rot_resample(): smoothlen must be a positive odd integer.")
    if not isinstance(method, ResampleMethod):
        raise Bosl2ValueError(f"rot_resample(): method must be a ResampleMethod member, got {method!r}.")
    m = len(rotlist_extra)
    tcount = m + (0 if closed else -1)
    if method == ResampleMethod.LENGTH:
        if not (isinstance(num_copies, int)):
            raise Bosl2ValueError("rot_resample(): num_copies must be an integer for method='length'.")
        count = (num_copies + 1) if closed else num_copies
    else:
        count = int(tcount * num_copies + 1) if isinstance(num_copies, (int, float)) else int(sum(num_copies) + 1)
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
    if method == ResampleMethod.LENGTH and not all(x > 0 for x in length):
        raise Bosl2ValueError("rot_resample(): a repeated/origin rotation makes method='length' undefined.")

    cumlen = [0.0]
    for x in length:
        cumlen.append(cumlen[-1] + x)
    totlen = cumlen[-1]
    stepsize = totlen / (count - 1) if count > 1 else totlen

    if method == ResampleMethod.COUNT:
        nlist = [int(num_copies)] * tcount if isinstance(num_copies, (int, float)) else [int(x) for x in num_copies]
        samples = [[k / N for k in range(N)] for N in nlist]
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
