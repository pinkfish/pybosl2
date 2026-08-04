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

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Self, cast

import numpy as np

from pybosl2.caps import CapSpec, CapType
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

    from numpy.typing import NDArray

__all__ = ["CutPoint", "Path", "SubdivideMethod", "stroke", "dashed_stroke"]


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

    def __new__(
        cls,
        points: Sequence[Sequence[float]] | None = None,
        closed: bool = True,  # noqa: ARG004
    ) -> Self:
        """Create a concrete Path2D or Path3D instance.

        Determine the point dimensionality and return the appropriate subclass.
        """
        if cls is Path:
            if points is None:
                raise ValueError("Cannot instantiate abstract Path class without points to determine dimension.")
            pts = np.asarray(points, dtype=float)
            dim = pts.shape[-1] if len(pts.shape) > 1 else 0
            if dim == 2:
                from pybosl2.path2d import Path2D

                return cast("Self", super().__new__(Path2D))
            elif dim == 3:
                from pybosl2.path3d import Path3D

                return cast("Self", super().__new__(Path3D))
            else:
                raise ValueError("Path points must be 2-D or 3-D.")
        return super().__new__(cls)

    @abstractmethod
    def __init__(self, points: Sequence[Sequence[float]], closed: bool = True) -> None: ...

    def __len__(self) -> int:
        return len(self._points)

    def __getitem__(self, key: int | slice | tuple[int, ...]) -> np.ndarray | Point:
        result = self._points[key]
        if isinstance(key, int):
            return Point.from_seq(result)
        return result

    def __iter__(self) -> Iterator[np.ndarray]:
        return iter(self._points)

    def __eq__(self, other: object) -> bool:
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
        """The closest point on the path to *pt*.

        Args:
            pt: The query point as :class:`~pybosl2.points.Point` or ``[x, y, z]``.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A :class:`~pybosl2.points.Point` of the closest point on the path.
        """
        ...

    @abstractmethod
    def tangents(self, closed: bool | None = None, uniform: bool = True) -> list[Point]:
        """Normalized tangent vector at each point of the path, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            uniform: If True, use uniform parameter spacing; if False, weight by segment lengths.

        Returns:
            An ndarray of unit tangent vectors, one per path point.
        """
        ...

    @abstractmethod
    def normals(self, tangents: list[Point] | None = None, closed: bool | None = None) -> list[Point]:
        """Normal vector (perpendicular to tangent, in the plane of the curve) at each point.

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


def _make_path(points: Any, closed: bool) -> Path:
    pts = np.asarray(points, dtype=float)
    dim = pts.shape[-1] if len(pts.shape) > 1 else 2
    if dim == 3:
        from pybosl2.path3d import Path3D

        return Path3D(points, closed=closed)
    else:
        from pybosl2.path2d import Path2D

        return Path2D(points, closed=closed)


def stroke(
    path: Any,
    width: float = 1,
    closed: bool | None = None,
    endcaps: CapType | CapSpec = CapType.ROUND,
    endcap1: CapType | CapSpec = CapType.ROUND,
    endcap2: CapType | CapSpec = CapType.ROUND,
    joints: CapType | CapSpec = CapType.ROUND,
) -> Any:
    """Render the path/region as a stroked polygon outline (2-D) or solid tube (3-D)."""
    if not isinstance(path, Path):
        path = _make_path(path, closed=True if closed is None else closed)
    return path.stroke(
        width=width,
        closed=closed,
        endcaps=endcaps,
        endcap1=endcap1,
        endcap2=endcap2,
        joints=joints,
    )


def dashed_stroke(
    path: Any,
    dashpat: Sequence[float] | None = None,
    closed: bool | None = None,
    fit: bool = True,
    mindash: float = 0.5,
) -> Any:
    """Break the path/region into dashed segments and stroke them."""
    if not isinstance(path, Path):
        path = _make_path(path, closed=True if closed is None else closed)
    return path.dashed_stroke(
        dashpat=dashpat,
        closed=closed,
        fit=fit,
        mindash=mindash,
    )
