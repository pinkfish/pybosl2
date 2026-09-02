# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Argument groups: the parameters that travel together, as one value (SPEC G-1 … G-5)."""

from __future__ import annotations

import pytest

from pybosl2 import Anchor, Facets, Placement, cuboid, cyl, use_defaults
from pybosl2.defaults import resolve_facets, resolve_res
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.groups import resolve_placement


class TestPlacement:
    """A placement is anchor, spin and orient as one reusable value."""

    def test_a_placement_places_the_shape_where_the_loose_arguments_would(self) -> None:
        """The group is a spelling, not a second behaviour."""
        grouped = cuboid([60, 40, 8], placement=Placement(anchor=Anchor.BOTTOM))
        loose = cuboid([60, 40, 8], anchor=Anchor.BOTTOM)
        assert grouped.bounds().min == loose.bounds().min
        assert grouped.bounds().size == pytest.approx([60.0, 40.0, 8.0])
        assert grouped.bounds().min[2] == pytest.approx(0.0)

    def test_one_placement_serves_several_shapes(self) -> None:
        """The point of the group: build it once, pass it to everything."""
        upright = Placement(anchor=Anchor.BOTTOM)
        plate = cuboid([60, 40, 8], placement=upright)
        boss = cyl(height=10, radius=4, placement=upright)
        assert plate.bounds().min[2] == pytest.approx(0.0)
        assert boss.bounds().min[2] == pytest.approx(0.0)

    def test_a_group_and_its_own_member_together_are_refused(self) -> None:
        """SPEC G-3, mirroring D-5: the call cannot mean two things at once."""
        with pytest.raises(Bosl2ValueError, match=r"placement= and anchor="):
            cuboid([10, 10, 10], placement=Placement(anchor=Anchor.BOTTOM), anchor=Anchor.TOP)

    def test_the_loose_spelling_still_works_untouched(self) -> None:
        """SPEC G-3: the common case stays the short one."""
        assert cuboid([10, 10, 10], anchor=Anchor.BOTTOM).bounds().min[2] == pytest.approx(0.0)

    def test_with_returns_a_new_placement(self) -> None:
        """Frozen: composing one leaves the original alone."""
        base = Placement(anchor=Anchor.BOTTOM)
        spun = base.with_(spin=45)
        assert spun.spin == pytest.approx(45.0)
        assert base.spin == pytest.approx(0.0)
        assert spun.anchor is Anchor.BOTTOM

    def test_the_defaults_are_the_common_case(self) -> None:
        """SPEC P-2, and what makes `placement=Placement()` a no-op."""
        assert Placement().as_kwargs() == {"anchor": Anchor.CENTER, "spin": 0.0, "orient": Anchor.TOP}

    def test_resolve_placement_passes_the_loose_values_through(self) -> None:
        """With no group, the loose arguments are returned unchanged."""
        assert resolve_placement(None, Anchor.TOP, 30, Anchor.LEFT, "f") == (Anchor.TOP, 30, Anchor.LEFT)


class TestFacets:
    """The resolution controls, carried as one value down the plumbing (SPEC R-1)."""

    def test_ambient_values_are_picked_up(self) -> None:
        """`use_defaults` remains the way a caller sets resolution (SPEC R-4)."""
        with use_defaults(fn=64):
            assert Facets.resolved().fn == 64

    def test_an_explicit_value_beats_the_ambient_one(self) -> None:
        """SPEC R-5."""
        with use_defaults(fn=64):
            assert Facets.resolved(fn=12).fn == 12

    def test_fn_zero_passes_through_as_the_opt_out(self) -> None:
        """SPEC R-5: `fn=0` means "ignore the ambient fn", not "zero facets"."""
        with use_defaults(fn=64):
            assert Facets.resolved(fn=0).fn == 0

    def test_as_kwargs_omits_what_is_unset(self) -> None:
        """So a group can be splatted into a callee that declares only some of the four."""
        assert Facets(fn=64).as_kwargs() == {"fn": 64}
        assert Facets().as_kwargs() == {}

    def test_both_resolvers_go_through_the_one_rule(self) -> None:
        """`resolve_facets` and `resolve_res` were two implementations of one rule (SPEC R-1)."""
        with use_defaults(fn=32, fa=6, fs=1, res=20):
            assert resolve_facets(fa=3) == (32, 3, 1)
            assert resolve_res() == 20
            resolved = Facets.resolved(fa=3)
            assert (resolved.fn, resolved.fa, resolved.fs) == resolve_facets(fa=3)
            assert resolved.res == resolve_res()

    def test_merge_lets_the_caller_win(self) -> None:
        """The direction matters: ambient.merge(caller), never the other way round."""
        assert Facets(fn=8).merge(Facets(fn=64)).fn == 64
        assert Facets(fn=8).merge(Facets(fa=2)).fn == 8

    def test_geometry_follows_the_ambient_default_through_the_group(self) -> None:
        """The plumbing is only worth anything if it reaches the geometry (PLAN X-8)."""
        with use_defaults(fn=6):
            coarse = cyl(height=10, radius=5)
        with use_defaults(fn=64):
            smooth = cyl(height=10, radius=5)
        assert len(coarse.vnf().vertices) == 12  # 6 facets, two rings
        assert len(smooth.vnf().vertices) > len(coarse.vnf().vertices)
