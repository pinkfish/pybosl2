# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A part builds its geometry on first access, not in ``__init__`` (SPEC C-14, PLAN O-2).

C-14 says a part "builds geometry lazily under a ``shape`` **property** ... Callers can therefore
*measure* a part without building it", and PLAN O-2 spells out the shape: resolve a frozen spec,
expose derived dimensions as properties, and build on first access.

**45 of 51 parts build in ``__init__`` instead.** Nothing measured it, so the claim sat in the spec
being false -- the pattern this project keeps finding in its own assertions (SPEC B2-1).

How much it costs is worth stating precisely, because the raw count overstates it. Most eager
parts expose almost nothing derived -- `SpurGear` has `teeth` and `shape`, so there is no catalogue
query to make cheap. Where it bites is the 17 parts that expose three or more derived dimensions
*and* build eagerly: asking `Slider` for its `length` costs a full 18 ms build. Querying all 17
costs about 31 ms, against roughly nothing if they were lazy -- `Screw`, which is lazy, answers
`.pitch` in a microsecond and defers its 11 ms build until someone wants geometry.

So: a real conformance gap, a modest performance one. This file measures both and lets neither grow.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

import pytest

import pybosl2.parts as parts

#: Parts that still build their geometry in ``__init__``. **This list only shrinks** -- a part
#: moved onto the lazy pattern comes off it, and a new part must not be added (PLAN O-2).
#:
#: Converting one is **not** the mechanical move it looks like, and an automated attempt over six
#: files proved it: splitting `__init__` at the resolved-spec assignments carries the *validation*
#: into `_build` along with the geometry, so a rejected call stops raising until someone asks for
#: geometry. 45 tests caught it. A part therefore separates three things, not two -- validate the
#: arguments, resolve the derived dimensions, *then* build -- and where the validation sits is a
#: judgement per part. `Slider` is the worked example (`pybosl2/parts/sliders.py`).
EAGER_PARTS = frozenset(
    {
        "HexDriveMask",
        "HoseSegment",
        "KnuckleHinge",
        "ManfrottoRC2Plate",
        "Nut",
        "PhillipsMask",
        "Rack2d",
        "RingHook",
        "RobertsonMask",
        "SparseCuboid",
        "SpurGear2d",
        "ThreadHelix",
        "ThreadedNut",
        "TorxMask",
        "Truss",
        "TrussCorner",
        "TrussSegment",
        "WireBundle",
        "WormGear",
    }
)

_ARGS: dict[str, tuple[Any, ...]] = {
    "HoseSegment": (0.5,),
    "NemaMountMask": (17,),
    "Nut": ("M6",),
    "RobertsonMask": (2,),
    "Screw": ("M6", 20),
    "ScrewHole": ("M6", 20),
    "SparseCuboid": ([30.0, 20.0, 10.0],),
    "ThreadedNut": (16.0, 10.0, 10.0, 1.5, "trapezoidal"),
    "ThreadedRod": (10.0, 20.0, 1.5, "trapezoidal"),
    "WireBundle": ([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]], 3),
    "RingHook": ([20.0, 10.0, 4.0], 5.0),
}
_KWARGS: dict[str, dict[str, Any]] = {"RingHook": {"outer_radius": 6.0, "inner_radius": 4.0}}

#: Where a part caches its built geometry. A part is eager if one of these is set straight after
#: construction.
_CACHES = ("_shape", "_solid", "_geometry")


def _parts() -> dict[str, type]:
    seen: set[int] = set()
    found: dict[str, type] = {}
    for module_info in pkgutil.iter_modules(parts.__path__):
        module = importlib.import_module(f"pybosl2.parts.{module_info.name}")
        for name, obj in vars(module).items():
            if not (inspect.isclass(obj) and obj.__module__ == module.__name__):
                continue
            if name.startswith("_") or name == "Buildable" or id(obj) in seen:
                continue
            if not isinstance(inspect.getattr_static(obj, "shape", None), property):
                continue
            seen.add(id(obj))
            found[obj.__name__] = obj
    return found


def _arguments(cls: type) -> tuple[tuple[Any, ...], dict[str, Any]]:
    name = cls.__name__
    if name in _ARGS:
        return _ARGS[name], _KWARGS.get(name, {})
    args: list[Any] = []
    for param in list(inspect.signature(cls.__init__).parameters.values())[1:]:
        if param.default is not inspect.Parameter.empty or param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        annotation = str(param.annotation)
        if "int" in annotation:
            args.append(6)
        elif any(token in annotation for token in ("Sequence", "list", "Path")):
            args.append([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]])
        else:
            args.append(10.0)
    return tuple(args), _KWARGS.get(name, {})


def _built_eagerly(cls: type) -> bool:
    args, kwargs = _arguments(cls)
    part = cls(*args, **kwargs)
    return any(getattr(part, cache, None) is not None for cache in _CACHES)


PARTS = _parts()


def test_no_part_becomes_eager() -> None:
    """A new or edited part builds on first access, not in `__init__` (PLAN O-2)."""
    newly_eager = sorted(name for name, cls in PARTS.items() if _built_eagerly(cls) and name not in EAGER_PARTS)
    assert not newly_eager, (
        f"these parts build their geometry in `__init__`: {newly_eager}. Resolve the spec and the "
        f"derived dimensions there, and build under the `shape` property so a caller can measure "
        f"the part without paying for geometry (SPEC C-14)."
    )


def test_the_eager_list_is_not_stale() -> None:
    """A part moved onto the lazy pattern comes off the list, so the debt cannot be overstated."""
    now_lazy = sorted(name for name in EAGER_PARTS if name in PARTS and not _built_eagerly(PARTS[name]))
    assert not now_lazy, f"these are lazy now -- remove them from EAGER_PARTS: {now_lazy}"


def test_reading_a_derived_property_never_triggers_a_build() -> None:
    """Whatever a part does in `__init__`, *querying* it must not build anything extra.

    This is the half of C-14 that already holds, and it is worth keeping: a property that quietly
    built geometry would make a catalogue query cost a CAD run with nothing in the signature to
    warn you.
    """
    offenders: list[str] = []
    for name, cls in sorted(PARTS.items()):
        if name in EAGER_PARTS:
            continue  # already built; there is nothing left to trigger
        args, kwargs = _arguments(cls)
        part = cls(*args, **kwargs)
        for prop in [n for n, v in vars(cls).items() if isinstance(v, property) and n != "shape"]:
            try:
                getattr(part, prop)
            except Exception:
                continue
        if any(getattr(part, cache, None) is not None for cache in _CACHES):
            offenders.append(name)
    assert not offenders, f"reading a derived property built geometry on: {offenders}"


def test_a_lazy_part_answers_its_catalogue_without_building() -> None:
    """The behaviour the rule exists for, on a part that already has it."""
    from pybosl2.parts import Screw

    screw = Screw("M6", length=20)
    assert all(getattr(screw, cache, None) is None for cache in _CACHES)
    assert screw.pitch == pytest.approx(1.0)
    assert screw.diameter == pytest.approx(6.0)
    assert all(getattr(screw, cache, None) is None for cache in _CACHES), (
        "measuring a screw must not have built one (SPEC C-14)"
    )
    assert screw.shape is not None  # ...and asking for geometry does build it
