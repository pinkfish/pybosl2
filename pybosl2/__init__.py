# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/__init__.py
#    Convenience top-level exports via lazy attribute access.  You can write
#    ``from pybosl2 import Path2D, square, cuboid`` and the underlying
#    sub-modules are only loaded when the name is first accessed — not at
#    ``import pybosl2`` time, which keeps sub-module isolation (e.g. the SDF
#    backend) intact.
#
#    Parts-library classes live under ``pybosl2.parts`` and are NOT re-exported
#    here; import them explicitly from that sub-package.
#
# FileSummary: Top-level convenience re-exports (lazy) for the pybosl2 BOSL2 toolkit.
# FileGroup: BOSL2

from pybosl2.version import Version, __version__, version

# All other exports are lazy — the sub-module is only imported when
# the attribute is first accessed.

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # core types
    "Path": ("pybosl2.paths", "Path"),
    "CutPoint": ("pybosl2.paths", "CutPoint"),
    "": ("pybosl2.paths", ""),
    "Path2D": ("pybosl2.path2d", "Path2D"),
    "Path3D": ("pybosl2.path3d", "Path3D"),
    "Region": ("pybosl2.regions", "Region"),
    "Point": ("pybosl2.points", "Point"),
    "Vector": ("pybosl2.points", "Vector"),
    "Bounds2D": ("pybosl2.bounds", "Bounds2D"),
    "Bounds3D": ("pybosl2.bounds", "Bounds3D"),
    "CapSpec": ("pybosl2.caps", "CapSpec"),
    "CapType": ("pybosl2.caps", "CapType"),
    "UnsupportedByBackendError": ("pybosl2.exceptions", "UnsupportedByBackendError"),
    # anchor system
    "Anchor": ("pybosl2._edges_lang", "Anchor"),
    "EdgePlane": ("pybosl2._edges_lang", "EdgePlane"),
    "CornerPlane": ("pybosl2._edges_lang", "CornerPlane"),
    # constants
    "EPSILON": ("pybosl2.math", "EPSILON"),
    "CENTRE": ("pybosl2.constants", "CENTER"),  # British spelling alias
    # colour
    "rainbow": ("pybosl2.color", "rainbow"),
    "rainbow_colors": ("pybosl2.color", "rainbow_colors"),
    # 2-D shapes
    "arc": ("pybosl2.shapes2d", "arc"),
    "circle": ("pybosl2.shapes2d", "circle"),
    "egg": ("pybosl2.shapes2d", "egg"),
    "ellipse": ("pybosl2.shapes2d", "ellipse"),
    "fill": ("pybosl2.shapes2d", "fill"),
    "glued_circles": ("pybosl2.shapes2d", "glued_circles"),
    "hexagon": ("pybosl2.shapes2d", "hexagon"),
    "jittered_poly": ("pybosl2.shapes2d", "jittered_poly"),
    "keyhole": ("pybosl2.shapes2d", "keyhole"),
    "octagon": ("pybosl2.shapes2d", "octagon"),
    "pentagon": ("pybosl2.shapes2d", "pentagon"),
    "rect": ("pybosl2.shapes2d", "rect"),
    "regular_ngon": ("pybosl2.shapes2d", "regular_ngon"),
    "reuleaux_polygon": ("pybosl2.shapes2d", "reuleaux_polygon"),
    "right_triangle": ("pybosl2.shapes2d", "right_triangle"),
    "ring": ("pybosl2.shapes2d", "ring"),
    "round2d": ("pybosl2.shapes2d", "round2d"),
    "shell2d": ("pybosl2.shapes2d", "shell2d"),
    "square": ("pybosl2.shapes2d", "square"),
    "squircle": ("pybosl2.shapes2d", "squircle"),
    "star": ("pybosl2.shapes2d", "star"),
    "supershape": ("pybosl2.shapes2d", "supershape"),
    "teardrop2d": ("pybosl2.shapes2d", "teardrop2d"),
    "text": ("pybosl2.shapes2d", "text"),
    "trapezoid": ("pybosl2.shapes2d", "trapezoid"),
    # 3-D shapes
    "cuboid": ("pybosl2.shapes3d", "cuboid"),
    "cube": ("pybosl2.shapes3d", "cube"),
    "sphere": ("pybosl2.shapes3d", "sphere"),
    "spheroid": ("pybosl2.shapes3d", "spheroid"),
    "cylinder": ("pybosl2.shapes3d", "cylinder"),
    "cyl": ("pybosl2.shapes3d", "cyl"),
    "prismoid": ("pybosl2.shapes3d", "prismoid"),
    "regular_prism": ("pybosl2.shapes3d", "regular_prism"),
    "octahedron": ("pybosl2.shapes3d", "octahedron"),
    "rect_tube": ("pybosl2.shapes3d", "rect_tube"),
    "torus": ("pybosl2.shapes3d", "torus"),
    "teardrop": ("pybosl2.shapes3d", "teardrop"),
    "onion": ("pybosl2.shapes3d", "onion"),
    "pie_slice": ("pybosl2.shapes3d", "pie_slice"),
    "roof": ("pybosl2.shapes3d", "roof"),
    "wedge": ("pybosl2.shapes3d", "wedge"),
    "tube": ("pybosl2.shapes3d", "tube"),
    "cross": ("pybosl2.shapes3d", "cross"),
    "path_text": ("pybosl2.shapes3d", "path_text"),
    "text3d": ("pybosl2.shapes3d", "text3d"),
    # distributors
    "xdistribute": ("pybosl2.distributors", "xdistribute"),
    "ydistribute": ("pybosl2.distributors", "ydistribute"),
    "zdistribute": ("pybosl2.distributors", "zdistribute"),
    # path generators
    "catenary": ("pybosl2.path2d", "catenary"),
    "helix": ("pybosl2.path3d", "helix"),
    # bezier / NURBS
    "Bezier": ("pybosl2.beziers", "Bezier"),
    "BezierPatch": ("pybosl2.beziers", "BezierPatch"),
    "nurbs_curve": ("pybosl2.nurbs", "nurbs_curve"),
    "nurbs_patch_points": ("pybosl2.nurbs", "nurbs_patch_points"),
    "nurbs_vnf": ("pybosl2.nurbs", "nurbs_vnf"),
    "is_nurbs_patch": ("pybosl2.nurbs", "is_nurbs_patch"),
    "nurbs_elevate_degree": ("pybosl2.nurbs", "nurbs_elevate_degree"),
    # skin / sweep
    "sweep": ("pybosl2.skin", "sweep"),
    "skin": ("pybosl2.skin", "skin"),
    "rot_resample": ("pybosl2.skin", "rot_resample"),
    # partitioning
    "partition_path": ("pybosl2.partitions", "partition_path"),
    "partition_mask": ("pybosl2.partitions", "partition_mask"),
    "partition_cut_mask": ("pybosl2.partitions", "partition_cut_mask"),
    # miscellaneous
    "extrude_from_to": ("pybosl2.miscellaneous", "extrude_from_to"),
    "cylindrical_extrude": ("pybosl2.miscellaneous", "cylindrical_extrude"),
    "chain_hull": ("pybosl2.miscellaneous", "chain_hull"),
    "minkowski_difference": ("pybosl2.miscellaneous", "minkowski_difference"),
    # rounding
    "round_corners": ("pybosl2.rounding", "_round_corners"),
    "smooth_path": ("pybosl2.rounding", "_smooth_path"),
    # isosurface / metaballs
    "mb_sphere": ("pybosl2.metaballs", "mb_sphere"),
    "mb_cuboid": ("pybosl2.metaballs", "mb_cuboid"),
    "mb_torus": ("pybosl2.metaballs", "mb_torus"),
    "mb_capsule": ("pybosl2.metaballs", "mb_capsule"),
    "mb_disk": ("pybosl2.metaballs", "mb_disk"),
    "mb_octahedron": ("pybosl2.metaballs", "mb_octahedron"),
    "mb_connector": ("pybosl2.metaballs", "mb_connector"),
    "Metaball": ("pybosl2.metaballs", "Metaball"),
    "MetaballSpec": ("pybosl2.metaballs", "MetaballSpec"),
    # VNF
    "VNF": ("pybosl2.vnf", "VNF"),
    "vnf_polyhedron": ("pybosl2.vnf", "vnf_polyhedron"),
    # surfaces
    "heightfield": ("pybosl2.surfaces3d", "heightfield"),
    "cylindrical_heightfield": ("pybosl2.surfaces3d", "cylindrical_heightfield"),
}


def __getattr__(name: str) -> object:
    if name in _LAZY_EXPORTS:
        parts = _LAZY_EXPORTS[name]
        import importlib

        mod = importlib.import_module(parts[0])
        if len(parts) == 3 and parts[1]:
            obj = getattr(getattr(mod, parts[1]), parts[2])
        elif parts[1]:
            obj = getattr(mod, parts[1])
        else:
            obj = mod  # side-effect import only (empty attr name)
        globals()[name] = obj
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["Version", "__version__", "version"] + sorted(k for k in _LAZY_EXPORTS if k)
