# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""An operation that forwards its arguments accepts what the callee accepts, and says so.

SPEC PAR-1, C-10, B-9. `SdfSolid.partition` is `self.to_csg().partition(**everything)` — it
converts and delegates, touching none of its arguments. Its declared types are therefore a claim
about the *callee*, and the only way for them to be narrower is for the claim to be false.

They were. T79 declared `cutsize: float` and `cutpath: str` against the CSG spelling's
`float | Sequence[float]` and `str | Path2D`, on the evidence that passing the wider forms raised
`TypeError`. They do — and so does `partition(cutsize=10)`, and so does `partition()` with no
arguments at all, because `to_csg()` cannot mesh a field without libfive and this environment has
none. **The measurement could not distinguish "the backend refuses this" from "nothing here can
run it", and it was read as the first.**

That is the defect this file guards, and it is a defect in a *method*, not in a signature: a
runtime probe against a backend whose dependency is absent tells you nothing about the backend.
The check below is static for that reason. It reads which parameters a delegating call passes
through untouched and requires the caller's annotation to be no narrower than the callee's, which
is answerable without running anything.

`tests/test_sdf_shapes3d.py::test_partition_returns_two_parts` carries a `needs_csg_operable_mesh`
skip marker saying exactly this — "no libfive: a meshed SDF solid cannot enter the CSG operators".
The marker was right and was not consulted.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "pybosl2"

#: Delegations to check, as (module, class, method) -> (callee module, callee class). Each names a
#: method whose body is a single forwarding call, so its parameter types are a claim about the
#: callee rather than about itself.
DELEGATIONS = {
    ("sdf/shapes3d.py", "SdfSolid", "partition"): ("partitions.py", "Partitionable"),
}


def _method(path: str, class_name: str, method: str) -> ast.FunctionDef:
    tree = ast.parse((PACKAGE / path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == method:
                    return member
    raise AssertionError(f"{path}::{class_name}.{method} not found")


def _annotations(node: ast.FunctionDef) -> dict[str, str]:
    found = {}
    for arg in node.args.args + node.args.kwonlyargs:
        if arg.arg in ("self", "cls") or arg.annotation is None:
            continue
        found[arg.arg] = ast.unparse(arg.annotation).strip("\"'")
    return found


def _forwarded(node: ast.FunctionDef) -> set[str]:
    """Parameters passed straight through to another call, unchanged."""
    passed = set()
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        for keyword in inner.keywords:
            if keyword.arg and isinstance(keyword.value, ast.Name) and keyword.value.id == keyword.arg:
                passed.add(keyword.arg)
    return passed


@pytest.mark.parametrize(("where", "callee"), sorted(DELEGATIONS.items()))
def test_a_forwarded_parameter_is_no_narrower_than_the_callee_declares(
    where: tuple[str, str, str], callee: tuple[str, str]
) -> None:
    """SPEC PAR-1: a type narrower than what the call forwards to is a promise nothing keeps."""
    caller = _method(*where)
    target = _method(callee[0], callee[1], where[2])
    caller_types, target_types = _annotations(caller), _annotations(target)
    forwarded = _forwarded(caller)
    assert forwarded, f"{where} forwards nothing; the delegation record is wrong"

    narrower = [
        f"{name}: forwards as {caller_types[name]!r} to a parameter declared {target_types[name]!r}"
        for name in sorted(forwarded)
        if name in caller_types and name in target_types and caller_types[name] != target_types[name]
    ]
    assert not narrower, f"{where[0]}::{where[1]}.{where[2]} declares types its callee does not:\n  " + "\n  ".join(
        narrower
    )


def test_the_scan_reads_real_forwarding() -> None:
    """A `_forwarded` that matched nothing would make the check above vacuous."""
    caller = _method("sdf/shapes3d.py", "SdfSolid", "partition")
    forwarded = _forwarded(caller)
    assert {"cutsize", "cutpath", "gap", "spin"} <= forwarded, sorted(forwarded)


def test_the_skip_marker_that_should_have_been_consulted_still_says_why() -> None:
    """SPEC B2-1: the marker recording *why* SDF partition cannot be exercised here is the record.

    It said "no libfive: a meshed SDF solid cannot enter the CSG operators" throughout, which is
    the sentence that would have prevented T79's conclusion. A skip is evidence about the
    environment, and it has to keep saying which environment.
    """
    source = (ROOT / "tests" / "test_sdf_shapes3d.py").read_text()
    assert "needs_csg_operable_mesh" in source
    assert "no libfive: a meshed SDF solid cannot enter the CSG operators" in source
