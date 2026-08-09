# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/svg.py
#    Load an SVG drawing as real path data -- a Region of Path2D outlines -- rather than
#    handing the file to the renderer's own importer and getting back an opaque handle.
#
# FileSummary: Load SVG drawings into a Region of outlines.
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

"""Load SVG drawings into a Region of outlines."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pybosl2.regions import Region

__all__ = ["svg_outlines", "region_from_svg"]

#: Points per curved segment when flattening. 12 keeps a letter-sized glyph smooth without
#: producing outlines so dense that every later boolean pays for it.
DEFAULT_STEPS = 12


def svg_outlines(
    file: str,
    steps: int = DEFAULT_STEPS,
    flip_y: bool = True,
) -> list[list[list[float]]]:
    """Return an SVG's outlines as plain ``[[x, y], ...]`` point rings.

    Every subpath of every shape becomes one closed ring. Curves (cubic/quadratic béziers and
    arcs) are flattened to *steps* points each; straight segments keep their endpoints.

    The raw rings, with no nesting applied -- see :func:`region_from_svg` to get a
    :class:`~pybosl2.regions.Region` with holes resolved.

    Args:
        file: Path to the SVG.
        steps: Points per curved segment. Higher is smoother and slower downstream.
        flip_y: Negate Y. SVG's Y axis points DOWN and OpenSCAD's points UP, so without this
            every imported drawing comes out mirrored.

    Returns:
        One list of ``[x, y]`` points per ring, in the SVG's own USER UNITS. The renderer's
        importer instead converts px to mm at 72 dpi (a factor of 25.4/72); nothing here
        guesses at a physical size, so resize the result to whatever the part needs.

    Raises:
        ImportError: If ``svgelements`` is not installed.

    """
    try:
        from svgelements import SVG, Close, Line, Move, Path, Shape
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError("loading SVG needs the 'svgelements' package (pip install svgelements)") from exc

    sign = -1.0 if flip_y else 1.0
    rings: list[list[list[float]]] = []
    for element in SVG.parse(file).elements():
        if not isinstance(element, Shape):
            continue
        for subpath in Path(element).as_subpaths():
            ring: list[list[float]] = []
            for segment in subpath:
                if isinstance(segment, Close):
                    continue
                if isinstance(segment, (Move, Line)):
                    # float(): svgelements hands back numpy scalars, which the native
                    # polygon()/FFI boundary rejects further downstream.
                    ring.append([float(segment.end.x), sign * float(segment.end.y)])
                    continue
                for i in range(1, steps + 1):
                    point = segment.point(i / steps)
                    ring.append([float(point.x), sign * float(point.y)])
            # A closed subpath repeats its start point; Path2D/Region want the bare ring.
            if len(ring) > 1 and ring[0] == ring[-1]:
                ring.pop()
            if len(ring) >= 3:
                rings.append(ring)
    return rings


def region_from_svg(
    file: str,
    steps: int = DEFAULT_STEPS,
    flip_y: bool = True,
) -> "Region":
    """Load an SVG drawing as a :class:`~pybosl2.regions.Region`.

    The alternative to handing the file to the renderer's importer: that returns an opaque
    handle you can only transform, while this returns real outlines you can measure, offset,
    round, tessellate or use as a lid pattern -- and it needs no renderer, so SVG-derived
    shapes become testable without one.

    Nesting is resolved with the EVEN-ODD rule (:meth:`~pybosl2.regions.Region.even_odd`),
    which is what a traced drawing means by a hole: an outline inside one solid cuts it, an
    outline inside that hole is solid again.

    Args:
        file: Path to the SVG.
        steps: Points per curved segment when flattening.
        flip_y: Negate Y so the drawing is not mirrored (SVG's Y axis points down).

    Returns:
        A :class:`~pybosl2.regions.Region` of the drawing.

    Raises:
        ImportError: If ``svgelements`` is not installed.

    Examples:
        An imported drawing, inset and extruded into a plate:

        .. pythonscad-example::

            from pybosl2 import Region

            Region.from_svg("logo.svg").offset(delta=-0.5).geometry().linear_extrude(height=2).show()

    """
    from pybosl2.regions import Region

    return Region.even_odd(svg_outlines(file, steps=steps, flip_y=flip_y))
