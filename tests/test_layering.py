# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The layering is what `spec/layers.toml` says it is (SPEC A-1).

A-1 -- "a lower layer MUST NOT import a higher one" -- was stated for as long as this project has
had a spec and measured for none of it. This walks the import graph and classifies every edge that
runs upwards:

* **runtime, module level** -- the violation. Each one is listed in `known_violations` with what it
  is, and that list only shrinks.
* **type-checking only** -- allowed and unlisted: `if TYPE_CHECKING:` creates no runtime edge, and
  PLAN M-4 requires annotations to use it.
* **deferred, inside a function body** -- allowed only when listed in `allowed_deferred` with a
  reason, which is PLAN M-5's "reserved for genuine cycles and commented when used" made
  checkable.

The layer table here is not the one in SPEC 4. That one could not describe the code even in
principle -- it placed `exceptions`, `enums` and `_edges_lang` above pure geometry, which every
geometry module imports, and omitted six modules. `spec/layers.toml` records the corrected model
and why.
"""

from __future__ import annotations

import ast
import pathlib
import re
import tomllib
from typing import TYPE_CHECKING, NamedTuple

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "pybosl2"
MODEL = tomllib.loads((ROOT / "spec" / "layers.toml").read_text())

LAYERS: dict[str, int] = {module: index for index, members in enumerate(MODEL["layers"].values()) for module in members}
LAYER_NAMES = list(MODEL["layers"])


class Edge(NamedTuple):
    """One import from *source* to *target*, and how it is written."""

    source: str
    target: str
    kind: str  # "runtime" | "typing" | "deferred"
    line: int
    path: str

    @property
    def name(self) -> str:
        """The edge as `spec/layers.toml` spells it."""
        return f"{self.source} -> {self.target}"


def _module_of(path: pathlib.Path) -> str:
    """Return the top-level module or subpackage *path* belongs to."""
    first = path.relative_to(PACKAGE).parts[0]
    return first[:-3] if first.endswith(".py") else first


def _source_name(path: pathlib.Path) -> str:
    """Return the name to report an edge under: the submodule for a package, else the module."""
    parts = path.relative_to(PACKAGE).parts
    if len(parts) > 1 and path.name != "__init__.py":
        return path.stem
    return _module_of(path)


def _edges() -> Iterator[Edge]:
    """Yield every import inside the package that points at another package module."""
    for path in sorted(PACKAGE.rglob("*.py")):
        source_module = _module_of(path)
        if source_module == "__init__":
            continue
        tree = ast.parse(path.read_text())
        deferred: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                deferred.update(id(child) for child in ast.walk(node))
        type_only: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and "TYPE_CHECKING" in ast.dump(node.test):
                type_only.update(id(child) for child in ast.walk(node))
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("pybosl2"):
                targets = [node.module]
            elif isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names if alias.name.startswith("pybosl2")]
            for dotted in targets:
                parts = dotted.split(".")
                if len(parts) < 2 or parts[1] == source_module:
                    continue
                kind = "typing" if id(node) in type_only else ("deferred" if id(node) in deferred else "runtime")
                yield Edge(_source_name(path), parts[1], kind, node.lineno, path.relative_to(ROOT).as_posix())


def _imports_of(module: str) -> set[str]:
    """Return the package modules *module* imports, at any depth inside it."""
    single = PACKAGE / f"{module}.py"
    paths = [single] if single.exists() else list((PACKAGE / module).rglob("*.py"))
    found: set[str] = set()
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("pybosl2"):
                parts = node.module.split(".")
                if len(parts) > 1:
                    found.add(parts[1])
    return found


def _is_cycle(edge: Edge) -> bool:
    """Whether *edge*'s target imports its source back -- PLAN M-5's "genuine cycle"."""
    source = _module_of(ROOT / edge.path)
    return source in _imports_of(edge.target)


EDGES = list(_edges())
UPWARD = [
    edge
    for edge in EDGES
    if LAYERS.get(_module_of(ROOT / edge.path)) is not None
    and LAYERS.get(edge.target) is not None
    and LAYERS[edge.target] > LAYERS[_module_of(ROOT / edge.path)]
]


def test_the_model_covers_every_module() -> None:
    """A module the model forgets is a module the rule cannot be applied to.

    SPEC 4's own table omitted six, which is one reason A-1 was never enforceable.
    """
    modules = {
        _module_of(p)
        for p in PACKAGE.rglob("*.py")
        if _module_of(p) != "__init__" and not _module_of(p).startswith("test")
    }
    assert modules - set(LAYERS) == set(), f"not in spec/layers.toml: {sorted(modules - set(LAYERS))}"
    assert set(LAYERS) - modules == set(), f"in spec/layers.toml but not the package: {sorted(set(LAYERS) - modules)}"


def test_the_graph_was_actually_walked() -> None:
    """A model that matched nothing would pass every test below it."""
    assert len(EDGES) > 300, f"only {len(EDGES)} intra-package imports found; the walker is broken"


@pytest.mark.parametrize("edge", [e for e in UPWARD if e.kind == "runtime"], ids=lambda e: f"{e.name}@{e.line}")
def test_every_runtime_upward_import_is_known_debt(edge: Edge) -> None:
    """A lower layer importing a higher one at module level is A-1's violation."""
    known = MODEL["known_violations"]
    capability = MODEL["capability_edges"]
    assert edge.name in known or edge.name in capability, (
        f"{edge.path}:{edge.line} imports upward at runtime ({edge.name}) and is not in "
        f"spec/layers.toml's known_violations. New upward imports are not accepted: move the "
        f"shared piece down a layer, or build through the façade (SPEC A-10). If it buys a "
        f"capability the layer below cannot have, say which in capability_edges and name the test "
        f"that pins it."
    )


@pytest.mark.parametrize("edge", [e for e in UPWARD if e.kind == "deferred"], ids=lambda e: f"{e.name}@{e.line}")
def test_every_deferred_upward_import_is_a_cycle_or_known_debt(edge: Edge) -> None:
    """PLAN M-5 reserves the function-local import for a genuine cycle.

    A deferred import that is *not* breaking a cycle is a deferred import dodging a layer, which
    is debt rather than architecture -- so it belongs in `known_violations`, not in the allowed
    list. Six of the fourteen deferred up-edges were exactly that when this was first drawn up.
    """
    allowed, known = MODEL["allowed_deferred"], MODEL["known_violations"]
    bridges, capability = MODEL["facade_bridges"], MODEL["capability_edges"]
    assert edge.name in allowed or edge.name in known or edge.name in bridges or edge.name in capability, (
        f"{edge.path}:{edge.line} defers an upward import ({edge.name}) that spec/layers.toml "
        f"does not know about. PLAN M-5 reserves this for a genuine cycle; say which one in "
        f"allowed_deferred, or route the call through the façade (SPEC A-10) and record it in "
        f"facade_bridges."
    )
    if edge.name in allowed:
        assert allowed[edge.name].strip(), f"{edge.name} is listed with an empty reason"


@pytest.mark.parametrize("name", sorted(MODEL["allowed_deferred"]), ids=lambda n: str(n))
def test_an_allowed_deferred_edge_really_is_a_cycle(name: str) -> None:
    """The justification is checked, not taken on trust.

    "It is a cycle" is a claim about the import graph, and the graph is right here -- so an entry
    that says so and is not one fails, rather than sitting in the allowed list forever as prose
    nobody rechecks.
    """
    source, _, target = name.partition(" -> ")
    matching = [e for e in UPWARD if e.name == name and e.kind == "deferred"]
    assert matching, f"{name} is in allowed_deferred but no deferred edge matches it"
    assert source in _imports_of(target), (
        f"{name} is listed as a cycle, but {target} does not import {source} back. "
        f"A deferred import that is not breaking a cycle is dodging a layer: move it to "
        f"known_violations, or route the call through the façade (SPEC A-10)."
    )


def test_the_debt_lists_are_not_stale() -> None:
    """An entry for an edge that no longer exists makes the list look worse than the code is.

    Or for an edge of the wrong *kind*, which is how four entries sat in `known_violations` that
    had never belonged there: `color -> _shape`, `distributors -> _shape`, `path3d -> shapes3d`
    and `turtle3d -> shapes3d` exist only under `if TYPE_CHECKING`, which the model calls allowed
    and unlisted. This asked whether the edge existed and got "yes" for all four -- a check that
    reads the right table and asks it the wrong question.
    """
    live = {edge.name for edge in UPWARD if edge.kind != "typing"}
    # Every pair of sections, not just the two T55 thought of. An edge listed twice is counted
    # twice, and three were: `_helpers -> shapes2d`, `_helpers -> shapes3d` and
    # `vnf -> isosurface` sat in `known_violations` *and* `allowed_deferred`, each with a debt row
    # claiming a module-level import that no longer existed. T55 added this check for
    # `capability_edges` alone and missed them, which is what a check aimed at one pair does.
    sections = ("known_violations", "allowed_deferred", "facade_bridges", "capability_edges")
    for i, first in enumerate(sections):
        for second in sections[i + 1 :]:
            overlap = sorted(set(MODEL[first]) & set(MODEL[second]))
            assert not overlap, (
                f"these are listed in both {first} and {second}: {overlap}. An edge is one thing, "
                f"and counting it twice is how a debt figure stops meaning anything."
            )
    deferred = {edge.name for edge in UPWARD if edge.kind == "deferred"}
    stale = sorted(set(MODEL["known_violations"]) - live)
    assert not stale, (
        f"spec/layers.toml [known_violations] lists edges that are not debt: {stale}. Either they "
        f"no longer exist, or they exist only under `if TYPE_CHECKING`, which creates no runtime "
        f"dependency and is allowed unlisted."
    )
    stale = sorted(set(MODEL["allowed_deferred"]) - deferred)
    assert not stale, f"spec/layers.toml [allowed_deferred] lists edges that are no longer deferred: {stale}"
    stale = sorted(set(MODEL["facade_bridges"]) - deferred)
    assert not stale, f"spec/layers.toml [facade_bridges] lists edges that are no longer deferred: {stale}"


@pytest.mark.parametrize("name", sorted(MODEL["facade_bridges"]), ids=lambda n: str(n))
def test_a_facade_bridge_really_targets_the_facade(name: str) -> None:
    """The A-10 bridge is allowed because of where it points, so that is what gets checked."""
    _, _, target = name.partition(" -> ")
    facade = MODEL["layers"]["L4_facade"]
    assert target in facade, (
        f"{name} is listed as a façade bridge, but {target} is not a façade module ({facade}). "
        f"Only the neutral façade may be reached this way (SPEC A-10)."
    )


def test_the_known_violation_count_only_shrinks() -> None:
    """The ratchet. Fixing an edge means deleting its row; nothing may add one."""
    budget = 3
    count = len(MODEL["known_violations"])
    assert count <= budget, f"{count} known violations, budget {budget}"
    if count < budget:
        pytest.fail(f"{count} known violations, budget {budget} -- lower the budget to {count}")


@pytest.mark.parametrize("name", sorted(MODEL["capability_edges"]), ids=lambda n: str(n))
def test_a_capability_edge_is_live_and_pinned(name: str) -> None:
    """`capability_edges` says an edge is permanent. That claim gets checked, twice.

    An entry here is an upward import nobody is going to remove, because removing it removes
    something the library can do. Three sat in `known_violations` first, each with a *different*
    stated reason, and all three reasons were wrong -- so the bar for moving one out of the debt
    list is that the capability is **pinned by a named test**, not that someone found the edge
    hard to fix.

    Checked here: the edge still exists (an entry for a vanished import makes the architecture
    look worse than it is), and the test it names exists and is about the module in question. What
    that test asserts is the capability itself, which is the part no layering check can see.
    """
    assert name in {edge.name for edge in UPWARD}, (
        f"{name} is listed as a capability edge but no upward import matches it -- delete the row"
    )
    entry = MODEL["capability_edges"][name]
    reason, pinned_by = entry["reason"].strip(), entry["pinned_by"].strip()
    assert reason, f"{name} is listed with an empty reason"

    path, _, test_name = pinned_by.partition("::")
    source = ROOT / path
    assert source.is_file(), f"{name} names {path}, which does not exist"
    text = source.read_text()
    assert re.search(rf"^\s*def {re.escape(test_name)}\b", text, re.MULTILINE), (
        f"{name} names {pinned_by}, and that test is not in the file"
    )
    edge_source = name.partition(" -> ")[0]
    assert edge_source in text, (
        f"{pinned_by} is named as pinning {name} but never mentions {edge_source} -- it cannot be "
        f"holding that capability in place"
    )
