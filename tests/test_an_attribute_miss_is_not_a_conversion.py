# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every shape's `__getattr__` answers a miss the same way (SPEC A-6, B-5, PAR-3, E-1, E-6).

Four shape classes carry an attribute fallback, and until T137 three of them agreed:

* `BaseShape.__getattr__` (`CsgSolid`, `CsgShape2D`) -- private name to `AttributeError`, a
  feature the other backend owns to its refusal, a whitelist (`_NATIVE_PASSTHROUGH`) forwarded to
  the native handle, and anything else to an `AttributeError` that says so.
* `SdfSolid.__getattr__` -- the same three steps, with `_MESH_OPERATIONS` as the whitelist (T3).
* `SdfShape2D.__getattr__` -- `return getattr(self.extrude(0.01).mesh(), name)`. One line, no
  steps. Measured in the real PythonSCAD app, from inside `use_backend("sdf")`:

      circle2d(radius=5).projection()   # -> openscad.PyOpenSCAD
      circle2d(radius=5).repair         # -> builtin_function_or_method
      copy.copy(circle2d(radius=5))     # -> RecursionError
      circle2d(radius=5).geometry       # -> AttributeError: 'openscad.PyOpenSCAD' object ...

  `projection` is in `CSG_ONLY_FEATURES`, so the first line is PLAN B-P4's third case -- *listed
  as exclusive and works anyway, so the refusal never fires* -- which SPEC 12.2 item 9 names as
  the defect `projection` itself had until T4 and `fill` had until T34. It was still live on the
  2-D class, and `docs/design/sdf-csg-compatibility.md` had already written the fallback down as
  closed, naming only `SdfSolid`.

The fix is not interesting; the reason nothing caught it is. T34 taught the parity sweep to walk
`PyShape2D` as well as `SdfSolid` -- and the sweep skips a name that is not statically present,
on the comment "reached through `__getattr__`, which refuses for anything unlisted", which was
true of the solid and false of the class the walk had just been extended to. An exemption carried
across to a class that does not satisfy its justification is worth less than no exemption at all.

So this file asks the fallbacks the same questions instead of trusting one of them, and the list
of classes is derived from the source: a new `__getattr__` anywhere in `pybosl2` either lands in
`FALLBACKS` with a probe or fails `test_every_attribute_fallback_is_covered_here`.
"""

from __future__ import annotations

import ast
import copy
import pathlib
from typing import Any, Callable

import pytest

from pybosl2 import use_backend
from pybosl2._backend import CSG_ONLY_FEATURES, SDF_ONLY_FEATURES
from pybosl2.exceptions import UnsupportedByBackendError

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: A name no shape has, and no backend will ever claim. The point of asking for it is that the
#: answer must not depend on what a *mesh* of the shape happens to have.
MISSING = "no_shape_has_this_attribute"


def _csg_solid() -> Any:
    from pybosl2.shapes3d import cuboid

    with use_backend("csg"):
        return cuboid(size=10)


def _csg_flat() -> Any:
    from pybosl2.shapes2d import circle

    with use_backend("csg"):
        return circle(radius=5)


def _sdf_solid() -> Any:
    from pybosl2.sdf.shapes3d import cuboid

    with use_backend("sdf"):
        return cuboid([10.0, 10.0, 10.0])


def _sdf_flat() -> Any:
    from pybosl2.sdf.shapes2d import circle2d

    with use_backend("sdf"):
        return circle2d(radius=5)


#: label -> (the backend it belongs to, a builder for one of them). Every shape class in the
#: library that answers an attribute miss itself.
FALLBACKS: dict[str, tuple[str, Callable[[], Any]]] = {
    "CsgSolid": ("csg", _csg_solid),
    "CsgShape2D": ("csg", _csg_flat),
    "SdfSolid": ("sdf", _sdf_solid),
    "SdfShape2D": ("sdf", _sdf_flat),
}


@pytest.mark.parametrize("label", sorted(FALLBACKS))
def test_a_private_name_is_a_plain_attribute_error(label: str) -> None:
    """A leading underscore is the class's own bookkeeping; answering it must build nothing.

    This is the guard whose absence turned `copy.copy` into a `RecursionError`: `copy` asks for
    `__copy__`, the 2-D fallback extruded and meshed to answer, and the lookup re-entered.
    """
    backend, build = FALLBACKS[label]
    with use_backend(backend):
        shape = build()
        for name in ("_not_a_real_private_name", "__copy__", "__deepcopy__"):
            with pytest.raises(AttributeError) as caught:
                getattr(shape, name)
            assert not isinstance(caught.value, UnsupportedByBackendError), (
                f"{label}.{name} answers a private probe with a backend refusal: {caught.value}. "
                f"`copy`/`pickle`/`hasattr` read these, and a refusal reads as a real answer."
            )


@pytest.mark.parametrize("label", sorted(FALLBACKS))
def test_a_miss_does_not_reach_for_geometry(label: str) -> None:
    """An unknown public name refuses or misses -- it never answers from a converted copy.

    `AttributeError` is the required base, because `hasattr` and `getattr(shape, name, default)`
    are how the library probes its own wrappers; `UnsupportedByBackendError` is one (E-6), so a
    refusal satisfies both this and the contract that it names the call the caller made.

    Of the three legs below, only the `getattr(..., default)` one could see the pre-T137 defect on
    `SdfShape2D`, and only on a machine with no mesher -- the mesh's own `AttributeError` carries
    the name and propagates. `test_the_probes_can_fail` says so where it is checkable, and
    `tests/test_no_mesher.py` holds the mesher-less case.
    """
    backend, build = FALLBACKS[label]
    with use_backend(backend):
        shape = build()
        with pytest.raises(AttributeError) as caught:
            getattr(shape, MISSING)
        assert MISSING in str(caught.value), (
            f"{label} misses on {MISSING!r} without naming it: {caught.value} (SPEC E-6)"
        )
        sentinel = object()
        assert getattr(shape, MISSING, sentinel) is sentinel, (
            f"{label} does not let `getattr(shape, name, default)` fall back to the default, so "
            f"the library's own `hasattr`-style probes raise instead of answering."
        )
        assert not hasattr(shape, MISSING), f"{label} claims to have {MISSING!r}"


@pytest.mark.parametrize("label", sorted(FALLBACKS))
def test_a_shape_survives_being_copied(label: str) -> None:
    """`copy.copy` asks the fallback for `__copy__`, and must not build geometry to answer.

    `copy.copy` only. `deepcopy` pickles, and a CSG wrapper holds a native `PyOpenSCAD` handle
    that cannot be pickled -- a property of the handle, not of the fallback, so asking it here
    would measure the wrong thing.
    """
    backend, build = FALLBACKS[label]
    with use_backend(backend):
        shape = build()
        assert type(copy.copy(shape)) is type(shape), f"{label} does not survive copy.copy"


@pytest.mark.parametrize("label", sorted(FALLBACKS))
def test_the_other_backends_features_refuse_by_name(label: str) -> None:
    """A feature the *other* backend owns refuses under its own name, however it is reached.

    Statically declared or left to the fallback makes no difference to a caller, which is the
    whole point: `projection` is declared on neither SDF class, and on the solid the fallback
    refused it while on the 2-D shape it meshed and ran (SPEC PAR-3, PLAN B-P4).
    """
    backend, build = FALLBACKS[label]
    exclusive = sorted(SDF_ONLY_FEATURES if backend == "csg" else CSG_ONLY_FEATURES)
    assert exclusive, "the exclusive list is empty; this test would pass by vacuum"
    quiet: list[str] = []
    with use_backend(backend):
        shape = build()
        for feature in exclusive:
            try:
                member = getattr(shape, feature)
            except UnsupportedByBackendError:
                continue
            except AttributeError:
                continue  # absent is not the defect; answering is
            if not callable(member):
                quiet.append(f"{feature} (-> {type(member).__name__})")
                continue
            try:
                member()
            except UnsupportedByBackendError:
                continue
            except Exception:  # a different error is a different contract (SPEC E-1)
                continue
            quiet.append(f"{feature}()")
    assert not quiet, (
        f"on {label} these are listed as exclusive to the other backend and answer anyway, so "
        f"the refusal never fires: {', '.join(quiet)} (SPEC PAR-3, PLAN B-P4)"
    )


# ---------------------------------------------------------------------------
# The list of classes is derived, not maintained.
# ---------------------------------------------------------------------------


def _classes_with_a_fallback() -> "dict[str, str]":
    """Every class in `pybosl2` that defines `__getattr__`, keyed `ClassName` -> path."""
    found: dict[str, str] = {}
    for path in sorted((ROOT / "pybosl2").rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if any(
                isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)) and inner.name == "__getattr__"
                for inner in node.body
            ):
                found[node.name] = str(path.relative_to(ROOT))
    return found


#: Classes with a fallback that is not a shape's, so the probes above measure nothing on them.
NOT_A_SHAPE = {
    "_LazyLibfive": "the libfive module shim -- it forwards to a module, and has no geometry",
}


def _sdf_cls(label: str) -> type:
    """The SDF class *label* names, or a placeholder so the lookup below can go on."""
    from pybosl2.sdf.shapes2d import SdfShape2D
    from pybosl2.sdf.shapes3d import SdfSolid

    return {"SdfSolid": SdfSolid, "SdfShape2D": SdfShape2D}.get(label, type(None))


def test_every_attribute_fallback_is_covered_here() -> None:
    """A new `__getattr__` on a shape joins `FALLBACKS` or says why it is not a shape.

    The defect this file records survived because the class that had it was never on anybody's
    list. Deriving the list from the source is the only form of that check worth having.
    """
    from pybosl2.shapes2d.base import CsgShape2D
    from pybosl2.shapes3d.base import CsgSolid

    found = _classes_with_a_fallback()
    # `CsgSolid` and `CsgShape2D` inherit theirs from `BaseShape`, so the scan finds that name and
    # not theirs; both are probed above, which is what covering `BaseShape` means.
    inherited = {"BaseShape"}
    assert "__getattr__" not in vars(CsgSolid), "CsgSolid now has its own fallback; probe it directly"
    assert "__getattr__" not in vars(CsgShape2D), "CsgShape2D now has its own fallback; probe it directly"

    missing = sorted(set(found) - set(FALLBACKS) - set(NOT_A_SHAPE) - inherited)
    assert not missing, (
        f"these classes answer an attribute miss and nothing here asks them how: {missing} -- "
        f"add each to FALLBACKS with a builder, or to NOT_A_SHAPE with the reason"
    )
    stale = sorted(set(NOT_A_SHAPE) - set(found))
    assert not stale, f"NOT_A_SHAPE names classes with no __getattr__ any more: {stale}"
    # Every probed class must still *have* a fallback, inherited or its own -- otherwise the
    # probes above are asking ordinary attribute lookup and measuring nothing.
    for label in FALLBACKS:
        cls = next(c for c in (CsgSolid, CsgShape2D, _sdf_cls(label)) if c.__name__ == label)
        assert any(c.__name__ in found for c in cls.__mro__), (
            f"{label} no longer reaches a `__getattr__` anywhere in its MRO, so the probes above pass by vacuum"
        )


def test_the_probes_can_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """The control: put the fallback back the way it was and every probe above fires.

    Not a stand-in class -- the real one, with the real line, so the control measures the probes
    against the defect they were written for rather than against a model of it.
    """
    from pybosl2.sdf.shapes2d import SdfShape2D

    def the_old_fallback(self: Any, name: str) -> Any:
        # verbatim, from before T137
        return getattr(self.extrude(0.01).mesh(), name)

    monkeypatch.setattr(SdfShape2D, "__getattr__", the_old_fallback)

    with use_backend("sdf"):
        shape = _sdf_flat()

        # 1. a private probe builds geometry instead of missing, and `copy` never terminates
        with pytest.raises(RecursionError):
            copy.copy(shape)

        # 2. a CSG-only feature answers from the mesh rather than refusing (PLAN B-P4)
        assert "projection" in CSG_ONLY_FEATURES, "the control picked a name that is not exclusive"
        answered = shape.projection()
        assert getattr(answered, "backend", None) != "sdf", (
            f"projection() returned {type(answered).__name__} with backend="
            f"{getattr(answered, 'backend', None)!r}; the control expects a solid the other "
            f"backend owns, which is what made this a defect"
        )

        # 3. and one probe that does *not* tell the two apart, recorded rather than implied:
        #    the mesh raises its own `AttributeError`, which carries the name and propagates, so
        #    `test_a_miss_does_not_reach_for_geometry` passes against the old fallback as well.
        #    Its worth is in the other three classes and in the `getattr(..., default)` leg; what
        #    catches *this* class is the two checks above.
        with pytest.raises(AttributeError) as caught:
            getattr(shape, MISSING)
        assert MISSING in str(caught.value), "the limitation recorded here has changed -- re-read it"
