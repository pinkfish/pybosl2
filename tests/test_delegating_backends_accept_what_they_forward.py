# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""An operation that forwards its arguments accepts what the callee accepts, and says so.

SPEC PAR-1, C-10, B-9. A method whose body is a single forwarding call touches none of its
arguments, so its declared types are a claim about the *callee*, and the only way for them to be
narrower is for the claim to be false.

They were. `SdfSolid.partition` was `self.to_csg().partition(**everything)`, and T79 declared
`cutsize: float` and `cutpath: str` against the CSG spelling's `float | Sequence[float]` and
`str | Path2D`, on the evidence that passing the wider forms raised `TypeError`. They do — and so
does `partition(cutsize=10)`, and so does `partition()` with no arguments at all, because
`to_csg()` cannot mesh a field without libfive and this environment has none. **The measurement
could not distinguish "the backend refuses this" from "nothing here can run it", and it was read
as the first.**

That is the defect this file guards, and it is a defect in a *method*, not in a signature: a
runtime probe against a backend whose dependency is absent tells you nothing about the backend.
The check below is static for that reason. It reads which parameters a delegating call passes
through untouched and requires the caller's annotation to be no narrower than the callee's, which
is answerable without running anything.

The skip marker on the SDF partition test said this throughout — "no libfive: a meshed SDF solid
cannot enter the CSG operators" — and was not consulted. T135 then asked the question the marker
invites: *why* was a field being meshed to split it? A split is two intersections with a cut mask
and a translate, all of it on the shared contract, and the mask was the only CSG-only part. It is
built through the façade now, so both backends run one implementation, nothing meshes, and the
marker is gone because there is nothing left for it to skip. **The unrunnable measurement was a
symptom of the conversion, not of the environment.** Two callers forward to that implementation
now, and both are checked below.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "pybosl2"

#: Delegations to check, as (module, class, method) -> (callee module, callee class, callee name).
#: Each names a method whose body is a single forwarding call, so its parameter types are a claim
#: about the callee rather than about itself. A `None` class means a module-level function.
DELEGATIONS = {
    ("sdf/shapes3d.py", "SdfSolid", "partition"): ("partitions.py", None, "partition_solid"),
    ("partitions.py", "Partitionable", "partition"): ("partitions.py", None, "partition_solid"),
}


def _method(path: str, class_name: "str | None", method: str) -> ast.FunctionDef:
    """The named function: a method of *class_name*, or a module-level one when that is None."""
    tree = ast.parse((PACKAGE / path).read_text())
    if class_name is None:
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == method:
                return node
        raise AssertionError(f"{path}::{method} not found")
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
    where: tuple[str, str, str], callee: "tuple[str, str | None, str]"
) -> None:
    """SPEC PAR-1: a type narrower than what the call forwards to is a promise nothing keeps."""
    caller = _method(*where)
    target = _method(*callee)
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


def test_the_sdf_partition_no_longer_needs_the_environment_it_could_not_have() -> None:
    """SPEC B2-1: the skip that recorded the conversion is only gone if the conversion is.

    `tests/test_sdf_shapes3d.py` carried a `needs_csg_operable_mesh` marker -- "no libfive: a
    meshed SDF solid cannot enter the CSG operators" -- because the SDF partition meshed its
    receiver. T135 removed the meshing and the marker with it. This holds that pair together: a
    `to_csg()` back in the method would make the marker necessary again, and a marker reintroduced
    without it would be recording something that is not happening.
    """
    node = _method("sdf/shapes3d.py", "SdfSolid", "partition")
    # Without dropping the docstring this matches the paragraph *recording* the old call -- the
    # overmatch T133's first scan made, where `ast.unparse` carried the prose along with the code.
    statements = node.body[1:] if ast.get_docstring(node) is not None else node.body
    body = "\n".join(ast.unparse(statement) for statement in statements)
    assert "to_csg" not in body, (
        "SdfSolid.partition meshes its receiver again, so it is back to being unexercisable "
        "wherever libfive is absent -- and back to handing a caller a `CsgSolid` from inside "
        '`use_backend("sdf")` (SPEC A-6)'
    )
    source = (ROOT / "tests" / "test_sdf_shapes3d.py").read_text()
    assert "pytest.mark.skipif" not in source, (
        "a skip is back in the SDF shape tests. If it is for want of libfive, say which operation "
        "needs a mesh and why it cannot be done in the field; the last two could both be done."
    )
