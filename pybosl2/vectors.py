# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/vectors.py
#    Pure-Python port of the pieces of BOSL2's vectors.scad that pybosl2/paths.py
#    depends on.  All vector-valued parameters accept :class:`~pybosl2.points.Point`
#    or any :class:`~collections.abc.Sequence` of floats.
#
# FileSummary: Vector predicates and scalar-vector operations (BOSL2 vectors.scad).
# DocCategory: Math & geometry
# FileGroup: BOSL2

import math
from collections.abc import Sequence

import numpy as np

from pybosl2.math import EPSILON
from pybosl2.points import Point


def is_vector(
    v: Point | Sequence[float] | np.ndarray,
    length: int | None = None,
    zero: bool | None = None,
    eps: float = EPSILON,
) -> bool:
    """True if *v* is a list/tuple/ndarray of finite numbers (optionally of a given length and/or
    zero-ness).
    """
    if isinstance(v, np.ndarray):
        if v.ndim != 1 or v.size == 0:
            return False
    elif not isinstance(v, (list, tuple)) or len(v) == 0:
        return False
    for x in v:
        if (
            isinstance(x, bool)
            or not isinstance(x, (int, float, np.floating, np.integer))
            or math.isinf(x)
            or math.isnan(x)
        ):
            return False
    if length is not None and len(v) != length:
        return False
    if zero is not None:
        is_zero = float(np.linalg.norm(np.asarray(v, dtype=float))) < eps
        if is_zero != zero:
            return False
    return True


def add_scalar(v: Point | Sequence[float] | np.ndarray, s: float) -> np.ndarray:
    """Return *v* with scalar *s* added to every entry."""
    return np.asarray(v, dtype=float) + s


def unit(
    v: Point | Sequence[float] | np.ndarray,
    error: Point | Sequence[float] | np.ndarray | None = None,
) -> np.ndarray:
    """Normalize *v* to unit length.

    If *v* has (near) zero length, returns *error* if given, else raises
    ValueError (matching BOSL2's default assert-on-zero-vector behavior).
    """
    arr = np.asarray(v, dtype=float)
    sides = float(np.linalg.norm(arr))
    if sides < EPSILON:
        if error is not None:
            return np.asarray(error, dtype=float)
        raise ValueError("Cannot normalize a zero vector")
    return arr / sides
