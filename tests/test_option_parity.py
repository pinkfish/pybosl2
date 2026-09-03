# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Parity is measured per option, not just per shape (SPEC PAR-4).

`tests/test_backend_matrix.py` builds the same *shapes* on both backends and that has always
passed. PAR-4 asks for more: if the CSG cuboid takes `rounding`, `chamfer`, `edges` and
`except_edges`, the SDF cuboid takes the same ones. Nothing walked the two constructors' parameter
lists and compared them until T39, and there are **176** options one backend has and the other does
not.

Two things this separates, because they are different defects:

* **A missing option** is honest parity debt. A caller who passes it gets
  `UnsupportedByBackendError` naming the parameter (B-9), which is the right answer while it is
  missing. Ratcheted per shape below; the number only goes down.
* **A missing *translation*** is not. Where a backend spells the same option differently, PAR-4
  says the difference lives in one central table -- and a name absent from that table reaches the
  refusal and comes back as "the sdf backend cannot do this", which is false when it can and
  merely calls it something else. `tube(outer_radius1=8)` built on CSG and refused on SDF until
  T39, whose `outer_r1` is the same option. That half has no budget.
"""

from __future__ import annotations

import inspect

import pytest

from pybosl2._csg import CsgBackend
from pybosl2.sdf import SdfBackend

#: Controls that describe *tessellation* rather than shape. SPEC B-9 already says a backend with no
#: facets is not missing a feature when it cannot honour these, so they are not a parity gap.
TESSELLATION = frozenset({"fn", "fa", "fs", "res", "realign", "circumscribe"})

#: How many options the SDF backend lacks, per shape. Honest parity debt: each is refused with the
#: parameter named (B-9) rather than silently dropped. Only shrinks.
OPTION_GAPS: dict[str, int] = {
    "cube": 9,
    "cuboid": 6,
    "cyl": 18,
    "cylinder": 25,
    "octahedron": 2,
    "onion": 2,
    "pie_slice": 3,
    "prismoid": 9,
    "rect_tube": 18,
    "regular_prism": 4,
    "sphere": 2,
    "spheroid": 2,
    "teardrop": 7,
    "torus": 3,
    "tube": 3,
    "wedge": 3,
    "xcyl": 20,
    "ycyl": 20,
    "zcyl": 20,
}


def _facade_shapes() -> list[str]:
    """Every shape the façade offers that both backends claim to build."""
    import pybosl2.solid as facade

    return sorted(n for n in facade.__all__ if callable(getattr(facade, n, None)))


def _options(backend: object, shape: str) -> set[str] | None:
    """Return the options a backend's constructor for *shape* declares, or None if it has none."""
    try:
        constructor = backend.constructor(shape)  # type: ignore[attr-defined]
    except Exception:
        return None
    return set(inspect.signature(constructor).parameters) - TESSELLATION - {"self"}


def _gaps() -> dict[str, list[str]]:
    """Return, per shape, the options CSG takes that SDF has no spelling for."""
    csg, sdf = CsgBackend(), SdfBackend()
    own = SdfBackend._OWN_NAMES
    out: dict[str, list[str]] = {}
    for shape in _facade_shapes():
        c, s = _options(csg, shape), _options(sdf, shape)
        if c is None or s is None:
            continue
        missing = sorted(name for name in c - s if own.get(name, name) not in s)
        if missing:
            out[shape] = missing
    return out


GAPS = _gaps()


def test_both_backends_were_actually_compared() -> None:
    """A comparison that found no shared shapes would make the checks below vacuous."""
    csg, sdf = CsgBackend(), SdfBackend()
    shared = [s for s in _facade_shapes() if _options(csg, s) and _options(sdf, s)]
    assert len(shared) > 15, f"only {len(shared)} shapes are built by both backends"


@pytest.mark.parametrize("shape", sorted(set(GAPS) | set(OPTION_GAPS)))
def test_no_shape_grows_its_option_gap(shape: str) -> None:
    """SPEC PAR-4: the two backends' option sets converge, never diverge."""
    actual, budget = len(GAPS.get(shape, [])), OPTION_GAPS.get(shape, 0)
    if actual > budget:
        pytest.fail(
            f"{shape}: the SDF backend lacks {actual} of the CSG options, budget {budget}. "
            f"New: {sorted(set(GAPS[shape]))[:5]}. Implement it on both backends, or add the "
            f"spelling to SdfBackend._OWN_NAMES if it is the same option by another name (PAR-4)."
        )
    if actual < budget:
        pytest.fail(f"{shape} is down to {actual} from {budget}; lower its entry in OPTION_GAPS.")


def test_the_budget_names_no_shape_that_is_gone() -> None:
    """A row for a shape neither backend builds makes the debt look larger than it is."""
    shapes = set(_facade_shapes())
    assert not set(OPTION_GAPS) - shapes, (
        f"OPTION_GAPS names shapes the façade does not offer: {sorted(set(OPTION_GAPS) - shapes)}"
    )


def test_no_option_is_refused_that_is_only_spelled_differently() -> None:
    """PAR-4's other half, which has no budget: a rename is not a capability gap.

    A near-synonym pair -- `outer_radius1` against `outer_r1`, `sides` against `num_sides` -- means
    both backends can do the thing and disagree about its name. Left out of the translation table
    it surfaces as `UnsupportedByBackendError`, telling the caller the backend cannot do something
    it can. The heuristic is deliberately narrow: two names count as the same option when one is an
    abbreviation of the other formed by dropping whole words or vowels.
    """

    def looks_like(a: str, b: str) -> bool:
        """Whether *b* reads as an abbreviation of *a* (or the reverse)."""
        short, long = sorted((a, b), key=len)
        if short == long:
            return False
        # `outer_radius1` -> `outer_r1`: same first and last character of every underscore part.
        parts_long, parts_short = long.split("_"), short.split("_")
        if len(parts_long) == len(parts_short):
            return all(p.startswith(q[0]) and p[-1] == q[-1] for p, q in zip(parts_long, parts_short, strict=True))
        # `inner_diameter1` -> `id1`: initials of the words, plus any trailing digits.
        initials = "".join(p[0] for p in parts_long) + "".join(c for c in parts_long[-1] if c.isdigit())
        return initials == short

    csg, sdf = CsgBackend(), SdfBackend()
    own = SdfBackend._OWN_NAMES
    untranslated: list[str] = []
    for shape in _facade_shapes():
        c, s = _options(csg, shape), _options(sdf, shape)
        if c is None or s is None:
            continue
        for missing in sorted(c - s):
            if own.get(missing, missing) in s:
                continue
            for candidate in sorted(s - c):
                if looks_like(missing, candidate):
                    untranslated.append(f"{shape}: {missing!r} (csg) is {candidate!r} (sdf)")
    assert not untranslated, (
        "the same option under two names, with no entry in SdfBackend._OWN_NAMES (SPEC PAR-4, "
        "PLAN B-P2). The caller is told the backend cannot do something it can:\n  " + "\n  ".join(untranslated)
    )
