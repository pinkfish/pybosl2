# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# The cuboid() edge-selector mini-language, mirroring BOSL2 attachments.scad. A single shared
# implementation used by BOTH solid backends: pybosl2.shapes3d (CSG) and pybosl2._sdf (SDF) each import
# it from here, so there is one source of truth for edge selectors and neither backend has to depend
# on the other's shape module. Pure Python (no numpy, no native runtime).

from __future__ import annotations

EDGES_ALL = [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]
EDGES_NONE = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]

# The vector pointing to the center of each edge of a unit cube; EDGE_OFFSETS[axis][i]
# corresponds to edges[axis][i] in the edge-set representation above.
EDGE_OFFSETS = [
    [[0, -1, -1], [0, 1, -1], [0, -1, 1], [0, 1, 1]],
    [[-1, 0, -1], [1, 0, -1], [-1, 0, 1], [1, 0, 1]],
    [[-1, -1, 0], [1, -1, 0], [-1, 1, 0], [1, 1, 0]],
]

_MAJOR_AXIS_VALID = ["X", "Y", "Z", "ALL", "NONE"]


def _is_edge_array(x) -> bool:
    return isinstance(x, list) and len(x) == 3 and all(isinstance(row, list) and len(row) == 4 for row in x)


def _edge_set(v) -> list[list[int]]:
    if _is_edge_array(v):
        return v
    out = []
    for ax in range(3):
        row = []
        for b in (-1, 1):
            for a in (-1, 1):
                v2 = [[0, a, b], [a, 0, b], [a, b, 0]][ax]
                if isinstance(v, str):
                    if v == "X":
                        matched = ax == 0
                    elif v == "Y":
                        matched = ax == 1
                    elif v == "Z":
                        matched = ax == 2
                    elif v == "ALL":
                        matched = True
                    elif v == "NONE":
                        matched = False
                    else:
                        raise ValueError(f"{v} must be a vector, edge array, or one of {_MAJOR_AXIS_VALID}")
                else:
                    nonz = sum(abs(x) for x in v)
                    if nonz == 2:
                        matched = list(v) == v2
                    else:
                        matches = sum(1 for i in range(3) if v[i] and v[i] == v2[i])
                        matched = matches == (1 if nonz == 1 else 2)
                row.append(1 if matched else 0)
        out.append(row)
    return out


def _is_plain_vector(v) -> bool:
    return (
        isinstance(v, list) and len(v) > 0 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)
    )


def _edges(v, except_: list | None = None) -> list[list[int]]:
    if except_ is None:
        except_ = []
    if v == []:
        return EDGES_NONE
    if isinstance(v, str) or _is_edge_array(v) or _is_plain_vector(v):
        return _edges([v], except_)
    if isinstance(except_, str) or _is_edge_array(except_) or _is_plain_vector(except_):
        return _edges(v, [except_])
    summed = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    for x in v:
        es = _edge_set(x)
        for ax in range(3):
            for i in range(4):
                summed[ax][i] += es[ax][i]
    normed = [[1 if summed[ax][i] > 0 else 0 for i in range(4)] for ax in range(3)]
    if not except_:
        return normed
    exc = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    for x in except_:
        es = _edge_set(x)
        for ax in range(3):
            for i in range(4):
                exc[ax][i] += es[ax][i]
    return [[1 if (normed[ax][i] - (1 if exc[ax][i] > 0 else 0)) > 0 else 0 for i in range(4)] for ax in range(3)]
