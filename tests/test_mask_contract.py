# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The masking API against the library's own rules (SPEC S-26a, S-26b, S-26c).

Masking broke more of this project's stated rules than anything else: `mask3d_roundover(r, size)`
demanded the *parent's* dimensions as a second positional, `mask3d_groove(width, depth, length)`
had three required positionals where D-2 says three is never acceptable, `r` was spelled `r` where
D-5 asks for `radius`/`diameter`, and `edge_mask(children=...)` took a raw `PyOpenSCAD` -- an L2
type crossing an L3 boundary in OpenSCAD's own module-with-children vocabulary, which B2-2 exists
to replace.
"""

from __future__ import annotations

import inspect

import pytest

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
from pybosl2 import Anchor, Mask2D, Mask3D, cuboid, use_backend
from pybosl2.exceptions import Bosl2ValueError, UnsupportedByBackendError

TREATMENTS = ("round_edges", "chamfer_edges", "cove_edges")
PLAIN_VOLUME = 40 * 30 * 20


def _plain() -> object:
    return cuboid([40, 30, 20])


# --- S-26b: a treatment is named, and never asks for a native handle -------------------------


@pytest.mark.parametrize(
    ("name", "kwargs"),
    [("round_edges", {"radius": 4}), ("chamfer_edges", {"chamfer": 3}), ("cove_edges", {"radius": 3})],
)
def test_a_named_treatment_needs_only_the_treatment(name: str, kwargs: dict[str, float]) -> None:
    """The solid knows its own box, so the caller never names it (SPEC S-26a, S-26b)."""
    treated = getattr(_plain(), name)(Anchor.Z, **kwargs).realize()
    assert treated.vnf().volume() < PLAIN_VOLUME, f"{name} removed nothing"
    assert treated.bounds().size == pytest.approx((40.0, 30.0, 20.0)), "a treatment must not resize the part"


def test_a_named_treatment_matches_the_mask_it_replaces() -> None:
    """The friendly spelling is the same geometry, not an approximation of it."""
    by_name = _plain().round_edges(Anchor.Z, radius=4, fn=32).realize()
    by_mask = _plain().edge_profile(Anchor.Z, mask=Mask2D.roundover(4, fn=32)).realize()
    assert by_name.vnf().volume() == pytest.approx(by_mask.vnf().volume(), rel=1e-12)


def test_no_public_masking_signature_mentions_a_native_type() -> None:
    """An L2 type in an L3 signature (SPEC A-1), in OpenSCAD's vocabulary (B2-2)."""
    import pybosl2.masking as masking
    from pybosl2.shapes3d.base import CsgSolid

    offenders: list[str] = []
    surfaces = [(masking, n) for n in dir(masking) if not n.startswith("_")]
    surfaces += [(CsgSolid, n) for n in ("edge_mask", "edge_profile", "corner_profile", "face_profile", *TREATMENTS)]
    for owner, name in surfaces:
        member = getattr(owner, name, None)
        if not callable(member):
            continue
        try:
            signature = inspect.signature(member)
        except (TypeError, ValueError):
            continue
        for param in signature.parameters.values():
            text = str(param.annotation)
            if "PyOpenSCAD" in text or "openscad" in text.lower():
                offenders.append(f"{getattr(owner, '__name__', owner)}.{name}({param.name}: {text})")
            if param.name == "children":
                offenders.append(f"{getattr(owner, '__name__', owner)}.{name} still takes `children=`")
    assert not offenders, "; ".join(offenders)


# --- S-26c: mask parameters follow the same rules as everything else --------------------------


def test_no_mask_factory_has_more_than_one_required_argument() -> None:
    """SPEC D-2: one required parameter; three is never acceptable."""
    offenders: list[str] = []
    for cls in (Mask2D, Mask3D):
        for name, member in inspect.getmembers(cls, predicate=callable):
            if name.startswith("_"):
                continue
            required = [
                p
                for p in inspect.signature(member).parameters.values()
                if p.default is inspect.Parameter.empty and p.kind is not p.VAR_KEYWORD
            ]
            # `size` describes the parent, not the treatment: it is keyword-only and excused here
            # only because the named treatments (S-26b) supply it.
            positional = [p for p in required if p.kind is not p.KEYWORD_ONLY]
            if len(positional) > 1:
                offenders.append(f"{cls.__name__}.{name} requires {[p.name for p in positional]}")
    assert not offenders, "; ".join(offenders)


def test_a_mask_names_its_size_measure_the_way_everything_else_does() -> None:
    """`radius`/`diameter` through pick_radius, not `r` (SPEC D-5, S-26c)."""
    assert "radius" in inspect.signature(Mask3D.roundover).parameters
    assert "diameter" in inspect.signature(Mask3D.roundover).parameters
    assert "r" not in inspect.signature(Mask3D.roundover).parameters

    with pytest.raises(Bosl2ValueError, match="not both"):
        Mask3D.roundover(radius=2, diameter=8, size=(10, 10, 10))
    with pytest.raises(Bosl2ValueError, match="give radius= or diameter="):
        Mask3D.roundover(size=(10, 10, 10))


def test_the_chamfer_profile_names_what_it_measures() -> None:
    """`x`/`y` named the axes rather than the thing (SPEC S-26c)."""
    parameters = inspect.signature(Mask2D.chamfer).parameters
    assert "width" in parameters
    assert "height" in parameters
    assert "x" not in parameters
    assert "y" not in parameters
    # a symmetric chamfer is one number
    assert len(Mask2D.chamfer(3)) == len(Mask2D.chamfer(3, 3))


def test_a_groove_derives_its_depth_and_length() -> None:
    """Only `width` is required; depth follows from it, length from the part (SPEC P-3, S-26a)."""
    default = Mask3D.groove(6)
    # the profile runs `excess` past the origin so the boolean cuts cleanly, hence the tolerance
    assert default.bounds().width == pytest.approx(6.0, abs=0.05)
    assert default.bounds().height == pytest.approx(60.0)  # ten widths, when nothing says otherwise

    sized = Mask3D.groove(6, size=(80.0, 20.0, 10.0))
    assert sized.bounds().height == pytest.approx(80.0), "length follows the part it grooves"

    explicit = Mask3D.groove(6, depth=1.0, length=25.0)
    assert explicit.bounds().height == pytest.approx(25.0)
    assert explicit.bounds().length < default.bounds().length, "a shallower groove cuts less deep"


@pytest.mark.parametrize("bad", [0.0, -3.0])
def test_a_groove_refuses_a_non_positive_width(bad: float) -> None:
    with pytest.raises(Bosl2ValueError, match="width must be positive"):
        Mask3D.groove(bad)


# --- the treatments honour the backend --------------------------------------------------------


@pytest.mark.parametrize("name", TREATMENTS)
def test_a_named_treatment_refuses_on_the_sdf_backend(name: str) -> None:
    """They are the edge masks by a friendlier name, so they are CSG-only for the same reason."""
    from pybosl2._backend import CSG_ONLY_FEATURES

    assert name in CSG_ONLY_FEATURES
    with use_backend("sdf"):
        shape = cuboid([10, 10, 10])
    with pytest.raises(UnsupportedByBackendError, match=name):
        getattr(shape, name)(Anchor.Z, radius=2, chamfer=2)
