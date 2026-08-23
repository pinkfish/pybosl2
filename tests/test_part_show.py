# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every part's show() hands its shape to the renderer and returns it (SPEC S-49, S-51).

`show()` is the one call in the library with a session side effect, and the convention every
docstring example ends with -- so each part's delegation is exercised here rather than only in the
docs build, which needs the PythonSCAD app.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

import pybosl2.parts as parts
from pybosl2.parts.enums import ScrewDriveType, ScrewHeadType
from pybosl2.parts.threading import _iso_profile

#: A real ISO thread profile, as the threading tests build one.
_ISO_PROFILE = _iso_profile()

#: Constructor arguments for the parts that need them; everything else builds bare (SPEC P-1).
KEYWORDS: dict[str, dict[str, Any]] = {
    # RingHook needs exactly two of outer radius / inner radius / wall
    "RingHook": {"outer_radius": 25.0, "inner_radius": 20.0},
}

ARGUMENTS: dict[str, tuple[Any, ...]] = {
    "LivingHingeMask": (40, 3),
    "RingHook": ([50.0, 10.0], 25.0),  # plus the two radii below
    "HoseSegment": (0.5,),  # 1/2" is a real trade size
    "NemaMountMask": (17,),
    "HexDriveMask": (3, 5),
    "RobertsonMask": (2,),
    "TorxMask": (20,),
    "TorxMask2d": (20,),
    "hex_mask": (3, 5),
    "Screw": ("M6", 20),
    "ScrewHole": ("M6", 20),
    "Nut": ("M6",),
    "ThreadedNut": (18.0, 12.0, 10.0, 1.75, _ISO_PROFILE),
    "ThreadedRod": (16.0, 24.0, 2.0, _ISO_PROFILE),
    "ThreadHelix": (8.0, 1.25),
    "SparseCuboid": ([20, 20, 20],),
    "WireBundle": ([[0.0, 0.0, 0.0], [20.0, 0.0, 0.0], [20.0, 20.0, 0.0]], 3),
}


def _part_classes() -> list[str]:
    names = []
    for name in parts.__all__:
        obj = getattr(parts, name)
        if not inspect.isclass(obj) or not hasattr(obj, "show"):
            continue
        names.append(name)
    return sorted(names)


@pytest.mark.parametrize("name", _part_classes())
def test_show_returns_the_parts_shape(name: str) -> None:
    """show() hands back the part's own shape object, not a copy and not None (SPEC S-49)."""
    cls = getattr(parts, name)
    args = ARGUMENTS.get(name, ())
    part = cls(*args, **KEYWORDS.get(name, {}))
    shown = part.show()
    assert shown is not None, f"{name}.show() returned None (SPEC S-49)"
    assert shown is part.shape, f"{name}.show() returned a different object than .shape (SPEC S-51)"


def test_show_is_the_shape_itself() -> None:
    """The value show() hands back is the shape, so a chain can continue from it."""
    screw = parts.Screw("M6", 20, head=ScrewHeadType.SOCKET, drive=ScrewDriveType.HEX)
    assert screw.show().bounds() == screw.shape.bounds()


def test_every_part_refuses_on_another_backend() -> None:
    """A part never hands back CSG geometry inside an sdf block (SPEC S-46a).

    Parts are composed from CSG primitives, meshes and native operations, so none has an SDF form
    yet. Refusing beats returning a shape that cannot combine with the surrounding SDF work and
    only fails much later. The refusal can come from the constructor (parts that build eagerly) or
    from the `shape` property; either is fine as long as it names the way forward.
    """
    import pybosl2.sdf  # noqa: F401  -- registers the sdf backend
    from pybosl2._backend import use_backend
    from pybosl2.exceptions import UnsupportedByBackendError

    leaked: list[str] = []
    unhelpful: list[str] = []
    with use_backend("sdf"):
        for name in _part_classes():
            cls = getattr(parts, name)
            try:
                shape = cls(*ARGUMENTS.get(name, ()), **KEYWORDS.get(name, {})).shape
            except UnsupportedByBackendError as exc:
                if "use_backend" not in str(exc):
                    unhelpful.append(name)
                continue
            if getattr(shape, "backend", None) == "csg":
                leaked.append(name)
    assert not leaked, f"parts that built CSG geometry inside an sdf block: {leaked}"
    assert not unhelpful, f"parts whose refusal does not name the way forward: {unhelpful}"


#: Parts that build on BOTH backends, not just CSG (SPEC S-46a, TASKS T14 phase 3). The list only
#: grows: a part converted to the façade goes in, and a part that stops building on SDF is a
#: regression, not a bookkeeping change.
BACKEND_NEUTRAL_PARTS = frozenset(
    {
        "CorrugatedWall",
        "Dovetail",
        "HerringboneGear",
        "HexDriveMask",
        "HoseSegment",
        "KnuckleHinge",
        "KnuckleHingePair",
        "LivingHingeMask",
        "NarrowingStrut",
        "NemaMotor",
        "NemaMountMask",
        "PhillipsMask",
        "Rack",
        "RegularPolyhedron",
        "RingGear",
        "RingHook",
        "RobertsonMask",
        "ScrewHole",
        "Slider",
        "SnapLock",
        "SnapPin",
        "SnapPinSocket",
        "SnapSocket",
        "SparseCuboid",
        "SparseWall",
        "SpurGear",
        "ThinningTriangle",
        "Truss",
        "TrussClip",
        "TrussCorner",
        "TrussFoot",
        "TrussJoiner",
        "TrussSegment",
        "TrussSupport",
        "TrussUClip",
        "hex_mask",
    }
)


#: Parts that build on both backends but whose SDF `bounds()` is conservative rather than exact.
#: Both are octagonal prisms turned half a facet: the SDF box after a rotation is the old box's
#: corners transformed, which is exact only for a shape that fills its box (a cuboid does, an
#: octagon does not). The geometry is right; only the reported envelope is loose, and it is a
#: superset, so nothing is clipped. Fixing it means carrying the profile outline on the shape so a
#: rotation can recompute the box -- see TASKS T14.
CONSERVATIVE_SDF_BOUNDS = frozenset({"TrussFoot", "TrussJoiner"})


@pytest.mark.parametrize("name", sorted(BACKEND_NEUTRAL_PARTS - CONSERVATIVE_SDF_BOUNDS))
def test_a_converted_part_builds_the_same_shape_on_either_backend(name: str) -> None:
    """The point of the conversion: one source, either backend, the same geometry.

    Sizes are compared with a tolerance because a CSG solid is faceted and its SDF twin is exact --
    a cylinder's faceted hull sits just inside the true one -- so they agree to within the facet
    error, not to the bit.
    """
    import pybosl2.sdf  # noqa: F401  -- registers the sdf backend
    from pybosl2._backend import use_backend

    built = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            shape = getattr(parts, name)(*ARGUMENTS.get(name, ()), **KEYWORDS.get(name, {})).shape
        assert shape.backend == backend, f"{name} built {shape.backend} geometry inside a {backend} block"
        built[backend] = shape.bounds()

    csg_centre, csg_size = built["csg"]
    sdf_centre, sdf_size = built["sdf"]
    for axis in range(3):
        assert abs(float(csg_size[axis]) - float(sdf_size[axis])) < 0.5, (
            f"{name}: backends disagree on size, csg={list(csg_size)} sdf={list(sdf_size)}"
        )
        assert abs(float(csg_centre[axis]) - float(sdf_centre[axis])) < 0.5, (
            f"{name}: backends disagree on placement, csg={list(csg_centre)} sdf={list(sdf_centre)}"
        )


def test_the_converted_list_matches_what_actually_builds() -> None:
    """Stops the list drifting from the code in either direction."""
    import pybosl2.sdf  # noqa: F401  -- registers the sdf backend
    from pybosl2._backend import use_backend
    from pybosl2.exceptions import UnsupportedByBackendError

    builds = set()
    with use_backend("sdf"):
        for name in _part_classes():
            try:
                shape = getattr(parts, name)(*ARGUMENTS.get(name, ()), **KEYWORDS.get(name, {})).shape
            except UnsupportedByBackendError:
                continue
            if getattr(shape, "backend", None) == "sdf":
                builds.add(name)

    assert builds == set(BACKEND_NEUTRAL_PARTS), (
        "parts that build on the SDF backend have changed (SPEC S-46a):\n"
        f"  newly building: {sorted(builds - BACKEND_NEUTRAL_PARTS)}\n"
        f"  no longer building: {sorted(BACKEND_NEUTRAL_PARTS - builds)}"
    )


def test_a_refusal_names_what_the_part_needs() -> None:
    """SPEC E-4: the message says why *this* part needs CSG, not that the library does.

    It used to say "the parts library builds exact CSG geometry" for all 53. That stopped being
    true once a third of them were converted, and it never told anyone which operation was the
    obstacle -- so `@csg_part` now takes the reason and the message carries it.
    """
    import pybosl2.sdf  # noqa: F401  -- registers the sdf backend
    from pybosl2._backend import use_backend
    from pybosl2.exceptions import UnsupportedByBackendError

    vague: list[str] = []
    with use_backend("sdf"):
        for name in _part_classes():
            if name in BACKEND_NEUTRAL_PARTS:
                continue
            try:
                _ = getattr(parts, name)(*ARGUMENTS.get(name, ()), **KEYWORDS.get(name, {})).shape
            except UnsupportedByBackendError as exc:
                message = str(exc)
                if "the parts library builds exact CSG geometry" in message:
                    vague.append(name)
                assert "use_backend" in message, f"{name}'s refusal does not say what to do: {message}"

    assert not vague, f"parts still refusing with the old library-wide reason: {vague}"


def test_the_named_reason_reaches_the_message() -> None:
    """The decorator is only worth its argument if the argument is what the caller reads.

    `ThreadedRod` is the subject because its guard is what actually fires: it sweeps its thread
    with `spiral_sweep()`, which has no dispatched form to refuse first, so the refusal comes from
    `shape`. Where a part reaches a *dispatched* operation instead -- `WireBundle` hits
    `polyhedron()`'s convexity check -- the primitive refuses before the guard is ever consulted,
    which is the more precise message anyway.
    """
    import pybosl2.sdf  # noqa: F401  -- registers the sdf backend
    from pybosl2._backend import use_backend
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.parts.threading import _iso_profile

    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError) as excinfo:
        _ = parts.ThreadedRod(16.0, 24.0, 2.0, _iso_profile()).shape
    message = str(excinfo.value)
    assert "ThreadedRod" in message
    assert "spiral_sweep()" in message  # the operation that is actually in the way


def test_a_dispatched_operation_refuses_before_the_part_guard() -> None:
    """A part that reaches a dispatched op gets the primitive's reason, which is more specific."""
    import pybosl2.sdf  # noqa: F401  -- registers the sdf backend
    from pybosl2._backend import use_backend
    from pybosl2.exceptions import UnsupportedByBackendError

    route = [[0.0, 0.0, 0.0], [20.0, 0.0, 0.0], [20.0, 20.0, 0.0]]
    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError, match="non-convex") as excinfo:
        _ = parts.WireBundle(route, 3).shape
    assert ".to_csg()" in str(excinfo.value)


@pytest.mark.parametrize("name", sorted(CONSERVATIVE_SDF_BOUNDS))
def test_a_conservative_bounds_part_still_builds_the_right_solid(name: str) -> None:
    """Loose bounds must stay a *superset*: under-reporting would clip the meshed geometry."""
    import pybosl2.sdf  # noqa: F401  -- registers the sdf backend
    from pybosl2._backend import use_backend

    built = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            shape = getattr(parts, name)(*ARGUMENTS.get(name, ()), **KEYWORDS.get(name, {})).shape
        assert shape.backend == backend
        built[backend] = shape.bounds()

    csg_centre, csg_size = built["csg"]
    sdf_centre, sdf_size = built["sdf"]
    for axis in range(3):
        assert float(sdf_size[axis]) >= float(csg_size[axis]) - 0.01, (
            f"{name}: the SDF box is SMALLER than the real solid on axis {axis}, which would clip it"
        )
    # ... and only in the plane the rotation is in; the extruded axis is still exact.
    assert float(sdf_size[2]) == pytest.approx(float(csg_size[2]), abs=0.01)
    assert float(sdf_centre[2]) == pytest.approx(float(csg_centre[2]), abs=0.01)
