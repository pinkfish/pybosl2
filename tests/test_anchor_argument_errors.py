# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A wrong anchor argument is rejected in the library's own terms (SPEC E-4).

Every anchor in the library rejects the legacy string form with a clear ``Bosl2ValueError`` --
except ``attach()`` and ``align()``, which reached straight for ``.vector`` and so surfaced
``AttributeError: 'str' object has no attribute 'vector'``. That names an internal attribute
rather than the parameter at fault, and it is an ``AttributeError`` where the rest of the
library raises ``Bosl2ValueError``, so ``except Bosl2Error`` did not catch it.
"""

import pytest

from pybosl2 import Anchor
from pybosl2.exceptions import Bosl2Error, Bosl2ValueError
from pybosl2.shapes2d import square
from pybosl2.solid import cuboid, cyl


def _pairs(*, accepts_none: bool = True) -> list:
    """The anchor parameters, as (parameter name, call).

    `child_anchor=None` is the documented default -- it means "mate against the opposite face" --
    so that one parameter is excluded when the value under test is None.
    """
    a, b = cuboid([10, 10, 10]), cyl(diameter=4, height=6)
    s1, s2 = square([10, 10]), square([4, 4])
    pairs = [
        ("parent_anchor", lambda v: a.attach(v, b)),
        ("anchor", lambda v: a.align(v, b)),
        ("parent_anchor", lambda v: s1.attach(v, s2)),
        ("anchor", lambda v: s1.align(v, s2)),
    ]
    if accepts_none:
        pairs.insert(1, ("child_anchor", lambda v: a.attach(Anchor.TOP, b, child_anchor=v)))
    return pairs


@pytest.mark.parametrize("bad", ["TOP", "top", "nonsense", [0, 0, 1], None, 3])
def test_a_non_anchor_is_rejected_as_a_value_error(bad: object) -> None:
    """Whatever is wrong with the argument, it fails as a Bosl2ValueError naming the parameter."""
    for parameter, call in _pairs(accepts_none=bad is not None):
        with pytest.raises(Bosl2ValueError) as excinfo:
            call(bad)
        message = str(excinfo.value)
        assert parameter in message, f"{message!r} does not name the parameter at fault"
        assert "Anchor" in message, f"{message!r} does not say what to pass instead"
        # It must also be reachable through the library's own base class, which an
        # AttributeError was not.
        assert isinstance(excinfo.value, Bosl2Error)


@pytest.mark.parametrize(("text", "member"), [("TOP", "TOP"), ("top", "TOP"), ("left", "LEFT")])
def test_a_misspelled_anchor_names_the_member_to_use(text: str, member: str) -> None:
    """A string that matches a member is the likeliest mistake, so the message becomes the fix."""
    with pytest.raises(Bosl2ValueError, match=rf"Did you mean Anchor\.{member}\?"):
        cuboid([10, 10, 10]).attach(text, cyl(diameter=4, height=6))


def test_a_string_with_no_matching_member_gets_no_misleading_suggestion() -> None:
    """Only suggest a member when one actually matches -- a wrong hint is worse than none."""
    with pytest.raises(Bosl2ValueError) as excinfo:
        cuboid([10, 10, 10]).attach("sideways", cyl(diameter=4, height=6))
    assert "Did you mean" not in str(excinfo.value)


def test_child_anchor_none_still_means_the_opposite_face() -> None:
    """None is `child_anchor`'s documented default, so the guard must not reject it."""
    a, b = cuboid([10, 10, 10]), cyl(diameter=4, height=6)
    assert a.attach(Anchor.TOP, b, child_anchor=None).realize().bounds().size == (10.0, 10.0, 16.0)


def test_a_real_anchor_still_attaches() -> None:
    """The guard rejects wrong arguments without disturbing correct ones."""
    a, b = cuboid([10, 10, 10]), cyl(diameter=4, height=6)
    assert a.attach(Anchor.TOP, b).realize().bounds().size == (10.0, 10.0, 16.0)
    assert square([10, 10]).attach(Anchor.LEFT, square([4, 4])).bounds().size == (10.0, 10.0)
