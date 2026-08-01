# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/isosurface.py
#    Metaball field primitives — each returns a :class:`Metaball` that a
#    user combines with :meth:`VNF.from_metaballs` into a blobby surface.
#    The marching-cubes mesher lives in :mod:`pybosl2.vnf` as
#    :meth:`VNF.from_field`.
#
# FileSummary: Metaball field primitives (sphere, cuboid, torus, capsule, disk, octahedron, connector).
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable

    from pybosl2.points import Point

__all__ = [
    "Metaball",
    "mb_sphere",
    "mb_cuboid",
    "mb_torus",
    "mb_capsule",
    "mb_disk",
    "mb_octahedron",
    "mb_connector",
]

INF = math.inf


# -- helpers -------------------------------------------------------------------


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


# -- Metaball ------------------------------------------------------------------


class Metaball:
    """A metaball field primitive: ``field(pts)`` over ``(N, 3)`` points.

    Combine several with :meth:`VNF.from_metaballs`.

    Args:
        field: A vectorised ``(N, 3) → (N,)`` callable.
        neg: 1 for additive, -1 for subtractive.
    """

    def __init__(self, field: Callable[[np.ndarray], np.ndarray], neg: int = 1):
        self.field = field
        self.neg = neg

    def __call__(self, pt: np.ndarray) -> float:
        return float(self.field(np.atleast_2d(np.asarray(pt, dtype=float)))[0])


# -- shape constructors --------------------------------------------------------


def mb_sphere(
    radius: float | None = None,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
    diameter: float | None = None,
) -> Metaball:
    """A spherical metaball field.

    Args:
        radius: Sphere radius (mutually exclusive with *diameter*).
        cutoff: Distance beyond which the field is clamped to 0. ``INF`` = no cutoff.
        influence: Blending strength (smaller = sharper).
        negative: If True, produce a subtractive metaball.
        diameter: Sphere diameter.

    Returns:
        A :class:`Metaball` primitive.

    Raises:
        AssertionError: If no positive radius or diameter is given.
    """
    rr = radius if radius is not None else (diameter / 2 if diameter is not None else None)
    assert rr and rr > 0, "mb_sphere(): need a positive radius or diameter."
    neg = -1 if negative else 1

    def field(pts: np.ndarray) -> np.ndarray:
        dist: np.ndarray = np.linalg.norm(pts, axis=1)
        return _mb_field(dist, rr, influence, cutoff, neg)

    return Metaball(field, neg)


def mb_cuboid(
    size: tuple[float, float, float] | float,
    squareness: float = 0.5,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
) -> Metaball:
    """A rounded-cuboid metaball field.

    Args:
        size: A scalar (cube edge) or ``(dx, dy, dz)`` tuple.
        squareness: 0 = fully round, 1 = sharp square edges.
        cutoff: Distance beyond which the field is clamped to 0.
        influence: Blending strength.
        negative: If True, produce a subtractive metaball.

    Returns:
        A :class:`Metaball` primitive.

    Raises:
        AssertionError: If *squareness* is not in ``[0, 1]``.
    """
    assert 0 <= squareness <= 1, "mb_cuboid(): squareness must be in [0, 1]."
    xp = _squircle_se_exponent(squareness)
    inv = np.array([2 / size] * 3, dtype=float) if isinstance(size, (int, float)) else 2 / np.asarray(size, dtype=float)
    neg = -1 if negative else 1

    def field(pts: np.ndarray) -> np.ndarray:
        p: np.ndarray = np.abs(pts * inv)
        dist: np.ndarray = np.max(p, axis=1) if xp >= 1100 else np.sum(p**xp, axis=1) ** (1 / xp)
        return _mb_field(dist, 1.0, influence, cutoff, neg)

    return Metaball(field, neg)


def mb_torus(
    major_radius: float | None = None,
    minor_radius: float | None = None,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
    major_diameter: float | None = None,
    minor_diameter: float | None = None,
) -> Metaball:
    """A torus metaball field.

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
        AssertionError: If either radius is missing or non-positive.
    """
    rmaj, rmin = (
        (major_radius if major_radius is not None else (major_diameter / 2 if major_diameter is not None else None)),
        (minor_radius if minor_radius is not None else (minor_diameter / 2 if minor_diameter is not None else None)),
    )
    assert rmaj and rmin and rmaj > 0 and rmin > 0, "mb_torus(): need positive major_radius and minor_radius."
    neg = -1 if negative else 1

    def field(pts: np.ndarray) -> np.ndarray:
        rad: np.ndarray = np.hypot(pts[:, 0], pts[:, 1]) - rmaj
        dist: np.ndarray = np.hypot(rad, pts[:, 2])
        return _mb_field(dist, rmin, influence, cutoff, neg)

    return Metaball(field, neg)


def mb_capsule(
    height: float | None = None,
    radius: float | None = None,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
    diameter: float | None = None,
) -> Metaball:
    """A capsule (round-ended cylinder) metaball field.

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
        AssertionError: If *height* or *radius* is missing, non-positive, or shaft too short.
    """
    rr = radius if radius is not None else (diameter / 2 if diameter is not None else None)
    assert height and rr and height > 0 and rr > 0, "mb_capsule(): need positive height and radius."
    hl = (height - 2 * rr) / 2
    assert hl > 0, "mb_capsule(): total length must exceed the two rounded ends."
    neg = -1 if negative else 1

    def field(pts: np.ndarray) -> np.ndarray:
        z = pts[:, 2]
        rxy: np.ndarray = np.hypot(pts[:, 0], pts[:, 1])
        below: np.ndarray = z < -hl
        above: np.ndarray = z > hl
        dist: np.ndarray = np.where(below, np.hypot(rxy, z + hl), np.where(above, np.hypot(rxy, z - hl), rxy))
        return _mb_field(dist, rr, influence, cutoff, neg)

    return Metaball(field, neg)


def mb_disk(
    height: float | None = None,
    radius: float | None = None,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
    diameter: float | None = None,
) -> Metaball:
    """A rounded-edge disk metaball field.

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
        AssertionError: If *height* or *radius* is missing, non-positive, or too thin.
    """
    rr = radius if radius is not None else (diameter / 2 if diameter is not None else None)
    assert height and rr and height > 0 and rr > 0, "mb_disk(): need positive height and radius."
    hl = height / 2
    ri = rr - hl
    assert ri > 0, "mb_disk(): diameter must exceed the thickness."
    neg = -1 if negative else 1

    def field(pts: np.ndarray) -> np.ndarray:
        rxy: np.ndarray = np.hypot(pts[:, 0], pts[:, 1])
        z = pts[:, 2]
        dist: np.ndarray = np.where(rxy < ri, np.abs(z), np.hypot(rxy - ri, z))
        return _mb_field(dist, hl, influence, cutoff, neg)

    return Metaball(field, neg)


def mb_octahedron(
    size: tuple[float, float, float] | float,
    squareness: float = 0.5,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
) -> Metaball:
    """A rounded-octahedron metaball field.

    Args:
        size: A scalar (circumscribed cube edge) or ``(dx, dy, dz)`` tuple.
        squareness: 0 = round, 1 = sharp octahedron edges.
        cutoff: Distance beyond which the field is clamped to 0.
        influence: Blending strength.
        negative: If True, produce a subtractive metaball.

    Returns:
        A :class:`Metaball` primitive.

    Raises:
        AssertionError: If *squareness* is not in ``[0, 1]``.
    """
    assert 0 <= squareness <= 1, "mb_octahedron(): squareness must be in [0, 1]."
    xp = _squircle_se_exponent(squareness)

    def _octdist(p: np.ndarray) -> np.ndarray:
        if xp >= 1100:
            return np.abs(p[:, 0]) + np.abs(p[:, 1]) + np.abs(p[:, 2])
        a = np.abs(p[:, 0] + p[:, 1] + p[:, 2]) ** xp
        b = np.abs(-p[:, 0] - p[:, 1] + p[:, 2]) ** xp
        c = np.abs(-p[:, 0] + p[:, 1] - p[:, 2]) ** xp
        e = np.abs(p[:, 0] - p[:, 1] - p[:, 2]) ** xp
        return (a + b + c + e) ** (1 / xp)

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


def mb_connector(
    p1: Point,
    p2: Point,
    radius: float | None = None,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
    diameter: float | None = None,
) -> Metaball:
    """A capsule metaball field spanning from *p1* to *p2*.

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
        AssertionError: If *radius* is missing, non-positive, or *p1* equals *p2*.
    """
    from pybosl2.transforms import axis_angle_matrix, rot_from_to

    rr = radius if radius is not None else (diameter / 2 if diameter is not None else None)
    a, b = np.asarray(p1, dtype=float), np.asarray(p2, dtype=float)
    assert rr and rr > 0 and not np.array_equal(a, b), "mb_connector(): need distinct points and positive radius."
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
        dist: np.ndarray = np.where(below, np.hypot(rxy, z + height), np.where(above, np.hypot(rxy, z - height), rxy))
        return _mb_field(dist, rr, influence, cutoff, neg)

    return Metaball(field, neg)


# -- backwards-compatible aliases (delegate to VNF) ---------------------------


def isosurface(*args, **kwargs):
    """Backwards-compatible alias for :meth:`VNF.from_field`."""
    from pybosl2.vnf import VNF

    return VNF.from_field(*args, **kwargs)


def metaballs(*args, **kwargs):
    """Backwards-compatible alias for :meth:`VNF.from_metaballs`."""
    from pybosl2.vnf import VNF

    return VNF.from_metaballs(*args, **kwargs)
