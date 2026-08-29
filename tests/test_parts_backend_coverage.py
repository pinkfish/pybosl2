# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""How much of the parts library builds on the SDF backend, measured (SPEC S-46a, PAR-1).

SPEC §12.2's last open item is a *number*: how many parts build on either backend and why the rest
do not. It was written by hand and nothing checked it, which is the failure mode B2-1 names --
"a claim of parity that nothing measures is a wish". It had drifted: the spec said 38 of 53 build
and 15 refuse; the truth is 40 of 51 build and 11 refuse, because the count included an alias
(`manfrotto_rc2_plate` *is* `ManfrottoRC2Plate`) and had not been rerun since parts were ported.

The reason held up exactly, though: **all 11 refusals cite non-convexity**, which is a fact about
the mathematics rather than about effort. An SDF polyhedron is the intersection of its face
half-spaces and so is always convex; a threaded rod, a bevel gear tooth and a jigsaw rail are not.
Closing the gap would mean approximating a distance field for a non-convex mesh, which SPEC B-5
forbids.

So this file pins the number and the reason, and fails when either changes -- including when it
changes for the *better*, so a part that gains an SDF form is recorded rather than absorbed.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

import pytest

import pybosl2.parts as parts
import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
from pybosl2 import use_backend
from pybosl2.exceptions import UnsupportedByBackendError

#: Parts that cannot build on the SDF backend, each because its geometry is a non-convex mesh.
#: **This list only shrinks.** An entry leaves it when the part gains an SDF form; nothing may be
#: added without a stated reason, and "it was easier" is not one (SPEC PAR-2).
CSG_ONLY_PARTS = frozenset(
    {
        "BevelGear",  # spiral bevel teeth: a swept non-convex surface
        "ManfrottoRC2Plate",  # dovetail plate profile, swept
        "Nut",  # its thread is a ThreadedNut
        "Rail",  # jigsaw/dovetail rail section, swept
        "Screw",  # its thread is a ThreadedRod
        "ThinningWall",  # a tapered web between two rims
        "ThreadedNut",  # helical thread surface as a VNF grid
        "ThreadedRod",  # helical thread surface as a VNF grid
        "WireBundle",  # each wire is a swept tube along a routed path
        "Worm",  # helical worm thread
        "WormGear",  # throated teeth cut by a worm
    }
)

#: Constructor arguments for parts that need more than their defaults.
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
}
_KWARGS: dict[str, dict[str, Any]] = {"RingHook": {"outer_radius": 6.0, "inner_radius": 4.0}}
_POSITIONAL_DEFAULTS: dict[str, tuple[Any, ...]] = {"RingHook": ([20.0, 10.0, 4.0], 5.0)}


def _distinct_parts() -> dict[str, type]:
    """Every part class exactly once, keyed by its own name.

    Deduplicated by identity: `manfrotto_rc2_plate` is a second name for `ManfrottoRC2Plate`, and
    counting it twice is what made the spec's total 53 instead of 51.
    """
    seen: set[int] = set()
    found: dict[str, type] = {}
    for module_info in pkgutil.iter_modules(parts.__path__):
        module = importlib.import_module(f"pybosl2.parts.{module_info.name}")
        for name, obj in vars(module).items():
            if not (inspect.isclass(obj) and obj.__module__ == module.__name__):
                continue
            if name.startswith("_") or name == "Buildable":
                continue
            if not isinstance(inspect.getattr_static(obj, "shape", None), property):
                continue
            if id(obj) in seen:
                continue
            seen.add(id(obj))
            found[obj.__name__] = obj
    return found


def _arguments(cls: type) -> tuple[tuple[Any, ...], dict[str, Any]]:
    name = cls.__name__
    if name in _POSITIONAL_DEFAULTS:
        return _POSITIONAL_DEFAULTS[name], _KWARGS.get(name, {})
    if name in _ARGS:
        return _ARGS[name], _KWARGS.get(name, {})
    args: list[Any] = []
    for param in list(inspect.signature(cls.__init__).parameters.values())[1:]:
        if param.default is not inspect.Parameter.empty or param.kind in (
            param.VAR_POSITIONAL,
            param.VAR_KEYWORD,
        ):
            continue
        annotation = str(param.annotation)
        if "int" in annotation:
            args.append(6)
        elif any(token in annotation for token in ("Sequence", "list", "Path")):
            args.append([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]])
        else:
            args.append(10.0)
    return tuple(args), _KWARGS.get(name, {})


def _build_on_sdf(cls: type) -> Exception | None:
    """Return the exception a part raises on the SDF backend, or None if it builds."""
    args, kwargs = _arguments(cls)
    try:
        with use_backend("sdf"):
            _ = cls(*args, **kwargs).shape
    except Exception as exc:
        return exc
    return None


PARTS = _distinct_parts()


def test_every_part_either_builds_on_sdf_or_is_listed() -> None:
    """No part may fail on SDF for a reason nobody wrote down (SPEC PAR-2)."""
    surprises: dict[str, str] = {}
    for name, cls in sorted(PARTS.items()):
        failure = _build_on_sdf(cls)
        if failure is not None and name not in CSG_ONLY_PARTS:
            surprises[name] = f"{type(failure).__name__}: {failure}"[:160]
    assert not surprises, (
        "these parts do not build on the SDF backend and are not in CSG_ONLY_PARTS. Either give "
        f"them an SDF form or add them with a stated reason (SPEC PAR-2): {surprises}"
    )


def test_the_csg_only_list_is_not_stale() -> None:
    """A part that has gained an SDF form comes off the list, so the gap cannot be overstated."""
    now_building = sorted(name for name in CSG_ONLY_PARTS if _build_on_sdf(PARTS[name]) is None)
    assert not now_building, (
        f"these now build on the SDF backend -- remove them from CSG_ONLY_PARTS and update SPEC §12.2: {now_building}"
    )


@pytest.mark.parametrize("name", sorted(CSG_ONLY_PARTS))
def test_each_refusal_names_non_convexity(name: str) -> None:
    """The stated reason is the whole justification for the gap, so it is checked per part.

    SPEC B-5 forbids approximating a distance field, and an SDF polyhedron is the intersection of
    its face half-spaces -- always convex. A refusal citing anything else would be a gap that
    *could* be closed, hiding inside one that cannot.
    """
    failure = _build_on_sdf(PARTS[name])
    assert isinstance(failure, UnsupportedByBackendError), (
        f"{name} is listed CSG-only but failed with {type(failure).__name__}: {failure}"
    )
    # Matched on meaning rather than one spelling: a part that builds lazily refuses from its own
    # `shape` with its own wording ("faces are not convex", "no distance-field form") rather than
    # from a generic guard at construction. Pinning the literal substring made the *better*,
    # more specific message look like a different reason.
    reasons = ("non-convex", "not convex", "no distance-field form", "has no closed-form")
    assert any(reason in str(failure) for reason in reasons), (
        f"{name} refuses for a reason other than non-convexity, which is the only reason "
        f"SPEC §12.2 accepts for this gap: {failure}"
    )


def test_the_measured_coverage_matches_what_the_spec_claims() -> None:
    """SPEC §12.2 states a number; this is the thing that makes it true (SPEC B2-1)."""
    from pathlib import Path

    building = sum(1 for cls in PARTS.values() if _build_on_sdf(cls) is None)
    assert building == len(PARTS) - len(CSG_ONLY_PARTS)

    spec = (Path(__file__).resolve().parent.parent / "SPEC.md").read_text()
    section = spec.split("### 12.2 Open", 1)[1].split("## 13.", 1)[0]
    assert f"{building} of the {len(PARTS)} parts" in section, (
        f"SPEC §12.2 does not state the measured figure. It is {building} of {len(PARTS)} parts "
        f"building on either backend, with {len(CSG_ONLY_PARTS)} refusing."
    )
