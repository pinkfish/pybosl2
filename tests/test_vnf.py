# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/vnf.py: VNF construction, grid/tri meshing, join and rendering."""

import pytest

from pybosl2.vnf import VNF, vnf_polyhedron


def _grid(rows: int, cols: int, warp: bool = False) -> list[list[list[float]]]:
    return [[[float(i), float(j), (float(i * j) if warp else 0.0)] for j in range(cols)] for i in range(rows)]


def _valid(vnf: object) -> bool:
    if not vnf.faces:  # type: ignore[attr-defined]
        return True
    return max(i for f in vnf.faces for i in f) < len(vnf.vertices)  # type: ignore[attr-defined, no-any-return]


def test_construction_and_repr() -> None:
    v = VNF([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]])
    assert len(v.vertices) == 3
    assert len(v.faces) == 1
    assert bool(v) is True
    assert "VNF" in repr(v)


def test_empty_is_falsey() -> None:
    assert not VNF([], [])


def test_bounds() -> None:
    v = VNF([[-1, 0, 0], [2, 3, 4]], [[0, 1, 2]])
    b = v.bounds()
    assert b.min_x == -1
    assert b.max_x == 2
    assert b.min_y == 0
    assert b.max_y == 3
    assert b.min_z == 0
    assert b.max_z == 4


def test_vertex_array_default_counts() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True))
    assert len(v.vertices) == 9
    assert len(v.faces) == 8  # 2x2 cells, 2 tris each
    assert _valid(v)


def test_vertex_array_quad_style() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), style="quad")
    assert len(v.faces) == 4
    assert all(len(f) == 4 for f in v.faces)


def test_vertex_array_quincunx_adds_center_verts() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), style="quincunx")
    assert len(v.vertices) == 9 + 4  # one center per cell
    assert len(v.faces) == 16  # 4 tris per cell


def test_vertex_array_reverse_flips_winding() -> None:
    a = VNF.vertex_array(_grid(2, 2, warp=True))
    b = VNF.vertex_array(_grid(2, 2, warp=True), reverse=True)
    assert a.faces[0] == b.faces[0][::-1]


def test_vertex_array_col_wrap_adds_cells() -> None:
    plain = VNF.vertex_array(_grid(3, 3, warp=True))
    wrapped = VNF.vertex_array(_grid(3, 3, warp=True), col_wrap=True)
    assert len(wrapped.faces) > len(plain.faces)


def test_vertex_array_too_small_is_empty() -> None:
    assert not VNF.vertex_array([[[0, 0, 0], [1, 0, 0]]])  # type: ignore  # single row


def test_vertex_array_caps_need_col_wrap() -> None:
    with pytest.raises(AssertionError):
        VNF.vertex_array(_grid(3, 3, warp=True), caps=True, col_wrap=False)


def test_vertex_array_bad_style() -> None:
    with pytest.raises(AssertionError):
        VNF.vertex_array(_grid(2, 2), style="nope")


def test_tri_array_triangular_rows() -> None:
    pts = [[[0, 0, 0]], [[-1, 1, 0], [1, 1, 0]], [[-2, 2, 0], [0, 2, 0], [2, 2, 0]]]
    v = VNF.tri_array(pts)  # type: ignore[arg-type]
    assert len(v.vertices) == 6
    assert _valid(v)


def test_union_offsets_indices() -> None:
    a = VNF([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]])
    b = VNF([[0, 0, 5], [1, 0, 5], [0, 1, 5]], [[0, 1, 2]])
    j = VNF.union([a, b])
    assert len(j.vertices) == 6
    assert j.faces == [[0, 1, 2], [3, 4, 5]]


def test_union_single_is_identity() -> None:
    a = VNF([[0, 0, 0]], [])
    assert VNF.union([a]) is a


def test_reverse() -> None:
    v = VNF([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]])
    assert v.reverse().faces == [[2, 1, 0]]


def test_polyhedron_renders_via_mock() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True))
    solid = v.polyhedron()  # mock polyhedron tracks a bounding box
    assert solid is not None
    assert solid.position is not None


def test_vnf_polyhedron_helper() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True))
    solid_method = v.polyhedron()
    solid_helper = vnf_polyhedron(v)
    assert solid_method is not None
    assert solid_helper is not None
    # Check that both return mock solids with same bounds or attributes
    assert str(solid_method.position) == str(solid_helper.position)
