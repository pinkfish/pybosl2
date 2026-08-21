# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/isosurface.py
#    Metaball field primitives that produce scalar distance fields for isosurface
#    meshing via :meth:`VNF.from_metaballs`.  Each ``mb_*`` function returns a
#    :class:`Metaball` — a callable that maps ``(N,3)`` points to ``(N,)`` field
#    values.  Position a metaball in space by wrapping it in a
#    :class:`MetaballSpec` (transform + metaball) and pass a list of them to
#    :meth:`VNF.from_metaballs`.
#
# FileSummary: Metaball field primitives for VNF isosurface meshing (BOSL2 metaballs3d.scad).
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

"""Metaball field primitives for VNF isosurface meshing (BOSL2 metaballs3d.scad)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from pybosl2._helpers import pick_radius as _pick_radius

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from pybosl2.bounds import Bounds2D
    from pybosl2.points import Point

INF = math.inf


def _mb_cutoff(dist: np.ndarray, cutoff: float) -> np.ndarray:
    if not math.isfinite(cutoff):
        return np.ones_like(dist)
    out = np.zeros_like(dist)
    m: np.ndarray = dist < cutoff
    out[m] = 0.5 * (np.cos(np.pi * (dist[m] / cutoff) ** 4) + 1)
    return out


def _mb_field(dist: np.ndarray, base: float, influence: float, cutoff: float, neg: int) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = base / dist
        v = ratio if influence == 1 else np.power(ratio, 1.0 / influence)
    if math.isfinite(cutoff):
        v = _mb_cutoff(dist, cutoff) * v
    return neg * v


def _squircle_se_exponent(squareness: float) -> float:
    s = min(0.998, squareness)
    rho = 1 + s * (math.sqrt(2) - 1)
    x = rho / math.sqrt(2)
    return math.log(0.5) / math.log(x)


class Metaball:
    """A metaball field primitive: ``field(pts)`` over ``(N, 3)`` points.

    Combine several with :meth:`VNF.from_metaballs`.

    Args:
        field: A vectorised ``(N, 3) → (N,)`` callable.
        neg: 1 for additive, -1 for subtractive.

    """

    def __init__(self, field: Callable[[np.ndarray], np.ndarray], neg: int = 1):
        """Wrap a vectorised field function as a metaball primitive.

        Prefer the factories -- :meth:`sphere`, :meth:`cuboid`, :meth:`torus`, :meth:`capsule`,
        :meth:`disk`, :meth:`octahedron`, :meth:`connector` -- and use this directly only for a
        field of your own.

        Args:
            field: A vectorised ``(N, 3) -> (N,)`` callable giving the field strength at each point.
            neg: 1 for an additive metaball, -1 for a subtractive one.

        """
        self.field = field
        self.neg = neg

    def __call__(self, pt: np.ndarray) -> float:
        """Evaluate the field at a single point.

        Args:
            pt: One ``[x, y, z]`` point.

        Returns:
            The field strength there.

        """
        return float(self.field(np.atleast_2d(np.asarray(pt, dtype=float)))[0])

    def at(self, position: "np.ndarray | Point | Sequence[float]") -> "MetaballSpec":
        """Place this metaball, returning the positioned spec :meth:`VNF.from_metaballs` consumes.

        Args:
            position: An ``[x, y, z]`` position, or a 4x4 transform matrix for a rotated or
                scaled placement.

        Returns:
            A :class:`MetaballSpec` pairing this field with that placement.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Metaball
                from pybosl2.bounds import Bounds3D
                from pybosl2.vnf import VNF

                spec = [Metaball.sphere(radius=12).at([-10, 0, 0]),
                        Metaball.sphere(radius=12).at([10, 0, 0])]
                VNF.from_metaballs(
                    spec, Bounds3D(-30, -20, -20, 30, 20, 20, 60, 40, 40), voxel_size=2
                ).polyhedron().show()

        """
        return MetaballSpec(np.asarray(position, dtype=float), self)

    # -- field primitives: the BOSL2 mb_* family, as factories on the class (SPEC P-8) --------

    @staticmethod
    def sphere(
        radius: float | None = None,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
        diameter: float | None = None,
    ) -> Metaball:
        """Return a spherical metaball field.

        Args:
            radius: Sphere radius (mutually exclusive with *diameter*).
            cutoff: Distance beyond which the field is clamped to 0. ``inf`` = no cutoff.
            influence: Blending strength (smaller = sharper).
            negative: If True, produce a subtractive metaball.
            diameter: Sphere diameter.

        Returns:
            A :class:`Metaball` primitive.

        Raises:
            ValueError: If no positive radius or diameter is given.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Metaball
                from pybosl2.bounds import Bounds3D
                from pybosl2.vnf import VNF

                spec = [Metaball.sphere(radius=15).at([0, 0, 0])]
                VNF.from_metaballs(
                    spec, Bounds3D(-20, -20, -20, 20, 20, 20, 40, 40, 40), voxel_size=2
                ).polyhedron().show()

        """
        rr = _pick_radius(radius=radius, diameter=diameter, dflt=None)
        if not (rr):
            raise ValueError("Metaball.sphere(): need a positive radius or diameter.")
        if not (rr > 0):
            raise ValueError("Metaball.sphere(): need a positive radius or diameter.")
        neg = -1 if negative else 1

        def field(pts: np.ndarray) -> np.ndarray:
            dist: np.ndarray = np.linalg.norm(pts, axis=1)
            return _mb_field(dist, rr, influence, cutoff, neg)

        return Metaball(field, neg)

    @staticmethod
    def cuboid(
        size: tuple[float, float, float] | float,
        squareness: float = 0.5,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
    ) -> Metaball:
        """Return a rounded-cuboid metaball field.

        Args:
            size: A scalar (cube edge) or ``(dx, dy, dz)`` tuple.
            squareness: 0 = fully round, 1 = sharp square edges.
            cutoff: Distance beyond which the field is clamped to 0.
            influence: Blending strength.
            negative: If True, produce a subtractive metaball.

        Returns:
            A :class:`Metaball` primitive.

        Raises:
            ValueError: If *squareness* is not in ``[0, 1]``.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Metaball
                from pybosl2.bounds import Bounds3D
                from pybosl2.vnf import VNF

                spec = [Metaball.cuboid(size=10, squareness=0.3).at([-12, 0, 0]),
                        Metaball.cuboid(size=10, squareness=0.3).at([12, 0, 0])]
                VNF.from_metaballs(
                    spec, Bounds3D(-25, -15, -15, 25, 15, 15, 50, 30, 30), voxel_size=2
                ).polyhedron().show()

        """
        if not (0 <= squareness <= 1):
            raise ValueError("Metaball.cuboid(): squareness must be in [0, 1].")
        xp = _squircle_se_exponent(squareness)
        inv = (
            np.array([2 / size] * 3, dtype=float)
            if isinstance(size, (int, float))
            else 2 / np.asarray(size, dtype=float)
        )
        neg = -1 if negative else 1

        def field(pts: np.ndarray) -> np.ndarray:
            p: np.ndarray = np.abs(pts * inv)
            dist: np.ndarray = np.max(p, axis=1) if xp >= 1100 else np.sum(p**xp, axis=1) ** (1 / xp)
            return _mb_field(dist, 1.0, influence, cutoff, neg)

        return Metaball(field, neg)

    @staticmethod
    def torus(
        major_radius: float | None = None,
        minor_radius: float | None = None,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
        major_diameter: float | None = None,
        minor_diameter: float | None = None,
    ) -> Metaball:
        """Return a torus metaball field.

        Args:
            major_radius: Distance from the origin to the tube centre.
            minor_radius: Tube radius.
            cutoff: Distance beyond which the field is clamped to 0.
            influence: Blending strength.
            negative: If True, produce a subtractive metaball.
            major_diameter: Overrides *major_radius*.
            minor_diameter: Overrides *minor_radius*.

        Returns:
            A :class:`Metaball` primitive.

        Raises:
            ValueError: If either radius is missing or non-positive.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Metaball
                from pybosl2.bounds import Bounds3D
                from pybosl2.vnf import VNF

                spec = [Metaball.torus(major_radius=15, minor_radius=5).at([0, 0, 0])]
                VNF.from_metaballs(
                    spec, Bounds3D(-20, -20, -10, 20, 20, 10, 40, 40, 20), voxel_size=2
                ).polyhedron().show()

        """
        rmaj, rmin = (
            (_pick_radius(radius=major_radius, diameter=major_diameter, dflt=None)),
            (_pick_radius(radius=minor_radius, diameter=minor_diameter, dflt=None)),
        )
        if not (rmaj):
            raise ValueError("Metaball.torus(): need positive major_radius and minor_radius.")
        if not (rmin):
            raise ValueError("Metaball.torus(): need positive major_radius and minor_radius.")
        if not (rmaj > 0):
            raise ValueError("Metaball.torus(): need positive major_radius and minor_radius.")
        if not (rmin > 0):
            raise ValueError("Metaball.torus(): need positive major_radius and minor_radius.")
        neg = -1 if negative else 1

        def field(pts: np.ndarray) -> np.ndarray:
            rad: np.ndarray = np.hypot(pts[:, 0], pts[:, 1]) - rmaj
            dist: np.ndarray = np.hypot(rad, pts[:, 2])
            return _mb_field(dist, rmin, influence, cutoff, neg)

        return Metaball(field, neg)

    @staticmethod
    def capsule(
        height: float | None = None,
        radius: float | None = None,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
        diameter: float | None = None,
    ) -> Metaball:
        """Return a capsule (round-ended cylinder) metaball field.

        Args:
            height: Total length including rounded ends.
            radius: Shaft radius.
            cutoff: Distance beyond which the field is clamped to 0.
            influence: Blending strength.
            negative: If True, produce a subtractive metaball.
            diameter: Shaft diameter.

        Returns:
            A :class:`Metaball` primitive.

        Raises:
            ValueError: If *height* or *radius* is missing, non-positive, or shaft too short.

        """
        rr = _pick_radius(radius=radius, diameter=diameter, dflt=None)
        if not (height):
            raise ValueError("Metaball.capsule(): need positive height and radius.")
        if not (rr):
            raise ValueError("Metaball.capsule(): need positive height and radius.")
        if not (height > 0):
            raise ValueError("Metaball.capsule(): need positive height and radius.")
        if not (rr > 0):
            raise ValueError("Metaball.capsule(): need positive height and radius.")
        hl = (height - 2 * rr) / 2
        if not (hl > 0):
            raise ValueError("Metaball.capsule(): total length must exceed the two rounded ends.")
        neg = -1 if negative else 1

        def field(pts: np.ndarray) -> np.ndarray:
            z = pts[:, 2]
            rxy: np.ndarray = np.hypot(pts[:, 0], pts[:, 1])
            below: np.ndarray = z < -hl
            above: np.ndarray = z > hl
            dist: np.ndarray = np.where(below, np.hypot(rxy, z + hl), np.where(above, np.hypot(rxy, z - hl), rxy))
            return _mb_field(dist, rr, influence, cutoff, neg)

        return Metaball(field, neg)

    @staticmethod
    def disk(
        height: float | None = None,
        radius: float | None = None,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
        diameter: float | None = None,
    ) -> Metaball:
        """Return a rounded-edge disk metaball field.

        Args:
            height: Disk thickness.
            radius: Outer radius.
            cutoff: Distance beyond which the field is clamped to 0.
            influence: Blending strength.
            negative: If True, produce a subtractive metaball.
            diameter: Outer diameter.

        Returns:
            A :class:`Metaball` primitive.

        Raises:
            ValueError: If *height* or *radius* is missing, non-positive, or too thin.

        """
        rr = _pick_radius(radius=radius, diameter=diameter, dflt=None)
        if not (height):
            raise ValueError("Metaball.disk(): need positive height and radius.")
        if not (rr):
            raise ValueError("Metaball.disk(): need positive height and radius.")
        if not (height > 0):
            raise ValueError("Metaball.disk(): need positive height and radius.")
        if not (rr > 0):
            raise ValueError("Metaball.disk(): need positive height and radius.")
        hl = height / 2
        ri = rr - hl
        if not (ri > 0):
            raise ValueError("Metaball.disk(): diameter must exceed the thickness.")
        neg = -1 if negative else 1

        def field(pts: np.ndarray) -> np.ndarray:
            rxy: np.ndarray = np.hypot(pts[:, 0], pts[:, 1])
            z = pts[:, 2]
            dist: np.ndarray = np.where(rxy < ri, np.abs(z), np.hypot(rxy - ri, z))
            return _mb_field(dist, hl, influence, cutoff, neg)

        return Metaball(field, neg)

    @staticmethod
    def octahedron(
        size: tuple[float, float, float] | float,
        squareness: float = 0.5,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
    ) -> Metaball:
        """Return a rounded-octahedron metaball field.

        Args:
            size: A scalar (circumscribed cube edge) or ``(dx, dy, dz)`` tuple.
            squareness: 0 = round, 1 = sharp octahedron edges.
            cutoff: Distance beyond which the field is clamped to 0.
            influence: Blending strength.
            negative: If True, produce a subtractive metaball.

        Returns:
            A :class:`Metaball` primitive.

        Raises:
            ValueError: If *squareness* is not in ``[0, 1]``.

        """
        if not (0 <= squareness <= 1):
            raise ValueError("Metaball.octahedron(): squareness must be in [0, 1].")
        xp = _squircle_se_exponent(squareness)

        def _octdist(p: np.ndarray) -> np.ndarray:
            if xp >= 1100:
                octa: np.ndarray = np.abs(p[:, 0]) + np.abs(p[:, 1]) + np.abs(p[:, 2])
                return octa
            a = np.abs(p[:, 0] + p[:, 1] + p[:, 2]) ** xp
            b = np.abs(-p[:, 0] - p[:, 1] + p[:, 2]) ** xp
            c = np.abs(-p[:, 0] + p[:, 1] - p[:, 2]) ** xp
            e = np.abs(p[:, 0] - p[:, 1] - p[:, 2]) ** xp
            return (a + b + c + e) ** (1 / xp)  # type: ignore[no-any-return]

        corr = 1.0 / _octdist(np.array([[1 / 3, 1 / 3, 1 / 3]]))[0]
        inv = (
            corr * np.array([2 / size] * 3, dtype=float)
            if isinstance(size, (int, float))
            else corr * 2 / np.asarray(size, dtype=float)
        )
        neg = -1 if negative else 1

        def field(pts: np.ndarray) -> np.ndarray:
            dist: np.ndarray = _octdist(pts * inv)
            return _mb_field(dist, 1.0, influence, cutoff, neg)

        return Metaball(field, neg)

    @staticmethod
    def connector(
        p1: Point,
        p2: Point,
        radius: float | None = None,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
        diameter: float | None = None,
    ) -> Metaball:
        """Return a capsule metaball field spanning from *p1* to *p2*.

        Args:
            p1: Start :class:`~pybosl2.points.Point`.
            p2: End :class:`~pybosl2.points.Point` (must be distinct from *p1*).
            radius: Shaft radius.
            cutoff: Distance beyond which the field is clamped to 0.
            influence: Blending strength.
            negative: If True, produce a subtractive metaball.
            diameter: Shaft diameter.

        Returns:
            A :class:`Metaball` primitive.

        Raises:
            ValueError: If *radius* is missing, non-positive, or *p1* equals *p2*.

        """
        from pybosl2.transforms import axis_angle_matrix, rot_from_to

        rr = _pick_radius(radius=radius, diameter=diameter, dflt=None)
        a, b = np.asarray(p1, dtype=float), np.asarray(p2, dtype=float)
        if not (rr):
            raise ValueError("Metaball.connector(): need distinct points and positive radius.")
        if not (rr > 0):
            raise ValueError("Metaball.connector(): need distinct points and positive radius.")
        if np.array_equal(a, b):
            raise ValueError("Metaball.connector(): need distinct points and positive radius.")
        neg = -1 if negative else 1
        dc: np.ndarray = b - a
        height: float = float(np.linalg.norm(dc)) / 2
        angle, axis = rot_from_to(dc, [0, 0, 1])
        m3: np.ndarray = np.asarray(axis_angle_matrix(angle, axis), dtype=float)

        def field(pts: np.ndarray) -> np.ndarray:
            local: np.ndarray = (pts - (a + b) / 2) @ m3.T
            z = local[:, 2]
            rxy: np.ndarray = np.hypot(local[:, 0], local[:, 1])
            below: np.ndarray = z < -height
            above: np.ndarray = z > height
            dist: np.ndarray = np.where(
                below, np.hypot(rxy, z + height), np.where(above, np.hypot(rxy, z - height), rxy)
            )
            return _mb_field(dist, rr, influence, cutoff, neg)

        return Metaball(field, neg)


@dataclass
class MetaballSpec:
    """A positioned metaball: a transform (always stored as a 4×4 matrix) and a :class:`Metaball`.

    Args:
        transform: A 4×4 matrix or a 3-element position (translation), normalized to 4×4.
        metaball: The field primitive to place at that transform.

    """

    transform: np.ndarray = field(init=False)
    metaball: Metaball = field(init=False)

    def __init__(self, transform: np.ndarray | Point, metaball: Metaball) -> None:
        """Pair a metaball with where it sits.

        :meth:`Metaball.at` is the readable way to build one.

        Args:
            transform: A 4x4 matrix, or an ``[x, y, z]`` position (normalised to a 4x4).
            metaball: The field primitive to place there.

        """
        a = np.asarray(transform, dtype=float)
        if a.shape != (4, 4):
            m = np.eye(4)
            m[:3, 3] = a[:3]
            a = m
        self.transform = a
        self.metaball = metaball


#: Back-compat spellings of the two classes, from when they were private.
_Metaball = Metaball
_MetaballSpec = MetaballSpec

# The BOSL2 spellings, kept as aliases of the factories above (SPEC P-6): `mb_sphere(...)` is
# `Metaball.sphere(...)`. New code should use the class -- these stay for one release.
mb_sphere = Metaball.sphere
mb_cuboid = Metaball.cuboid
mb_torus = Metaball.torus
mb_capsule = Metaball.capsule
mb_disk = Metaball.disk
mb_octahedron = Metaball.octahedron
mb_connector = Metaball.connector


def metaballs2d(
    spec: list[MetaballSpec],
    bounding_box: "Bounds2D",
    pixel_size: float | None = None,
    pixel_count: int | None = None,
    isovalue: float = 1,
    closed: bool = True,
    exact_bounds: bool = False,
) -> list[list[list[float]]]:
    """Generate 2-D contour paths from metaball field primitives.

    The metaball spec uses the same 3-D transforms and field primitives as
    :meth:`VNF.from_metaballs`, but evaluated on the z=0 plane to produce
    a 2-D contour via marching squares.

    Args:
        spec: A list of :class:`MetaballSpec` entries,
            each holding a 4×4 transform and a :class:`Metaball`.
        bounding_box: A :class:`~pybosl2.bounds.Bounds2D`.
        pixel_size: Isotropic pixel size.
        pixel_count: Approximate total pixel count.
        isovalue: Field threshold.  Defaults to 1.
        closed: If True, return only closed contour loops.
        exact_bounds: If True, use *bounding_box* exactly.

    Returns:
        A list of contour paths, each a list of ``[x, y]`` points.

    Examples:
        .. pythonscad-example::

            import numpy as np
            from pybosl2 import mb_sphere, MetaballSpec, metaballs2d, Bounds2D
            from pybosl2.path2d import Path2D

            spec = [
                MetaballSpec([-14, 0, 0], mb_sphere(12)),
                MetaballSpec([14, 0, 0], mb_sphere(12)),
            ]
            paths = metaballs2d(spec, Bounds2D(-40, -20, 40, 20, 80, 40), pixel_size=2)
            Path2D(paths[0]).stroke(width=0.5).linear_extrude(height=2).show()

    """
    if not (spec):
        raise ValueError("metaballs2d(): the spec is empty.")
    from pybosl2.vnf import contour

    invs: list[np.ndarray] = [np.linalg.inv(s.transform) for s in spec]

    def field_2d(pts: np.ndarray) -> np.ndarray:
        pts3d: np.ndarray = np.hstack([pts, np.zeros((len(pts), 1))])
        homo: np.ndarray = np.hstack([pts3d, np.ones((len(pts), 1))])
        total: np.ndarray = np.zeros(len(pts))
        for s, inv in zip(spec, invs, strict=False):
            local: np.ndarray = (inv @ homo.T).T[:, :3]
            total += s.metaball.field(local)
        return total

    return contour(
        field_2d,
        float(isovalue),
        bounding_box,
        pixel_size=pixel_size,
        pixel_count=pixel_count,
        closed=closed,
        exact_bounds=exact_bounds,
    )


__all__ = [
    "Metaball",
    "MetaballSpec",
    "INF",
    "mb_sphere",
    "mb_cuboid",
    "mb_torus",
    "mb_capsule",
    "mb_disk",
    "mb_octahedron",
    "mb_connector",
    "metaballs2d",
]
