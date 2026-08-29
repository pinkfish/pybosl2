# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Asking an empty shape for its bounds fails the same way whatever the type (SPEC E-4).

An empty path is a legitimate value -- it is what clipping returns when nothing is left, and
several operations produce one deliberately. Asking one for a bounding box is still a mistake,
and the three types disagreed about how to say so: `Region` raised `Bosl2ValueError`, `Path3D`
leaked numpy's "zero-size array to reduction operation minimum", and `Path2D` returned NaN.

NaN was the worst of the three. It survives arithmetic and every comparison against it is False,
so a guard like ``if bounds.width > 0`` silently passes nothing through and the mistake surfaces
far from the call that caused it.
"""

import pytest

from pybosl2 import Path2D
from pybosl2.exceptions import Bosl2Error, Bosl2ValueError
from pybosl2.path3d import Path3D
from pybosl2.regions import Region


@pytest.mark.parametrize(
    ("name", "make"),
    [("Path2D", lambda: Path2D([])), ("Path3D", lambda: Path3D([])), ("Region", lambda: Region([]))],
)
def test_empty_bounds_raise_a_value_error_naming_the_type(name: str, make: object) -> None:
    """All three refuse, as a Bosl2ValueError, naming the type the caller actually has."""
    with pytest.raises(Bosl2ValueError) as excinfo:
        make().bounds()  # type: ignore[operator]
    message = str(excinfo.value)
    assert name in message, f"{message!r} does not name the type"
    assert isinstance(excinfo.value, Bosl2Error)


def test_an_empty_path_is_still_a_legal_value() -> None:
    """Only `bounds()` is refused -- emptiness itself is a normal result, not an error."""
    assert len(Path2D([])) == 0
    assert Path2D([]).area() == 0.0
    assert Path2D([], closed=True).array.shape == (0,)


def test_bounds_still_work_when_there_is_something_to_measure() -> None:
    """The guard rejects the empty case without disturbing the ordinary one."""
    assert Path2D([[0, 0], [3, 4]]).bounds().size == (3.0, 4.0)
    assert Path3D([[0, 0, 0], [1, 2, 3]]).bounds().size == (1.0, 2.0, 3.0)


def test_no_bounds_call_ever_answers_nan() -> None:
    """The specific regression: a NaN answer is indistinguishable from a real measurement."""
    import math

    for make in (lambda: Path2D([]), lambda: Path3D([]), lambda: Region([])):
        try:
            size = make().bounds().size  # type: ignore[union-attr]
        except Bosl2ValueError:
            continue
        assert not any(math.isnan(v) for v in size), f"bounds() answered NaN: {size}"
