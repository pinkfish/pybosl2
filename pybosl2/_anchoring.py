# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Anchoring, shared by both backends.

Anchoring is arithmetic over a shape's *bounds and anchor vector* -- where a named point of a box
sits, and what it takes to move that point to the origin. None of it touches CSG topology, so none
of it is CSG-specific: an SDF shape knows its own exact bounds (better ones, which is what PAR-5
was about), and that is all this needs.

Lifting it here is the first half of closing the method gap (TASKS T14 phase 5a). It is one
implementation rather than two on purpose -- `pybosl2/partitions.py` spent a release as a drifted
duplicate of the same operators in `shapes3d/base.py`, with a suite of tests that all passed
against code that was never executed (TASKS T12).

A backend mixes this in and gets `anchor_point`, `reanchor`, `reorient` and `orient`. All it must
already provide is `bounds()`, `translate()` and `multmatrix()` -- both backends do.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import numpy as np

from pybosl2._edges_lang import Anchor
from pybosl2._helpers import anchor_vector
from pybosl2.exceptions import Bosl2ValueError

if TYPE_CHECKING:
    from collections.abc import Sequence


class Anchorable:
    """Anchor-point arithmetic over a shape's bounding box.

    Mixed into both backends' solids so the same call means the same thing on either.
    """

    def _resolve_bounds(self, bbox: Sequence[Sequence[float]] | None = None) -> tuple[list[float], list[float]]:
        """Return ``(centre, size)`` for anchoring, from *bbox* if given or the shape's own box.

        *bbox* overrides the shape's own box -- useful when the real box is wrong for the purpose
        (a shape with an overhang, a mask positioned against a nominal box, or a cheap way to skip
        the meshing a native box needs). It is a min/max corner pair,
        ``[[min_x, min_y, min_z], [max_x, max_y, max_z]]``.

        Args:
            bbox: Optional box to anchor against instead of this shape's own.

        Returns:
            The centre and the size of the box anchoring should use.

        Raises:
            ValueError: If *bbox* is not a min/max corner pair with max >= min.

        """
        if bbox is None:
            return self._center_size()  # type: ignore[attr-defined,no-any-return]
        try:
            arr = np.asarray(bbox, dtype=float)
        except (TypeError, ValueError) as exc:
            # A ragged box used to surface numpy's "inhomogeneous shape" message, which says
            # nothing about what to pass (SPEC E-4).
            raise Bosl2ValueError("bbox must be [[min_x,min_y,min_z],[max_x,max_y,max_z]].") from exc
        if arr.shape != (2, 3):
            raise Bosl2ValueError("bbox must be [[min_x,min_y,min_z],[max_x,max_y,max_z]].")
        lo, hi = arr[0], arr[1]
        if not bool(np.all(hi >= lo - 1e-12)):
            raise Bosl2ValueError("bbox must be [[min...],[max...]] with max >= min.")
        return [(lo[i] + hi[i]) / 2 for i in range(3)], [hi[i] - lo[i] for i in range(3)]

    def anchor_point(
        self,
        anchor: Anchor | Sequence[float],
        bbox: Sequence[Sequence[float]] | None = None,
    ) -> list[float]:
        """Return the ``[x, y, z]`` point on this shape's box for *anchor*, in its current frame.

        That is ``centre + anchor * size / 2``, so it works on any shape that can report bounds.

        Args:
            anchor: An :class:`~pybosl2.Anchor`, or a three-vector.
            bbox: Optional box to anchor against instead of this shape's own.

        Returns:
            The anchor point.

        """
        centre, size = self._resolve_bounds(bbox)
        vector = anchor_vector(anchor)
        return [centre[i] + vector[i] * size[i] / 2 for i in range(3)]

    def reanchor(
        self,
        anchor: Anchor | Sequence[float],
        bbox: Sequence[Sequence[float]] | None = None,
    ) -> Self:
        """Return this shape translated so its box's *anchor* point sits at the origin.

        Re-anchors anything after the fact; the constructors only do it at build time.

        Args:
            anchor: The point of the box to bring to the origin.
            bbox: Optional box to anchor against instead of this shape's own.

        Returns:
            The translated shape.

        """
        point = self.anchor_point(anchor, bbox=bbox)
        moved = self.translate([-point[0], -point[1], -point[2]])  # type: ignore[attr-defined]
        if isinstance(anchor, Anchor):
            moved._record_anchor(anchor)
        return moved  # type: ignore[no-any-return]

    def reorient(
        self,
        anchor: Anchor | Sequence[float] = Anchor.CENTER,
        spin: float = 0,
        orient: Anchor | Sequence[float] = Anchor.TOP,
        bbox: Sequence[Sequence[float]] | None = None,
    ) -> Self:
        """Reorient this already-built shape by its own box.

        Moves the box's *anchor* point to the origin, spins *spin* degrees about Z, then rotates
        the shape's UP toward *orient*. The size comes from the box, so -- unlike BOSL2's function
        form -- it is never passed.

        Args:
            anchor: The point of the box to bring to the origin.
            spin: Degrees about Z, applied after the anchor move.
            orient: Direction to rotate the shape's UP towards, applied after the spin.
            bbox: Optional box to anchor against instead of this shape's own.

        Returns:
            The reoriented shape.

        """
        from pybosl2.transforms import reorient as _reorient_matrix

        centre, size = self._resolve_bounds(bbox)
        matrix = _reorient_matrix(
            anchor=list(anchor_vector(anchor)),
            spin=spin,
            orient=list(anchor_vector(orient)),
            size=size,
        )
        centred = self.translate([-centre[0], -centre[1], -centre[2]])  # type: ignore[attr-defined]
        return centred.multmatrix(np.asarray(matrix).tolist())  # type: ignore[no-any-return]

    def orient(
        self,
        direction: Anchor | Sequence[float] = Anchor.TOP,
        spin: float = 0,
        bbox: Sequence[Sequence[float]] | None = None,
    ) -> Self:
        """Rotate this shape so its top (UP) faces *direction*.

        Args:
            direction: Where the shape's UP should point.
            spin: Degrees about Z, applied first.
            bbox: Optional box to anchor against instead of this shape's own.

        Returns:
            The rotated shape.

        """
        return self.reorient(anchor=Anchor.CENTER, spin=spin, orient=direction, bbox=bbox)

    def _record_anchor(self, anchor: Anchor) -> None:
        """Note which anchor this shape now sits on, where the backend tracks that.

        A no-op by default: it is bookkeeping for the nominal anchor box (SPEC S-2a), and a shape
        that carries no such box has nothing to record.
        """
