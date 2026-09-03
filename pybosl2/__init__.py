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

"""Top-level convenience re-exports (lazy) for the pybosl2 BOSL2 toolkit."""

from pybosl2.version import Version, __version__, version

# All other exports are lazy — the sub-module is only imported when
# the attribute is first accessed.

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # backend selection
    "current_backend": ("pybosl2._backend", "current_backend"),
    "use_backend": ("pybosl2._backend", "use_backend"),
    "set_default_backend": ("pybosl2._backend", "set_default_backend"),
    "known_backends": ("pybosl2._backend", "known_backends"),
    # ambient resolution defaults
    "Resolution": ("pybosl2.defaults", "Resolution"),
    # argument groups (SPEC G-1)
    "Placement": ("pybosl2.groups", "Placement"),
    "Facets": ("pybosl2.groups", "Facets"),
    "EdgeTreatment": ("pybosl2.groups", "EdgeTreatment"),
    "EdgeSelection": ("pybosl2.groups", "EdgeSelection"),
    "Texturing": ("pybosl2.groups", "Texturing"),
    "EdgeTreatmentKind": ("pybosl2.enums", "EdgeTreatmentKind"),
    "current_defaults": ("pybosl2.defaults", "current_defaults"),
    "use_defaults": ("pybosl2.defaults", "use_defaults"),
    "set_defaults": ("pybosl2.defaults", "set_defaults"),
    "reset_defaults": ("pybosl2.defaults", "reset_defaults"),
    "effective_defaults": ("pybosl2.solid", "effective_defaults"),
    # core types
    "Path": ("pybosl2.paths", "Path"),
    "PathLike": ("pybosl2.paths", "PathLike"),
    "CutPoint": ("pybosl2.paths", "CutPoint"),
    "Path2D": ("pybosl2.path2d", "Path2D"),
    "Path3D": ("pybosl2.path3d", "Path3D"),
    "Region": ("pybosl2.regions", "Region"),
    "Point": ("pybosl2.points", "Point"),
    "Vector": ("pybosl2.points", "Vector"),
    "Bounds2D": ("pybosl2.bounds", "Bounds2D"),
    "Bounds3D": ("pybosl2.bounds", "Bounds3D"),
    "CapSpec": ("pybosl2.caps", "CapSpec"),
    "CapType": ("pybosl2.caps", "CapType"),
    "Bosl2Error": ("pybosl2.exceptions", "Bosl2Error"),
    "Bosl2NotImplementedError": ("pybosl2.exceptions", "Bosl2NotImplementedError"),
    "UnsupportedByBackendError": ("pybosl2.exceptions", "UnsupportedByBackendError"),
    "CrossBackendError": ("pybosl2.exceptions", "CrossBackendError"),
    "Shape": ("pybosl2._backend", "Shape"),
    "Solid": ("pybosl2.solid", "Solid"),
    "Flat": ("pybosl2.flat", "Flat"),
    # anchor system
    "Anchor": ("pybosl2._edges_lang", "Anchor"),
    "EdgePlane": ("pybosl2._edges_lang", "EdgePlane"),
    "CornerPlane": ("pybosl2._edges_lang", "CornerPlane"),
    "AttachTag": ("pybosl2.enums", "AttachTag"),
    "diff": ("pybosl2._shape", "diff"),
    "intersect": ("pybosl2._shape", "intersect"),
    # constants
    "EPSILON": ("pybosl2.math", "EPSILON"),
    "CENTRE": ("pybosl2.constants", "CENTER"),  # British spelling alias
    "INCH": ("pybosl2.constants", "INCH"),
    "IDENT": ("pybosl2.constants", "IDENT"),
    "LEFT": ("pybosl2.constants", "LEFT"),
    "RIGHT": ("pybosl2.constants", "RIGHT"),
    "FRONT": ("pybosl2.constants", "FRONT"),
    "FORWARD": ("pybosl2.constants", "FORWARD"),
    "BACK": ("pybosl2.constants", "BACK"),
    "BOTTOM": ("pybosl2.constants", "BOTTOM"),
    "DOWN": ("pybosl2.constants", "DOWN"),
    "TOP": ("pybosl2.constants", "TOP"),
    "UP": ("pybosl2.constants", "UP"),
    "CENTER": ("pybosl2.constants", "CENTER"),
    "SEGMENT": ("pybosl2.constants", "SEGMENT"),
    "RAY": ("pybosl2.constants", "RAY"),
    "LINE": ("pybosl2.constants", "LINE"),
    # math
    "slerp": ("pybosl2.math", "slerp"),
    "slerpn": ("pybosl2.math", "slerpn"),
    "modang": ("pybosl2.math", "modang"),
    "quant": ("pybosl2.math", "quant"),
    "constrain": ("pybosl2.math", "constrain"),
    "mean": ("pybosl2.math", "mean"),
    # colour
    "Color": ("pybosl2.color", "Color"),
    "rainbow": ("pybosl2.color", "rainbow"),
    "rainbow_colors": ("pybosl2.color", "rainbow_colors"),
    # 2-D shapes
    "shapes2d": ("pybosl2.shapes2d", ""),
    "arc": ("pybosl2.shapes2d", "arc"),
    "circle": ("pybosl2.flat", "circle"),
    "egg": ("pybosl2.shapes2d", "egg"),
    "ellipse": ("pybosl2.flat", "ellipse"),
    "fill": ("pybosl2.shapes2d", "fill"),
    "glued_circles": ("pybosl2.shapes2d", "glued_circles"),
    "hexagon": ("pybosl2.shapes2d", "hexagon"),
    "jittered_poly": ("pybosl2.shapes2d", "jittered_poly"),
    "keyhole": ("pybosl2.shapes2d", "keyhole"),
    "octagon": ("pybosl2.shapes2d", "octagon"),
    "pentagon": ("pybosl2.shapes2d", "pentagon"),
    "polygon": ("pybosl2.flat", "polygon"),
    "rect": ("pybosl2.flat", "rect"),
    "regular_ngon": ("pybosl2.flat", "regular_ngon"),
    "reuleaux_polygon": ("pybosl2.shapes2d", "reuleaux_polygon"),
    "right_triangle": ("pybosl2.shapes2d", "right_triangle"),
    "ring": ("pybosl2.shapes2d", "ring"),
    "round2d": ("pybosl2.shapes2d", "round2d"),
    "shell2d": ("pybosl2.shapes2d", "shell2d"),
    "square": ("pybosl2.flat", "square"),
    "squircle": ("pybosl2.shapes2d", "squircle"),
    "star": ("pybosl2.flat", "star"),
    "supershape": ("pybosl2.shapes2d", "supershape"),
    "teardrop2d": ("pybosl2.shapes2d", "teardrop2d"),
    "text": ("pybosl2.flat", "text"),
    "trapezoid": ("pybosl2.flat", "trapezoid"),
    # 3-D shapes
    "shapes3d": ("pybosl2.shapes3d", ""),
    "cuboid": ("pybosl2.solid", "cuboid"),
    "cube": ("pybosl2.solid", "cube"),
    "sphere": ("pybosl2.solid", "sphere"),
    "spheroid": ("pybosl2.solid", "spheroid"),
    "cylinder": ("pybosl2.solid", "cylinder"),
    "cyl": ("pybosl2.solid", "cyl"),
    "xcyl": ("pybosl2.solid", "xcyl"),
    "ycyl": ("pybosl2.solid", "ycyl"),
    "zcyl": ("pybosl2.solid", "zcyl"),
    "cone": ("pybosl2.shapes3d", "cone"),
    "prismoid": ("pybosl2.solid", "prismoid"),
    "regular_prism": ("pybosl2.solid", "regular_prism"),
    "octahedron": ("pybosl2.solid", "octahedron"),
    "rect_tube": ("pybosl2.solid", "rect_tube"),
    "torus": ("pybosl2.solid", "torus"),
    "teardrop": ("pybosl2.solid", "teardrop"),
    "onion": ("pybosl2.solid", "onion"),
    "pie_slice": ("pybosl2.solid", "pie_slice"),
    "roof": ("pybosl2.shapes3d", "roof"),
    "wedge": ("pybosl2.solid", "wedge"),
    "tube": ("pybosl2.solid", "tube"),
    "cross": ("pybosl2.shapes3d", "cross"),
    "path_text": ("pybosl2.shapes3d", "path_text"),
    "text3d": ("pybosl2.shapes3d", "text3d"),
    "polyhedron": ("pybosl2.solid", "polyhedron"),
    "union": ("pybosl2.solid", "union"),
    "difference": ("pybosl2.solid", "difference"),
    "intersection": ("pybosl2.solid", "intersection"),
    # distributors
    "xdistribute": ("pybosl2.distributors", "xdistribute"),
    "ydistribute": ("pybosl2.distributors", "ydistribute"),
    "zdistribute": ("pybosl2.distributors", "zdistribute"),
    # bezier / NURBS
    "Bezier": ("pybosl2.beziers", "Bezier"),
    "BezierPatch": ("pybosl2.beziers", "BezierPatch"),
    "NurbsType": ("pybosl2.nurbs", "NurbsType"),
    "NurbsCurve": ("pybosl2.nurbs", "NurbsCurve"),
    "NurbsPatch": ("pybosl2.nurbs", "NurbsPatch"),
    "turtle2d": ("pybosl2.turtle", "turtle2d"),
    "turtle3d": ("pybosl2.turtle", "turtle3d"),
    # partitioning
    "partition_path": ("pybosl2.partitions", "partition_path"),
    "partition_mask": ("pybosl2.partitions", "partition_mask"),
    "partition_cut_mask": ("pybosl2.partitions", "partition_cut_mask"),
    # miscellaneous
    "extrude_from_to": ("pybosl2.miscellaneous", "extrude_from_to"),
    "cylindrical_extrude": ("pybosl2.miscellaneous", "cylindrical_extrude"),
    "chain_hull": ("pybosl2.miscellaneous", "chain_hull"),
    "minkowski_difference": ("pybosl2.miscellaneous", "minkowski_difference"),
    "MinkowskiJoin": ("pybosl2.path2d", "MinkowskiJoin"),
    # isosurface / metaballs
    "mb_sphere": ("pybosl2.isosurface", "mb_sphere"),
    "mb_cuboid": ("pybosl2.isosurface", "mb_cuboid"),
    "mb_torus": ("pybosl2.isosurface", "mb_torus"),
    "mb_capsule": ("pybosl2.isosurface", "mb_capsule"),
    "mb_disk": ("pybosl2.isosurface", "mb_disk"),
    "mb_octahedron": ("pybosl2.isosurface", "mb_octahedron"),
    "mb_connector": ("pybosl2.isosurface", "mb_connector"),
    "metaballs2d": ("pybosl2.isosurface", "metaballs2d"),
    "Metaball": ("pybosl2.isosurface", "Metaball"),
    "MetaballSpec": ("pybosl2.isosurface", "MetaballSpec"),
    # VNF
    "VNF": ("pybosl2.vnf", "VNF"),
    "contour": ("pybosl2.vnf", "contour"),
    # surfaces
    "heightfield": ("pybosl2.surfaces3d", "heightfield"),
    "cylindrical_heightfield": ("pybosl2.surfaces3d", "cylindrical_heightfield"),
    # quaternions
    "quaternion": ("pybosl2.quaternions", "quaternion"),
    "quaternion_to_matrix": ("pybosl2.quaternions", "quaternion_to_matrix"),
    "quaternion_to_axis": ("pybosl2.quaternions", "quaternion_to_axis"),
    "quaternion_mult": ("pybosl2.quaternions", "quaternion_mult"),
    "quaternion_slerp": ("pybosl2.quaternions", "quaternion_slerp"),
    "quaternion_rot": ("pybosl2.quaternions", "quaternion_rot"),
    # sweeps: the sweep itself is a Path2D/Path3D method (S-19), so what the top level owes the
    # caller is the vocabulary those methods take -- the enums and the end treatments (A-8).
    "SweepMethod": ("pybosl2.enums", "SweepMethod"),
    "SkinMethod": ("pybosl2.enums", "SkinMethod"),
    "SamplingType": ("pybosl2.enums", "SamplingType"),
    "ResampleMethod": ("pybosl2.enums", "ResampleMethod"),
    "RoundingMethod": ("pybosl2.enums", "RoundingMethod"),
    "PartitionCutType": ("pybosl2.enums", "PartitionCutType"),
    "VNFStyle": ("pybosl2.enums", "VNFStyle"),
    "EdgeMode": ("pybosl2.enums", "EdgeMode"),
    "Measure": ("pybosl2.enums", "Measure"),
    "StaggerMode": ("pybosl2.enums", "StaggerMode"),
    # offset-sweep end treatments (S-21): a rim treatment is one value, so the values are exported
    "os_circle": ("pybosl2.skin", "os_circle"),
    "os_smooth": ("pybosl2.skin", "os_smooth"),
    "os_teardrop": ("pybosl2.skin", "os_teardrop"),
    "os_chamfer": ("pybosl2.skin", "os_chamfer"),
    "os_flat": ("pybosl2.skin", "os_flat"),
    "os_profile": ("pybosl2.skin", "os_profile"),
    "OSProfile": ("pybosl2.skin", "OSProfile"),
    "OSType": ("pybosl2.skin", "OSType"),
    # corner treatment (S-8) is `path.round_corners(...)` / `path.smooth_path(...)` -- methods on
    # the Path types (PLAN O-3), so what the top level owes is the vocabulary: RoundingMethod above.
    # turtles (S-10)
    "Turtle2D": ("pybosl2.turtle", "Turtle2D"),
    "Turtle3D": ("pybosl2.turtle", "Turtle3D"),
    # rotation algebra (S-5): the class is the preferred spelling, not just the functions
    "Quaternion": ("pybosl2.quaternions", "Quaternion"),
    # textures (S-34)
    "texture": ("pybosl2.texture", "texture"),
    # the mask family, whole (S-26): mask2d_roundover was the one member left out
    "mask2d_roundover": ("pybosl2.masking", "mask2d_roundover"),
    # export (S-53)
    "Bosl2ValueError": ("pybosl2.exceptions", "Bosl2ValueError"),
    # masking
    "Mask2D": ("pybosl2.masking", "Mask2D"),
    "Mask3D": ("pybosl2.masking", "Mask3D"),
    "mask2d_chamfer": ("pybosl2.masking", "mask2d_chamfer"),
    "mask2d_cove": ("pybosl2.masking", "mask2d_cove"),
    "mask2d_tear": ("pybosl2.masking", "mask2d_tear"),
    "mask2d_step": ("pybosl2.masking", "mask2d_step"),
    "mask2d_groove": ("pybosl2.masking", "mask2d_groove"),
    "mask3d_roundover": ("pybosl2.masking", "mask3d_roundover"),
    "mask3d_chamfer": ("pybosl2.masking", "mask3d_chamfer"),
    "mask3d_groove": ("pybosl2.masking", "mask3d_groove"),
}


def __getattr__(name: str) -> object:
    if name in _LAZY_EXPORTS:
        module_name, attribute = _LAZY_EXPORTS[name]
        import importlib

        mod = importlib.import_module(module_name)
        obj = getattr(mod, attribute) if attribute else mod  # empty attr name: the module itself
        globals()[name] = obj
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return everything the façade exports, so the lazy names are still discoverable.

    PEP 562 pairs a module `__getattr__` with a module `__dir__` for exactly this reason: a name
    reached lazily does not exist in `globals()` until something asks for it, so without this
    `dir(pybosl2)` -- and every REPL and IDE completion built on it -- listed 3 public names out
    of 191, and the top-level façade the library points newcomers at looked empty (SPEC DOC-5).
    """
    return sorted(set(__all__) | set(globals()))


__all__ = ["Version", "__version__", "version"] + sorted(k for k in _LAZY_EXPORTS if k)
