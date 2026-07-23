# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/hooks.py
#    Pure-Python port of BOSL2's hooks.scad: hooks and hook-like parts. At the moment BOSL2 supplies
#    a single part, :meth:`Hooks.ring_hook` -- a rectangular mounting base that flares up and joins
#    tangentially to a Y-axis cylinder (the "ring"), with an optional round, D-shaped or custom
#    through-hole.
#
# FileSummary: Hooks and hook-like parts (the ring hook).
# FileGroup: BOSL2

from __future__ import annotations

import math

import numpy as np

from bosl2.shapes2d import _opolygon
from bosl2.shapes3d import Bosl2Solid, cuboid, cyl, prismoid

__all__ = ["Hooks"]


def _circle_point_tangents(r, cp, pt):
    """The two tangent points on a circle (centre *cp*, radius *r*) from external point *pt* (BOSL2
    circle_point_tangents()). Points are 2-vectors ``[x, height]``."""
    cp = np.asarray(cp, dtype=float)
    pt = np.asarray(pt, dtype=float)
    d = float(np.linalg.norm(pt - cp))
    if d <= r:
        raise ValueError("point must be outside the circle for a tangent to exist")
    u = (pt - cp) / d
    ang = math.acos(r / d)
    out = []
    for s in (1, -1):
        c, si = math.cos(s * ang), math.sin(s * ang)
        rot = np.array([c * u[0] - si * u[1], si * u[0] + c * u[1]])
        out.append((cp + r * rot).tolist())
    return out


def _radius(r, d):
    if r is not None:
        return float(r)
    if d is not None:
        return float(d) / 2
    return None


class Hooks:
    """Hooks and hook-like parts (BOSL2 hooks.scad)."""

    @staticmethod
    def ring_hook(base_size, hole_z, or_=None, ir=None, od=None, id=None, wall=None,
                  hole: str = "circle", rounding: float = 0, hole_rounding: float = 0,
                  fillet: float = 0, outside_segments: int | None = None,
                  _fn: int | None = None) -> Bosl2Solid:
        """A ring hook: a rectangular base that flares tangentially into a Y-axis cylinder with a hole (BOSL2 ring_hook()).

        *base_size* is the ``[x, y]`` of the mounting base, which sits on ``z = 0``; *hole_z* the
        height of the cylinder centre above it; *or_* / *od* the cylinder's outer radius / diameter.
        Give exactly two of *or_/od*, *ir/id* and *wall* to set the wall around the through-hole (or a
        zero inner radius for a solid paddle). *hole* is ``"circle"``, ``"D"`` (semicircular, flat side
        down) or a list of ``[x, z]`` points for a custom hole. *rounding* rounds the base's vertical
        edges; *hole_rounding* eases the hole mouth.

        The base corners must lie outside the cylinder (``hypot(base_size.x/2, hole_z) > or``) so a
        tangent join exists. The base weld *fillet* of the original is not yet ported.

        Examples:
            A ring connector:

            .. pythonscad-example::

                from bosl2.hooks import Hooks
                Hooks.ring_hook([50, 10], 25, or_=25, ir=20).show()
        """
        if fillet:
            raise NotImplementedError("ring_hook(): the base fillet is not yet ported; use fillet=0.")
        bx, w = float(base_size[0]), float(base_size[1])
        custom = not isinstance(hole, str)

        or_t = _radius(or_, od)
        ir_t = _radius(ir, id)
        if custom:
            if ir_t is not None or wall is not None:
                raise ValueError("ring_hook(): cannot give ir/id or wall with a custom hole path.")
            if or_t is None:
                raise ValueError("ring_hook(): a custom hole needs or/od.")
            ri, ro = 0.0, or_t
        else:
            defined = sum(v is not None for v in (or_t, ir_t, wall))
            if defined != 2:
                raise ValueError("ring_hook(): define exactly two of or/od, ir/id and wall.")
            ri = ir_t if ir_t is not None else or_t - wall
            ro = or_t if or_t is not None else ri + wall
            if ri > ro:
                raise ValueError("ring_hook(): hole doesn't fit, or wall is negative.")
            if hole not in ("circle", "D"):
                raise ValueError('ring_hook(): hole must be "circle", "D" or a 2-D path.')
            if hole == "circle" and ri > 0 and ri + hole_rounding >= hole_z:
                raise ValueError(f"ring_hook(): ir + hole_rounding must be less than hole_z ({hole_z}).")

        if math.hypot(bx / 2, hole_z) <= ro:
            raise ValueError("ring_hook(): base corners must be outside the cylinder (need a tangent).")

        # tangent point where a base corner's flare meets the cylinder (take the higher one)
        tangents = _circle_point_tangents(ro, [0, hole_z], [bx / 2, 0])
        tx, tz = max(tangents, key=lambda t: t[1])

        base = prismoid([bx, w], [2 * tx, w], h=tz, rounding=rounding if rounding else 0)  # anchor=BOTTOM: base on z=0
        ring = cyl(h=w, r=ro, _fn=outside_segments if outside_segments else _fn).rotate([90, 0, 0]).up(hole_z)
        body = base | ring

        if ri > 0 or custom:
            body = body - _hole_cutter(hole, ri, w, hole_z, hole_rounding, custom, _fn)
        return Bosl2Solid(body.shape, size=[bx, w, hole_z + ro])


def _hole_cutter(hole, ri, w, hole_z, hole_rounding, custom, _fn):
    """The solid to subtract for the through-hole, laid along Y and centred at z=hole_z."""
    L = w + 2
    if custom:
        pts = [[float(p[0]), float(p[1])] for p in hole]
        cut = _opolygon(pts).linear_extrude(height=L, center=True)
        return Bosl2Solid(cut).rotate([90, 0, 0]).up(hole_z)
    rnd = hole_rounding if hole_rounding else None
    bore = cyl(h=L, r=ri, rounding=rnd, _fn=_fn).rotate([90, 0, 0]).up(hole_z)
    if hole == "D":                                        # keep the upper half -> flat-bottomed D-hole
        upper = cuboid([2 * ri + 2, L + 2, 2 * ri]).up(hole_z + ri)
        bore = bore & upper
    return bore
