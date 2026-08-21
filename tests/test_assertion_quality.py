# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The PLAN X-8 ratchet: a test asserts what the result *is*, never merely that it exists.

`assert isinstance(result, Bosl2Solid)` passes for every wrong answer that is still a solid, and
`assert result is not None` passes for every wrong answer at all. Converting the suite away from
that shape turned up nine real bugs -- an inverted corner cutter, SDF half-cuts that kept an
octant, a chamfer factory that silently returned the roundover -- every one of them behind a test
that could not fail. This scans the suite so the shape cannot come back.

A handful of tests genuinely do claim a type and nothing else; they are listed in `_ALLOWED`
with the reason, and the list is meant to shrink, never grow.
"""

from __future__ import annotations

import ast
import pathlib

TESTS_DIR = pathlib.Path(__file__).resolve().parent

#: Tests whose claim really is the type, with the reason each one is exempt (PLAN X-8).
_ALLOWED: dict[str, str] = {
    # Every 2-D constructor and operator must hand back the wrapper rather than a bare native
    # object -- and a bare native has a bounding box too, so no measurement can tell them apart.
    # The geometry each one produces is measured by the sibling test that shares its table.
    "test_shapes2d_object.py::test_every_constructor_returns_the_2d_wrapper": "wrapper type is the claim",
    "test_shapes2d_object.py::test_transforms_return_the_2d_wrapper": "wrapper type is the claim",
    "test_shapes2d_object.py::test_csg_between_wrappers_returns_the_2d_wrapper": "wrapper type is the claim",
    "test_shapes2d_object.py::test_reflected_csg_returns_the_2d_wrapper": "wrapper type is the claim",
    "test_shapes2d_object.py::test_fill_returns_the_2d_wrapper": "wrapper type is the claim",
    "test_shapes2d_object.py::test_module_level_fill_accepts_every_child_form": "wrapper type is the claim",
    "test_shapes2d_object.py::test_hull_of_self_returns_the_2d_wrapper": "wrapper type is the claim",
    "test_shapes2d_object.py::test_hull_accepts_every_child_form": "wrapper type is the claim",
    "test_shapes2d_object.py::test_offset_returns_the_2d_wrapper": "wrapper type is the claim",
    "test_shapes2d_object.py::test_region_geometry_is_the_2d_wrapper": "wrapper type is the claim",
    "test_shapes2d_object.py::test_minkowski_returns_2d_wrapper": "wrapper type is the claim",
    "test_shapes2d_object.py::test_corner_treatments_return_shape2d": "wrapper type is the claim",
    # wrap() is the one operation that cannot be measured in-process: asking the wrapped solid for
    # its bounds -- or even its program text -- re-enters the native op and never returns. Its
    # geometry is measured against the real app in test_stl_render.py.
    "test_native_ops.py::test_wrap_returns_solid_with_and_without_fn": "bounds() re-enters the native op and hangs",
}


def _is_shallow(node: ast.Assert) -> bool:
    """True if this assert only says "something came back", not what it is."""
    test = node.test
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Name) and test.func.id in ("isinstance", "all"):
        return "isinstance" in ast.unparse(test)
    if isinstance(test, ast.Compare) and any(isinstance(op, ast.IsNot) for op in test.ops):
        return any(isinstance(c, ast.Constant) and c.value is None for c in test.comparators)
    return False


def _measures(node: ast.FunctionDef) -> bool:
    """True if the test measures a value outside a bare `assert` -- np.testing, mostly."""
    for call in ast.walk(node):
        if isinstance(call, ast.Call):
            name = ast.unparse(call.func)
            if "np.testing.assert" in name or "numpy.testing.assert" in name:
                return True
    return False


def existence_only_tests(source: str) -> list[str]:
    """Names of the tests in *source* whose every assertion is an existence check."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        asserts = [a for a in ast.walk(node) if isinstance(a, ast.Assert)]
        if asserts and all(_is_shallow(a) for a in asserts) and not _measures(node):
            found.append(node.name)
    return found


def test_no_test_asserts_only_that_a_result_exists() -> None:
    offenders = []
    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        if path.name == pathlib.Path(__file__).name:
            continue
        for name in existence_only_tests(path.read_text()):
            key = f"{path.relative_to(TESTS_DIR)}::{name}"
            if key not in _ALLOWED:
                offenders.append(key)
    assert not offenders, (
        "tests that assert only that a result exists (PLAN X-8); assert what it *is* -- bounds, "
        "point counts, area, volume -- or add it to _ALLOWED with a reason:\n  " + "\n  ".join(offenders)
    )


def test_every_allowed_entry_still_exists() -> None:
    """The exemption list shrinks with the suite: a stale entry hides a test that could regress."""
    stale = []
    for key in _ALLOWED:
        filename, _, test_name = key.partition("::")
        path = TESTS_DIR / filename
        if not path.is_file() or test_name not in existence_only_tests(path.read_text()):
            stale.append(key)
    assert not stale, "exempted tests that no longer exist or no longer need the exemption:\n  " + "\n  ".join(stale)


def test_the_ratchet_would_catch_an_existence_only_test() -> None:
    """The check above is only worth having if it fires -- these are the shapes it must catch."""
    assert existence_only_tests("def test_a():\n    assert isinstance(cuboid([1, 1, 1]), Bosl2Solid)\n") == ["test_a"]
    assert existence_only_tests("def test_b():\n    assert cuboid([1, 1, 1]) is not None\n") == ["test_b"]
    assert existence_only_tests("def test_c():\n    for x in items:\n        assert isinstance(x, Bosl2Solid)\n") == [
        "test_c"
    ]

    # ... and does not fire on a test that measures anything at all.
    assert existence_only_tests("def test_d():\n    assert cuboid([1, 1, 1]).bounds()[1] == [1, 1, 1]\n") == []
    assert (
        existence_only_tests(
            "def test_e():\n    assert isinstance(p, Path2D)\n    np.testing.assert_allclose(p, [[0, 0]])\n"
        )
        == []
    )
    assert existence_only_tests("def test_f():\n    with pytest.raises(ValueError):\n        cuboid(-1)\n") == []
