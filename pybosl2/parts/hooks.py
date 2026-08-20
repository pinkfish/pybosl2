# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/hooks.py
#    Pure-Python port of BOSL2's hooks.scad: hooks and hook-like parts. At the moment BOSL2 supplies
#    a single part, :class:`RingHook` -- a rectangular mounting base that flares up and joins
#    tangentially to a Y-axis cylinder (the "ring"), with an optional round, D-shaped or custom
#    through-hole.
#
# FileSummary: Hooks and hook-like parts (the ring hook).
# DocCategory: Parts library
# FileGroup: BOSL2

"""Hooks and hook-like parts (the ring hook)."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Any

import numpy as np

from pybosl2._backend import csg_part
from pybosl2._native import native
from pybosl2.shapes3d import Bosl2Solid, cuboid, cyl, prismoid

_opolygon = native("polygon")

__all__ = ["RingHook", "HoleType"]


class HoleType(StrEnum):
    """Through-hole shape for :class:`RingHook`."""

    CIRCLE = "circle"
    D = "D"


def _circle_point_tangents(r: float, center: list[float], pt: list[float]) -> list[list[float]]:
    """Return the two tangent points on a circle (centre *center*, radius *r*) from external point *pt* (BOSL2.

    circle_point_tangents()). Points are 2-vectors ``[x, height]``.
    """
    center_arr = np.asarray(center, dtype=float)
    pt_arr = np.asarray(pt, dtype=float)
    diameter = float(np.linalg.norm(pt_arr - center_arr))
    if diameter <= r:
        raise ValueError("point must be outside the circle for a tangent to exist")
    u = (pt_arr - center_arr) / diameter
    angle = math.acos(r / diameter)
    out: list[list[float]] = []
    for s in (1, -1):
        c, si = math.cos(s * angle), math.sin(s * angle)
        rot = np.array([c * u[0] - si * u[1], si * u[0] + c * u[1]])
        out.append((center_arr + r * rot).tolist())
    return out


def _radius(r: float | None, d: float | None) -> float | None:
    if r is not None:
        return float(r)
    if d is not None:
        return float(d) / 2
    return None


class RingHook:
    """A ring hook: a rectangular base that flares tangentially into a Y-axis cylinder with a hole.

    *base_size* is the ``[x, y]`` of the mounting base, which sits on ``z = 0``; *hole_z* the
    height of the cylinder centre above it; *outer_radius* / *outer_diameter* the cylinder's
    outer radius / diameter.  Give exactly two of *outer_radius/outer_diameter*,
    *inner_radius/inner_diameter* and *wall* to set the wall around the through-hole.
    *hole* is :attr:`HoleType.CIRCLE`, :attr:`HoleType.D` (semicircular, flat side down)
    or a list of ``[x, z]`` points for a custom hole.  *rounding* rounds the base's vertical
    edges; *hole_rounding* eases the hole mouth.

    Examples:
        A ring connector:

        .. pythonscad-example::

            from pybosl2.parts.hooks import RingHook
            RingHook([50, 10], 25, outer_radius=25, inner_radius=20).show()

    """

    def __init__(
        self,
        base_size: list[float],
        hole_z: float,
        outer_radius: float | None = None,
        inner_radius: float | None = None,
        outer_diameter: float | None = None,
        inner_diameter: float | None = None,
        wall: float | None = None,
        hole: HoleType | list[list[float]] = HoleType.CIRCLE,
        rounding: float = 0,
        hole_rounding: float = 0,
        fillet: float = 0,
        outside_segments: int | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a ring hook.

        Args:
            base_size: The ``[x, y]`` dimensions of the mounting base rectangle.
            hole_z: Height of the cylinder centre above the base.
            outer_radius: Outer radius of the cylinder.
            inner_radius: Inner (bore) radius of the cylinder.
            outer_diameter: Outer diameter of the cylinder (alternative to outer_radius).
            inner_diameter: Inner diameter of the cylinder (alternative to inner_radius).
            wall: Wall thickness around the through-hole.
            hole: Through-hole shape -- :attr:`HoleType.CIRCLE`, :attr:`HoleType.D`, or a custom 2-D path.
            rounding: Radius for rounding the base's vertical edges.
            hole_rounding: Radius for easing the hole mouth.
            fillet: Fillet radius at the base-to-cylinder junction.
            outside_segments: Number of segments on the outer cylinder.
            fn: Number of facets for $fn-based resolution.
            fa: Minimum facet angle.
            fs: Minimum facet size.

        Returns:
            None.

        Raises:
            NotImplementedError: If *fillet* is non-zero (not yet ported).
            ValueError: If the geometry constraints are violated.

        """
        if fillet:
            raise NotImplementedError("ring_hook(): the base fillet is not yet ported; use fillet=0.")
        bx, w = float(base_size[0]), float(base_size[1])
        custom = isinstance(hole, list)

        or_t = _radius(outer_radius, outer_diameter)
        ir_t = _radius(inner_radius, inner_diameter)
        if custom:
            if ir_t is not None or wall is not None:
                raise ValueError(
                    "ring_hook(): cannot give inner_radius/inner_diameter or wall with a custom hole path."
                )
            if or_t is None:
                raise ValueError("ring_hook(): a custom hole needs or/outer_diameter.")
            ri, ro = 0.0, or_t
        else:
            defined = sum(v is not None for v in (or_t, ir_t, wall))
            if defined != 2:
                raise ValueError(
                    "ring_hook(): define exactly two of or/outer_diameter, inner_radius/inner_diameter and wall."
                )
            ri = ir_t if ir_t is not None else float(or_t) - float(wall)  # type: ignore[arg-type]
            ro = or_t if or_t is not None else float(ri) + float(wall)  # type: ignore[arg-type]
            if ri > ro:
                raise ValueError("ring_hook(): hole doesn't fit, or wall is negative.")
            if isinstance(hole, HoleType) and hole not in (HoleType.CIRCLE, HoleType.D):
                raise ValueError(f"ring_hook(): hole must be CIRCLE, D or a 2-D path, got {hole!r}")
            if hole == HoleType.CIRCLE and ri > 0 and ri + hole_rounding >= hole_z:
                raise ValueError(f"ring_hook(): inner_radius + hole_rounding must be less than hole_z ({hole_z}).")

        if math.hypot(bx / 2, hole_z) <= ro:
            raise ValueError("ring_hook(): base corners must be outside the cylinder (need a tangent).")

        tangents = _circle_point_tangents(ro, [0, hole_z], [bx / 2, 0])
        tx, tz = max(tangents, key=lambda t: t[1])

        base = prismoid(
            [bx, w],
            [2 * tx, w],
            height=tz,
            rounding=rounding if rounding else 0,
            fn=fn,
            fa=fa,
            fs=fs,
        )
        ring = (
            cyl(
                height=w,
                radius=ro,
                fn=outside_segments if outside_segments else fn,
                fa=fa,
                fs=fs,
            )
            .rotate([90, 0, 0])
            .up(hole_z)
        )
        body = base | ring

        if ri > 0 or custom:
            body = body - _hole_cutter(hole, ri, w, hole_z, hole_rounding, fn, fa, fs)
        self._solid: Bosl2Solid = Bosl2Solid(body.shape, size=[bx, w, hole_z + ro])
        self._base_size: list[float] = base_size
        self._hole_z: float = hole_z
        self._outer_radius: float = ro
        self._inner_radius: float = ri

    @property
    def base_size(self) -> list[float]:
        """Mounting base ``[x, y]``."""
        return self._base_size

    @property
    def hole_z(self) -> float:
        """Cylinder centre height."""
        return self._hole_z

    @property
    def outer_radius(self) -> float:
        """Cylinder outer radius."""
        return self._outer_radius

    @property
    def inner_radius(self) -> float:
        """Cylinder inner (bore) radius."""
        return self._inner_radius

    @property
    @csg_part
    def shape(self) -> Bosl2Solid:
        """Return the ring hook geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the ring hook in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


def _hole_cutter(
    hole: HoleType | list[list[float]],
    ri: float,
    w: float,
    hole_z: float,
    hole_rounding: float,
    fn: int | None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """Return the solid to subtract for the through-hole, laid along Y and centred at z=hole_z."""
    length_ = w + 2
    if isinstance(hole, list):
        pts = [[float(p[0]), float(p[1])] for p in hole]
        cut = _opolygon(pts).linear_extrude(height=length_, center=True)
        return Bosl2Solid(cut).rotate([90, 0, 0]).up(hole_z)
    rnd = hole_rounding if hole_rounding else None
    bore = cyl(height=length_, radius=ri, rounding=rnd, fn=fn, fa=fa, fs=fs).rotate([90, 0, 0]).up(hole_z)
    if hole == HoleType.D:
        upper = cuboid([2 * ri + 2, length_ + 2, 2 * ri], fn=fn, fa=fa, fs=fs).up(hole_z + ri)
        bore = bore & upper
    return bore
