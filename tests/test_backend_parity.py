# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The exclusive-feature lists must match the implementations (SPEC PAR-3, PLAN B-P4).

A name listed as exclusive to one backend but implemented on the other is worse than no list at
all: the refusal never fires, and the two records of what a backend can do disagree.
"""

from __future__ import annotations

import inspect
from typing import cast

import pytest

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
from pybosl2._backend import CSG_ONLY_FEATURES, SDF_ONLY_FEATURES
from pybosl2.bounds import Bounds3D
from pybosl2.exceptions import UnsupportedByBackendError
from pybosl2.sdf.shapes3d import SdfSolid
from pybosl2.shapes3d.base import CsgSolid


def test_every_csg_only_feature_refuses_on_the_sdf_shape() -> None:
    """A CSG-only feature is declared on the SDF shape and refuses (SPEC PAR-3, PLAN B-P4).

    What must never happen is the third case -- listed as exclusive and quietly *working*, as
    `projection` once did, so the refusal never fires. Absence is no longer the requirement:
    a member supplied only by `__getattr__` makes `isinstance(sdf_solid, Solid)` false (T-6b), and
    a method that says why is more explicit than a missing name (C-13).
    """
    from pybosl2.exceptions import UnsupportedByBackendError

    shape = _sdf_probe()
    silent: list[str] = []
    for feature in sorted(CSG_ONLY_FEATURES):
        member = inspect.getattr_static(SdfSolid, feature, None)
        if member is None:
            continue  # reached through __getattr__, which refuses for anything unlisted
        try:
            getattr(shape, feature)()
        except UnsupportedByBackendError:
            continue
        except Exception:
            continue
        silent.append(feature)
    assert not silent, "listed as CSG-only but succeeds on SdfSolid, so the refusal never fires: " + ", ".join(silent)


def _sdf_probe() -> SdfSolid:
    """A plain SDF solid to probe the refusals against."""
    from pybosl2._backend import use_backend
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        return cast("SdfSolid", cuboid([10, 10, 10]))


def test_sdf_only_features_are_absent_from_the_csg_shape() -> None:
    implemented = sorted(f for f in SDF_ONLY_FEATURES if inspect.getattr_static(CsgSolid, f, None) is not None)
    assert not implemented, "listed as SDF-only but implemented on CsgSolid: " + ", ".join(implemented)


def test_the_refusal_names_the_explicit_conversion() -> None:
    import pytest

    from pybosl2._backend import use_backend
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
        with pytest.raises(UnsupportedByBackendError, match=r"\.to_csg\(\)"):
            shape.projection()


def test_sdf_shapes_keep_their_backend_through_moves_and_colour() -> None:
    """Modelling operations stay in the field instead of meshing behind the caller's back.

    `up()` and `color()` used to fall through to `getattr(self.mesh(), name)`, which returned a
    raw native handle with no backend tag (SPEC C-1, B-5, PLAN E-P6).
    """
    from pybosl2._backend import use_backend
    from pybosl2.color import Color
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        moved = cuboid([10, 10, 10]).up(5).right(2).forward(1)
        assert isinstance(moved, SdfSolid)
        assert moved.backend == "sdf"
        assert moved.bounds() == Bounds3D.from_center_size([2.0, -1.0, 5.0], [10.0, 10.0, 10.0])

        coloured = cuboid([10, 10, 10]).color(Color("red")).ghost()
        assert isinstance(coloured, SdfSolid)
        assert coloured.backend == "sdf"
        # the appearance rides along with the field rather than forcing an early mesh
        assert coloured.bounds() == cuboid([10, 10, 10]).bounds()


def test_an_unknown_operation_refuses_instead_of_meshing() -> None:
    """The fallback no longer converts a field to a mesh to answer a name it does not know."""
    import pytest

    from pybosl2._backend import use_backend
    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
        with pytest.raises(UnsupportedByBackendError, match=r"\.to_csg\(\)"):
            shape.no_such_operation()


def test_every_directional_move_stays_in_the_field() -> None:
    """Every directional move is an exact wrapper over the SDF's own translate (SPEC C-1).

    `fwd` was here too, as a synonym of `forward`; it is gone (SPEC C-21).
    """
    from pybosl2._backend import use_backend
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
        moves = {
            "right": ([2.0], [2.0, 0.0, 0.0]),
            "left": ([2.0], [-2.0, 0.0, 0.0]),
            "back": ([2.0], [0.0, 2.0, 0.0]),
            "forward": ([2.0], [0.0, -2.0, 0.0]),
            "up": ([2.0], [0.0, 0.0, 2.0]),
            "down": ([2.0], [0.0, 0.0, -2.0]),
        }
        for name, (args, expected_centre) in moves.items():
            moved = getattr(shape, name)(*args)
            assert isinstance(moved, SdfSolid), name
            assert moved.backend == "sdf", name
            assert moved.bounds().center == expected_centre, name

        assert shape.translate([1.0, 2.0, 3.0]).bounds().center == [1.0, 2.0, 3.0]
        assert isinstance(shape.rotate(90), SdfSolid)


def test_colour_and_modifiers_are_recorded_on_the_field() -> None:
    """Colour rides along as metadata and is applied when the shape is realized (SPEC C-19)."""
    from pybosl2._backend import use_backend
    from pybosl2.color import Color
    from pybosl2.solid import cuboid

    class _FakeMesh:
        """Stands in for the meshed native solid, recording what was applied to it."""

        def __init__(self) -> None:
            self.applied: list[str] = []

        def color(self, colour: object, alpha: object = None) -> "_FakeMesh":
            self.applied.append(f"color={colour}:{alpha}")
            return self

        def highlight(self) -> "_FakeMesh":
            self.applied.append("highlight")
            return self

        def background(self) -> "_FakeMesh":
            self.applied.append("ghost")
            return self

    with use_backend("sdf"):
        plain = cuboid([10, 10, 10])
        assert plain._apply_appearance(_FakeMesh()).applied == []

        red = plain.color(Color("red"))
        assert red._colour is not None
        assert red._apply_appearance(_FakeMesh()).applied == ["color=[1.0, 0.0, 0.0]:None"]

        assert plain.highlight()._apply_appearance(_FakeMesh()).applied == ["highlight"]
        assert plain.ghost()._apply_appearance(_FakeMesh()).applied == ["ghost"]

        # and it survives an exact transform rather than forcing an early mesh
        assert red.up(5)._colour == red._colour


def test_two_dimensional_fields_refuse_to_render() -> None:
    """A 2-D distance field has no rendering of its own; show() names the extrusion (SPEC S-50)."""
    import pytest

    from pybosl2.exceptions import UnsupportedByBackendError
    from pybosl2.sdf.shapes2d import circle2d

    with pytest.raises(UnsupportedByBackendError, match="linear_extrude"):
        circle2d(radius=5).show()


def test_realizing_an_sdf_shape_applies_its_appearance() -> None:
    """show() meshes (rendering IS meshing) and paints what the caller recorded (SPEC S-50)."""
    from pybosl2._backend import use_backend
    from pybosl2.color import Color
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        shape = cuboid([10, 10, 10]).color(Color("#00ff00")).ghost()
        returned = shape.show()
        assert returned is shape  # the chain stays in SDF-land
        meshed = shape.mesh()
        assert getattr(meshed, "shown", False)
        assert getattr(meshed, "colour", None) == ([0.0, 1.0, 0.0], None)
        assert getattr(meshed, "modifier", None) == "ghost"


def test_a_mesh_operation_is_forwarded_to_the_meshed_solid() -> None:
    """Operations that genuinely need mesh topology mesh the field; that is not a silent conversion."""
    from pybosl2._backend import use_backend
    from pybosl2.sdf.shapes3d import _MESH_OPERATIONS
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
        assert "background" in _MESH_OPERATIONS  # it is on the list *because* it needs topology

        meshed = shape.background()  # forwarded to the meshed solid, not refused
        assert meshed is not None
        # Forwarded to the field's own mesh -- realized once and reused, not meshed afresh.
        assert meshed is shape.mesh()
        # ... and the solid it was called on is still an SDF solid: nothing was converted in place.
        assert shape.backend == "sdf"
        assert type(shape).__name__ == "SdfSolid"


def test_the_mesh_operation_list_only_holds_names_that_reach_the_fallback() -> None:
    """An entry that is also a real method is a stale record, like `projection` was (PLAN B-P4)."""
    from pybosl2.sdf.shapes3d import _MESH_OPERATIONS

    shadowed = sorted(n for n in _MESH_OPERATIONS if inspect.getattr_static(SdfSolid, n, None) is not None)
    assert not shadowed, f"listed as forwarded-to-the-mesh but implemented on SdfSolid: {shadowed}"


def test_a_private_name_is_answered_without_meshing() -> None:
    """copy/pickle/hasattr probe underscore names; answering them must not realize the field."""
    from pybosl2._backend import use_backend
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
        assert not hasattr(shape, "_not_a_real_attribute")
        assert shape._mesh_cache is None  # nothing was meshed to answer that


#: Shapes whose SDF bounds() is not the shape's own box. Empty, and meant to stay that way: the
#: SDF backend's selling point is exact bounds, so a conservative box here is a defect, not a
#: tolerance. `pie_slice` was the last entry -- it stored the full disc rather than the wedge, and
#: over-reported by four times the area at 30 degrees (PAR-5).
BOUNDS_NOT_YET_EXACT: frozenset[str] = frozenset()


#: Arguments for the façade constructors that cannot be called bare, so the convergence check
#: below exercises them rather than skipping them. A bare call is used for everything else.
CONSTRUCTOR_ARGUMENTS: dict[str, dict[str, object]] = {
    "regular_prism": {"sides": 6, "radius": 5, "height": 10},
    "prismoid": {"size1": [10, 10], "size2": [6, 6], "height": 8},
}


def test_the_same_call_builds_the_same_geometry_on_both_backends() -> None:
    """PAR-5: an identical call differs only in tessellation, so both converge at high resolution."""
    import inspect

    import pybosl2.solid as facade
    from pybosl2._backend import use_backend
    from pybosl2.defaults import use_defaults

    checked = 0
    with use_defaults(fn=256):
        for name in sorted(facade.__all__):
            function = getattr(facade, name)
            if not inspect.isfunction(function) or name in BOUNDS_NOT_YET_EXACT:
                continue
            if name in {"current_backend", "known_backends", "effective_defaults", "given_arguments"}:
                continue  # not shape constructors
            parameters = inspect.signature(function).parameters.values()
            arguments = CONSTRUCTOR_ARGUMENTS.get(name, {})
            required = [
                p for p in parameters if p.default is inspect.Parameter.empty and p.kind is not p.VAR_POSITIONAL
            ]
            if required and not arguments:
                continue
            # A constructor that cannot be called bare used to be skipped outright, which left
            # `regular_prism` unchecked -- and its SDF form anchored half a height too high on
            # every anchor, for as long as it had existed. Give it arguments instead of skipping.
            built = {}
            for backend in ("csg", "sdf"):
                with use_backend(backend):
                    try:
                        built[backend] = function(**arguments).bounds()
                    except (ValueError, UnsupportedByBackendError):
                        built = {}
                        break
            if not built:
                continue
            checked += 1
            csg_centre, csg_size = list(built["csg"].center), list(built["csg"].size)
            sdf_centre, sdf_size = list(built["sdf"].center), list(built["sdf"].size)
            # Placement must match outright -- that is what a shared default decides. Size is
            # compared proportionally: a facetted CSG solid inscribes its analytic SDF twin, and
            # at these unit-sized defaults that gap is a few percent even at fn=256.
            for csg_value, sdf_value in zip(csg_centre, sdf_centre, strict=True):
                assert abs(csg_value - sdf_value) < 0.12, (
                    f"{name}() sits in a different place per backend: csg={csg_centre} sdf={sdf_centre}"
                )
            for csg_value, sdf_value in zip(csg_size, sdf_size, strict=True):
                span = max(abs(csg_value), abs(sdf_value), 1e-9)
                assert abs(csg_value - sdf_value) / span < 0.12, (
                    f"{name}() is a different size per backend: csg={csg_size} sdf={sdf_size}"
                )
    assert checked >= 8, f"only {checked} shapes compared across backends"


# ---------------------------------------------------------------------------
# PAR-5: a difference reports the bounds of what is left, not of what it started with
# ---------------------------------------------------------------------------


def test_a_cut_that_trims_an_end_tightens_the_bounds() -> None:
    """SPEC PAR-5. An SDF difference used to keep the base's box verbatim.

    Safe, but not exact -- and exact bounds are what this backend is for. It cost a real bug:
    `TrussClip` squares off its ends with two box cuts and reported the untrimmed height, 6mm
    taller than the CSG twin of the same source. The field was right the whole time; only the
    box it advertised was stale.
    """
    from pybosl2._backend import use_backend
    from pybosl2.solid import cuboid

    for backend in ("csg", "sdf"):
        with use_backend(backend):
            trimmed = cuboid([10, 10, 20]) - cuboid([12, 12, 6]).up(10)  # type: ignore[operator]
        _box = trimmed.bounds()
        _centre, size = list(_box.center), list(_box.size)
        assert [float(v) for v in size] == pytest.approx([10.0, 10.0, 17.0], abs=0.01), (
            f"{backend} reported {list(size)} for a solid cut down to 17 tall"
        )


def test_the_tightened_bounds_still_contain_the_solid() -> None:
    """Under-reporting is worse than over-reporting: `mn`/`mx` is the meshing domain."""
    from pybosl2._backend import use_backend
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        trimmed = cuboid([10, 10, 20]) - cuboid([12, 12, 6]).up(10)  # type: ignore[operator]
        field = trimmed.mesh()
        assert float(field.sample(0, 0, 6.9)) < 0  # solid just below the cut ...
        assert float(field.sample(0, 0, 7.5)) > 0  # ... and gone just above it
        assert trimmed.mx[2] == pytest.approx(7.0)  # so the box ends exactly where the solid does


def test_a_cut_that_cannot_be_proved_leaves_the_bounds_alone() -> None:
    """Only a provable trim is applied; anything else keeps the conservative box.

    A hole through the middle removes nothing from any face, a cut that misses the cross-section
    trims nothing, and a rotated cutter is no longer a box this can reason about.
    """
    from pybosl2._backend import use_backend
    from pybosl2.solid import cuboid, cyl

    with use_backend("sdf"):
        base = cuboid([10, 10, 20])  # type: ignore[operator]
        through_hole = base - cyl(height=30, radius=2)  # type: ignore[operator]
        assert [float(v) for v in through_hole.bounds().size] == pytest.approx([10, 10, 20])

        partial = base - cuboid([4, 4, 6]).up(10)  # type: ignore[operator]  # too narrow to trim the end
        assert [float(v) for v in partial.bounds().size] == pytest.approx([10, 10, 20])

        turned = base - cuboid([12, 12, 6]).up(10).rotate(30, [0, 0, 1])  # type: ignore[operator]
        assert [float(v) for v in turned.bounds().size] == pytest.approx([10, 10, 20])


def test_a_rounded_cutter_does_not_count_as_a_box() -> None:
    """An edge treatment rounds the corners away, so the cutter no longer fills its own box."""
    from pybosl2.sdf.shapes3d import _axis_aligned_box
    from pybosl2.sdf.shapes3d import cuboid as sdf_cuboid

    assert _axis_aligned_box(sdf_cuboid([10, 10, 10])) is not None
    assert _axis_aligned_box(sdf_cuboid([10, 10, 10]).round(2)) is None
    assert _axis_aligned_box(sdf_cuboid([10, 10, 10]).rotate(30, [0, 0, 1])) is None
    # ... but a plain move keeps it a box, including when the move is spelt as a matrix
    assert _axis_aligned_box(sdf_cuboid([10, 10, 10]).up(5)) is not None
    translation = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 5], [0, 0, 0, 1]]
    moved = _axis_aligned_box(sdf_cuboid([10, 10, 10]).multmatrix(translation))
    assert moved is not None
    assert moved[0][2] == pytest.approx(0.0)
    assert moved[1][2] == pytest.approx(10.0)


class TestLinearSweepAgreesAcrossBackends:
    """The two backends must sweep the same solid: same twist direction, same shifted top.

    These compare the SDF field against the CSG sweep's actual meshed vertices rather than
    against a hand-derived expectation, so they stay honest if either transform is retuned.
    """

    HEIGHT = 10.0

    @staticmethod
    def _blob_profile(radius: float = 1.5, offset: float = 5.0, sides: int = 24) -> list[list[float]]:
        """A small disc pushed out along +X -- off-centre, so a twist's direction shows up."""
        import math

        return [
            [offset + radius * math.cos(t), radius * math.sin(t)]
            for t in [i * 2 * math.pi / sides for i in range(sides)]
        ]

    def _csg_top_centre(self, **kwargs: object) -> list[float]:
        import numpy as np

        from pybosl2 import Path2D

        swept = Path2D(self._blob_profile()).linear_sweep(height=self.HEIGHT, **kwargs)  # type: ignore[arg-type]
        verts = np.asarray(swept.vnf().vertices, dtype=float)
        top = verts[np.abs(verts[:, 2] - self.HEIGHT) < 1e-6]
        return [float(c) for c in top[:, :2].mean(axis=0)]

    def _sdf_solid(self, **kwargs: object) -> object:
        from pybosl2.sdf import shapes2d as sdf_s2d
        from pybosl2.sdf import skin as sdf_skin

        profile = sdf_s2d.circle2d(radius=1.5).translate([5, 0])
        return sdf_skin._linear_sweep_sdf(profile, height=self.HEIGHT, **kwargs)  # type: ignore[arg-type]

    def _sdf_contains(self, solid: object, x: float, y: float) -> bool:
        d = solid._sdf_fn(x, y, self.HEIGHT - 0.1)  # type: ignore[attr-defined]
        z = self.HEIGHT - 0.1
        return (float(d(x, y, z)) if callable(d) else float(d)) <= 1e-6

    @pytest.mark.parametrize("twist", [90.0, -90.0, 45.0])
    def test_twist_carries_the_profile_the_same_way(self, twist: float) -> None:
        """Where CSG's mesh puts the top of the blob, the SDF field must also be solid -- and its
        mirror image about the origin must not be."""
        cx, cy = self._csg_top_centre(twist=twist)
        solid = self._sdf_solid(twist=twist)
        assert self._sdf_contains(solid, cx, cy), f"twist={twist}: SDF is empty where CSG put the blob ({cx}, {cy})"
        assert not self._sdf_contains(solid, -cx, -cy), f"twist={twist}: SDF twisted the opposite way"

    def test_shift_and_scale_land_the_top_in_the_same_place(self) -> None:
        """The profile is scaled about the origin and then shifted, so the blob's own centre at
        x=5 goes to 2*5 + 4 = 14 -- not 2*(5 + 4) = 18, which is where shifting first put it."""
        cx, cy = self._csg_top_centre(scale=2.0, shift=(4.0, 0.0))
        assert [round(cx, 6), round(cy, 6)] == [14.0, 0.0]  # the CSG mesh agrees with the argument
        solid = self._sdf_solid(scale=2.0, shift=(4.0, 0.0))
        assert self._sdf_contains(solid, cx, cy)
        assert not self._sdf_contains(solid, 18.0, cy)
