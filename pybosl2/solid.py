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
from pybosl2.exceptions import CrossBackendError, UnsupportedByBackendError

#: Resolution knobs whose default is ambient rather than per-shape (see pybosl2.defaults).
_AMBIENT = frozenset({"fn", "fa", "fs", "res"})

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pybosl2._edges_lang import Anchor, EdgeAtom

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
    size: float | Sequence[float] | None = None,
    *,
    chamfer: float | None = None,
    rounding: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a cube on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.cube`).
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
    size: float | Sequence[float] | None = None,
    *,
    chamfer: float | None = None,
    rounding: float | None = None,
    edges: EdgeAtom | list[EdgeAtom] | None = None,
    except_edges: list[EdgeAtom] | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a cuboid on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.cuboid`).
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
    shift: Sequence[float] | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a cyl on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.cyl`).
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
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a cylinder on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.cylinder`).
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
    size: float | None = None,
    *,
    anchor: Anchor | Sequence[float] | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    res: int | None = None,
) -> Solid:
    """Return an octahedron on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.octahedron`).
    """
    return get_backend().construct(
        "octahedron", given_arguments({"size": size, "anchor": anchor, "spin": spin, "orient": orient, "res": res})
    )


def onion(
    radius: float | None = None,
    *,
    angle: float | None = None,
    cap_height: float | None = None,
    diameter: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return an onion on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.onion`).
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
    angle: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    length: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a pie_slice on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.pie_slice`).
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
    shift: Sequence[float] | None = None,
    length: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a prismoid on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.prismoid`).
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
    rounding: float | Sequence[float] | None = None,
    inner_rounding: float | Sequence[float] | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    length: float | None = None,
    center: bool | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    res: int | None = None,
) -> Solid:
    """Return a rect_tube on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.rect_tube`).
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
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    realign: bool | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a regular_prism on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.regular_prism`).
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
    anchor: Anchor | Sequence[float] | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a sphere on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.sphere`).
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
    anchor: Anchor | Sequence[float] | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a spheroid on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.spheroid`).
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
    angle: float | None = None,
    cap_height: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a teardrop on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.teardrop`).
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
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a torus on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.torus`).
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
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a tube on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.tube`).
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
    size: Sequence[float] | None = None,
    *,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    res: int | None = None,
) -> Solid:
    """Return a wedge on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.wedge`).
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
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a xcyl on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.xcyl`).
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
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a ycyl on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.ycyl`).
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
    spin: float | None = None,
    orient: Anchor | Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a zcyl on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization. Only the
    arguments actually given are passed on, so each backend sees the ones it knows:
    *res* is the SDF backend's resolution and *spin*/*orient*/*fn*/*fa*/*fs* are the CSG
    backend's. Anything outside this shared set lives on the backend's own constructor
    (:func:`pybosl2.shapes3d.zcyl`).
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


def effective_defaults(shape: str, backend: str | None = None) -> dict[str, Any]:
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
        Each parameter of that backend's constructor mapped to its default, omitting the ones with
        no default (the caller must supply those) and the ambient resolution knobs, which come
        from :func:`pybosl2.defaults.use_defaults`.

    Raises:
        ValueError: If the backend has no constructor by that name.

    Examples:
        >>> from pybosl2.solid import effective_defaults
        >>> effective_defaults("cuboid")["size"]
        (1, 1, 1)

    """
    constructor = get_backend(backend).constructor(shape)
    parameters = inspect.signature(constructor).parameters
    return {
        name: parameter.default
        for name, parameter in parameters.items()
        if parameter.default is not inspect.Parameter.empty and name not in _AMBIENT
    }


def polyhedron(points: Any, faces: Any = None, convexity: int | None = None) -> Solid:
    """Return a polyhedron on the active backend.

    Backends differ on what a polyhedron means (this is not part of the shared primitive surface):
    the CSG backend builds the exact mesh from *points* and *faces* (both required); the SDF backend
    ignores *faces* and builds the convex hull of *points* as a distance field.
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
    """Return the union of *solids* on the active backend (all operands must share the active backend).

    Raises:
        ValueError: If no solids are given.

    """
    _require_operands("union", solids)
    return get_backend().union(solids)


def difference(*solids: Solid) -> Solid:
    """Return the first solid minus the rest, on the active backend.

    Raises:
        ValueError: If no solids are given.

    """
    _require_operands("difference", solids)
    return get_backend().difference(solids)


def intersection(*solids: Solid) -> Solid:
    """Return the intersection of *solids* on the active backend.

    Raises:
        ValueError: If no solids are given.

    """
    _require_operands("intersection", solids)
    return get_backend().intersection(solids)
