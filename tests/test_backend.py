# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for the dual-backend selection machinery (pybosl2/_backend.py) and its exceptions
(pybosl2/exceptions.py). Milestone 1 of the CSG/SDF merge: the foundation, no dispatch yet."""

import pytest

from pybosl2 import _backend
from pybosl2.exceptions import Bosl2Error, CrossBackendError, UnsupportedByBackend


def test_default_backend_is_csg():
    assert _backend.current_backend() == "csg"


def test_use_backend_switches_and_restores():
    assert _backend.current_backend() == "csg"
    with _backend.use_backend("sdf"):
        assert _backend.current_backend() == "sdf"
        with _backend.use_backend("csg"):  # nesting
            assert _backend.current_backend() == "csg"
        assert _backend.current_backend() == "sdf"
    assert _backend.current_backend() == "csg"  # restored even after nesting


def test_set_default_backend_roundtrip():
    try:
        _backend.set_default_backend("sdf")
        assert _backend.current_backend() == "sdf"
        with _backend.use_backend("csg"):
            assert _backend.current_backend() == "csg"  # context still overrides the default
    finally:
        _backend.set_default_backend("csg")
    assert _backend.current_backend() == "csg"


def test_unknown_backend_raises():
    with pytest.raises(Bosl2Error):
        _backend.use_backend("nope").__enter__()
    with pytest.raises(Bosl2Error):
        _backend.set_default_backend("nope")


def test_bosl2solid_is_csg_backend_and_conforms_to_solid_protocol():
    from pybosl2.shapes3d import Bosl2Solid, cuboid

    box = cuboid([10, 10, 10])
    assert box.backend == "csg"
    assert Bosl2Solid.backend == "csg"
    assert isinstance(box, _backend.Solid)  # runtime-checkable Protocol conformance


def test_unsupported_by_backend_message_and_fields():
    err = UnsupportedByBackend("attach", "sdf", hint="use the csg backend for attachment")
    assert err.feature == "attach" and err.backend == "sdf"
    assert "attach" in str(err) and "sdf" in str(err) and "csg backend for attachment" in str(err)


def test_cross_backend_error_gives_conversion_guidance():
    err = CrossBackendError("csg", "sdf")
    assert err.left == "csg" and err.right == "sdf"
    msg = str(err)
    assert "to_csg" in msg  # points at the supported SDF->CSG bridge
    assert isinstance(err, Bosl2Error)
