# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A call that looks backend-neutral must be one, or say it is not (SPEC A-6, PAR-1, B-4).

This campaign has found the same defect five separate times, and each time it was found by
accident while looking at something else:

* `partition_mask`/`partition_cut_mask` returned a `CsgSolid` inside an `sdf` block, hidden
  because `arc()` refused on their behalf (T50);
* `path_extrude`/`path_extrude2d` failed from inside with a raw `AttributeError` (T51);
* `Region.debug_region(vertices=True)` surfaced `text3d`'s name three frames down (T53);
* `debug_bezier_patches` re-wrapped an `SdfSolid` into a CSG wrapper and blamed the union (T58);
* and T133's six: `Path3D.dashed_stroke`, `extrude_from_to`, `cylindrical_extrude`, `chain_hull`,
  `minkowski_difference` and `masking.rounding_edge_mask`.

Nothing scanned for it. `tests/test_neutral_geometry_is_not_gated.py` checks the *marked*
functions -- that nothing refuses for no reason -- and the converse had no check at all: a
function that builds CSG whatever the backend and declares nothing. So five of them were in the
code at once, two of them in a module whose own layering row says a mask cutter is built by
whichever backend is active.

Two checks here, because neither alone is enough. The **static** one is cheap and runs over the
whole package, and it has a blind spot this file states rather than hides: it sees a native reach
written as an import or a call to a native alias, and not one that arrives through a helper in
another module -- which is why it misses `extrude_from_to`, whose only native reach is
`_as_native_2d(profile).linear_extrude(...)`. The **dynamic** one has no blind spot and no reach:
it calls each function and looks at what comes back.
"""

from __future__ import annotations

import ast
import pathlib
import re
import textwrap

import pytest

from pybosl2 import use_backend
from pybosl2.exceptions import UnsupportedByBackendError

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "pybosl2"

#: Return annotations naming a solid one backend owns. `Path2D`, `Region` and `VNF` are neutral --
#: a function returning one of those has nothing to hand back that could belong to a backend --
#: and `Solid`/`Flat` are the façade's own protocol names, which are whatever is active.
OWNED = re.compile(r"\b(Bosl2Solid|Bosl2Shape2D|CsgSolid|CsgShape2D)\b")

#: The packages the native handles belong to.
NATIVE_PACKAGES = frozenset({"pythonscad", "openscad"})

#: The residue, with the reason each one is not the defect above. Every entry is inside the CSG
#: backend's own code, where reaching a native handle is the module's job.
ALLOWED: dict[str, str] = {
    "pybosl2/_stroke3d.py::stroke_3d": (
        "the CSG backend's own `stroke`, reached through the protocol -- `CsgBackend.stroke` "
        "forwards here, and the inner `_stroke_3d_csg` carries the marker"
    ),
    "pybosl2/miscellaneous.py::minkowski_difference": (
        "dispatches to the active backend's own method first; the native body below it is the CSG "
        "implementation that `Bosl2Solid.minkowski_difference` forwards to"
    ),
    "pybosl2/shapes2d/base.py::fill": "a method on the CSG 2-D shape class, so CSG by construction",
    "pybosl2/shapes2d/base.py::hull": "a method on the CSG 2-D shape class, so CSG by construction",
    "pybosl2/shapes3d/base.py::hull": "a method on the CSG solid class, so CSG by construction",
    "pybosl2/shapes3d/base.py::offset3d": "a method on the CSG solid class, so CSG by construction",
    "pybosl2/shapes3d/cylinder.py::cyl": "the CSG backend's own constructor; `pybosl2.solid.cyl` is the neutral door",
}


def _marked(node: ast.FunctionDef) -> bool:
    """Say whether *node* declares which backend it builds for."""
    decorators = " ".join(ast.unparse(d) for d in node.decorator_list)
    return "backend_only" in decorators or "builds_with" in decorators


def _native_aliases(tree: ast.Module) -> set[str]:
    """Return the module-level names bound to a native handle.

    Both spellings: `from pythonscad import square as _osquare`, and the `native("square")`
    lookup the package uses when the wheel is absent. A call to one of these is a native reach
    however far from the import it is written.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in NATIVE_PACKAGES:
            names |= {alias.asname or alias.name for alias in node.names}
        elif isinstance(node, ast.Import):
            names |= {
                alias.asname or alias.name.split(".")[0]
                for alias in node.names
                if alias.name.split(".")[0] in NATIVE_PACKAGES
            }
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            function = node.value.func
            if isinstance(function, ast.Name) and function.id == "native":
                names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def _builds_with_names(sources: "dict[str, str]") -> set[str]:
    """Return every `@builds_with` function's name: calling one is a native reach by proxy."""
    found: set[str] = set()
    for source in sources.values():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.FunctionDef) and any("builds_with" in ast.unparse(d) for d in node.decorator_list):
                found.add(node.name)
    return found


def _why_native(node: ast.FunctionDef, aliases: "set[str]", builds: "set[str]") -> str | None:
    """Return how *node* reaches a native handle, or None if it does not."""
    for inner in ast.walk(node):
        if isinstance(inner, ast.ImportFrom) and (inner.module or "").split(".")[0] in NATIVE_PACKAGES:
            return f"imports {inner.module}"
        if isinstance(inner, ast.Import) and any(a.name.split(".")[0] in NATIVE_PACKAGES for a in inner.names):
            return "imports a native module"
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
            if inner.func.id in builds:
                return f"calls {inner.func.id}(), which is @builds_with"
            if inner.func.id in aliases:
                return f"calls the native {inner.func.id}"
    return None


def _unmarked_native_builders(sources: "dict[str, str]") -> "dict[str, str]":
    """Return every public callable that returns a backend-owned solid and reaches native CSG."""
    builds = _builds_with_names(sources)
    found: dict[str, str] = {}
    for path, source in sources.items():
        tree = ast.parse(source)
        aliases = _native_aliases(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.returns is None or _marked(node):
                continue
            if node.name.startswith("_"):
                continue
            if not OWNED.search(ast.unparse(node.returns).strip("'\"")):
                continue
            why = _why_native(node, aliases, builds)
            if why is not None:
                found[f"{path}::{node.name}"] = why
    return found


def _package_sources() -> "dict[str, str]":
    """Return every non-SDF module in the package, keyed by its path from the repository root."""
    return {
        str(path.relative_to(ROOT)): path.read_text()
        for path in sorted(PACKAGE.rglob("*.py"))
        if path.parts[-2] != "sdf"
    }


def test_no_unmarked_native_builder_returns_a_backend_owned_solid() -> None:
    """The ratchet: a new one of these fails here rather than being found by accident later."""
    found = _unmarked_native_builders(_package_sources())
    unexpected = {name: why for name, why in found.items() if name not in ALLOWED}
    assert not unexpected, (
        "these return a solid one backend owns and reach native CSG, without saying which backend "
        'they build for -- so inside `use_backend("sdf")` they hand back a `CsgSolid` that will '
        "not combine with its surroundings (SPEC A-6):\n  "
        + "\n  ".join(f"{name} -- {why}" for name, why in sorted(unexpected.items()))
        + '\nMark it `@backend_only("csg")` if it is genuinely CSG-only, build it through the '
        "façade if it is not, or add it to ALLOWED with the reason it is neither."
    )


def test_the_allowlist_has_not_gone_stale() -> None:
    """An entry for something the scan no longer reports makes the residue look bigger than it is.

    The same failure mode as `spec/layers.toml`'s debt rows, which carried four entries that had
    never belonged and three counted twice (T50, T56).
    """
    found = _unmarked_native_builders(_package_sources())
    stale = sorted(set(ALLOWED) - set(found))
    assert not stale, f"ALLOWED lists entries the scan does not report any more: {stale} -- delete them"


def test_the_scan_sees_a_planted_violation() -> None:
    """The control. A scan that matched nothing would pass the ratchet above for the wrong reason."""
    planted = textwrap.dedent(
        '''
        from pybosl2.shapes3d import Bosl2Solid

        def plausible_helper(size: float) -> Bosl2Solid:
            """Looks neutral, builds CSG."""
            from pythonscad import cube as _ocube

            return Bosl2Solid(_ocube([size, size, size]))
        '''
    )
    found = _unmarked_native_builders({"planted.py": planted})
    assert "planted.py::plausible_helper" in found, f"the scan missed a plain violation: {found}"

    aliased = textwrap.dedent(
        '''
        from pybosl2._native import native

        _ocube = native("cube")

        def by_alias(size: float) -> "Bosl2Solid":
            """The other spelling: a module-level native alias, called far from its binding."""
            return Bosl2Solid(_ocube([size, size, size]))
        '''
    )
    found = _unmarked_native_builders({"aliased.py": aliased})
    assert "aliased.py::by_alias" in found, f"the scan missed the native-alias spelling: {found}"


def test_the_scan_leaves_a_declared_builder_alone() -> None:
    """The other control: marking a function is the thing that clears it, so that must work."""
    declared = textwrap.dedent(
        '''
        from pybosl2._backend import backend_only
        from pybosl2.shapes3d import Bosl2Solid

        @backend_only("csg")
        def honest(size: float) -> Bosl2Solid:
            """Says what it builds."""
            from pythonscad import cube as _ocube

            return Bosl2Solid(_ocube([size, size, size]))
        '''
    )
    assert _unmarked_native_builders({"declared.py": declared}) == {}, (
        "a @backend_only function is still reported, so marking one does not clear it and the "
        "ratchet cannot be satisfied by doing the right thing"
    )


# ---------------------------------------------------------------------------
# The dynamic half: what actually comes back.
# ---------------------------------------------------------------------------


def _square_path() -> "object":
    from pybosl2.path2d import Path2D

    return Path2D([[-5.0, -5.0], [5.0, -5.0], [5.0, 5.0], [-5.0, 5.0]], closed=True)


def _calls() -> "dict[str, object]":
    """The six T133 found, by the call a caller would write."""
    from pybosl2.masking import rounding_edge_mask
    from pybosl2.miscellaneous import chain_hull, cylindrical_extrude, extrude_from_to, minkowski_difference
    from pybosl2.path3d import Path3D
    from pybosl2.solid import cuboid, sphere

    path = Path3D([[0.0, 0.0, 0.0], [30.0, 0.0, 0.0], [30.0, 20.0, 10.0]])
    return {
        "Path3D.dashed_stroke": lambda: path.dashed_stroke(dashpat=[5, 2]),
        "extrude_from_to": lambda: extrude_from_to(_square_path(), [0, 0, 0], [0, 0, 20]),
        "cylindrical_extrude": lambda: cylindrical_extrude(_square_path(), inner_radius=10, outer_radius=12),
        "chain_hull": lambda: chain_hull([sphere(radius=4), sphere(radius=4).translate([15, 0, 0])]),
        "minkowski_difference": lambda: minkowski_difference(cuboid(size=20), sphere(radius=3)),
        "rounding_edge_mask": lambda: rounding_edge_mask(length=20, radius=3),
    }


@pytest.mark.parametrize("name", sorted(_calls()))
def test_each_builder_follows_the_backend_or_refuses_by_name(name: str) -> None:
    """Under `sdf`: an sdf-backed solid, or a refusal naming the call. Never a `CsgSolid`.

    Measured before the fix, these were: a `CsgSolid` with `backend == "csg"` from
    `Path3D.dashed_stroke`, `extrude_from_to`, `cylindrical_extrude` and `rounding_edge_mask`; a
    raw `TypeError: Error during parsing hull` out of the native parser from `chain_hull`; and a
    `Bosl2ValueError` about a missing native bounding box, three frames down, from
    `minkowski_difference`. Six functions, four distinct ways of not saying it (SPEC E-1, E-6).
    """
    build = _calls()[name]

    with use_backend("csg"):
        on_csg = build()
    assert getattr(on_csg, "backend", None) == "csg", f"{name} does not build on csg either: {on_csg!r}"

    refusal: UnsupportedByBackendError | None = None
    on_sdf: object = None
    with use_backend("sdf"):
        try:
            on_sdf = build()
        except UnsupportedByBackendError as raised:
            refusal = raised
    if refusal is not None:
        head = name.split(".")[-1]
        assert head in str(refusal), (
            f"{name} refuses the sdf backend without naming itself: {refusal}. A refusal a "
            f"caller cannot act on is the defect T51 and T53 both found (SPEC E-6)."
        )
        return
    assert getattr(on_sdf, "backend", None) == "sdf", (
        f"{name} returned {type(on_sdf).__name__} with backend="
        f'{getattr(on_sdf, "backend", None)!r} from inside `use_backend("sdf")`. A solid the '
        f"other backend owns will not combine with its surroundings, and nothing said so (A-6)."
    )


def test_the_dynamic_check_can_see_a_foreign_solid() -> None:
    """The control for the half with no blind spot: a csg solid inside an sdf block must fail it."""
    from pybosl2.shapes3d import cuboid as csg_cuboid

    with use_backend("sdf"), use_backend("csg"):
        leaked = csg_cuboid(size=10)
    assert leaked.backend == "csg", "the fixture is not a csg solid, so it controls nothing"
    assert getattr(leaked, "backend", None) != "sdf", (
        "a solid built by the csg backend reports backend == 'sdf', so the assertion above cannot "
        "tell a foreign solid from a native one"
    )
