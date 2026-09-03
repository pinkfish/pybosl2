# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Parity is measured per option, not just per shape (SPEC PAR-4).

`tests/test_backend_matrix.py` builds the same *shapes* on both backends and that has always
passed. PAR-4 asks for more: if the CSG cuboid takes `rounding`, `chamfer`, `edges` and
`except_edges`, the SDF cuboid takes the same ones. Nothing walked the two constructors' parameter
lists and compared them until T39, which found **176** options one backend has and the other does
not. T40 closed 63 of them, and what it closed says more than the count: none of the 63 needed a
distance field anyone had to invent.

* 38 were `spin` and `orient`, missing from *every* SDF constructor. A rotation about Z and a
  rotation of +Z onto a direction are exact in a field; they had simply never been written.
* 11 were `center`, which is not a shape option at all -- it is `anchor` spelled as a boolean.
* 14 were pure forwarding: `cube` is `cuboid`, and `cylinder` and `zcyl` are `cyl`, on both
  backends -- but the SDF aliases each kept their own field and so quietly lacked the rim
  treatments and the `shift` the thing they alias had built all along.

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
    "cube": 2,
    "cuboid": 4,
    "cyl": 16,
    "cylinder": 16,
    "prismoid": 6,
    "rect_tube": 15,
    "regular_prism": 1,
    "teardrop": 5,
    "xcyl": 16,
    "ycyl": 16,
    "zcyl": 16,
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


#: Shapes whose cross-section is a disc, so a spin about Z cannot change the geometry -- and the
#: SDF bound grows anyway. `PyShape.rotate` recomputes the bound as the axis-aligned box of the
#: rotated *corner box*, which is exact for a cuboid and loose for a disc: `sphere(spin=30)`
#: reports 27.3 across where it is still 20. The field is unchanged (rotating `|p| - r` gives back
#: `|p| - r`); it is the stored box that is conservative. Pre-existing in `rotate`, and reachable
#: only now that spin reaches these shapes (SPEC S-2b, recorded in §12.2).
ROUND_ABOUT_Z = frozenset({"sphere", "spheroid", "cyl", "cylinder", "zcyl", "tube", "onion", "torus"})


@pytest.mark.parametrize(
    ("shape", "kwargs"),
    [
        ("cuboid", {"size": [40, 20, 10]}),
        ("cube", {"size": 20}),
        ("prismoid", {"size1": [20, 20], "size2": [10, 10], "height": 10}),
        ("wedge", {"size": [20, 10, 10]}),
        ("cyl", {"height": 20, "radius": 5}),
        ("sphere", {"radius": 10}),
    ],
)
def test_spin_and_orient_place_the_same_on_both_backends(shape: str, kwargs: dict[str, object]) -> None:
    """SPEC PAR-4 and PAR-5: the same options, and the same result from them.

    `spin` and `orient` were missing from every SDF constructor -- 38 of the 176 gaps -- and
    nothing about a distance field made them hard. They are a rotation about Z and a rotation of
    +Z onto a direction, which a field expresses exactly; they had simply never been written.

    A shape that is round about Z is compared on `orient` only: its *geometry* matches, but the
    SDF box grows under a spin that cannot move it (see `ROUND_ABOUT_Z`).
    """
    from pybosl2 import Anchor, use_backend
    from pybosl2 import solid as facade

    placements: list[dict[str, object]] = [{"orient": Anchor.RIGHT}]
    if shape not in ROUND_ABOUT_Z:
        placements += [{"spin": 45}, {"spin": 30, "orient": Anchor.BACK}]
    for placement in placements:
        sizes = {}
        for backend in ("csg", "sdf"):
            with use_backend(backend):
                sizes[backend] = [round(v, 1) for v in getattr(facade, shape)(**kwargs, **placement).bounds().size]
        assert sizes["csg"] == pytest.approx(sizes["sdf"], abs=0.2), f"{shape} {placement}: {sizes}"


def test_a_spin_about_z_leaves_a_round_shape_where_it_was() -> None:
    """The geometry is right even where the reported box is not -- and the box is what is wrong.

    Kept as a live record of the defect in §12.2: if a shape stops reporting a looser box after a
    spin, it comes off `ROUND_ABOUT_Z` rather than sitting there as a stale excuse.
    """
    from pybosl2 import solid as facade
    from pybosl2 import use_backend

    with use_backend("sdf"):
        plain = facade.sphere(radius=10).bounds().size
        spun = facade.sphere(radius=10, spin=30).bounds().size
    assert plain[0] == pytest.approx(20.0, abs=0.2)
    assert spun[0] > plain[0], (
        "the SDF bound is no longer conservative after a spin -- delete ROUND_ABOUT_Z, this test, "
        "and the §12.2 row that records it"
    )


@pytest.mark.parametrize(
    ("shape", "kwargs"),
    [
        ("cube", {"size": 10}),
        ("prismoid", {"size1": [20, 20], "size2": [10, 10], "height": 10}),
        ("wedge", {"size": [20, 10, 10]}),
        ("rect_tube", {"height": 10, "size": 20, "wall": 2}),
        ("tube", {"height": 10, "outer_radius": 8, "inner_radius": 4}),
        ("torus", {"outer_radius": 10, "inner_radius": 4}),
        ("xcyl", {"height": 10, "radius": 5}),
        ("ycyl", {"height": 10, "radius": 5}),
        ("zcyl", {"height": 10, "radius": 5}),
    ],
)
def test_center_places_the_same_on_both_backends(shape: str, kwargs: dict[str, object]) -> None:
    """`center=` is `anchor=` wearing a boolean, and it means the same thing on either backend.

    Eleven of the 176 gaps were this one option. It is not geometry: True is CENTER and False is
    whatever this shape sits on -- BOTTOM for the cylinders, BOTTOM_FRONT_LEFT for the boxes --
    and `pybosl2.groups.resolve_center_anchor` is the single place that says so.
    """
    from pybosl2 import solid as facade
    from pybosl2 import use_backend

    for centred in (True, False):
        placed = {}
        for backend in ("csg", "sdf"):
            with use_backend(backend):
                box = getattr(facade, shape)(**kwargs, center=centred).bounds()
                placed[backend] = [round(v, 1) for v in box.center]
        assert placed["csg"] == pytest.approx(placed["sdf"], abs=0.1), f"{shape} center={centred}: {placed}"


@pytest.mark.parametrize("shape", ["cyl", "cylinder", "zcyl", "xcyl", "ycyl"])
@pytest.mark.parametrize("shift", [[3, 0], [0, 3], [2, -1], [-4, 2]])
def test_an_oblique_cylinder_leans_the_same_way_on_both_backends(shape: str, shift: list[float]) -> None:
    """SPEC PAR-5. Two defects lived here, and a symmetric test case would have hidden both.

    `shift` is the offset of the far end's centre *relative to the near one*, and the shear is
    taken about the mid-plane -- the CSG backend's shear matrix is `x' = x + shift_x * z / length`
    on a cylinder spanning `z = -h/2 .. h/2`. The SDF backend measured its interpolation from the
    bottom face instead, so it built the same lean half a shift away from where CSG built it, and
    then reported a box widened by the whole shift at *both* ends when each end carries its own
    radius: a 13-wide box for a solid 10 wide.

    Every case here is asymmetric on purpose. `_AXIS_LEAN` carries `shift` through the rotation
    that turns a `cyl` into an `xcyl`, and its first version had every sign inverted -- which
    `shift=[3, 3]` on a symmetric cone would have passed.
    """
    from pybosl2 import solid as facade
    from pybosl2 import use_backend

    boxes = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            box = getattr(facade, shape)(height=10, radius1=5, radius2=2, shift=shift).bounds()
            boxes[backend] = [round(v, 1) for v in (*box.size, *box.center)]
    assert boxes["csg"] == pytest.approx(boxes["sdf"], abs=0.15), f"{shape} shift={shift}: {boxes}"


def test_an_alias_offers_everything_the_shape_it_aliases_does() -> None:
    """`cube` is `cuboid`; `cylinder` and `zcyl` are `cyl`. An alias that drops options is a gap.

    This is how 14 of the 176 arose: each SDF alias had grown its own field rather than calling
    the thing it aliases, so `cylinder(rounding=1)` came back "the sdf backend cannot do this"
    while `cyl(rounding=1)` built it. The refusal was false, which is the half of PAR-4 that has
    no budget.
    """
    import inspect

    from pybosl2.sdf import shapes3d

    for alias, aliased in (("cube", "cuboid"), ("cylinder", "cyl"), ("zcyl", "cyl")):
        offered = set(inspect.signature(getattr(shapes3d, alias)).parameters)
        available = set(inspect.signature(getattr(shapes3d, aliased)).parameters)
        missing = available - offered - {"center", "size1", "size2"}
        assert not missing, f"sdf.{alias} drops what sdf.{aliased} builds: {sorted(missing)}"


def test_the_oblique_shear_is_taken_about_the_mid_plane() -> None:
    """The half of the `shift` defect a bounds comparison cannot see (SPEC PAR-5).

    An SDF shape's `bounds()` is the box it *declares*, not a measurement of its field, so a shear
    applied from the wrong plane moves the geometry and leaves the reported box untouched --
    `test_an_oblique_cylinder_leans_the_same_way_on_both_backends` passes with this defect put
    back. This one asks the field where the material is.

    `shift` is the far end's offset relative to the near one, and CSG takes the shear about the
    mid-plane: the section centre at height *z* is `shift * z / length`, so for a 10-tall cone
    with `shift=[6, 0]` the bottom disc sits at x=-3 (radius 5, spanning -8..2) and the top at
    x=+3 (radius 2, spanning 1..5). Measuring the interpolation from the bottom face instead
    leaves the bottom at x=0 and puts the top at x=+6 -- the same lean, three units across from
    where the CSG backend builds it.
    """
    from pybosl2.sdf import shapes3d as sdf

    field = sdf.cyl(height=10, radius1=5, radius2=2, shift=[6, 0]).mesh()
    # Bottom disc: centred x=-3, radius 5. Sharpest discriminator -- the two conventions put its
    # centre three units apart, and its radius is large enough that both probes land inside one
    # of them and outside the other.
    assert float(field.sample(-7.0, 0.0, -4.9)) < 0, "the bottom disc has not slid to -shift/2"
    assert float(field.sample(4.0, 0.0, -4.9)) > 0, "the bottom disc is still centred on the axis"
    # Top disc: centred x=+3, radius 2.
    assert float(field.sample(3.0, 0.0, 4.9)) < 0, "the top disc is not at +shift/2"
    assert float(field.sample(6.0, 0.0, 4.9)) > 0, "the top disc has slid the whole shift"


def test_the_design_note_states_the_measured_gap() -> None:
    """`docs/design/sdf-csg-compatibility.md` names a number, so something has to keep it true.

    That file's own preamble records having drifted into fiction twice, and it warns the reader
    off trusting it. A figure written into it is a claim (SPEC B2-1), and this is the thing that
    makes this one true: the same pattern `test_the_measured_coverage_matches_what_the_spec_claims`
    uses for §12.2's parts count.
    """
    import pathlib

    note = (pathlib.Path(__file__).resolve().parent.parent / "docs" / "design" / "sdf-csg-compatibility.md").read_text()
    total = sum(len(options) for options in GAPS.values())
    assert f"{total} options one backend takes and the other does not" in note, (
        f"the design note does not state the measured figure, which is {total} options across {len(GAPS)} shapes"
    )
