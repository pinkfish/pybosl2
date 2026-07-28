# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Milestone 5 of the CSG/SDF merge: the capability map. A backend-exclusive feature raises
UnsupportedByBackendError on the other backend (rather than a confusing AttributeError -- or, on the SDF
side, meshing via libfive just to fail)."""

import pytest

from pybosl2 import solid
from pybosl2._backend import supports, use_backend
from pybosl2.exceptions import UnsupportedByBackendError


@pytest.mark.parametrize("feature", ["attach", "anchor_point", "align", "edge_mask", "face_profile"])
def test_csg_attachment_features_unsupported_on_sdf(feature):
    with use_backend("sdf"):
        s = solid.sphere(radius=10)  # building is FFI-free; the check fires before any meshing
        with pytest.raises(UnsupportedByBackendError) as ei:
            getattr(s, feature)
        assert ei.value.backend == "sdf"
        assert ei.value.feature == feature


@pytest.mark.parametrize("feature", ["round", "chamfer"])
def test_sdf_edge_treatments_unsupported_on_csg(feature):
    s = solid.sphere(radius=10)  # csg (default)
    with pytest.raises(UnsupportedByBackendError) as ei:
        getattr(s, feature)
    assert ei.value.backend == "csg"
    assert ei.value.feature == feature


def test_csg_attachment_methods_still_work_on_csg():
    box = solid.cuboid([10, 10, 10])
    assert callable(box.attach)  # real method on the CSG backend, not intercepted
    assert callable(box.edge_mask)


def test_sdf_edge_treatments_still_work_on_sdf():
    with use_backend("sdf"):
        box = solid.cuboid([10, 10, 10])
        assert callable(box.round)  # real PyShape method on the SDF backend
        assert callable(box.chamfer)


def test_supports_query():
    assert supports("csg", "attach")
    assert not supports("sdf", "attach")
    assert supports("sdf", "round")
    assert not supports("csg", "round")
    assert supports("csg", "sphere")
    assert supports("sdf", "sphere")  # shared surface
