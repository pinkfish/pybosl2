# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/_helpers.py: internal helper functions."""

import numpy as np
import pytest

from pybosl2._helpers import (
    frame_map4_yz,
    is_num,
    rot_from_to4,
    scalar_vec3,
    translate4,
    unit,
    unwrap,
    vec3,
    zrot4,
)

# ---------------------------------------------------------------------------
# is_num
# ---------------------------------------------------------------------------


class TestIsNum:
    def test_is_num_int(self) -> None:
        assert is_num(3) is True
        assert is_num(0) is True
        assert is_num(-1) is True

    def test_is_num_float(self) -> None:
        assert is_num(3.14) is True
        assert is_num(0.0) is True
        assert is_num(-2.5) is True

    def test_is_num_not_string(self) -> None:
        assert is_num("a") is False
        assert is_num("3") is False

    def test_is_num_not_bool(self) -> None:
        assert is_num(True) is False
        assert is_num(False) is False

    def test_is_num_not_list(self) -> None:
        assert is_num([1, 2, 3]) is False

    def test_is_num_numpy_float64(self) -> None:
        assert is_num(np.float64(3.14)) is True

    def test_is_num_numpy_int32(self) -> None:
        assert is_num(np.int32(5)) is True

    def test_is_num_numpy_int64(self) -> None:
        assert is_num(np.int64(10)) is True

    def test_is_num_numpy_bool_false(self) -> None:
        assert is_num(np.bool_(True)) is False

    def test_is_num_none(self) -> None:
        assert is_num(None) is False


# ---------------------------------------------------------------------------
# vec3
# ---------------------------------------------------------------------------


class TestVec3:
    def test_vec3_from_list_3(self) -> None:
        result = vec3([1, 2, 3])
        np.testing.assert_allclose(result, [1, 2, 3])

    def test_vec3_from_tuple_2(self) -> None:
        result = vec3((1, 2))
        np.testing.assert_allclose(result, [1, 2, 0])

    def test_vec3_from_scalar(self) -> None:
        result = vec3(5)
        np.testing.assert_allclose(result, [5, 5, 5])

    def test_vec3_from_scalar_float(self) -> None:
        result = vec3(3.5)
        np.testing.assert_allclose(result, [3.5, 3.5, 3.5])

    def test_vec3_returns_fresh_float_array(self) -> None:
        # Callers slice and mutate the result (e.g. partitions' `unit(...)[:2]`), so it has to be
        # a float64 array of its own, never a view onto the caller's data.
        src = np.array([1, 2, 3])
        result = vec3(src)
        assert result.dtype == np.float64
        assert not np.shares_memory(result, src)
        result[0] = 99
        np.testing.assert_allclose(src, [1, 2, 3])

    def test_vec3_shape(self) -> None:
        assert vec3([1, 2, 3]).shape == (3,)
        assert vec3([1, 2]).shape == (3,)
        assert vec3(0).shape == (3,)


# ---------------------------------------------------------------------------
# scalar_vec3
# ---------------------------------------------------------------------------


class TestScalarVec3:
    def test_scalar_vec3_from_scalar(self) -> None:
        result = scalar_vec3(5)
        np.testing.assert_allclose(result, [5, 0, 0])

    def test_scalar_vec3_from_scalar_with_fill(self) -> None:
        result = scalar_vec3(5, fill=1.0)
        np.testing.assert_allclose(result, [5, 1, 1])

    def test_scalar_vec3_from_list_2(self) -> None:
        result = scalar_vec3([1, 2])
        np.testing.assert_allclose(result, [1, 2, 0])

    def test_scalar_vec3_from_list_3(self) -> None:
        result = scalar_vec3([1, 2, 3])
        np.testing.assert_allclose(result, [1, 2, 3])

    def test_scalar_vec3_returns_fresh_float_array(self) -> None:
        src = np.array([1, 2, 3])
        result = scalar_vec3(src)
        assert result.dtype == np.float64
        assert not np.shares_memory(result, src)
        np.testing.assert_allclose(result, [1, 2, 3])
        assert scalar_vec3(5).dtype == np.float64  # int scalars are widened too

    def test_scalar_vec3_shape(self) -> None:
        assert scalar_vec3(5).shape == (3,)


# ---------------------------------------------------------------------------
# unit (vector normalization)
# ---------------------------------------------------------------------------


class TestUnit:
    def test_unit_2d(self) -> None:
        result = unit([3, 4])
        np.testing.assert_allclose(result, [0.6, 0.8])

    def test_unit_3d_positive(self) -> None:
        result = unit([0, 0, 5])
        np.testing.assert_allclose(result, [0, 0, 1])

    def test_unit_3d_general(self) -> None:
        result = unit([1, 2, 2])
        norm_mag = np.linalg.norm([1, 2, 2])
        expected = np.array([1, 2, 2]) / norm_mag
        np.testing.assert_allclose(result, expected)

    def test_unit_zero_vector_returns_zero(self) -> None:
        result = unit([0, 0, 0])
        np.testing.assert_allclose(result, [0, 0, 0])

    def test_unit_returns_unit_length(self) -> None:
        result = unit([3, 4, 0])
        assert pytest.approx(float(np.linalg.norm(result))) == 1.0

    def test_unit_returns_fresh_float_array(self) -> None:
        src = np.array([1.0, 2.0, 3.0])
        result = unit(src)
        assert result.dtype == np.float64
        assert not np.shares_memory(result, src)
        np.testing.assert_allclose(src, [1.0, 2.0, 3.0])  # input left unnormalised
        np.testing.assert_allclose(result, src / np.linalg.norm(src))


# ---------------------------------------------------------------------------
# zrot4
# ---------------------------------------------------------------------------


class TestZrot4:
    def test_zrot4_identity(self) -> None:
        result = zrot4(0)
        np.testing.assert_allclose(result, np.eye(4))

    def test_zrot4_90deg(self) -> None:
        result = zrot4(90)
        v = np.array([1, 0, 0, 1])
        rotated = result @ v
        np.testing.assert_allclose(rotated[:3], [0, 1, 0], atol=1e-15)

    def test_zrot4_180deg(self) -> None:
        result = zrot4(180)
        v = np.array([1, 0, 0, 1])
        rotated = result @ v
        np.testing.assert_allclose(rotated[:3], [-1, 0, 0], atol=1e-15)

    def test_zrot4_270deg(self) -> None:
        result = zrot4(270)
        v = np.array([1, 0, 0, 1])
        rotated = result @ v
        np.testing.assert_allclose(rotated[:3], [0, -1, 0], atol=1e-15)

    def test_zrot4_z_axis_unchanged(self) -> None:
        result = zrot4(45)
        v = np.array([0, 0, 1, 1])
        rotated = result @ v
        np.testing.assert_allclose(rotated[:3], [0, 0, 1], atol=1e-15)

    def test_zrot4_is_4x4(self) -> None:
        result = zrot4(30)
        assert result.shape == (4, 4)

    def test_zrot4_translation_zero(self) -> None:
        result = zrot4(60)
        np.testing.assert_allclose(result[:3, 3], [0, 0, 0])
        assert result[3, 3] == 1.0


# ---------------------------------------------------------------------------
# rot_from_to4
# ---------------------------------------------------------------------------


class TestRotFromTo4:
    def test_rot_from_to4_identity(self) -> None:
        result = rot_from_to4([1, 0, 0], [1, 0, 0])
        np.testing.assert_allclose(result, np.eye(4), atol=1e-14)

    def test_rot_from_to4_x_to_y(self) -> None:
        result = rot_from_to4([1, 0, 0], [0, 1, 0])
        v = np.array([1, 0, 0, 1])
        rotated = result @ v
        np.testing.assert_allclose(rotated[:3], [0, 1, 0], atol=1e-14)

    def test_rot_from_to4_y_to_z(self) -> None:
        result = rot_from_to4([0, 1, 0], [0, 0, 1])
        v = np.array([0, 1, 0, 1])
        rotated = result @ v
        np.testing.assert_allclose(rotated[:3], [0, 0, 1], atol=1e-14)

    def test_rot_from_to4_antiparallel(self) -> None:
        result = rot_from_to4([1, 0, 0], [-1, 0, 0])
        v = np.array([1, 0, 0, 1])
        rotated = result @ v
        np.testing.assert_allclose(rotated[:3], [-1, 0, 0], atol=1e-14)

    def test_rot_from_to4_is_4x4(self) -> None:
        result = rot_from_to4([1, 0, 0], [0, 1, 0])
        assert result.shape == (4, 4)

    def test_rot_from_to4_translation_zero(self) -> None:
        result = rot_from_to4([1, 0, 0], [0, 0, 1])
        np.testing.assert_allclose(result[:3, 3], [0, 0, 0])
        assert result[3, 3] == 1.0


# ---------------------------------------------------------------------------
# translate4
# ---------------------------------------------------------------------------


class TestTranslate4:
    def test_translate4_basic(self) -> None:
        result = translate4([1, 2, 3])
        expected = np.eye(4)
        expected[:3, 3] = [1, 2, 3]
        np.testing.assert_allclose(result, expected)

    def test_translate4_2d(self) -> None:
        result = translate4([1, 2])
        expected = np.eye(4)
        expected[:3, 3] = [1, 2, 0]
        np.testing.assert_allclose(result, expected)

    def test_translate4_applies_to_point(self) -> None:
        t = translate4([10, 20, 30])
        v = np.array([0, 0, 0, 1])
        result = t @ v
        np.testing.assert_allclose(result[:3], [10, 20, 30])

    def test_translate4_is_4x4(self) -> None:
        assert translate4([1, 2, 3]).shape == (4, 4)

    def test_translate4_rotation_part_is_identity(self) -> None:
        result = translate4([5, 5, 5])
        np.testing.assert_allclose(result[:3, :3], np.eye(3))


# ---------------------------------------------------------------------------
# frame_map4_yz
# ---------------------------------------------------------------------------


class TestFrameMap4Yz:
    def test_frame_map4_yz_identity(self) -> None:
        result = frame_map4_yz([0, 1, 0], [0, 0, 1])
        np.testing.assert_allclose(result, np.eye(4), atol=1e-14)

    def test_frame_map4_yz_90deg_x(self) -> None:
        result = frame_map4_yz([0, 0, 1], [0, -1, 0])
        v = np.array([0, 1, 0, 1])
        rotated = result @ v
        np.testing.assert_allclose(rotated[:3], [0, 0, 1], atol=1e-14)

    def test_frame_map4_yz_is_4x4(self) -> None:
        assert frame_map4_yz([0, 1, 0], [0, 0, 1]).shape == (4, 4)

    def test_frame_map4_yz_orthonormal(self) -> None:
        result = frame_map4_yz([1, 1, 0], [0, 0, 1])
        for i in range(3):
            col = result[:3, i]
            assert pytest.approx(float(np.linalg.norm(col))) == 1.0


# ---------------------------------------------------------------------------
# unwrap
# ---------------------------------------------------------------------------


class TestUnwrap:
    def test_unwrap_plain_int(self) -> None:
        assert unwrap(42) == 42

    def test_unwrap_plain_float(self) -> None:
        assert unwrap(3.14) == 3.14

    def test_unwrap_plain_string(self) -> None:
        assert unwrap("hello") == "hello"

    def test_unwrap_numpy_array(self) -> None:
        arr = np.array([1, 2, 3])
        result = unwrap(arr)
        np.testing.assert_allclose(result, arr)
