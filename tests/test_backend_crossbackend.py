# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Milestone 4 of the CSG/SDF merge: cross-backend guards and the to_csg()/to_sdf() converters.

Boolean ops require operands to share a backend (else CrossBackendError with conversion guidance);
SDF->CSG is an exact mesh->polyhedron bridge, CSG->SDF is unsupported."""

import importlib.util

import pytest

from pybosl2 import solid
from pybosl2._backend import Solid, use_backend
from pybosl2.exceptions import CrossBackendError, UnsupportedByBackendError


def _libfive_available() -> bool:
    try:
        return importlib.util.find_spec("libfive") is not None
    except (ImportError, ValueError):
        return False


def _csg_sphere() -> Solid:
    return solid.sphere(radius=10)  # type: ignore[attr-defined, no-any-return]


def _sdf_sphere() -> Solid:
    with use_backend("sdf"):
        return solid.sphere(radius=10)  # type: ignore[attr-defined, no-any-return]


def test_same_backend_booleans_work() -> None:
    assert (_csg_sphere() | solid.cube(5)).backend == "csg"  # type: ignore[attr-defined]
    with use_backend("sdf"):
        assert (solid.sphere(radius=10) | solid.cube(5)).backend == "sdf"  # type: ignore[attr-defined]  # FFI-free SDF compose


@pytest.mark.parametrize("op", ["__or__", "__and__", "__sub__"])
def test_cross_backend_boolean_raises_both_directions(op: str) -> None:
    csg, sdf = _csg_sphere(), _sdf_sphere()
    with pytest.raises(CrossBackendError):
        getattr(csg, op)(sdf)  # csg <op> sdf
    with pytest.raises(CrossBackendError):
        getattr(sdf, op)(csg)  # sdf <op> csg


def test_cross_backend_error_points_at_to_csg() -> None:
    with pytest.raises(CrossBackendError) as ei:
        _ = _csg_sphere() | _sdf_sphere()
    assert "to_csg" in str(ei.value)


def test_converter_identities_are_noops() -> None:
    csg, sdf = _csg_sphere(), _sdf_sphere()
    assert csg.to_csg() is csg  # type: ignore[attr-defined]
    assert sdf.to_sdf() is sdf  # type: ignore[attr-defined]


def test_csg_to_sdf_is_unsupported() -> None:
    with pytest.raises(UnsupportedByBackendError) as ei:
        _csg_sphere().to_sdf()  # type: ignore[attr-defined]
    assert ei.value.backend == "csg"
    assert ei.value.feature == "to_sdf"


@pytest.mark.skipif(
    not _libfive_available(),
    reason="SDF->CSG conversion meshes via libfive (not installed here)",
)
def test_sdf_to_csg_meshes_into_a_csg_solid() -> None:
    csg = _sdf_sphere().to_csg()  # type: ignore[attr-defined]
    assert csg.backend == "csg"
    # and it can now be combined with other CSG solids without error
    assert (csg | solid.cube(5)).backend == "csg"  # type: ignore[attr-defined]
