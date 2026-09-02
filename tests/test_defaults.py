# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Ambient resolution defaults, and the API-ergonomics rules they serve (SPEC.md D-1..D-8, R-1..R-7)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
import pybosl2.shapes2d as s2
from pybosl2._backend import use_backend
from pybosl2.bounds import Bounds3D
from pybosl2.defaults import (
    Resolution,
    current_defaults,
    reset_defaults,
    resolve_facets,
    resolve_res,
    set_defaults,
    use_defaults,
)
from pybosl2.solid import cuboid, effective_defaults

PACKAGE = Path(__file__).resolve().parent.parent / "pybosl2"


@pytest.fixture(autouse=True)
def _clean_defaults():
    """No test may leak a global default into the next one."""
    reset_defaults()
    yield
    reset_defaults()


# --- the context itself -------------------------------------------------------------------


def test_nothing_set_by_default() -> None:
    assert current_defaults() == Resolution()
    assert resolve_facets() == (None, None, None)
    assert resolve_res() is None


def test_block_scoped_and_restored() -> None:
    with use_defaults(fn=64):
        assert current_defaults().fn == 64
    assert current_defaults().fn is None


def test_blocks_nest_and_inherit() -> None:
    with use_defaults(fn=64):
        with use_defaults(fs=0.5):
            inner = current_defaults()
            assert (inner.fn, inner.fs) == (64, 0.5)
        assert current_defaults().fs is None


def test_explicit_argument_beats_ambient() -> None:
    with use_defaults(fn=64):
        assert resolve_facets(fn=8) == (8, None, None)


def test_set_defaults_is_partial_and_resettable() -> None:
    set_defaults(fn=32)
    set_defaults(fs=0.4)
    assert (current_defaults().fn, current_defaults().fs) == (32, 0.4)
    reset_defaults()
    assert current_defaults() == Resolution()


def test_block_shadows_the_global() -> None:
    set_defaults(fn=32)
    with use_defaults(fn=8):
        assert current_defaults().fn == 8
    assert current_defaults().fn == 32


# --- the defaults actually reach the geometry ---------------------------------------------


def test_ambient_fn_changes_generated_geometry() -> None:
    plain = len(s2.arc(radius=10, angle=90))
    with use_defaults(fn=64):
        ambient = len(s2.arc(radius=10, angle=90))
    assert ambient == 17  # a quarter of 64 fragments, plus the closing point
    assert ambient != plain
    assert len(s2.arc(radius=10, angle=90)) == plain  # and it does not leak out of the block


def test_explicit_fn_still_wins_over_ambient_in_geometry() -> None:
    with use_defaults(fn=64):
        assert len(s2.arc(radius=10, angle=90, fn=8)) == len(s2.arc(radius=10, angle=90, fn=8))
        assert len(s2.arc(radius=10, angle=90, fn=8)) == 3


def test_ambient_res_reaches_the_sdf_backend() -> None:
    with use_backend("sdf"):
        assert cuboid([10, 10, 10]).res == 10
        with use_defaults(res=25):
            assert cuboid([10, 10, 10]).res == 25
            assert cuboid([10, 10, 10], res=4).res == 4


# --- what a caller gets when they say nothing (SPEC.md P-2, B-8) ------------------------


def test_effective_defaults_reports_the_real_signature() -> None:
    assert effective_defaults("cuboid")["size"] == (1, 1, 1)
    assert effective_defaults("cuboid", "csg")["anchor"] is not None


def test_effective_defaults_omits_the_ambient_knobs() -> None:
    reported = effective_defaults("cyl")
    assert not {"fn", "fa", "fs", "res"} & set(reported)


def test_effective_defaults_rejects_an_unknown_shape() -> None:
    with pytest.raises(ValueError, match="no shape constructor"):
        effective_defaults("not_a_shape")


def test_backends_agree_on_the_defaults_they_share() -> None:
    """Every façade shape, not a spot-check: an omitted argument means the same on both backends.

    The façade owns the default for anything both backends understand (SPEC B-3) and forwards it,
    so the two can only diverge on options exclusive to one of them.
    """
    import pybosl2.sdf.shapes3d as sdf_shapes
    import pybosl2.shapes3d as csg_shapes
    import pybosl2.solid as facade

    ambient = {"fn", "fa", "fs", "res"}
    checked = 0
    for name in facade.__all__:
        function = getattr(facade, name)
        if not inspect.isfunction(function) or name in {"effective_defaults", "given_arguments"}:
            continue
        csg = getattr(csg_shapes, name, None)
        sdf = getattr(sdf_shapes, name, None)
        if csg is None or sdf is None:
            continue
        facade_params = inspect.signature(function).parameters
        csg_params = inspect.signature(csg).parameters
        sdf_params = inspect.signature(sdf).parameters
        for param, declared in facade_params.items():
            if param in ambient or declared.default is inspect.Parameter.empty:
                continue
            if param not in csg_params or param not in sdf_params:
                continue
            checked += 1
            # the façade's value is what both receive; a backend default only shows through when
            # the façade leaves the argument as None ("not given")
            if declared.default is not None:
                continue
            csg_default = csg_params[param].default
            sdf_default = sdf_params[param].default
            if inspect.Parameter.empty in (csg_default, sdf_default):
                continue
            if csg_default is None or sdf_default is None:
                continue
            assert _same_default(csg_default, sdf_default), (
                f"{name}({param}=) resolves differently per backend: csg={csg_default!r} sdf={sdf_default!r}"
            )
    assert checked > 100, f"only {checked} shared parameters checked"


def _same_default(left: object, right: object) -> bool:
    """True if two spellings of a default mean the same thing (Anchor.CENTER vs [0, 0, 0])."""
    if left == right:
        return True
    try:
        return [float(x) for x in getattr(left, "vector", left)] == [  # type: ignore[union-attr]
            float(x)
            for x in getattr(right, "vector", right)  # type: ignore[union-attr]
        ]
    except (TypeError, ValueError):
        return False


def test_the_facade_owns_the_shared_defaults() -> None:
    """A bare call resolves to the façade's own value, not to whatever a backend happened to pick."""
    from pybosl2.solid import cuboid, effective_defaults

    assert inspect.signature(cuboid).parameters["size"].default == (1, 1, 1)
    assert effective_defaults("cuboid")["size"] == (1, 1, 1)
    assert effective_defaults("cuboid", "sdf")["size"] == (1, 1, 1)


# --- the rules themselves (SPEC.md D-1, D-3) ----------------------------------------------


def test_no_mutable_defaults_anywhere_in_the_package() -> None:
    """A list/dict/set default is shared between every call that takes it (SPEC.md D-3)."""
    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            defaults = list(args.defaults) + [d for d in args.kw_defaults if d is not None]
            for default in defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    offenders.append(f"{path.relative_to(PACKAGE.parent)}:{node.lineno} {node.name}()")
    assert not offenders, "mutable defaults: " + ", ".join(offenders)


def test_facade_never_defaults_an_argument_its_backend_requires() -> None:
    """An optional-looking argument that the backend demands is a TypeError from inside (SPEC.md P-1)."""
    import pybosl2.sdf.shapes3d as sdf_shapes
    import pybosl2.shapes3d as csg_shapes
    import pybosl2.solid as facade

    lies: list[str] = []
    for name in facade.__all__:
        function = getattr(facade, name)
        if not inspect.isfunction(function):
            continue
        facade_params = inspect.signature(function).parameters
        for module, label in ((csg_shapes, "csg"), (sdf_shapes, "sdf")):
            impl = getattr(module, name, None)
            if impl is None:
                continue
            impl_params = inspect.signature(impl).parameters
            for param, facade_p in facade_params.items():
                impl_p = impl_params.get(param)
                if impl_p is None:
                    continue
                backend_requires = impl_p.default is inspect.Parameter.empty and impl_p.kind not in (
                    impl_p.VAR_POSITIONAL,
                    impl_p.VAR_KEYWORD,
                )
                if facade_p.default is not inspect.Parameter.empty and backend_requires:
                    lies.append(f"{name}({param}=) is optional on the facade but required by {label}")
    assert not lies, "; ".join(lies)


def _argument_free(module: object) -> list[tuple[str, object]]:
    """Return the module's public callables that declare no required parameter."""
    found: list[tuple[str, object]] = []
    for name in getattr(module, "__all__", []):
        function = getattr(module, name, None)
        if not inspect.isfunction(function) or name in {"effective_defaults", "given_arguments"}:
            continue
        parameters = inspect.signature(function).parameters.values()
        if any(p.default is inspect.Parameter.empty and p.kind is not p.VAR_POSITIONAL for p in parameters):
            continue
        found.append((f"{getattr(module, '__name__', module)}.{name}", function))
    return found


@pytest.mark.parametrize("module_name", ["pybosl2.solid", "pybosl2.flat", "pybosl2.shapes2d", "pybosl2.shapes3d"])
def test_argument_free_constructors_either_build_or_explain(module_name: str) -> None:
    """A no-argument call raises ValueError or builds a *usable* shape (SPEC P-1, E-4, E-5).

    "Does not raise" is not enough, and asserting only that is how ``regular_ngon()`` shipped
    returning a polygon of coincident points whose bounds were ``[-inf, -inf]``: no traceback, no
    shape either. PLAN E-P4 requires the result to be checked, so a constructor that cannot make
    something from its defaults has to say so.
    """
    import importlib
    import math

    module = importlib.import_module(module_name)
    built = 0
    for label, function in _argument_free(module):
        try:
            shape = function()
        except ValueError:
            continue  # a documented "you must choose one of these spellings"
        except (AssertionError, TypeError) as exc:  # pragma: no cover - the failure we guard against
            pytest.fail(f"{label}() with no arguments raised {type(exc).__name__}: {exc}")
        assert shape is not None, label

        # E-5: what came back has to be something somebody could use. For a shape that means every
        # extent finite and positive -- a degenerate build is a silent wrong answer, not a lenient
        # default. `current_backend()` and the raw point-list helpers are argument-free too but
        # are not shapes, so they are measured by what they are.
        if hasattr(shape, "bounds"):
            size = shape.bounds().size
            assert all(math.isfinite(extent) for extent in size), (
                f"{label}() built a shape with non-finite bounds: {size}"
            )
            assert all(extent > 0 for extent in size), f"{label}() built an empty shape: {size}"
        elif isinstance(shape, (list, tuple)):
            assert shape, f"{label}() returned an empty sequence"
        built += 1
    assert built, f"no argument-free constructor in {module_name} actually built"


def test_parts_build_from_their_catalogue_name_alone() -> None:
    """A part takes its trade size and nothing else (SPEC P-1, P-4)."""
    import pybosl2.parts as parts

    # Screw/ScrewHole carry the one justified second required argument (SPEC D-2): a length no
    # default can invent. Everything else builds from the catalogue name alone.
    cases = {
        "Screw": ("M6", 20),
        "Nut": ("M6",),
        "ScrewHole": ("M6", 20),
        "SpurGear": (),
        "RegularPolyhedron": (),
        "NemaMotor": (),
        "WireBundle": ([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]], 3),  # route + wire count
    }
    for name, args in cases.items():
        cls = getattr(parts, name, None)
        if cls is None:
            continue
        try:
            part = cls(*args)
        except (AssertionError, TypeError) as exc:  # pragma: no cover - the failure we guard against
            pytest.fail(f"{name}({', '.join(map(repr, args))}) raised {type(exc).__name__}: {exc}")
        assert part.shape is not None, name
        # A part built from its name alone must still be a real solid, not an empty one: every
        # extent positive, and the size sane for the catalogue entry it came from.
        _lo, size = part.shape._native_bounds()  # type: ignore[misc]
        assert all(extent > 0 for extent in size), f"{name} built an empty solid: {size}"
        assert all(extent < 1000 for extent in size), f"{name} built a runaway solid: {size}"


def test_size_only_rect_tube_gets_a_wall() -> None:
    """An outer size with no bore stated still makes a tube (SPEC.md P-3)."""
    from pybosl2.solid import rect_tube

    assert rect_tube(size=[20, 20], height=10).bounds() == Bounds3D.from_center_size(
        [0.0, 0.0, 5.0], [20.0, 20.0, 10.0]
    )


def test_a_radius_and_its_own_diameter_together_are_rejected() -> None:
    """Two spellings of one dimension is a mistake, not a preference (SPEC.md D-5, E-5)."""
    from pybosl2.shapes2d import circle as flat_circle
    from pybosl2.solid import cyl, sphere

    for call in (
        lambda: flat_circle(radius=5, diameter=20),
        lambda: sphere(radius=3, diameter=8),
        lambda: cyl(height=5, radius=2, diameter=9),
    ):
        with pytest.raises(ValueError, match="not both"):
            call()


def test_different_levels_of_specificity_are_not_a_conflict() -> None:
    """radius1 legitimately overrides radius; only same-dimension pairs are rejected (SPEC.md D-5)."""
    from pybosl2.solid import cyl

    assert cyl(height=10, radius1=4, radius=2).bounds() == cyl(height=10, radius1=4, radius2=2).bounds()


@pytest.mark.parametrize("operation", ["union", "difference", "intersection"])
def test_empty_boolean_explains_itself(operation: str) -> None:
    import pybosl2.solid as facade

    with pytest.raises(ValueError, match="at least one solid"):
        getattr(facade, operation)()


def test_fn_zero_opts_out_of_an_ambient_fn() -> None:
    """`fn=0` means "use fa/fs", so one call can escape an ambient fn (SPEC R-5)."""
    plain = len(s2.arc(radius=10, angle=90))
    with use_defaults(fn=64):
        assert len(s2.arc(radius=10, angle=90)) == 17
        assert len(s2.arc(radius=10, angle=90, fn=0)) == plain


def test_validation_messages_name_the_accepted_spellings() -> None:
    """Each converted assert became a ValueError that says what to pass (SPEC E-4)."""
    import pybosl2.shapes2d as shapes2d
    import pybosl2.shapes3d as shapes3d
    from pybosl2.sdf.shapes2d import trapezoid2d

    cases = [
        (lambda: shapes2d.ring(radius=-10, ring_width=5), "positive outer radius"),
        (lambda: shapes2d.shell2d(thickness=2), "children="),
        (lambda: shapes2d.round2d(radius=2), "children="),
        (lambda: shapes2d.arc(), "radius="),
        (lambda: shapes2d.trapezoid(height=5), "exactly three"),
        (lambda: trapezoid2d(height=5), "exactly three"),
        (lambda: shapes3d.cross(height=0), "positive height="),
    ]
    for call, expected in cases:
        with pytest.raises(ValueError, match=expected):
            call()


def test_no_assert_validates_user_input() -> None:
    """Argument validation raises ValueError; `assert` is for internal invariants (SPEC E-4).

    Asserts vanish under ``python -O``, so a validating assert means bad input silently produces
    wrong geometry. The test for which is which (PLAN E-P2): if the message names something the
    caller typed — a call, a parameter assignment, or one of the enclosing function's own
    parameter names — it is validation.
    """
    import ast
    import re

    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            names = {a.arg for a in args.args + args.kwonlyargs + args.posonlyargs} - {"self", "cls"}
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Assert) or sub.msg is None:
                    continue
                if isinstance(sub.msg, ast.Constant):
                    message = str(sub.msg.value)
                elif isinstance(sub.msg, ast.JoinedStr):
                    message = "".join(p.value for p in sub.msg.values if isinstance(p, ast.Constant))
                else:
                    continue
                # whole words only: a one-character parameter like `h` otherwise matches inside
                # any word of any message ("chamfered", "this", ...)
                spoken = {
                    n
                    for n in names
                    if re.search(rf"\b{re.escape(n)}\b", message)
                    or re.search(rf"\b{re.escape(n.replace('_', ' '))}\b", message)
                }
                if "()" in message or "=" in message or spoken:
                    offenders.append(f"{path.relative_to(PACKAGE.parent)}:{sub.lineno}: {message[:58]}")
    assert not offenders, "asserts that validate user input:\n  " + "\n  ".join(offenders)


def _raise_messages(node: ast.AST) -> str:
    """Every raise message inside *node*, concatenated -- what this function has told callers."""
    import ast as _ast

    out: list[str] = []
    for sub in _ast.walk(node):
        if not isinstance(sub, _ast.Raise) or not isinstance(sub.exc, _ast.Call):
            continue
        for arg in sub.exc.args:
            if isinstance(arg, _ast.Constant):
                out.append(str(arg.value))
            elif isinstance(arg, _ast.JoinedStr):
                out.extend(str(v.value) for v in arg.values if isinstance(v, _ast.Constant))
    return " ".join(out)


def test_no_bare_assert_stands_in_for_validation() -> None:
    """A message-less `assert` on a caller's argument is validation too (SPEC E-4, PLAN E-P2).

    The message-based rule above cannot see `assert sides >= 3`, and that is exactly the form that
    kept slipping through: seven of them were still rejecting user input at `-O`-erasable asserts.
    A bare assert on a parameter is allowed only where it *narrows* a value the function has
    already validated -- which shows up as an earlier `raise` whose message names that parameter,
    so the caller was told about it properly before the assert ever runs.
    """
    import ast
    import re

    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            names = {a.arg for a in args.args + args.kwonlyargs + args.posonlyargs} - {"self", "cls"}
            if not names:
                continue
            said = _raise_messages(node)
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Assert) or sub.msg is not None:
                    continue
                touched = {n.id for n in ast.walk(sub.test) if isinstance(n, ast.Name)} & names
                touched |= {
                    n.attr
                    for n in ast.walk(sub.test)
                    if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in names
                }
                unexplained = {
                    n
                    for n in touched
                    if not re.search(rf"\b{re.escape(n)}\b", said)
                    and not re.search(rf"\b{re.escape(n.replace('_', ' '))}\b", said)
                }
                if unexplained:
                    offenders.append(
                        f"{path.relative_to(PACKAGE.parent)}:{sub.lineno}: "
                        f"assert {ast.unparse(sub.test)[:48]} (nothing tells the caller about "
                        f"{', '.join(sorted(unexplained))})"
                    )
    assert not offenders, "message-less asserts validating user input:\n  " + "\n  ".join(offenders)


def test_no_assertion_error_is_raised_directly() -> None:
    """`raise AssertionError(...)` is an assert that the ratchets cannot see (SPEC E-4).

    It survives `python -O` -- so it is not even an assert's equivalent -- while telling the caller
    their input was an internal bug. Bad input raises ValueError; a broken invariant uses `assert`.
    """
    import ast

    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            called = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            if isinstance(called, ast.Name) and called.id == "AssertionError":
                offenders.append(f"{path.relative_to(PACKAGE.parent)}:{node.lineno}")
    assert not offenders, "raise AssertionError instead of ValueError:\n  " + "\n  ".join(offenders)


# ---------------------------------------------------------------------------
# The façade owns the shared defaults (SPEC B-3, PLAN F-P1)
# ---------------------------------------------------------------------------

#: Shared arguments the façade deliberately leaves at `None`, with the reason. `None` means
#: "decide for me" (SPEC D-4), and these are the two cases where that is the right answer.
JUSTIFIED_NONE: dict[str, str] = {
    "res": (
        "an ambient control: `None` means inherit (SPEC R-2), and with nothing set anywhere there "
        "is nothing to inherit, so the backend's own facet default is the answer (R-7)"
    ),
    "anchor": (
        "only on the cylinders and regular_prism, where the right anchor depends on `center` -- "
        "the backend computes it, and no constant the façade could write would be right"
    ),
}


def _shared_defaults() -> list[tuple[str, str, str]]:
    """Return (shape, parameter, backend default) for façade arguments still defaulting to None."""
    import inspect

    import pybosl2.solid as facade
    from pybosl2._csg import CsgBackend
    from pybosl2.sdf import SdfBackend

    rows: list[tuple[str, str, str]] = []
    for name in sorted(n for n in facade.__all__ if callable(getattr(facade, n, None))):
        function = getattr(facade, name)
        reals: dict[str, str] = {}
        for backend in (CsgBackend(), SdfBackend()):
            try:
                parameters = inspect.signature(backend.constructor(name)).parameters
            except Exception:  # pragma: no cover - a shape one backend does not build
                continue
            for pname, parameter in parameters.items():
                if parameter.default is not inspect.Parameter.empty and parameter.default is not None:
                    reals.setdefault(pname, repr(parameter.default))
        for pname, parameter in inspect.signature(function).parameters.items():
            if parameter.default is None and pname in reals:
                rows.append((name, pname, reals[pname]))
    return rows


def test_the_facade_owns_every_shared_default() -> None:
    """A shared argument's default belongs in the façade signature, not the backend's.

    SPEC B-3: the façade declares the default and always forwards it, so an identical call builds
    identical geometry on either backend. It did not: **every** façade default was `None`, so the
    backend's own default decided anything the caller left out and the two could resolve the same
    call differently. 67 defaults were lifted in T31; what remains is `None` for a reason.
    """
    unjustified = [
        (shape, parameter, default)
        for shape, parameter, default in _shared_defaults()
        if parameter not in JUSTIFIED_NONE
    ]
    assert not unjustified, (
        f"these façade arguments default to None while a backend has a real default: "
        f"{unjustified}. Lift the backend's default into the façade signature (PLAN F-P1), or "
        f"add the parameter to JUSTIFIED_NONE with the reason `None` is right for it."
    )


def test_the_justified_list_is_not_stale() -> None:
    """A reason for a parameter that no longer defaults to None overstates the debt."""
    live = {parameter for _, parameter, _ in _shared_defaults()}
    stale = sorted(set(JUSTIFIED_NONE) - live)
    assert not stale, f"JUSTIFIED_NONE explains parameters that no longer default to None: {stale}"


def test_an_omitted_shared_argument_resolves_the_same_on_both_backends() -> None:
    """What B-3 is actually for, exercised rather than read off the signatures."""
    from pybosl2 import cuboid, use_backend

    sizes = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            sizes[backend] = tuple(cuboid([20, 20, 20]).bounds().size)
    assert sizes["csg"] == pytest.approx(sizes["sdf"]), sizes
