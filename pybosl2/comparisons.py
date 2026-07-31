# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/comparisons.py
#    BOSL2 approximate-equality module.  The ``approx`` function that was
#    previously defined here has been removed in favour of direct calls to
#    :func:`math.isclose` (scalars) and :func:`numpy.allclose` (vectors) at
#    each call site — all callers were always passing same-length arrays and
#    the different-length-vector guard was never exercised, so the custom
#    wrapper added no value.
#
# FileSummary: Approximate-equality primitives (see math.isclose / numpy.allclose).
# DocCategory: Math & geometry
# FileGroup: BOSL2

from pybosl2.math import EPSILON

__all__ = ["EPSILON"]
