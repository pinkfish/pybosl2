# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/_edges_lang.py
#    Unified anchor/edge/corner selector enum used by all 3-D anchor, attach,
#    align, position, reorient, and edge-masking operations.  Each :class:`Anchor`
#    member stores its own 3-D vector (a :class:`~pybosl2.points.Vector`) so every
#    public API only asks for the enum -- the vector is resolved internally.
#    ``Anchor.TOP_LEFT`` is an edge (two faces meet); ``Anchor.TOP_FRONT_LEFT``
#    is a corner (three faces meet).
#
#    Legacy :class:`EdgePlane` and :class:`CornerPlane` are kept as thin aliases
#    so existing code does not break.
#
# FileSummary: Unified anchor/edge/corner selector enum (faces, edges, corners, axes).
# DocCategory: Foundational
# FileGroup: BOSL2

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pybosl2.points import Point

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

# -- internal edge-matrix constants (shared by both backends) -------------------

EDGES_ALL: list[list[int]] = [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]
EDGES_NONE: list[list[int]] = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]

EDGE_OFFSETS: list[list[list[float]]] = [
    [[0.0, -1.0, -1.0], [0.0, 1.0, -1.0], [0.0, -1.0, 1.0], [0.0, 1.0, 1.0]],
    [[-1.0, 0.0, -1.0], [1.0, 0.0, -1.0], [-1.0, 0.0, 1.0], [1.0, 0.0, 1.0]],
    [[-1.0, -1.0, 0.0], [1.0, -1.0, 0.0], [-1.0, 1.0, 0.0], [1.0, 1.0, 0.0]],
]

CORNER_OFFSETS: list[list[float]] = [[xa, ya, za] for za in (-1.0, 1.0) for ya in (-1.0, 1.0) for xa in (-1.0, 1.0)]


# -- public Anchor enum --------------------------------------------------------


class Anchor(Enum):
    """A single selector for a face, edge, corner, or axis set on a 3-D solid.

    Every member carries its own 3-D anchor vector as a :class:`Point`.
    Pass an ``Anchor`` wherever a public API asks for an anchor, edge set, or
    corner set -- the vector is resolved internally.

    **Faces** (two axes are zero):
      ``CENTER``, ``TOP``, ``BOTTOM``, ``FRONT``, ``BACK``, ``LEFT``, ``RIGHT``

    **Edges** (one axis is zero -- where two named faces meet):
      ``TOP_FRONT``, ``TOP_BACK``, ``TOP_LEFT``, ``TOP_RIGHT``,
      ``BOTTOM_FRONT``, ``BOTTOM_BACK``, ``BOTTOM_LEFT``, ``BOTTOM_RIGHT``,
      ``FRONT_LEFT``, ``FRONT_RIGHT``, ``BACK_LEFT``, ``BACK_RIGHT``

    **Corners** (all three axes ±1):
      ``TOP_FRONT_LEFT``, ``TOP_FRONT_RIGHT``, ``TOP_BACK_LEFT``,
      ``TOP_BACK_RIGHT``, ``BOTTOM_FRONT_LEFT``, ``BOTTOM_FRONT_RIGHT``,
      ``BOTTOM_BACK_LEFT``, ``BOTTOM_BACK_RIGHT``

    **Axis presets** (for edge selection on cuboids):
      ``ALL``, ``NONE``, ``X``, ``Y``, ``Z``
    """

    # ---- faces ---------------------------------------------------------------
    CENTER = (0.0, 0.0, 0.0)
    TOP = (0.0, 0.0, 1.0)
    BOTTOM = (0.0, 0.0, -1.0)
    FRONT = (0.0, -1.0, 0.0)
    BACK = (0.0, 1.0, 0.0)
    LEFT = (-1.0, 0.0, 0.0)
    RIGHT = (1.0, 0.0, 0.0)

    # ---- edges (two faces meet) ----------------------------------------------
    TOP_FRONT = (0.0, -1.0, 1.0)
    TOP_BACK = (0.0, 1.0, 1.0)
    TOP_LEFT = (-1.0, 0.0, 1.0)
    TOP_RIGHT = (1.0, 0.0, 1.0)
    BOTTOM_FRONT = (0.0, -1.0, -1.0)
    BOTTOM_BACK = (0.0, 1.0, -1.0)
    BOTTOM_LEFT = (-1.0, 0.0, -1.0)
    BOTTOM_RIGHT = (1.0, 0.0, -1.0)
    FRONT_LEFT = (-1.0, -1.0, 0.0)
    FRONT_RIGHT = (1.0, -1.0, 0.0)
    BACK_LEFT = (-1.0, 1.0, 0.0)
    BACK_RIGHT = (1.0, 1.0, 0.0)

    # ---- corners (three faces meet) ------------------------------------------
    TOP_FRONT_LEFT = (-1.0, -1.0, 1.0)
    TOP_FRONT_RIGHT = (1.0, -1.0, 1.0)
    TOP_BACK_LEFT = (-1.0, 1.0, 1.0)
    TOP_BACK_RIGHT = (1.0, 1.0, 1.0)
    BOTTOM_FRONT_LEFT = (-1.0, -1.0, -1.0)
    BOTTOM_FRONT_RIGHT = (1.0, -1.0, -1.0)
    BOTTOM_BACK_LEFT = (-1.0, 1.0, -1.0)
    BOTTOM_BACK_RIGHT = (1.0, 1.0, -1.0)

    # ---- axis presets (edge selection only) ----------------------------------
    ALL = "all"
    NONE = "none"
    X = "x"
    Y = "y"
    Z = "z"

    @property
    def vector(self) -> Point:
        """The 3-D anchor vector ``(±1 or 0, ±1 or 0, ±1 or 0)``.

        Raises:
            TypeError: For axis presets (``ALL``, ``NONE``, ``X``, ``Y``, ``Z``)
                       that don't represent a geometric point.
        """
        if isinstance(self.value, str):
            raise TypeError(f"Anchor.{self.name} is an axis preset, not a point -- use an edge/face/corner member")
        return Point(self.value)

    @property
    def is_face(self) -> bool:
        """True when exactly one axis is non-zero (a face centre)."""
        if isinstance(self.value, str):
            return False
        nz = sum(1 for v in self.value if v != 0)
        return nz == 1 or nz == 0  # CENTER also counts as face-ish

    @property
    def vector_2d(self) -> Point:
        """The 2-D anchor vector ``(x, y)`` using the OpenSCAD 2-D convention.

        Maps the 3-D anchor to a 2-D point where the Y axis of the 2-D plane
        receives contributions from both the 3-D Y and Z axes (Z becomes
        ``+Y`` in 2-D, matching OpenSCAD's native 2-D anchor behaviour).

        Raises:
            TypeError: For axis presets (``ALL``, ``NONE``, ``X``, ``Y``, ``Z``).
        """
        v = self.vector
        return Point((v[0], v[1] + v[2]))

    @property
    def is_edge(self) -> bool:
        """True when exactly two axes are non-zero (an edge midpoint)."""
        if isinstance(self.value, str):
            return False
        return sum(1 for v in self.value if v != 0) == 2

    @property
    def is_corner(self) -> bool:
        """True when all three axes are non-zero (a corner)."""
        if isinstance(self.value, str):
            return False
        return sum(1 for v in self.value if v != 0) == 3

    def __iter__(self) -> "Iterator[float]":
        """Iterate over the anchor vector components (x, y, z).

        Raises:
            TypeError: For axis presets that don't represent a geometric point.
        """
        if isinstance(self.value, str):
            raise TypeError(f"Anchor.{self.name} is an axis preset, not iterable")
        return iter(self.value)

    def __getitem__(self, index: int) -> float:
        """Access an anchor vector component by index.

        Raises:
            TypeError: For axis presets that don't represent a geometric point.
        """
        if isinstance(self.value, str):
            raise TypeError(f"Anchor.{self.name} is an axis preset, not indexable")
        return float(self.value[index])

    def __len__(self) -> int:
        """Return 3 for geometric anchor members.

        Raises:
            TypeError: For axis presets that don't represent a geometric point.
        """
        if isinstance(self.value, str):
            raise TypeError(f"Anchor.{self.name} is an axis preset, has no length")
        return 3

    def __add__(self, other: Anchor) -> Point:
        """Elementwise sum of two anchor vectors, e.g. ``Anchor.TOP + Anchor.FRONT``."""
        return self.vector + other.vector

    def to_edge_matrix(self) -> list[list[int]]:
        """Convert this anchor to the internal 3×4 edge-selection matrix.

        Only meaningful for faces (``TOP``, ``FRONT``, …), axis presets
        (``X``, ``Y``, ``Z``, ``ALL``, ``NONE``), or lists thereof.
        For a single edge/corner this resolves to the edge(s) sharing that
        geometric feature.
        """
        return _anchor_to_edge_matrix(self)

    def to_corner_set(self) -> list[int]:
        """Convert this anchor to an 8-element boolean corner-selection list."""
        return _anchor_to_corner_set(self)


# -- backward-compatible aliases -----------------------------------------------

# EdgePlane and CornerPlane are backward-compatible aliases for Anchor.
# Enum subclasses cannot extend an enum that already has members, so we
# alias at the module level rather than subclassing.
EdgePlane = Anchor
CornerPlane = Anchor
# -- internal conversion helpers -----------------------------------------------


_STR_EDGE_MAP: dict[str, Anchor] = {
    "x": Anchor.X,
    "y": Anchor.Y,
    "z": Anchor.Z,
    "all": Anchor.ALL,
    "none": Anchor.NONE,
    "X": Anchor.X,
    "Y": Anchor.Y,
    "Z": Anchor.Z,
    "ALL": Anchor.ALL,
    "NONE": Anchor.NONE,
}


# Map legacy string face/corner names to Anchor members
_LEGACY_CORNER_MAP: dict[str, Anchor] = {
    "all": Anchor.ALL,
    "none": Anchor.NONE,
    "top": Anchor.TOP,
    "bottom": Anchor.BOTTOM,
    "front": Anchor.FRONT,
    "back": Anchor.BACK,
    "left": Anchor.LEFT,
    "right": Anchor.RIGHT,
}


def _is_edge_matrix(x: object) -> bool:
    return isinstance(x, list) and len(x) == 3 and all(isinstance(row, list) and len(row) == 4 for row in x)


_is_edge_array = _is_edge_matrix


def _is_plain_vector(v: object) -> bool:
    return (
        isinstance(v, (list, Point))
        and len(v) > 0
        and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)
    )


def _vector_to_edge_set(v: Sequence[int | float]) -> list[list[int]]:
    """Convert a legacy edge vector ``[axis, d1, d2]`` to the 3×4 edge matrix."""
    out: list[list[int]] = []
    for ax in range(3):
        row: list[int] = []
        for b in (-1, 1):
            for a in (-1, 1):
                v2 = [[0, a, b], [a, 0, b], [a, b, 0]][ax]
                nonz = sum(abs(x) for x in v)
                if nonz == 2:
                    matched = list(v) == v2
                else:
                    matches = sum(1 for i in range(3) if v[i] and v[i] == v2[i])
                    matched = matches == (1 if nonz == 1 else 2)
                row.append(1 if matched else 0)
        out.append(row)
    return out


def _anchor_to_edge_matrix(anchor: Anchor) -> list[list[int]]:
    """Resolve a single :class:`Anchor` to the 3×4 edge matrix."""
    if anchor == Anchor.ALL:
        return EDGES_ALL
    if anchor == Anchor.NONE:
        return EDGES_NONE
    if anchor == Anchor.X:
        return _vector_to_edge_set([0, 1, 1])
    if anchor == Anchor.Y:
        return _vector_to_edge_set([1, 0, 1])
    if anchor == Anchor.Z:
        return _vector_to_edge_set([1, 1, 0])
    # Faces: single non-zero axis
    try:
        v = anchor.vector
    except TypeError:
        raise ValueError(f"Anchor.{anchor.name} cannot be converted to edge matrix") from None
    nz_count = sum(1 for x in v if x != 0)
    if nz_count == 1:
        # Face: select all edges on that face
        vec: list[int] = [int(v[0]), int(v[1]), int(v[2])]
        return _vector_to_edge_set(vec)
    if nz_count == 2:
        # Edge: select just that specific edge
        vec = [int(v[0]), int(v[1]), int(v[2])]
        return _vector_to_edge_set(vec)
    # Corner or CENTER -- no edges
    return EDGES_NONE


def _anchor_to_corner_set(anchor: Anchor) -> list[int]:
    """Resolve a single :class:`Anchor` to an 8-element boolean corner list."""
    if anchor == Anchor.ALL:
        return [1] * 8
    if anchor == Anchor.NONE:
        return [0] * 8
    try:
        v = anchor.vector
    except TypeError:
        raise ValueError(f"Anchor.{anchor.name} cannot be converted to corner set") from None
    # Match: each CORNER_OFFSET entry whose signed axes equal or are superset of the selector
    return [1 if all(v[i] == 0 or v[i] == c[i] for i in range(3)) else 0 for c in CORNER_OFFSETS]


def resolve_anchor(anchor: Anchor | str | list[int | float] | list[list[int]]) -> Anchor:
    """Normalize any anchor specifier (enum, string, legacy vector) to an Anchor enum.

    Args:
        anchor: An anchor specifier -- :class:`Anchor` enum, a string name, or a legacy vector.

    Returns:
        An :class:`Anchor` member.

    Raises:
        ValueError: If the specifier is unrecognised.
    """
    if isinstance(anchor, Anchor):
        return anchor
    if isinstance(anchor, str):
        candidate = _STR_EDGE_MAP.get(anchor)
        if candidate is None:
            candidate = _LEGACY_CORNER_MAP.get(anchor.lower())
        if candidate is not None:
            return candidate
        raise ValueError(f"Unknown anchor string: {anchor!r}")
    if _is_edge_matrix(anchor):
        raise ValueError("Cannot resolve a raw edge matrix to a single Anchor; use a list of Anchors instead.")
    if _is_plain_vector(anchor):
        v = [int(round(float(x))) for x in anchor]  # type: ignore[arg-type]
        # Search for matching Anchor
        for a in Anchor:
            if isinstance(a.value, tuple) and list(a.value) == v:
                return a
        raise ValueError(f"No Anchor member matches vector {v}")
    raise ValueError(f"Cannot resolve anchor: {anchor!r}")


def _edge_set(
    v: Anchor | str | Point | list[int | float] | list[list[int]] | list[Anchor | str | Point],
) -> list[list[int]]:
    """Convert an edge specifier to the internal 3×4 integer matrix.

    Args:
        v: An :class:`Anchor`, a string like ``"X"``, a legacy edge vector
           ``[0, 1, -1]``, a precomputed edge matrix, or a list of such.

    Returns:
        A ``[[int×4],[int×4],[int×4]]`` edge matrix.
    """
    if isinstance(v, str):
        return _anchor_to_edge_matrix(_STR_EDGE_MAP[v])
    if isinstance(v, Anchor):
        return _anchor_to_edge_matrix(v)
    if _is_edge_matrix(v):
        return v  # type: ignore[return-value]
    if _is_plain_vector(v):
        return _vector_to_edge_set(v)  # type: ignore[arg-type]
    if isinstance(v, list):
        summed: list[list[int]] = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
        for x in v:
            es = _edge_set(x)  # type: ignore[arg-type]
            for ax in range(3):
                for i in range(4):
                    summed[ax][i] += es[ax][i]
        return [[1 if summed[ax][i] > 0 else 0 for i in range(4)] for ax in range(3)]
    raise ValueError(f"Unrecognised edge specifier: {v!r}")


def edges(
    v: Anchor | str | Sequence[object] | list[list[int]] | Point,
    except_: Anchor | str | Sequence[object] | list[list[int]] | None = None,
) -> list[list[int]]:
    """Resolve edge selectors to a 3×4 integer matrix, with optional exclusion.

    Args:
        v: An :class:`Anchor`, edge vector, or list thereof.
        except_: Edges to exclude, same forms.

    Returns:
        A ``[[int×4],[int×4],[int×4]]`` edge matrix.
    """
    if except_ is None:
        except_ = []
    if v == [] or v == Anchor.NONE:
        return EDGES_NONE
    if isinstance(v, (Anchor, str)) or _is_edge_matrix(v) or _is_plain_vector(v):
        return edges([v], except_)
    if isinstance(except_, (Anchor, str)) or _is_edge_matrix(except_) or _is_plain_vector(except_):
        return edges(v, [except_])
    summed: list[list[int]] = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    for x in v:
        es = _edge_set(x)  # type: ignore[arg-type]
        for ax in range(3):
            for i in range(4):
                summed[ax][i] += es[ax][i]
    normed = [[1 if summed[ax][i] > 0 else 0 for i in range(4)] for ax in range(3)]
    if not except_:
        return normed
    exc: list[list[int]] = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    for x in except_:
        es = _edge_set(x)  # type: ignore[arg-type]
        for ax in range(3):
            for i in range(4):
                exc[ax][i] += es[ax][i]
    return [[1 if (normed[ax][i] - (1 if exc[ax][i] > 0 else 0)) > 0 else 0 for i in range(4)] for ax in range(3)]


# -- legacy public helpers (kept for backward compat) --------------------------


def _edge_plane_to_matrix(ep: Anchor) -> list[list[int]]:
    return _anchor_to_edge_matrix(ep)


def _corner_plane_to_set(cp: Anchor | list[int]) -> list[int]:
    if isinstance(cp, Anchor):
        return _anchor_to_corner_set(cp)
    # Legacy vector form
    return [1 if all(c[i] == 0 or c[i] == cp[i] for i in range(3)) else 0 for c in CORNER_OFFSETS]


def _edge_set_by_enum(ep: Anchor) -> list[list[int]]:
    return _anchor_to_edge_matrix(ep)


edges = edges
resolve_anchor = resolve_anchor

__all__ = [
    "Anchor",
    "CornerPlane",
    "EdgePlane",
    "EDGES_ALL",
    "EDGES_NONE",
    "EDGE_OFFSETS",
    "CORNER_OFFSETS",
    "edges",
    "resolve_anchor",
    "edges",
    "_edge_set",
    "_is_edge_array",
    "_is_edge_matrix",
    "_is_plain_vector",
    "_edge_plane_to_matrix",
    "_corner_plane_to_set",
    "_edge_set_by_enum",
    "_anchor_to_edge_matrix",
    "_anchor_to_corner_set",
    "resolve_anchor",
]
