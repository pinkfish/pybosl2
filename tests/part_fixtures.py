# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""The parts inventory and the arguments that build each one, in one place.

`tests/test_parts_are_lazy.py` and `tests/test_parts_backend_coverage.py` each carried their own
copy of both -- the same discovery walk and the same table of constructor arguments -- and the
copies drifted where nothing looked. Both passed `"trapezoidal"` as `ThreadedRod`'s *profile*,
which is a `Sequence[Sequence[float]]` of points in pitch units: `__init__` accepts it, because
iterating a string yields characters and `[list(row) for row in profile]` happily produces
`[['t'], ['r'], ...]`, and `shape` then fails with a raw `ValueError` from a different method than
the one called wrongly.

Neither module noticed, for the same reason in each: `test_parts_are_lazy` only checks that nothing
is built during `__init__`, and `test_parts_backend_coverage` only builds on the SDF backend, where
both parts are listed CSG-only and refuse *before* the profile is ever read. A refusal that arrives
first makes every argument behind it unfalsifiable.

So the table lives here, one copy, and `tests/test_every_part_builds.py` builds every part on the
backend that is supposed to work -- which is what makes the arguments in it mean anything.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

from pybosl2 import parts
from pybosl2.parts.threading import _trapezoidal_profile

#: A real thread profile. The string that used to sit here was never a profile; see the module
#: docstring for why two test modules could both hold it and both stay green.
_THREAD_PROFILE = _trapezoidal_profile(1.5)

#: Constructor arguments for parts whose signature the generic derivation below cannot serve.
ARGS: dict[str, tuple[Any, ...]] = {
    "HoseSegment": (0.5,),
    "NemaMountMask": (17,),
    "Nut": ("M6",),
    "RingHook": ([20.0, 10.0, 4.0], 5.0),
    "RobertsonMask": (2,),
    "Screw": ("M6", 20),
    "ScrewHole": ("M6", 20),
    "SparseCuboid": ([30.0, 20.0, 10.0],),
    "ThreadedNut": (16.0, 10.0, 10.0, 1.5, _THREAD_PROFILE),
    "ThreadedRod": (10.0, 20.0, 1.5, _THREAD_PROFILE),
    "WireBundle": ([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]], 3),
}

#: Keyword arguments, where positional ones will not do.
KWARGS: dict[str, dict[str, Any]] = {"RingHook": {"outer_radius": 6.0, "inner_radius": 4.0}}


def discover_parts() -> dict[str, type]:
    """Every part class exactly once, keyed by its own name.

    Deduplicated by identity: `manfrotto_rc2_plate` is a second name for `ManfrottoRC2Plate`, and
    counting it twice is what made the spec's total 53 instead of 51.
    """
    seen: set[int] = set()
    found: dict[str, type] = {}
    for module_info in pkgutil.iter_modules(parts.__path__):
        module = importlib.import_module(f"pybosl2.parts.{module_info.name}")
        for name, obj in vars(module).items():
            if not (inspect.isclass(obj) and obj.__module__ == module.__name__):
                continue
            if name.startswith("_") or name == "Buildable" or id(obj) in seen:
                continue
            if not isinstance(inspect.getattr_static(obj, "shape", None), property):
                continue
            seen.add(id(obj))
            found[obj.__name__] = obj
    return found


def arguments(cls: type) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Return ``(args, kwargs)`` that build *cls*, from the table or derived from its annotations."""
    name = cls.__name__
    if name in ARGS:
        return ARGS[name], KWARGS.get(name, {})
    args: list[Any] = []
    for param in list(inspect.signature(cls.__init__).parameters.values())[1:]:
        if param.default is not inspect.Parameter.empty or param.kind in (
            param.VAR_POSITIONAL,
            param.VAR_KEYWORD,
        ):
            continue
        annotation = str(param.annotation)
        if "int" in annotation:
            args.append(6)
        elif any(token in annotation for token in ("Sequence", "list", "Path")):
            args.append([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]])
        else:
            args.append(10.0)
    return tuple(args), KWARGS.get(name, {})


#: The inventory, resolved once.
PARTS: dict[str, type] = discover_parts()
