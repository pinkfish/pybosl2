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

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
from pybosl2._backend import CSG_ONLY_FEATURES, SDF_ONLY_FEATURES
from pybosl2.exceptions import UnsupportedByBackendError
from pybosl2.sdf.shapes3d import SdfSolid
from pybosl2.shapes3d.base import CsgSolid


def test_csg_only_features_are_absent_from_the_sdf_shape() -> None:
    implemented = sorted(f for f in CSG_ONLY_FEATURES if inspect.getattr_static(SdfSolid, f, None) is not None)
    assert not implemented, "listed as CSG-only but implemented on SdfSolid, so the refusal never fires: " + ", ".join(
        implemented
    )


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
        moved = cuboid([10, 10, 10]).up(5).right(2).fwd(1)
        assert isinstance(moved, SdfSolid)
        assert moved.backend == "sdf"
        assert moved.bounds() == ([2.0, -1.0, 5.0], [10.0, 10.0, 10.0])

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
    """All nine moves are exact wrappers over the SDF's own translate/rotate (SPEC C-1)."""
    from pybosl2._backend import use_backend
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
        moves = {
            "right": ([2.0], [2.0, 0.0, 0.0]),
            "left": ([2.0], [-2.0, 0.0, 0.0]),
            "back": ([2.0], [0.0, 2.0, 0.0]),
            "forward": ([2.0], [0.0, -2.0, 0.0]),
            "fwd": ([2.0], [0.0, -2.0, 0.0]),
            "up": ([2.0], [0.0, 0.0, 2.0]),
            "down": ([2.0], [0.0, 0.0, -2.0]),
        }
        for name, (args, expected_centre) in moves.items():
            moved = getattr(shape, name)(*args)
            assert isinstance(moved, SdfSolid), name
            assert moved.backend == "sdf", name
            assert moved.bounds()[0] == expected_centre, name

        assert shape.move([1.0, 2.0, 3.0]).bounds()[0] == [1.0, 2.0, 3.0]
        assert isinstance(shape.rot(90), SdfSolid)


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
    from pybosl2.solid import cuboid

    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
        assert shape.background() is not None  # forwarded to the meshed solid, not refused


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


#: Shapes whose SDF bounds are not yet the shape's own: pie_slice stores the full disc's box
#: rather than the wedge's, so an exact bounds() query over-reports (SPEC §12.2, PAR-5).
BOUNDS_NOT_YET_EXACT = frozenset({"pie_slice"})


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
            if any(p.default is inspect.Parameter.empty and p.kind is not p.VAR_POSITIONAL for p in parameters):
                continue
            built = {}
            for backend in ("csg", "sdf"):
                with use_backend(backend):
                    try:
                        built[backend] = function().bounds()
                    except (ValueError, UnsupportedByBackendError):
                        built = {}
                        break
            if not built:
                continue
            checked += 1
            csg_centre, csg_size = built["csg"]
            sdf_centre, sdf_size = built["sdf"]
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
