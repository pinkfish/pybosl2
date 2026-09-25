# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Doubling a stroke's width doubles its caps and its joints, and a decorative cap trims the body.

SPEC S-25, a MUST that carried no enforcer until T88. It makes two claims, and one of them already
had a guard under a different name: T65 built `tests/test_stroke_caps_agree.py` to establish that
an arrow's *tip* lands on the point it was given, which is the trimming half stated as a
measurement. That file is wired to this requirement now rather than duplicated.

The scaling half is what was unchecked, and measuring it needed one thing said plainly first: at
the default facet settings the 3-D stroke does **not** scale linearly, and that is not a defect.
A round joint is a faceted sphere, `fa`/`fs` give a larger sphere more facets, and an inscribed
polyhedron sits closer to its ideal as the facet count rises. Measured, the overhang past the path
runs 0.809, 0.832 and 0.971 of `width / 2` at widths 2, 4 and 8 -- converging, not scaling.

Hold the facet count fixed and it is 0.999 at every width. That is the experiment this file runs,
and the distinction it rests on is B-9's: a backend's tessellation is not part of what a shape
promises, so a scaling rule has to be measured with tessellation held still or it measures the
tessellation instead.
"""

from __future__ import annotations

import pytest

from pybosl2 import use_backend, use_defaults
from pybosl2.caps import CapType
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D

#: Fixed, so the adaptive facet count cannot be mistaken for a scaling failure. High enough that a
#: faceted circle is within a thousandth of its ideal at every width tested.
FACETS = 64

WIDTHS = [2.0, 4.0, 8.0]

#: A corner, so the bend is a joint rather than a cap.
CORNER_2D = [[0.0, 0.0], [20.0, 0.0], [20.0, 20.0]]
CORNER_3D = [[0.0, 0.0, 0.0], [20.0, 0.0, 0.0], [20.0, 20.0, 0.0]]


@pytest.mark.parametrize("width", WIDTHS)
def test_a_two_dimensional_joint_is_half_a_width_past_the_corner(width: float) -> None:
    """SPEC S-25: the joint scales with the stroke, so the overhang is always `width / 2`."""
    with use_backend("csg"), use_defaults(fn=FACETS):
        box = Path2D(CORNER_2D, closed=False).stroke(width=width, endcap1=CapType.ROUND, endcap2=CapType.ROUND).bounds()
    assert -float(box.min_x) == pytest.approx(width / 2, rel=0.01)
    assert float(box.max_y) - 20.0 == pytest.approx(width / 2, rel=0.01)


@pytest.mark.parametrize("width", WIDTHS)
def test_a_three_dimensional_joint_scales_once_the_facets_are_held_still(width: float) -> None:
    """SPEC S-25 and B-9: the shape scales; the tessellation is not part of what it promises.

    At the default settings this reads 0.809, 0.832 and 0.971 of `width / 2` -- which looks like a
    scaling defect and is an adaptive facet count, since `fa`/`fs` give a larger sphere more
    facets and an inscribed polyhedron approaches its ideal as they rise. A scaling rule measured
    without fixing that measures the tessellation instead.
    """
    with use_backend("csg"), use_defaults(fn=FACETS):
        box = Path3D(CORNER_3D, closed=False).stroke(width=width, endcaps=CapType.ROUND).bounds()
    assert -float(box.min_x) == pytest.approx(width / 2, rel=0.01)


@pytest.mark.parametrize(
    "cap",
    [CapType.ARROW, CapType.DIAMOND, CapType.DOT, CapType.ROUND, CapType.SQUARE],
    ids=lambda c: c.name,
)
def test_a_cap_doubles_when_the_width_doubles(cap: CapType) -> None:
    """SPEC S-25: cap geometry scales with stroke width, whatever the cap is.

    Measured across the cap's own extent rather than its reach past the end, because a cap that
    added a constant would keep its reach and change its height -- and a cap that scaled only its
    reach would pass a test looking at reach alone.
    """
    line = Path2D([[0.0, 0.0], [20.0, 0.0]], closed=False)
    with use_backend("csg"), use_defaults(fn=FACETS):
        thin = line.stroke(width=2.0, endcap1=cap, endcap2=cap).bounds()
        thick = line.stroke(width=4.0, endcap1=cap, endcap2=cap).bounds()
    assert float(thick.size[1]) == pytest.approx(2 * float(thin.size[1]), rel=0.01), "height"
    thin_reach, thick_reach = float(thin.max_x) - 20.0, float(thick.max_x) - 20.0
    if thin_reach > 1e-9:
        assert thick_reach == pytest.approx(2 * thin_reach, rel=0.02), "reach past the end"


def test_the_trimming_half_of_the_rule_is_guarded_where_it_was_first_measured() -> None:
    """SPEC S-25's second clause, which T65 established before this requirement had an enforcer.

    Not duplicated here. `tests/test_stroke_caps_agree.py` measures it as the thing it is -- an
    arrow's tip landing on the point it was given -- and that file is named in this requirement's
    `enforced_by`. This asserts the guard still exists, so wiring the requirement to it cannot
    quietly become a reference to nothing.
    """
    import pathlib

    source = (pathlib.Path(__file__).resolve().parent / "test_stroke_caps_agree.py").read_text()
    assert "def test_an_arrow_marks_the_point_it_was_given" in source
    assert "endcap_trim" in source, "the trimming guard no longer mentions the mechanism it checks"
