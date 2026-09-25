# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A member on `Flat` or `Solid` alone is genuinely dimensional, or it belongs on `Shape`.

SPEC C-22, a MUST that carried no enforcer until T87 -- the same gap T71 found in D-4, and the
same consequence: the rule named three examples of its own defect and two of them were still
there. `spin` on `Flat` alone had been fixed at some point; `xflip`/`yflip` on `Flat` alone had
not, and `up`/`down` on `Solid` alone are recorded below with the reason they stay.

The `xflip` case is the one worth keeping in view. All four implementations carried
`xflip_copy`, `yflip_copy` and `zflip_copy` -- inherited from `Distributable`, so present in both
dimensions by construction -- while the plain `xflip`/`yflip` were written per-dimension and only
2-D got them. **A solid could make a mirrored copy of itself and could not simply flip.** Nothing
about three dimensions forbids a mirror about the YZ plane; it had just never been written.

What the allowlist is for: a member that is *actually* dimensional. `linear_extrude` takes an
outline into a solid and has no three-dimensional meaning; `vnf` and `export` need a mesh; the
half-cuts need a third axis to cut across. Each row says which, and the rule is that the reason
names the dimension, not the history.
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "pybosl2"

#: Members on one protocol alone, each with what makes it dimensional. C-22's test is whether the
#: *other* dimension could honour it -- not whether it historically did.
DIMENSIONAL: dict[str, str] = {
    # Flat only: these leave two dimensions behind, or act on an outline that a solid has not got.
    "fill": "closes the holes in an outline; a solid's voids are not holes in a boundary",
    "linear_extrude": "takes an outline into a solid -- it is the crossing itself",
    "rotate_extrude": "revolves an outline into a solid -- likewise",
    "offset": "grows or shrinks a 2-D outline; the 3-D spelling is `offset3d`",
    # Solid only: these need a third axis, or a mesh.
    "up": "translates along Z, which a 2-D shape has not got",
    "down": "translates along Z, which a 2-D shape has not got",
    "half_of": "cuts across a plane in space; the 2-D spelling would be a different operation",
    "top_half": "as `half_of`",
    "bottom_half": "as `half_of`",
    "front_half": "as `half_of`",
    "back_half": "as `half_of`",
    "left_half": "as `half_of`",
    "right_half": "as `half_of`",
    "projection": "flattens a solid into an outline -- the crossing, the other way",
    "vnf": "a mesh of a surface in space",
    "export": "writes a mesh",
    "to_csg": "converts a solid between backends; the 2-D pair is a different conversion",
    "to_sdf": "as `to_csg`",
    "repair": "repairs a mesh",
    "oversample": "subdivides a mesh",
    "wrap": "wraps a solid around a cylinder -- needs the third axis to wrap about",
    "round3d": "rounds a solid's surface; the 2-D spelling is `offset`",
    "offset3d": "offsets a solid's surface; the 2-D spelling is `offset`",
    "orient": "points a solid along an axis; a planar shape has no axis to point",
    "reorient": "as `orient`",
    "partition": "cuts a solid into interlocking pieces across a plane in space",
    "chain_hull": "hulls consecutive solids; the 2-D pair is `hull`",
    "minkowski_difference": "erodes a solid by another; the 2-D pair is `offset`",
    "edge_mask": "treats the edges of a solid, which a 2-D outline has not got",
    "edge_profile": "as `edge_mask`",
    "edge_profile_asym": "as `edge_mask`",
    "corner_profile": "as `edge_mask`",
    "face_profile": "treats the faces of a solid",
    "round_edges": "as `edge_mask`",
    "chamfer_edges": "as `edge_mask`",
    "cove_edges": "as `edge_mask`",
}


def _declared() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for module in ("_backend.py", "flat.py"):
        for node in ast.walk(ast.parse((PACKAGE / module).read_text())):
            if isinstance(node, ast.ClassDef) and node.name in ("Shape", "Flat", "Solid"):
                found[node.name] = {
                    member.name
                    for member in node.body
                    if isinstance(member, ast.FunctionDef) and not member.name.startswith("_")
                }
    return found


DECLARED = _declared()


def test_the_scan_found_the_protocols() -> None:
    """A scan matching nothing would make the checks below vacuous."""
    assert set(DECLARED) == {"Shape", "Flat", "Solid"}, sorted(DECLARED)
    assert len(DECLARED["Shape"]) > 40, f"Shape declares {len(DECLARED['Shape'])}; the scan is broken"


def test_every_one_sided_member_is_genuinely_dimensional() -> None:
    """SPEC C-22: a member both dimensions can honour belongs on `Shape`."""
    shape, flat, solid = DECLARED["Shape"], DECLARED["Flat"], DECLARED["Solid"]
    one_sided = (flat - solid - shape) | (solid - flat - shape)
    unjustified = sorted(one_sided - set(DIMENSIONAL))
    assert not unjustified, (
        f"on one protocol alone with no reason recorded: {unjustified}. Either move it to `Shape` "
        f"-- C-22's answer when both dimensions can honour it -- or say what makes it dimensional."
    )


def test_the_reasons_do_not_outlive_the_members() -> None:
    """SPEC C-22: a row for a member that is no longer one-sided overstates the split."""
    shape, flat, solid = DECLARED["Shape"], DECLARED["Flat"], DECLARED["Solid"]
    one_sided = (flat - solid - shape) | (solid - flat - shape)
    stale = sorted(set(DIMENSIONAL) - one_sided)
    assert not stale, f"these are no longer on one protocol alone -- remove them: {stale}"


def test_the_flips_are_on_shape_where_c22_says_they_belong() -> None:
    """SPEC C-22, named in the rule's own text, so named here.

    This is the row the rule cites and the one that was still open. Asserting it by name rather
    than trusting the allowlist to stay empty of it: an allowlist entry is one edit away from
    excusing exactly what the rule points at.
    """
    for member in ("xflip", "yflip"):
        assert member in DECLARED["Shape"], f"{member} is not on Shape (SPEC C-22)"
        assert member not in DIMENSIONAL, f"{member} is excused as dimensional; C-22 says it is not"
