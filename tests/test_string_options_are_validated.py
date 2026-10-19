# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""A string-valued option refuses what it does not understand (SPEC E-4, B2-2).

`strokes` was compared only against `"polygon"`, and every other value fell through to the
`"ignore"` branch. So a typo did not fail -- it silently changed the answer. An SVG holding one
stroked path returns **two** regions with `strokes="polygon"` and **one** with `strokes="polygn"`,
dropping the stroke, with nothing said. Five public entries took the parameter and none validated
it.

B2-2 says enums replace magic strings, and this would be better as one. It stays a `str` here
because the public signatures are the compatibility surface and widening them to an enum is an API
change rather than a fix; what the fix owes is that an unrecognised value refuses by name.

Also in this file: the one `VnfStyle` the package had left. `vnf.py` aliased `VnfStyle = VNFStyle`,
exported **only the alias** in its `__all__`, and annotated one parameter `VNFStyle | VnfStyle` -- a
union of a type with itself, which reads as "either spelling" and means nothing. C-21 asks for one
concept and one name; `nurbs.py` was the only consumer and now imports `VNFStyle` from
`pybosl2.enums`, where every other module gets it.
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from pybosl2.exceptions import Bosl2ValueError

#: One filled-less path with a stroke, so `"polygon"` and `"ignore"` give different answers and a
#: silent fall-through is visible as a missing region rather than as an error.
STROKED_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
    '<path d="M10,10 L90,10 L90,90 L10,90 Z" fill="none" stroke="black" stroke-width="4"/></svg>'
)

#: The modes that exist. A third would need adding here and to `_STROKE_MODES` together.
VALID = ("polygon", "ignore")

#: Values that must refuse: a near-miss typo, an unrelated word, the empty string, and a plausible
#: synonym someone might reach for.
INVALID = ("polygn", "nonsense", "", "fill")


def _svg_file(directory: str) -> str:
    path = pathlib.Path(directory) / "stroked.svg"
    path.write_text(STROKED_SVG)
    return str(path)


def _entries() -> dict[str, object]:
    from pybosl2.regions import Region
    from pybosl2.svg import region_from_svg, regions_from_svg, svg_rings_with_colors

    return {
        "region_from_svg": region_from_svg,
        "regions_from_svg": regions_from_svg,
        "svg_rings_with_colors": svg_rings_with_colors,
        "Region.from_svg": Region.from_svg,
    }


@pytest.mark.parametrize("entry", sorted(_entries()))
@pytest.mark.parametrize("mode", INVALID, ids=lambda m: m or "empty")
def test_an_unknown_stroke_mode_refuses(entry: str, mode: str) -> None:
    """SPEC E-4: the refusal arrives at the call that was wrong, not several frames down."""
    with tempfile.TemporaryDirectory() as directory:
        source = _svg_file(directory)
        with pytest.raises(Bosl2ValueError, match="strokes"):
            _entries()[entry](source, strokes=mode)  # type: ignore[operator]


@pytest.mark.parametrize("entry", sorted(_entries()))
@pytest.mark.parametrize("mode", VALID)
def test_every_valid_stroke_mode_is_accepted(entry: str, mode: str) -> None:
    """And the guard must not refuse what the docstrings offer."""
    with tempfile.TemporaryDirectory() as directory:
        _entries()[entry](_svg_file(directory), strokes=mode)  # type: ignore[operator]


def test_the_two_modes_give_different_answers() -> None:
    """Which is why a silent fall-through mattered: it dropped geometry rather than erring.

    Without this, the refusals above could be satisfied by a guard on a parameter that changes
    nothing -- the case T106 found twice.
    """
    from pybosl2.svg import regions_from_svg

    with tempfile.TemporaryDirectory() as directory:
        source = _svg_file(directory)
        kept = len(list(regions_from_svg(source, strokes="polygon")))
        dropped = len(list(regions_from_svg(source, strokes="ignore")))
    assert kept > dropped, (
        f'strokes="polygon" gives {kept} region(s) and "ignore" {dropped}; the modes no longer '
        f"differ, so a typo falling through to one of them would be harmless and this file moot"
    )


def test_the_vnf_style_enum_has_one_spelling() -> None:
    """SPEC C-21: one concept, one name.

    `vnf.py` aliased `VnfStyle = VNFStyle`, put only the alias in its `__all__`, and annotated a
    parameter `VNFStyle | VnfStyle`. Asserted on the module surface rather than by reading source,
    so re-adding the alias anywhere fails rather than only re-adding it here.
    """
    import pybosl2.vnf as vnf_module

    assert not hasattr(vnf_module, "VnfStyle"), (
        "pybosl2.vnf has a `VnfStyle` again. The canonical spelling is `VNFStyle`, from "
        "`pybosl2.enums`, which is where every module imports it"
    )
