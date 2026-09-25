# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every parameter the façade declares reaches the backend that builds the shape.

SPEC B-9, A-10, D-4. A façade constructor is a forwarder: it takes the union of what both backends
build (B-9) and hands it on. It does that by naming every parameter **twice** — once in the
signature and once as a key in the dict it forwards::

    def zcyl(height=None, radius=None, ..., 44 parameters):
        return get_backend().construct(
            "zcyl",
            _forward(_groups("zcyl", {"height": height, "radius": radius, ...})),
        )

A parameter present in the signature and missing from that dict is accepted and then **silently
dropped**. Nothing raises, nothing warns, and the shape comes back built as though the argument
had never been passed — which is the failure D-4 is about, arriving by a different road: not
`None` misread as "off", but a value discarded between the door and the workshop.

Measured, every one of the 44 does reach the backend today, and that is worth keeping rather than
rediscovering. The hazard is structural: 44 parameters written twice, five near-identical
constructors, and a signature is the thing most likely to gain a parameter.

The group objects (`placement`, `treatment`, `selection`, `texturing`) are not dict keys and are
not meant to be — `_groups` takes them as keyword arguments and resolves them into the dict in
place. Counting those as omissions reported nineteen false positives on the first run, which is
why this checks both routes.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FACADES = ("solid.py", "flat.py")


def _forwarding_constructors(source: str) -> list[tuple[str, set[str], set[str]]]:
    """Public constructors that forward a dict, with their parameters and everything they pass on."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
            continue
        parameters = {a.arg for a in node.args.args + node.args.kwonlyargs} - {"self", "cls"}
        keys: set[str] = set()
        keywords: set[str] = set()
        for inner in ast.walk(node):
            if isinstance(inner, ast.Dict):
                keys |= {
                    key.value for key in inner.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)
                }
            if isinstance(inner, ast.Call):
                keywords |= {k.arg for k in inner.keywords if k.arg}
        if keys and parameters:
            found.append((node.name, parameters, keys | keywords))
    return found


CONSTRUCTORS = [
    (module, name, parameters, forwarded)
    for module in FACADES
    for name, parameters, forwarded in _forwarding_constructors((ROOT / "pybosl2" / module).read_text())
]


def test_the_scan_found_the_forwarders() -> None:
    """A scan matching nothing would make the check below vacuous."""
    assert len(CONSTRUCTORS) > 15, f"only {len(CONSTRUCTORS)} forwarding constructors found"
    widest = max(len(parameters) for _, _, parameters, _ in CONSTRUCTORS)
    assert widest > 30, f"the widest takes {widest} parameters; the scan is reading the wrong thing"


@pytest.mark.parametrize(
    ("module", "name", "parameters", "forwarded"),
    CONSTRUCTORS,
    ids=[f"{module}::{name}" for module, name, _, _ in CONSTRUCTORS],
)
def test_no_declared_parameter_is_dropped_on_the_way_to_the_backend(
    module: str, name: str, parameters: set[str], forwarded: set[str]
) -> None:
    """SPEC B-9: a parameter the façade accepts and does not pass on is accepted and ignored."""
    dropped = sorted(parameters - forwarded)
    assert not dropped, (
        f"{module}::{name} declares {dropped} and forwards neither as a dict key nor as a keyword "
        f"-- the caller's value is discarded without a word (SPEC B-9)."
    )
