# SDF ↔ CSG Backend Compatibility

**Status:** current as of the T4 reconciliation. This document describes *where the two backends
still differ*. It is not the authority on what is exclusive — [`CSG_ONLY_FEATURES` and
`SDF_ONLY_FEATURES` in `pybosl2/_backend.py`](../../pybosl2/_backend.py) are (SPEC PAR-3), and
`tests/test_backend_parity.py` fails if either list drifts from the implementations.

> An earlier version of this file listed `projection`, `bounding_box`, `distribute_on_path`,
> `inside`, `chain_hull`, `half_of`, `partition`, `round3d` and `offset3d` as gaps. All of them
> were implemented long before anyone re-read the file, and the stale list then misled a design
> review into repeating it. A design note that is not maintained is worse than none: check the
> code before trusting anything here.

## What the SDF backend has

3-D primitives, 2-D shapes (`PyShape2D`), paths and sweeps, joiners, exact booleans and
transforms, exact `bounds()` with no meshing, `bounding_box`, `inside`, `hull`, `chain_hull`,
`half_of`, `partition`, `round3d`/`offset3d`, `distribute_on_path`, `separate`, `to_csg`, and
`show()` (which meshes, as rendering must).

## Deliberately exclusive

| Feature | Backend | Why it cannot cross |
|---|---|---|
| attachment & anchoring (`attach`, `align`, `position`, `reorient`, the tag/diff system, edge and corner profiles) | CSG | Anchoring needs a shape's face and edge structure; a distance field does not retain one, so there is nothing to anchor to. |
| `projection`, `fill` | CSG | Both need a 2-D shadow of a solid, which is not derivable in closed form from a field. Meshing to answer them would hand a CSG shape back from an SDF one (SPEC B-5), so they refuse and name `.to_csg()`. |
| `round()`, `chamfer()` as methods that survive later transforms | SDF | CSG expresses these as constructor parameters, applied once at build time. |

## Real remaining gaps

1. **The attribute fallback still meshes.** `SdfSolid.__getattr__` ends in
   `getattr(self.mesh(), name)`, so any unimplemented method silently converts the field and
   returns a raw native handle. Nineteen names reach it — the directional moves (`up`, `down`,
   `left`, `right`, `back`, `forward`, `fwd`, `move`, `rot`), the colour and display operations
   (`color`, `recolor`, `color_this`, `hsl`, `hsv`, `highlight`, `ghost`), and three attachment
   properties that belong on the CSG-only list. See [TASKS.md](../../TASKS.md) T3.
2. **Colour.** SDF shapes carry none, so `Shape` cannot yet declare it (SPEC C-19).
3. **Distribution on 2-D SDF shapes.** `SdfSolid` has `_distribute`; `PyShape2D` does not.
4. **Parts.** Every part builds CSG directly, so `use_backend("sdf")` does not reach them
   (SPEC S-46a, TASKS T0f).

## Adding a feature to one backend

Per SPEC PAR-2 and PLAN B-P1: implement it on both, or raise `UnsupportedByBackendError` **and**
add it to the exclusive list with its reason. "CSG only for now" is a tracked decision, never a
silent omission — and when it becomes implementable, remove the entry rather than leaving it as an
excuse.
