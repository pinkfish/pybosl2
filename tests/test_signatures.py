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
#: **Empty since T75.** Every exported callable puts placement, resolution and escape-hatch
#: parameters behind a bare `*`. The four exceptions are not listed here but recognised by
#: `_resolves_tiers`: a callable whose every positional parameter is a tier and which builds no
#: geometry is deciding what the placement will be, not placing a shape, and has nothing for a
#: `*` to separate.
POSITIONAL_TIERS: dict[str, int] = {}


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


def _resolves_tiers(node: ast.FunctionDef) -> bool:
    """Whether this callable's subject *is* the tier, so there is nothing for a `*` to separate.

    `resolve_facets(fn, fa, fs)` and `set_defaults(fn, fa, fs, res)` take tiers and hand tiers
    back; they are not placing a shape, they are deciding what the placement will be. Putting a
    bare `*` after the first one, which is what T-9a says literally, turns every internal call
    into `resolve_facets(fn, fa=fa, fs=fs)` -- noise in service of a rule about callers not
    depending on positional order, where the caller is this package.

    The rule has two halves and needs both. *Every* positional parameter is a tier, so there is no
    shape argument for them to trail; **and** it does not build geometry, because a constructor
    whose only parameters are tiers is still a constructor. That second half is what keeps this
    from being a list of whatever was inconvenient: `BottleCaps.pco1881_neck(fn, fa, fs)` passes
    the first test and fails this one, and `pco1881_neck(32)` is exactly the call T-9a prevents.
    """
    positional = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
    return bool(positional) and all(name in TIERS for name in positional) and not _builds_geometry(node)


def _tier_in_the_tail(node: ast.FunctionDef) -> bool:
    """Whether a tier parameter sits *past* the subject argument, which is what T-9a forbids.

    PLAN T-9a says "everything past the subject argument goes after a bare `*`", so a tier name at
    position 0 is the subject and is compliant: `shape.align(Anchor.TOP, child)` names the face the
    operation is about, and `resolve_anchor(anchor)` takes the anchor as its operand. This counted
    those too, which inflated the figure by twelve against the rule's own words.
    """
    if _resolves_tiers(node):
        return False
    positional = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
    return any(name in TIERS for name in positional[1:])


POSITIONAL = _counts(_tier_in_the_tail)


def test_the_subject_exemption_is_only_the_first_parameter() -> None:
    """PLAN T-9a: "past the subject argument" is position 0, and nothing wider.

    The exemption is the one place this scan can be quietly weakened -- widen it by one and the
    count drops without a line of code changing. So it is exercised on both sides: a tier name at
    position 0 is compliant, and the same name one place later is not.
    """
    subject = ast.parse("def f(anchor, size): ...").body[0]
    tail = ast.parse("def f(size, anchor): ...").body[0]
    assert isinstance(subject, ast.FunctionDef)
    assert isinstance(tail, ast.FunctionDef)
    assert not _tier_in_the_tail(subject), "a tier name at position 0 is the subject argument"
    assert _tier_in_the_tail(tail), "a tier name past the subject is what the rule forbids"

    method = ast.parse("def f(self, anchor, child): ...").body[0]
    assert isinstance(method, ast.FunctionDef)
    assert not _tier_in_the_tail(method), "`self` is the receiver, not the subject argument"


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


@pytest.mark.parametrize("path", sorted(set(POSITIONAL) | set(POSITIONAL_TIERS)) or ["(none)"])
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


def test_every_exported_callable_keeps_its_tiers_behind_a_star() -> None:
    """SPEC P-5, D-1, PLAN T-9a -- the whole rule in one assertion, now that it holds everywhere.

    The per-file ratchet above parametrizes over the files that carry debt, so with the debt gone
    it parametrizes over nothing and runs as a single placeholder. That is the right shape for a
    ratchet and the wrong shape for a finished rule: a scan that returned an empty result for any
    reason would pass it. This states the rule directly instead, and is what would fail if the
    exemption were widened or the walk stopped reaching a package.
    """
    offenders = {path: sorted(names) for path, names in POSITIONAL.items() if names}
    assert not offenders, (
        f"exported callables taking a tier parameter positionally: {offenders}. Put a bare `*` "
        f"before it -- or, if its subject *is* the tier, see `_resolves_tiers`."
    )
    assert len(CALLABLES) > 500, f"only {len(CALLABLES)} callables scanned; the walk is broken"


def test_the_resolver_exemption_covers_what_it_should_and_no_more() -> None:
    """PLAN T-9a: the exemption is the one way this rule can be emptied without changing code.

    Four callables use it, and each is checked by name: they take tiers and hand tiers back. The
    pairing is `BottleCaps.pco1881_neck(fn, fa, fs)`, whose parameters are *also* all tiers and
    which is not exempt, because it builds geometry -- a constructor whose only parameters are
    tiers is still a constructor, and `pco1881_neck(32)` is exactly the call T-9a prevents.
    """
    # Scoped to `CALLABLES`, the exported surface the rule applies to. `EVERY_SIGNATURE` is the
    # wide walk O-6b uses for a *type* rule; a private helper taking tiers positionally is nobody's
    # call surface, and counting one would put an entry on this list that no conversion removes.
    # Scoped to `CALLABLES`, the exported surface the rule applies to -- `EVERY_SIGNATURE` is the
    # wide walk O-6b uses for a *type* rule, and a private helper taking tiers positionally is
    # nobody's call surface.
    #
    # Only the ones with **two or more** positional tiers are asserted, because those are where
    # this exemption does any work. Nine callables satisfy `_resolves_tiers`; five take a single
    # tier and are already the subject argument, so they are exempt twice over and say nothing
    # about whether this rule is too wide.
    load_bearing = {
        f"{path}::{name}"
        for path, name, node in CALLABLES
        if _resolves_tiers(node)
        and sum(1 for a in node.args.args if a.arg in TIERS and a.arg not in ("self", "cls")) >= 2
    }
    assert load_bearing == {
        "defaults.py::set_defaults",
        "defaults.py::use_defaults",
        "defaults.py::resolve_facets",
        "groups.py::Facets.resolved",
    }, sorted(load_bearing)


#: Exported callables taking `**kwargs`, per file. A public signature that accepts anything and
#: documents nothing is not a contract (SPEC P-5b). Only shrinks.
#:
#: 21 of these are on `Shape`/`Solid` themselves, where the cost is highest: a protocol declaring
#: `edge_mask(*args, **kwargs)` has declared the *name* of an operation and nothing else, which is
#: the same defect as omitting it (C-20) arriving by a different road.
OPAQUE_KWARGS: dict[str, int] = {
    "_backend.py": 7,
    "_shape.py": 1,
    "flat.py": 6,
}

#: Exported callables whose `*args` carries no element type. `*shapes: Solid` says what an n-ary
#: operation accepts; `*args: Any` says only that there may be several of something. Only shrinks.
UNTYPED_VARARGS: dict[str, int] = {
    "_backend.py": 8,
    "_shape.py": 2,
    "flat.py": 5,
    "miscellaneous.py": 2,
}

#: Annotations that name no type. `object` is here with `Any`: a variadic typed `object` accepts
#: everything, which is what the rule is about, whatever the spelling.
UNTYPED = frozenset({"Any", "object", "(none)"})


def _variadics() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Exported callables taking `**kwargs`, and those whose `*args` names no element type."""
    kwargs_users: dict[str, list[str]] = {}
    untyped: dict[str, list[str]] = {}
    for path, name, node in CALLABLES:
        if node.args.kwarg is not None:
            kwargs_users.setdefault(path, []).append(name)
        vararg = node.args.vararg
        if vararg is None:
            continue
        annotation = ast.unparse(vararg.annotation).strip("\"'") if vararg.annotation else "(none)"
        if annotation in UNTYPED:
            untyped.setdefault(path, []).append(name)
    return kwargs_users, untyped


KWARGS_USERS, UNTYPED_VARIADICS = _variadics()


@pytest.mark.parametrize("path", sorted(set(KWARGS_USERS) | set(OPAQUE_KWARGS)) or ["(none)"])
def test_no_public_callable_takes_untyped_variadics(path: str) -> None:
    """SPEC P-5b: `**kwargs` on a public signature accepts anything and documents nothing."""
    actual, budget = len(KWARGS_USERS.get(path, [])), OPAQUE_KWARGS.get(path, 0)
    if actual > budget:
        pytest.fail(
            f"{path} has {actual} exported callables taking `**kwargs`, budget {budget}: "
            f"{sorted(KWARGS_USERS[path])[:4]}. Name the parameters the call actually takes."
        )
    if actual < budget:
        pytest.fail(f"{path} is down to {actual} from {budget}; lower its entry in OPAQUE_KWARGS.")


@pytest.mark.parametrize("path", sorted(set(UNTYPED_VARIADICS) | set(UNTYPED_VARARGS)) or ["(none)"])
def test_a_variadic_is_only_for_a_genuinely_n_ary_operation(path: str) -> None:
    """SPEC P-5b: `*shapes: Solid` says what it accepts; `*args: Any` says only "several"."""
    actual, budget = len(UNTYPED_VARIADICS.get(path, [])), UNTYPED_VARARGS.get(path, 0)
    if actual > budget:
        pytest.fail(
            f"{path} has {actual} exported callables whose `*args` names no element type, budget "
            f"{budget}: {sorted(UNTYPED_VARIADICS[path])[:4]}. Type it, or spell the parameters out."
        )
    if actual < budget:
        pytest.fail(f"{path} is down to {actual} from {budget}; lower its entry in UNTYPED_VARARGS.")


def test_a_typed_n_ary_variadic_is_not_counted() -> None:
    """SPEC P-5b: the rule permits `*shapes: Solid`, so the scan must not report one.

    Without this the two budgets above could be satisfied by a scan that flags everything, and
    `union(*shapes: Solid)` -- the shape the rule explicitly allows -- would be debt it can never
    pay off. `Region.hull(*args: Region | Path2D)` is the worked example.
    """
    typed = [
        f"{path}::{name}"
        for path, name, node in CALLABLES
        if node.args.vararg is not None
        and node.args.vararg.annotation is not None
        and ast.unparse(node.args.vararg.annotation).strip("\"'") not in UNTYPED
    ]
    assert typed, "no typed n-ary variadic found; the scan cannot be distinguishing them"
    for entry in typed:
        path, name = entry.split("::")
        assert name not in UNTYPED_VARIADICS.get(path, []), f"{entry} is typed and was counted anyway"


def _protocol_declarations() -> dict[str, int]:
    """How many parameters each protocol member declares positionally.

    A member the protocol still declares as `(*args, **kwargs)` is skipped: a loose declaration
    constrains nothing, and treating it as "zero positional" would demand that every
    implementation make *all* its parameters keyword-only. The first version of this scan did
    exactly that and rewrote signatures that were never in question.
    """
    declared: dict[str, int] = {}
    source = (PACKAGE / "_backend.py").read_text()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ClassDef) or node.name not in ("Shape", "Flat", "Solid"):
            continue
        for member in node.body:
            if not isinstance(member, ast.FunctionDef) or member.name.startswith("_"):
                continue
            if member.args.vararg or member.args.kwarg:
                continue
            declared[member.name] = len([a for a in member.args.args if a.arg != "self"])
    return declared


PROTOCOL_DECLARATIONS = _protocol_declarations()


def test_the_protocol_scan_found_the_declarations() -> None:
    """A scan matching nothing would make the check below vacuous."""
    assert len(PROTOCOL_DECLARATIONS) > 50, f"only {len(PROTOCOL_DECLARATIONS)} found; scan broken"


def test_no_implementation_accepts_positionally_what_its_protocol_declares_keyword_only() -> None:
    """SPEC C-20, P-5: the protocol is the contract, and an implementation may not be looser.

    A *more permissive* implementation satisfies a stricter protocol, so `mypy` is content when a
    concrete class takes positionally what the protocol declares keyword-only -- and the tier scan
    reaches only the exported surface, which `CsgSolid` is not part of. Between them, protocol and
    implementation drifted on fifteen members: `Solid.wrap(radius, *, fn)` against
    `CsgSolid.wrap(radius, fn)`, so a caller holding a `Solid` got the rule and a caller holding a
    `CsgSolid` did not. Nothing was checking, because each rule's scope stopped short of the gap.

    `wrap` had a third spelling in `_shape.pyi` that had drifted from both, which is what a
    hand-written stub beside a real class is for.
    """
    # Only the classes that actually implement a protocol. Matching by member *name* across the
    # whole package over-matches: `BezierPatch.vnf(splinesteps)` is a different operation from
    # `Shape.vnf()`, and a `BezierPatch` is not a `Shape`. The list is the one
    # `tests/test_shape_contract.py` walks as `IMPLEMENTATIONS`, for the same reason it keeps one.
    implementations = {"CsgSolid", "SdfSolid", "CsgShape2D", "PyShape2D"}
    looser = []
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).as_posix()
        if relative == "_backend.py":
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover - another test's problem
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name not in implementations:
                continue
            for member in node.body:
                if not isinstance(member, ast.FunctionDef):
                    continue
                declared = PROTOCOL_DECLARATIONS.get(member.name)
                if declared is None or member.args.vararg or member.args.kwarg:
                    continue
                positional = [a.arg for a in member.args.args if a.arg != "self"]
                if len(positional) > declared:
                    looser.append(
                        f"{relative}::{node.name}.{member.name} takes {positional[declared]!r} "
                        f"positionally; the protocol declares it keyword-only"
                    )
    assert not looser, "implementations looser than the protocol they satisfy:\n  " + "\n  ".join(looser)


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


#: Validators, which take `object` precisely so they can reject anything that is not an anchor.
#: Typing the parameter narrowly would make the rejection unreachable.
ANCHOR_VALIDATORS = frozenset({"require_anchor", "_reject_anchor"})


def _every_signature() -> list[tuple[str, str, ast.FunctionDef]]:
    """Every function in the package, public or not, exported or not.

    Deliberately wider than `CALLABLES`. The tier-order rules are about the *call surface* a user
    sees, so the exported scope is right for them. O-6b is about a **type**, and a type is wrong
    wherever it is written -- mypy reads every signature, and so does anyone calling a backend
    module directly. Scoping it to the exported surface is what let the entire SDF backend type
    `anchor: Sequence[float]` while the check reported nothing (T71).
    """
    found: list[tuple[str, str, ast.FunctionDef]] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).as_posix()
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover - a file that does not parse is another test's job
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                found.append((relative, node.name, node))
    return found


EVERY_SIGNATURE = _every_signature()


def test_the_signature_scan_reaches_the_backends() -> None:
    """PLAN O-6b: the wide scan is only wide if it actually reaches past the exported surface.

    `CALLABLES` covers 62 modules and, of the SDF package, only `sdf/textures.py`. That is correct
    for the tier rules and was silently wrong for the type rule below.
    """
    modules = {path for path, _, _ in EVERY_SIGNATURE}
    assert any(m.startswith("sdf/") for m in modules), "the scan does not reach the SDF backend"
    assert len(modules) > len({p for p, _, _ in CALLABLES}), "the wide scan is no wider"


def test_every_anchor_parameter_speaks_the_anchor_language() -> None:
    """PLAN O-6b, SPEC C-10: an anchor is `Anchor | Sequence[float]`, never a bare vector.

    `flat.text()` took `anchor: str = "baseline"` for as long as it existed and nothing noticed
    until T36 went looking by hand. `Any` is allowed only on the shape protocols, where PLAN T-6c
    sanctions it to bridge two backends' spellings.

    Checked over **every** signature, not just the exported ones. Scoped to the exported surface
    this reported nothing while 24 SDF constructors declared `anchor: Sequence[float]` -- a plain
    vector, which the rule names explicitly -- and the annotation was not merely unidiomatic but
    **false**: those functions accept an `Anchor` and always have, so `mypy --strict` rejected
    `sdf.cuboid(size, anchor=Anchor.TOP)` while accepting the identical CSG call. `orient` in the
    very same signatures was already `Anchor | Sequence[float]`, which is what makes it an
    oversight rather than a decision.
    """
    wrong = [
        f"{path}::{name} {a.arg}: {ast.unparse(a.annotation)}"
        for path, name, node in EVERY_SIGNATURE
        for a in node.args.args + node.args.kwonlyargs
        if a.arg in ("anchor", "orient")
        and name not in ANCHOR_VALIDATORS
        and a.annotation is not None
        and "Anchor" not in ast.unparse(a.annotation)
        and ast.unparse(a.annotation) != "Any"
    ]
    assert not wrong, "anchors outside the anchor language (PLAN O-6b):\n  " + "\n  ".join(wrong)


#: Parameters whose `list[...]` is deliberate, with the reason. A `list` in an *input* position
#: rejects a tuple, so it needs one -- and "the body happens to mutate it" is not one: copy it.
#: Empty, and it stayed empty through T73: every candidate turned out to be a stored attribute
#: aliasing the caller's sequence, which is a defect in its own right -- the caller's list is
#: theirs to mutate afterwards -- and the fix is `list(row)`, not a narrower parameter.
INVARIANT_BY_DESIGN: dict[str, str] = {}


def test_no_input_parameter_demands_a_list() -> None:
    """SPEC C-10, PAR-1: `list` is invariant, so a `list[float]` parameter rejects a tuple.

    Not a style point. `list[float]` on a parameter is a promise the function does not keep:
    `cyl(shift=(2, 1))` builds on both backends and `mypy --strict` rejected it, and so did
    `region.round_corners(radius=(1.0, 2.0, 1.0))` and `shape.mirror_copy(center=(1.0, 0.0, 0.0))`.
    Fifty-one public parameters were annotated this way -- nineteen in the SDF backend and
    thirty-two outside it, so it is not one backend's habit. It is the same defect class T71 fixed
    for `anchor`, in a different parameter family: an annotation narrower than the behaviour, which
    no runtime test can see because the call it rejects is a call that works.

    `Sequence[float]` is the input type; `list[float]` remains right for a **return**, where being
    precise about what is produced is the point. Only parameters are checked here.
    """
    demanding = [
        f"{path}::{name} {a.arg}: {ast.unparse(a.annotation)}"
        for path, name, node in EVERY_SIGNATURE
        # `not name.startswith("_")` was the first spelling of this, and it silently excluded
        # every **dunder** -- so `VNF(vertices=[(0,0,0), ...])` kept failing `mypy --strict` for a
        # task after the rule that forbids it was written. A constructor is the most public thing
        # a class has, and an operator is public too; `_private` helpers are the only exemption.
        if not (name.startswith("_") and not name.startswith("__"))
        for a in node.args.args + node.args.kwonlyargs
        if a.annotation is not None
        and f"{name}.{a.arg}" not in INVARIANT_BY_DESIGN
        and any(t in ast.unparse(a.annotation) for t in ("list[float]", "list[int]", "list[list["))
    ]
    assert not demanding, (
        "input parameters typed `list`, which rejects a tuple that works (SPEC C-10):\n  " + "\n  ".join(demanding)
    )


def test_the_list_rule_is_about_inputs_only() -> None:
    """SPEC C-10: a return type may be a `list`, and the check above must not have eaten them.

    If it had, the assertion would be passing because the package stopped returning lists, which
    is not the same thing as the parameters being right.
    """
    returning = [
        name for _, name, node in EVERY_SIGNATURE if node.returns is not None and "list[" in ast.unparse(node.returns)
    ]
    assert len(returning) > 50, f"only {len(returning)} functions return a list; the scan is broken"


def test_an_anchor_parameter_is_annotated_at_all() -> None:
    """PLAN O-6b: an unannotated anchor evades the check above by having nothing to read.

    `sdf/joiners.py` carried three functions whose `anchor` and `orient` had no annotation and a
    `# type: ignore[no-untyped-def]` above them, so both the type rule and mypy saw nothing.
    """
    bare = [
        f"{path}::{name} {a.arg}"
        for path, name, node in EVERY_SIGNATURE
        for a in node.args.args + node.args.kwonlyargs
        if a.arg in ("anchor", "orient") and a.annotation is None
    ]
    assert not bare, "anchor parameters with no annotation (PLAN O-6b):\n  " + "\n  ".join(bare)


#: How many parameters *named for a type this project defines* are annotated `Any`, per file.
#: Only shrinks.
#:
#: 177 parameters in the package are annotated `Any` and most of them are fine -- a protocol's
#: `*args: Any`, a colour spec, a numeric-or-array. What is not fine is `path: Any` on a function
#: that takes a path, when `PathLike` exists and every caller passes one: it declares a type the
#: library already has and then throws it away, which is T33's "found by name, checked not at all"
#: one layer down from the public contract.
#:
#: Found by measurement, not by suspicion. `_stroke3d.stroke_3d(path: Any)` came out of chasing a
#: *layering* edge in T56 -- it was the reason `path3d -> _stroke3d` could not be seen as a cycle
#: -- and measuring the class immediately turned up its 2-D twin, `_stroke2d.stroke_2d`, with the
#: identical defect. Both are `PathLike` now.
#: **Empty since T73.** Every one had an honest type already written down somewhere: `polyhedron`'s
#: `points` is the `Sequence[Sequence[float]]` a `VNF` hands it, `stroke_3d`'s `path` is the
#: `PathLike` its 2-D twin was given in T56, and `distribute_on_path`'s `path` is the `Path3D` the
#: CSG spelling had declared all along. Two of them were the type being *wrong* rather than
#: missing: `Region(paths=)` needed a name that did not exist, and the bottlecap profile helpers
#: turned out to return `Path2D`, not the `Turtle2D` their own annotations claimed.
DOMAIN_TYPED_ANY: dict[str, int] = {}

#: Parameter names that mean a type the project defines, so `Any` on one is throwing that type
#: away rather than describing something genuinely unconstrained.
DOMAIN_NAMES = frozenset({"path", "paths", "region", "profile", "vnf", "point", "points"})


def _domain_typed_any() -> dict[str, list[str]]:
    """Return, per file, the domain-named parameters annotated exactly `Any`."""
    import ast

    found: dict[str, list[str]] = {}
    for path in sorted((ROOT / "pybosl2").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.FunctionDef):
                continue
            for argument in node.args.args:
                annotation = argument.annotation
                if argument.arg not in DOMAIN_NAMES or annotation is None:
                    continue
                if ast.unparse(annotation).strip("\"'") == "Any":
                    found.setdefault(str(path.relative_to(ROOT / "pybosl2")), []).append(
                        f"{node.name}({argument.arg}=)"
                    )
    return found


@pytest.mark.parametrize("path", sorted(set(DOMAIN_TYPED_ANY) | set(_domain_typed_any())))
def test_no_file_grows_its_domain_named_any_parameters(path: str) -> None:
    """SPEC C-20, PLAN T-9a: a parameter named for a type should carry it."""
    found = _domain_typed_any()
    actual, budget = len(found.get(path, [])), DOMAIN_TYPED_ANY.get(path, 0)
    if actual > budget:
        pytest.fail(
            f"{path} has {actual} domain-named parameters annotated `Any`, budget {budget}: "
            f"{sorted(found[path])[:4]}. Give them the type their name promises."
        )
    if actual < budget:
        pytest.fail(f"{path} is down to {actual} from {budget}; lower its entry in DOMAIN_TYPED_ANY.")


def test_the_strokes_take_the_path_they_stroke() -> None:
    """The pair this ratchet was built around, asserted directly rather than only counted.

    Both stroke modules declared `path: Any` on every public function. `PathLike` is the honest
    type -- a `Path` *or* a raw point list, and both callers exist -- so narrowing further would
    be wrong, and it was: `Path3D` alone typechecks against the outside callers and fails on
    `_stroke3d`'s own internal one, which passes a bare list.
    """
    import inspect

    from pybosl2 import _stroke2d, _stroke3d

    for module, names in (
        (_stroke2d, ("stroke_2d", "dashed_stroke_2d")),
        (_stroke3d, ("stroke_3d", "dashed_stroke_3d")),
    ):
        for name in names:
            annotation = inspect.signature(getattr(module, name)).parameters["path"].annotation
            assert "PathLike" in str(annotation), (
                f"{module.__name__}.{name} takes path: {annotation}, not the PathLike it strokes"
            )
