# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A call that type-checks on one backend type-checks on the other.

SPEC PAR-1, C-10; PLAN O-6b. Option parity reached zero in T63 -- every option one backend takes,
the other takes too. That was measured by *calling*, and calling is not the whole contract: a
signature is also a promise to the type checker, and the two backends can agree at runtime while
disagreeing about what they accept.

They did. Twenty-four SDF constructors declared `anchor: Sequence[float]` -- a plain vector, which
PLAN O-6b names explicitly as the thing an anchor must not be -- and the annotation was **false**.
Those functions accept an `Anchor` and always have; `sdf.cuboid([20,20,20], anchor=Anchor.TOP)`
builds exactly what the vector spelling builds. So the defect was invisible to every runtime test
in this repository and reached the user as::

    error: Argument "anchor" to "cuboid" has incompatible type "Anchor";
           expected "Sequence[float]"  [arg-type]

on code that runs. `orient` in the very same signatures was already `Anchor | Sequence[float]`,
which is what makes this an oversight rather than a decision.

This runs `mypy --strict` over calls written the way the documentation writes them, against both
spellings, so a divergence in the *type* surface fails the way a divergence in the option surface
already does. It is the same instrument `tests/test_docstring_examples.py` uses on the examples --
type-checking user code rather than reading the signature -- pointed at the backend pair.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Calls written as a user writes them, in both spellings. Each must type-check on both sides;
#: what is being compared is the *pair*, so a row that is wrong in the same way twice still fails
#: the moment either one is corrected.
PAIRS = [
    ("cuboid anchor", "cuboid([20, 20, 20], anchor=Anchor.TOP)"),
    ("cuboid orient", "cuboid([20, 20, 20], orient=Anchor.RIGHT)"),
    ("sphere anchor", "sphere(radius=10, anchor=Anchor.BOTTOM)"),
    ("cyl anchor", "cyl(length=20, radius=5, anchor=Anchor.TOP)"),
    ("tube anchor", "tube(height=20, outer_radius=10, inner_radius=5, anchor=Anchor.BOTTOM)"),
    ("prismoid anchor", "prismoid([20, 20], [10, 10], height=10, anchor=Anchor.TOP)"),
    ("torus anchor", "torus(major_radius=20, minor_radius=5, anchor=Anchor.TOP)"),
    # Both directions. `cuboid` typed `anchor: Anchor` and `orient: Anchor` on the CSG side --
    # rejecting the *vector* the SDF side accepts, the mirror image of the defect above, and alone
    # among every sibling in its own file. The vector builds at runtime on both.
    ("vector anchor still works", "cuboid([20, 20, 20], anchor=[0, 0, 1])"),
    ("vector orient still works", "cuboid([20, 20, 20], orient=[1, 0, 0])"),
]


def _typecheck(source: str) -> str:
    """Run `mypy --strict` over *source* and return its output, empty when clean."""
    scratch = REPO_ROOT / ".mypy_parity_check.py"
    scratch.write_text(source)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--strict", str(scratch)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
    finally:
        scratch.unlink(missing_ok=True)
    return "" if result.returncode == 0 else result.stdout + result.stderr


@pytest.mark.parametrize(("label", "call"), PAIRS, ids=[label for label, _ in PAIRS])
def test_the_same_call_type_checks_on_both_backends(label: str, call: str) -> None:
    """SPEC PAR-1: parity is a promise to the type checker too, not only to the interpreter."""
    source = textwrap.dedent(f"""
        from pybosl2._edges_lang import Anchor
        import pybosl2.sdf.shapes3d as sdf
        import pybosl2.shapes3d as csg

        sdf.{call}
        csg.{call}
    """)
    complaint = _typecheck(source)
    assert not complaint, f"{label}: the two backends disagree about what they accept\n{complaint}"


def test_the_checker_is_actually_running() -> None:
    """SPEC PAR-1: a harness that always reports clean would pass every row above in silence."""
    assert _typecheck("x: int = 'not an int'\n"), "mypy reported nothing for a certain error"
    assert not _typecheck("x: int = 1\n"), "mypy reported something for correct code"


# --- the sweep (T72) ----------------------------------------------------------------------------

#: Parameters the two spellings may legitimately disagree about, with the reason. A row is a claim
#: that the difference is intended, and has to say why -- not merely record it. Both rows are the
#: SDF side being *wider*, which is the harmless direction: nothing a CSG caller writes is refused.
#: The dangerous direction -- SDF narrower than CSG -- has no rows and may not gain any, because
#: that is an annotation rejecting a call that works, which is the whole of T71 and T72.
DECLARED_DIFFERENCES: dict[str, str] = {
    "texture": "the SDF backend also accepts a TextureData tile; the CSG one takes a name only",
    "data": "heightfield: the SDF field is a callable of libfive trees, not of floats",
}

#: Shared parameters whose annotations still differ, all of them a `| None` the façade normalises
#: before either backend sees it. Measured, not chosen, and it only shrinks.
DIFFERENCE_BUDGET = 20


def _shared_signatures() -> list[tuple[str, str, str, str]]:
    """Every parameter shared by both backends' spelling of the same constructor.

    The rows above are a *sample* -- eight calls chosen by hand, which is how a sample fails: it
    covers what its author thought of. This is the sweep, and it is a different instrument: it
    compares annotations rather than type-checking calls, so it sees every parameter without
    needing a plausible value for each, and it cannot see a signature that is wrong in the same
    way on both sides. The two together are what the pair of guards in `test_signatures.py` is to
    each other.
    """
    import inspect

    import pybosl2.sdf.shapes3d as sdf
    import pybosl2.shapes3d as csg

    def normalise(text: str) -> str:
        for noise in ("'", '"', "pybosl2._edges_lang.", "collections.abc.", "typing."):
            text = text.replace(noise, "")
        return text

    rows: list[tuple[str, str, str, str]] = []
    for name in sorted(dir(sdf)):
        left, right = getattr(sdf, name, None), getattr(csg, name, None)
        if name.startswith("_") or not inspect.isfunction(left) or not callable(right):
            continue
        try:
            a = inspect.signature(left).parameters
            b = inspect.signature(right).parameters
        except (TypeError, ValueError):  # pragma: no cover - a builtin or C callable
            continue
        for parameter in sorted(set(a) & set(b)):
            ta, tb = normalise(str(a[parameter].annotation)), normalise(str(b[parameter].annotation))
            if ta != tb:
                rows.append((name, parameter, ta, tb))
    return rows


SHARED = _shared_signatures()


def test_the_sweep_reaches_the_shared_surface() -> None:
    """A sweep that compared nothing would pass the check below in silence."""
    import inspect

    import pybosl2.sdf.shapes3d as sdf
    import pybosl2.shapes3d as csg

    shared = [
        n
        for n in dir(sdf)
        if not n.startswith("_") and inspect.isfunction(getattr(sdf, n, None)) and callable(getattr(csg, n, None))
    ]
    assert len(shared) > 15, f"only {len(shared)} shared constructors found; the sweep is broken"


def test_no_shared_parameter_differs_in_shape() -> None:
    """SPEC PAR-1: the two spellings may differ in nullability, never in what they accept.

    Thirty-five parameters disagreed when this was measured. The interesting ones were the SDF
    side declaring *less* than it accepts: `prismoid(chamfer=[1,2,1,2])` builds on both backends
    while the SDF annotation said `float | None`, and `cuboid(p1=[0,0,0])` builds on both while
    the CSG annotation said `Point | None` -- `PointLike` is the alias that exists for exactly
    that and was not being used. Each is T71's defect in another parameter family: an annotation
    narrower than the behaviour, which no runtime test can see because the call it rejects works.

    What is allowed through is a `| None` difference, because the façade resolves `None` before
    either backend sees it -- both `cuboid(rounding=None)` and `wedge(anchor=None)` build on both
    backends through `pybosl2.solid`, which is the documented entry point (A-10). Reaching a
    backend module directly with a `None` its signature does not declare is a call mypy already
    refuses, so there the type and the behaviour agree.
    """
    shaped = [
        f"{name}.{parameter}: sdf={left!r} csg={right!r}"
        for name, parameter, left, right in SHARED
        if parameter not in DECLARED_DIFFERENCES and left.replace(" | None", "") != right.replace(" | None", "")
    ]
    assert not shaped, "the backends disagree about what a shared parameter accepts (SPEC PAR-1):\n  " + "\n  ".join(
        shaped
    )


def test_the_nullability_differences_only_shrink() -> None:
    """SPEC PAR-1: a `| None` gap is tolerable and is still a gap, so the count is a ratchet."""
    nullable = [r for r in SHARED if r[1] not in DECLARED_DIFFERENCES]
    assert len(nullable) <= DIFFERENCE_BUDGET, (
        f"{len(nullable)} shared parameters differ, budget {DIFFERENCE_BUDGET}: "
        f"{[f'{n}.{p}' for n, p, _, _ in nullable][:6]}"
    )
    assert len(nullable) == DIFFERENCE_BUDGET, (
        f"down to {len(nullable)} from {DIFFERENCE_BUDGET} -- lower DIFFERENCE_BUDGET to hold it."
    )


def test_every_declared_difference_is_still_real() -> None:
    """SPEC PAR-1: a row excusing a difference that has gone makes the pair look worse than it is."""
    differing = {parameter for _, parameter, _, _ in SHARED}
    stale = sorted(set(DECLARED_DIFFERENCES) - differing)
    assert not stale, f"{stale} no longer differ -- take them out of DECLARED_DIFFERENCES"
