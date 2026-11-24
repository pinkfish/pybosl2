# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every spelling of an extrusion taper must actually taper (SPEC E-5, PLAN X-8).

`linear_extrude(scale=...)` takes a number or an ``[x, y]`` pair, as OpenSCAD does. PythonSCAD only
ever acts on the pair. Up to 1.1.2 it **dropped a scalar silently**, and `pybosl2/shapes2d/base.py`
knew that -- it converts, with a comment saying why. Three other call sites reached the native
extruder directly and passed the scalar through:

| call | built, up to pythonscad 1.1.2 |
|---|---|
| `rounding_edge_mask(length=20, radius1=6, radius2=2)` | 6.1 x 6.1 at *both* ends -- the untapered mask |
| `extrude_from_to(circle(radius=4), ..., scale=2)` | identical to `scale=1` |
| `fillet(length=20, radius1=.., radius2=..)` | the same mask, via `rounding_edge_mask` |

Nothing noticed, because a mask that does not taper is still a solid, still exports, and still cuts
*something* -- the same blind spot as T89's groove and T115's strokes. What finally reported it was
pythonscad 1.2.0 turning the silent drop into `TypeError: Invalid linear_extrude scale parameter`,
which took out seven tests in CI and none locally, where 1.1.2 was installed.

So the conversion lives in one place (`pybosl2._helpers.scale_pair`) and this file asks the
question of every public spelling, by measuring the two ends of what each one builds.
"""

from __future__ import annotations

import numpy as np
import pytest

from pybosl2 import masking, miscellaneous
from pybosl2 import shapes2d as s2
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.path2d import Path2D
from pybosl2.regions import Region
from pybosl2.surfaces3d import fillet

#: Radius of the round profile every builder below starts from.
RADIUS = 4.0

#: Height of every extrusion, so the two ends are far enough apart to measure separately.
HEIGHT = 10.0

#: The taper each case asks for, as (top extent / bottom extent).
FACTOR = 2.0

SQUARE = [[-RADIUS, -RADIUS], [RADIUS, -RADIUS], [RADIUS, RADIUS], [-RADIUS, RADIUS]]


def _end_extents(solid: object) -> tuple[float, float]:
    """Return the X extent of *solid*'s lowest and highest layers of vertices."""
    points = np.asarray(solid.vnf().vertices, dtype=float)  # type: ignore[attr-defined]
    low = points[points[:, 2] < points[:, 2].min() + 1e-6]
    high = points[points[:, 2] > points[:, 2].max() - 1e-6]
    return float(low[:, 0].max() - low[:, 0].min()), float(high[:, 0].max() - high[:, 0].min())


#: One entry per public route to the native extruder that accepts a scalar `scale`. The scalar is
#: the point: a caller writing `[2, 2]` was never affected, which is why the defect survived.
TAPERS = {
    "shape.linear_extrude": lambda: s2.circle(radius=RADIUS).linear_extrude(height=HEIGHT, scale=FACTOR),
    "Path2D.linear_extrude": lambda: Path2D(SQUARE).linear_extrude(height=HEIGHT, scale=FACTOR),
    "Region.linear_extrude": lambda: Region([SQUARE]).linear_extrude(height=HEIGHT, scale=FACTOR),
    "extrude_from_to": lambda: miscellaneous.extrude_from_to(
        s2.circle(radius=RADIUS), [0, 0, 0], [0, 0, HEIGHT], scale=FACTOR
    ),
}


@pytest.mark.parametrize("label", sorted(TAPERS))
def test_a_scalar_scale_reaches_the_far_end(label: str) -> None:
    """The top face is `scale` times the bottom one, whichever spelling asked for it."""
    bottom, top = _end_extents(TAPERS[label]())
    assert bottom > 0, f"{label}: nothing was built to measure"
    assert top == pytest.approx(bottom * FACTOR, rel=0.02), (
        f"{label}: the far end measures {top:.4f} against {bottom:.4f} at the near end, a factor "
        f"of {top / bottom:.4f} where {FACTOR} was asked for. A scalar scale is being dropped."
    )


@pytest.mark.parametrize(
    ("label", "build"),
    [
        ("rounding_edge_mask", lambda: masking.rounding_edge_mask(length=20, radius1=6, radius2=2)),
        ("fillet", lambda: fillet(length=20, radius1=6, radius2=2)),
    ],
)
def test_a_mask_given_two_radii_tapers_between_them(label: str, build: object) -> None:
    """SPEC E-5: a cutter built from `radius1`/`radius2` must be those two radii, not one twice.

    `rounding_edge_mask` scales its own cross-section rather than sweeping between two profiles, so
    the taper *is* the `scale` argument -- which is why losing the scalar left both ends at the
    larger radius and no test could see it from a bounding box.
    """
    bottom, top = _end_extents(build())  # type: ignore[operator]
    assert top == pytest.approx(bottom / 3.0, rel=0.02), (
        f"{label}(radius1=6, radius2=2): the ends measure {bottom:.4f} and {top:.4f}, a ratio of "
        f"{bottom / top if top else float('inf'):.4f} where 3 was asked for"
    )


def test_an_untapered_mask_is_still_untapered() -> None:
    """The control for the test above: one radius must give two equal ends.

    Without this, 'the ends differ' would be satisfied by a mask that tapers when nobody asked.
    """
    bottom, top = _end_extents(masking.rounding_edge_mask(length=20, radius=6))
    assert top == pytest.approx(bottom, rel=1e-6), f"a mask given one radius tapered anyway: {bottom:.4f} to {top:.4f}"


def test_a_scale_that_is_not_two_numbers_is_refused() -> None:
    """SPEC E-4: the pair is what the native acts on, so a triple has to be named, not truncated."""
    with pytest.raises(Bosl2ValueError, match=r"number or an \[x, y\] pair, got 3 values"):
        s2.circle(radius=RADIUS).linear_extrude(height=HEIGHT, scale=[1, 2, 3])
