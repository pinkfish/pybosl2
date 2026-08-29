# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A bad dimension is refused the same way on both backends (SPEC E-4, PAR-1).

The two backends disagreed about the same invalid input, and both answers were wrong. CSG leaked
the kernel's own `TypeError` -- "Invalid Cube dimensions" -- naming a class the caller never used
and escaping `except Bosl2Error`. SDF accepted it outright: `cuboid([-5, 5, 5])` built a shape
whose `bounds().size` was `-5`, handing a negative number back as a measurement, which then flowed
into anchoring and layout arithmetic with nothing to mark it as nonsense.
"""

import pytest

from pybosl2 import cuboid, cylinder, rect_tube, sphere, use_backend
from pybosl2.exceptions import Bosl2Error, Bosl2ValueError

BACKENDS = ["csg", "sdf"]

# Each case pairs the bad call with the words its refusal must contain: the constructor the
# caller named, and the argument that was wrong. Asserting only "it raised" would pass for any
# message at all, including the leaked backend ones this exists to prevent (PLAN X-8).
BAD = [
    ("empty size", lambda: cuboid([]), ["cuboid()", "size"]),
    ("too many components", lambda: cuboid([10, 10, 10, 10]), ["cuboid()", "size", "4"]),
    ("negative component", lambda: cuboid([-5, 5, 5]), ["cuboid()", "size", "positive"]),
    ("zero component", lambda: cuboid([0, 5, 5]), ["cuboid()", "size", "positive"]),
    ("negative height", lambda: cylinder(radius=3, height=-5), ["cylinder()", "height", "-5"]),
    ("negative radius", lambda: sphere(radius=-1), ["sphere()", "radius", "-1"]),
]


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize(("call", "expected"), [(b[1], b[2]) for b in BAD], ids=[b[0] for b in BAD])
def test_bad_dimensions_are_refused_identically(backend: str, call: object, expected: list[str]) -> None:
    """Same input, same refusal, whichever backend is active -- and the message says why."""
    with use_backend(backend), pytest.raises(Bosl2ValueError) as excinfo:
        call()  # type: ignore[operator]
    assert isinstance(excinfo.value, Bosl2Error), "must be catchable as a library error"
    message = str(excinfo.value)
    missing = [word for word in expected if word not in message]
    assert not missing, f"{message!r} is missing {missing}"


@pytest.mark.parametrize("backend", BACKENDS)
def test_no_shape_ever_reports_a_negative_size(backend: str) -> None:
    """The regression itself: a negative extent came back as a measurement.

    This is the half that mattered -- an exception is loud, but a `bounds().size` of -5 is a
    number, and it kept its sign all the way into whatever arithmetic used it.
    """
    with use_backend(backend):
        for build in (lambda: cuboid([-5, 5, 5]), lambda: cylinder(radius=3, height=-5), lambda: sphere(radius=-1)):
            with pytest.raises(Bosl2ValueError):
                build().bounds()


@pytest.mark.parametrize("backend", BACKENDS)
def test_valid_dimensions_are_untouched(backend: str) -> None:
    """The guard must not narrow what the library legitimately accepts.

    `rect_tube` is the case that caught an over-strict first version: its size is a 2-D
    cross-section, so a rule allowing only 1 or 3 components rejected a correct call.
    """
    with use_backend(backend):
        assert cuboid([10, 10, 10]).bounds().size == (10.0, 10.0, 10.0)
        assert cuboid(10).bounds().size == (10.0, 10.0, 10.0)
        assert rect_tube(size=[20, 20], wall=2, height=10).bounds().size == (20.0, 20.0, 10.0)


def test_the_message_names_the_constructor_and_the_argument() -> None:
    """A refusal should point at the call the caller made, not at a backend internal."""
    with pytest.raises(Bosl2ValueError) as excinfo:
        cylinder(radius=3, height=-5)
    message = str(excinfo.value)
    assert "cylinder()" in message
    assert "height" in message
    assert "-5" in message
