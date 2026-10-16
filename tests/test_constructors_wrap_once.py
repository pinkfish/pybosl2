# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""A constructor wraps its native handle once, and `ruler(labels=True)` builds (SPEC C-14a, E-1).

T91 asserted C-14a on all 51 **parts**: a part's `.shape` is the finished geometry, never the raw
native handle its wrapper holds. `ruler` is not a part -- it is a top-level constructor -- so it
was outside that guard, and it broke the invariant from the other side: it returned
`Bosl2Solid(_finish3(...))`, and `_finish3` is declared `-> Bosl2Solid` and already wraps. The
result was **double-wrapped**, so `ruler(...).shape` was a `CsgSolid`, `.vnf()` reached `.mesh` on
a wrapper, and the ruler could not be meshed or exported at all. `partition_cut_mask` did the same,
and there the extra wrap was *how the function satisfied its own* `-> Bosl2Solid` annotation.

`mypy --strict` cannot see either: `PyOpenSCAD` is an untyped third-party class, so the wrapper's
`shape` parameter accepts anything. Every other `_finish3` caller in `surfaces3d.py` returns it
directly; `ruler` was the only one that re-wrapped.

Separately, **`ruler(labels=True)` raised a bare `TypeError: invalid argument left to operator` at
every size**. The function is a native builder -- `pieces` is declared `list[PyOpenSCAD]` and the
ticks come from `_ocube` -- but the label pieces came back from the façade's `linear_extrude` as
`CsgSolid` wrappers and were appended as such. The list alternated native and wrapped, so
`base | p` fell through to pythonscad's own operator with an argument it does not understand. Text
itself was never the problem: it builds, bounds and extrudes fine, and all 110 label strings were
created successfully before the union failed.

The fixture is honest about its reach: 83 of the ~100 top-level callables cannot be built from
generic arguments, so the sweep below covers the 14 that can plus the three named cases. That is
not a scope this file can widen without a per-shape fixture, which T99 and T102 both rejected.
"""

from __future__ import annotations

import inspect

import pytest

import pybosl2
from pybosl2.partitions import partition_cut_mask
from pybosl2.surfaces3d import ruler

#: Enough to build a shape, by parameter name. Deliberately generic: a per-shape table would make
#: this a list of cases rather than a sweep, and the sweep's value is that it needs no curation.
GENERIC = {
    "radius": 5.0,
    "r": 5.0,
    "diameter": 10.0,
    "height": 10.0,
    "h": 10.0,
    "length": 20.0,
    "size": [10.0, 10.0, 10.0],
    "size1": [10.0, 10.0],
    "size2": [6.0, 6.0],
    "sides": 6,
    "num_sides": 6,
    "n": 6,
    "data": [[0.0, 1.0], [1.0, 2.0]],
    "l": 20.0,
    "wall": 1.0,
    "width": 8.0,
    "angle": 90.0,
    "turns": 3,
}

#: The two that were double-wrapped, named so they are covered whatever the sweep reaches. `ruler`
#: is not exported at the top level, which is why the sweep alone missed it.
NAMED = {
    "ruler": lambda: ruler(length=20.0, depth=1),
    "ruler(labels=True)": lambda: ruler(length=20.0, depth=1, labels=True),
    "partition_cut_mask": lambda: partition_cut_mask(length=60.0, height=20.0, cutsize=8.0),
}


def _buildable() -> dict[str, object]:
    found: dict[str, object] = {}
    for name in sorted(dir(pybosl2)):
        if name.startswith("_"):
            continue
        fn = getattr(pybosl2, name, None)
        if not callable(fn) or inspect.isclass(fn):
            continue
        try:
            params = inspect.signature(fn).parameters
        except (TypeError, ValueError):  # pragma: no cover - a builtin or C callable
            continue
        try:
            built = fn(**{k: v for k, v in GENERIC.items() if k in params})
        except Exception:
            continue
        if getattr(built, "shape", None) is not None:
            found[name] = built
    return found


BUILDABLE = _buildable()


def test_the_sweep_reaches_some_constructors() -> None:
    """A sweep that built nothing would make the check below vacuous."""
    assert len(BUILDABLE) >= 10, (
        f"only {len(BUILDABLE)} top-level constructors built from generic arguments; the sweep is "
        f"broken rather than the package being empty"
    )


@pytest.mark.parametrize("name", sorted(BUILDABLE))
def test_a_constructor_wraps_a_native_handle_not_a_wrapper(name: str) -> None:
    """SPEC C-14a: on a wrapper, `.shape` is the raw native handle -- wrapped twice it is not."""
    inner = type(BUILDABLE[name].shape).__name__  # type: ignore[attr-defined]
    assert not inner.startswith(("Csg", "Sdf")), (
        f"{name}().shape is a {inner}, so the result is wrapped twice. `.vnf()` reaches `.mesh` on "
        f"a wrapper and the shape cannot be meshed or exported. `mypy` cannot catch it: the "
        f"wrapper's `shape` parameter is typed with an untyped third-party class"
    )


@pytest.mark.parametrize("label", sorted(NAMED))
def test_the_named_constructors_wrap_once_and_mesh(label: str) -> None:
    """The three cases found by hand, asserted end to end rather than by type alone.

    `.vnf()` is the measurement that matters: it is what a double wrap actually breaks, and it
    would still fail if the wrapping were fixed and something else put a wrapper in the way.
    """
    built = NAMED[label]()
    inner = type(built.shape).__name__
    assert not inner.startswith(("Csg", "Sdf")), f"{label}.shape is a {inner}"
    assert float(built.vnf().volume()) > 0.0, f"{label} meshed to nothing"


def test_a_labelled_ruler_builds_and_adds_material() -> None:
    """SPEC E-1: `labels=True` raised a bare TypeError at every length and depth.

    Asserted as *more material than the unlabelled ruler* rather than merely "it builds": the
    labels are extruded text unioned into the body, so if they were silently dropped the call would
    succeed and measure the same. The margin is small -- 200.00 against 200.81 mm^3 at these
    dimensions -- because the labels are thin, which is exactly why a bounds comparison cannot see
    them: they sit inside the ruler's envelope.
    """
    plain = float(ruler(length=20.0, depth=1, labels=False).vnf().volume())
    labelled = float(ruler(length=20.0, depth=1, labels=True).vnf().volume())
    assert labelled > plain, (
        f"a labelled ruler measures {labelled} and an unlabelled one {plain}; the labels are not reaching the solid"
    )


@pytest.mark.parametrize(("length", "depth"), [(5.0, 1), (20.0, 2), (50.0, 2)])
def test_a_labelled_ruler_builds_at_every_size(length: float, depth: int) -> None:
    """It failed at every size, so more than one is checked -- the defect was unconditional."""
    assert float(ruler(length=length, depth=depth, labels=True).vnf().volume()) > 0.0
