# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The protocol members no test had ever called.

SPEC C-20. A coverage report named four lines: the bodies of `xflip` and `yflip` on both backends,
added in T87 and sitting at 50% -- the signature ran, the one line doing the mirroring did not.
T87 established that geometry by hand at the prompt and left no test behind, which is how a
verified change becomes an unverified one the next time somebody edits it.

Asking what else was in that position found five more. `chamfer_edges`, `cove_edges`,
`edge_profile_asym`, `front_half` and `intersect` are declared on `Shape`/`Solid`, exported, and
were called by no test in the suite -- 87 protocol members, six never exercised.

`intersect` is the one worth reading twice. It is **not** boolean intersection: it is BOSL2's
attachment-tag operation, and the first call written here passed it a solid and got
`TypeError: 'CsgSolid' object is not iterable`. The signature was honest and the caller was wrong,
which is the risk a never-called member carries -- nothing had ever established what it takes.
"""

from __future__ import annotations

import pytest

from pybosl2 import cuboid
from pybosl2.enums import AttachTag

SIZE = 20.0


def _box() -> object:
    return cuboid([SIZE, SIZE, SIZE])


def test_chamfer_edges_cuts_the_corners_without_moving_the_bounds() -> None:
    """SPEC C-20: declared, exported, and called by nothing until T89."""
    chamfered = _box().chamfer_edges(chamfer=2.0).realize()  # type: ignore[attr-defined]
    assert [float(v) for v in chamfered.bounds().size] == pytest.approx([SIZE] * 3, abs=0.1)
    assert chamfered.vnf().volume() < _box().vnf().volume(), "a chamfer removes material"  # type: ignore[attr-defined]


def test_cove_edges_removes_material_along_the_edges() -> None:
    """SPEC C-20: a cove is a concave fillet, so it cuts in rather than rounding off."""
    coved = _box().cove_edges(radius=2.0).realize()  # type: ignore[attr-defined]
    assert [float(v) for v in coved.bounds().size] == pytest.approx([SIZE] * 3, abs=0.1)
    assert coved.vnf().volume() < _box().vnf().volume(), "a cove removes material"  # type: ignore[attr-defined]


def test_edge_profile_asym_builds_and_keeps_the_envelope() -> None:
    """SPEC C-20: the asymmetric edge profile, never called before this."""
    profiled = _box().edge_profile_asym(radius=2.0).realize()  # type: ignore[attr-defined]
    assert [float(v) for v in profiled.bounds().size] == pytest.approx([SIZE] * 3, abs=0.1)


def test_front_half_keeps_the_half_in_front_of_the_cut() -> None:
    """SPEC C-20: its five siblings were all exercised and this one was not.

    Asserted on which half survives, not merely that the depth halved -- a cut keeping the *back*
    half would halve the depth just as well and be the opposite operation.
    """
    half = _box().front_half()  # type: ignore[attr-defined]
    box = half.bounds()
    assert float(box.size[1]) == pytest.approx(SIZE / 2, abs=0.1), "half the depth"
    assert float(box.max_y) == pytest.approx(0.0, abs=0.1), "the kept half is in front of y=0"
    assert float(box.size[0]) == pytest.approx(SIZE, abs=0.1), "the other axes are untouched"


def test_intersect_is_the_attachment_tag_not_a_boolean() -> None:
    """SPEC C-20: a never-called member is one whose call shape nobody has established.

    The first call written here passed a solid, as "intersect" suggests, and raised
    `TypeError: 'CsgSolid' object is not iterable`. It takes an `AttachTag`: this is BOSL2's
    tagged-children mechanism, and boolean intersection is `&`. Both are asserted, so the next
    reader does not have to make the same mistake to learn the difference.
    """
    tagged = _box().intersect(AttachTag.INTERSECT)  # type: ignore[attr-defined]
    assert [float(v) for v in tagged.bounds().size] == pytest.approx([SIZE] * 3, abs=0.1)

    with pytest.raises(TypeError):
        _box().intersect(cuboid([10.0, 10.0, 10.0]))  # type: ignore[attr-defined]

    overlap = _box() & cuboid([10.0, 10.0, 10.0])  # type: ignore[operator]
    assert [float(v) for v in overlap.bounds().size] == pytest.approx([10.0] * 3, abs=0.1)
