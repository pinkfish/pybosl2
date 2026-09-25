# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The names and annotations several signature rules share, defined once.

T85 found two scans in `tests/test_signatures.py` disagreeing about what "untyped" means: the
variadic rule counted `object` and the domain-named rule did not, twenty lines apart, so the second
reported **zero** while four `profile: object` parameters stood on the exported surface. The fix
there was to widen one constant. That left two constants meaning the same thing in one file, which
is the same defect one step along -- and a third and fourth list of *parameter names meaning a
path* lived in two other test modules, the widest knowing twenty names and the narrowest seven.

A shared concept checked by more than one rule belongs in one place. These are they.
"""

from __future__ import annotations

#: Annotations that name no type. `object` belongs with `Any`: it accepts everything and describes
#: nothing, which is the property every rule using this set is about. `(none)` stands for a
#: parameter with no annotation at all -- the same gap, spelled by omission.
UNTYPED_ANNOTATIONS = frozenset({"Any", "object", "(none)"})

#: Parameter names that mean a type this project defines, so an untyped annotation on one is
#: throwing that type away rather than describing something genuinely unconstrained.
#:
#: The union of what the rules using it knew separately. `tests/test_signatures.py` had seven,
#: `tests/test_polyline_parameters.py` twenty and `tests/test_exports.py` eight; measured at the
#: time of merging, the wider names caught nothing the narrow list missed, so this is not a
#: backlog -- it is the same list stopping being three lists that drift.
DOMAIN_NAMES = frozenset(
    {
        "contour",
        "control_points",
        "cp",
        "curve",
        "loop",
        "loops",
        "outline",
        "outlines",
        "path",
        "paths",
        "point",
        "points",
        "poly",
        "polygon",
        "profile",
        "profiles",
        "pts",
        "region",
        "regions",
        "section",
        "vertices",
        "verts",
        "vnf",
    }
)


#: Parameters a name-based scan reads as a polyline and which are not one, with the reason. T81
#: established the case: `polyhedron(points, faces)` holds indices into `points` in `faces`, so
#: `points` is an unordered vertex **pool** and the traversal order lives elsewhere. Wrapping it in
#: a `Path` would be calling it something it is not, and the documented example passes a raw list,
#: as the OpenSCAD primitive it wraps does.
#:
#: Shared because two rules need it: the one requiring a polyline parameter to take a `Path`, and
#: the one requiring it to *accept* one. Before T86 only the first knew, so widening the second's
#: name list surfaced the same three signatures again.
NOT_A_POLYLINE: dict[str, str] = {
    "polyhedron::points": "a vertex pool indexed by `faces`, not a traversal",
}
