# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Abstract :class:`Path` base class for 2-D and 3-D path types.

Concrete math helpers live in :mod:`pybosl2._path_math`.
"""

# LibFile: pybosl2/paths.py
# FileSummary: Abstract Path base class + CutPoint type.
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

from __future__ import annotations

import collections.abc as abc
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Self, cast

import numpy as np

from pybosl2.caps import CapSpec, CapType
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.math import EPSILON, deriv
from pybosl2.points import Point


@dataclass(frozen=True, slots=True)
class CutPoint:
    """A point along a path where it was cut, with the index of the next segment.

    Returned by :meth:`~pybosl2.path2d.Path2D.cut_points` and related methods.
    When requested with ``direction=True``, the *direction* and *normal*
    attributes are populated; otherwise they are ``None``.
    """

    point: Point
    next_index: int
    direction: np.ndarray | None = None
    normal: np.ndarray | None = None

    @property
    def is_directed(self) -> bool:
        """True if direction and normal vectors are present."""
        return self.direction is not None and self.normal is not None


if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from typing import TypeAlias

    from numpy.typing import NDArray

    from pybosl2.color import Color

#: **Internal.** The permissive form a body normalises *from*, never a public parameter type
#: (SPEC C-7c, PLAN T-4a). A public parameter meaning an ordered set of points is typed `Path2D`,
#: `Path3D` or `Path` and guarded with :func:`require_path` (SPEC C-7a).
#:
#: This alias used to be documented as "anything an API that wants a polyline accepts", and that
#: sentence is how it reached 36 public signatures: the widest form read as the intended contract,
#: so every new function copied it. A bare sequence carries no dimension, no open/closed flag and
#: no winding, leaving each callee to re-derive all three -- and they disagreed.
#:
#: Normalise on the first line -- ``np.asarray(x, dtype=float)`` or ``Path2D(x)`` -- so the rest of
#: the body works on one shape.
PathLike: "TypeAlias" = "Path | Sequence[Sequence[float]] | NDArray[np.float64]"

__all__ = ["CutPoint", "Path", "PathLike", "SubdivideMethod", "require_path", "require_paths"]


def require_closed_flag(closed: object, type_name: str) -> bool:
    """Return *closed* as a `bool`, refusing anything that is not one.

    `closed` sits next to `points` in every `Path` constructor, so a misplaced positional argument
    lands here rather than being rejected: `Path3D(row_a, row_b)` used to store the second *row* as
    the closed flag and carry on, producing a path whose `closed` was a list of points. Nothing
    downstream reads it as anything but truthy, so the result was an empty mesh with no error --
    the silent wrong answer that SPEC C-7a exists to remove, in the constructor callers were being
    sent to.
    """
    if isinstance(closed, bool):
        return closed
    raise Bosl2ValueError(
        f"{type_name}(): closed must be True or False, got {closed!r}. "
        f"For several outlines, pass a list of {type_name} objects to the function that takes them "
        f"-- {type_name} itself builds one path."
    )


def require_path(value: object, parameter: str, function: str, expect: "type[Path] | None" = None) -> "Path":
    """Return *value* as a :class:`Path`, refusing raw points and naming the wrapper (SPEC C-7a/b).

    A bare sequence carries no dimension, no open/closed flag and no winding, so every function
    that accepted one had to re-derive all three -- and they did not agree: the same list was a
    2-D outline to one and a degenerate 3-D path to the next. Requiring the type moves that
    decision to the single place that can make it once, at construction.

    Raw points are what a caller usually has -- literals, a CSV, another library's output -- so the
    refusal names the wrapper to apply, picking `Path2D` or `Path3D` from the width of what was
    passed rather than making the caller work it out (SPEC C-7b).

    Args:
        value: the argument supplied for a polyline parameter.
        parameter: the parameter's name, so the message points at the argument that was wrong.
        function: the function's name, so it points at the call.
        expect: the concrete type the parameter needs, when only one width will do -- pass
            :class:`~pybosl2.path2d.Path2D` for a parameter typed `Path2D`, and leave it `None`
            only where the annotation is `Path` because both widths really are meant. **A wrong
            width is not a type error a caller can see:** `Path2D` and `Path3D` are siblings, so
            without this a `Path3D` satisfies a `Path2D`-typed parameter and flows into a formula
            that indexes columns 0 and 1 and drops z -- a wrong answer rather than a refusal.

    Returns:
        *value* unchanged, when it is already a :class:`Path` of the expected width.

    Raises:
        Bosl2ValueError: If *value* is not a :class:`Path`, or is not an *expect*.

    """
    if not isinstance(value, Path):
        raise Bosl2ValueError(f"{function}(): {parameter} must be a {_suggest_path_type(value)}.")
    if expect is not None and not isinstance(value, expect):
        raise Bosl2ValueError(
            f"{function}(): {parameter} must be a {expect.__name__}, got a {type(value).__name__}. "
            f"{_conversion_hint(type(value).__name__, expect.__name__)}"
        )
    return value


def _conversion_hint(got: str, wanted: str) -> str:
    """Say how to get from the path type the caller has to the one the parameter needs."""
    if got == "Path3D" and wanted == "Path2D":
        return "Drop the third column with .path2d(), or build the outline in the XY plane."
    if got == "Path2D" and wanted == "Path3D":
        return "Lift it with .path3d(), which places the points at z=0."
    return f"Rebuild it as a {wanted}."


def require_paths(values: object, parameter: str, function: str, expect: "type[Path] | None" = None) -> "list[Path]":
    """Return *values* as a list of :class:`Path`, refusing raw points elementwise (SPEC C-7a).

    The sequence form of :func:`require_path`. The index of the offending element is part of the
    message, because a list of profiles where only one is raw is the usual way to get here and
    saying only "profiles must be Paths" leaves the caller to find which.

    Args:
        values: the argument supplied for a sequence-of-polylines parameter.
        parameter: the parameter's name.
        function: the function's name.
        expect: the concrete type each element needs, as :func:`require_path` takes it.

    Returns:
        The paths as a list, unchanged.

    Raises:
        Bosl2ValueError: If *values* is not a sequence, or any element is not an *expect*.

    """
    if isinstance(values, (str, bytes)) or not isinstance(values, abc.Sequence):
        raise Bosl2ValueError(f"{function}(): {parameter} must be a sequence of Path2D/Path3D, got {values!r}.")
    out: list[Path] = []
    for index, value in enumerate(values):
        out.append(require_path(value, f"{parameter}[{index}]", function, expect))
    return out


def _suggest_path_type(value: object) -> str:
    """Describe the Path type *value* should have been wrapped in, from its own shape."""
    width = _point_width(value)
    if width == 2:
        return "Path2D, not raw points -- wrap them with Path2D(points)"
    if width == 3:
        return "Path3D, not raw points -- wrap them with Path3D(points)"
    return "Path2D or Path3D, not raw points -- wrap them with Path2D(points) or Path3D(points)"


def _point_width(value: object) -> int | None:
    """Return the number of components per point, or None if *value* is not point-shaped."""
    try:
        arr = np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return None
    if arr.ndim != 2 or arr.shape[0] == 0:
        return None
    return int(arr.shape[1])


class SubdivideMethod(Enum):
    """Method for subdividing a path."""

    LENGTH = "length"
    SEGMENT = "segment"


# -- Path -- dimension-agnostic path-math kernels shared by Path2D and Path3D


class Path(ABC):
    """Dimension-agnostic numeric path operations shared by :class:`Path2D` and :class:`Path3D`.

    Abstract base class. Subclasses must provide ``_points`` (:class:`numpy.ndarray`) and
    ``closed`` (:class:`bool`).
    """

    _points: np.ndarray
    closed: bool
    _color: "Color | None"

    def __new__(
        cls,
        points: Sequence[Sequence[float]] | None = None,
        closed: bool = False,  # noqa: ARG004
    ) -> Self:
        """Create a concrete Path2D or Path3D instance.

        Determine the point dimensionality and return the appropriate subclass.
        """
        if cls is Path:
            if points is None:
                raise Bosl2ValueError("Cannot instantiate abstract Path class without points to determine dimension.")
            pts = np.asarray(points, dtype=float)
            dim = pts.shape[-1] if len(pts.shape) > 1 else 0
            if dim == 2:
                from pybosl2.path2d import Path2D

                return cast("Self", super().__new__(Path2D))
            elif dim == 3:
                from pybosl2.path3d import Path3D

                return cast("Self", super().__new__(Path3D))
            else:
                raise Bosl2ValueError("Path points must be 2-D or 3-D.")
        return super().__new__(cls)

    def color(self, c: "Color") -> Self:
        """Return a copy of this path with the given :class:`Color`."""
        copy = self.copy()
        copy._color = c
        return copy

    @abstractmethod
    def copy(self) -> Self:
        """Return a shallow copy of this path."""

    @abstractmethod
    def __init__(self, points: Sequence[Sequence[float]], closed: bool = False) -> None:
        """Initialize the instance."""
        ...

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self._points)

    def __getitem__(self, key: int | slice | tuple[Any, ...]) -> np.ndarray | Point:
        """Return the item at index."""
        result = self._points[key]
        if isinstance(key, int):
            return Point.from_seq(result)
        return result

    def __iter__(self) -> Iterator[np.ndarray]:
        """Return an iterator."""
        return iter(self._points)

    def __array__(self, dtype: None = None, copy: bool = False) -> np.ndarray:
        """Return a numpy array representation."""
        if copy:
            return self._points.copy()
        return self._points

    def __eq__(self, other: object) -> bool:
        """Return whether two objects are equal."""
        if not isinstance(other, Path):
            return NotImplemented
        return bool(np.allclose(self._points, other._points)) and self.closed == other.closed

    @property
    def array(self) -> np.ndarray:
        """The points as an (N, D) numpy array."""
        return self._points

    # -- Path2D length calculation -----------------------------------------------------------

    @abstractmethod
    def segment_lengths(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Length of each segment of the path, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of segment lengths.

        """
        ...

    @abstractmethod
    def perimeter(self) -> float:
        """Total length along the path.

        Returns:
            The total path length as a float.

        """
        ...

    @abstractmethod
    def length_fractions(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Distance fraction of each point in the path (0 at start, 1 at end).

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of cumulative length fractions, from 0 to 1.

        """
        ...

    @abstractmethod
    def closest_point(self, pt: Point | Sequence[float], closed: bool | None = None) -> Point:
        """Return the closest point on the path to *pt*.

        Args:
            pt: The query point as :class:`~pybosl2.points.Point` or ``[x, y, z]``.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A :class:`~pybosl2.points.Point` of the closest point on the path.

        """
        ...

    def tangent_array(self, closed: bool | None = None, uniform: bool = True) -> NDArray[np.float64]:
        """Return the unit tangent at every point of the path, as an (N, D) array (BOSL2 path_tangents).

        The shared implementation behind :meth:`tangents` for both dimensions. Always returns
        one tangent per path point, never one per segment.

        A path of fewer than two points has no direction to derive -- there is no neighbour to
        difference against. Rather than raise, each such point is given **+x** (``[1, 0]`` /
        ``[1, 0, 0]``). That is a CONVENTION, not a measurement: it is arbitrary, inherited
        from the original implementation, and kept only so callers get a usable unit vector and
        a predictable ``(N, D)`` shape. Do not read meaning into the direction, and do not
        change it casually -- :meth:`normals` rotates whatever comes back, so anything
        downstream of a one-point path moves with it.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            uniform: If True, estimate the derivative assuming equally spaced points. If False,
                sample it at the true (non-uniform) segment lengths, which tracks a path whose
                points are unevenly spaced far better.

        Returns:
            An ndarray of unit tangent vectors, one per path point.

        Raises:
            ValueError: If two adjacent points coincide, leaving a zero-length tangent.

        """
        if closed is None:
            closed = self.closed
        pts = self._points
        if len(pts) < 2:
            # The +x convention documented above. An empty Path2D holds a 1-D zero-length array
            # rather than an (0, 2) one, so this cannot go through zeros_like: build the (N, D)
            # result from the point count instead.
            straight: NDArray[np.float64] = np.zeros((len(pts), pts.shape[1] if pts.ndim > 1 else 2))
            straight[:, 0] = 1.0
            return straight
        height: float | NDArray[np.float64] = 1.0 if uniform else self.segment_lengths(closed=closed)
        derivs = np.asarray(deriv(pts, height=height, closed=closed), dtype=float)
        norms = np.linalg.norm(derivs, axis=1, keepdims=True)
        if not (np.all(norms.ravel() > EPSILON)):
            raise Bosl2ValueError("Cannot normalize a zero vector")
        result: NDArray[np.float64] = derivs / norms
        return result

    @abstractmethod
    def tangents(self, closed: bool | None = None, uniform: bool = True) -> list[Point]:
        """Return normalized tangent vector at each point of the path, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            uniform: If True, use uniform parameter spacing; if False, weight by segment lengths.

        Returns:
            An ndarray of unit tangent vectors, one per path point.

        """
        ...

    @abstractmethod
    def normals(self, tangents: list[Point] | None = None, closed: bool | None = None) -> list[Point]:
        """Return normal vector (perpendicular to tangent, in the plane of the curve) at each point.

        For 2-D paths this is a 90-degree rotation of the tangent. For 3-D paths it is the
        principal normal estimated via the triple-product cross.

        Args:
            tangents: Optional pre-computed tangent vectors; computed automatically if None.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of unit normal vectors, one per path point.

        """
        ...

    @abstractmethod
    def curvature(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Numeric curvature estimate of the path at each point, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of curvature values, one per path point.

        """
        ...

    @abstractmethod
    def torsion(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Numeric torsion estimate of the path at each point, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of torsion values, one per path point.

        """
        ...

    @abstractmethod
    def cut(self, cutdist: float | Sequence[float], closed: bool | None = None) -> list[Any]:
        """Cut path into subpaths at the given ascending list of distances (or a single distance).

        Args:
            cutdist: A single distance or a list of ascending distances from the start.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A list of subpath point lists.

        """
        ...

    @abstractmethod
    def cut_getpaths(self, cutlist: list[CutPoint], closed: bool) -> Sequence[Path]:
        """Reconstruct sub-paths from the output of cut_points().

        Args:
            cutlist: Output from cut_points(), a list of :class:`CutPoint` entries.
            closed: Whether the path is closed.

        Returns:
            A list of subpath point lists.

        """
        ...

    @abstractmethod
    def cut_points(
        self,
        cutdist: float | Sequence[float],
        closed: bool | None = None,
        direction: bool = False,
    ) -> list[CutPoint]:
        """Cut path at given distance(s) from start.

        Returns a list of :class:`CutPoint` entries (or :class:`` if direction is True).

        Args:
            cutdist: A single distance or a list of ascending distances from the start.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            direction: If True, also include direction and normal at each cut point.

        Returns:
            A list of :class:`CutPoint` or :class:`` entries, one per cut distance.

        """
        ...

    @abstractmethod
    def cut_points_recurse(self, dists: Sequence[float], closed: bool = False) -> list[CutPoint]:
        """Walk the path accumulating distance until each cut distance is reached.

        Args:
            dists: Ordered list of distances from the start at which to cut.
            closed: Whether the path is closed.

        Returns:
            A list of :class:`CutPoint` entries, one per cut distance.

        """
        ...

    @abstractmethod
    def cut_single(self, dist: float, closed: bool = False, ind: int = 0, eps: float = 1e-7) -> CutPoint:
        """Find the single cut point at distance dist from segment ind.

        Args:
            dist: Distance along the path from the given segment index.
            closed: Whether the path is closed.
            ind: The segment index to start searching from.
            eps: Epsilon for distance comparison.

        Returns:
            A :class:`CutPoint` with the cut point and its next segment index.

        """
        ...

    @abstractmethod
    def cuts_path_normals(self, cuts: list[CutPoint], closed: bool = False) -> list[Point]:
        """Compute normals at each cut point from the path geometry.

        Args:
            cuts: List of cut entries from cut_points().
            closed: Whether the path is closed.

        Returns:
            A list of normal vectors, one per cut point.

        """
        ...

    @abstractmethod
    def plane(self, ind: int, i: int, closed: bool = False) -> list[Point]:
        """Find the local plane defined by point ind, ind-1, and the nearest non-collinear point.

        Args:
            ind: Index of the first point defining the plane.
            i: Index of the search start for the third non-collinear point.
            closed: Whether the path is closed.

        Returns:
            A 2x3 ndarray of two basis vectors defining the local plane, or None if no
            non-collinear point is found.

        """
        ...

    @abstractmethod
    def cuts_dir(self, cuts: list[CutPoint], closed: bool = False, eps: float = 1e-2) -> list[Point]:
        """Compute direction vectors at each cut point (blended from adjacent segments).

        Args:
            cuts: List of cut entries from cut_points().
            closed: Whether the path is closed.
            eps: Epsilon for numerical comparisons.

        Returns:
            A list of direction vectors, one per cut point.

        """
        ...

    @abstractmethod
    def subdivide_path(
        self,
        points: int | None = None,
        points_per_segment: Sequence[int] | None = None,
        maxlen: float | None = None,
        exact: bool = True,
        closed: bool | None = None,
        method: SubdivideMethod = SubdivideMethod.LENGTH,
    ) -> Path:
        """Subdivide the path into evenly spaced points.

        Args:
            points: Target total number of points.
            points_per_segment: Number of points to add to each segment index.
            maxlen: Maximum allowed segment length.
            exact: If False, favor uniform sampling — point count may differ.
            closed: Override the instance's closed flag.
            method: Subdivision method — ``LENGTH`` (uniform along path) or ``SEGMENT`` (per segment).

        Returns:
            A new path with the subdivided points.

        """
        ...

    @abstractmethod
    def resample_path(
        self,
        num_copies: int | None = None,
        spacing: float | None = None,
        closed: bool | None = None,
    ) -> Path:
        """Uniformly resample path to num_copies points, or to a spacing near spacing.

        Args:
            num_copies: Target number of points.
            spacing: Approximate spacing between points.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A list of uniformly resampled path points.

        """
        ...

    @abstractmethod
    def select(self, s1: int, u1: float, s2: int, u2: float, closed: bool | None = None) -> Path:
        """Portion of path from the u1 fraction of segment s1 to the u2 fraction of segment s2.

        Args:
            s1: Starting segment index.
            u1: Fraction along segment s1 (0 to 1).
            s2: Ending segment index.
            u2: Fraction along segment s2 (0 to 1).
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A list of points representing the selected portion of the path.

        """
        ...

    @abstractmethod
    def stroke(
        self,
        width: float = 1,
        closed: bool | None = None,
        endcaps: CapType | CapSpec = CapType.ROUND,
        endcap1: CapType | CapSpec = CapType.ROUND,
        endcap2: CapType | CapSpec = CapType.ROUND,
        joints: CapType | CapSpec = CapType.ROUND,
    ) -> Any:
        """Render the path as a stroked polygon outline (2-D) or solid tube (3-D).

        Args:
            width: Stroke line width.
            closed: Override the instance's closed flag.
            endcaps: Default endcap style for both ends.
            endcap1: Start endcap style (overrides endcaps).
            endcap2: End endcap style (overrides endcaps).
            joints: Joint style at vertices.

        Returns:
            A :class:`Path2D` for 2-D strokes, :class:`Bosl2Solid` for 3-D.

        """
        ...

    @abstractmethod
    def dashed_stroke(
        self,
        dashpat: Sequence[float] | None = None,
        closed: bool | None = None,
        fit: bool = True,
        mindash: float = 0.5,
    ) -> Any:
        """Break the path into dashed segments and stroke them.

        Args:
            dashpat: Dash pattern [line_len, space_len, ...].
            closed: Override the instance's closed flag.
            fit: Scale the pattern to fit a whole number of repeats.
            mindash: Drop a trailing dash shorter than this.

        Returns:
            A :class:`Region` for 2-D, :class:`Bosl2Solid` for 3-D.

        """
        ...

    @abstractmethod
    def merge_collinear(self, closed: bool | None = None, eps: float = 1e-9) -> Path:
        """Remove sequential collinear points and return a new path.

        Args:
            closed: Override the instance's closed flag.
            eps: Epsilon for collinearity comparison.

        Returns:
            A new path with collinear points removed.

        """
        ...

    @abstractmethod
    def deduplicate(self, closed: bool | None = None, eps: float = 1e-9) -> Path:
        """Remove duplicate consecutive points and return a new path.

        Args:
            closed: Override the instance's closed flag.
            eps: Epsilon for distance comparison.

        Returns:
            A new path with duplicate points removed.

        """
        ...
