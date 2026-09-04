# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""One scan over the public signatures, closing six rules at once (T39).

The triage in T38 found nineteen requirements that are mechanically checkable and simply
unchecked. Six of them are the same scan asked six ways, so they get one:

* **SPEC P-5, D-1 and PLAN T-9a** -- everything past the subject argument is keyword-only, so no
  caller can depend on positional order for placement, resolution or an escape hatch.
* **SPEC D-2** -- one required parameter is the target; a second needs a written justification;
  three is never acceptable. Checked for the mask factories since T22 and nowhere else. Scoped to
  callables that **return geometry**, because that is what §8.1's tiers are about and what the
  rule's own examples are (`Screw(spec, length)`, `prismoid(size1, size2)`): `slerp(a, b, t)`
  takes three operands and is not a constructor with two parameters too many.
* **PLAN R-P1** -- the facet controls are spelled `fn: int | None`, `fa`/`fs: float | None`.
* **PLAN O-6b** -- a parameter meaning "which face, edge or corner" is typed in the anchor
  language, never a bare string or a plain vector. This is the rule `flat.text()` broke with
  `anchor: str = "baseline"` for as long as it existed, until T36; nothing was looking.

**Scope, which is part of the rule.** Names a module exports through `__all__`, **plus everything
the top-level lazy table exports** -- a module without an `__all__` can still hold public API, and
skipping those is how `text3d`'s string anchor survived this scan's first version even though
`flat.text()`'s identical one had just been fixed. Only module-level functions and the methods of
module-level classes -- a nested `def` has no public parameters, and
counting one puts an entry on a list no conversion can remove (the lesson PLAN T-4c records). The
first version of this scan ignored that and reported 316 violations, most of them a decorator's
inner function whose `fn` is a *function*, not a facet count.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "pybosl2"

#: Parameters in the placement, resolution and escape-hatch tiers (SPEC §8.1). Everything here
#: belongs past the `*`.
TIERS = frozenset({"anchor", "spin", "orient", "center", "fn", "fa", "fs", "res", "convexity"})

#: Public callables with three or more required parameters, per file. SPEC D-2 says three is never
#: acceptable; these predate the rule being checked anywhere but the masks. Only shrinks.
TOO_MANY_REQUIRED: dict[str, int] = {
    "_backend.py": 2,
    "caps.py": 1,
    "miscellaneous.py": 1,
    "path2d.py": 1,
    "path3d.py": 1,
    "surfaces3d.py": 1,
    "textures.py": 1,
}

#: Public callables taking a tier parameter positionally, per file. Only shrinks.
POSITIONAL_TIERS: dict[str, int] = {
    "_backend.py": 18,
    "_edges_lang.py": 3,
    "_shape.py": 1,
    "beziers.py": 1,
    "bounds.py": 2,
    "defaults.py": 4,
    "distributors.py": 5,
    "groups.py": 3,
    "masking.py": 9,
    "miscellaneous.py": 4,
    "partitions.py": 5,
    "parts/ball_bearings.py": 1,
    "parts/bottlecaps.py": 4,
    "parts/linear_bearings.py": 3,
    "path2d.py": 7,
    "path3d.py": 1,
    "regions.py": 5,
    "rounding.py": 4,
    "shapes2d/circle.py": 5,
    "shapes2d/curves.py": 4,
    "shapes2d/ops.py": 2,
    "shapes2d/square.py": 4,
    "shapes3d/cylinder.py": 1,
    "shapes3d/extrusions.py": 5,
    "solid.py": 1,
    "surfaces3d.py": 6,
    "svg.py": 5,
    "textures.py": 1,
}


def _lazy_exports() -> dict[str, set[str]]:
    """Return {module file: names} for everything `pybosl2/__init__.py` re-exports.

    The top-level table is the public surface a caller actually sees, and it reaches modules that
    declare no `__all__` of their own.
    """
    import pybosl2

    out: dict[str, set[str]] = {}
    for name in pybosl2._LAZY_EXPORTS:
        try:
            value = getattr(pybosl2, name)
        except Exception:  # pragma: no cover - a name whose backend is absent here
            continue
        # Resolve to where it is *defined*, not where it is re-exported from: the table says
        # `text3d` comes from `pybosl2.shapes3d`, which imports it from `shapes3d/extrusions.py`,
        # and looking only at the re-exporting package is how its string anchor stayed invisible.
        module = getattr(value, "__module__", "")
        if not module.startswith("pybosl2"):
            continue
        relative = module.removeprefix("pybosl2.").replace(".", "/") + ".py"
        out.setdefault(relative, set()).add(getattr(value, "__name__", name))
    return out


LAZY = _lazy_exports()


def _exported(tree: ast.Module, relative: str) -> set[str]:
    """Return the public names of a module: its `__all__`, plus what the top level re-exports."""
    names = set(LAZY.get(relative, set()))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "__all__" for t in node.targets):
            names |= {e.value for e in ast.walk(node.value) if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return names


def _public_callables() -> list[tuple[str, str, ast.FunctionDef]]:
    """Return (file, name, node) for every exported function and exported class's public methods."""
    found: list[tuple[str, str, ast.FunctionDef]] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).as_posix()
        tree = ast.parse(path.read_text())
        exported = _exported(tree, relative)
        if not exported:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in exported:
                found.append((relative, node.name, node))
            elif isinstance(node, ast.ClassDef) and node.name in exported:
                found += [
                    (relative, f"{node.name}.{m.name}", m)
                    for m in node.body
                    if isinstance(m, ast.FunctionDef) and not m.name.startswith("_")
                ]
    return found


CALLABLES = _public_callables()


def test_the_scan_found_the_public_surface() -> None:
    """A scan that matched nothing would make every check below vacuous."""
    assert len(CALLABLES) > 300, f"only {len(CALLABLES)} public callables found; the scan is broken"


def _required(node: ast.FunctionDef) -> list[str]:
    """The parameters a caller must supply positionally."""
    positional = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
    return positional[: len(positional) - len(node.args.defaults)]


def _counts(predicate: object) -> dict[str, list[str]]:
    """Group the callables matching *predicate* by file."""
    out: dict[str, list[str]] = {}
    for relative, name, node in CALLABLES:
        if predicate(node):  # type: ignore[operator]
            out.setdefault(relative, []).append(name)
    return out


#: Return annotations that mean "this makes geometry", which is the frame SPEC §8.1 argues in.
SHAPES = ("Solid", "Flat", "Shape", "VNF", "Path2D", "Path3D", "Region", "Bosl2Solid", "PyShape")


def _builds_geometry(node: ast.FunctionDef) -> bool:
    """Whether the callable returns geometry, and so falls under the argument tiers."""
    if node.returns is None:
        return False
    returns = ast.unparse(node.returns).strip("\"'")
    return any(s in returns for s in SHAPES)


TOO_MANY = _counts(lambda n: _builds_geometry(n) and len(_required(n)) > 2)
POSITIONAL = _counts(lambda n: any(a.arg in TIERS for a in n.args.args if a.arg not in ("self", "cls")))


@pytest.mark.parametrize("path", sorted(set(TOO_MANY) | set(TOO_MANY_REQUIRED)))
def test_no_file_grows_its_three_argument_callables(path: str) -> None:
    """SPEC D-2: three required parameters is never acceptable."""
    actual, budget = len(TOO_MANY.get(path, [])), TOO_MANY_REQUIRED.get(path, 0)
    if actual > budget:
        pytest.fail(
            f"{path} has {actual} exported callables with three or more required parameters, "
            f"budget {budget}: {sorted(TOO_MANY[path])[:4]}. Give the extras defaults, or derive "
            f"them (SPEC P-3)."
        )
    if actual < budget:
        pytest.fail(f"{path} is down to {actual} from {budget}; lower its entry in TOO_MANY_REQUIRED.")


@pytest.mark.parametrize("path", sorted(set(POSITIONAL) | set(POSITIONAL_TIERS)))
def test_no_file_grows_its_positional_tier_parameters(path: str) -> None:
    """SPEC P-5 and D-1, PLAN T-9a: placement, resolution and escape hatches are keyword-only."""
    actual, budget = len(POSITIONAL.get(path, [])), POSITIONAL_TIERS.get(path, 0)
    if actual > budget:
        pytest.fail(
            f"{path} has {actual} exported callables taking a tier parameter positionally, budget "
            f"{budget}: {sorted(POSITIONAL[path])[:4]}. Put a bare `*` before it."
        )
    if actual < budget:
        pytest.fail(f"{path} is down to {actual} from {budget}; lower its entry in POSITIONAL_TIERS.")


def test_the_budgets_name_no_file_that_is_gone() -> None:
    """A row for a deleted file makes the debt look larger than it is."""
    for label, budget in (("TOO_MANY_REQUIRED", TOO_MANY_REQUIRED), ("POSITIONAL_TIERS", POSITIONAL_TIERS)):
        missing = sorted(name for name in budget if not (PACKAGE / name).exists())
        assert not missing, f"{label} names files that no longer exist: {missing}"


def test_every_facet_parameter_is_spelled_the_same_way() -> None:
    """PLAN R-P1: `fn: int | None`, `fa`/`fs: float | None`, everywhere and with no exceptions.

    Clean when first measured, which is why it has no budget: a second spelling would be a new
    defect, not old debt.
    """
    wanted = {"fn": {"int | None", "int"}, "fa": {"float | None", "float"}, "fs": {"float | None", "float"}}
    wrong = [
        f"{path}::{name} {a.arg}: {ast.unparse(a.annotation)}"
        for path, name, node in CALLABLES
        for a in node.args.args + node.args.kwonlyargs
        if a.arg in wanted and a.annotation is not None and ast.unparse(a.annotation) not in wanted[a.arg]
    ]
    assert not wrong, "facet controls with another spelling (PLAN R-P1):\n  " + "\n  ".join(wrong)


def test_every_anchor_parameter_speaks_the_anchor_language() -> None:
    """PLAN O-6b, SPEC C-10: an anchor is `Anchor | Sequence[float]`, never a bare string.

    `flat.text()` took `anchor: str = "baseline"` for as long as it existed and nothing noticed
    until T36 went looking by hand. `Any` is allowed only on the shape protocols, where PLAN T-6c
    sanctions it to bridge two backends' spellings.
    """
    wrong = [
        f"{path}::{name} anchor: {ast.unparse(a.annotation)}"
        for path, name, node in CALLABLES
        for a in node.args.args + node.args.kwonlyargs
        if a.arg == "anchor"
        and a.annotation is not None
        and "Anchor" not in ast.unparse(a.annotation)
        and ast.unparse(a.annotation) != "Any"
    ]
    assert not wrong, "anchors outside the anchor language (PLAN O-6b):\n  " + "\n  ".join(wrong)
