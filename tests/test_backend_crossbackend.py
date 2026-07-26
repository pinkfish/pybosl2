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

from bosl2 import solid
from bosl2._backend import use_backend
from bosl2.exceptions import CrossBackendError, UnsupportedByBackend


def _libfive_available() -> bool:
    try:
        return importlib.util.find_spec("libfive") is not None
    except (ImportError, ValueError):
        return False


def _csg_sphere():
    return solid.sphere(radius=10)


def _sdf_sphere():
    with use_backend("sdf"):
        return solid.sphere(radius=10)


def test_same_backend_booleans_work():
    assert (_csg_sphere() | solid.cube(5)).backend == "csg"
    with use_backend("sdf"):
        assert (solid.sphere(radius=10) | solid.cube(5)).backend == "sdf"  # FFI-free SDF compose


@pytest.mark.parametrize("op", ["__or__", "__and__", "__sub__"])
def test_cross_backend_boolean_raises_both_directions(op):
    csg, sdf = _csg_sphere(), _sdf_sphere()
    with pytest.raises(CrossBackendError):
        getattr(csg, op)(sdf)  # csg <op> sdf
    with pytest.raises(CrossBackendError):
        getattr(sdf, op)(csg)  # sdf <op> csg


def test_cross_backend_error_points_at_to_csg():
    with pytest.raises(CrossBackendError) as ei:
        _ = _csg_sphere() | _sdf_sphere()
    assert "to_csg" in str(ei.value)


def test_converter_identities_are_noops():
    csg, sdf = _csg_sphere(), _sdf_sphere()
    assert csg.to_csg() is csg
    assert sdf.to_sdf() is sdf


def test_csg_to_sdf_is_unsupported():
    with pytest.raises(UnsupportedByBackend) as ei:
        _csg_sphere().to_sdf()
    assert ei.value.backend == "csg" and ei.value.feature == "to_sdf"


@pytest.mark.skipif(
    not _libfive_available(),
    reason="SDF->CSG conversion meshes via libfive (not installed here)",
)
def test_sdf_to_csg_meshes_into_a_csg_solid():
    csg = _sdf_sphere().to_csg()
    assert csg.backend == "csg"
    # and it can now be combined with other CSG solids without error
    assert (csg | solid.cube(5)).backend == "csg"
