# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""Every turtle command builds, or refuses as a library error (SPEC E-1, E-4, G-8).

A matrix, for the reason G-8 already gives about `CapType`: a per-case test only ever finds the
case it was written for, and a dispatch chain 161 lines long has room to hide the cases nobody
wrote. `Turtle3D._command` had four.

* `rot` takes a rotation *matrix*. A scalar reached the `@` and came back as a bare `ValueError`
  about operand shapes, naming neither the command nor the argument.
* `arctodir` wants a direction vector and `arcrot` a matrix. Neither was checked, so a scalar
  surfaced as a bare `ValueError` from `rot_from_to4` and a bare `IndexError` from `rot_decode`.
* Three `assert sz is not None` validated `cmd.size`, a caller-supplied value, at an `-O`-erasable
  assert (SPEC E-4, PLAN E-P2).
* **`arcxrot` produced `NaN` from the default heading.** Both arc branches divided by the length of
  the heading with the turn axis projected out, which is zero exactly when the turtle already
  points along that axis. `arcxrot` turns about `[1, 0, 0]`; the turtle *starts* pointing along
  `[1, 0, 0]`. So the first `arcxrot` in a program divided by zero, and every transform it produced
  came back `NaN` -- no exception, no warning a caller would see, just an unusable turtle.

The last is why the matrix checks finiteness as well as the exception type. A command that returns
normally having written `NaN` into the state passes every test that only asks whether it raised.
"""

from __future__ import annotations

import numpy as np
import pytest

from pybosl2.exceptions import Bosl2Error
from pybosl2.turtle import Turtle2D, Turtle3D
from pybosl2.turtle.commands import TurtleCommand, TurtleCommandType

#: Plausible arguments for any command: a length, an angle, a radius and a step count. Most
#: commands want a subset, and the point is that the rest must *say so* rather than crash or
#: quietly produce nonsense.
PROBE = {"size": 10.0, "angle": 30.0, "radius": 8.0, "steps": 8}

TURTLES = (Turtle2D, Turtle3D)


def _state_is_finite(state: object) -> bool:
    """Whether every float the turtle is holding is a real number."""
    for value in vars(state).values():
        try:
            array = np.asarray(value, dtype=float)
        except (TypeError, ValueError):
            continue
        if array.dtype.kind == "f" and array.size and not np.all(np.isfinite(array)):
            return False
    return True


@pytest.mark.parametrize("command", list(TurtleCommandType), ids=lambda c: c.name)
@pytest.mark.parametrize("turtle", TURTLES, ids=lambda t: t.__name__)
def test_a_command_builds_or_refuses_as_a_library_error(turtle: type, command: TurtleCommandType) -> None:
    """SPEC E-1, E-4: a refusal is a `Bosl2Error` naming the command, never a raw Python error."""
    instance = turtle()
    try:
        instance._command(TurtleCommand(cmd_type=command, **PROBE), 0)
    except Bosl2Error:
        return  # refusing is a perfectly good answer, and it says which command and which index
    except Exception as exc:
        pytest.fail(
            f"{turtle.__name__} raised a bare {type(exc).__name__} for {command.name}: {exc}. "
            f"A refusal must be a Bosl2Error naming the command and the index (SPEC E-1, E-4)"
        )
    assert _state_is_finite(instance._state), (
        f"{turtle.__name__}.{command.name} returned normally but left NaN in the turtle's state. "
        f"That passes every test that only asks whether it raised"
    )


def test_an_arc_about_the_current_heading_refuses_rather_than_returning_nan() -> None:
    """The defect in the form a caller met it: the first `arcxrot` in a program."""
    arc = TurtleCommand(cmd_type=TurtleCommandType.ARCXROT, angle=90.0, radius=10.0)
    with pytest.raises(Bosl2Error, match="already points along"):
        Turtle3D()._command(arc, 0)


def test_the_same_arc_builds_once_the_turtle_faces_elsewhere() -> None:
    """And the guard refuses only the degenerate case, not the command."""
    turtle = Turtle3D()
    turtle._command(TurtleCommand(cmd_type=TurtleCommandType.LEFT, angle=90.0), 0)
    turtle._command(TurtleCommand(cmd_type=TurtleCommandType.ARCXROT, angle=90.0, radius=10.0), 1)
    points = np.asarray([[float(c) for c in p] for p in turtle.points()], dtype=float)
    assert np.all(np.isfinite(points))
    spans = points.max(axis=0) - points.min(axis=0)
    # A quarter turn of radius 10 about X: nothing in X, ten each way in Y and Z.
    assert [float(v) for v in spans] == pytest.approx([0.0, 10.0, 10.0], abs=0.01)
