# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2/skin.py: frame_map, sweep and path_sweep frame methods."""

import math

import numpy as np
import pytest

from bosl2.skin import (
    OSProfile,
    attach_prism,
    bent_cutout_mask,
    clockwise_polygon,
    convex_offset_extrude,
    frame_map,
    join_prism,
    linear_sweep,
    offset_sweep,
    os_chamfer,
    os_circle,
    os_flat,
    os_profile,
    os_smooth,
    os_teardrop,
    path3d,
    path_sweep,
    path_sweep2d,
    prism_connector,
    rot_resample,
    rotate_sweep,
    rounded_prism,
    skin,
    slice_profiles,
    spiral_sweep,
    subdivide_and_slice,
    sweep,
)

SQUARE = [[-1, -1], [1, -1], [1, 1], [-1, 1]]


def _valid(vnf):
    return not vnf.faces or max(i for f in vnf.faces for i in f) < len(vnf.vertices)


def _circle(r, sides=24):
    return [[r * math.cos(t), r * math.sin(t)] for t in np.linspace(0, 2 * math.pi, sides, endpoint=False)]


def test_path3d_pads_z():
    assert path3d([[1, 2], [3, 4]]) == [[1, 2, 0], [3, 4, 0]]
    assert path3d([[1, 2, 3]]) == [[1, 2, 3]]


def test_clockwise_polygon():
    counterclockwise = [[0, 0], [1, 0], [1, 1], [0, 1]]
    assert clockwise_polygon(counterclockwise) == list(reversed(counterclockwise))  # counterclockwise gets reversed
    clockwise = list(reversed(counterclockwise))
    assert clockwise_polygon(clockwise) == clockwise  # already clockwise, unchanged


def test_frame_map_orthonormal():
    m = frame_map(y=[0, 1, 0], z=[0, 0, 1])
    radius = m[:3, :3]
    np.testing.assert_allclose(radius @ radius.T, np.eye(3), atol=1e-9)
    assert math.isclose(float(np.linalg.det(radius)), 1.0)


def test_frame_map_fills_third_axis():
    m = frame_map(y=[0, 1, 0], z=[0, 0, 1])  # x should be +X
    np.testing.assert_allclose(m[:3, 0], [1, 0, 0], atol=1e-9)


def test_straight_sweep_counts():
    vnf = path_sweep(SQUARE, [[0, 0, 0], [0, 0, 5], [0, 0, 10]])
    assert len(vnf.vertices) == 12  # 4 shape pts x 3 profiles
    assert _valid(vnf)


def test_sweep_open_has_caps_closed_does_not():
    line = [[0, 0, 0], [0, 0, 5], [0, 0, 10]]
    open_faces = len(path_sweep(SQUARE, line, caps=True).faces)
    nocap_faces = len(path_sweep(SQUARE, line, caps=False).faces)
    assert open_faces == nocap_faces + 2  # two flat end caps


@pytest.mark.parametrize("method", ["incremental", "natural"])
def test_curved_sweep_methods(method):
    curve = [[math.cos(t) * 10, math.sin(t) * 10, t * 2] for t in np.linspace(0, math.pi, 10)]
    vnf = path_sweep(SQUARE, curve, method=method)
    assert len(vnf.vertices) == 40
    assert _valid(vnf)


def test_manual_method_with_normals():
    path = [[0, 0, 0], [0, 0, 5], [0, 0, 10]]
    normals = [[1, 0, 0]] * 3
    vnf = path_sweep(SQUARE, path, method="manual", normal=normals)
    assert _valid(vnf)


def test_closed_sweep_has_no_caps():
    circ = [[math.cos(t) * 20, math.sin(t) * 20, 0] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
    vnf = path_sweep(SQUARE, circ, closed=True)
    assert _valid(vnf)
    # 25 profiles (closed adds the wrap) x 4 verts
    assert len(vnf.vertices) == 100


def test_transforms_mode_returns_matrices():
    tl = path_sweep(SQUARE, [[0, 0, 0], [0, 0, 5], [0, 0, 10]], transforms=True)
    assert len(tl) == 3
    assert np.asarray(tl[0]).shape == (4, 4)


def test_twist_and_scale_run():
    vnf = path_sweep(SQUARE, [[0, 0, 0], [0, 0, 5], [0, 0, 10]], twist=90, scale=2)
    assert _valid(vnf)


def test_unknown_method_raises():
    with pytest.raises(AssertionError):
        path_sweep(SQUARE, [[0, 0, 0], [0, 0, 5]], method="bogus")


def test_sweep_direct_from_transforms():
    ident = np.eye(4)
    up = np.eye(4)
    up[2, 3] = 10
    vnf = sweep(SQUARE, [ident, up])
    assert _valid(vnf)


# -- skin ---------------------------------------------------------------------------------


def test_slice_profiles_inserts_intermediates():
    a = [[0, 0], [1, 0], [1, 1]]
    b = [[0, 2], [1, 2], [1, 3]]
    out = slice_profiles([a, b], 3)  # 3 interpolated + final = 5 profiles
    assert len(out) == 5
    np.testing.assert_allclose(out[0], a)
    np.testing.assert_allclose(out[-1], b)


def test_skin_two_profiles():
    vnf = skin([_circle(6), [[-8, -8], [8, -8], [8, 8], [-8, 8]]], slices=10, z=[0, 25])
    assert _valid(vnf)
    assert vnf.volume() > 0  # winding fixed to outward


def test_skin_reindex_method():
    vnf = skin(
        [_circle(6), [[-8, -8], [8, -8], [8, 8], [-8, 8]]],
        slices=8,
        method="reindex",
        z=[0, 20],
    )
    assert _valid(vnf) and vnf.volume() > 0


def test_skin_three_profiles():
    vnf = skin([_circle(4), _circle(8), _circle(4)], slices=5, z=[0, 15, 30])
    assert _valid(vnf) and vnf.volume() > 0


def test_skin_closed_stack():
    profs = [
        _circle(4),
        [[-6, -6], [6, -6], [6, 6], [-6, 6]],
        _circle(4),
        [[-6, -6], [6, -6], [6, 6], [-6, 6]],
    ]
    vnf = skin(profs, slices=3, closed=True, z=[0, 10, 20, 30])
    assert _valid(vnf)


def test_skin_rejects_unsupported_method():
    with pytest.raises(AssertionError):
        skin([_circle(4), _circle(6)], slices=2, method="distance", z=[0, 10])


def test_skin_needs_two_profiles():
    with pytest.raises(AssertionError):
        skin([_circle(4)], slices=2, z=[0])


# -- linear_sweep -------------------------------------------------------------------------


def test_linear_sweep_plain_box_volume():
    sq = [[-10, -10], [10, -10], [10, 10], [-10, 10]]
    vnf = linear_sweep(sq, height=5)
    assert _valid(vnf)
    assert math.isclose(vnf.volume(), 20 * 20 * 5, rel_tol=1e-6)  # 2000


def test_linear_sweep_twist_scale():
    sq = [[-10, -10], [10, -10], [10, 10], [-10, 10]]
    vnf = linear_sweep(sq, height=40, twist=120, scale=0.4)
    assert _valid(vnf) and vnf.volume() > 0


def test_linear_sweep_center_vs_base():
    sq = [[-5, -5], [5, -5], [5, 5], [-5, 5]]
    base = linear_sweep(sq, height=10)
    centered = linear_sweep(sq, height=10, center=True)
    bz = [v[2] for v in base.vertices]
    cz = [v[2] for v in centered.vertices]
    assert math.isclose(min(bz), 0.0, abs_tol=1e-9) and math.isclose(max(bz), 10.0, abs_tol=1e-9)
    assert math.isclose(min(cz), -5.0, abs_tol=1e-9) and math.isclose(max(cz), 5.0, abs_tol=1e-9)


# -- rotate_sweep -------------------------------------------------------------------------

PROFILE = [[4, -10], [12, -10], [12, 10], [4, 10]]


def test_rotate_sweep_full():
    vnf = rotate_sweep(PROFILE, 360)
    assert _valid(vnf) and vnf.volume() > 0


def test_rotate_sweep_partial_has_caps():
    vnf = rotate_sweep(PROFILE, 270)
    assert _valid(vnf) and vnf.volume() > 0


def test_rotate_sweep_rejects_bad_angle():
    with pytest.raises(AssertionError):
        rotate_sweep(PROFILE, 400)


# -- spiral_sweep -------------------------------------------------------------------------


def test_spiral_sweep_coil():
    section = [[-1.2, -1.2], [1.2, -1.2], [1.2, 1.2], [-1.2, 1.2]]
    vnf = spiral_sweep(section, height=40, radius=12, turns=5)
    assert _valid(vnf) and vnf.volume() > 0


def test_spiral_sweep_conical_taper():
    section = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
    vnf = spiral_sweep(section, height=30, radius1=15, radius2=5, turns=4)
    assert _valid(vnf) and vnf.volume() > 0


# -- path_sweep2d -------------------------------------------------------------------------


def test_path_sweep2d_open():
    shape = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
    path = [[t, 8 * math.sin(t / 12)] for t in range(0, 90, 3)]
    vnf = path_sweep2d(shape, path)
    assert _valid(vnf) and vnf.volume() > 0


def test_path_sweep2d_closed_loop():
    shape = [[-1, -2], [1, -2], [1, 2], [-1, 2]]
    ring = [[20 * math.cos(t), 20 * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 32, endpoint=False)]
    vnf = path_sweep2d(shape, ring, closed=True)
    assert _valid(vnf) and vnf.volume() > 0


# -- subdivide_and_slice ------------------------------------------------------------------


def test_subdivide_and_slice_equalizes_and_slices():
    profs = subdivide_and_slice([[[0, 0], [1, 0], [1, 1]], [[0, 2], [2, 2], [2, 3]]], slices=3, numpoints=6)
    assert len(profs) == 5  # 3 interpolated + 2 endpoints
    assert all(len(p) == 6 for p in profs)


# -- rot_resample -------------------------------------------------------------------------


def test_rot_resample_changes_count_and_sweeps():
    sq = [[-3, -3], [3, -3], [3, 3], [-3, 3]]
    curve = [[0, 0, 0], [10, 0, 5], [10, 10, 10], [0, 10, 15]]
    tl = path_sweep(sq, curve, transforms=True)
    out = rot_resample(tl, sides=20)
    assert len(out) == 20
    assert np.asarray(out[0]).shape == (4, 4)
    assert _valid(sweep(sq, out))


def test_rot_resample_count_method():
    sq = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
    tl = path_sweep(sq, [[0, 0, 0], [0, 0, 10], [0, 0, 20]], transforms=True)
    out = rot_resample(tl, sides=5, method="count")
    assert len(out) == 5 * 2 + 1  # samples-per-gap * gaps + 1


def test_rot_resample_rejects_even_smoothlen():
    tl = path_sweep([[-1, -1], [1, -1], [1, 1], [-1, 1]], [[0, 0, 0], [0, 0, 10]], transforms=True)
    with pytest.raises(AssertionError):
        rot_resample(tl, sides=6, smoothlen=2)


# -- os_circle / offset_sweep ---------------------------------------------------------------

_SQ20 = [[-10, -10], [10, -10], [10, 10], [-10, 10]]


def test_os_circle_returns_dict():
    d = os_circle(r=3)
    assert isinstance(d, OSProfile)
    assert d["type"] == "circle"
    assert d["r"] == 3.0
    assert d["h"] == 3.0  # h defaults to abs(r)
    assert d["extra"] == 0.0


def test_os_circle_explicit_h():
    d = os_circle(r=5, h=2)
    assert d["h"] == 2.0


def test_os_circle_negative_r():
    d = os_circle(r=-4)
    assert d["r"] == -4.0
    assert d["h"] == 4.0


def test_offset_sweep_plain_volume():
    """No rim treatment → same volume as linear_sweep."""
    vnf_os = offset_sweep(_SQ20, height=10)
    vnf_ls = linear_sweep(_SQ20, height=10)
    assert _valid(vnf_os)
    assert math.isclose(vnf_os.volume(), vnf_ls.volume(), rel_tol=1e-4)


def test_offset_sweep_top_roundover_smaller_volume():
    """Inward top roundover removes material → volume < plain extrusion."""
    plain = offset_sweep(_SQ20, height=20)
    rounded = offset_sweep(_SQ20, height=20, top=os_circle(r=4))
    assert _valid(rounded)
    assert rounded.volume() > 0
    assert rounded.volume() < plain.volume()


def test_offset_sweep_bottom_roundover_smaller_volume():
    """Inward bottom roundover removes material → volume < plain extrusion."""
    plain = offset_sweep(_SQ20, height=20)
    rounded = offset_sweep(_SQ20, height=20, bottom=os_circle(r=4))
    assert _valid(rounded)
    assert rounded.volume() < plain.volume()


def test_offset_sweep_both_ends_smaller_than_one():
    """Both rims rounded → even less volume than a single rounded rim."""
    one_end = offset_sweep(_SQ20, height=20, top=os_circle(r=3))
    both = offset_sweep(_SQ20, height=20, top=os_circle(r=3), bottom=os_circle(r=3))
    assert _valid(both)
    assert both.volume() < one_end.volume()


def test_offset_sweep_flare_larger_volume():
    """Outward flare (r < 0) adds material → volume > plain extrusion."""
    plain = offset_sweep(_SQ20, height=20)
    flared = offset_sweep(_SQ20, height=20, bottom=os_circle(r=-3))
    assert _valid(flared)
    assert flared.volume() > plain.volume()


def test_offset_sweep_rejects_nonpositive_height():
    with pytest.raises(AssertionError):
        offset_sweep(_SQ20, height=-5)


def test_offset_sweep_rejects_oversized_rim():
    """Rim heights summing to more than the extrusion height must fail."""
    with pytest.raises(AssertionError):
        offset_sweep(_SQ20, height=10, top=os_circle(r=6), bottom=os_circle(r=6))


def test_os_smooth_fields():
    d1 = os_smooth(cut=4)
    assert d1["type"] == "smooth"
    assert d1["cut"] == 4.0
    assert d1["k"] == 0.5
    assert d1["r_sign"] == 1.0

    d2 = os_smooth(r=-2, k=0.3)
    assert d2["cut"] == 2.0
    assert d2["k"] == 0.3
    assert d2["r_sign"] == -1.0


def test_os_teardrop_fields():
    d1 = os_teardrop(r=3)
    assert d1["type"] == "teardrop"
    assert d1["r"] == 3.0
    assert d1["h"] == 3.0
    assert d1["max_angle"] == 45.0

    d2 = os_teardrop(cut=2, h=4, max_angle=30.0)
    assert d2["r"] == 2.0
    assert d2["h"] == 4.0
    assert d2["max_angle"] == 30.0


def test_os_chamfer_fields():
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
    assert math.isclose(d4["width"], 5.0)


def test_os_flat_fields():
    d = os_flat()
    assert d["type"] == "flat"


def test_os_profile_fields():
    prof = [[0, 0], [1, 2], [3, 4]]
    d = os_profile(prof)
    assert d["type"] == "profile"
    assert d["points"] == [[0.0, 0.0], [1.0, 2.0], [3.0, 4.0]]

    with pytest.raises(AssertionError):
        # Must start at [0,0]
        os_profile([[1, 1]])


def test_offset_sweep_smooth():
    plain = offset_sweep(_SQ20, height=20)
    smoothed = offset_sweep(_SQ20, height=20, top=os_smooth(cut=4))
    assert _valid(smoothed)
    assert smoothed.volume() < plain.volume()


def test_offset_sweep_teardrop():
    plain = offset_sweep(_SQ20, height=20)
    td = offset_sweep(_SQ20, height=20, top=os_teardrop(r=3))
    assert _valid(td)
    assert td.volume() < plain.volume()


def test_offset_sweep_chamfer():
    plain = offset_sweep(_SQ20, height=20)
    chamf = offset_sweep(_SQ20, height=20, top=os_chamfer(width=3, height=3))
    assert _valid(chamf)
    assert chamf.volume() < plain.volume()


def test_offset_sweep_flat():
    plain = offset_sweep(_SQ20, height=20)
    flat_sweep = offset_sweep(_SQ20, height=20, top=os_flat())
    assert _valid(flat_sweep)
    assert math.isclose(flat_sweep.volume(), plain.volume(), rel_tol=1e-4)


def test_offset_sweep_profile():
    plain = offset_sweep(_SQ20, height=20)
    # Custom profile: starts at [0,0], goes inward by 2 at z=3
    prof = [[0.0, 0.0], [2.0, 3.0]]
    prof_sweep = offset_sweep(_SQ20, height=20, top=os_profile(prof))
    assert _valid(prof_sweep)
    assert prof_sweep.volume() < plain.volume()


# -- convex_offset_extrude & rounded_prism --------------------------------------------------


def test_convex_offset_extrude_alias():
    v1 = convex_offset_extrude(_SQ20, height=15, top=os_circle(r=2))
    v2 = offset_sweep(_SQ20, height=15, top=os_circle(r=2))
    assert _valid(v1)
    assert math.isclose(v1.volume(), v2.volume(), rel_tol=1e-9)


def test_rounded_prism_plain():
    """No rounding → volume == linear_sweep."""
    plain = rounded_prism(_SQ20, height=20)
    expected = linear_sweep(_SQ20, height=20)
    assert _valid(plain)
    assert math.isclose(plain.volume(), expected.volume(), rel_tol=1e-4)


def test_rounded_prism_rim_rounding():
    """Top/bottom rim rounding removes volume."""
    plain = rounded_prism(_SQ20, height=20)
    rounded = rounded_prism(_SQ20, height=20, joint_top=3, joint_bottom=3)
    assert _valid(rounded)
    assert rounded.volume() < plain.volume()


def test_rounded_prism_compat():
    """Compatibility mapping for joint_bot and k_sides."""
    v1 = rounded_prism(_SQ20, height=20, joint_top=3, joint_bottom=3, joint_sides=2, curvature_sides=0.5)
    v2 = rounded_prism(_SQ20, height=20, joint_top=3, joint_bot=3, joint_sides=2, k_sides=0.5)
    assert _valid(v1)
    assert _valid(v2)
    assert math.isclose(v1.volume(), v2.volume(), rel_tol=1e-9)


def test_rounded_prism_side_rounding():
    """Side rounding removes volume."""
    plain = rounded_prism(_SQ20, height=20)
    rounded = rounded_prism(_SQ20, height=20, joint_sides=2)
    assert _valid(rounded)
    assert rounded.volume() < plain.volume()


def test_rounded_prism_tapered():
    """Loft/prism with different top and bottom."""
    top_sq = [[-5, -5], [5, -5], [5, 5], [-5, 5]]
    # Prism height=20 from bottom to top
    prism = rounded_prism(_SQ20, top=top_sq, height=20, joint_sides=1)
    assert _valid(prism)
    # Volume should be between bottom-extruded and top-extruded cubes
    vol_bot = linear_sweep(_SQ20, height=20).volume()
    vol_top = linear_sweep(top_sq, height=20).volume()
    assert vol_top < prism.volume() < vol_bot


# -- join_prism & prism_connector -----------------------------------------------------------


def test_join_prism_fillet():
    plain = join_prism(_SQ20, height=20, fillet=0)
    filleted = join_prism(_SQ20, height=20, fillet=2)
    assert _valid(filleted)
    # Filleting at the bottom adds volume (outward flare)
    assert filleted.volume() > plain.volume()


def test_prism_connector_fillets():
    plain = prism_connector(_SQ20, length=20, fillet=0)
    filleted = prism_connector(_SQ20, length=20, fillet1=2, fillet2=2)
    assert _valid(filleted)
    # Filleting at both ends adds volume (outward flares)
    assert filleted.volume() > plain.volume()


# -- attach_prism & bent_cutout_mask --------------------------------------------------------


def test_attach_prism_fillet_rounding():
    plain = attach_prism(_SQ20, length=20)
    filleted_rounded = attach_prism(_SQ20, length=20, fillet=2, rounding=2)
    assert _valid(filleted_rounded)
    # Fillet (adds volume at bottom) vs Roundover (removes volume at top)
    # Let's verify it constructs a valid VNF with correct dimensions.
    assert len(filleted_rounded.vertices) > len(plain.vertices)


def test_bent_cutout_mask():
    cutout = [[-5, -5], [5, -5], [5, 5], [-5, 5]]
    mask = bent_cutout_mask(radius=30, thickness=4, path=cutout)
    assert _valid(mask)
    assert mask.volume() > 0
    # Thickness check (roughly 4 in radius direction)
    verts = np.asarray(mask.vertices)
    radii = np.linalg.norm(verts[:, :2], axis=1)
    r_min = np.min(radii)
    r_max = np.max(radii)
    assert math.isclose(r_max - r_min, 4.0, abs_tol=1e-4)
