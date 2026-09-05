# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A cap that cannot be built must say so, not quietly come out butt-ended.

SPEC G-8, D-1. `CapType` has three consumers -- the sweep path, the 3-D stroke and the 2-D
stroke -- and each decides for itself which members it handles. Every one of them decides by
listing the members it knows and falling through for the rest, and every fall-through lands on a
flat end: `endcap_polys` returns `[]` (which `endcap_geometry_3d` reads as "no cap"), and
`_cap_style` returns `"flat"`. So a member a consumer has never heard of does not fail there. It
produces a butt cap, and the caller is told nothing.

Three members were doing exactly that when this was measured, and the reason none had been
noticed is that a butt cap is a perfectly good solid:

* `SPHERE` is documented as a synonym of `ROUND` and is one on the sweep path, which domes both
  ends. On both strokes it fell through to flat.
* `CIRCLE` refuses on the sweep path and on the 3-D stroke -- it is genuinely unbuilt -- but the
  2-D stroke had it in the list of types that need no decorative polygon, so it flattened.

The measurement that found them is the one below, and it is the point of the file: compare each
member against `BUTT` on the same input. A cap that is doing anything at all changes the bounds.
One that does not is either flat on purpose (`NONE`, `BUTT`) or a silent fall-through, and the
only other acceptable answer is a refusal that names the member.

This is a ratchet in the same sense as the parity budgets: a new `CapType` member, or a new
consumer, has to be handled or refused in each of the three, and cannot be added silently.
"""

from __future__ import annotations

import math
from typing import Callable

import pytest

from pybosl2._backend import use_backend
from pybosl2.caps import CapType
from pybosl2.exceptions import Bosl2NotImplementedError
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D

#: Members that are flat by definition -- the only ones allowed to match `BUTT`.
LEGITIMATELY_FLAT = frozenset({CapType.NONE, CapType.BUTT})

#: Members no consumer builds yet. Each must raise, in every consumer, naming itself.
#: `CIRCLE` is a round-over cap: the swept rim filleted rather than domed, which is a distinct
#: shape from `ROUND` and unbuilt on both backends. Shrinking this set is the work; growing it
#: is not, and the count below is the ratchet that says so.
UNBUILT = frozenset({CapType.CIRCLE})

#: Flat annotation markers whose profile is a bare line. The 3-D consumers revolve a cap profile
#: about the path axis, and a line revolved is a disc -- so these build in 2-D and refuse in 3-D.
#: They were the guard's own find: it was written for `SPHERE` and `CIRCLE`, and turned up two
#: more members producing bounds identical to `BUTT` in all six components.
TWO_D_ONLY = frozenset({CapType.LINE, CapType.X})

#: `CUSTOM` carries its own polygon and cannot be exercised from the enum member alone.
NEEDS_A_PATH = frozenset({CapType.CUSTOM})


def _may_refuse(cap: CapType, consumer: str) -> bool:
    """Whether *cap* is allowed to refuse in *consumer* -- and required to build otherwise."""
    return cap in UNBUILT or (cap in TWO_D_ONLY and consumer != "stroke2d")


CASES = sorted(set(CapType) - NEEDS_A_PATH, key=lambda c: c.name)


def _sweep_extent(cap: CapType) -> tuple[float, float]:
    spine = Path3D([[0, 0, 0], [0, 0, 20]], closed=False)
    ring = [[5 * math.cos(t), 5 * math.sin(t)] for t in [i * 2 * math.pi / 24 for i in range(24)]]
    b = spine.path_sweep(Path2D(ring, closed=True), caps=cap).bounds()
    return (b.min_z, b.max_z)


def _stroke3d_extent(cap: CapType) -> tuple[float, float]:
    b = Path3D([[0, 0, 0], [0, 0, 20]], closed=False).stroke(width=4, endcaps=cap).bounds()
    return (b.min_z, b.max_z)


def _stroke2d_extent(cap: CapType) -> tuple[float, float]:
    b = Path2D([[0, 0], [20, 0]], closed=False).stroke(width=4, endcap1=cap, endcap2=cap).bounds()
    return (b.min_x, b.max_x)


CONSUMERS: dict[str, Callable[[CapType], tuple[float, float]]] = {
    "sweep": _sweep_extent,
    "stroke3d": _stroke3d_extent,
    "stroke2d": _stroke2d_extent,
}


@pytest.mark.parametrize("consumer", sorted(CONSUMERS))
@pytest.mark.parametrize("cap", CASES, ids=lambda c: c.name)
def test_a_cap_changes_the_shape_or_refuses_by_name(cap: CapType, consumer: str) -> None:
    """SPEC G-8: no cap type falls through to a flat end without saying so."""
    measure = CONSUMERS[consumer]
    refusal: Bosl2NotImplementedError | None = None
    got: tuple[float, float] | None = None
    with use_backend("csg"):
        flat = measure(CapType.BUTT)
        try:
            got = measure(cap)
        except Bosl2NotImplementedError as exc:
            refusal = exc

    if refusal is not None:
        assert _may_refuse(cap, consumer), f"{cap.name} refuses on {consumer} and is not listed as unbuildable there"
        # `CapType.NAME`, not the bare name or value. A negative control that stripped the member
        # from the message still passed the looser test: `CapType.X`'s value is "x", which occurs
        # in almost any sentence, and `LINE`'s "line" occurs in its own refusal's reasoning.
        message = str(refusal)
        assert f"CapType.{cap.name}" in message, f"{consumer}: the refusal does not name CapType.{cap.name}: {message}"
        return

    assert not _may_refuse(cap, consumer), (
        f"{cap.name} is listed as unbuildable on {consumer} but built there -- take it off the list"
    )
    if cap in LEGITIMATELY_FLAT:
        assert got == pytest.approx(flat), f"{cap.name} should be flat on {consumer}, got {got} vs {flat}"
        return
    assert got != pytest.approx(flat), (
        f"{cap.name} on {consumer} produced the same bounds as BUTT ({got}) -- it fell through to "
        f"a flat end instead of being built or refused."
    )


def test_sphere_is_the_synonym_of_round_it_is_documented_as() -> None:
    """SPEC G-8: `CapType.ROUND` / `SPHERE` are one cap, so they must measure as one.

    The test above catches SPHERE coming out flat; it does not catch SPHERE coming out as some
    third thing. `CapType`'s own docstring pairs them on one line, which is a promise about the
    geometry and not just about the names.
    """
    with use_backend("csg"):
        for consumer, measure in sorted(CONSUMERS.items()):
            assert measure(CapType.SPHERE) == pytest.approx(measure(CapType.ROUND)), (
                f"{consumer}: SPHERE and ROUND are documented as one cap but measure differently"
            )


def test_the_unbuildable_sets_only_shrink() -> None:
    """SPEC G-8: a new cap type may not join either list to avoid being built or refused."""
    assert len(UNBUILT) <= 1, f"{sorted(c.name for c in UNBUILT)} -- the unbuilt set only shrinks"
    assert len(TWO_D_ONLY) <= 2, f"{sorted(c.name for c in TWO_D_ONLY)} -- the 2-D-only set only shrinks"
    assert not (UNBUILT & TWO_D_ONLY), "a cap cannot be both wholly unbuilt and 2-D-only"
