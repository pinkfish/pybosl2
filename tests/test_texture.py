# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.texture: the texture() engine and textured_tile's use of it."""

import numpy as np
import pytest

from bosl2.texture import (
    TEXTURES,
    texture,
    is_heightfield_texture,
    is_vnf_texture,
    is_watertight_topology,
    rasterize_vnf_texture,
    vnf_tile_to_solid,
)
from bosl2.shapes3d import textured_tile, Bosl2Solid

_HF = [n for n, (_b, k) in TEXTURES.items() if k == "heightfield"]
_VNF = [n for n, (_b, k) in TEXTURES.items() if k == "vnf"]


@pytest.mark.parametrize("name", _HF)
def test_heightfield_textures_are_2d_arrays_in_range(name):
    a = np.array(texture(name))
    assert a.ndim == 2 and a.size > 0
    assert (
        a.min() >= -1e-9 and a.max() <= 1.6 + 1e-9
    )  # heights normalised to [0,1] (trunc_pyr to 1.5)
    assert is_heightfield_texture(texture(name))


@pytest.mark.parametrize("name", _VNF)
def test_vnf_textures_are_valid_meshes(name):
    verts, faces = texture(name)
    assert all(len(v) == 3 for v in verts)
    assert max(i for f in faces for i in f) < len(verts)  # face indices in range
    assert is_vnf_texture(texture(name))
    assert not is_heightfield_texture(texture(name))


def test_unknown_texture_raises():
    with pytest.raises(ValueError):
        texture("not_a_texture")


def test_resolution_parameter():
    assert len(texture("ribs", sides=8)[0]) == 8
    assert np.array(texture("pyramids", sides=6)).shape == (6, 6)


@pytest.mark.parametrize("name", _VNF)
def test_vnf_texture_tiles_watertight_or_rasterizes(name):
    # every VNF texture must either tile to a closed manifold via the sharp path, or have a valid
    # height-field rasterization that textured_tile falls back to.
    verts, faces = texture(name)
    v, f = vnf_tile_to_solid(verts, faces, size=[30, 30], reps=[4, 4], tex_depth=3)
    if is_watertight_topology(v, f):
        return
    a = np.array(rasterize_vnf_texture(verts, faces))
    assert a.ndim == 2 and a.min() >= -1e-6 and a.max() <= 1.6 + 1e-6


@pytest.mark.parametrize("name", _HF + _VNF)
def test_textured_tile_by_name_builds(name):
    s = textured_tile(name, size=[40, 40], tex_reps=[4, 4], tex_depth=3)
    assert isinstance(s, Bosl2Solid)
    _, sz = s.bounds()
    assert round(sz[0]) == 40 and round(sz[1]) == 40


def test_textured_tile_raw_array_still_works():
    s = textured_tile(
        [[0, 0, 0], [0, 1, 0], [0, 0, 0]], size=[40, 40], tex_reps=[4, 4], tex_depth=3
    )
    assert isinstance(s, Bosl2Solid)


def test_textured_tile_tex_size_picks_reps():
    s = textured_tile("pyramids", size=[40, 40], tex_size=10, tex_depth=2)
    assert isinstance(s, Bosl2Solid)
