# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# Static type stub for the lazily re-exported top-level API.
#
# `pybosl2/__init__.py` resolves its convenience exports through `__getattr__` so `import pybosl2`
# stays cheap. That is invisible to type checkers and IDEs, so this stub declares the same names
# statically (SPEC.md A-4): every entry mirrors one row of `_LAZY_EXPORTS`, and
# tests/test_init_stub.py fails if the two ever drift apart.

from typing import Final

from pybosl2 import shapes2d as shapes2d
from pybosl2 import shapes3d as shapes3d
from pybosl2._backend import current_backend as current_backend
from pybosl2._backend import known_backends as known_backends
from pybosl2._backend import set_default_backend as set_default_backend
from pybosl2._backend import use_backend as use_backend
from pybosl2._edges_lang import Anchor as Anchor
from pybosl2._edges_lang import CornerPlane as CornerPlane
from pybosl2._edges_lang import EdgePlane as EdgePlane
from pybosl2._shape import diff as diff
from pybosl2._shape import intersect as intersect
from pybosl2.beziers import Bezier as Bezier
from pybosl2.beziers import BezierPatch as BezierPatch
from pybosl2.bounds import Bounds2D as Bounds2D
from pybosl2.bounds import Bounds3D as Bounds3D
from pybosl2.caps import CapSpec as CapSpec
from pybosl2.caps import CapType as CapType
from pybosl2.color import Color as Color
from pybosl2.color import rainbow as rainbow
from pybosl2.color import rainbow_colors as rainbow_colors
from pybosl2.constants import BACK as BACK
from pybosl2.constants import BOTTOM as BOTTOM
from pybosl2.constants import CENTER as CENTER
from pybosl2.constants import DOWN as DOWN
from pybosl2.constants import FORWARD as FORWARD
from pybosl2.constants import FRONT as FRONT
from pybosl2.constants import IDENT as IDENT
from pybosl2.constants import INCH as INCH
from pybosl2.constants import LEFT as LEFT
from pybosl2.constants import LINE as LINE
from pybosl2.constants import RAY as RAY
from pybosl2.constants import RIGHT as RIGHT
from pybosl2.constants import SEGMENT as SEGMENT
from pybosl2.constants import TOP as TOP
from pybosl2.constants import UP as UP
from pybosl2.defaults import Resolution as Resolution
from pybosl2.defaults import current_defaults as current_defaults
from pybosl2.defaults import reset_defaults as reset_defaults
from pybosl2.defaults import set_defaults as set_defaults
from pybosl2.defaults import use_defaults as use_defaults
from pybosl2.distributors import xdistribute as xdistribute
from pybosl2.distributors import ydistribute as ydistribute
from pybosl2.distributors import zdistribute as zdistribute
from pybosl2.enums import AttachTag as AttachTag
from pybosl2.exceptions import Bosl2Error as Bosl2Error
from pybosl2.exceptions import CrossBackendError as CrossBackendError
from pybosl2.exceptions import UnsupportedByBackendError as UnsupportedByBackendError
from pybosl2.flat import Flat as Flat
from pybosl2.flat import Shape2D as Shape2D
from pybosl2.flat import circle as circle
from pybosl2.flat import polygon as polygon
from pybosl2.flat import rect as rect
from pybosl2.flat import square as square
from pybosl2.flat import text as text
from pybosl2.isosurface import Metaball as Metaball
from pybosl2.isosurface import MetaballSpec as MetaballSpec
from pybosl2.isosurface import mb_capsule as mb_capsule
from pybosl2.isosurface import mb_connector as mb_connector
from pybosl2.isosurface import mb_cuboid as mb_cuboid
from pybosl2.isosurface import mb_disk as mb_disk
from pybosl2.isosurface import mb_octahedron as mb_octahedron
from pybosl2.isosurface import mb_sphere as mb_sphere
from pybosl2.isosurface import mb_torus as mb_torus
from pybosl2.isosurface import metaballs2d as metaballs2d
from pybosl2.masking import mask2d_chamfer as mask2d_chamfer
from pybosl2.masking import mask2d_cove as mask2d_cove
from pybosl2.masking import mask2d_groove as mask2d_groove
from pybosl2.masking import mask2d_step as mask2d_step
from pybosl2.masking import mask2d_tear as mask2d_tear
from pybosl2.masking import mask3d_chamfer as mask3d_chamfer
from pybosl2.masking import mask3d_groove as mask3d_groove
from pybosl2.masking import mask3d_roundover as mask3d_roundover
from pybosl2.math import EPSILON as EPSILON
from pybosl2.math import constrain as constrain
from pybosl2.math import mean as mean
from pybosl2.math import modang as modang
from pybosl2.math import quant as quant
from pybosl2.math import slerp as slerp
from pybosl2.math import slerpn as slerpn
from pybosl2.miscellaneous import chain_hull as chain_hull
from pybosl2.miscellaneous import cylindrical_extrude as cylindrical_extrude
from pybosl2.miscellaneous import extrude_from_to as extrude_from_to
from pybosl2.miscellaneous import minkowski_difference as minkowski_difference
from pybosl2.nurbs import NurbsCurve as NurbsCurve
from pybosl2.nurbs import NurbsPatch as NurbsPatch
from pybosl2.nurbs import NurbsType as NurbsType
from pybosl2.partitions import partition_cut_mask as partition_cut_mask
from pybosl2.partitions import partition_mask as partition_mask
from pybosl2.partitions import partition_path as partition_path
from pybosl2.path2d import MinkowskiJoin as MinkowskiJoin
from pybosl2.path2d import Path2D as Path2D
from pybosl2.path3d import Path3D as Path3D
from pybosl2.paths import CutPoint as CutPoint
from pybosl2.paths import Path as Path
from pybosl2.points import Point as Point
from pybosl2.points import Vector as Vector
from pybosl2.quaternions import quaternion as quaternion
from pybosl2.quaternions import quaternion_mult as quaternion_mult
from pybosl2.quaternions import quaternion_rot as quaternion_rot
from pybosl2.quaternions import quaternion_slerp as quaternion_slerp
from pybosl2.quaternions import quaternion_to_axis as quaternion_to_axis
from pybosl2.quaternions import quaternion_to_matrix as quaternion_to_matrix
from pybosl2.regions import Region as Region
from pybosl2.shapes2d import arc as arc
from pybosl2.shapes2d import egg as egg
from pybosl2.shapes2d import ellipse as ellipse
from pybosl2.shapes2d import fill as fill
from pybosl2.shapes2d import glued_circles as glued_circles
from pybosl2.shapes2d import hexagon as hexagon
from pybosl2.shapes2d import jittered_poly as jittered_poly
from pybosl2.shapes2d import keyhole as keyhole
from pybosl2.shapes2d import octagon as octagon
from pybosl2.shapes2d import pentagon as pentagon
from pybosl2.shapes2d import regular_ngon as regular_ngon
from pybosl2.shapes2d import reuleaux_polygon as reuleaux_polygon
from pybosl2.shapes2d import right_triangle as right_triangle
from pybosl2.shapes2d import ring as ring
from pybosl2.shapes2d import round2d as round2d
from pybosl2.shapes2d import shell2d as shell2d
from pybosl2.shapes2d import squircle as squircle
from pybosl2.shapes2d import star as star
from pybosl2.shapes2d import supershape as supershape
from pybosl2.shapes2d import teardrop2d as teardrop2d
from pybosl2.shapes2d import trapezoid as trapezoid
from pybosl2.shapes3d import cone as cone
from pybosl2.shapes3d import cross as cross
from pybosl2.shapes3d import path_text as path_text
from pybosl2.shapes3d import roof as roof
from pybosl2.shapes3d import text3d as text3d
from pybosl2.solid import Solid as Solid
from pybosl2.solid import cube as cube
from pybosl2.solid import cuboid as cuboid
from pybosl2.solid import cyl as cyl
from pybosl2.solid import cylinder as cylinder
from pybosl2.solid import effective_defaults as effective_defaults
from pybosl2.solid import octahedron as octahedron
from pybosl2.solid import onion as onion
from pybosl2.solid import pie_slice as pie_slice
from pybosl2.solid import polyhedron as polyhedron
from pybosl2.solid import prismoid as prismoid
from pybosl2.solid import rect_tube as rect_tube
from pybosl2.solid import regular_prism as regular_prism
from pybosl2.solid import sphere as sphere
from pybosl2.solid import spheroid as spheroid
from pybosl2.solid import teardrop as teardrop
from pybosl2.solid import torus as torus
from pybosl2.solid import tube as tube
from pybosl2.solid import wedge as wedge
from pybosl2.surfaces3d import cylindrical_heightfield as cylindrical_heightfield
from pybosl2.surfaces3d import heightfield as heightfield
from pybosl2.turtle import turtle2d as turtle2d
from pybosl2.turtle import turtle3d as turtle3d
from pybosl2.version import Version as Version
from pybosl2.version import version as version
from pybosl2.vnf import VNF as VNF
from pybosl2.vnf import contour as contour

CENTRE = CENTER  # British spelling alias

__version__: Final[str]
__all__: list[str] = [
    "Anchor",
    "AttachTag",
    "BACK",
    "BOTTOM",
    "Bezier",
    "BezierPatch",
    "Bosl2Error",
    "Bounds2D",
    "Bounds3D",
    "CENTER",
    "CENTRE",
    "CapSpec",
    "CapType",
    "Color",
    "CornerPlane",
    "CrossBackendError",
    "CutPoint",
    "DOWN",
    "EPSILON",
    "EdgePlane",
    "FORWARD",
    "FRONT",
    "Flat",
    "IDENT",
    "INCH",
    "LEFT",
    "LINE",
    "Metaball",
    "MetaballSpec",
    "MinkowskiJoin",
    "NurbsCurve",
    "NurbsPatch",
    "NurbsType",
    "Path",
    "Path2D",
    "Path3D",
    "Point",
    "RAY",
    "RIGHT",
    "Region",
    "Resolution",
    "SEGMENT",
    "Shape2D",
    "Solid",
    "TOP",
    "UP",
    "UnsupportedByBackendError",
    "VNF",
    "Vector",
    "Version",
    "__version__",
    "arc",
    "chain_hull",
    "circle",
    "cone",
    "constrain",
    "contour",
    "cross",
    "cube",
    "cuboid",
    "current_backend",
    "current_defaults",
    "cyl",
    "cylinder",
    "cylindrical_extrude",
    "cylindrical_heightfield",
    "diff",
    "effective_defaults",
    "egg",
    "ellipse",
    "extrude_from_to",
    "fill",
    "glued_circles",
    "heightfield",
    "hexagon",
    "intersect",
    "jittered_poly",
    "keyhole",
    "known_backends",
    "mask2d_chamfer",
    "mask2d_cove",
    "mask2d_groove",
    "mask2d_step",
    "mask2d_tear",
    "mask3d_chamfer",
    "mask3d_groove",
    "mask3d_roundover",
    "mb_capsule",
    "mb_connector",
    "mb_cuboid",
    "mb_disk",
    "mb_octahedron",
    "mb_sphere",
    "mb_torus",
    "mean",
    "metaballs2d",
    "minkowski_difference",
    "modang",
    "octagon",
    "octahedron",
    "onion",
    "partition_cut_mask",
    "partition_mask",
    "partition_path",
    "path_text",
    "pentagon",
    "pie_slice",
    "polygon",
    "polyhedron",
    "prismoid",
    "quant",
    "quaternion",
    "quaternion_mult",
    "quaternion_rot",
    "quaternion_slerp",
    "quaternion_to_axis",
    "quaternion_to_matrix",
    "rainbow",
    "rainbow_colors",
    "rect",
    "rect_tube",
    "regular_ngon",
    "regular_prism",
    "reset_defaults",
    "reuleaux_polygon",
    "right_triangle",
    "ring",
    "roof",
    "round2d",
    "set_default_backend",
    "set_defaults",
    "shapes2d",
    "shapes3d",
    "shell2d",
    "slerp",
    "slerpn",
    "sphere",
    "spheroid",
    "square",
    "squircle",
    "star",
    "supershape",
    "teardrop",
    "teardrop2d",
    "text",
    "text3d",
    "torus",
    "trapezoid",
    "tube",
    "turtle2d",
    "turtle3d",
    "use_backend",
    "use_defaults",
    "version",
    "wedge",
    "xdistribute",
    "ydistribute",
    "zdistribute",
]
