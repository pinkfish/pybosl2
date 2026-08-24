# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The error contract as a caller experiences it (SPEC E-1, E-4, E-5, E-6, E-7).

Four things §9 promised that the code did not do: `except Bosl2Error` caught none of the ~570
validation errors, `hasattr()` on an SDF shape raised instead of answering, `flat - solid` printed
a warning to stdout and returned the flat unchanged, and a constructor with nothing to build from
returned a degenerate shape rather than saying so.
"""

from __future__ import annotations

import ast
import copy
import inspect
from pathlib import Path as FilePath

import pytest

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
from pybosl2 import circle, cuboid, cyl, sphere, square, use_backend
from pybosl2.exceptions import Bosl2Error, Bosl2ValueError, UnsupportedByBackendError

PACKAGE = FilePath(__file__).resolve().parent.parent / "pybosl2"


# --- E-1: one base a caller can actually catch --------------------------------------------


def test_a_validation_error_is_catchable_as_the_library_family() -> None:
    """E-1 and E-4 both bind, so the type raised is both (SPEC E-1)."""
    with pytest.raises(Bosl2Error):
        cyl(height=10, radius=5, diameter=10)


def test_a_validation_error_is_still_a_value_error() -> None:
    """Every caller who already wrote `except ValueError` keeps working -- that is the MRO's job."""
    with pytest.raises(ValueError, match="not both"):
        cyl(height=10, radius=5, diameter=10)


def test_bosl2_value_error_is_both() -> None:
    assert issubclass(Bosl2ValueError, Bosl2Error)
    assert issubclass(Bosl2ValueError, ValueError)


def test_the_package_raises_no_bare_value_error() -> None:
    """A bare `ValueError` opts out of E-1; the ratchet keeps it from coming back (PLAN E-P4a)."""
    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            call = node.exc
            name = call.func if isinstance(call, ast.Call) else call
            if isinstance(name, ast.Name) and name.id == "ValueError":
                offenders.append(f"{path.relative_to(PACKAGE.parent)}:{node.lineno}")
    assert not offenders, "raise Bosl2ValueError instead (PLAN E-P4a): " + ", ".join(offenders)


# --- E-6: a refusal is still an attribute error --------------------------------------------


def test_hasattr_on_an_unknown_name_answers_rather_than_raising() -> None:
    """`hasattr` catches AttributeError and nothing else, so a refusal has to be one (SPEC E-6).

    The `__getattr__` fallback is what this guards: anything the SDF backend neither implements nor
    lists refuses from there, and a capability probe must get an answer rather than a traceback.
    (The *listed* CSG-only features are real refusing methods -- see PAR-3 -- so `hasattr` finds
    them and the refusal fires on the call.)
    """
    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
    assert hasattr(shape, "no_such_operation") is False
    assert getattr(shape, "no_such_operation", "fallback") == "fallback"


def test_the_refusal_still_teaches_when_you_call_it() -> None:
    """A refusal names the feature, the backend and the way forward (SPEC E-2)."""
    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
    with pytest.raises(UnsupportedByBackendError, match="attachment, tagging and the edge treatments"):
        shape.attach(None, None)
    with pytest.raises(UnsupportedByBackendError, match=r"convert explicitly with \.to_csg\(\)"):
        shape.no_such_operation()  # type: ignore[attr-defined]


def test_an_sdf_shape_survives_the_protocols_that_probe_attributes() -> None:
    """copy and inspect walk attributes; both used to hit a traceback rather than a missing name.

    (Not pickle: an SDF shape holds its field as a closure, so it is unpicklable for reasons that
    have nothing to do with the refusal type.)
    """
    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
    assert copy.deepcopy(shape).bounds().size == shape.bounds().size
    # `dir()`/`getattr_static` walk names without evaluating properties -- `getmembers()` would
    # call `vnf`, and meshing a field is not what a capability probe should cost.
    assert "bounds" in dir(shape)
    assert inspect.getattr_static(type(shape), "bounds", None) is not None


def test_unsupported_is_both_bases() -> None:
    assert issubclass(UnsupportedByBackendError, Bosl2Error)
    assert issubclass(UnsupportedByBackendError, AttributeError)


# --- E-7: mixing dimensions raises -----------------------------------------------------------


@pytest.mark.parametrize("backend", ["csg", "sdf"])
def test_mixing_dimensions_raises_and_names_the_way_across(backend: str) -> None:
    """It used to warn on stdout and hand back the flat unchanged (SPEC C-4, C-16, E-7)."""
    with use_backend(backend):
        flat, solid = square([10, 10]), cuboid([5, 5, 5])
        for operation in (lambda: flat - solid, lambda: flat | solid, lambda: flat & solid):
            with pytest.raises(Bosl2ValueError, match="linear_extrude"):
                operation()
        for operation in (lambda: solid - flat, lambda: solid | flat, lambda: solid & flat):
            with pytest.raises(Bosl2ValueError, match="projection"):
                operation()


@pytest.mark.parametrize("backend", ["csg", "sdf"])
def test_same_dimension_booleans_are_untouched(backend: str) -> None:
    """The guard must not cost the ordinary case anything."""
    with use_backend(backend):
        flat_cut = square([10, 10]) - circle(radius=2)
        solid_cut = cuboid([10, 10, 10]) - sphere(radius=2)
    # the cut happened and the outer extent is untouched: the guard is in the operand check, not
    # in the geometry
    assert flat_cut.bounds().size == pytest.approx((10.0, 10.0), abs=0.01)
    assert solid_cut.bounds().size == pytest.approx((10.0, 10.0, 10.0), abs=0.01)
    if backend == "csg":  # meshing an SDF field needs libfive, which the pip wheel does not carry
        assert solid_cut.vnf().volume() < 10 * 10 * 10


# --- E-5: a call that cannot mean what it says fails loudly ---------------------------------


def test_a_constructor_with_nothing_to_build_from_refuses() -> None:
    """`regular_ngon()` returned a polygon of coincident points with infinite bounds (SPEC E-5)."""
    from pybosl2 import regular_ngon

    with pytest.raises(Bosl2ValueError, match="needs a size"):
        regular_ngon()
