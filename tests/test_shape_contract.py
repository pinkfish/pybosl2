# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The declared contract and the delivered object agree (SPEC C-20, C-22; PLAN T-6b, T-6c).

Two directions, both of which have failed in this codebase:

* **The object has more than the contract declares.** `Solid` declared 32 members while `CsgSolid`
  had 92, so `attach`, `diff`, `tag`, `projection`, the edge treatments and the whole distribution
  family were invisible to a type checker -- and a caller following this project's own typing
  advice could not call the library's headline composition features.
* **The contract declares more than the object has.** That one is worse, because it is silent: on
  Python 3.12+ `isinstance` resolves a protocol statically, so an attribute assigned only in
  `__init__` makes a class fail a check it satisfies perfectly at runtime (PLAN T-6b). `size` did
  exactly that on both concrete shapes.
"""

from __future__ import annotations

import inspect
from typing import Generic, Protocol

import pytest

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
from pybosl2._backend import Shape, Solid
from pybosl2.flat import Flat
from pybosl2.sdf.shapes2d import PyShape2D
from pybosl2.sdf.shapes3d import SdfSolid
from pybosl2.shapes2d.base import CsgShape2D
from pybosl2.shapes3d.base import CsgSolid

IMPLEMENTATIONS = [
    ("CsgSolid", CsgSolid, (Shape, Solid)),
    ("SdfSolid", SdfSolid, (Shape, Solid)),
    ("CsgShape2D", CsgShape2D, (Shape, Flat)),
    ("PyShape2D", PyShape2D, (Shape, Flat)),
]

#: Public members a contract deliberately does not declare, each with the reason. This is the
#: allowlist SPEC C-20 requires -- "a named, justified allowlist for the deliberate exceptions" --
#: and it is meant to shrink.
UNDECLARED_BY_DESIGN: dict[str, str] = {
    # --- C-21: synonym halves, pending removal (SPEC §12.2) ---
    "move": "synonym of translate (C-21), pending removal",
    "rot": "synonym of rotate (C-21), pending removal",
    "fwd": "synonym of forward (C-21), pending removal",
    "bounding_box": "returns the box as a *solid*, which is a different operation from bounds()",
    # --- attachment machinery: state, not operations ---
    "attachments": "attachment state; the operations that use it are declared",
    "diff_config": "attachment state; set by the treatments, read by realize()",
    "tag_name": "attachment state; `tag()` is the operation",
    "realize": "resolves attachments; CSG-only and reached through diff()/intersect()",
    # --- the dimension tag ---
    "dimensions": "the operand guard's own tag (SPEC E-7), not a caller-facing operation",
    # --- backend-specific extras, which SPEC B-6 keeps on the backend's own module ---
    "mesh": "SDF: turns the field into a native solid; the neutral spelling is vnf()",
    "sdf": "SDF: the field itself, the backend's own representation",
    "render": "SDF: native passthrough",
    "resize": "SDF: native passthrough",
    "chamfer": "SDF-only: survives transforms, which CSG expresses as a constructor parameter",
    "round": "SDF-only: as `chamfer`",
    "union": "SDF: n-ary form of `|`, which is declared",
    "difference": "SDF: n-ary form of `-`, which is declared",
    "intersection": "SDF: n-ary form of `&`, which is declared",
    "union2d": "SDF 2-D: n-ary form of `|`",
    "outline": "SDF 2-D: the field's own boundary extraction",
    "extrude": "SDF 2-D: the backend's spelling; `linear_extrude` is the contract's and is declared",
    "linear_sweep": "SDF 2-D: reached through the Sweepable mixin on paths",
    "linear_sweep_sdf": "SDF 2-D: the backend's own sweep",
    "revolve_sdf": "SDF 2-D: the backend's own revolve",
    "rotate_sweep": "SDF 2-D: reached through the Sweepable mixin on paths",
    # --- distribution helpers whose declared twins carry the contract ---
    "distribute": "the free-function form; the method form `distribute_on_path` is declared",
    "move_and_copy": "internal to the distributors; the copy operations themselves are declared",
    # --- genuinely internal, pending an underscore ---
    "inside": "internal predicate",
    "pull": "internal",
    "separate": "internal",
    "fill": "CSG-only (SPEC PAR-3); declared on neither contract because only one backend has it",
    "path_extrude": "CSG-only native sweep; the neutral spellings live on the path types",
    "spin": "CSG 2-D only; C-22 would move it to Shape with the C-21 synonym work",
}

#: Contract members the SDF 2-D shape does not implement. This is the C-19 parity gap the spec
#: already records -- "the SDF backend's shapes carry no colour, and its 2-D shapes no
#: distribution" -- stated here as a number so it cannot quietly grow.
SDF_FLAT_PARITY_GAP = frozenset(
    {
        "align",
        "anchor_point",
        "attach",
        "back",
        "color",
        "color_this",
        "diff",
        "distribute_on_path",
        "forward",
        "ghost",
        "highlight",
        "hsl",
        "hsv",
        "intersect",
        "left",
        "minkowski",
        "mirror_copy",
        "multmatrix",
        "position",
        "reanchor",
        "recolor",
        "right",
        "rotate_extrude",
        "size",
        "tag",
        "tag_this",
        "with_nominal_size",
        "arc_copies",
        "grid_copies",
        "line_copies",
        "path_copies",
        "rot_copies",
        "sphere_copies",
        "xcopies",
        "ycopies",
        "zcopies",
        "xflip_copy",
        "yflip_copy",
        "zflip_copy",
        "xrot_copies",
        "yrot_copies",
        "zrot_copies",
    }
)


#: Bases that carry no contract of their own and whose members must not be counted.
_NOT_CONTRACT_BASES = frozenset({object, Protocol, Generic})


def _declared(protocols: tuple[type, ...]) -> set[str]:
    """Return every public member the given protocols declare.

    Computed by walking the protocols' own MRO rather than reading `__protocol_attrs__`, which is
    a CPython implementation detail that does not exist before 3.12 -- and this project supports
    3.11 (`requires-python`), so a test built on it passes locally and errors on the oldest
    supported interpreter. That is the same trap as PLAN T-6e, one layer up: a check that behaves
    differently per version is not a check.
    """
    names: set[str] = set()
    for protocol in protocols:
        for base in protocol.__mro__:
            if base in _NOT_CONTRACT_BASES or base.__module__ == "typing":
                continue
            names |= {n for n in vars(base) if not n.startswith("_")}
            names |= {n for n in getattr(base, "__annotations__", {}) if not n.startswith("_")}
    return names


@pytest.mark.parametrize(("label", "cls", "protocols"), IMPLEMENTATIONS)
def test_the_contract_is_the_whole_object(label: str, cls: type, protocols: tuple[type, ...]) -> None:
    """Every public operation an implementation has is declared on a contract (SPEC C-20)."""
    undeclared = sorted(
        name
        for name in dir(cls)
        if not name.startswith("_") and name not in _declared(protocols) and name not in UNDECLARED_BY_DESIGN
    )
    assert not undeclared, (
        f"{label} has public members no protocol declares, so typed callers cannot use them "
        f"(SPEC C-20): {undeclared}. Declare them on Shape if both dimensions can honour them "
        f"(C-22), on Flat/Solid if they are genuinely dimensional, or add them to "
        f"UNDECLARED_BY_DESIGN with the reason."
    )


@pytest.mark.parametrize(("label", "cls", "protocols"), IMPLEMENTATIONS)
def test_the_object_has_everything_the_contract_declares(label: str, cls: type, protocols: tuple[type, ...]) -> None:
    """A declared member the class lacks fails `isinstance` silently on 3.12+ (PLAN T-6b)."""
    gap = SDF_FLAT_PARITY_GAP if cls is PyShape2D else frozenset()
    missing = sorted(name for name in _declared(protocols) if not hasattr(cls, name) and name not in gap)
    assert not missing, (
        f"{label} is missing contract members, so `isinstance({label.lower()}, ...)` is False for a "
        f"perfectly good shape: {missing}"
    )


def test_the_parity_gap_list_is_not_stale() -> None:
    """A name the SDF 2-D shape has gained comes off the gap list, so the gap cannot be overstated."""
    stale = sorted(name for name in SDF_FLAT_PARITY_GAP if hasattr(PyShape2D, name))
    assert not stale, f"PyShape2D now implements these -- remove them from SDF_FLAT_PARITY_GAP: {stale}"


@pytest.mark.parametrize(("label", "cls", "protocols"), IMPLEMENTATIONS)
def test_no_contract_member_is_a_property_that_computes(label: str, cls: type, protocols: tuple[type, ...]) -> None:
    """PLAN T-6e: `isinstance` evaluates properties on 3.11, so a contract property must be cheap.

    `Solid.vnf` was a property that meshed, which made every type check do the meshing and, where
    no mesher existed, raise out of the check. The rule is that anything on a contract which
    computes is a method; the guard is that a contract property must be a plain attribute or a
    trivial accessor.
    """
    allowed_properties = {"backend", "size", "dimensions"}
    offenders = []
    for name in sorted(_declared(protocols)):
        member = inspect.getattr_static(cls, name, None)
        if isinstance(member, property) and name not in allowed_properties:
            offenders.append(f"{label}.{name}")
    assert not offenders, (
        f"contract members declared as computing properties (PLAN T-6e): {offenders}. "
        f"Make them methods -- `isinstance` calls `hasattr` on every member and that evaluates a "
        f"property."
    )
