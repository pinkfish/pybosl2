# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""`SkinMethod` and `SamplingType` change the skin they are passed to (SPEC S-20, G-8).

S-20 says sweeps take their orientation method, sampling type and vertex-matching method *as
enums, never as strings*. That is true of the signatures and was its only enforcement: S-20's
`enforced_by` named `tests/test_exports.py`, which checks the names exist. **Both of the enums it
names were inert.**

* `if method[i - 1] == SkinMethod.DIRECT:` indexed the **scalar** parameter. `SkinMethod` is a
  `StrEnum`, so `SkinMethod.DIRECT[0]` is `'d'`, which never equals `SkinMethod.DIRECT` -- the
  comparison was always false, the `DIRECT` branch was dead, and **every** skin reindexed.
  `method_list`, built two lines earlier for exactly this, was used only in the validation loop.
* `sampling` was normalised to `SamplingType.LENGTH` and then never read. `subdivide_path` has
  carried the same distinction under the same two names the whole time.

So all four combinations built one solid. Fixed, they build four, and the controls separate the two
causes exactly: restoring the index typo makes `DIRECT` and `REINDEX` agree to the last digit, and
dropping the sampling argument makes `LENGTH` and `SEGMENT` agree.

**The obvious fixture cannot see any of this**, which is most of why it survived. Two regular
polygons inscribed in circles are uniformly spaced by arc length *and* by segment, so `LENGTH` and
`SEGMENT` coincide; they are also already optimally aligned, so reindexing is the identity. Worse,
`refine` defaults to `1.0`, which makes the resample target equal to the point count the profile
already has -- so **no points are added and the sampling method cannot matter whatever profiles are
used**. Three separate reasons a plausible test proves nothing, and the first two fixtures I wrote
hit them.
"""

from __future__ import annotations

import itertools

import pytest

from pybosl2.enums import SamplingType, SkinMethod
from pybosl2.path3d import Path3D
from pybosl2.vnf import VNF

#: Deliberately irregular: the edges differ in length, so arc-length and per-segment spacing part
#: company once points are added.
LOWER = Path3D([[0.0, 0.0, 0.0], [20.0, 0.0, 0.0], [20.0, 3.0, 0.0], [2.0, 6.0, 0.0]])

#: The same shape with its point order **rotated**, so pairing by index is not the best pairing and
#: `REINDEX` has something to do.
UPPER = Path3D([[2.0, 5.0, 10.0], [3.0, 1.0, 10.0], [17.0, 1.0, 10.0], [18.0, 4.0, 10.0]])

#: Above 1.0 on purpose. At the default the resample target equals the existing point count, so
#: nothing is added and no sampling method can change the result.
REFINE = 3.0
SLICES = 3


def _skinned(method: SkinMethod, sampling: SamplingType) -> tuple[int, float]:
    solid = VNF.from_skin([LOWER, UPPER], slices=SLICES, refine=REFINE, method=method, sampling=sampling)
    mesh = solid.vnf() if hasattr(solid, "vnf") else solid
    return len(mesh.faces), round(float(mesh.volume()), 4)  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("left", "right"),
    sorted(
        itertools.combinations(
            [(m, s) for m in SkinMethod for s in SamplingType],
            2,
        )
    ),
    ids=lambda pair: f"{pair[0].name}-{pair[1].name}",
)
def test_every_method_and_sampling_pair_builds_its_own_solid(
    left: tuple[SkinMethod, SamplingType], right: tuple[SkinMethod, SamplingType]
) -> None:
    """SPEC G-8: an accepted enum member that changes nothing is a parameter that lies."""
    assert _skinned(*left) != _skinned(*right), (
        f"skin(method={left[0].name}, sampling={left[1].name}) and "
        f"skin(method={right[0].name}, sampling={right[1].name}) build the same solid"
    )


def test_direct_does_not_reindex() -> None:
    """The defect in its own terms: `DIRECT` means pair by index, and it was reindexing.

    Asserted as a *difference from* `REINDEX` rather than against a fixed volume, because the
    number would then have to be updated by whoever changed the reindexing and the assertion would
    say nothing about the method.
    """
    direct = _skinned(SkinMethod.DIRECT, SamplingType.LENGTH)
    reindexed = _skinned(SkinMethod.REINDEX, SamplingType.LENGTH)
    assert direct != reindexed, (
        "DIRECT and REINDEX built the same solid on profiles whose point orders are rotated "
        "relative to each other, which is the one case the two methods must disagree on. Check "
        "that the dispatch reads `method_list[i - 1]` and not `method[i - 1]`: the latter indexes "
        "the StrEnum's own characters and is always false"
    )


def test_the_sampling_type_reaches_the_resampler() -> None:
    """`SamplingType` was normalised and dropped; `subdivide_path` had the distinction all along."""
    by_length = _skinned(SkinMethod.DIRECT, SamplingType.LENGTH)
    by_segment = _skinned(SkinMethod.DIRECT, SamplingType.SEGMENT)
    assert by_length != by_segment, (
        "LENGTH and SEGMENT sampling built the same solid on a profile with unequal edges, where "
        "spacing new points by arc length and spreading them per segment must differ"
    )


def test_the_fixture_can_tell_the_four_apart() -> None:
    """A guard whose fixture cannot express the difference measures the fixture (T97, T104).

    Three properties are needed and the first two fixtures I wrote had none of them: unequal edge
    lengths, a rotated point order, and `refine` above 1. This asserts the last one directly,
    because it is the one that silently disables sampling for *any* profile.
    """
    assert REFINE > 1.0, "at refine=1 no points are added and no sampling method can matter"
    volumes = {_skinned(m, s)[1] for m in SkinMethod for s in SamplingType}
    assert len(volumes) == 4, (
        f"the four combinations produce {len(volumes)} distinct volumes, not 4: {sorted(volumes)}. "
        f"Either a method has stopped working or the fixture has stopped separating them"
    )
