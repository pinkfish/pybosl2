# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.texture: the texture() engine and textured_tile's use of it."""

import numpy as np
import pytest

from pybosl2.shapes3d import Bosl2Solid, textured_tile
from pybosl2.texture import (
    TEXTURES,
    is_heightfield_texture,
    is_vnf_texture,
    is_watertight_topology,
    rasterize_vnf_texture,
    texture,
    vnf_tile_to_solid,
)

_HF = [n for n, (_b, k) in TEXTURES.items() if k == "heightfield"]
_VNF = [n for n, (_b, k) in TEXTURES.items() if k == "vnf"]


@pytest.mark.parametrize("name", _HF)
def test_heightfield_textures_are_2d_arrays_in_range(name: str) -> None:
    a = np.array(texture(name))
    assert a.ndim == 2
    assert a.size > 0
    assert a.min() >= -1e-9
    assert a.max() <= 1.6 + 1e-9  # heights normalised to [0,1] (trunc_pyr to 1.5)
    assert is_heightfield_texture(texture(name))


@pytest.mark.parametrize("name", _VNF)
def test_vnf_textures_are_valid_meshes(name: str) -> None:
    verts, faces = texture(name)
    assert all(len(v) == 3 for v in verts)  # type: ignore[arg-type]
    assert max(i for f in faces for i in f) < len(verts)  # type: ignore[union-attr]  # face indices in range
    assert is_vnf_texture(texture(name))
    assert not is_heightfield_texture(texture(name))


def test_unknown_texture_raises() -> None:
    with pytest.raises(ValueError, match="Unrecognized"):
        texture("not_a_texture")


def test_resolution_parameter() -> None:
    assert len(texture("ribs", sides=8)[0]) == 8
    assert np.array(texture("pyramids", sides=6)).shape == (6, 6)


@pytest.mark.parametrize("name", _VNF)
def test_vnf_texture_tiles_watertight_or_rasterizes(name: str) -> None:
    # every VNF texture must either tile to a closed manifold via the sharp path, or have a valid
    # height-field rasterization that textured_tile falls back to.
    verts, faces = texture(name)
    v, f = vnf_tile_to_solid(verts, faces, size=[30, 30], reps=[4, 4], tex_depth=3)  # type: ignore[arg-type]
    if is_watertight_topology(v, f):
        return
    a: np.ndarray = np.array(rasterize_vnf_texture(verts, faces))  # type: ignore[arg-type]
    assert a.ndim == 2
    assert a.min() >= -1e-6
    assert a.max() <= 1.6 + 1e-6


@pytest.mark.parametrize("name", _HF + _VNF)
def test_textured_tile_by_name_builds(name: str) -> None:
    # tex_reps=[2, 2] keeps a tile-to-tile seam while building a far smaller mesh than [4, 4]:
    # this test only checks that each named texture builds a valid solid of the right outer size
    # (the dense [4, 4] render path is exercised by tests/test_stl_render.py::test_textured_tile_heightfield).
    s = textured_tile(name, size=[40, 40], tex_reps=[2, 2], tex_depth=3)  # type: ignore[operator]
    assert isinstance(s, Bosl2Solid)
    _, sz = s.bounds()
    assert round(sz[0]) == 40
    assert round(sz[1]) == 40


@pytest.mark.parametrize(("peak", "tex_depth"), [(1.0, 3), (1.0, 6), (0.5, 3)])
def test_textured_tile_raw_array_drives_the_height(peak: float, tex_depth: float) -> None:
    """A raw height-field array is used as given: heights are fractions of tex_depth."""
    base = 0.1  # the backing plate textured_tile always lays down
    s = textured_tile(  # type: ignore[operator]
        [[0, 0, 0], [0, peak, 0], [0, 0, 0]],
        size=[40, 40],
        tex_reps=[4, 4],
        tex_depth=tex_depth,
    )
    _, size = s.bounds()
    assert size[:2] == pytest.approx([40.0, 40.0])
    assert size[2] == pytest.approx(peak * tex_depth + base)

    # An all-zero array is the control: nothing but the backing plate.
    flat = textured_tile([[0, 0, 0]] * 3, size=[40, 40], tex_reps=[4, 4], tex_depth=tex_depth)  # type: ignore[operator]
    assert flat.bounds()[1][2] == pytest.approx(base)


@pytest.mark.parametrize(("tex_size", "reps"), [(20, 2), (10, 4), (5, 8)])
def test_textured_tile_tex_size_picks_reps(tex_size: float, reps: int) -> None:
    """tex_size is the repeat *size*: on a 40mm tile it must choose 40/tex_size repeats.

    Same tile, same texture, so picking the right count means emitting the identical model.
    """
    by_size = textured_tile("pyramids", size=[40, 40], tex_size=tex_size, tex_depth=2)  # type: ignore[operator]
    by_reps = textured_tile("pyramids", size=[40, 40], tex_reps=[reps, reps], tex_depth=2)  # type: ignore[operator]
    assert repr(by_size) == repr(by_reps)
    assert by_size.bounds()[1] == pytest.approx([40.0, 40.0, 2.1])
