# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Checked against the CSG backend's own **mesh**, which was available the whole time.

SPEC PAR-5. Every cross-backend check written before this one compared *bounding boxes* -- two
numbers each side computed analytically -- or compared the SDF field against a CSG-side Python
geometry builder (`cyl_profile`, `rect_path`, `teardrop_stations`). Both are real evidence and
both have a hole in the middle: a box cannot see the shape inside it, and a builder cannot see
what the backend does with what it builds.

`PyOpenSCAD.mesh()` returns actual vertices. So the strongest available statement is simply: **is
the SDF field zero at every vertex of the mesh the CSG backend produces?** That is what this file
asks, and it is what finally settled `trimcorners`, which no box could distinguish -- the trimmed
and untrimmed solids have the same bounding box, differ by one vertex out of 24, and this backend
had been building the untrimmed one for a uniform chamfer with no way to say so.
"""

from __future__ import annotations

import pytest

import pybosl2.sdf.shapes3d as sdf
from pybosl2 import solid as facade
from pybosl2 import use_backend
from pybosl2.sdf._libfive import lv


def _csg_vertices(shape: str, **kwargs: object) -> list[tuple[float, float, float]]:
    """Return the vertices of the mesh the CSG backend builds for this call."""
    with use_backend("csg"):
        mesh = getattr(facade, shape)(**kwargs).shape.mesh()
    vertices = mesh[0] if isinstance(mesh, (list, tuple)) else mesh
    return [tuple(float(c) for c in v) for v in vertices]


def _has_meshing() -> bool:
    try:
        return len(_csg_vertices("cuboid", size=[2, 2, 2])) > 0
    except Exception:  # pragma: no cover - no pythonscad in this environment
        return False


needs_meshing = pytest.mark.skipif(not _has_meshing(), reason="no pythonscad: the CSG mesh is the reference here")


@needs_meshing
@pytest.mark.parametrize("chamfer", [1.0, 2.0, 3.0])
@pytest.mark.parametrize("trimcorners", [True, False])
def test_the_field_passes_through_every_vertex_of_the_csg_mesh(chamfer: float, trimcorners: bool) -> None:
    """A chamfered box meshes exactly on the CSG side, so this is an equality, not a tolerance.

    24 vertices when the corners are trimmed and a few more when they are not -- the difference
    being the point where three chamfer planes would otherwise meet, which the trim takes off with
    one more plane at `x + y + z = sum(half) - 2c` (read off these very vertices, at four chamfer
    sizes). The exact untrimmed count is 32 or 33 depending on how the corner happens to be
    triangulated, so it is not asserted; `test_trimming_is_the_one_vertex_that_tells_them_apart`
    names the vertex instead, which is the thing that actually differs.
    """
    kwargs = {"size": [20, 20, 20], "chamfer": chamfer, "trimcorners": trimcorners}
    vertices = _csg_vertices("cuboid", **kwargs)
    assert len(vertices) >= 24, f"unexpected mesh: {len(vertices)} vertices"

    tree = sdf.cuboid(size=[20, 20, 20], chamfer=chamfer, trimcorners=trimcorners, anchor=[0, 0, 0])._sdf_fn(
        lv.x(), lv.y(), lv.z()
    )
    worst = max(abs(float(tree(*v))) for v in vertices)
    assert worst == pytest.approx(0.0, abs=1e-9), f"worst |field| at a CSG mesh vertex is {worst}"


@needs_meshing
@pytest.mark.parametrize("chamfer", [1.0, 2.0, 3.0])
def test_trimming_is_the_one_vertex_that_tells_them_apart(chamfer: float) -> None:
    """And a bounding box cannot see it, which is why it went unnoticed.

    The two solids have the *same* box: trimming removes a corner the box's own faces already
    reach past. The one thing that differs is the point where the three chamfer planes meet, at
    `10 - c/2` on each axis -- present in the untrimmed mesh, absent from the trimmed one, and the
    field has to agree about it either way.
    """
    tip = (10.0 - chamfer / 2,) * 3

    boxes = {}
    for trim in (True, False):
        with use_backend("csg"):
            boxes[trim] = [
                round(v, 4) for v in facade.cuboid(size=[20, 20, 20], chamfer=chamfer, trimcorners=trim).bounds().size
            ]
    assert boxes[True] == boxes[False], "if the box could tell them apart this test would be unnecessary"

    meshes = {
        trim: _csg_vertices("cuboid", size=[20, 20, 20], chamfer=chamfer, trimcorners=trim) for trim in (True, False)
    }
    assert not any(all(abs(c - t) < 1e-6 for c, t in zip(v, tip, strict=True)) for v in meshes[True])
    assert any(all(abs(c - t) < 1e-6 for c, t in zip(v, tip, strict=True)) for v in meshes[False])

    for trim, expected_outside in ((True, True), (False, False)):
        tree = sdf.cuboid(size=[20, 20, 20], chamfer=chamfer, trimcorners=trim, anchor=[0, 0, 0])._sdf_fn(
            lv.x(), lv.y(), lv.z()
        )
        value = float(tree(*tip))
        if expected_outside:
            assert value > 0.1, f"trimcorners=True should cut the tip away, and the field says {value}"
        else:
            assert value == pytest.approx(0.0, abs=1e-9), f"trimcorners=False keeps the tip, and the field says {value}"


@needs_meshing
def test_a_plain_box_and_a_rounded_one_meet_the_mesh_too() -> None:
    """The same instrument on the cases that were already right, so it is not a one-shape test.

    A rounded box's CSG mesh is faceted -- its vertices sit *inside* the exact surface by up to
    the sagitta of one facet -- so this asks for the sign and a bound rather than equality. The
    plain box is exact.
    """
    plain = _csg_vertices("cuboid", size=[20, 20, 20])
    tree = sdf.cuboid(size=[20, 20, 20], anchor=[0, 0, 0])._sdf_fn(lv.x(), lv.y(), lv.z())
    assert max(abs(float(tree(*v))) for v in plain) == pytest.approx(0.0, abs=1e-9)

    rounded = _csg_vertices("cuboid", size=[20, 20, 20], rounding=2)
    tree = sdf.cuboid(size=[20, 20, 20], rounding=2, anchor=[0, 0, 0])._sdf_fn(lv.x(), lv.y(), lv.z())
    values = [float(tree(*v)) for v in rounded]
    assert max(values) < 1e-9, "a facet vertex of the CSG mesh is never outside the exact field"
    assert min(values) > -0.2, f"nor far inside it -- the worst is {min(values)}, which is faceting"


@needs_meshing
@pytest.mark.parametrize("fn", [8, 16, None])
def test_a_rounded_box_ignores_the_flag_because_the_csg_backend_does(fn: int | None) -> None:
    """Measured, not assumed -- and the first version of this got it wrong the other way.

    `trimcorners` reads like it should apply to a rounding too: BOSL2's own edge-mask code picks a
    sphere for the corner when it is set and the intersection of three cylinders when it is not.
    But `cuboid(rounding=2, trimcorners=False)` and the default produce **byte-identical meshes**,
    at every facet count checked -- whatever route the flag takes, it does not reach the positive
    uniform-rounding path.

    So the SDF backend ignores it there as well. Honouring it would have made the two disagree on
    a call they already agree on, which is what the first attempt did and what meshing the CSG
    shape caught.
    """
    extra = {} if fn is None else {"fn": fn}
    meshes = {
        trim: sorted(
            tuple(round(c, 6) for c in v)
            for v in _csg_vertices("cuboid", size=[20, 20, 20], rounding=2, trimcorners=trim, **extra)
        )
        for trim in (True, False)
    }
    assert meshes[True] == meshes[False], "the CSG backend has started distinguishing these -- the SDF must follow"

    fields = {}
    for trim in (True, False):
        tree = sdf.cuboid(size=[20, 20, 20], rounding=2, trimcorners=trim, anchor=[0, 0, 0])._sdf_fn(
            lv.x(), lv.y(), lv.z()
        )
        fields[trim] = [round(float(tree(*v)), 9) for v in meshes[True]]
    assert fields[True] == fields[False], "and neither may the SDF backend"
