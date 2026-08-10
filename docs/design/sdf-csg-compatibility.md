# SDF ↔ CSG Backend Compatibility Design

## Current State

The SDF backend (`pybosl2/sdf/`) is structurally superior to CSG for exact math (transforms,
booleans, and bounds are resolution-independent) but functionally narrower.  The tables
below catalogue every CSG feature and whether the SDF backend provides an equivalent.

---

## Tier 1 — High Impact, Implementable Quickly

These features unlock real-world workflows (colour-3D printing, assembly checks, path
distribution) with modest implementation effort.

### 1. `projection(cut)` → 2-D shadow

**CSG** calls native `projection()`.

**SDF** raises `UnsupportedByBackendError`.  A 2-D distance field cannot be derived in
closed form, but a sampling-based approach works:

```
pybosl2/sdf/shapes3d.py :: PyShape.projection()
  → evaluate the 3-D SDF on a dense XY grid at z = cut
  → run marching squares to extract isocontour at value 0
  → return polygon2d(result, res=res)
```

This is a pure-math approach — no meshing requires.  The resolution is controlled by the
grid spacing, which defaults from the shape's own `res`.

### 2. `bounding_box(excess)` → AABB as cuboid

**CSG** constructs a native cuboid from `bounds()`.

**SDF** already has exact `bounds()` — the stored `mn`/`mx` from every constructor.
Implementation is trivial:

```python
def bounding_box(self, excess=0):
    center, size = self.bounds()
    inflated = [s + 2 * excess for s in size]
    return cuboid(inflated).translate(center)
```

This lets SDF shapes participate in placement workflows that use bounding boxes.

### 3. `distribute_on_path(path, ...)` → distributed copies

**CSG** has `_distribute()` plus a path sampler.

**SDF** already has `_distribute(mats)` that returns multmatrix copies.  The path
distribution logic is shared between CSG and Path2D/Path3D — it lives in
`distributors.py` and is backend-agnostic.  Adding `distribute_on_path()` to
`PyShape`/`SdfSolid` is a thin wrapper that computes matrices from the path and calls
`_distribute()`.

### 4. `inside(point)` → point containment

**CSG** calls native `inside()`.

**SDF** evaluates the field at `point`:

```python
def inside(self, point):
    return float(self.sdf().sample(point[0], point[1], point[2])) <= 0
```

Trivially implementable since the SDF IS a signed distance field.

### 5. `fill()` (2-D)

**CSG** calls native `fill()` to close holes.

**SDF** can implement this as the union of the shape's positive region with a
greedy-flood-fill to close internal negative pockets.  Alternatively, evaluate the
field on a grid, find connected negative components, and subtract only the
genuine exterior.

### 6. `chain_hull(*others)` → sequential hull

**CSG** hulls consecutive pairs: `hull(a,b) | hull(b,c) | hull(c,d) | ...`.

**SDF** already has `PyShape.hull()`.  Implementation:

```python
def chain_hull(*others):
    parts = [self] + list(others)
    result = None
    for i in range(len(parts) - 1):
        pair_hull = parts[i].hull(parts[i + 1])
        result = pair_hull if result is None else result | pair_hull
    return result
```

---

## Tier 2 — Medium Impact, Moderate Effort

### 7. `half_of(v, center, s, cut_path, cut_angle, offset)` → planar half-cut

**CSG** intersects the solid with a half-space mask, auto-sizing `s` from the
object's bounding box.

**SDF** implementation:

1. Build the half-space as an explicit SDF cuboid (or polygon-prism for a cut-path
   mask).
2. Intersect (`&`) the shape with the mask.
3. The mask dimensions are derived from the shape's bounds (already exact).

The partition mask geometry (`_partition_mask_shape` in `partitions.py`) can be shared
since it returns native geometry.  The SDF version just uses `polygon_prism()` instead
of `linear_extrude()` internally.

### 8. `partition(spread, cutsize, cutpath, gap, slop)` → interlocking split

**CSG** splits into two interlocking halves by building two half-cuts with
complementary masks.

**SDF** can follow the same strategy: build the positive and negative halves as
intersections of the solid with complementary masks, both computed from the
same cut-path generator.

### 9. `round3d(radius)` and `offset3d(radius)` → surface offset

**CSG** uses `minkowski()` with a sphere — slow but general.

**SDF** can implement this as:

```python
def offset3d(self, radius):
    # SDF offset = d(p) - radius  (expand) or d(p) + radius (contract)
    # This requires a new SDF node that adds/subtracts a constant
    fn = self._sdf_fn
    if radius > 0:
        new_fn = lambda x, y, z: fn(x, y, z) - radius
    else:
        new_fn = lambda x, y, z: fn(x, y, z) + abs(radius)
    return self._wrap(new_fn, ...)
```

This is **exact and lightning fast** — a single subtraction on the field.
`round3d()` just chains three offset calls (outer offset → inner offset → outer offset).

### 10. Edge round/chamfer — survive transforms

**SDF** round/chamfer uses `_cuboid_edge_sdf()` which wraps the SDF in a
max()-layer that rounds edges indirectly.  This metadata is dropped after
`rotate`/`scale`/`mirror`/`multmatrix` because the transform is applied to the
field coordinates, not to the edge geometry.

**Fix**: Before applying any edge treatment that drops metadata, apply the
treatment first and then transform the result.  Currently the code drops
`cuboid_edge_amounts`/`cuboid_edge_modes`; instead it should
`_edge_treat()` before the transform.

---

## Tier 3 — Major Effort, Defer

### Attachment & Anchoring System

**CSG** has a full deferred child-parent placement system with `position()`,
`align()`, `attach()`, `reanchor()`, `reorient()`, `orient()`, `anchor_point()`,
and tag-based boolean resolution (`realize()`, `diff()`, `intersect()`).

**SDF** has none of this.  The attachment system is the largest gap.  It requires:

1. Implementing `_resolve_bounds()` that uses the stored `mn`/`mx` to compute
   bounding-box anchors.
2. Implementing the anchor vocabulary (`TOP`, `BOTTOM`, `LEFT`, `RIGHT`,
   `FRONT`, `BACK`, `CENTER` and their combinations) as offset vectors.
3. Implementing deferred evaluation (`_attachments` list, `tag_name`,
   `diff_config`) that the SDF's `__or__`/`__and__`/`__sub__` operators
   would resolve by casting to CSG and applying the tag system.

This is a several-thousand-line undertaking and touches the core `BaseShape`
abstraction.  Defer until the exact-math benefits of SDF genuinely require
this feature set for user-facing workflows.

### Native Mesh Operations

`repair()`, `wrap()`, `pull()`, `oversample()`, `separate()`, `render()`,
`roof()` — these are OpenSCAD-native operations with no SDF analogue.  They
can be partially emulated:

- `repair()` → remesh the SDF (already exists as `mesh()`)
- `render()` → redundant on SDF (the field IS the representation)
- `wrap()` → remap coordinates to a cylindrical space
- `pull()` → offset the field in a gradient direction

But these are niche operations; `to_csg()` is the escape hatch for users who
genuinely need them.

### Face/Edge/Corner Masking for Arbitrary Shapes

**CSG** `edge_mask()`, `edge_profile()`, `corner_profile()`, `face_profile()`
construct negative-space cutters aligned to bounding-box edges/corners/faces.

**SDF** currently supports `round()`/`chamfer()` only on cuboids.  The
half-plane approach could be extended to arbitrary convex shapes, but
general-purpose edge masking on concave SDFs requires solving per-edge
parameterisation — a research-level problem.

### Text Operations

`text3d()`, `path_text()`, `cross()` — these build geometry from font glyphs
or fixed 2-D shapes.  They could be implemented on the SDF backend by
first building the 2-D outlines on the CSG backend and then converting, but
a native SDF implementation from glyph contours is feasible.

---

## Implementation Priority Summary

| Priority | Feature | Lines of code effort | User impact |
|----------|---------|---------------------|-------------|
| **1** | `bounding_box()` | ~5 | Alignment workflows |
| **1** | `inside()` | ~5 | Point-in-shape queries |
| **1** | `chain_hull()` | ~15 | Organic bridging |
| **2** | `distribute_on_path()` | ~30 | Assembly/pattern layouts |
| **2** | `projection()` | ~60 | 2-D extraction from 3-D |
| **3** | `fill()` (2-D) | ~40 | Region cleanup |
| **4** | `offset3d()` / `round3d()` | ~40 | Surface modification |
| **5** | `half_of()` / `partition()` | ~100 | Print-splitting workflows |
| **6** | Preserve edge metadata across transforms | ~30 | Chained rounding after rotate |
| **7** | Attachment system | ~2000+ | Full assembly workflows |
