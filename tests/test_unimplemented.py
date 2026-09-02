# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""What the signatures advertise and the port does not build (SPEC E-1, E-2, G-8).

A parameter in a public signature is a promise. Four of them were not kept -- `cyl(texture=...)`,
`cuboid(teardrop=...)`, `CapType.CIRCLE` and `VNF.from_field` with a range -- and each raised a
bare `NotImplementedError`, which is neither a `Bosl2Error` (so `except Bosl2Error` missed it) nor
a refusal that names an alternative (E-2).

`texture=` is the one that matters most: SPEC S-34 and S-35 specify textures as a working
subsystem, the registry *is* built (`texture("diamonds")` returns its tile), and thirteen public
constructors take the five texture parameters. It was found while trying to build a `Texturing`
argument group for those five (T30) -- there is no point grouping parameters no call can honour.

So the gaps are named here, and the list only shrinks.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from pybosl2.exceptions import Bosl2Error, Bosl2NotImplementedError

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "pybosl2"

#: Public capabilities this port advertises and does not build. Each entry is where the refusal
#: lives. Building one removes its row; nothing may be added without a spec item saying why.
KNOWN_GAPS: frozenset[str] = frozenset(
    {
        "caps.py::endcap_polys",  # CapType.CIRCLE
        "shapes3d/cuboid.py::cuboid",  # teardrop=
        "shapes3d/cylinder.py::cyl",  # texture= and its four companions (SPEC S-34, S-35)
        "vnf.py::from_field",  # tuple (lo, hi) isovalue ranges
    }
)


def _public_refusals() -> dict[str, list[str]]:
    """Return, per public callable, the `NotImplementedError`-family raises it contains.

    An abstract-method stub -- a bare ``raise NotImplementedError`` with no message, in a private
    or base-class method -- is not an advertised gap and is not counted.
    """
    found: dict[str, list[str]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).as_posix()
        for function in ast.walk(ast.parse(path.read_text())):
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if function.name.startswith("_"):
                continue
            for node in ast.walk(function):
                if not isinstance(node, ast.Raise) or node.exc is None:
                    continue
                raised = ast.unparse(node.exc)
                if not raised.startswith(("NotImplementedError", "Bosl2NotImplementedError")):
                    continue
                if raised.strip() == "NotImplementedError":
                    continue  # an abstract stub, not an advertised gap
                found.setdefault(f"{relative}::{function.name}", []).append(raised)
    return found


REFUSALS = _public_refusals()


def test_the_scan_found_the_refusals() -> None:
    """A scan matching nothing would make everything below vacuous."""
    assert REFUSALS, "no public NotImplementedError refusals found; the scan is broken"


@pytest.mark.parametrize("where", sorted(REFUSALS))
def test_every_advertised_gap_is_known(where: str) -> None:
    """A new unbuilt parameter is a promise the signature makes and the code breaks."""
    assert where in KNOWN_GAPS, (
        f"{where} raises NotImplementedError for something its signature advertises, and is not "
        f"in KNOWN_GAPS. Either build it, or add it with a spec item saying why it is advertised "
        f"and unbuilt."
    )


@pytest.mark.parametrize("where", sorted(REFUSALS))
def test_every_gap_refuses_as_a_library_error(where: str) -> None:
    """SPEC E-1: `except Bosl2Error` catches the family, gaps included."""
    for raised in REFUSALS[where]:
        assert raised.startswith("Bosl2NotImplementedError"), (
            f"{where} raises a bare NotImplementedError, which `except Bosl2Error` does not "
            f"catch (SPEC E-1). Raise Bosl2NotImplementedError, which is both."
        )


def test_the_gap_list_is_not_stale() -> None:
    """A row for a gap that has been built makes the debt look worse than it is."""
    stale = sorted(KNOWN_GAPS - set(REFUSALS))
    assert not stale, f"KNOWN_GAPS names callables that no longer refuse: {stale}"


def test_the_refusal_is_both_bases_and_names_a_way_forward() -> None:
    """SPEC E-1 and E-2, exercised rather than read off the class statement."""
    from pybosl2 import cyl

    with pytest.raises(Bosl2NotImplementedError) as caught:
        cyl(height=20, radius=10, texture="diamonds")
    error = caught.value
    assert isinstance(error, Bosl2Error), "except Bosl2Error must catch it (E-1)"
    assert isinstance(error, NotImplementedError), "callers catching the stdlib type still work"
    assert "texture(" in str(error), "the refusal must name what does work (E-2)"


def test_the_texture_registry_works_even_though_the_parameter_does_not() -> None:
    """The half that is built, so the refusal's advice is not a dead end (SPEC S-34)."""
    from pybosl2 import texture

    assert texture("diamonds"), "the named-texture registry should return a tile"
