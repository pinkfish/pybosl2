# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# The cuboid edge-selector mini-language, mirroring BOSL2 attachments.scad.
# A single shared implementation used by BOTH solid backends (CSG and SDF),
# so there is one source of truth for edge/corner selectors.
#
# The public API is :class:`EdgePlane` and :class:`CornerPlane` enums;
# the internal 3×4 integer matrix representation is still used for
# geometry computation but is no longer exposed publicly.

from __future__ import annotations

from enum import Enum

# -- internal edge-matrix constants (shared by both backends) -------------------

EDGES_ALL: list[list[int]] = [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]
EDGES_NONE: list[list[int]] = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]

EDGE_OFFSETS: list[list[list[float]]] = [
    [[0.0, -1.0, -1.0], [0.0, 1.0, -1.0], [0.0, -1.0, 1.0], [0.0, 1.0, 1.0]],
    [[-1.0, 0.0, -1.0], [1.0, 0.0, -1.0], [-1.0, 0.0, 1.0], [1.0, 0.0, 1.0]],
    [[-1.0, -1.0, 0.0], [1.0, -1.0, 0.0], [-1.0, 1.0, 0.0], [1.0, 1.0, 0.0]],
]

# -- corner offsets (ordered [xa, ya, za] for za in (-1,1) for ya in (-1,1) for xa in (-1,1))
CORNER_OFFSETS: list[list[float]] = [[xa, ya, za] for za in (-1.0, 1.0) for ya in (-1.0, 1.0) for xa in (-1.0, 1.0)]

_MAJOR_AXIS_VALID = ["X", "Y", "Z", "ALL", "NONE"]


# -- public enums --------------------------------------------------------------


class EdgePlane(Enum):
    """Selects edges on a cuboid by axis, face, or set.

    Use as arguments to :meth:`~pybosl2.shapes3d.Bosl2Solid.edge_mask`,
    :meth:`~pybosl2.shapes3d.Bosl2Solid.edge_profile`, etc.
    """

    ALL = "all"
    NONE = "none"
    X = "x"
    Y = "y"
    Z = "z"
    TOP = "top"
    BOTTOM = "bottom"
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"
    TOP_FRONT = "top_front"
    TOP_BACK = "top_back"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_FRONT = "bottom_front"
    BOTTOM_BACK = "bottom_back"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class CornerPlane(Enum):
    """Selects corners on a cuboid by position.

    Use as arguments to :meth:`~pybosl2.shapes3d.Bosl2Solid.corner_profile`.
    """

    ALL = "all"
    NONE = "none"
    TOP = "top"
    BOTTOM = "bottom"
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"

    # Specific corner positions — use integer values so auto() works
    TOP_FRONT_LEFT = 0
    TOP_FRONT_RIGHT = 1
    TOP_BACK_LEFT = 2
    TOP_BACK_RIGHT = 3
    BOTTOM_FRONT_LEFT = 4
    BOTTOM_FRONT_RIGHT = 5
    BOTTOM_BACK_LEFT = 6
    BOTTOM_BACK_RIGHT = 7


# -- internal conversion helpers -----------------------------------------------


def _is_edge_matrix(x: object) -> bool:
    return isinstance(x, list) and len(x) == 3 and all(isinstance(row, list) and len(row) == 4 for row in x)


# Backwards-compatible alias
_is_edge_array = _is_edge_matrix


def _edge_plane_to_matrix(ep: EdgePlane) -> list[list[int]]:
    """Convert an :class:`EdgePlane` to the internal 3×4 integer matrix."""
    return _edge_set(ep.value if isinstance(ep, EdgePlane) else ep)


def _corner_plane_to_set(cp: CornerPlane | str | list[int]) -> list[int]:
    """Convert a :class:`CornerPlane` or legacy spec to an 8-element boolean list."""
    if isinstance(cp, CornerPlane):
        if cp == CornerPlane.ALL:
            return [1] * 8
        if cp == CornerPlane.NONE:
            return [0] * 8
        # Face-based selection: all corners on a face
        if cp in (
            CornerPlane.TOP,
            CornerPlane.BOTTOM,
            CornerPlane.FRONT,
            CornerPlane.BACK,
            CornerPlane.LEFT,
            CornerPlane.RIGHT,
        ):
            idx = {"top": 2, "bottom": 2, "front": 1, "back": 1, "left": 0, "right": 0}
            sign = {"top": 1, "bottom": -1, "front": 1, "back": -1, "left": -1, "right": 1}
            name = cp.name.lower()
            axis, s = idx.get(name, 0), sign.get(name, 1)
            return [1 if c[axis] == s else 0 for c in CORNER_OFFSETS]
        # Specific corner (value 0-7 maps to CORNER_OFFSETS index)
        if isinstance(cp.value, int) and 0 <= cp.value < 8:
            result = [0] * 8
            result[cp.value] = 1
            return result
        raise ValueError(f"CornerPlane {cp} could not be resolved")
    if isinstance(cp, str):
        if cp == "ALL":
            return [1] * 8
        if cp == "NONE":
            return [0] * 8
        raise ValueError(f'{cp} must be "ALL", "NONE", or a vector')
    arr = cp
    return [1 if all(c[i] == 0 or c[i] == arr[i] for i in range(3)) else 0 for c in CORNER_OFFSETS]


def _edge_set(v: EdgePlane | str | list[int] | list[list[int]]) -> list[list[int]]:
    """Convert an edge specifier to the internal 3×4 integer matrix.

    Args:
        v: An :class:`EdgePlane`, a legacy string (``"X"``, ``"ALL"``, etc.),
           an edge vector like ``[0, 1, -1]``, or a precomputed edge matrix.

    Returns:
        A ``[[int×4],[int×4],[int×4]]`` edge matrix.
    """
    if isinstance(v, EdgePlane):
        v = v.value
    if _is_edge_matrix(v):
        return v  # type: ignore[return-value]
    out: list[list[int]] = []
    for ax in range(3):
        row: list[int] = []
        for b in (-1, 1):
            for a in (-1, 1):
                v2 = [[0, a, b], [a, 0, b], [a, b, 0]][ax]
                if isinstance(v, str):
                    v_lower = v.lower()
                    if v_lower == "x":
                        matched = ax == 0
                    elif v_lower == "y":
                        matched = ax == 1
                    elif v_lower == "z":
                        matched = ax == 2
                    elif v_lower == "all":
                        matched = True
                    elif v_lower == "none":
                        matched = False
                    else:
                        raise ValueError(f"{v} must be a vector, edge array, or EdgePlane value")
                else:
                    nonz = sum(abs(x) for x in v)  # type: ignore[arg-type, misc]
                    if nonz == 2:
                        matched = list(v) == v2
                    else:
                        matches = sum(1 for i in range(3) if v[i] and v[i] == v2[i])
                        matched = matches == (1 if nonz == 1 else 2)
                row.append(1 if matched else 0)
        out.append(row)
    return out


def _edges(
    v: EdgePlane | str | list | list[list[int]],
    except_: EdgePlane | str | list | list[list[int]] | None = None,
) -> list[list[int]]:
    """Resolve edge selectors to a 3×4 integer matrix, with optional exclusion.

    Args:
        v: An :class:`EdgePlane`, legacy string, edge vector, or list thereof.
        except_: Edges to exclude, same forms.

    Returns:
        A ``[[int×4],[int×4],[int×4]]`` edge matrix.
    """
    if except_ is None:
        except_ = []
    if v == [] or v == EdgePlane.NONE:
        return EDGES_NONE
    if isinstance(v, (EdgePlane, str)) or _is_edge_matrix(v) or _is_plain_vector(v):
        return _edges([v], except_)
    if isinstance(except_, (EdgePlane, str)) or _is_edge_matrix(except_) or _is_plain_vector(except_):
        return _edges(v, [except_])
    summed: list[list[int]] = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    for x in v:
        es = _edge_set(x)
        for ax in range(3):
            for i in range(4):
                summed[ax][i] += es[ax][i]
    normed = [[1 if summed[ax][i] > 0 else 0 for i in range(4)] for ax in range(3)]
    if not except_:
        return normed
    exc: list[list[int]] = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    for x in except_:
        es = _edge_set(x)
        for ax in range(3):
            for i in range(4):
                exc[ax][i] += es[ax][i]
    return [[1 if (normed[ax][i] - (1 if exc[ax][i] > 0 else 0)) > 0 else 0 for i in range(4)] for ax in range(3)]


def _is_plain_vector(v: object) -> bool:
    return (
        isinstance(v, list) and len(v) > 0 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)
    )
