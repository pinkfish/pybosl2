# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/surfaces3d.py: face winding and the cylindrical heightfield.

The winding helpers decide which way every generated face points, so a mistake there produces a
solid that renders inside-out rather than one that fails to build -- these check the winding
itself, not that a mesh came back.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import pybosl2.surfaces3d as surfaces3d
from pybosl2.surfaces3d import (
    _heightfield_reorient,
    _heightfield_reorient_tris,
    _heightfield_tris,
    cylindrical_heightfield,
    heightfield,
    plot3d,
    plot_revolution,
)
from pybosl2.vnf import VNFStyle

# a unit cube as 8 corners and 6 quad faces
CUBE_PTS = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]]
CUBE_QUADS = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]

# a regular octahedron: all triangles, so it takes the vectorized path
OCTA_PTS = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]
OCTA_TRIS = [[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4], [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]]


def _scramble(faces: list[list[int]]) -> list[list[int]]:
    """Reverse every other face, so no two neighbours agree on which way is out."""
    return [list(reversed(f)) if i % 2 else list(f) for i, f in enumerate(faces)]


def _signed_volume(pts: list[list[int]] | list[list[float]], faces: list[list[int]]) -> float:
    """Six times the enclosed volume, signed by the winding."""
    total = 0.0
    for f in faces:
        v0 = np.asarray(pts[f[0]], dtype=float)
        for i in range(1, len(f) - 1):
            v1, v2 = np.asarray(pts[f[i]], dtype=float), np.asarray(pts[f[i + 1]], dtype=float)
            total += float(np.dot(v0, np.cross(v1, v2)))
    return total / 6.0


def _outward_dots(pts: list[list[int]] | list[list[float]], faces: list[list[int]]) -> list[float]:
    """For each face, the dot of its normal with the direction out of the solid's centre."""
    centre = np.asarray(pts, dtype=float).mean(axis=0)
    out = []
    for f in faces:
        p = [np.asarray(pts[i], dtype=float) for i in f]
        normal = np.cross(p[1] - p[0], p[2] - p[0])
        out.append(float(np.dot(normal, sum(p) / len(p) - centre)))
    return out


class TestFaceWinding:
    """_heightfield_reorient: one consistent, outward-matching winding from a scrambled list."""

    def test_quad_faces_come_back_consistently_wound(self) -> None:
        """A cube given as quads takes the flood-fill (the fast path is triangles only): every
        face must end up wound the same way round the solid, not merely unchanged."""
        fixed = _heightfield_reorient(CUBE_PTS, _scramble(CUBE_QUADS))
        dots = _outward_dots(CUBE_PTS, fixed)
        assert all(d < 0 for d in dots), f"faces disagree about which way is out: {dots}"
        # |volume| is the cube's own, and the sign is OpenSCAD's convention (clockwise from outside)
        assert _signed_volume(CUBE_PTS, fixed) == pytest.approx(-1.0)

    def test_a_scrambled_cube_really_was_inconsistent(self) -> None:
        """Guard the test above: the input has to be broken for the fix to mean anything."""
        dots = _outward_dots(CUBE_PTS, _scramble(CUBE_QUADS))
        assert not all(d < 0 for d in dots)
        assert not all(d > 0 for d in dots)

    def test_the_two_paths_produce_the_same_winding(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The vectorized path documents itself as equivalent to the flood-fill; with the fast
        path stubbed out, the same scrambled octahedron must come back wound identically."""
        fast = _heightfield_reorient_tris(OCTA_PTS, _scramble(OCTA_TRIS))
        assert fast is not None
        monkeypatch.setattr(surfaces3d, "_heightfield_reorient_tris", lambda *_a, **_k: None)
        flood = _heightfield_reorient(OCTA_PTS, _scramble(OCTA_TRIS))

        def canonical(faces: list[list[int]]) -> list[tuple[int, ...]]:
            """A face is the same loop however it is rotated, so start each at its lowest index."""
            rotated = [tuple(f[f.index(min(f)) :] + f[: f.index(min(f))]) for f in faces]
            return sorted(rotated)

        assert canonical(fast) == canonical(flood)

    def test_a_non_manifold_mesh_falls_back_to_the_flood_fill(self) -> None:
        """Three triangles sharing one edge have no consistent winding, so the vectorized path
        declines it rather than returning a wrong answer."""
        pts = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1]]
        fins = [[0, 1, 2], [0, 1, 3], [0, 1, 4]]
        assert _heightfield_reorient_tris(pts, fins) is None
        assert len(_heightfield_reorient(pts, [list(f) for f in fins])) == 3  # ...and is still handled


class TestCylindricalHeightfield:
    """cylindrical_heightfield: heights wrapped around a cylinder's outside."""

    FLAT = [[1.0] * 8 for _ in range(6)]

    def test_the_solid_is_as_long_as_the_cylinder(self) -> None:
        """The data wraps around the circumference, so `length` is the Z run whatever it holds."""
        _box = cylindrical_heightfield(self.FLAT, length=20, radius=15).bounds()
        _centre, size = list(_box.center), list(_box.size)
        assert float(size[2]) == pytest.approx(20.0)

    def test_transpose_matches_passing_the_transposed_array(self) -> None:
        """That is what transposing means: with a non-square array the two must agree exactly."""
        data = [[float(r + 2 * c) for c in range(8)] for r in range(6)]
        flipped = [list(col) for col in zip(*data, strict=False)]
        swapped = cylindrical_heightfield(data, length=20, radius=15, transpose=True).bounds()
        by_hand = cylindrical_heightfield(flipped, length=20, radius=15).bounds()
        assert [float(v) for v in swapped.center] == pytest.approx([float(v) for v in by_hand.center])
        assert [float(v) for v in swapped.size] == pytest.approx([float(v) for v in by_hand.size])

    def test_maxh_clamps_the_data(self) -> None:
        """A tall spike capped at maxh builds the same solid as data that never exceeded it."""
        spiky = [[50.0] * 8 for _ in range(6)]
        capped = cylindrical_heightfield(spiky, length=20, radius=15, maxh=2).bounds()
        flat2 = cylindrical_heightfield([[2.0] * 8 for _ in range(6)], length=20, radius=15).bounds()
        assert [float(v) for v in capped.size] == pytest.approx([float(v) for v in flat2.size])

    def test_taller_data_stands_further_out(self) -> None:
        """The heights are radial, so raising them widens the solid without lengthening it."""
        low = cylindrical_heightfield(self.FLAT, length=20, radius=15).bounds().size
        high = cylindrical_heightfield([[4.0] * 8 for _ in range(6)], length=20, radius=15).bounds().size
        assert float(high[0]) > float(low[0])
        assert float(high[2]) == pytest.approx(float(low[2]))

    def test_a_constant_function_matches_the_same_constant_array(self) -> None:
        """A callable is just another way to supply the grid: sampled to the same 5x5 heights it
        must build the very same solid the array does."""
        sampled = cylindrical_heightfield(
            lambda _x, _y: 2.0, length=20, radius=15, xrange=(-1, 0.5, 1), yrange=(-1, 0.5, 1)
        ).bounds()
        tabulated = cylindrical_heightfield([[2.0] * 5 for _ in range(5)], length=20, radius=15).bounds()
        assert [float(v) for v in sampled.center] == pytest.approx([float(v) for v in tabulated.center])
        assert [float(v) for v in sampled.size] == pytest.approx([float(v) for v in tabulated.size])

    def test_more_columns_wrap_further_around(self) -> None:
        """Each sampled column takes a fixed step around the circumference, so sampling xrange
        more finely (at a fixed yrange) covers a wider arc of the cylinder."""
        profile = lambda x, _y: 2 + math.cos(x * 3)  # noqa: E731
        coarse = cylindrical_heightfield(profile, length=20, radius=15, xrange=(-1, 0.5, 1), yrange=(-1, 0.5, 1))
        fine = cylindrical_heightfield(profile, length=20, radius=15, xrange=(-1, 0.25, 1), yrange=(-1, 0.5, 1))
        assert float(fine.bounds().size[1]) > float(coarse.bounds().size[1])
        assert float(fine.bounds().size[2]) == pytest.approx(20.0)  # ...but no longer

    def test_a_taper_is_wider_at_its_wide_end(self) -> None:
        """radius1/radius2 taper the cylinder the data wraps around."""
        tapered = cylindrical_heightfield(self.FLAT, length=20, radius1=15, radius2=10).bounds()
        straight = cylindrical_heightfield(self.FLAT, length=20, radius=15).bounds()
        assert float(tapered.size[2]) == pytest.approx(20.0)
        assert float(tapered.size[0]) > float(straight.size[0])  # the taper leans it across X

    def test_data_too_wide_for_the_cylinder_is_refused(self) -> None:
        """The data has to fit around the circumference; the message says the radius it needs."""
        with pytest.raises(ValueError, match="needs a radius of at least"):
            cylindrical_heightfield([[1.0] * 40 for _ in range(6)], length=20, radius=2)


class TestQuadSplitting:
    """_heightfield_tris: which way each grid quad is cut into triangles.

    The styles all cover the same surface, so a bounding box cannot tell them apart -- what
    differs is the diagonal each one uses, and that is what these check.
    """

    QUAD = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]  # corners 0..3 anticlockwise

    def _split(self, style: str, corners: list[list[float]] | None = None) -> tuple[list[list[int]], list[list[float]]]:
        pts = [list(v) for v in (corners if corners is not None else self.QUAD)]
        return _heightfield_tris(pts, 0, 1, 2, 3, style), pts

    def test_default_cuts_across_the_first_diagonal(self) -> None:
        """Two triangles meeting on the 0-2 diagonal."""
        tris, pts = self._split("default")
        assert tris == [[0, 2, 1], [0, 3, 2]]
        assert len(pts) == 4  # no vertex invented

    def test_alt_cuts_across_the_other_diagonal(self) -> None:
        """The mirror split: the shared edge is 1-3 instead, which is the whole point of alt."""
        tris, pts = self._split("alt")
        assert tris == [[0, 3, 1], [1, 3, 2]]
        assert len(pts) == 4

    def test_quincunx_adds_a_centre_vertex(self) -> None:
        """Four triangles round a new vertex at the quad's centre, so neither diagonal is picked."""
        tris, pts = self._split("quincunx")
        assert len(pts) == 5
        assert pts[4] == [0.5, 0.5, 0.0]  # the average of the four corners
        assert tris == [[0, 4, 1], [1, 4, 2], [2, 4, 3], [3, 4, 0]]

    def test_a_collapsed_corner_drops_the_empty_triangle(self) -> None:
        """Where the grid pinches, a quad degenerates to a triangle: the zero-area half is left
        out rather than emitted as a sliver face."""
        pinched = [[0, 0, 0], [0, 0, 0], [1, 1, 0], [0, 1, 0]]  # corners 0 and 1 coincide
        assert self._split("default", pinched)[0] == [[0, 3, 2]]
        assert self._split("alt", pinched)[0] == [[1, 3, 2]]


class TestHeightfield:
    """heightfield: a grid of heights over a flat rectangle."""

    def test_a_constant_function_matches_the_same_constant_array(self) -> None:
        """Sampling a callable on a 5x5 grid must build what the equivalent 5x5 array builds."""
        sampled = heightfield(lambda _x, _y: 3.0, size=[40, 40], xrange=(-1, 0.5, 1), yrange=(-1, 0.5, 1)).bounds()
        tabulated = heightfield([[3.0] * 5 for _ in range(5)], size=[40, 40]).bounds()
        assert [float(v) for v in sampled.center] == pytest.approx([float(v) for v in tabulated.center])
        assert [float(v) for v in sampled.size] == pytest.approx([float(v) for v in tabulated.size])

    def test_the_footprint_is_the_requested_size(self) -> None:
        """`size` is the XY rectangle the data is spread over, whatever the heights do in Z."""
        size = (
            heightfield(
                lambda x, y: 5 + math.cos(x * 3) * math.sin(y * 3),
                size=[40, 25],
                xrange=(-1, 0.25, 1),
                yrange=(-1, 0.25, 1),
            )
            .bounds()
            .size
        )
        assert [float(size[0]), float(size[1])] == pytest.approx([40.0, 25.0])

    def test_maxz_clamps_the_sampled_heights(self) -> None:
        """A function that runs away is capped, so it builds what a flat field at maxz builds."""
        capped = heightfield(
            lambda _x, _y: 99.0, size=[40, 40], maxz=4, xrange=(-1, 0.5, 1), yrange=(-1, 0.5, 1)
        ).bounds()
        flat = heightfield([[4.0] * 5 for _ in range(5)], size=[40, 40]).bounds()
        assert [float(v) for v in capped.size] == pytest.approx([float(v) for v in flat.size])

    @pytest.mark.parametrize("style", [VNFStyle.DEFAULT, VNFStyle.ALT, VNFStyle.QUINCUNX, VNFStyle.MIN_EDGE])
    def test_every_style_covers_the_same_surface(self, style: VNFStyle) -> None:
        """The quad styles change the triangulation underneath, never the surface it describes."""
        data = [[float((r * c) % 4) + 1 for c in range(6)] for r in range(6)]
        _box = heightfield(data, size=[40, 40], style=style).bounds()
        _centre, size = list(_box.center), list(_box.size)
        assert [float(v) for v in size] == pytest.approx([40.0, 40.0, 24.0])


class TestPlot3d:
    """plot3d: z = f(x, y) sampled over a grid, on an optional base slab."""

    SAMPLES = [i * 0.5 for i in range(-6, 7)]

    @staticmethod
    def _ripple(x: float, y: float) -> float:
        return 5 * math.sin(x) * math.cos(y)

    def test_zclip_clamps_the_surface(self) -> None:
        """Clamped to +/-1 the surface is 2 tall, and the default base adds its own 1mm."""
        _box = plot3d(self._ripple, x=self.SAMPLES, y=self.SAMPLES, zclip=[-1.0, 1.0]).bounds()
        _centre, size = list(_box.center), list(_box.size)
        assert float(size[2]) == pytest.approx(3.0)

    def test_zspan_rescales_the_surface_into_the_given_range(self) -> None:
        """Rescaling maps the sampled heights onto exactly the span asked for, base aside."""
        _box = plot3d(self._ripple, x=self.SAMPLES, y=self.SAMPLES, zspan=[0, 10]).bounds()
        _centre, size = list(_box.center), list(_box.size)
        assert float(size[2]) == pytest.approx(11.0)

    def test_zspan_rescales_rather_than_clips(self) -> None:
        """The difference from zclip: a span keeps the whole shape of the surface, so a span as
        wide as the data leaves the heights alone."""
        plain = plot3d(self._ripple, x=self.SAMPLES, y=self.SAMPLES).bounds()
        spread = float(plain.size[2]) - 1.0  # take the base back off
        spanned = plot3d(self._ripple, x=self.SAMPLES, y=self.SAMPLES, zspan=[0, spread]).bounds()
        assert float(spanned.size[2]) == pytest.approx(float(plain.size[2]))

    def test_base_zero_leaves_just_the_surface(self) -> None:
        """base=0 drops the slab, so the solid is only as tall as the data's own range."""
        with_base = plot3d(self._ripple, x=self.SAMPLES, y=self.SAMPLES).bounds()
        bare = plot3d(self._ripple, x=self.SAMPLES, y=self.SAMPLES, base=0).bounds()
        assert float(with_base.size[2]) - float(bare.size[2]) == pytest.approx(1.0)


class TestPlotRevolution:
    """plot_revolution: a surface of revolution whose radius is modulated by f(angle, z)."""

    ANGLES = list(range(0, 361, 15))

    @staticmethod
    def _ripple(theta: float, _z: float) -> float:
        return 3 * math.sin(math.radians(theta * 4))

    def _cylinder_bounds(self) -> list[float]:
        """The same revolution with no displacement at all: a plain radius-10 cylinder."""
        undisplaced = plot_revolution(lambda _t, _z: 0.0, angle=self.ANGLES, z=[-10, 10], radius=10)
        return [float(v) for v in undisplaced.bounds().size]

    def test_a_zero_width_span_removes_the_modulation(self) -> None:
        """rspan squeezes every displacement into the given range, so a zero-width one leaves
        the plain cylinder -- the ripple is gone, not merely reduced."""
        squeezed = plot_revolution(self._ripple, angle=self.ANGLES, z=[-10, 10], radius=10, rspan=[0, 0])
        assert [float(v) for v in squeezed.bounds().size] == pytest.approx(self._cylinder_bounds())

    def test_a_zero_width_clip_removes_the_modulation(self) -> None:
        """Clamping the displacement to exactly zero does the same, by the other route."""
        clamped = plot_revolution(self._ripple, angle=self.ANGLES, z=[-10, 10], radius=10, rclip=[0, 0])
        assert [float(v) for v in clamped.bounds().size] == pytest.approx(self._cylinder_bounds())

    def test_the_modulation_actually_widens_the_solid(self) -> None:
        """Guard the two above: left alone, the ripple has to make a visible difference."""
        rippled = plot_revolution(self._ripple, angle=self.ANGLES, z=[-10, 10], radius=10)
        assert float(rippled.bounds().size[0]) > self._cylinder_bounds()[0]
        assert float(rippled.bounds().size[2]) == pytest.approx(20.0)  # ...without changing the height
