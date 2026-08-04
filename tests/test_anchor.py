# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/_edges_lang.py: the Anchor enum and edge/corner helpers."""

import pytest

from pybosl2._edges_lang import (
    CORNER_OFFSETS,
    EDGES_ALL,
    EDGES_NONE,
    Anchor,
    CornerPlane,
    EdgePlane,
    _edge_set,
    edges,
    resolve_anchor,
)

# ---------------------------------------------------------------------------
# Anchor enum basics
# ---------------------------------------------------------------------------


class TestAnchorBasics:
    def test_all_37_anchor_members_exist(self) -> None:
        expected = {
            "CENTER",
            "TOP",
            "BOTTOM",
            "FRONT",
            "BACK",
            "LEFT",
            "RIGHT",
            "TOP_FRONT",
            "TOP_BACK",
            "TOP_LEFT",
            "TOP_RIGHT",
            "BOTTOM_FRONT",
            "BOTTOM_BACK",
            "BOTTOM_LEFT",
            "BOTTOM_RIGHT",
            "FRONT_LEFT",
            "FRONT_RIGHT",
            "BACK_LEFT",
            "BACK_RIGHT",
            "TOP_FRONT_LEFT",
            "TOP_FRONT_RIGHT",
            "TOP_BACK_LEFT",
            "TOP_BACK_RIGHT",
            "BOTTOM_FRONT_LEFT",
            "BOTTOM_FRONT_RIGHT",
            "BOTTOM_BACK_LEFT",
            "BOTTOM_BACK_RIGHT",
            "ALL",
            "NONE",
            "X",
            "Y",
            "Z",
        }
        assert {m.name for m in Anchor} == expected
        assert len(list(Anchor)) == 32  # 7 faces + 12 edges + 8 corners + 5 axis presets

    def test_face_anchors_have_correct_vectors(self) -> None:
        assert list(Anchor.TOP.vector) == [0.0, 0.0, 1.0]
        assert list(Anchor.BOTTOM.vector) == [0.0, 0.0, -1.0]
        assert list(Anchor.FRONT.vector) == [0.0, -1.0, 0.0]
        assert list(Anchor.BACK.vector) == [0.0, 1.0, 0.0]
        assert list(Anchor.LEFT.vector) == [-1.0, 0.0, 0.0]
        assert list(Anchor.RIGHT.vector) == [1.0, 0.0, 0.0]
        assert list(Anchor.CENTER.vector) == [0.0, 0.0, 0.0]

    def test_edge_anchors_have_correct_vectors(self) -> None:
        assert list(Anchor.TOP_FRONT.vector) == [0.0, -1.0, 1.0]
        assert list(Anchor.TOP_BACK.vector) == [0.0, 1.0, 1.0]
        assert list(Anchor.TOP_LEFT.vector) == [-1.0, 0.0, 1.0]
        assert list(Anchor.TOP_RIGHT.vector) == [1.0, 0.0, 1.0]
        assert list(Anchor.BOTTOM_FRONT.vector) == [0.0, -1.0, -1.0]
        assert list(Anchor.BOTTOM_BACK.vector) == [0.0, 1.0, -1.0]
        assert list(Anchor.BOTTOM_LEFT.vector) == [-1.0, 0.0, -1.0]
        assert list(Anchor.BOTTOM_RIGHT.vector) == [1.0, 0.0, -1.0]
        assert list(Anchor.FRONT_LEFT.vector) == [-1.0, -1.0, 0.0]
        assert list(Anchor.FRONT_RIGHT.vector) == [1.0, -1.0, 0.0]
        assert list(Anchor.BACK_LEFT.vector) == [-1.0, 1.0, 0.0]
        assert list(Anchor.BACK_RIGHT.vector) == [1.0, 1.0, 0.0]

    def test_corner_anchors_have_correct_vectors(self) -> None:
        assert list(Anchor.TOP_FRONT_LEFT.vector) == [-1.0, -1.0, 1.0]
        assert list(Anchor.TOP_FRONT_RIGHT.vector) == [1.0, -1.0, 1.0]
        assert list(Anchor.TOP_BACK_LEFT.vector) == [-1.0, 1.0, 1.0]
        assert list(Anchor.TOP_BACK_RIGHT.vector) == [1.0, 1.0, 1.0]
        assert list(Anchor.BOTTOM_FRONT_LEFT.vector) == [-1.0, -1.0, -1.0]
        assert list(Anchor.BOTTOM_FRONT_RIGHT.vector) == [1.0, -1.0, -1.0]
        assert list(Anchor.BOTTOM_BACK_LEFT.vector) == [-1.0, 1.0, -1.0]
        assert list(Anchor.BOTTOM_BACK_RIGHT.vector) == [1.0, 1.0, -1.0]

    def test_axis_presets_have_string_values(self) -> None:
        assert Anchor.X.value == "x"
        assert Anchor.Y.value == "y"
        assert Anchor.Z.value == "z"
        assert Anchor.ALL.value == "all"
        assert Anchor.NONE.value == "none"


# ---------------------------------------------------------------------------
# Anchor properties
# ---------------------------------------------------------------------------


class TestAnchorProperties:
    def test_is_face_returns_true_for_faces_and_center(self) -> None:
        assert Anchor.CENTER.is_face is True
        assert Anchor.TOP.is_face is True
        assert Anchor.BOTTOM.is_face is True
        assert Anchor.FRONT.is_face is True
        assert Anchor.BACK.is_face is True
        assert Anchor.LEFT.is_face is True
        assert Anchor.RIGHT.is_face is True

    def test_is_face_returns_false_for_edges_and_corners(self) -> None:
        assert Anchor.TOP_LEFT.is_face is False
        assert Anchor.TOP_FRONT.is_face is False
        assert Anchor.TOP_FRONT_LEFT.is_face is False
        assert Anchor.TOP_FRONT_RIGHT.is_face is False
        assert Anchor.BOTTOM_BACK_RIGHT.is_face is False

    def test_is_face_returns_false_for_axis_presets(self) -> None:
        assert Anchor.X.is_face is False
        assert Anchor.Y.is_face is False
        assert Anchor.Z.is_face is False
        assert Anchor.ALL.is_face is False
        assert Anchor.NONE.is_face is False

    def test_is_edge_returns_true_for_edges(self) -> None:
        edges = [
            Anchor.TOP_FRONT,
            Anchor.TOP_BACK,
            Anchor.TOP_LEFT,
            Anchor.TOP_RIGHT,
            Anchor.BOTTOM_FRONT,
            Anchor.BOTTOM_BACK,
            Anchor.BOTTOM_LEFT,
            Anchor.BOTTOM_RIGHT,
            Anchor.FRONT_LEFT,
            Anchor.FRONT_RIGHT,
            Anchor.BACK_LEFT,
            Anchor.BACK_RIGHT,
        ]
        for edge in edges:
            assert edge.is_edge is True, f"{edge.name} should be an edge"

    def test_is_edge_returns_false_for_faces_and_corners(self) -> None:
        assert Anchor.TOP.is_edge is False
        assert Anchor.FRONT.is_edge is False
        assert Anchor.CENTER.is_edge is False
        assert Anchor.TOP_FRONT_LEFT.is_edge is False
        assert Anchor.BOTTOM_BACK_RIGHT.is_edge is False

    def test_is_corner_returns_true_for_corners(self) -> None:
        corners = [
            Anchor.TOP_FRONT_LEFT,
            Anchor.TOP_FRONT_RIGHT,
            Anchor.TOP_BACK_LEFT,
            Anchor.TOP_BACK_RIGHT,
            Anchor.BOTTOM_FRONT_LEFT,
            Anchor.BOTTOM_FRONT_RIGHT,
            Anchor.BOTTOM_BACK_LEFT,
            Anchor.BOTTOM_BACK_RIGHT,
        ]
        for corner in corners:
            assert corner.is_corner is True, f"{corner.name} should be a corner"

    def test_is_corner_returns_false_for_faces_and_edges(self) -> None:
        assert Anchor.TOP.is_corner is False
        assert Anchor.CENTER.is_corner is False
        assert Anchor.TOP_LEFT.is_corner is False
        assert Anchor.FRONT_LEFT.is_corner is False

    def test_axis_presets_raise_typeerror_on_vector(self) -> None:
        for preset in (Anchor.X, Anchor.Y, Anchor.Z, Anchor.ALL, Anchor.NONE):
            with pytest.raises(TypeError):
                _ = preset.vector

    def test_vector_2d_returns_2d_point(self) -> None:
        v2d = Anchor.TOP_LEFT.vector_2d
        assert list(v2d) == [-1.0, 1.0]  # x=-1, y=0+z=1

    def test_vector_2d_front(self) -> None:
        v2d = Anchor.FRONT.vector_2d
        assert list(v2d) == [0.0, -1.0]

    def test_vector_2d_center(self) -> None:
        v2d = Anchor.CENTER.vector_2d
        assert list(v2d) == [0.0, 0.0]

    def test_vector_2d_axis_preset_raises(self) -> None:
        with pytest.raises(TypeError):
            _ = Anchor.X.vector_2d

    def test_anchor_iter(self) -> None:
        assert list(Anchor.TOP) == [0.0, 0.0, 1.0]
        assert list(Anchor.CENTER) == [0.0, 0.0, 0.0]
        assert list(Anchor.TOP_FRONT_LEFT) == [-1.0, -1.0, 1.0]

    def test_anchor_iter_axis_preset_raises(self) -> None:
        with pytest.raises(TypeError):
            list(Anchor.X)

    def test_anchor_len(self) -> None:
        assert len(Anchor.CENTER) == 3
        assert len(Anchor.TOP) == 3
        assert len(Anchor.TOP_FRONT_LEFT) == 3

    def test_anchor_len_axis_preset_raises(self) -> None:
        with pytest.raises(TypeError):
            len(Anchor.X)

    def test_anchor_getitem(self) -> None:
        assert Anchor.TOP_FRONT_LEFT[0] == -1.0
        assert Anchor.TOP[2] == 1.0
        assert Anchor.CENTER[1] == 0.0

    def test_anchor_getitem_axis_preset_raises(self) -> None:
        with pytest.raises(TypeError):
            _ = Anchor.X[0]


# ---------------------------------------------------------------------------
# Anchor arithmetic
# ---------------------------------------------------------------------------


class TestAnchorArithmetic:
    def test_anchor_add_face_plus_face(self) -> None:
        result = Anchor.TOP + Anchor.FRONT
        assert list(result) == [0.0, -1.0, 1.0]

    def test_anchor_add_face_plus_face_left(self) -> None:
        result = Anchor.TOP + Anchor.LEFT
        assert list(result) == [-1.0, 0.0, 1.0]

    def test_anchor_add_face_plus_back(self) -> None:
        result = Anchor.TOP + Anchor.BACK
        assert list(result) == [0.0, 1.0, 1.0]

    def test_anchor_add_edge_plus_face(self) -> None:
        result = Anchor.TOP_FRONT + Anchor.LEFT
        assert list(result) == [-1.0, -1.0, 1.0]  # TOP_FRONT_LEFT

    def test_anchor_add_center_unchanged(self) -> None:
        result = Anchor.TOP + Anchor.CENTER
        assert list(result) == [0.0, 0.0, 1.0]


# ---------------------------------------------------------------------------
# Edge/corner matrix helpers
# ---------------------------------------------------------------------------


class TestEdgeMatrix:
    def test_edge_matrix_shape(self) -> None:
        matrix = Anchor.TOP.to_edge_matrix()
        assert len(matrix) == 3
        assert all(len(row) == 4 for row in matrix)

    def test_edge_matrix_from_face_has_edges(self) -> None:
        for face in (Anchor.TOP, Anchor.BOTTOM, Anchor.FRONT, Anchor.BACK, Anchor.LEFT, Anchor.RIGHT):
            matrix = face.to_edge_matrix()
            assert sum(sum(row) for row in matrix) == 4, f"{face.name} face should select 4 edges"

    def test_edge_matrix_from_edge_anchor(self) -> None:
        matrix = Anchor.TOP_FRONT.to_edge_matrix()
        assert len(matrix) == 3
        assert sum(sum(row) for row in matrix) == 1  # exactly one edge selected

    def test_edge_matrix_from_corner_anchor_returns_none(self) -> None:
        matrix = Anchor.TOP_FRONT_LEFT.to_edge_matrix()
        assert matrix == EDGES_NONE

    def test_edge_matrix_from_center_returns_none(self) -> None:
        matrix = Anchor.CENTER.to_edge_matrix()
        assert matrix == EDGES_NONE

    def test_edge_matrix_all(self) -> None:
        assert Anchor.ALL.to_edge_matrix() == EDGES_ALL

    def test_edge_matrix_none(self) -> None:
        assert Anchor.NONE.to_edge_matrix() == EDGES_NONE

    def test_edge_matrix_x(self) -> None:
        matrix = Anchor.X.to_edge_matrix()
        assert len(matrix) == 3
        assert all(len(row) == 4 for row in matrix)

    def test_edge_matrix_y(self) -> None:
        matrix = Anchor.Y.to_edge_matrix()
        assert len(matrix) == 3
        assert all(len(row) == 4 for row in matrix)

    def test_edge_matrix_z(self) -> None:
        matrix = Anchor.Z.to_edge_matrix()
        assert len(matrix) == 3
        assert all(len(row) == 4 for row in matrix)


class TestCornerSet:
    def test_corner_set_from_face_top(self) -> None:
        cs = Anchor.TOP.to_corner_set()
        assert len(cs) == 8
        assert sum(cs) == 4  # top face has 4 corners

    def test_corner_set_from_face_bottom(self) -> None:
        cs = Anchor.BOTTOM.to_corner_set()
        assert len(cs) == 8
        assert sum(cs) == 4

    def test_corner_set_from_face_left(self) -> None:
        cs = Anchor.LEFT.to_corner_set()
        assert sum(cs) == 4

    def test_corner_set_from_face_front(self) -> None:
        cs = Anchor.FRONT.to_corner_set()
        assert sum(cs) == 4

    def test_corner_set_from_corner(self) -> None:
        cs = Anchor.TOP_FRONT_LEFT.to_corner_set()
        assert len(cs) == 8
        assert sum(cs) == 1

    def test_corner_set_all(self) -> None:
        cs = Anchor.ALL.to_corner_set()
        assert cs == [1] * 8

    def test_corner_set_none(self) -> None:
        cs = Anchor.NONE.to_corner_set()
        assert cs == [0] * 8

    def test_corner_set_from_edge(self) -> None:
        cs = Anchor.TOP_FRONT.to_corner_set()
        assert sum(cs) == 2  # an edge has 2 corners


# ---------------------------------------------------------------------------
# Backward compat aliases
# ---------------------------------------------------------------------------


class TestBackwardCompatAliases:
    def test_edgeplane_is_anchor_alias(self) -> None:
        assert EdgePlane is Anchor

    def test_cornerplane_is_anchor_alias(self) -> None:
        assert CornerPlane is Anchor

    def test_edgeplane_members_work(self) -> None:
        assert EdgePlane.TOP is Anchor.TOP
        assert EdgePlane.X is Anchor.X
        assert EdgePlane.TOP_FRONT_LEFT is Anchor.TOP_FRONT_LEFT
        assert list(EdgePlane.TOP.vector) == [0.0, 0.0, 1.0]

    def test_cornerplane_members_work(self) -> None:
        assert CornerPlane.TOP is Anchor.TOP
        assert CornerPlane.BOTTOM_FRONT_RIGHT is Anchor.BOTTOM_FRONT_RIGHT
        assert list(CornerPlane.TOP_FRONT_LEFT.vector) == [-1.0, -1.0, 1.0]


# ---------------------------------------------------------------------------
# Edge selection helpers
# ---------------------------------------------------------------------------


class TestEdgeSet:
    def test_edge_set_with_string_x(self) -> None:
        matrix = _edge_set("X")
        assert len(matrix) == 3
        assert all(len(row) == 4 for row in matrix)

    def test_edge_set_with_string_y(self) -> None:
        matrix = _edge_set("Y")
        assert len(matrix) == 3
        assert all(len(row) == 4 for row in matrix)

    def test_edge_set_with_string_z(self) -> None:
        matrix = _edge_set("Z")
        assert len(matrix) == 3
        assert all(len(row) == 4 for row in matrix)

    def test_edge_set_with_anchor(self) -> None:
        matrix = _edge_set(Anchor.TOP)
        assert len(matrix) == 3
        assert all(len(row) == 4 for row in matrix)

    def test_edge_set_with_list_of_strings(self) -> None:
        spec: list[str] = ["X", "Y"]
        matrix = _edge_set(spec)  # type: ignore[arg-type]
        assert len(matrix) == 3
        assert any(v == 1 for row in matrix for v in row)

    def test_edge_set_with_string_all(self) -> None:
        matrix = _edge_set("ALL")
        assert matrix == EDGES_ALL

    def test_edge_set_with_string_none(self) -> None:
        matrix = _edge_set("NONE")
        assert matrix == EDGES_NONE

    def test_edge_set_with_empty_list(self) -> None:
        spec: list[Anchor] = [Anchor.NONE]
        matrix = _edge_set(spec)  # type: ignore[arg-type]
        assert matrix == EDGES_NONE


class TestEdges:
    def test_edges_with_anchor_all(self) -> None:
        matrix = edges(Anchor.ALL)
        assert matrix == EDGES_ALL

    def test_edges_with_except_z(self) -> None:
        matrix = edges(Anchor.ALL, except_=Anchor.Z)
        assert len(matrix) == 3
        assert all(len(row) == 4 for row in matrix)
        assert matrix != EDGES_ALL  # something was removed
        assert any(v == 1 for row in matrix for v in row)

    def test_edges_with_except_x(self) -> None:
        matrix_all = edges(Anchor.ALL)
        matrix_except = edges(Anchor.ALL, except_="X")
        assert matrix_except != matrix_all  # something was removed

    def test_edges_combines_multiple(self) -> None:
        matrix = edges(["X", "Y"])
        assert len(matrix) == 3
        assert all(len(row) == 4 for row in matrix)
        assert any(v == 1 for row in matrix for v in row)

    def test_edges_with_none(self) -> None:
        matrix = edges(Anchor.NONE)
        assert matrix == EDGES_NONE

    def test_edges_with_empty_list(self) -> None:
        matrix = edges([])
        assert matrix == EDGES_NONE


# ---------------------------------------------------------------------------
# String resolution
# ---------------------------------------------------------------------------


class TestResolveAnchor:
    def test_resolve_anchor_from_string_x(self) -> None:
        assert resolve_anchor("x") is Anchor.X

    def test_resolve_anchor_from_string_y(self) -> None:
        assert resolve_anchor("Y") is Anchor.Y

    def test_resolve_anchor_from_string_z(self) -> None:
        assert resolve_anchor("z") is Anchor.Z

    def test_resolve_anchor_from_string_all(self) -> None:
        assert resolve_anchor("ALL") is Anchor.ALL

    def test_resolve_anchor_from_string_none(self) -> None:
        assert resolve_anchor("none") is Anchor.NONE

    def test_resolve_anchor_from_legacy_string_top(self) -> None:
        assert resolve_anchor("top") is Anchor.TOP

    def test_resolve_anchor_from_legacy_string_bottom(self) -> None:
        assert resolve_anchor("bottom") is Anchor.BOTTOM

    def test_resolve_anchor_from_legacy_string_front(self) -> None:
        assert resolve_anchor("front") is Anchor.FRONT

    def test_resolve_anchor_from_legacy_string_left(self) -> None:
        assert resolve_anchor("left") is Anchor.LEFT

    def test_resolve_anchor_from_legacy_string_right(self) -> None:
        assert resolve_anchor("right") is Anchor.RIGHT

    def test_resolve_anchor_from_anchor_passthrough(self) -> None:
        assert resolve_anchor(Anchor.TOP) is Anchor.TOP

    def test_resolve_anchor_from_vector_float(self) -> None:
        assert resolve_anchor([0.0, 0.0, 1.0]) is Anchor.TOP

    def test_resolve_anchor_from_vector_int(self) -> None:
        vec: list[int | float] = [0, 0, 1]
        assert resolve_anchor(vec) is Anchor.TOP

    def test_resolve_anchor_from_vector_edge(self) -> None:
        vec: list[int | float] = [-1, -1, 0]
        assert resolve_anchor(vec) is Anchor.FRONT_LEFT

    def test_resolve_anchor_from_vector_corner(self) -> None:
        vec: list[int | float] = [-1, -1, 1]
        assert resolve_anchor(vec) is Anchor.TOP_FRONT_LEFT

    def test_resolve_anchor_unknown_string_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown anchor string"):
            resolve_anchor("nonsense")

    def test_resolve_anchor_unmatching_vector_raises(self) -> None:
        vec: list[int | float] = [2, 0, 0]
        with pytest.raises(ValueError, match="No Anchor member matches"):
            resolve_anchor(vec)

    def test_resolve_anchor_edge_matrix_raises(self) -> None:
        with pytest.raises(ValueError, match="raw edge matrix"):
            resolve_anchor(EDGES_ALL)


# ---------------------------------------------------------------------------
# CORNER_OFFSETS
# ---------------------------------------------------------------------------


class TestCornerOffsets:
    def test_corner_offsets_length(self) -> None:
        assert len(CORNER_OFFSETS) == 8

    def test_corner_offsets_are_unit(self) -> None:
        for c in CORNER_OFFSETS:
            assert all(abs(x) == 1.0 for x in c)

    def test_corner_offsets_all_unique(self) -> None:
        tuples = [tuple(c) for c in CORNER_OFFSETS]
        assert len(set(tuples)) == 8
