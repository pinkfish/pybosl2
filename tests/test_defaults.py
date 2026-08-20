# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Ambient resolution defaults, and the API-ergonomics rules they serve (SPEC.md D-1..D-10)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
import pybosl2.shapes2d as s2
from pybosl2._backend import use_backend
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


# --- what a caller gets when they say nothing (SPEC.md P-2, item 5) ------------------------


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
    """Where both backends declare the same parameter with a real default, they must match."""
    import pybosl2.sdf.shapes3d as sdf_shapes
    import pybosl2.shapes3d as csg_shapes

    for name in ("cube", "octahedron", "onion", "pie_slice"):
        csg = inspect.signature(getattr(csg_shapes, name)).parameters
        sdf = inspect.signature(getattr(sdf_shapes, name)).parameters
        for param, csg_p in csg.items():
            sdf_p = sdf.get(param)
            if sdf_p is None or param in {"fn", "fa", "fs", "res", "anchor"}:
                continue
            if csg_p.default in (None, inspect.Parameter.empty) or sdf_p.default in (
                None,
                inspect.Parameter.empty,
            ):
                continue
            assert csg_p.default == sdf_p.default, f"{name}({param}=) differs between backends"


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


def test_argument_free_constructors_either_build_or_explain() -> None:
    """No-argument calls must build or raise ValueError -- never assert or TypeError (SPEC.md P-1, E-4)."""
    import pybosl2.solid as facade

    built = 0
    for name in facade.__all__:
        function = getattr(facade, name)
        if not inspect.isfunction(function) or name in {"effective_defaults", "given_arguments"}:
            continue
        parameters = inspect.signature(function).parameters.values()
        if any(p.default is inspect.Parameter.empty and p.kind is not p.VAR_POSITIONAL for p in parameters):
            continue
        try:
            assert function() is not None, name
        except ValueError:
            continue  # a documented "you must choose one of these spellings"
        except (AssertionError, TypeError) as exc:  # pragma: no cover - the failure we are guarding against
            pytest.fail(f"{name}() with no arguments raised {type(exc).__name__}: {exc}")
        built += 1
    assert built >= 13, f"only {built} facade constructors build with no arguments at all"


def test_size_only_rect_tube_gets_a_wall() -> None:
    """An outer size with no bore stated still makes a tube (SPEC.md P-3)."""
    from pybosl2.solid import rect_tube

    assert rect_tube(size=[20, 20], height=10).bounds() == ([0.0, 0.0, 5.0], [20.0, 20.0, 10.0])


@pytest.mark.parametrize("operation", ["union", "difference", "intersection"])
def test_empty_boolean_explains_itself(operation: str) -> None:
    import pybosl2.solid as facade

    with pytest.raises(ValueError, match="at least one solid"):
        getattr(facade, operation)()
