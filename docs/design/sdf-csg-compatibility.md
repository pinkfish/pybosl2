# SDF ↔ CSG Backend Compatibility

**Status:** current as of the T40 sweep (checked against the code, not from memory). This document
describes *where the two backends still differ*. It is not the authority on what is exclusive — [`CSG_ONLY_FEATURES` and
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

1. **Distribution on 2-D SDF shapes.** `SdfSolid` has `_distribute` and the whole copier surface
   (`xcopies`, `ycopies`, `distribute_on_path`, …); `PyShape2D` has none of it, so a 2-D field
   cannot be laid out the way a 2-D CSG shape can.
2. **Eleven parts have no SDF form.** 40 of the 51 build on either backend (T14). The eleven that
   refuse all need the same thing — a non-convex mesh, which has no closed-form distance field —
   so closing this fully would mean approximating one, which SPEC B-5 forbids. The refusal is
   tracked rather than a silent CSG shape, which is what S-46a asks for (SPEC §12.2 item 2).
   *This entry said "all 53 build CSG directly" until T40, which is what the preamble above warns
   about: the total double-counted an alias and the claim had not been rerun since parts were
   ported.*
3. **2 options one backend takes and the other does not**, and neither is a gap in the usual sense. Parity is measured per option, not
   per shape (`tests/test_option_parity.py`), and each missing one is refused with the parameter
   named rather than dropped (B-9). What remains after T48 is `cuboid`/`cube`'s
   `teardrop` (2), which raises `Bosl2NotImplementedError` on the CSG backend too -- a feature
   neither backend has rather than something one can do and the other cannot.

   Down from 176 when the measurement was first taken. What closed them was almost never a
   distance field somebody had to invent: it was reading what the CSG backend actually does, which
   twice as often as not turned out to be "reduce it to something simple and then build that". *This entry said the cylinder family's `texture`/`tex_*`
   could not cross, "a textured field, not a mesh with a texture applied, so B-5 rules out the
   cheap route". That was wrong, and it was wrong the same day it was written: the CSG backend
   does not apply a texture to a mesh either — it reduces the texture to a grid of heights and
   then places vertices at it. The map is not a mesh, and there was nothing to convert. T41 built
   it (SPEC §12.2 item 12).*
4. **`pie_slice` bounds.** The SDF wedge stores the full disc's bounding box, so `bounds()`
   over-reports on the backend whose selling point is exact bounds.
   `tests/test_backend_parity.py::BOUNDS_NOT_YET_EXACT` pins it (SPEC PAR-5).

### Closed since this note was written

* **The attribute fallback no longer meshes silently.** `SdfSolid.__getattr__` now falls through
  only for names in `_MESH_OPERATIONS` — operations that genuinely consume or produce mesh
  topology (`linear_extrude`, `rotate_extrude`, `offset`, `roof`, `size`, `background`,
  `textmetrics`). Everything else raises `UnsupportedByBackendError` naming `.to_csg()` (T3).
* **Colour rides the field.** SDF shapes carry colour as metadata, so `Shape` declares it for both
  backends (SPEC C-19).
* **The directional moves are native**, not meshed: `up`/`down`/`left`/`right`/`back`/`fwd`/`move`
  are implemented on the field.

## Adding a feature to one backend

Per SPEC PAR-2 and PLAN B-P1: implement it on both, or raise `UnsupportedByBackendError` **and**
add it to the exclusive list with its reason. "CSG only for now" is a tracked decision, never a
silent omission — and when it becomes implementable, remove the entry rather than leaving it as an
excuse.
