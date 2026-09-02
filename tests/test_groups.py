# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Argument groups: the parameters that travel together, as one value (SPEC G-1 … G-5)."""

from __future__ import annotations

import pytest

from pybosl2 import Anchor, EdgeSelection, EdgeTreatment, Facets, Placement, cuboid, cyl, use_defaults
from pybosl2.defaults import resolve_facets, resolve_res
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.flat import circle, rect, square
from pybosl2.groups import resolve_placement, resolve_placement_2d


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


class TestPlacementInThePlane:
    """A placement reads in two dimensions as well as three (SPEC G-1, E-5)."""

    def test_one_placement_serves_an_outline_and_the_solid_from_it(self) -> None:
        """The case worth having: anchor a 2-D profile and the solid extruded from it alike."""
        upright = Placement(anchor=Anchor.LEFT)
        outline = square([40, 20], placement=upright)
        solid = cuboid([40, 20, 5], placement=upright)
        assert outline.bounds().min[0] == pytest.approx(0.0)
        assert solid.bounds().min[0] == pytest.approx(0.0)

    def test_it_places_the_shape_where_the_loose_arguments_would(self) -> None:
        """The group is a spelling, not a second behaviour."""
        grouped = square([40, 20], placement=Placement(anchor=Anchor.LEFT))
        loose = square([40, 20], anchor=Anchor.LEFT)
        assert grouped.bounds().min == loose.bounds().min

    def test_spin_travels_with_it(self) -> None:
        """Both members the plane can honour, not just the anchor."""
        spun = circle(radius=10, placement=Placement(spin=45))
        assert spun.bounds().size[0] == pytest.approx(19.973, abs=0.05)

    def test_a_placement_that_really_orients_is_refused(self) -> None:
        """SPEC E-5: the plane has no third axis, so dropping the orient would be a silent lie."""
        with pytest.raises(Bosl2ValueError, match="cannot honour"):
            square([10, 10], placement=Placement(orient=Anchor.RIGHT))

    def test_the_default_orient_is_dimension_neutral(self) -> None:
        """`Placement()` and `Placement(anchor=...)` pass anywhere; only a real orient refuses."""
        assert Placement(anchor=Anchor.LEFT).orients() is False
        assert Placement(orient=Anchor.RIGHT).orients() is True
        assert square([10, 10], placement=Placement()).bounds().size == pytest.approx([10.0, 10.0])

    def test_the_group_and_member_conflict_applies_in_two_dimensions_too(self) -> None:
        """SPEC G-3 is not a 3-D-only rule."""
        with pytest.raises(Bosl2ValueError, match=r"placement= and anchor="):
            square([10, 10], placement=Placement(anchor=Anchor.LEFT), anchor=Anchor.TOP)

    def test_resolve_placement_2d_passes_the_loose_values_through(self) -> None:
        """With no group, the loose arguments come back unchanged."""
        assert resolve_placement_2d(None, Anchor.TOP, 30, "f") == (Anchor.TOP, 30)

    def test_text_keeps_its_own_anchor_vocabulary(self) -> None:
        """`text()` anchors on a typographic baseline string, not the anchor language.

        That is an O-6b defect in its own right, and it is why `text()` is the one 2-D façade
        constructor without `placement=`: a placement carries an `Anchor`, and this does not.
        """
        import inspect

        from pybosl2.flat import text

        assert "placement" not in inspect.signature(text).parameters


class TestEdgeTreatment:
    """A rounding or a chamfer, never both, as one value (SPEC G-1, G-7)."""

    def test_a_treatment_rounds_the_way_the_loose_argument_does(self) -> None:
        """The group is a spelling, not a second behaviour."""
        grouped = cuboid([40, 30, 20], treatment=EdgeTreatment.rounding(4))
        loose = cuboid([40, 30, 20], rounding=4)
        assert grouped.bounds().size == loose.bounds().size
        assert grouped.vnf().volume() == pytest.approx(loose.vnf().volume(), rel=1e-6)

    def test_rounding_and_chamfering_are_different_geometry(self) -> None:
        """X-8: assert the content, not that an object came back."""
        rounded = cuboid([40, 30, 20], treatment=EdgeTreatment.rounding(4))
        chamfered = cuboid([40, 30, 20], treatment=EdgeTreatment.chamfer(4))
        assert rounded.vnf().volume() != pytest.approx(chamfered.vnf().volume(), rel=1e-6)

    def test_the_conflict_is_unrepresentable_in_the_group(self) -> None:
        """One kind and one size, so there is nothing for the two to disagree about."""
        assert EdgeTreatment.rounding(4).as_kwargs() == {"rounding": 4.0}
        assert EdgeTreatment.chamfer(4).as_kwargs() == {"chamfer": 4.0}
        assert EdgeTreatment.none().as_kwargs() == {}

    def test_the_loose_pair_is_refused_with_one_message(self) -> None:
        """SPEC G-5: the rule was written six times with six wordings, none naming the fix."""
        with pytest.raises(Bosl2ValueError, match="rounded or chamfered, never both"):
            cuboid([20, 20, 20], rounding=3, chamfer=2)

    def test_the_group_beside_a_loose_member_is_refused(self) -> None:
        """SPEC G-3, as for every group."""
        with pytest.raises(Bosl2ValueError, match=r"treatment= and chamfer="):
            cuboid([20, 20, 20], treatment=EdgeTreatment.rounding(3), chamfer=2)

    def test_a_two_dimensional_constructor_takes_a_size_per_corner(self) -> None:
        """`rect` rounds each corner independently, and the group carries that."""
        shaped = rect([40, 20], treatment=EdgeTreatment.rounding([1, 2, 3, 4]))
        assert shaped.bounds().size == pytest.approx([40.0, 20.0])

    def test_a_per_corner_treatment_on_a_scalar_constructor_is_refused(self) -> None:
        """SPEC E-1/E-4: it used to reach the backend and surface as a bare TypeError."""
        with pytest.raises(Bosl2ValueError, match="one size to the whole shape"):
            cuboid([20, 20, 20], treatment=EdgeTreatment.rounding([1, 2, 3, 4]))


class TestEdgeSelection:
    """Which edges a treatment applies to, as one value (SPEC G-1)."""

    def test_a_selection_treats_the_edges_the_loose_arguments_would(self) -> None:
        """The group is a spelling, not a second behaviour."""
        grouped = cuboid([40, 30, 20], treatment=EdgeTreatment.rounding(4), selection=EdgeSelection(edges=Anchor.TOP))
        loose = cuboid([40, 30, 20], rounding=4, edges=Anchor.TOP)
        assert grouped.vnf().volume() == pytest.approx(loose.vnf().volume(), rel=1e-9)

    def test_selecting_edges_is_not_the_same_as_treating_them_all(self) -> None:
        """X-8: the selection has to actually reach the geometry."""
        some = cuboid([40, 30, 20], treatment=EdgeTreatment.rounding(4), selection=EdgeSelection(edges=Anchor.TOP))
        every = cuboid([40, 30, 20], treatment=EdgeTreatment.rounding(4))
        assert some.vnf().volume() != pytest.approx(every.vnf().volume(), rel=1e-6)

    def test_the_group_beside_a_loose_member_is_refused(self) -> None:
        """SPEC G-3, as for every group."""
        with pytest.raises(Bosl2ValueError, match=r"selection= and edges="):
            cuboid([20, 20, 20], selection=EdgeSelection(edges=Anchor.TOP), edges=Anchor.BOTTOM)

    def test_the_two_members_compose_rather_than_conflict(self) -> None:
        """Unlike a treatment, a selection's members narrow one another (SPEC G-7 does not apply)."""
        both = EdgeSelection(edges=Anchor.TOP, excepted=Anchor.FRONT).as_kwargs()
        assert both == {"edges": Anchor.TOP, "except_edges": Anchor.FRONT}


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
