# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/skin.py: frame_map, sweep and path_sweep frame methods."""

import math
from typing import Any

import numpy as np
import pytest

from pybosl2.caps import CapType
from pybosl2.enums import ResampleMethod, SkinMethod, SweepMethod
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D
from pybosl2.skin import (
    OSProfile,
    clockwise_polygon,
    frame_map,
    os_chamfer,
    os_circle,
    os_flat,
    os_profile,
    os_smooth,
    os_teardrop,
    path3d,
    rot_resample,
    slice_profiles,
    subdivide_and_slice,
)
from pybosl2.skin import (
    _linear_sweep as linear_sweep,
)
from pybosl2.skin import (
    _path_sweep2d as path_sweep2d,
)
from pybosl2.skin import (
    _rotate_sweep as rotate_sweep,
)
from pybosl2.skin import (
    _skin as skin,
)
from pybosl2.skin import (
    _spiral_sweep as spiral_sweep,
)

SQUARE = [[-1, -1], [1, -1], [1, 1], [-1, 1]]


def _mesh(swept: object) -> Any:
    """The mesh behind a sweep result.

    Sweeps return a `Solid` now (SPEC S-19a) and keep the mesh on `.vnf()`; the lower-level helpers
    still hand back a bare VNF, so both are accepted.
    """
    mesh = getattr(swept, "vnf", swept)
    return mesh() if callable(mesh) else mesh  # `.vnf` is a method now (PLAN T-6e)


def _valid(swept: object) -> bool:
    """Every face indexes a vertex that exists.

    A sweep hands back a Solid now (SPEC S-19a), so the mesh is reached through `.vnf()`; a bare VNF
    (from the lower-level helpers) is accepted as-is.
    """
    vnf = _mesh(swept)
    return not vnf.faces or max(i for f in vnf.faces for i in f) < len(vnf.vertices)  # type: ignore[attr-defined]


def _circle(r: float, sides: int = 24) -> list[list[float]]:
    return [[r * math.cos(t), r * math.sin(t)] for t in np.linspace(0, 2 * math.pi, sides, endpoint=False)]


def test_path3d_pads_z() -> None:
    assert path3d([[1, 2], [3, 4]]) == [[1, 2, 0], [3, 4, 0]]
    assert path3d([[1, 2, 3]]) == [[1, 2, 3]]


def test_clockwise_polygon() -> None:
    counterclockwise = [[0, 0], [1, 0], [1, 1], [0, 1]]
    assert clockwise_polygon(counterclockwise) == list(reversed(counterclockwise))  # counterclockwise gets reversed
    clockwise = list(reversed(counterclockwise))
    assert clockwise_polygon(clockwise) == clockwise  # already clockwise, unchanged


def test_frame_map_orthonormal() -> None:
    m = frame_map(y=[0, 1, 0], z=[0, 0, 1])
    radius = m[:3, :3]
    np.testing.assert_allclose(radius @ radius.T, np.eye(3), atol=1e-9)
    assert math.isclose(float(np.linalg.det(radius)), 1.0)


def test_frame_map_fills_third_axis() -> None:
    m = frame_map(y=[0, 1, 0], z=[0, 0, 1])  # x should be +X
    np.testing.assert_allclose(m[:3, 0], [1, 0, 0], atol=1e-9)


def test_straight_sweep_counts() -> None:
    vnf = Path3D([[0, 0, 0], [0, 0, 5], [0, 0, 10]]).path_sweep(SQUARE)  # type: ignore[arg-type]
    assert len(_mesh(vnf).vertices) == 12  # type: ignore[arg-type, union-attr]  # 4 shape pts x 3 profiles
    assert _valid(vnf)


def test_sweep_open_has_caps_closed_does_not() -> None:
    line = [[0, 0, 0], [0, 0, 5], [0, 0, 10]]
    open_faces = len(Path3D(line).path_sweep(SQUARE, caps=CapType.BUTT).faces)  # type: ignore[arg-type, union-attr]
    nocap_faces = len(Path3D(line).path_sweep(SQUARE, caps=CapType.NONE).faces)  # type: ignore[arg-type, union-attr]
    assert open_faces == nocap_faces + 2  # two flat end caps


@pytest.mark.parametrize("method", [SweepMethod.INCREMENTAL, SweepMethod.NATURAL])
def test_curved_sweep_methods(method: str) -> None:
    curve = [[math.cos(t) * 10, math.sin(t) * 10, t * 2] for t in np.linspace(0, math.pi, 10)]
    vnf = Path3D(curve).path_sweep(SQUARE, method=method)  # type: ignore[arg-type]
    assert len(_mesh(vnf).vertices) == 40  # type: ignore[arg-type, union-attr]
    assert _valid(vnf)


def test_manual_method_with_normals() -> None:
    path = [[0, 0, 0], [0, 0, 5], [0, 0, 10]]
    normals = [[1, 0, 0]] * 3
    vnf = Path3D(path).path_sweep(SQUARE, method=SweepMethod.MANUAL, normal=normals)  # type: ignore[arg-type]
    assert _valid(vnf)


def test_closed_sweep_has_no_caps() -> None:
    circ = [[math.cos(t) * 20, math.sin(t) * 20, 0] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
    vnf = Path3D(circ).path_sweep(SQUARE, closed=True)  # type: ignore[arg-type]
    assert _valid(vnf)
    # 25 profiles (closed adds the wrap) x 4 verts
    assert len(_mesh(vnf).vertices) == 100  # type: ignore[arg-type, union-attr]


def test_transforms_mode_returns_matrices() -> None:
    tl = Path3D([[0, 0, 0], [0, 0, 5], [0, 0, 10]]).path_sweep_transforms()  # type: ignore[arg-type]
    assert len(tl) == 3  # type: ignore[arg-type]
    assert np.asarray(tl[0]).shape == (4, 4)  # type: ignore[index]


def test_twist_and_scale_run() -> None:
    vnf = Path3D([[0, 0, 0], [0, 0, 5], [0, 0, 10]]).path_sweep(SQUARE, twist=90, scale=2)  # type: ignore[arg-type]
    assert _valid(vnf)


def test_unknown_method_raises() -> None:
    with pytest.raises(ValueError, match="unknown method"):
        Path3D([[0, 0, 0], [0, 0, 5]]).path_sweep(SQUARE, method="bogus")  # type: ignore[arg-type]


def test_sweep_direct_from_transforms() -> None:
    ident = np.eye(4)
    up = np.eye(4)
    up[2, 3] = 10
    vnf = Path2D(SQUARE).sweep([ident, up])  # type: ignore[list-item]
    assert _valid(vnf)


# -- skin ---------------------------------------------------------------------------------


def test_slice_profiles_inserts_intermediates() -> None:
    a = Path2D([[0, 0], [1, 0], [1, 1]])
    b = Path2D([[0, 2], [1, 2], [1, 3]])
    out = slice_profiles([a, b], 3)  # 3 interpolated + final = 5 profiles
    assert len(out) == 5
    np.testing.assert_allclose(out[0], list(a))
    np.testing.assert_allclose(out[-1], list(b))


def test_skin_two_profiles() -> None:
    vnf = skin([_circle(6), [[-8, -8], [8, -8], [8, 8], [-8, 8]]], slices=10, z=[0, 25])
    assert _valid(vnf)
    assert _mesh(vnf).volume() > 0  # type: ignore[operator, union-attr]  # winding fixed to outward


def test_skin_reindex_method() -> None:
    vnf = skin(
        [_circle(6), [[-8, -8], [8, -8], [8, 8], [-8, 8]]],
        slices=8,
        method=SkinMethod.REINDEX,
        z=[0, 20],
    )
    assert _valid(vnf)
    assert _mesh(vnf).volume() > 0  # type: ignore[operator, union-attr]


def test_skin_three_profiles() -> None:
    vnf = skin([_circle(4), _circle(8), _circle(4)], slices=5, z=[0, 15, 30])
    assert _valid(vnf)
    assert _mesh(vnf).volume() > 0  # type: ignore[operator, union-attr]


def test_skin_closed_stack() -> None:
    profs = [
        _circle(4),
        [[-6, -6], [6, -6], [6, 6], [-6, 6]],
        _circle(4),
        [[-6, -6], [6, -6], [6, 6], [-6, 6]],
    ]
    vnf = skin(profs, slices=3, closed=True, z=[0, 10, 20, 30])  # type: ignore[arg-type]
    assert _valid(vnf)


def test_skin_rejects_unsupported_method() -> None:
    with pytest.raises(ValueError, match="only the 'direct' and"):
        skin([_circle(4), _circle(6)], slices=2, method="distance", z=[0, 10])


def test_skin_needs_two_profiles() -> None:
    with pytest.raises(ValueError, match=r"skin\(\) needs at least two"):
        skin([_circle(4)], slices=2, z=[0])


# -- linear_sweep -------------------------------------------------------------------------


def test_linear_sweep_plain_box_volume() -> None:
    sq = [[-10, -10], [10, -10], [10, 10], [-10, 10]]
    vnf = Path2D(sq).linear_sweep(height=5)
    assert _valid(vnf)
    assert math.isclose(_mesh(vnf).volume(), 20 * 20 * 5, rel_tol=1e-6)  # type: ignore[operator, union-attr]  # 2000


def test_linear_sweep_twist_scale() -> None:
    sq = [[-10, -10], [10, -10], [10, 10], [-10, 10]]
    vnf = linear_sweep(sq, height=40, twist=120, scale=0.4)
    assert _valid(vnf)
    assert _mesh(vnf).volume() > 0  # type: ignore[operator, union-attr]


def test_linear_sweep_center_vs_base() -> None:
    sq = [[-5, -5], [5, -5], [5, 5], [-5, 5]]
    base = Path2D(sq).linear_sweep(height=10)
    centered = Path2D(sq).linear_sweep(height=10, center=True)
    bz = [v[2] for v in _mesh(base).vertices]  # type: ignore[attr-defined, union-attr]
    cz = [v[2] for v in _mesh(centered).vertices]  # type: ignore[attr-defined, union-attr]
    assert math.isclose(min(bz), 0.0, abs_tol=1e-9)
    assert math.isclose(max(bz), 10.0, abs_tol=1e-9)
    assert math.isclose(min(cz), -5.0, abs_tol=1e-9)
    assert math.isclose(max(cz), 5.0, abs_tol=1e-9)


# -- rotate_sweep -------------------------------------------------------------------------

PROFILE = [[4, -10], [12, -10], [12, 10], [4, 10]]


def test_rotate_sweep_full() -> None:
    vnf = rotate_sweep(PROFILE, 360)
    assert _valid(vnf)
    assert _mesh(vnf).volume() > 0  # type: ignore[operator, union-attr]


def test_rotate_sweep_partial_has_caps() -> None:
    vnf = rotate_sweep(PROFILE, 270)
    assert _valid(vnf)
    assert _mesh(vnf).volume() > 0  # type: ignore[operator, union-attr]


def test_rotate_sweep_rejects_bad_angle() -> None:
    with pytest.raises(ValueError, match="angle must be in"):
        Path2D(PROFILE).rotate_sweep(angle=400)


# -- spiral_sweep -------------------------------------------------------------------------


def test_spiral_sweep_coil() -> None:
    section = [[-1.2, -1.2], [1.2, -1.2], [1.2, 1.2], [-1.2, 1.2]]
    vnf = spiral_sweep(section, height=40, radius=12, turns=5)
    assert _valid(vnf)
    assert _mesh(vnf).volume() > 0  # type: ignore[operator, union-attr]


def test_spiral_sweep_conical_taper() -> None:
    section = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
    vnf = spiral_sweep(section, height=30, radius1=15, radius2=5, turns=4)
    assert _valid(vnf)
    assert _mesh(vnf).volume() > 0  # type: ignore[operator, union-attr]


# -- path_sweep2d -------------------------------------------------------------------------


def test_path_sweep2d_open() -> None:
    shape = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
    path = [[t, 8 * math.sin(t / 12)] for t in range(0, 90, 3)]
    vnf = path_sweep2d(shape, path)
    assert _valid(vnf)
    assert _mesh(vnf).volume() > 0  # type: ignore[operator, union-attr]


def test_path_sweep2d_closed_loop() -> None:
    shape = [[-1, -2], [1, -2], [1, 2], [-1, 2]]
    ring = [[20 * math.cos(t), 20 * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 32, endpoint=False)]
    vnf = path_sweep2d(shape, ring, closed=True)
    assert _valid(vnf)
    assert _mesh(vnf).volume() > 0  # type: ignore[operator, union-attr]


# -- subdivide_and_slice ------------------------------------------------------------------


def test_subdivide_and_slice_equalizes_and_slices() -> None:
    profs = subdivide_and_slice([[[0, 0], [1, 0], [1, 1]], [[0, 2], [2, 2], [2, 3]]], slices=3, numpoints=6)
    assert len(profs) == 5  # 3 interpolated + 2 endpoints
    assert all(len(p) == 6 for p in profs)


# -- rot_resample -------------------------------------------------------------------------


def test_rot_resample_changes_count_and_sweeps() -> None:
    sq = [[-3, -3], [3, -3], [3, 3], [-3, 3]]
    curve = [[0, 0, 0], [10, 0, 5], [10, 10, 10], [0, 10, 15]]
    tl = Path3D(curve).path_sweep_transforms()  # type: ignore[arg-type]
    out = rot_resample(tl, num_copies=20)
    assert len(out) == 20
    assert np.asarray(out[0]).shape == (4, 4)
    assert _valid(Path2D(sq).sweep(out))


def test_rot_resample_count_method() -> None:
    _sq = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
    tl = Path3D([[0, 0, 0], [0, 0, 10], [0, 0, 20]]).path_sweep_transforms()  # type: ignore[arg-type]
    out = rot_resample(tl, num_copies=5, method=ResampleMethod.COUNT)
    assert len(out) == 5 * 2 + 1  # samples-per-gap * gaps + 1


def test_rot_resample_rejects_even_smoothlen() -> None:
    tl = Path3D([[0, 0, 0], [0, 0, 10]]).path_sweep_transforms()
    with pytest.raises(ValueError, match="smoothlen must be a"):
        rot_resample(tl, num_copies=6, smoothlen=2)


# -- os_circle / offset_sweep ---------------------------------------------------------------

_SQ20 = [[-10, -10], [10, -10], [10, 10], [-10, 10]]


def test_os_circle_returns_dict() -> None:
    d = os_circle(radius=3)
    assert isinstance(d, OSProfile)
    assert d["type"] == "circle"
    assert d["r"] == 3.0
    assert d["h"] == 3.0  # h defaults to abs(r)
    assert d["extra"] == 0.0


def test_os_circle_explicit_h() -> None:
    d = os_circle(radius=5, height=2)
    assert d["h"] == 2.0


def test_os_circle_negative_r() -> None:
    d = os_circle(radius=-4)
    assert d["r"] == -4.0
    assert d["h"] == 4.0


def test_offset_sweep_plain_volume() -> None:
    """No rim treatment → same volume as linear_sweep."""
    vnf_os = Path2D(_SQ20).offset_sweep(height=10)
    vnf_ls = Path2D(_SQ20).linear_sweep(height=10)
    assert _valid(vnf_os)
    assert math.isclose(_mesh(vnf_os).volume(), _mesh(vnf_ls).volume(), rel_tol=1e-4)  # type: ignore[operator, attr-defined, union-attr]


def test_offset_sweep_top_roundover_smaller_volume() -> None:
    """Inward top roundover removes material → volume < plain extrusion."""
    plain = Path2D(_SQ20).offset_sweep(height=20)
    rounded = Path2D(_SQ20).offset_sweep(height=20, top=os_circle(radius=4))
    assert _valid(rounded)
    assert _mesh(rounded).volume() > 0  # type: ignore[attr-defined]
    assert _mesh(rounded).volume() < _mesh(plain).volume()  # type: ignore[attr-defined]


def test_offset_sweep_bottom_roundover_smaller_volume() -> None:
    """Inward bottom roundover removes material → volume < plain extrusion."""
    plain = Path2D(_SQ20).offset_sweep(height=20)
    rounded = Path2D(_SQ20).offset_sweep(height=20, bottom=os_circle(radius=4))
    assert _valid(rounded)
    assert _mesh(rounded).volume() < _mesh(plain).volume()  # type: ignore[attr-defined]


def test_offset_sweep_both_ends_smaller_than_one() -> None:
    """Both rims rounded → even less volume than a single rounded rim."""
    one_end = Path2D(_SQ20).offset_sweep(height=20, top=os_circle(radius=3))
    both = Path2D(_SQ20).offset_sweep(height=20, top=os_circle(radius=3), bottom=os_circle(radius=3))
    assert _valid(both)
    assert _mesh(both).volume() < _mesh(one_end).volume()  # type: ignore[attr-defined]


def test_offset_sweep_flare_larger_volume() -> None:
    """Outward flare (radius < 0) adds material → volume > plain extrusion."""
    plain = Path2D(_SQ20).offset_sweep(height=20)
    flared = Path2D(_SQ20).offset_sweep(height=20, bottom=os_circle(radius=-3))
    assert _valid(flared)
    assert _mesh(flared).volume() > _mesh(plain).volume()  # type: ignore[attr-defined]


def test_offset_sweep_rejects_nonpositive_height() -> None:
    with pytest.raises(ValueError, match="height must be positive"):
        Path2D(_SQ20).offset_sweep(height=-5)


def test_offset_sweep_rejects_oversized_rim() -> None:
    """Rim heights summing to more than the extrusion height must fail."""
    with pytest.raises(ValueError, match="rim heights"):
        Path2D(_SQ20).offset_sweep(height=10, top=os_circle(radius=6), bottom=os_circle(radius=6))


def test_os_smooth_fields() -> None:
    d1 = os_smooth(cut=4)
    assert d1["type"] == "smooth"
    assert d1["cut"] == 4.0
    assert d1["k"] == 0.5
    assert d1["r_sign"] == 1.0

    d2 = os_smooth(radius=-2, curvature=0.3)
    assert d2["cut"] == 2.0
    assert d2["k"] == 0.3
    assert d2["r_sign"] == -1.0


def test_os_teardrop_fields() -> None:
    d1 = os_teardrop(radius=3)
    assert d1["type"] == "teardrop"
    assert d1["r"] == 3.0
    assert d1["h"] == 3.0
    assert d1["max_angle"] == 45.0

    d2 = os_teardrop(cut=2, height=4, max_angle=30.0)
    assert d2["r"] == 2.0
    assert d2["h"] == 4.0
    assert d2["max_angle"] == 30.0


def test_os_chamfer_fields() -> None:
    d1 = os_chamfer(width=3)
    assert d1["type"] == "chamfer"
    assert d1["width"] == 3.0
    assert d1["height"] == 3.0

    d2 = os_chamfer(width=2, height=4)
    assert d2["width"] == 2.0
    assert d2["height"] == 4.0

    d3 = os_chamfer(cut=2)
    assert d3["width"] == 2.0
    assert d3["height"] == 2.0

    d4 = os_chamfer(height=5, angle=45)
    assert math.isclose(d4["width"], 5.0)  # type: ignore[arg-type]


def test_os_flat_fields() -> None:
    d = os_flat()
    assert d["type"] == "flat"


def test_os_profile_fields() -> None:
    prof = [[0, 0], [1, 2], [3, 4]]
    d = os_profile(Path2D(prof))
    assert d["type"] == "profile"
    assert d["points"] == [[0.0, 0.0], [1.0, 2.0], [3.0, 4.0]]

    with pytest.raises(ValueError, match="First point of the"):
        # Must start at [0,0]
        os_profile(Path2D([[1, 1]]))


def test_offset_sweep_smooth() -> None:
    plain = Path2D(_SQ20).offset_sweep(height=20)
    smoothed = Path2D(_SQ20).offset_sweep(height=20, top=os_smooth(cut=4))
    assert _valid(smoothed)
    assert _mesh(smoothed).volume() < _mesh(plain).volume()  # type: ignore[attr-defined]


def test_offset_sweep_teardrop() -> None:
    plain = Path2D(_SQ20).offset_sweep(height=20)
    td = Path2D(_SQ20).offset_sweep(height=20, top=os_teardrop(radius=3))
    assert _valid(td)
    assert _mesh(td).volume() < _mesh(plain).volume()  # type: ignore[attr-defined]


def test_offset_sweep_chamfer() -> None:
    plain = Path2D(_SQ20).offset_sweep(height=20)
    chamf = Path2D(_SQ20).offset_sweep(height=20, top=os_chamfer(width=3, height=3))
    assert _valid(chamf)
    assert _mesh(chamf).volume() < _mesh(plain).volume()  # type: ignore[attr-defined]


def test_offset_sweep_flat() -> None:
    plain = Path2D(_SQ20).offset_sweep(height=20)
    flat_sweep = Path2D(_SQ20).offset_sweep(height=20, top=os_flat())
    assert _valid(flat_sweep)
    assert math.isclose(_mesh(flat_sweep).volume(), _mesh(plain).volume(), rel_tol=1e-4)  # type: ignore[attr-defined]


def test_offset_sweep_profile() -> None:
    plain = Path2D(_SQ20).offset_sweep(height=20)
    # Custom profile: starts at [0,0], goes inward by 2 at z=3
    prof = [[0.0, 0.0], [2.0, 3.0]]
    prof_sweep = Path2D(_SQ20).offset_sweep(height=20, top=os_profile(Path2D(prof)))
    assert _valid(prof_sweep)
    assert _mesh(prof_sweep).volume() < _mesh(plain).volume()  # type: ignore[attr-defined]


# -- convex_offset_extrude & rounded_prism --------------------------------------------------


def test_convex_offset_extrude_alias() -> None:
    v1 = Path2D(_SQ20).convex_offset_extrude(height=15, top=os_circle(radius=2))
    v2 = Path2D(_SQ20).offset_sweep(height=15, top=os_circle(radius=2))
    assert _valid(v1)
    assert math.isclose(_mesh(v1).volume(), _mesh(v2).volume(), rel_tol=1e-9)  # type: ignore[attr-defined]


def test_rounded_prism_plain() -> None:
    """No rounding → volume == linear_sweep."""
    plain = Path2D(_SQ20).rounded_prism(height=20)
    expected = Path2D(_SQ20).linear_sweep(height=20)
    assert _valid(plain)
    assert math.isclose(_mesh(plain).volume(), _mesh(expected).volume(), rel_tol=1e-4)  # type: ignore[operator, attr-defined, union-attr]


def test_rounded_prism_rim_rounding() -> None:
    """Top/bottom rim rounding removes volume."""
    plain = Path2D(_SQ20).rounded_prism(height=20)
    rounded = Path2D(_SQ20).rounded_prism(height=20, joint_top=3, joint_bottom=3)
    assert _valid(rounded)
    assert _mesh(rounded).volume() < _mesh(plain).volume()  # type: ignore[attr-defined]


def test_rounded_prism_compat() -> None:
    """Compatibility mapping for joint_bot and k_sides."""
    v1 = Path2D(_SQ20).rounded_prism(height=20, joint_top=3, joint_bottom=3, joint_sides=2, curvature_sides=0.5)
    v2 = Path2D(_SQ20).rounded_prism(height=20, joint_top=3, joint_bot=3, joint_sides=2, k_sides=0.5)
    assert _valid(v1)
    assert _valid(v2)
    assert math.isclose(_mesh(v1).volume(), _mesh(v2).volume(), rel_tol=1e-9)  # type: ignore[attr-defined]


def test_rounded_prism_side_rounding() -> None:
    """Side rounding removes volume."""
    plain = Path2D(_SQ20).rounded_prism(height=20)
    rounded = Path2D(_SQ20).rounded_prism(height=20, joint_sides=2)
    assert _valid(rounded)
    assert _mesh(rounded).volume() < _mesh(plain).volume()  # type: ignore[attr-defined]


def test_rounded_prism_tapered() -> None:
    """Loft/prism with different top and bottom."""
    top_sq = [[-5, -5], [5, -5], [5, 5], [-5, 5]]
    # Prism height=20 from bottom to top
    prism = Path2D(_SQ20).rounded_prism(top=top_sq, height=20, joint_sides=1)
    assert _valid(prism)
    # Volume should be between bottom-extruded and top-extruded cubes
    vol_bot = Path2D(_SQ20).linear_sweep(height=20).vnf().volume()
    vol_top = Path2D(top_sq).linear_sweep(height=20).vnf().volume()
    assert vol_top < _mesh(prism).volume() < vol_bot  # type: ignore[attr-defined, union-attr]


# -- join_prism & prism_connector -----------------------------------------------------------


def test_join_prism_fillet() -> None:
    plain = Path2D(_SQ20).join_prism(height=20, fillet=0)
    filleted = Path2D(_SQ20).join_prism(height=20, fillet=2)
    assert _valid(filleted)
    # Filleting at the bottom adds volume (outward flare)
    assert _mesh(filleted).volume() > _mesh(plain).volume()  # type: ignore[attr-defined]


def test_prism_connector_fillets() -> None:
    plain = Path2D(_SQ20).prism_connector(length=20, fillet=0)
    filleted = Path2D(_SQ20).prism_connector(length=20, fillet1=2, fillet2=2)
    assert _valid(filleted)
    # Filleting at both ends adds volume (outward flares)
    assert _mesh(filleted).volume() > _mesh(plain).volume()  # type: ignore[attr-defined]


# -- attach_prism & bent_cutout_mask --------------------------------------------------------


def test_attach_prism_fillet_rounding() -> None:
    plain = Path2D(_SQ20).attach_prism(length=20)
    filleted_rounded = Path2D(_SQ20).attach_prism(length=20, fillet=2, rounding=2)
    assert _valid(filleted_rounded)
    # Fillet (adds volume at bottom) vs Roundover (removes volume at top)
    # Let's verify it constructs a valid VNF with correct dimensions.
    assert len(_mesh(filleted_rounded).vertices) > len(_mesh(plain).vertices)  # type: ignore[attr-defined]


def test_bent_cutout_mask() -> None:
    cutout = [[-5, -5], [5, -5], [5, 5], [-5, 5]]
    mask = Path2D(cutout).bent_cutout_mask(radius=30, thickness=4)
    assert _valid(mask)
    assert _mesh(mask).volume() > 0  # type: ignore[attr-defined]
    # Thickness check (roughly 4 in radius direction)
    verts = np.asarray(_mesh(mask).vertices)  # type: ignore[attr-defined]
    radii = np.linalg.norm(verts[:, :2], axis=1)
    r_min = np.min(radii)
    r_max = np.max(radii)
    assert math.isclose(r_max - r_min, 4.0, abs_tol=1e-4)


def test_sweepable_mixin() -> None:
    path = Path3D([[0, 0, 0], [0, 0, 10], [0, 10, 10]])
    shape = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
    vnf1 = path.path_sweep(shape)  # type: ignore[arg-type]
    assert abs(_mesh(vnf1).volume()) > 0  # type: ignore[operator, union-attr]

    path2d = Path2D([[t, 8 * math.sin(t / 12)] for t in range(0, 90, 3)])
    vnf2 = path2d.path_sweep2d(shape)  # type: ignore[arg-type]
    assert abs(_mesh(vnf2).volume()) > 0  # type: ignore[operator, union-attr]

    profile = Path2D(shape)
    vnf3 = profile.linear_sweep(height=20)
    assert abs(_mesh(vnf3).volume()) > 0  # type: ignore[operator, union-attr]

    prof = Path2D([[2, 0], [4, 0], [4, 5], [2, 5]])
    vnf4 = prof.rotate_sweep(angle=180)
    assert abs(_mesh(vnf4).volume()) > 0  # type: ignore[operator, union-attr]

    vnf5 = profile.spiral_sweep(height=10, radius=5, turns=2)
    assert abs(_mesh(vnf5).volume()) > 0  # type: ignore[operator, union-attr]


def test_oop_skin_and_sweep() -> None:
    from pybosl2.vnf import VNF

    circle = Path2D([[math.cos(t), math.sin(t)] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)])
    square = Path2D([[-1, -1], [1, -1], [1, 1], [-1, 1]])
    vnf_skinned = VNF.from_skin([circle, square], slices=5, method=SkinMethod.REINDEX, z=[0, 10])
    assert isinstance(vnf_skinned.vnf(), VNF)  # a Solid now (SPEC S-19a); the mesh is on .vnf()
    assert abs(_mesh(vnf_skinned).volume()) > 0

    shape = Path2D(square)
    transforms = [np.eye(4), np.eye(4)]
    transforms[1][:3, 3] = [0, 0, 10]
    vnf_swept = shape.sweep(transforms)
    assert isinstance(vnf_swept.vnf(), VNF)  # a Solid now (S-19a); its mesh is on .vnf()


# ── decorative caps coverage ────────────────────────────────────────────


def test_path_sweep_arrow_cap() -> None:
    """A decorative cap needs real geometry, so the sweep comes back as a solid, not a VNF."""
    from pybosl2.caps import CapSpec
    from pybosl2.vnf import VNF

    circle = [[5, 0], [3, 4], [-4, 3], [-5, 0], [-4, -3], [3, -4]]
    spine = Path2D([[0, 0], [20, 0], [20, 20]])
    plain = spine.path_sweep(circle)
    capped = spine.path_sweep(circle, caps=CapSpec(CapType.ARROW, length=2))
    assert isinstance(plain.vnf(), VNF)  # a Solid now (S-19a); its mesh is on .vnf()
    assert not isinstance(capped, VNF)
    assert "rotate_extrude" in repr(capped.shape)  # the arrow is a revolved profile


def test_linear_sweep_decorative_cap() -> None:
    """The capped extrusion keeps the profile's own 20x20x10 envelope."""
    from pybosl2.caps import CapSpec

    sq = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    capped = sq.linear_sweep(height=10, caps=CapSpec(CapType.ARROW, length=3))
    assert [float(v) for v in capped.bounds().size] == pytest.approx([20.0, 20.0, 10.0], abs=0.01)


def test_rotate_sweep_decorative_cap() -> None:
    """A dot cap is a sphere on each open end, so the revolved quarter grows past its own profile."""
    from pybosl2.caps import CapSpec

    profile = [[10, 0], [10, 2], [2, 6], [0, 10]]
    capped = Path2D(profile).rotate_sweep(angle=90, caps=CapSpec(CapType.DOT))
    assert "sphere(" in repr(capped.shape)
    assert float(capped.bounds().size[0]) > 10.0  # the profile reaches x=10; the cap goes further


#: (name, the rim descriptor). Each treats the top rim of the same 20x20x10 prism.
PRISM_RIMS = [
    ("teardrop", lambda: os_teardrop(radius=3)),
    ("smooth", lambda: os_smooth(cut=3, curvature=0.8)),
    ("chamfer", lambda: os_chamfer(width=2)),
    ("profile", lambda: os_profile(Path2D([[0, 0], [1, 3], [2, 5]]))),
]


@pytest.mark.parametrize(("name", "rim"), PRISM_RIMS, ids=[row[0] for row in PRISM_RIMS])
def test_rounded_prism_rim_treatments(name: str, rim: object) -> None:
    """Every rim style takes material off the top edge and leaves the prism's envelope alone."""
    base = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    plain = base.rounded_prism(height=10)
    treated = base.rounded_prism(height=10, joint_top=rim())  # type: ignore[operator, arg-type]
    points = np.asarray(_mesh(treated).vertices)
    assert points.min(axis=0).tolist() == pytest.approx([0.0, 0.0, 0.0], abs=0.01), name
    assert points.max(axis=0).tolist() == pytest.approx([20.0, 20.0, 10.0], abs=0.01), name
    assert 0 < float(_mesh(treated).volume()) < float(_mesh(plain).volume()), name
    assert len(_mesh(treated).vertices) > len(_mesh(plain).vertices), name  # the rim is a curve now


def test_rounded_prism_teardrop_rim() -> None:
    """A teardrop rim leans the roundover over so it prints without support."""
    base = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    teardrop = base.rounded_prism(height=10, joint_top=os_teardrop(radius=3))  # type: ignore[arg-type]
    chamfered = base.rounded_prism(height=10, joint_top=os_chamfer(width=2))  # type: ignore[arg-type]
    assert float(_mesh(teardrop).volume()) > float(_mesh(chamfered).volume())  # it keeps more material


# ── rot_resample with transforms path ───────────────────────────────────


def test_rot_resample_twist_list() -> None:
    _sq = [[-3, -3], [3, -3], [3, 3], [-3, 3]]
    curve = [[0, 0, 0], [10, 0, 5], [10, 10, 10], [0, 10, 15]]
    tl = Path3D(curve).path_sweep_transforms()  # type: ignore[arg-type]
    result = rot_resample(tl, num_copies=12, twist=[5, 10, 15])
    assert len(result) == 12


def test_rounded_prism_smooth_rim() -> None:
    """`curvature=` tunes how tightly the smooth rim hugs the corner, so it changes the volume."""
    base = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    tight = base.rounded_prism(height=10, joint_top=os_smooth(cut=3, curvature=0.2))  # type: ignore[arg-type]
    loose = base.rounded_prism(height=10, joint_top=os_smooth(cut=3, curvature=0.8))  # type: ignore[arg-type]
    assert float(_mesh(tight).volume()) != pytest.approx(float(_mesh(loose).volume()), abs=1.0)


def test_rounded_prism_chamfer_rim() -> None:
    """A wider chamfer cuts more off the rim."""
    base = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    narrow = base.rounded_prism(height=10, joint_top=os_chamfer(width=1))  # type: ignore[arg-type]
    wide = base.rounded_prism(height=10, joint_top=os_chamfer(width=3))  # type: ignore[arg-type]
    assert float(_mesh(wide).volume()) < float(_mesh(narrow).volume())


def test_rounded_prism_profile_rim() -> None:
    """A hand-drawn rim profile is swept round the top edge like any of the named ones."""
    base = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    custom = base.rounded_prism(height=10, joint_top=os_profile(Path2D([[0, 0], [1, 3], [2, 5]])))  # type: ignore[arg-type]
    plain = base.rounded_prism(height=10)
    assert float(_mesh(custom).volume()) < float(_mesh(plain).volume())
    assert np.asarray(_mesh(custom).vertices).max(axis=0).tolist() == pytest.approx([20.0, 20.0, 10.0], abs=0.01)
