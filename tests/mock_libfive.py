# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# mypy: ignore_errors

import importlib
import math
import sys
import types
from collections.abc import Sequence
from typing import Any


def _is_real(name: str) -> bool:
    """True if *name* imports for real -- i.e. it is not missing and not one of our own stand-ins."""
    try:
        module = importlib.import_module(name)
    except Exception:
        return False
    return not getattr(module, "_pybosl2_mock", False)


class Tree:
    """A symbolic SDF sub-expression: callable as `tree(x, y, z) -> float`. Every operator
    returns a new Tree wrapping both operands' closures, mirroring how the real libfive Tree
    type builds an expression graph instead of evaluating eagerly."""

    def __init__(self, fn):
        self.fn = fn

    def __call__(self, x, y, z):
        return self.fn(x, y, z)

    def _other(self, o):
        return o if isinstance(o, Tree) else Tree(lambda _x, _y, _z: o)

    def __add__(self, o):
        o = self._other(o)
        return Tree(lambda x, y, z: self(x, y, z) + o(x, y, z))

    __radd__ = __add__

    def __sub__(self, o):
        o = self._other(o)
        return Tree(lambda x, y, z: self(x, y, z) - o(x, y, z))

    def __rsub__(self, o):
        o = self._other(o)
        return Tree(lambda x, y, z: o(x, y, z) - self(x, y, z))

    def __mul__(self, o):
        o = self._other(o)
        return Tree(lambda x, y, z: self(x, y, z) * o(x, y, z))

    __rmul__ = __mul__

    def __truediv__(self, o):
        o = self._other(o)
        return Tree(lambda x, y, z: self(x, y, z) / o(x, y, z))

    def __neg__(self):
        return Tree(lambda x, y, z: -self(x, y, z))


def x():
    return Tree(lambda x, _y, _z: x)


def y():
    return Tree(lambda _x, y, _z: y)


def z():
    return Tree(lambda _x, _y, z: z)


def _as_tree(v):
    # Bind `v` as a default argument (`_v=v`) rather than closing over the loop/call-site
    # variable directly -- otherwise, if the caller later rebinds the same variable name
    # before this closure is ever invoked, the closure would see the *new* value (Python
    # closures capture variables, not values). Using a default argument freezes the value at
    # closure-creation time instead.
    return v if isinstance(v, Tree) else Tree(lambda _x, _y, _z, _v=v: _v)


def _wrap1(f):
    def g(v):
        vt = _as_tree(v)
        return Tree(lambda x, y, z: f(vt(x, y, z)))

    return g


def _wrap2(f):
    def g(a, b):
        at = _as_tree(a)
        bt = _as_tree(b)
        return Tree(lambda x, y, z: f(at(x, y, z), bt(x, y, z)))

    return g


sqrt = _wrap1(math.sqrt)
square = _wrap1(lambda v: v * v)
abs = _wrap1(__import__("builtins").abs)  # noqa: A001
max = _wrap2(__import__("builtins").max)  # noqa: A001
min = _wrap2(__import__("builtins").min)  # noqa: A001
atan2 = _wrap2(math.atan2)
# The twist branch of _linear_sweep_sdf() rotates by an angle that varies with z, so it needs
# these as symbolic ops rather than plain math.sin/cos on a float.
sin = _wrap1(math.sin)
cos = _wrap1(math.cos)


class _FrepResult:
    """Stand-in for the meshed solid frep() would return in the real app -- keeps the SDF
    closure and bounds so tests can .sample() it directly, plus a .translate() that composes
    an offset (so translate()/anchor= can be tested the same way a real solid would behave)."""

    def __init__(self, sdf, mn, mx, res):
        self.sdf = sdf
        self.mn = mn
        self.mx = mx
        self.res = res
        self.offset = [0.0, 0.0, 0.0]

    @property
    def position(self):
        return [self.mn[i] + self.offset[i] for i in range(3)]

    @property
    def size(self):
        return [self.mx[i] - self.mn[i] for i in range(3)]

    def translate(self, v):
        r = _FrepResult(self.sdf, self.mn, self.mx, self.res)
        r.offset = [self.offset[i] + v[i] for i in range(3)]
        return r

    # -- what a real meshed solid answers once the field has been realized -------------------

    def show(self):
        """Register as the output, as the app's show() does; returns self so chains continue."""
        self.shown = True
        return self

    def color(self, c, alpha=None):
        self.colour = (c, alpha)
        return self

    def highlight(self):
        self.modifier = "highlight"
        return self

    def background(self):
        self.modifier = "ghost"
        return self

    def render(self):
        self.rendered = True
        return self

    def sample(self, px, py, pz):
        # Subtract the accumulated translate offset to get back into the SDF's own frame.
        return self.sdf(px - self.offset[0], py - self.offset[1], pz - self.offset[2])

    def projection(self, cut=False):  # noqa: ARG002
        """Stand-in for native projection: returns the XY bounding box as a 2-D AABB."""
        mn, mx = self.mn, self.mx
        off = self.offset
        box_mn = [mn[0] + off[0], mn[1] + off[1], 0.0]
        box_mx = [mx[0] + off[0], mx[1] + off[1], 0.0]
        return _AabbSolid(box_mn, box_mx)

    def __getattr__(self, name):
        # Permissive no-op for native methods called through Bosl2Solid passthroughs.
        if name == "separate":
            return lambda: [self]
        if name == "partition":
            return lambda **_k: [self, self]
        if name in (
            "repair",
            "wrap",
            "pull",
            "render",
            "minkowski_difference",
            "resize",
            "minkowski",
            "hull",
            "oversample",
        ):
            return lambda *_a, **_k: self
        raise AttributeError(name)

    def mesh(self, _triangulate=False, _color=False):
        """Numeric stand-in for the real app's solid.mesh() -> (points, faces): samples the
        SDF on a regular grid over the bounds and returns the world-frame points that fall
        inside (sdf <= 0), with an empty faces list. Enough for vertex consumers like
        pysolidfive.hull(); anything needing real face topology needs the real app. The grid
        is capped at 16 cells per axis so pure-Python sampling of a deep SDF stays cheap."""
        # NOTE: this module shadows builtins max()/min() with Tree-returning wrappers above,
        # so clamp with plain conditionals here.
        n = int(self.res)
        n = 16 if n > 16 else (2 if n < 2 else n)
        points = []
        steps = [[self.mn[i] + (self.mx[i] - self.mn[i]) * k / n for k in range(n + 1)] for i in range(3)]
        for px in steps[0]:
            for py in steps[1]:
                for pz in steps[2]:
                    if self.sdf(px, py, pz) <= 1e-9:
                        points.append(
                            [
                                px + self.offset[0],
                                py + self.offset[1],
                                pz + self.offset[2],
                            ]
                        )
        return points, []


def frep(exp, mn, mx, res):
    return _FrepResult(exp, mn, mx, res)


# This module shadows the builtins min/max/abs with SDF-Tree-returning wrappers (above), so
# the AABB helpers below -- which need ordinary numeric min/max -- bind the real builtins.
import builtins as _bi  # noqa: E402

_bmin = _bi.min
_bmax = _bi.max


class _AabbSolid:
    """A tiny native-solid stand-in that tracks an axis-aligned bounding box through the
    transforms/booleans pybosl2 uses, and exposes it as `.position`/`.size` -- the same native
    accessors PythonSCAD's real PyOpenSCAD provides. This lets pybosl2's bbox-backed anchoring
    (Bosl2Solid.bounds()/anchor_point()/attach()/position()/align()) be unit-tested numerically
    without the real app. `mn`/`mx` are the AABB corners, or None for an unknown/2-D shape (its
    .position/.size then read None, matching the real API's empty-geometry sentinel).

    Every method or attribute not defined here is a permissive no-op returning self, so a box
    module can call anything (.color(), .linear_extrude(), .show(), ...) without the mock
    needing to model it -- only the AABB-affecting operations actually update the box."""

    def __init__(self, mn=None, mx=None):
        self.mn = list(mn) if mn is not None else None
        self.mx = list(mx) if mx is not None else None

    @property
    def position(self):
        return list(self.mn) if self.mn is not None else None

    @property
    def size(self):
        mn, mx = self.mn, self.mx
        if mn is None or mx is None:
            return None
        return [mx[i] - mn[i] for i in range(3)]

    def translate(self, v):
        mn, mx = self.mn, self.mx
        if mn is None or mx is None:
            return _AabbSolid()
        v = list(v) + [0.0] * (3 - len(v))
        res = _AabbSolid([mn[i] + v[i] for i in range(3)], [mx[i] + v[i] for i in range(3)])
        if getattr(self, "is_cylindrical", False) is True:
            res.is_cylindrical = True  # type: ignore[attr-defined]  # type: ignore[attr-defined]
        return res

    def scale(self, v):
        mn, mx = self.mn, self.mx
        if mn is None or mx is None:
            return _AabbSolid()
        import builtins

        sv_lst = [float(x) for x in v] if isinstance(v, (list, tuple)) else [float(v)] * 3
        sv = list(sv_lst) + [1.0] * (3 - len(sv_lst))
        z_min = mn[2] if len(mn) > 2 else 0.0
        z_max = mx[2] if len(mx) > 2 else 0.0
        mn3 = [mn[0], mn[1], z_min]
        mx3 = [mx[0], mx[1], z_max]
        out_mn = [builtins.min(mn3[i] * sv[i], mx3[i] * sv[i]) for i in range(3)]
        out_mx = [builtins.max(mn3[i] * sv[i], mx3[i] * sv[i]) for i in range(3)]
        res = _AabbSolid(out_mn, out_mx)
        if getattr(self, "is_cylindrical", False) is True and sv[0] == sv[1]:
            res.is_cylindrical = True  # type: ignore[attr-defined]
        return res

    def rotate(self, a, v=None):
        mn, mx = self.mn, self.mx
        if mn is None or mx is None:
            return _AabbSolid()
        is_z_rot = False
        if (
            v is not None
            and list(v) == [0, 0, 1]
            or isinstance(a, (list, tuple))
            and len(a) == 3
            and a[0] == 0
            and a[1] == 0
        ):
            is_z_rot = True
        elif v is None and not isinstance(a, (list, tuple)):
            # single angle with no vector defaults to Z rotation
            is_z_rot = True

        if getattr(self, "is_cylindrical", False) is True and is_z_rot:
            res = _AabbSolid(self.mn, self.mx)
            res.is_cylindrical = True  # type: ignore[attr-defined]
            return res

        m = _rot_matrix(a, v)
        corners = [
            [
                mn[0] if i & 1 == 0 else mx[0],
                mn[1] if i & 2 == 0 else mx[1],
                mn[2] if i & 4 == 0 else mx[2],
            ]
            for i in range(8)
        ]
        rot = [[sum(m[r][k] * c[k] for k in range(3)) for r in range(3)] for c in corners]
        return _AabbSolid(
            [_bmin(c[i] for c in rot) for i in range(3)],
            [_bmax(c[i] for c in rot) for i in range(3)],
        )

    def _combine(self, other, mode):
        o = other if isinstance(other, _AabbSolid) else _AabbSolid()
        smn, smx, omn, omx = self.mn, self.mx, o.mn, o.mx
        if smn is None or smx is None:
            res = _AabbSolid(o.mn, o.mx)
        elif omn is None or omx is None or mode == "sub":
            res = _AabbSolid(smn, smx)
        elif mode == "or":
            res = _AabbSolid(
                [_bmin(smn[i], omn[i]) for i in range(3)],
                [_bmax(smx[i], omx[i]) for i in range(3)],
            )
        else:
            res = _AabbSolid(
                [_bmax(smn[i], omn[i]) for i in range(3)],
                [_bmin(smx[i], omx[i]) for i in range(3)],
            )
        if getattr(self, "is_cylindrical", False) is True:
            res.is_cylindrical = True  # type: ignore[attr-defined]
        return res

    def __or__(self, other):
        return self._combine(other, "or")

    def __and__(self, other):
        return self._combine(other, "and")

    def __sub__(self, other):
        return self._combine(other, "sub")

    def color(self, *_a, **_k):
        return _AabbSolid(self.mn, self.mx)

    def resize(self, newsize, _auto=None, **_k):
        # Modelled (rather than left to the permissive __getattr__) because the real
        # resize() REJECTS a 2-element vector with "TypeError: Invalid resize dimensions"
        # even for 2-D geometry -- a shape_type.py CLOUD bug that shipped precisely because
        # the mock accepted it silently. A 0 component means "leave that axis alone".
        if not isinstance(newsize, (list, tuple)) or len(newsize) != 3:
            raise TypeError("Invalid resize dimensions")
        mn, mx = self.mn, self.mx
        if mn is None or mx is None:
            return _AabbSolid()
        out_mn, out_mx = list(mn), list(mx)
        for i in range(3):
            want = float(newsize[i])
            if want > 0:
                out_mn[i] = mn[i]
                out_mx[i] = mn[i] + want
        return _AabbSolid(out_mn, out_mx)

    def multmatrix(self, m):
        mn, mx = self.mn, self.mx
        if mn is None or mx is None:
            return _AabbSolid()
        z_min = mn[2] if len(mn) > 2 else 0.0
        z_max = mx[2] if len(mx) > 2 else 0.0
        corners = [
            [
                mn[0] if i & 1 == 0 else mx[0],
                mn[1] if i & 2 == 0 else mx[1],
                z_min if i & 4 == 0 else z_max,
            ]
            for i in range(8)
        ]
        transformed = []
        for c in corners:
            if len(m) >= 4 and len(m[0]) >= 4:
                w = m[3][0] * c[0] + m[3][1] * c[1] + m[3][2] * c[2] + m[3][3]
                w = w if w != 0 else 1.0
                tx = (m[0][0] * c[0] + m[0][1] * c[1] + m[0][2] * c[2] + m[0][3]) / w
                ty = (m[1][0] * c[0] + m[1][1] * c[1] + m[1][2] * c[2] + m[1][3]) / w
                tz = (m[2][0] * c[0] + m[2][1] * c[1] + m[2][2] * c[2] + m[2][3]) / w
            else:
                tx = m[0][0] * c[0] + m[0][1] * c[1] + m[0][2] * c[2]
                ty = m[1][0] * c[0] + m[1][1] * c[1] + m[1][2] * c[2]
                tz = m[2][0] * c[0] + m[2][1] * c[1] + m[2][2] * c[2]
            transformed.append([tx, ty, tz])
        res = _AabbSolid(
            [_bmin(c[i] for c in transformed) for i in range(3)],
            [_bmax(c[i] for c in transformed) for i in range(3)],
        )
        if getattr(self, "is_cylindrical", False) is True:
            res.is_cylindrical = True  # type: ignore[attr-defined]
        return res

    def separate(self):
        # Native separate() splits disconnected lumps; the mock has a single AABB, so it is one part.
        return [_AabbSolid(self.mn, self.mx)]

    def inside(self, point):
        # Model the real native inside() from the tracked AABB so Bosl2Solid.inside() is testable.
        mn, mx = self.mn, self.mx
        if mn is None or mx is None:
            return False
        return all(mn[i] <= float(point[i]) <= mx[i] for i in range(3))

    def linear_extrude(self, height=1.0, center=False, **_k):
        mn, mx = self.mn, self.mx
        if mn is None or mx is None:
            return _AabbSolid()
        z0, z1 = (-float(height) / 2, float(height) / 2) if center else (0.0, float(height))
        z_min = mn[2] if len(mn) > 2 else 0.0
        z_max = mx[2] if len(mx) > 2 else 0.0
        return _AabbSolid([mn[0], mn[1], z_min + z0], [mx[0], mx[1], z_max + z1])

    @property
    def paths(self) -> list:
        """Return the bounding rectangle as a 2-D path for projection tests."""
        mn, mx = self.mn, self.mx
        if mn is None or mx is None:
            return []
        return [[[mn[0], mn[1]], [mx[0], mn[1]], [mx[0], mx[1]], [mn[0], mx[1]]]]

    # -- directional move convenience methods (match Bosl2Solid interface) -----

    def right(self, x: float):
        return self.translate([float(x), 0.0, 0.0])

    def left(self, x: float):
        return self.translate([-float(x), 0.0, 0.0])

    def back(self, y: float):
        return self.translate([0.0, float(y), 0.0])

    def forward(self, y: float):
        return self.translate([0.0, -float(y), 0.0])

    def up(self, z: float):
        return self.translate([0.0, 0.0, float(z)])

    def down(self, z: float):
        return self.translate([0.0, 0.0, -float(z)])

    def __getattr__(self, name):
        # Permissive no-op for standard output/display/query/transform methods
        if name in (
            "show",
            "mesh",
            "render",
            "png",
            "write",
            "stl",
            "save",
            "plot",
            "view",
            "linear_extrude",
            "rotate_extrude",
            "minkowski",
            "hull",
            "fill",
            "offset",
            "highlight",
            "background",
            "path_extrude",
            "projection",
            "mirror",
            "repair",
            "wrap",
            "pull",
            "oversample",
            "separate",
            "minkowski_difference",
            "resize",
            "partition",
            "wrap",
        ):
            return lambda *_a, **_k: self
        raise AttributeError(name)

    # -- copier methods (match Distributable interface, used by parts/* code) ---

    def _distribute(self, mats):
        return [self.__class__(self.bounds.mn, self.bounds.mx - self.bounds.mn) for _ in mats]

    def zrot_copies(self, **kw):
        from pybosl2.distributors import _rotate_around_z  # type: ignore[attr-defined]

        mats = _rotate_around_z(**kw)
        return [
            self.__class__.from_multmatrix(self, m) if hasattr(self.__class__, "from_multmatrix") else self
            for m in mats
        ]

    def xcopies(self, **kw):
        from pybosl2.constants import RIGHT
        from pybosl2.distributors import _axis_copies

        return self._distribute(_axis_copies(RIGHT, **kw))

    def ycopies(self, **kw):
        from pybosl2.constants import BACK
        from pybosl2.distributors import _axis_copies

        return self._distribute(_axis_copies(BACK, **kw))

    def zcopies(self, **kw):
        from pybosl2.constants import UP
        from pybosl2.distributors import _axis_copies

        return self._distribute(_axis_copies(UP, **kw))

    def mirror_copy(self, **kw):
        from pybosl2.distributors import _mirror_mat  # type: ignore[attr-defined]

        mats = _mirror_mat(**kw)
        return self._distribute(mats)

    def xflip_copy(self, **kw):
        from pybosl2.distributors import _mirror_mat  # type: ignore[attr-defined]

        mats = _mirror_mat(v=[1, 0, 0], center=[kw.get("x", 0), kw.get("offset", 0), 0])
        return self._distribute(mats)


def _rot_matrix(a, v=None):
    if v is None and isinstance(a, (list, tuple)):
        rx, ry, rz = (math.radians(x) for x in (list(a) + [0, 0, 0])[:3])
        cx, sx, cy, sy, cz, sz = (
            math.cos(rx),
            math.sin(rx),
            math.cos(ry),
            math.sin(ry),
            math.cos(rz),
            math.sin(rz),
        )
        mx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
        my = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
        mz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]

        def mm(p, q):
            return [[sum(p[i][k] * q[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

        return mm(mz, mm(my, mx))
    angle = math.radians(a)
    ax = list(v) if v is not None else [0, 0, 1]
    n = math.sqrt(sum(x * x for x in ax)) or 1.0
    x, y, z = (c / n for c in ax)
    c, s, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
    return [
        [t * x * x + c, t * x * y - s * z, t * x * z + s * y],
        [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
        [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
    ]


def _mock_cube(size: "float | Sequence[float]" = 1, center=None, dim=None, **_k) -> Any:
    s = dim if dim is not None else size
    sv = [float(s)] * 3 if isinstance(s, (int, float)) else [float(x) for x in s]
    if center:
        return _AabbSolid([-sv[i] / 2 for i in range(3)], [sv[i] / 2 for i in range(3)])
    return _AabbSolid([0.0, 0.0, 0.0], sv)


def _mock_cylinder(
    h: float = 1, r=None, radius1=None, radius2=None, d=None, diameter1=None, diameter2=None, center=None, **k
) -> Any:
    rr = [
        v
        for v in (
            r,
            radius1,
            radius2,
            (d / 2 if d else None),
            (diameter1 / 2 if diameter1 else None),
            (diameter2 / 2 if diameter2 else None),
            k.get("r1"),
            k.get("r2"),
        )
        if v is not None
    ]
    rad = _bmax(rr) if rr else 1.0
    hh = float(h)
    z0, z1 = (-hh / 2, hh / 2) if center else (0.0, hh)
    res = _AabbSolid([-rad, -rad, z0], [rad, rad, z1])
    res.is_cylindrical = True  # type: ignore[attr-defined]
    return res


def _mock_sphere(r=None, d=None, **_k) -> Any:
    rad = float(r) if r is not None else (float(d) / 2 if d is not None else 1.0)
    res = _AabbSolid([-rad, -rad, -rad], [rad, rad, rad])
    res.is_cylindrical = True  # type: ignore[attr-defined]
    return res


def _mock_square(size: float | Sequence[float] = 1, center=True, **_k) -> Any:
    sv = [float(size)] * 2 if isinstance(size, (int, float)) else [float(x) for x in size]
    if center:
        return _AabbSolid([-sv[0] / 2, -sv[1] / 2, 0.0], [sv[0] / 2, sv[1] / 2, 0.0])
    return _AabbSolid([0.0, 0.0, 0.0], [sv[0], sv[1], 0.0])


def _mock_circle(r=1.0, radius=None, d=None, diameter=None, **_k) -> Any:
    rad_val = r if radius is None else radius
    dia_val = d if diameter is None else diameter
    rad = float(rad_val) if rad_val is not None else (float(dia_val) / 2 if dia_val is not None else 1.0)
    return _AabbSolid([-rad, -rad, 0.0], [rad, rad, 0.0])


def _mock_polyhedron(points=None, *_a, **_k) -> Any:
    if not points:
        return _AabbSolid()
    pts = [[float(c) for c in p] for p in points]
    return _AabbSolid(
        [_bmin(p[i] for p in pts) for i in range(3)],
        [_bmax(p[i] for p in pts) for i in range(3)],
    )


def _mock_polygon(points=None, *_a, **_k) -> Any:
    if not points:
        return _AabbSolid()
    pts = [[float(c) for c in p] for p in points]
    x_coords = [p[0] for p in pts]
    y_coords = [p[1] for p in pts]
    return _AabbSolid(
        [_bmin(x_coords), _bmin(y_coords), 0.0],
        [_bmax(x_coords), _bmax(y_coords), 0.0],
    )


def _mock_hull(*solids, **_k) -> Any:
    pts: list[list[float]] = []
    for s in solids:
        if isinstance(s, _AabbSolid) and s.mn is not None and s.mx is not None:
            pts.append(list(s.mn))
            pts.append(list(s.mx))
    if not pts:
        return _AabbSolid()
    return _AabbSolid(
        [_bmin(p[i] for p in pts) for i in range(3)],
        [_bmax(p[i] for p in pts) for i in range(3)],
    )


def _mock_fill(shape=None, **_k) -> Any:
    # fill() drops a 2-D shape's holes, which never changes its bounding box -- so the mock
    # just hands back the same box (or an unknown one for the bbox-less 2-D stand-ins).
    if isinstance(shape, _AabbSolid):
        return _AabbSolid(shape.mn, shape.mx)
    return _AabbSolid()


def _mock_minkowski(*solids, **_k) -> Any:
    mns: list[list[float]] = []
    mxs: list[list[float]] = []
    for s in solids:
        if isinstance(s, _AabbSolid) and s.mn is not None and s.mx is not None:
            mns.append(list(s.mn))
            mxs.append(list(s.mx))
    if not mns:
        return _AabbSolid()
    return _AabbSolid(
        [sum(m[i] for m in mns) for i in range(3)],
        [sum(m[i] for m in mxs) for i in range(3)],
    )


def _mock_rotate_extrude(shape, *_a, **_k) -> Any:
    inner = shape.shape if (hasattr(shape, "shape") and not callable(shape.shape)) else shape
    if isinstance(inner, _AabbSolid) and inner.mn is not None and inner.mx is not None:
        # 2D bounds: mn=[x0, y0], mx=[x1, y1]
        x0, y0 = inner.mn[0], inner.mn[1]
        x1, y1 = inner.mx[0], inner.mx[1]
        import builtins

        rad = builtins.max(builtins.abs(x0), builtins.abs(x1))
        # Z-axis extrusion maps Y to Z, and revolves X on XY plane
        return _AabbSolid([-rad, -rad, y0], [rad, rad, y1])
    return _AabbSolid()


def install():
    """Patch sys.modules with mock `libfive`/`pythonscad`/`openscad` modules, so `import pysolidfive`
    (and its `pybosl2.shapes2d`/`pybosl2.shapes3d` imports) succeed without a real PythonSCAD app.
    Idempotent -- safe to call more than once (e.g. from multiple test modules).

    Each module is stood in for INDEPENDENTLY, and only when the real one is missing. libfive ships
    in no extra, so it is almost always mocked; standing in for pythonscad/openscad on that account
    too would hide the real wheel behind bbox-less stubs, silently downgrading every geometry
    assertion in the suite to a mock one (which is exactly what used to happen)."""
    if not _is_real("libfive"):
        libfive_mock = types.ModuleType("libfive")
        libfive_mock._pybosl2_mock = True
        for name in ["Tree", "x", "y", "z", "sqrt", "square", "abs", "max", "min", "atan2", "sin", "cos"]:
            setattr(libfive_mock, name, globals()[name])
        sys.modules["libfive"] = libfive_mock
        # frep() is handed the Tree objects libfive just built, so the two have to come from the
        # same world: with a mocked libfive, the real wheel's frep() rejects them outright
        # ("Unknown frep expression type"). Everything else on pythonscad stays real.
        if _is_real("pythonscad"):
            _shim_frep()

    if not _is_real("pythonscad"):
        _install_pythonscad_mock()
    if not _is_real("openscad"):
        _install_openscad_mock()


class _FrepShim(types.ModuleType):
    """The real `pythonscad`, with only frep() swapped for the mock's -- see install()."""

    _pybosl2_frep_shim = True

    def __init__(self, real):
        super().__init__("pythonscad")
        self.__dict__["_real"] = real
        self.__dict__["frep"] = frep

    def __getattr__(self, name):
        return getattr(self.__dict__["_real"], name)


def _shim_frep():
    """Route frep() to the mock while leaving the rest of the real wheel in place. Idempotent."""
    real = sys.modules.get("pythonscad") or importlib.import_module("pythonscad")
    if getattr(real, "_pybosl2_frep_shim", False):
        return
    sys.modules["pythonscad"] = _FrepShim(real)


def _install_pythonscad_mock():
    # pythonscad: frep() is real (routes to _FrepResult above). The 3-D primitives return an
    # _AabbSolid that tracks its bounding box (so pybosl2's bbox-backed anchoring is numerically
    # testable); the 2-D/other builders return a permissive bbox-less _AabbSolid. pysolidfive
    # itself never calls any of these (it only builds SDFs and calls frep()).
    pythonscad_mock = types.ModuleType("pythonscad")
    pythonscad_mock._pybosl2_mock = True
    pythonscad_mock.frep = frep  # type: ignore[attr-defined]
    pythonscad_mock.cube = _mock_cube  # type: ignore[attr-defined]
    pythonscad_mock.cylinder = _mock_cylinder  # type: ignore[attr-defined]
    pythonscad_mock.sphere = _mock_sphere
    pythonscad_mock.polyhedron = _mock_polyhedron
    pythonscad_mock.hull = _mock_hull
    pythonscad_mock.fill = _mock_fill
    pythonscad_mock.minkowski = _mock_minkowski
    pythonscad_mock.rotate_extrude = _mock_rotate_extrude
    pythonscad_mock.polygon = _mock_polygon
    for name in [
        "textmetrics",
        "square",
        "circle",
        "text",
        "osuse",
    ]:
        setattr(pythonscad_mock, name, lambda *_a, **_k: _AabbSolid())
    sys.modules["pythonscad"] = pythonscad_mock


def _install_openscad_mock():
    # openscad: PyOpenSCAD needs to exist (pybosl2/shapes3d.py imports the name for a type hint).
    # The geometry free functions imported by name (cap_box_polygon.py does
    # `from openscad import hull, polygon`) get the same AABB-aware stand-ins.
    openscad_mock = types.ModuleType("openscad")
    openscad_mock._pybosl2_mock = True
    openscad_mock.PyOpenSCAD = _AabbSolid
    openscad_mock.PyOpenSCADVector = list
    openscad_mock.cube = _mock_cube
    openscad_mock.cylinder = _mock_cylinder
    openscad_mock.sphere = _mock_sphere
    openscad_mock.hull = _mock_hull
    openscad_mock.fill = _mock_fill
    openscad_mock.polygon = _mock_polygon
    for name in ["square", "circle"]:
        setattr(openscad_mock, name, lambda *_a, **_k: _AabbSolid())
    sys.modules["openscad"] = openscad_mock


install()
