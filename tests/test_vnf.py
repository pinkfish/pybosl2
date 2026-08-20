# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/vnf.py: VNF construction, grid/tri meshing, join and rendering."""

import math

import pytest

from pybosl2.caps import CapType
from pybosl2.enums import VNFStyle
from pybosl2.vnf import VNF


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
    b = v.bounds()
    assert b.min_x == 0.0
    assert b.max_x == 1.0
    assert b.min_y == 0.0
    assert b.max_y == 1.0
    assert b.min_z == 0.0
    assert b.max_z == 0.0
    assert b.width == 1.0
    assert b.length == 1.0
    assert b.height == 0.0
    assert math.isclose(v.volume(), 0.0, abs_tol=1e-12)


def test_empty_is_falsey() -> None:
    e = VNF([], [])
    assert not e
    assert len(e.vertices) == 0
    assert len(e.faces) == 0


def test_bounds() -> None:
    v = VNF([[-1, 0, 0], [2, 3, 4]], [[0, 1, 2]])
    b = v.bounds()
    assert b.min_x == -1
    assert b.max_x == 2
    assert b.min_y == 0
    assert b.max_y == 3
    assert b.min_z == 0
    assert b.max_z == 4
    assert b.width == 3.0
    assert b.length == 3.0
    assert b.height == 4.0


def test_vertex_array_default_counts() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True))
    assert len(v.vertices) == 9
    assert len(v.faces) == 8  # 2x2 cells, 2 tris each
    assert _valid(v)
    b = v.bounds()
    assert b.min_x == 0.0
    assert b.max_x == 2.0
    assert b.min_y == 0.0
    assert b.max_y == 2.0
    assert b.min_z == 0.0
    assert b.max_z == 4.0
    assert b.width == 2.0
    assert b.length == 2.0
    assert b.height == 4.0
    assert v.volume() == pytest.approx(1.0)


def test_vertex_array_quad_style() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), style=VNFStyle.QUAD)
    assert len(v.faces) == 4
    assert all(len(f) == 4 for f in v.faces)
    assert v.faces[0] == [0, 3, 4, 1]
    assert len(v.vertices) == 9
    b = v.bounds()
    assert b.min_z == 0.0
    assert b.max_z == 4.0
    assert _valid(v)


def test_vertex_array_quincunx_adds_center_verts() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), style=VNFStyle.QUINCUNX)
    assert len(v.vertices) == 9 + 4  # one center per cell
    assert len(v.faces) == 16  # 4 tris per cell
    b = v.bounds()
    assert b.min_z == 0.0
    assert b.max_z == 4.0
    assert v.volume() == pytest.approx(1.3333333333333333)


def test_vertex_array_reverse_flips_winding() -> None:
    a = VNF.vertex_array(_grid(2, 2, warp=True))
    b = VNF.vertex_array(_grid(2, 2, warp=True), reverse=True)
    assert a.faces[0] == b.faces[0][::-1]
    assert len(a.vertices) == 4
    assert len(a.faces) == 2


def test_vertex_array_col_wrap_adds_cells() -> None:
    plain = VNF.vertex_array(_grid(3, 3, warp=True))
    wrapped = VNF.vertex_array(_grid(3, 3, warp=True), col_wrap=True)
    assert len(wrapped.faces) > len(plain.faces)
    assert len(plain.faces) == 8
    assert len(wrapped.faces) == 12
    assert len(wrapped.vertices) == 9


def test_vertex_array_too_small_is_empty() -> None:
    result = VNF.vertex_array([[[0, 0, 0], [1, 0, 0]]])  # type: ignore  # single row
    assert not result
    assert len(result.vertices) == 0
    assert len(result.faces) == 0


def test_vertex_array_caps_need_col_wrap() -> None:
    with pytest.raises(ValueError, match="caps need col_wrap=True"):
        VNF.vertex_array(_grid(3, 3, warp=True), caps=CapType.BUTT, col_wrap=False)


def test_vertex_array_bad_style() -> None:
    v = VNF.vertex_array(_grid(2, 2), style="nope")
    assert isinstance(v, VNF)
    assert len(v.vertices) == 4
    assert len(v.faces) == 2


def test_tri_array_triangular_rows() -> None:
    pts = [[[0, 0, 0]], [[-1, 1, 0], [1, 1, 0]], [[-2, 2, 0], [0, 2, 0], [2, 2, 0]]]
    v = VNF.tri_array(pts)  # type: ignore[arg-type]
    assert len(v.vertices) == 6
    assert len(v.faces) == 4
    assert _valid(v)
    b = v.bounds()
    assert b.min_x == -2.0
    assert b.max_x == 2.0
    assert b.min_y == 0.0
    assert b.max_y == 2.0
    assert b.min_z == 0.0
    assert b.max_z == 0.0
    assert v.faces == [[1, 0, 2], [3, 1, 4], [4, 1, 2], [4, 2, 5]]


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
    r = v.reverse()
    assert r.faces == [[2, 1, 0]]
    assert len(r.vertices) == 3
    assert len(r.faces) == 1


def test_polyhedron_renders_via_mock() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True))
    assert len(v.vertices) == 9
    assert len(v.faces) == 8
    assert v.volume() == pytest.approx(1.0)
    solid = v.polyhedron()  # mock polyhedron tracks a bounding box
    assert solid is not None
    assert solid.position is not None


def test_vnf_polyhedron_helper() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True))
    assert len(v.vertices) == 9
    assert len(v.faces) == 8
    b = v.bounds()
    assert b.max_z == 4.0
    solid_method = v.polyhedron()
    assert solid_method is not None


def test_polyhedron_hands_over_faces_the_other_way_round(monkeypatch: pytest.MonkeyPatch) -> None:
    """polyhedron() winds its faces the opposite way from a VNF, so they go out reversed.

    Handing them over as they are builds every VNF-derived solid inside out: it still measures
    and exports correctly on its own, but unions and differences with it then do the opposite of
    what they should.
    """
    import pythonscad

    captured: dict[str, object] = {}

    def fake_polyhedron(points: object = None, faces: object = None, **_kwargs: object) -> object:
        captured["points"], captured["faces"] = points, faces
        return object()

    monkeypatch.setattr(pythonscad, "polyhedron", fake_polyhedron)
    cube = VNF(
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]],
        [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]],
    )
    assert cube.volume() == pytest.approx(1.0)  # wound the VNF way: outward faces, positive volume
    cube.polyhedron()
    assert captured["faces"] == [list(reversed(f)) for f in cube.faces]
    assert captured["points"] == [[float(c) for c in v] for v in cube.vertices]


# -- vertex_array style tests ---------------------------------------------------------------


def test_vertex_array_min_edge_style() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), style=VNFStyle.MIN_EDGE)
    assert len(v.vertices) == 9
    assert len(v.faces) == 8
    assert _valid(v)
    b = v.bounds()
    assert b.min_z == 0.0
    assert b.max_z == 4.0
    assert v.volume() == pytest.approx(1.6666666666666667)


def test_vertex_array_min_area_style() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), style=VNFStyle.MIN_AREA)
    assert len(v.vertices) == 9
    assert len(v.faces) == 8
    assert _valid(v)
    b = v.bounds()
    assert b.min_z == 0.0
    assert b.max_z == 4.0
    assert v.volume() == pytest.approx(1.6666666666666667)


def test_vertex_array_convex_style() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), style=VNFStyle.CONVEX)
    assert len(v.vertices) == 9
    assert len(v.faces) == 8
    assert _valid(v)
    b = v.bounds()
    assert b.min_z == 0.0
    assert b.max_z == 4.0
    assert v.volume() == pytest.approx(1.0)


def test_vertex_array_concave_style() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), style=VNFStyle.CONCAVE)
    assert len(v.vertices) == 9
    assert len(v.faces) == 8
    assert _valid(v)
    b = v.bounds()
    assert b.min_z == 0.0
    assert b.max_z == 4.0
    assert v.volume() == pytest.approx(1.6666666666666667)


def test_vertex_array_flip1_style() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), style=VNFStyle.FLIP1)
    assert len(v.vertices) == 9
    assert len(v.faces) == 8
    assert _valid(v)
    b = v.bounds()
    assert b.min_z == 0.0
    assert b.max_z == 4.0
    assert v.volume() == pytest.approx(1.3333333333333333)


def test_vertex_array_flip2_style() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), style=VNFStyle.FLIP2)
    assert len(v.vertices) == 9
    assert len(v.faces) == 8
    assert _valid(v)
    b = v.bounds()
    assert b.min_z == 0.0
    assert b.max_z == 4.0
    assert v.volume() == pytest.approx(1.3333333333333333)


def test_vertex_array_row_wrap() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), row_wrap=True)
    assert len(v.vertices) == 9
    assert len(v.faces) == 12
    assert _valid(v)
    b = v.bounds()
    assert b.min_x == 0.0
    assert b.max_x == 2.0
    assert b.min_y == 0.0
    assert b.max_y == 2.0
    assert b.min_z == 0.0
    assert b.max_z == 4.0
    assert v.volume() == pytest.approx(-1.0)


# -- cap tests ------------------------------------------------------------------------------


def test_vertex_array_flat_caps() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), col_wrap=True, caps=CapType.BUTT)
    assert len(v.vertices) == 9
    assert len(v.faces) == 14
    assert _valid(v)
    b = v.bounds()
    assert b.min_x == 0.0
    assert b.max_x == 2.0
    assert b.min_y == 0.0
    assert b.max_y == 2.0
    assert b.min_z == 0.0
    assert b.max_z == 4.0
    assert b.width == 2.0
    assert b.length == 2.0
    assert b.height == 4.0
    assert v.volume() == pytest.approx(-1.0)


def test_vertex_array_round_dome_caps() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), col_wrap=True, caps=CapType.ROUND)
    assert len(v.vertices) == 11
    assert len(v.faces) == 18
    assert _valid(v)
    b = v.bounds()
    assert b.min_x == 0.0
    assert b.max_x == 2.0
    assert b.min_y == 0.0
    assert b.max_y == 2.0
    assert b.min_z == -1.0
    assert b.max_z == 4.0
    assert b.height == 5.0
    assert v.volume() == pytest.approx(-1.0)


def test_vertex_array_mixed_caps() -> None:
    v = VNF.vertex_array(_grid(3, 3, warp=True), col_wrap=True, caps=[CapType.BUTT, CapType.ROUND])
    assert len(v.vertices) == 10
    assert len(v.faces) == 16
    assert _valid(v)
    b = v.bounds()
    assert b.min_x == 0.0
    assert b.max_x == 2.0
    assert b.min_y == 0.0
    assert b.max_y == 2.0
    assert b.min_z == 0.0
    assert b.max_z == 4.0
    assert v.volume() == pytest.approx(-1.0)


# -- VNF class method tests -----------------------------------------------------------------


def test_vnf_from_polyhedron_empty() -> None:
    v = VNF([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]])
    assert len(v.vertices) == 3
    assert len(v.faces) == 1
    result = v.polyhedron()
    assert result is not None


def test_vnf_volume_positive() -> None:
    verts: list[list[float]] = [
        [0, 0, 0],
        [1, 0, 0],
        [1, 1, 0],
        [0, 1, 0],
        [0, 0, 1],
        [1, 0, 1],
        [1, 1, 1],
        [0, 1, 1],
    ]
    faces: list[list[int]] = [
        [0, 2, 1],
        [0, 3, 2],
        [4, 5, 6],
        [4, 6, 7],
        [0, 1, 5],
        [0, 5, 4],
        [1, 2, 6],
        [1, 6, 5],
        [2, 3, 7],
        [2, 7, 6],
        [3, 0, 4],
        [3, 4, 7],
    ]
    v = VNF(verts, faces)
    assert math.isclose(v.volume(), 1.0, rel_tol=1e-9)
    assert len(v.vertices) == 8
    assert len(v.faces) == 12
    b = v.bounds()
    assert b.min_x == 0.0
    assert b.max_x == 1.0
    assert b.min_y == 0.0
    assert b.max_y == 1.0
    assert b.min_z == 0.0
    assert b.max_z == 1.0


def test_vnf_volume_zero_for_flat() -> None:
    verts: list[list[float]] = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    faces: list[list[int]] = [[0, 1, 2], [0, 2, 3]]
    v = VNF(verts, faces)
    assert math.isclose(v.volume(), 0.0, abs_tol=1e-12)
    assert len(v.vertices) == 4
    assert len(v.faces) == 2


def test_vnf_union_two_grids() -> None:
    a = VNF.vertex_array(_grid(3, 3, warp=True))
    b = VNF.vertex_array(_grid(3, 3, warp=True))
    j = VNF.union([a, b])
    assert len(j.vertices) == 18
    assert len(j.faces) == 16
    assert _valid(j)
    bj = j.bounds()
    assert bj.min_x == 0.0
    assert bj.max_x == 2.0
    assert bj.min_y == 0.0
    assert bj.max_y == 2.0
    assert bj.min_z == 0.0
    assert bj.max_z == 4.0
    assert j.volume() == pytest.approx(2.0)


# -- VNF.join / halfspace / slice tests ----------------------------------------------------


def test_vnf_join_is_alias_for_union() -> None:
    a = VNF([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]])
    b = VNF([[0, 0, 5], [1, 0, 5], [0, 1, 5]], [[0, 1, 2]])
    j = VNF.join([a, b])
    assert len(j.vertices) == 6
    assert j.faces == [[0, 1, 2], [3, 4, 5]]


def test_vnf_halfspace_plane_remove_top() -> None:
    cube_vnf = VNF.vertex_array(
        [
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
            [[0.0, 1.0, 0.0], [1.0, 1.0, 0.0]],
            [[0.0, 0.0, 1.0], [1.0, 0.0, 1.0]],
            [[0.0, 1.0, 1.0], [1.0, 1.0, 1.0]],
        ],
        style=VNFStyle.QUAD,
    )
    assert len(cube_vnf.vertices) == 8
    assert len(cube_vnf.faces) == 3
    cut = VNF.halfspace(cube_vnf, [0, 0, 1, 0.5], keep=True, closed=True)
    assert len(cut.vertices) == 6
    assert len(cut.faces) == 3
    assert _valid(cut)
    for v in cut.vertices:
        assert v[2] >= 0.5 - 1e-6
    cut_b = cut.bounds()
    assert cut_b.min_z == pytest.approx(0.5)
    assert cut_b.max_z == 1.0


def test_vnf_halfspace_keep_false() -> None:
    cube_vnf = VNF.vertex_array(
        [
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
            [[0.0, 1.0, 0.0], [1.0, 1.0, 0.0]],
            [[0.0, 0.0, 1.0], [1.0, 0.0, 1.0]],
            [[0.0, 1.0, 1.0], [1.0, 1.0, 1.0]],
        ],
        style=VNFStyle.QUAD,
    )
    cut = VNF.halfspace(cube_vnf, [0, 0, 1, 0.5], keep=False, closed=True)
    assert len(cut.vertices) == 6
    assert len(cut.faces) == 3
    assert _valid(cut)
    for v in cut.vertices:
        assert v[2] <= 0.5 + 1e-6
    cut_b = cut.bounds()
    assert cut_b.min_z == 0.0
    assert cut_b.max_z == pytest.approx(0.5)


def test_vnf_halfspace_no_closed() -> None:
    cube_vnf = VNF.vertex_array(
        [
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
            [[0.0, 1.0, 0.0], [1.0, 1.0, 0.0]],
            [[0.0, 0.0, 1.0], [1.0, 0.0, 1.0]],
            [[0.0, 1.0, 1.0], [1.0, 1.0, 1.0]],
        ],
        style=VNFStyle.QUAD,
    )
    cut = VNF.halfspace(cube_vnf, [0, 0, 1, 0.5], keep=True, closed=False)
    assert len(cut.vertices) == 6
    assert len(cut.faces) > 0


def test_vnf_halfspace_empty() -> None:
    v = VNF([], [])
    cut = VNF.halfspace(v, [0, 0, 1, 0], keep=True)
    assert len(cut.vertices) == 0
    assert len(cut.faces) == 0


def test_vnf_halfspace_all_inside() -> None:
    v = VNF([[0.0, 0.0, 5.0], [1.0, 0.0, 5.0], [0.0, 1.0, 5.0]], [[0, 1, 2]])
    cut = VNF.halfspace(v, [0, 0, 1, 0], keep=True)  # z=5 > 0 → all inside
    assert len(cut.vertices) == 3
    assert len(cut.faces) == 1


def test_vnf_halfspace_all_outside() -> None:
    v = VNF([[0.0, 0.0, 5.0], [1.0, 0.0, 5.0], [0.0, 1.0, 5.0]], [[0, 1, 2]])
    cut = VNF.halfspace(v, [0, 0, 1, 10], keep=True)  # z=5 < 10 → all outside
    assert len(cut.vertices) == 0
    assert len(cut.faces) == 0


def test_vnf_slice_returns_above_below() -> None:
    cube_vnf = VNF.vertex_array(
        [
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
            [[0.0, 1.0, 0.0], [1.0, 1.0, 0.0]],
            [[0.0, 0.0, 1.0], [1.0, 0.0, 1.0]],
            [[0.0, 1.0, 1.0], [1.0, 1.0, 1.0]],
        ],
        style=VNFStyle.QUAD,
    )
    above, below = VNF.slice(cube_vnf, [0, 0, 1, 0.5], closed=True)
    assert len(above.vertices) == 6
    assert len(above.faces) == 3
    assert len(below.vertices) == 6
    assert len(below.faces) == 3
    assert _valid(above)
    assert _valid(below)
    for v in above.vertices:
        assert v[2] >= 0.5 - 1e-6
    for v in below.vertices:
        assert v[2] <= 0.5 + 1e-6


# -- additional VNF coverage ---------------------------------------------------------------


def test_vnf_geometry() -> None:
    vnf = VNF.vertex_array(
        [[[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]]],
        col_wrap=True,
        style=VNFStyle.MIN_EDGE,
    )
    assert len(vnf.vertices) == 0
    assert len(vnf.faces) == 0
    # A single wrapped row spans no quads, so there is nothing to hand to the native polyhedron():
    # it rejects an empty point list, and geometry() says so in VNF terms.
    with pytest.raises(ValueError, match="no geometry to build"):
        vnf.geometry()


def test_vnf_from_field_cube() -> None:
    def field(pt: list[float]) -> float:
        return float(max(abs(pt[0]), abs(pt[1]), abs(pt[2])))

    vnf = VNF.from_field(field, isovalue=5.0, bounding_box=10.0, voxel_size=2.0)
    assert isinstance(vnf, VNF)
    assert len(vnf.vertices) > 100
    assert len(vnf.faces) > 100
    b = vnf.bounds()
    assert b.min_x == -5.0
    assert b.max_x == 5.0
    assert b.min_y == -5.0
    assert b.max_y == 5.0
    assert b.min_z == -5.0
    assert b.max_z == 5.0
    assert vnf.volume() == pytest.approx(197.33333333333334)


def test_vnf_halfspace_closed() -> None:
    vnf = VNF.vertex_array(
        [[[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]], [[0, 0, 10], [10, 0, 10], [10, 10, 10], [0, 10, 10]]],
        col_wrap=True,
        style=VNFStyle.MIN_EDGE,
    )
    assert len(vnf.vertices) == 8
    assert len(vnf.faces) == 8
    b_in = vnf.bounds()
    assert b_in.min_z == 0.0
    assert b_in.max_z == 10.0
    result = vnf.halfspace([0, 0, 1, -5], closed=True)
    assert isinstance(result, VNF)
    assert len(result.vertices) == 8
    assert len(result.faces) == 8
    b_out = result.bounds()
    assert b_out.min_z == 0.0
    assert b_out.max_z == 10.0
    assert result.volume() == pytest.approx(vnf.volume())
