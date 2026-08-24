# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every name a module advertises must resolve (SPEC A-7, PLAN M-2)."""

from __future__ import annotations

import ast
import importlib
import pathlib
import pkgutil
import re

import pytest

import pybosl2

MODULES = sorted(
    name
    for _, name, _ in pkgutil.walk_packages(pybosl2.__path__, prefix="pybosl2.")
    if not any(part.startswith("_") for part in name.split("."))
)


@pytest.mark.parametrize("module_name", MODULES)
def test_every_all_entry_resolves(module_name: str) -> None:
    module = importlib.import_module(module_name)
    declared = getattr(module, "__all__", None)
    if declared is None:
        return
    missing = sorted(name for name in declared if not hasattr(module, name))
    assert not missing, f"{module_name}.__all__ advertises names that do not exist: {missing}"


def test_top_level_all_resolves() -> None:
    missing = sorted(name for name in pybosl2.__all__ if not hasattr(pybosl2, name))
    assert not missing, f"pybosl2.__all__ advertises names that do not exist: {missing}"


def test_every_part_exposes_shape_as_a_property() -> None:
    """A part's geometry is a value, not an action (SPEC C-14, PLAN O-2)."""
    import inspect

    import pybosl2.parts as parts

    offenders: list[str] = []
    for name in parts.__all__:
        cls = getattr(parts, name)
        if not inspect.isclass(cls) or not hasattr(cls, "shape"):
            continue
        if not isinstance(inspect.getattr_static(cls, "shape"), property):
            offenders.append(name)
    assert not offenders, f"parts whose `shape` is not a property: {offenders}"


def test_part_show_returns_the_shape() -> None:
    """show() closes a chain rather than swallowing the value (SPEC S-49, S-51)."""
    import inspect

    import pybosl2.parts as parts

    offenders: list[str] = []
    for name in parts.__all__:
        cls = getattr(parts, name)
        if not inspect.isclass(cls) or not hasattr(cls, "show"):
            continue
        if inspect.signature(cls.show).return_annotation in (None, "None"):
            offenders.append(name)
    assert not offenders, f"parts whose show() returns None: {offenders}"


def test_no_top_level_name_builds_on_the_wrong_backend() -> None:
    """A top-level name honours the active backend or refuses; it never returns the other's shape.

    SPEC A-6: `from pybosl2 import …` must not quietly hand back CSG geometry inside a
    `use_backend("sdf")` block, because the mistake only surfaces later as a CrossBackendError.
    """
    import inspect

    import pybosl2.sdf
    from pybosl2._backend import use_backend
    from pybosl2.exceptions import UnsupportedByBackendError

    offenders: list[str] = []
    with use_backend("sdf"):
        for name in pybosl2.__all__:
            candidate = getattr(pybosl2, name)
            if not inspect.isfunction(candidate):
                continue
            parameters = inspect.signature(candidate).parameters.values()
            if any(p.default is inspect.Parameter.empty and p.kind is not p.VAR_POSITIONAL for p in parameters):
                continue
            try:
                built = candidate()
            except (UnsupportedByBackendError, ValueError, TypeError):
                continue  # refused, or needs arguments -- both fine
            if getattr(built, "backend", None) == "csg":
                offenders.append(name)
    assert not offenders, f"top-level names that built CSG geometry inside an sdf block: {offenders}"


#: Parameter names that mean "a polyline" -- the thing SPEC C-7 is about. Deliberately excludes
#: `points`/`pts`, which are just as often a point *cloud* (hull inputs) or a sample grid.
_POLYLINE_PARAMETERS = frozenset({"path", "paths", "profile", "profiles", "outline", "outlines", "poly", "polygon"})

#: Annotations that spell a polyline as raw nesting -- the form that rejects a Path (PLAN T-4).
_RAW_NESTING = re.compile(
    r"(Sequence\[Sequence\[float\]\]|list\[list\[float\]\]"
    r"|Sequence\[Sequence\[Sequence\[float\]\]\]|list\[list\[list\[float\]\]\])"
)


def _public_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Module-level and class-level functions with public names -- not nested closures."""
    out: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in tree.body:
        bodies = node.body if isinstance(node, ast.ClassDef) else [node]
        for item in bodies:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not item.name.startswith("_"):
                out.append(item)
    return out


def test_every_polyline_parameter_accepts_a_path() -> None:
    """An API taking a polyline must accept a `Path` (SPEC C-7, PLAN T-4).

    A `Path` is what the library hands back, so an API that only spells its input as
    `Sequence[Sequence[float]]` makes callers unpack their own return values -- it works at
    runtime (a Path is iterable and array-like) while the checker rejects it, which is the worst
    of both. `PathLike` is the alias to use; normalise on the first line of the body.
    """
    package = pathlib.Path(pybosl2.__file__).parent
    offenders: list[str] = []
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for function in _public_functions(tree):
            arguments = function.args
            for argument in arguments.args + arguments.kwonlyargs + arguments.posonlyargs:
                if argument.annotation is None or argument.arg.rstrip("123") not in _POLYLINE_PARAMETERS:
                    continue
                annotation = ast.unparse(argument.annotation)
                if not _RAW_NESTING.search(annotation) or re.search(r"\bPath(Like|2D|3D)?\b", annotation):
                    continue
                offenders.append(
                    f"{path.relative_to(package.parent)}:{argument.lineno}: "
                    f"{function.name}({argument.arg}: {annotation}) -- use PathLike"
                )
    assert not offenders, "polyline parameters that reject a Path:\n  " + "\n  ".join(offenders)


def test_polyline_ratchet_would_catch_a_raw_nesting() -> None:
    """The check above is only worth having if it fires -- this is the shape it must catch."""
    source = "def stroke(path: Sequence[Sequence[float]]) -> None: ...\n"
    tree = ast.parse(source)
    function = _public_functions(tree)[0]
    annotation = ast.unparse(function.args.args[0].annotation)
    assert _RAW_NESTING.search(annotation)
    assert not re.search(r"\bPath(Like|2D|3D)?\b", annotation)
    assert not _RAW_NESTING.search("PathLike | None")


# --- SPEC A-8 / A-9: families are exported whole, plumbing is not exported at all -------------


def test_the_named_families_are_exported_whole() -> None:
    """Where the spec names a family as *the* way to do something, all of it is reachable (A-8).

    Five of the six ``mask2d_*`` were exported and ``mask2d_roundover`` -- the one people actually
    reach for -- was not; the sweep enums were missing while the sweeps they configure were the
    documented API. Neither was a decision, which is what makes a review-only rule the wrong tool.
    """
    import pybosl2

    families = {
        "S-5 rotation algebra": ["Quaternion"],
        "S-10 turtles": ["Turtle2D", "Turtle3D", "turtle2d", "turtle3d"],
        "S-20 sweep vocabulary": ["SweepMethod", "SkinMethod", "SamplingType", "VNFStyle"],
        "S-21 offset-sweep end treatments": [
            "os_circle",
            "os_smooth",
            "os_teardrop",
            "os_chamfer",
            "os_flat",
            "os_profile",
        ],
        "S-26 masks": [
            "mask2d_roundover",
            "mask2d_chamfer",
            "mask2d_cove",
            "mask2d_tear",
            "mask2d_step",
            "mask2d_groove",
            "mask3d_roundover",
            "mask3d_chamfer",
            "mask3d_groove",
            "Mask2D",
            "Mask3D",
        ],
        "S-30 partition profiles": ["PartitionCutType"],
        "S-34 textures": ["texture"],
        "E-1 error family": ["Bosl2Error", "Bosl2ValueError", "UnsupportedByBackendError", "CrossBackendError"],
    }
    missing = {family: [name for name in names if name not in pybosl2.__all__] for family, names in families.items()}
    missing = {family: names for family, names in missing.items() if names}
    assert not missing, f"exported in part, which is drift rather than a decision: {missing}"


def test_no_public_all_advertises_internal_plumbing() -> None:
    """Argument forwarding and signature filtering are not API (SPEC A-9)."""
    import importlib
    import pkgutil

    import pybosl2

    plumbing = {"given_arguments", "for_backend", "refuse_unhonoured", "check_operand_backend"}
    offenders: list[str] = []
    for module_info in pkgutil.walk_packages(pybosl2.__path__, "pybosl2."):
        if "._" in module_info.name or module_info.name.rsplit(".", 1)[-1].startswith("_"):
            continue
        try:
            module = importlib.import_module(module_info.name)
        except Exception:
            continue
        for name in getattr(module, "__all__", []):
            if name in plumbing:
                offenders.append(f"{module_info.name}.__all__ holds {name!r}")
    assert not offenders, "; ".join(offenders)
