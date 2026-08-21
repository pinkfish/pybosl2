# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: Foundational
# LibFile: pybosl2/solid.py
# FileSummary: Statically typed shape constructors and backend-neutral solid facade.
# FileGroup: BOSL2

"""Statically typed shape constructors and backend-neutral solid facade."""

# The backend-neutral solid facade: unified shape constructors that build on whichever backend is
# active (``"csg"`` by default, ``"sdf"`` under ``use_backend("sdf")``). Each returns a common
# :class:`~pybosl2._backend.Solid` -- a CsgSolid on the CSG backend, an SdfSolid on the SDF backend --
# so the same code realizes exact CSG or an F-Rep/signed-distance field depending on context:
#
#     from pybosl2.solid import sphere, use_backend
#     a = sphere(radius=10)                 # CSG (default) -> CsgSolid
#     with use_backend("sdf"):
#         b = sphere(radius=10)             # libfive SDF   -> SdfSolid
#
# The shape constructors below are the 3-D primitives BOTH backends expose; each dispatches by name
# through the active backend's ``construct``. n-ary CSG (union/difference/intersection) dispatches to
# the backend's own operators. The backend-specific modules (pybosl2.shapes3d, pybosl2.sdf) remain
# directly importable for anything not yet unified here.

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from pybosl2._backend import (
    Solid,
    current_backend,
    get_backend,
    given_arguments,
    set_default_backend,
    use_backend,
)
from pybosl2._edges_lang import Anchor
from pybosl2.exceptions import CrossBackendError, UnsupportedByBackendError

#: Resolution knobs whose default is ambient rather than per-shape (see pybosl2.defaults).
_AMBIENT = frozenset({"fn", "fa", "fs", "res"})

#: What an omitted argument resolves to, as reported by :func:`effective_defaults`: a scalar, a
#: size/shift tuple, an anchor, or ``None`` -- which means "decide for me" rather than "no value"
#: (PLAN T-9b). Every façade and backend default across the shape surface is one of these.
DefaultValue: "TypeAlias" = "bool | int | float | str | tuple[float, ...] | Anchor | Point | None"

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TypeAlias

    from pybosl2._edges_lang import EdgeAtom
    from pybosl2.points import Point  # noqa: F401  # used by the DefaultValue alias (a string, so ruff cannot see it)

_SHARED_3D = (
    "cube",
    "cuboid",
    "cyl",
    "cylinder",
    "octahedron",
    "onion",
    "pie_slice",
    "prismoid",
    "rect_tube",
    "regular_prism",
    "sphere",
    "spheroid",
    "teardrop",
    "torus",
    "tube",
    "wedge",
    "xcyl",
    "ycyl",
    "zcyl",
)

__all__ = [
    "DefaultValue",
    "effective_defaults",
    "cube",
    "cuboid",
    "cyl",
    "cylinder",
    "octahedron",
    "onion",
    "pie_slice",
    "prismoid",
    "rect_tube",
    "regular_prism",
    "sphere",
    "spheroid",
    "teardrop",
    "torus",
    "tube",
    "wedge",
    "xcyl",
    "ycyl",
    "zcyl",
    "polyhedron",
    "union",
    "difference",
    "intersection",
    # backend controls, re-exported for convenience
    "use_backend",
    "set_default_backend",
    "current_backend",
    "Solid",
    "CrossBackendError",
    "UnsupportedByBackendError",
    "given_arguments",
]


def cube(
    size: float | Sequence[float] | None = 1,
    *,
    chamfer: float | None = None,
    rounding: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a cube on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        size: Size of the cube, a number or length-3 vector.
        chamfer: Chamfer size along all edges (default none)
        rounding: Rounding radius along all edges (default none)
        anchor: Anchor point (default Anchor.CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> FRONT+LEFT+BOTTOM)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default Anchor.TOP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        Basic cube:

        .. pythonscad-example::

            from pybosl2 import cube

            cube(size=20).show()

        Cube with chamfered edges:

        .. pythonscad-example::

            from pybosl2 import cube

            cube(size=20, chamfer=2).show()

        Cube with rounded edges:

        .. pythonscad-example::

            from pybosl2 import cube

            cube(size=20, rounding=3).show()

    """
    return get_backend().construct(
        "cube",
        given_arguments(
            {
                "size": size,
                "chamfer": chamfer,
                "rounding": rounding,
                "anchor": anchor,
                "center": center,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def cuboid(
    size: float | Sequence[float] | None = (1, 1, 1),
    *,
    chamfer: float | None = None,
    rounding: float | None = None,
    edges: EdgeAtom | list[EdgeAtom] | None = Anchor.ALL,
    except_edges: list[EdgeAtom] | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a cuboid on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        size: Size of the cuboid, a number or length-3 vector.
        chamfer: Chamfer size, inset from sides (default: no chamfer)
        rounding: Edge rounding radius (default: no rounding)
        edges: Edges to mask (default ``"ALL"``)
        except_edges: Edges to explicitly not mask (BOSL2's `except=` synonym; `except` is a Python keyword)
        anchor: Anchor point (default Anchor.CENTER)
        spin: Z-axis rotation in degrees (default 0)
        orient: Direction to rotate the top towards (default Anchor.TOP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import cuboid

            shape = cuboid([40, 30, 20])
            shape.show()

        .. pythonscad-example::

            from pybosl2 import cuboid

            shape = cuboid([40, 30, 20], rounding=5)
            shape.show()

    """
    return get_backend().construct(
        "cuboid",
        given_arguments(
            {
                "size": size,
                "chamfer": chamfer,
                "rounding": rounding,
                "edges": edges,
                "except_edges": except_edges,
                "anchor": anchor,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def cyl(
    height: float | None = None,
    radius: float | None = None,
    *,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    shift: Sequence[float] | None = (0, 0),
    anchor: Anchor | Sequence[float] | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a cyl on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        center: If given, overrides anchor (True -> CENTER, False -> BOTTOM)
        length: Length of the cylinder along its axis (default 1)
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter: Diameter of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        shift: X/Y offset for the positive end (shear) (default [0,0])
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        A basic cylinder:
        .. pythonscad-example::

            from pybosl2 import cyl

            shape = cyl(radius=10, height=30)
            shape.show()

        A cylinder with chamfered ends:
        .. pythonscad-example::

            from pybosl2 import cyl

            shape = cyl(radius=15, height=40, chamfer=2)
            shape.show()

        A cylinder with rounded ends:
        .. pythonscad-example::

            from pybosl2 import cyl

            shape = cyl(radius=12, height=35, rounding=3)
            shape.show()

    """
    return get_backend().construct(
        "cyl",
        given_arguments(
            {
                "height": height,
                "radius": radius,
                "center": center,
                "length": length,
                "radius1": radius1,
                "radius2": radius2,
                "diameter": diameter,
                "diameter1": diameter1,
                "diameter2": diameter2,
                "chamfer": chamfer,
                "chamfer1": chamfer1,
                "chamfer2": chamfer2,
                "rounding": rounding,
                "rounding1": rounding1,
                "rounding2": rounding2,
                "shift": shift,
                "anchor": anchor,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def cylinder(
    height: float | None = None,
    radius: float | None = None,
    *,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a cylinder on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        center: If given, overrides anchor (True -> CENTER, False -> BOTTOM)
        length: Length of the cylinder along its axis (default 1)
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter: Diameter of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        anchor: Anchor point (default BOTTOM if center=False, otherwise CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        A basic cylinder:

        .. pythonscad-example::

            from pybosl2 import cylinder

            cylinder(height=30, radius=10).show()

        A cylinder with chamfered ends:

        .. pythonscad-example::

            from pybosl2 import cylinder

            cylinder(height=40, radius=15, chamfer=2).show()

        A cylinder with rounded ends:

        .. pythonscad-example::

            from pybosl2 import cylinder

            cylinder(height=30, radius=12, rounding=2).show()

    """
    return get_backend().construct(
        "cylinder",
        given_arguments(
            {
                "height": height,
                "radius": radius,
                "chamfer": chamfer,
                "chamfer1": chamfer1,
                "chamfer2": chamfer2,
                "rounding": rounding,
                "rounding1": rounding1,
                "rounding2": rounding2,
                "center": center,
                "length": length,
                "radius1": radius1,
                "radius2": radius2,
                "diameter": diameter,
                "diameter1": diameter1,
                "diameter2": diameter2,
                "anchor": anchor,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def octahedron(
    size: float | None = 1,
    *,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    res: int | None = None,
) -> Solid:
    """Return a octahedron on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        size: Width of the octahedron, tip to tip.
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import octahedron

            octahedron(size=20).show()

    """
    return get_backend().construct(
        "octahedron", given_arguments({"size": size, "anchor": anchor, "spin": spin, "orient": orient, "res": res})
    )


def onion(
    radius: float | None = None,
    *,
    angle: float | None = 45,
    cap_height: float | None = None,
    diameter: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a onion on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        radius: Radius of the spherical portion of the bottom (default 1)
        angle: Angle of the cone from vertical in degrees (default 45)
        cap_height: Height above the sphere center to truncate the shape (default: no truncation)
        diameter: Diameter of the spherical portion of the bottom.
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import onion

            onion(radius=15).show()

    """
    return get_backend().construct(
        "onion",
        given_arguments(
            {
                "radius": radius,
                "angle": angle,
                "cap_height": cap_height,
                "diameter": diameter,
                "anchor": anchor,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def pie_slice(
    height: float | None = None,
    radius: float | None = None,
    *,
    angle: float | None = 30,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    length: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a pie_slice on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Height of the pie slice.
        radius: Radius of the pie slice.
        angle: Pie slice angle in degrees (default 30)
        radius1: Bottom radius of the pie slice.
        radius2: Top radius of the pie slice.
        diameter: Diameter of the pie slice.
        diameter1: Diameter of the bottom.
        diameter2: Diameter of the top.
        length: Height of the pie slice.
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor.
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import pie_slice

            pie_slice(radius=20, angle=120, height=5).show()

    """
    return get_backend().construct(
        "pie_slice",
        given_arguments(
            {
                "height": height,
                "radius": radius,
                "angle": angle,
                "radius1": radius1,
                "radius2": radius2,
                "diameter": diameter,
                "diameter1": diameter1,
                "diameter2": diameter2,
                "length": length,
                "anchor": anchor,
                "center": center,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def prismoid(
    size1: Sequence[float],
    size2: Sequence[float],
    *,
    height: float | None = None,
    shift: Sequence[float] | None = (0, 0),
    length: float | None = None,
    rounding: float | Sequence[float] | None = None,
    rounding1: float | Sequence[float] | None = None,
    rounding2: float | Sequence[float] | None = None,
    chamfer: float | Sequence[float] | None = None,
    chamfer1: float | Sequence[float] | None = None,
    chamfer2: float | Sequence[float] | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.BOTTOM,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a prismoid on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        size1: [width, length] of the bottom end.
        size2: [width, length] of the top end.
        height: Height of the prism.
        shift: [X,Y] shift of the top center relative to the bottom center.
        length: Height of the prism.
        rounding: Radius of the vertical edge rounding, or one radius per edge (CSG backend --
            the SDF prismoid has no exact form for a tapered box's independently-radiused vertical
            edges; see :func:`pybosl2.sdf.shapes3d.prismoid`).
        rounding1: Vertical edge rounding at the bottom end (CSG backend).
        rounding2: Vertical edge rounding at the top end (CSG backend).
        chamfer: Size of the vertical edge chamfer, or one size per edge (CSG backend).
        chamfer1: Vertical edge chamfer at the bottom end (CSG backend).
        chamfer2: Vertical edge chamfer at the top end (CSG backend).
        anchor: Anchor point (default BOTTOM)
        center: If given, overrides anchor.
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import prismoid

            shape = prismoid([40, 40], [20, 25], height=30)
            shape.show()

    """
    return get_backend().construct(
        "prismoid",
        given_arguments(
            {
                "size1": size1,
                "size2": size2,
                "height": height,
                "shift": shift,
                "length": length,
                "rounding": rounding,
                "rounding1": rounding1,
                "rounding2": rounding2,
                "chamfer": chamfer,
                "chamfer1": chamfer1,
                "chamfer2": chamfer2,
                "anchor": anchor,
                "center": center,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def rect_tube(
    height: float | None = None,
    size: float | Sequence[float] | None = None,
    *,
    isize: float | Sequence[float] | None = None,
    wall: float | None = None,
    rounding: float | Sequence[float] | None = 0,
    inner_rounding: float | Sequence[float] | None = 0,
    anchor: Anchor | Sequence[float] | None = Anchor.BOTTOM.vector,
    length: float | None = None,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a rect_tube on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Height of the tube (default 1)
        size: Outer [X,Y] size of the tube.
        isize: Inner [X,Y] size of the tube.
        wall: Wall thickness.
        rounding: Outer edge rounding radius (overall/bottom/top)
        inner_rounding: Inner edge rounding radius (default: same as rounding)
        anchor: Anchor point (default BOTTOM)
        length: Length of the tube (default 1)
        center: If given, overrides anchor.
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import rect_tube

            rect_tube(size=30, wall=3, height=20).show()

    """
    return get_backend().construct(
        "rect_tube",
        given_arguments(
            {
                "height": height,
                "size": size,
                "isize": isize,
                "wall": wall,
                "rounding": rounding,
                "inner_rounding": inner_rounding,
                "anchor": anchor,
                "length": length,
                "center": center,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def regular_prism(
    sides: int,
    height: float | None = None,
    radius: float | None = None,
    *,
    diameter: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    shift: Sequence[float] | None = None,
    circumscribe: bool | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    realign: bool | None = False,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a regular_prism on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        sides: Number of sides (integer >= 3)
        height: Prism height (default 1)
        radius: Overall size (see above)
        diameter: Overall size (see above)
        inner_radius: Overall size (see above)
        inner_diameter: Overall size (see above)
        side: Overall size (see above)
        length: Prism height (default 1)
        radius1: Bottom radius, for a tapered prism (CSG backend).
        radius2: Top radius, for a tapered prism (CSG backend).
        shift: ``[x, y]`` offset of the top face from the bottom (CSG backend).
        circumscribe: If True the polygon encloses the given radius instead of being inscribed in
            it (CSG backend).
        rounding: End rounding radius (overall/bottom/top)
        rounding1: End rounding radius (overall/bottom/top)
        rounding2: End rounding radius (overall/bottom/top)
        chamfer: End chamfer size (overall/bottom/top)
        chamfer1: End chamfer size (overall/bottom/top)
        chamfer2: End chamfer size (overall/bottom/top)
        realign: Rotate by half a facet so a face, not a vertex, faces +X (default False)
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> BOTTOM)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import regular_prism

            shape = regular_prism(6, height=20, radius=15)
            shape.show()

        .. pythonscad-example::

            from pybosl2 import regular_prism

            shape = regular_prism(5, height=20, inner_radius=12, rounding=2)
            shape.show()

    """
    return get_backend().construct(
        "regular_prism",
        given_arguments(
            {
                "sides": sides,
                "height": height,
                "radius": radius,
                "diameter": diameter,
                "inner_radius": inner_radius,
                "inner_diameter": inner_diameter,
                "side": side,
                "length": length,
                "radius1": radius1,
                "radius2": radius2,
                "shift": shift,
                "circumscribe": circumscribe,
                "rounding": rounding,
                "rounding1": rounding1,
                "rounding2": rounding2,
                "chamfer": chamfer,
                "chamfer1": chamfer1,
                "chamfer2": chamfer2,
                "realign": realign,
                "anchor": anchor,
                "center": center,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def sphere(
    radius: float | None = None,
    *,
    diameter: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a sphere on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        radius: Radius of the sphere.
        diameter: Diameter of the sphere.
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import sphere

            shape = sphere(radius=15)
            shape.show()

    """
    return get_backend().construct(
        "sphere",
        given_arguments(
            {
                "radius": radius,
                "diameter": diameter,
                "anchor": anchor,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def spheroid(
    radius: float | None = None,
    *,
    diameter: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a spheroid on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        radius: Radius of the spheroid.
        diameter: Diameter of the spheroid.
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import spheroid

            spheroid(radius=15).show()

    """
    return get_backend().construct(
        "spheroid",
        given_arguments(
            {
                "radius": radius,
                "diameter": diameter,
                "anchor": anchor,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def teardrop(
    height: float | None = None,
    radius: float | None = None,
    *,
    angle: float | None = 45,
    cap_height: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a teardrop on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Thickness of the teardrop (default 1)
        radius: Radius of the circular part (default 1)
        angle: Angle of the hat walls from the Z axis in degrees (default 45)
        cap_height: Height above center to truncate the shape (default: no truncation)
        radius1: Radius of the circular portion of the front end.
        radius2: Radius of the circular portion of the back end.
        diameter: Diameter of the circular portion.
        diameter1: Diameter of the front end.
        diameter2: Diameter of the back end.
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import teardrop

            shape = teardrop(radius=8, angle=45, height=15)
            shape.show()

    """
    return get_backend().construct(
        "teardrop",
        given_arguments(
            {
                "height": height,
                "radius": radius,
                "angle": angle,
                "cap_height": cap_height,
                "radius1": radius1,
                "radius2": radius2,
                "diameter": diameter,
                "diameter1": diameter1,
                "diameter2": diameter2,
                "anchor": anchor,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def torus(
    major_radius: float | None = None,
    minor_radius: float | None = None,
    *,
    major_diameter: float | None = None,
    minor_diameter: float | None = None,
    outer_radius: float | None = None,
    inner_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a torus on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        major_radius: Major radius of the torus ring (use with minor_radius or minor_diameter)
        minor_radius: Minor radius of the torus ring (use with major_radius or major_diameter)
        major_diameter: Major diameter of the torus ring.
        minor_diameter: Minor diameter of the torus ring.
        outer_radius: Outer radius of the torus (BOSL2 `or`) (use with inner_radius or inner_diameter)
        inner_radius: Inside radius of the torus (use with outer_radius or outer_diameter)
        outer_diameter: Outer diameter of the torus (use with inner_radius or inner_diameter)
        inner_diameter: Inside diameter of the torus (use with outer_radius or outer_diameter)
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> DOWN)
        spin: Z-axis rotation in degrees (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import torus

            shape = torus(major_radius=25, minor_radius=8)
            shape.show()

    """
    return get_backend().construct(
        "torus",
        given_arguments(
            {
                "major_radius": major_radius,
                "minor_radius": minor_radius,
                "major_diameter": major_diameter,
                "minor_diameter": minor_diameter,
                "outer_radius": outer_radius,
                "inner_radius": inner_radius,
                "outer_diameter": outer_diameter,
                "inner_diameter": inner_diameter,
                "anchor": anchor,
                "center": center,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def tube(
    height: float | None = None,
    outer_radius: float | None = None,
    *,
    inner_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    wall: float | None = None,
    length: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a tube on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Height of the tube (default 1)
        outer_radius: Outer radius of the tube (BOSL2 ``or``) (default 1)
        inner_radius: Inner radius of the tube.
        outer_diameter: Outer diameter of the tube.
        inner_diameter: Inner diameter of the tube.
        wall: Horizontal wall thickness (default 1)
        length: Height of the tube (default 1)
        rounding: Rounding radius on end rims (overall/bottom/top)
        rounding1: Rounding radius on end rims (overall/bottom/top)
        rounding2: Rounding radius on end rims (overall/bottom/top)
        chamfer: Chamfer size on end rims (overall/bottom/top)
        chamfer1: Chamfer size on end rims (overall/bottom/top)
        chamfer2: Chamfer size on end rims (overall/bottom/top)
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> DOWN)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import tube

            shape = tube(height=20, outer_radius=15, inner_radius=10)
            shape.show()

        A tube with chamfered end rims:

        .. pythonscad-example::

            from pybosl2 import tube

            shape = tube(height=20, outer_radius=15, inner_radius=10, chamfer=1)
            shape.show()

    """
    return get_backend().construct(
        "tube",
        given_arguments(
            {
                "height": height,
                "outer_radius": outer_radius,
                "inner_radius": inner_radius,
                "outer_diameter": outer_diameter,
                "inner_diameter": inner_diameter,
                "wall": wall,
                "length": length,
                "rounding": rounding,
                "rounding1": rounding1,
                "rounding2": rounding2,
                "chamfer": chamfer,
                "chamfer1": chamfer1,
                "chamfer2": chamfer2,
                "anchor": anchor,
                "center": center,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def wedge(
    size: Sequence[float] | None = (1, 1, 1),
    *,
    anchor: Anchor | Sequence[float] | None = Anchor.BOTTOM_FRONT_LEFT.vector,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    res: int | None = None,
) -> Solid:
    """Return a wedge on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        size: [width, thickness, height].
        anchor: Anchor point (default FRONT+LEFT+BOTTOM)
        center: If given, overrides anchor (True -> CENTER, False -> FRONT+LEFT+BOTTOM)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import wedge

            wedge([30, 20, 15]).show()

    """
    return get_backend().construct(
        "wedge",
        given_arguments({"size": size, "anchor": anchor, "center": center, "spin": spin, "orient": orient, "res": res}),
    )


def xcyl(
    height: float | None = None,
    radius: float | None = None,
    *,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a xcyl on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        length: Length of the cylinder along its axis (default 1)
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter: Diameter of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> BOTTOM)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import xcyl

            shape = xcyl(radius=10, height=30)
            shape.show()

    """
    return get_backend().construct(
        "xcyl",
        given_arguments(
            {
                "height": height,
                "radius": radius,
                "length": length,
                "radius1": radius1,
                "radius2": radius2,
                "diameter": diameter,
                "diameter1": diameter1,
                "diameter2": diameter2,
                "chamfer": chamfer,
                "chamfer1": chamfer1,
                "chamfer2": chamfer2,
                "rounding": rounding,
                "rounding1": rounding1,
                "rounding2": rounding2,
                "anchor": anchor,
                "center": center,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def ycyl(
    height: float | None = None,
    radius: float | None = None,
    *,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a ycyl on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        length: Length of the cylinder along its axis (default 1)
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter: Diameter of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> BOTTOM)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import ycyl

            shape = ycyl(radius=10, height=30)
            shape.show()

    """
    return get_backend().construct(
        "ycyl",
        given_arguments(
            {
                "height": height,
                "radius": radius,
                "length": length,
                "radius1": radius1,
                "radius2": radius2,
                "diameter": diameter,
                "diameter1": diameter1,
                "diameter2": diameter2,
                "chamfer": chamfer,
                "chamfer1": chamfer1,
                "chamfer2": chamfer2,
                "rounding": rounding,
                "rounding1": rounding1,
                "rounding2": rounding2,
                "anchor": anchor,
                "center": center,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def zcyl(
    height: float | None = None,
    radius: float | None = None,
    *,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a zcyl on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        length: Length of the cylinder along its axis (default 1)
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter: Diameter of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> BOTTOM)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend).
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend).
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend).
        res: Sampling resolution; ambient default when omitted (SDF backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import zcyl

            shape = zcyl(radius=10, height=30)
            shape.show()

    """
    return get_backend().construct(
        "zcyl",
        given_arguments(
            {
                "height": height,
                "radius": radius,
                "length": length,
                "radius1": radius1,
                "radius2": radius2,
                "diameter": diameter,
                "diameter1": diameter1,
                "diameter2": diameter2,
                "chamfer": chamfer,
                "chamfer1": chamfer1,
                "chamfer2": chamfer2,
                "rounding": rounding,
                "rounding1": rounding1,
                "rounding2": rounding2,
                "anchor": anchor,
                "center": center,
                "spin": spin,
                "orient": orient,
                "fn": fn,
                "fa": fa,
                "fs": fs,
                "res": res,
            }
        ),
    )


def effective_defaults(shape: str, backend: str | None = None) -> dict[str, DefaultValue]:
    """Report the value each argument of *shape* takes when the caller leaves it out.

    The facade constructors default every argument to ``None`` and forward only what was actually
    given (:func:`~pybosl2._backend.given_arguments`), so the backend keeps its own defaults. That
    keeps the two backends independent, but it would leave a caller unable to see what
    ``cuboid()`` with no arguments actually builds -- this reports it, read live off the
    constructor the backend would call, so it can never drift from the code.

    Args:
        shape: BOSL2 shape name, e.g. ``"cuboid"``.
        backend: Backend to report for; the active one by default.

    Returns:
        Each parameter mapped to the :data:`DefaultValue` a bare call resolves to: the façade's own default for
        everything both backends understand, plus the backend's own for its exclusive options.
        Parameters with no default (the caller must supply those) and the ambient resolution
        knobs are omitted -- the latter come from :func:`pybosl2.defaults.use_defaults`.

    Raises:
        ValueError: If the backend has no constructor by that name.

    Examples:
        >>> from pybosl2.solid import effective_defaults
        >>> effective_defaults("cuboid")["size"]
        (1, 1, 1)

    """
    facade = globals().get(shape)
    owned: dict[str, DefaultValue] = {}
    if inspect.isfunction(facade):
        # the façade owns the default for everything both backends understand (SPEC B-3)
        owned = {
            name: parameter.default
            for name, parameter in inspect.signature(facade).parameters.items()
            if parameter.default is not inspect.Parameter.empty and name not in _AMBIENT
        }
    constructor = get_backend(backend).constructor(shape)
    parameters = inspect.signature(constructor).parameters
    backend_own: dict[str, DefaultValue] = {
        name: parameter.default
        for name, parameter in parameters.items()
        if parameter.default is not inspect.Parameter.empty and name not in _AMBIENT and name not in owned
    }
    return {**owned, **backend_own}


def polyhedron(points: Any, faces: Any = None, convexity: int | None = None) -> Solid:
    """Return a polyhedron on the active backend.

    Backends differ on what a polyhedron means (this is not part of the shared primitive surface):
    the CSG backend builds the exact mesh from *points* and *faces* (both required); the SDF backend
    ignores *faces* and builds the convex hull of *points* as a distance field.

    Args:
        points: The vertices, as ``[x, y, z]`` triples.
        faces: Vertex indices per face (CSG backend; ignored by the SDF backend).
        convexity: Convexity hint for preview rendering (CSG backend).

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import polyhedron

            points = [[0, 0, 0], [20, 0, 0], [10, 18, 0], [10, 6, 16]]
            faces = [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]]
            polyhedron(points, faces).show()

    """
    return get_backend().polyhedron(points, faces, convexity=convexity)


def _require_operands(operation: str, solids: tuple[Solid, ...]) -> None:
    """Reject an n-ary boolean with nothing to combine.

    Args:
        operation: Name of the calling boolean, used in the message.
        solids: The operands as given.

    Raises:
        ValueError: If *solids* is empty.

    """
    if not solids:
        raise ValueError(f"{operation}(): needs at least one solid to combine.")


def union(*solids: Solid) -> Solid:
    """Return the union of *solids* on the active backend.

    Args:
        solids: The shapes to combine; all must share a backend (SPEC C-1).

    Returns:
        One solid covering all of them.

    Raises:
        ValueError: If no solids are given.

    Examples:
        .. pythonscad-example::

            from pybosl2 import cuboid, cyl, union

            union(cuboid([20, 20, 10]), cyl(height=20, radius=5)).show()

    """
    _require_operands("union", solids)
    return get_backend().union(solids)


def difference(*solids: Solid) -> Solid:
    """Return the first solid minus the rest, on the active backend.

    Args:
        solids: The shape to cut from, then the shapes to remove.

    Returns:
        The first solid with the others carved out of it.

    Raises:
        ValueError: If no solids are given.

    Examples:
        .. pythonscad-example::

            from pybosl2 import cuboid, cyl, difference

            difference(cuboid([20, 20, 10]), cyl(height=30, radius=5)).show()

    """
    _require_operands("difference", solids)
    return get_backend().difference(solids)


def intersection(*solids: Solid) -> Solid:
    """Return the intersection of *solids* on the active backend.

    Args:
        solids: The shapes to intersect; all must share a backend.

    Returns:
        The solid covered by every one of them.

    Raises:
        ValueError: If no solids are given.

    Examples:
        .. pythonscad-example::

            from pybosl2 import cuboid, sphere, intersection

            intersection(cuboid([20, 20, 20]), sphere(radius=13)).show()

    """
    _require_operands("intersection", solids)
    return get_backend().intersection(solids)
