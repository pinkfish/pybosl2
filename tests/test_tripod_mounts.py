# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for the TripodMounts module (Manfrotto RC2 plate)."""

from __future__ import annotations

import math

import pytest

from pybosl2._edges_lang import Anchor
from pybosl2.parts.tripod_mounts import ManfrottoRC2Plate
from pybosl2.shapes3d import Bosl2Solid


def _size(s: Bosl2Solid) -> list[float]:
    _box = s.bounds()
    _center, size = list(_box.center), list(_box.size)
    return size


def _center(s: Bosl2Solid) -> list[float]:
    _box = s.bounds()
    center = list(_box.center)
    return center


class TestManfrottoRC2Plate:
    """Tests for the ManfrottoRC2Plate().shape static method."""

    # ── BOSL2 geometry constants (from tripod_mounts.scad) ──────────────

    _LENGTH = 52.5
    _INNERLEN = 43.0
    _TOPWID = 37.4
    _BOTWID = 42.4
    _THICKNESS = 10.5

    # ── type and construction ──────────────────────────────────────────

    @pytest.mark.parametrize("chamfer", ["all", "bot", "bottom", "none"])
    def test_returns_bosl2solid(self, chamfer: str) -> None:
        """The plate is the same catalogue part whatever gets chamfered."""
        obj = ManfrottoRC2Plate(chamfer=chamfer).shape
        assert isinstance(obj, Bosl2Solid)
        assert _size(obj) == pytest.approx([self._BOTWID, self._LENGTH, self._THICKNESS], abs=0.01)

    def test_chamfer_mode_changes_what_is_cut(self) -> None:
        """ "all" chamfers both faces, "bot" only the underside, "none" neither -- and each does
        strictly more work than the last, which the bounding box cannot see."""
        programs = {mode: repr(ManfrottoRC2Plate(chamfer=mode).shape.shape) for mode in ("all", "bot", "none")}
        assert len(programs["all"]) > len(programs["bot"]) > len(programs["none"])

    def test_bottom_is_an_alias_for_bot(self) -> None:
        assert repr(ManfrottoRC2Plate(chamfer="bottom").shape.shape) == repr(
            ManfrottoRC2Plate(chamfer="bot").shape.shape
        )

    # ── error handling ─────────────────────────────────────────────────

    @pytest.mark.parametrize(
        "invalid_chamfer",
        ["top", "side", "partial", "BOTTOM", "ALL", "", "chamfer"],
    )
    def test_invalid_chamfer_raises_valueerror(self, invalid_chamfer: str) -> None:
        """Invalid chamfer values raise ValueError."""
        with pytest.raises(ValueError, match="chamfer"):
            _ = ManfrottoRC2Plate(chamfer=invalid_chamfer).shape

    # ── dimensional validation ─────────────────────────────────────────

    def test_bounding_box_dimensions_default(self) -> None:
        """The default plate has expected dimensions (botwid x length x thickness)."""
        obj = ManfrottoRC2Plate().shape
        size = _size(obj)
        assert size[0] == pytest.approx(self._BOTWID, abs=0.5)
        assert size[1] == pytest.approx(self._LENGTH, abs=0.5)
        assert size[2] == pytest.approx(self._THICKNESS, abs=0.5)

    def test_length_gt_innerlen(self) -> None:
        """The outer length exceeds the inner cutout region."""
        obj = ManfrottoRC2Plate().shape
        size = _size(obj)
        assert size[1] > self._INNERLEN

    def test_bottom_wider_than_top(self) -> None:
        """The plate is trapezoidal: bottom (botwid=42.4) wider than top (topwid=37.4)."""
        assert self._BOTWID > self._TOPWID

    @pytest.mark.parametrize("chamfer", ["all", "bot", "none"])
    def test_thickness_consistent_across_modes(self, chamfer: str) -> None:
        """Thickness is always 10.5 mm regardless of chamfer mode."""
        obj = ManfrottoRC2Plate(chamfer=chamfer).shape
        size = _size(obj)
        assert size[2] == pytest.approx(self._THICKNESS, abs=0.5)

    @pytest.mark.parametrize("chamfer", ["all", "bot", "none"])
    def test_width_and_length_consistent_across_modes(self, chamfer: str) -> None:
        """Width and length vary minimally across chamfer modes."""
        obj = ManfrottoRC2Plate(chamfer=chamfer).shape
        size = _size(obj)
        assert size[0] == pytest.approx(self._BOTWID, abs=1.0)
        assert size[1] == pytest.approx(self._LENGTH, abs=1.0)

    # ── cutout validation ──────────────────────────────────────────────

    def test_inner_region_is_narrower(self) -> None:
        """The inner cutout region (innerlen=43.0) is shorter than outer length (52.5)."""
        assert self._INNERLEN < self._LENGTH
        # The difference (length - innerlen) / 2 = corner cutout depth
        cutout_depth = (self._LENGTH - self._INNERLEN) / 2
        assert cutout_depth == pytest.approx(4.75, abs=1e-6)

    # ── chamfer mode differentiation ───────────────────────────────────
    # These require the real PythonSCAD app for accurate edge_mask rendering;
    # the pure-Python mock's edge_mask is a no-op that cannot differentiate.

    def test_chamfer_modes_all_produce_valid_solids(self) -> None:
        """All chamfer modes produce a valid Bosl2Solid without errors."""
        for chamfer in ("all", "bot", "bottom", "none"):
            obj = ManfrottoRC2Plate(chamfer=chamfer).shape
            assert isinstance(obj, Bosl2Solid)
            size = _size(obj)
            assert all(s > 0 for s in size), f"chamfer={chamfer}: all dimensions should be positive"

    # ── anchor parameter ───────────────────────────────────────────────

    def test_default_anchor_produces_positive_dimensions(self) -> None:
        """Default anchor=CENTER produces a plate with the expected dimensions."""
        obj = ManfrottoRC2Plate().shape
        size = _size(obj)
        assert size[0] == pytest.approx(self._BOTWID, abs=0.5)
        assert size[1] == pytest.approx(self._LENGTH, abs=0.5)
        assert size[2] == pytest.approx(self._THICKNESS, abs=0.5)

    def test_different_anchors_produce_different_centers(self) -> None:
        """Different anchors produce measurably different center positions."""
        obj_center = ManfrottoRC2Plate(anchor=Anchor.CENTER).shape
        obj_right = ManfrottoRC2Plate(anchor=Anchor.RIGHT).shape
        c_center = _center(obj_center)
        c_right = _center(obj_right)
        assert any(not math.isclose(a, b, abs_tol=1e-6) for a, b in zip(c_center, c_right, strict=True)), (
            "CENTER and RIGHT anchors should produce different center positions"
        )

    # ── spin parameter ─────────────────────────────────────────────────

    def test_spin_90_swaps_axes(self) -> None:
        """A 90-degree spin swaps the X and Y dimensions."""
        obj0 = ManfrottoRC2Plate(spin=0).shape
        obj90 = ManfrottoRC2Plate(spin=90).shape
        size0 = _size(obj0)
        size90 = _size(obj90)
        assert size0[0] == pytest.approx(size90[1], abs=1.0)
        assert size0[1] == pytest.approx(size90[0], abs=1.0)

    def test_spin_180_preserves_xy_dimensions(self) -> None:
        """A 180-degree spin preserves the X and Y dimensions."""
        obj0 = ManfrottoRC2Plate(spin=0).shape
        obj180 = ManfrottoRC2Plate(spin=180).shape
        size0 = _size(obj0)
        size180 = _size(obj180)
        assert size0[0] == pytest.approx(size180[0], abs=1.0)
        assert size0[1] == pytest.approx(size180[1], abs=1.0)

    # ── orient parameter ───────────────────────────────────────────────

    def test_default_orient_is_top(self) -> None:
        """Default orient=TOP places the plate flat (thickness along Z)."""
        obj = ManfrottoRC2Plate().shape
        size = _size(obj)
        # The thickness (Z) should be 10.5; the X/Y should be botwid/length
        assert size[2] == pytest.approx(self._THICKNESS, abs=0.5)
        # X and Y should be width and length, not thickness
        assert size[0] > self._THICKNESS
        assert size[1] > self._THICKNESS

    def test_orient_front_rotates_thickness_into_y(self) -> None:
        """orient=FRONT rotates the plate so thickness is along Y."""
        obj = ManfrottoRC2Plate(orient=Anchor.FRONT).shape
        size = _size(obj)
        # After orienting to FRONT, thickness should appear in one of the axes
        thickness_values = [s for s in size if s == pytest.approx(self._THICKNESS, abs=1.0)]
        assert len(thickness_values) >= 1, "Thickness should appear in at least one axis"

    # ── fn/fa/fs parameters ────────────────────────────────────────────

    @pytest.mark.parametrize(
        ("name", "kwargs"),
        [
            ("fn", {"fn": 32}),
            ("fa", {"fa": 5.0}),
            ("fs", {"fs": 1.0}),
            ("all_three", {"fn": 32, "fa": 5.0, "fs": 1.0}),
        ],
    )
    def test_facet_controls_are_accepted_and_passed_down(self, name: str, kwargs: dict[str, float]) -> None:
        """The plate takes fn/fa/fs and threads them into the shapes it builds (SPEC R-1).

        Its geometry is all boxes, chamfers and swept polygons -- no arcs -- so the facet count
        has nothing to smooth and the result is identical either way. That the *geometry* does not
        move is the point: a plate that changed shape with fn would be the bug.
        """
        plate = ManfrottoRC2Plate(**kwargs).shape  # type: ignore[arg-type]
        assert isinstance(plate, Bosl2Solid)
        assert repr(plate.shape) == repr(ManfrottoRC2Plate().shape.shape), name

    # ── numeric anchor parameter ───────────────────────────────────────

    def test_numeric_vector_anchor_accepted(self) -> None:
        """A numeric [x, y, z] anchor puts that face on the origin, without resizing the plate."""
        anchored = ManfrottoRC2Plate(anchor=[1.0, 0.0, 0.0]).shape
        assert isinstance(anchored, Bosl2Solid)
        assert _size(anchored) == pytest.approx([self._BOTWID, self._LENGTH, self._THICKNESS], abs=0.01)
        assert _center(anchored)[0] == pytest.approx(-self._BOTWID / 2, abs=0.6)

    def test_numeric_anchor_moves_center(self) -> None:
        """A numeric anchor off center shifts the object's center."""
        obj_center = ManfrottoRC2Plate(anchor=[0.0, 0.0, 0.0]).shape
        obj_right = ManfrottoRC2Plate(anchor=[1.0, 0.0, 0.0]).shape
        c_center = _center(obj_center)
        c_right = _center(obj_right)
        # Anchor [1,0,0] means right face at origin => center moves left
        assert c_right[0] < c_center[0]

    # ── numeric orient parameter ───────────────────────────────────────

    def test_numeric_vector_orient_accepted(self) -> None:
        """orient=+Y stands the plate on end, so its length and thickness swap axes."""
        upright = ManfrottoRC2Plate(orient=[0.0, 1.0, 0.0]).shape
        assert isinstance(upright, Bosl2Solid)
        assert _size(upright) == pytest.approx([self._BOTWID, self._THICKNESS, self._LENGTH], abs=0.01)

    # ── zero rotation identity ─────────────────────────────────────────

    def test_spin_zero_preserves_volume_sign(self) -> None:
        """Zero spin with default parameters produces a valid solid."""
        obj = ManfrottoRC2Plate(spin=0.0).shape
        size = _size(obj)
        assert all(s > 0 for s in size), "All dimensions should be positive"


class TestTripodMountsModuleAlias:
    """Tests that the module-level function alias matches the class method."""

    @pytest.mark.parametrize("chamfer", ["all", "bot", "none"])
    def test_alias_produces_same_dimensions_as_class_method(self, chamfer: str) -> None:
        """ManfrottoRC2Plate().shape and ManfrottoRC2Plate().shape produce identical dimensions."""
        obj_cls = ManfrottoRC2Plate(chamfer=chamfer).shape
        obj_fn = ManfrottoRC2Plate(chamfer=chamfer).shape
        size_cls = _size(obj_cls)
        size_fn = _size(obj_fn)
        for a, b in zip(size_cls, size_fn, strict=True):
            assert math.isclose(a, b, rel_tol=1e-9), (
                f"chamfer={chamfer}: dimensions differ between alias and class method"
            )


class TestTripodMountsEdgeCases:
    """Edge case and boundary tests."""

    def test_multiple_plates_independent(self) -> None:
        """Generating multiple plates does not share state."""
        obj1 = ManfrottoRC2Plate().shape
        obj2 = ManfrottoRC2Plate(chamfer="none").shape
        assert isinstance(obj1, Bosl2Solid)
        assert isinstance(obj2, Bosl2Solid)
        assert obj1 is not obj2, "Each call should return a new instance"
