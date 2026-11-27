# Changelog

What has changed, release by release. The **Unreleased** section is kept current as work lands,
so tagging a release means moving a section heading rather than reconstructing the history from
`git log`: [TASKS.md](TASKS.md) holds the full record of each task and
[SPEC.md §12](SPEC.md) the narrative, and this file is the short version for somebody upgrading.

Versions follow [semantic versioning](https://semver.org/) loosely — this is a 0.x library, and a
minor bump is the signal that **rendered geometry has changed**, not that an API was removed.

## Unreleased

**This changeset changes rendered geometry**, in one place: every rim treatment on a *tapered*
cylinder. Read "Output changes" before upgrading a model that uses one.

### Output changes

- **The 2-D `hull()` of shapes growing by *different* radii is now exact.** The last release note
  below describes the hull being computed from each shape's extreme-point claim; where the radii
  differed it sampled 64 support directions and returned an inscribed polygon. It is now the true
  hull — the discs' common outer tangent segments joined by arcs of each radius — so
  `circle(5).hull(square(6))` and `circle(5).hull(circle(3).translate([20, 0]))` gain the material
  the faceting was losing (areas 193.365 → 193.625 and 213.862 → 214.224, both against a hand
  derivation of 214.2077 for the second). **`hull()` no longer takes `directions=`**: there is
  nothing left to approximate, and a resolution argument on an exact construction is a promise it
  cannot keep. Equal-radius hulls are unchanged — that branch was already exact. A hull can also
  now be hulled again, because it records its own extreme discs.

- **`flat`/2-D `hull()` on the SDF backend never returned a hull.** `circle2d(5).hull(other)`
  handed back **the receiver**, with every other operand silently discarded, or raised
  `hull(): a child shape meshed to nothing` — depending on how far the old chain got. It extruded
  each operand to a 0.01mm slab (which meshes to nothing at `res=10`), hulled the slabs in 3-D,
  meshed that, crossed to CSG, projected back and read `.paths` off the projection — an attribute
  a `CsgShape2D` does not have, so the success branch was unreachable at any thickness. It is
  computed from each shape's own extreme-point claim now: exact when every operand grows by the
  same radius (so `hull(circle().translate(), circle().translate())` has genuine arcs), and
  faceted over `directions=64` when the radii differ, matching what the CSG backend builds. By
  area it agrees with the CSG hull to within 2.7%, always on the larger side because CSG facets
  its circles, and exactly for polygons. It needs no mesher at all, where the old route needed one
  twice. A shape with no usable claim — a boolean, an `outline`, a shrunk shape, a rectangle
  rounded by unequal radii — is refused by name with the `.to_csg()` route rather than
  approximated, because a libfive field cannot be asked for its own boundary points.

- **A rim fillet or chamfer on a tapered cylinder was in the wrong place, on both backends.** The
  fillet's centre sat at `radius - amount` from the axis, which is only the corner's incentre when
  the wall is vertical; BOSL2 fits it tangent to *both* legs of the corner. On a 10-to-4 cone with
  a 3mm rounding the fillet was over a millimetre out. The same measurement found a chamfer
  measured as the cut's hypotenuse rather than along the side face, and `from_end=` therefore
  taking a different length from the one BOSL2 gives it. `cyl`, `cylinder`, `xcyl`, `ycyl`,
  `zcyl`, `tube` and `regular_prism` are all affected where the ends differ in radius; a straight
  wall is unchanged, to 2e-15 over 44 profiles.

  This was found by transcribing BOSL2's own `_cyl_path()` into the suite
  (`tests/bosl2_cyl_path.py`) and comparing against it. Every cross-backend instrument this
  project had compares the two backends *against each other*, and none of them can see a rim they
  both get wrong — which is what had happened, twice refined.

- **`bounds()` over-claimed on a treated taper.** Once the fillet moved to the incentre the
  declared box no longer matched the solid: a 10-to-4 cone with a 2mm rounding reaches 9.31mm and
  the box said 10.0, and a 20-to-2 cone with a 1mm rounding was 1.245mm out, against the 0.35mm
  the project's own test allows. Both backends disagreed by the same amount.

- **`grid_copies(stagger=)` refused two of `StaggerMode`'s three values.** `StaggerMode.NONE` and
  `StaggerMode.STANDARD` both raised, as did the strings `"none"` and `"standard"`, while the
  booleans they are named for worked. All seven spellings work now.

### New features

- **Argument groups reach every constructor that takes the family.** `solid.teardrop` takes a
  chamfer and no rounding, `flat.regular_ngon` a rounding and no chamfer, and neither accepted an
  `EdgeTreatment` group — so a caller holding one had to unpack it by hand, asking the single
  question the group exists to answer. Both accept one now, and a shape that can only chamfer says
  so by name when handed a rounding.
- `regular_prism` takes `outer_radius` / `outer_diameter`.
- `Flat.linear_extrude` declares `scale`, `twist` and `slices` on the shared contract. The CSG
  backend builds them; the SDF backend refuses them **by name** rather than raising a bare
  `TypeError` about a keyword from inside.

### Backend parity

- **A shape from the other backend is refused wherever a call takes one, not just by the boolean
  operators.** Handing a CSG shape to an SDF call, or the reverse, raised `CrossBackendError` for
  `a | b`, `a - b`, `a & b` and `minkowski`, and for nothing else. Measured across 38 ways to pass
  a shape as an *argument*, 29 reported something else: most raised a raw `TypeError` or
  `AttributeError` from the native layer that `except Bosl2Error` could not catch (`hull`, `fill`,
  `round2d`, `shell2d`, `chain_hull`, `minkowski_difference`, `extrude_from_to`,
  `cylindrical_extrude`, `path_extrude`, `path_extrude2d`, and the n-ary calls on both backends);
  `sdf_solid.minkowski(csg_solid)` and `.minkowski_difference(csg_solid)` built a **wrong answer
  in silence**, dilating or eroding by the foreign solid's bounding ball; `sdf_2d.union([csg_2d])`
  returned the **CSG** shape; and `position`/`align`/`attach`/`edge_mask` accepted the foreign
  child or cutter and failed at *render* time with `TypeError: invalid argument left to operator`.
  All of them now raise `CrossBackendError` naming the call you made and the conversion that
  applies in that direction — `.to_csg()` for a field, or rebuilding inside `use_backend("sdf")`
  for a CSG shape, since there is no CSG→SDF conversion to take for you.

- **`CsgSolid.union()`, `.intersection()` and `.difference()` now work.** None of them ever did,
  with any argument: all three fall through to the native passthrough, which wrapped the result on
  the way out and never unwrapped the arguments on the way in, so
  `sphere(radius=5).union(cuboid([6, 6, 6]))` raised `TypeError: Error during parsing union.
  arguments must be solids or arrays`. The SDF backend has had working
  `union`/`intersection`/`difference` methods throughout, so this was a parity gap as well as a
  break. Both the varargs and the `union([a, b])` list form work now. Use `a | b`, `a & b`, `a - b`
  or `pybosl2.solid.union(a, b)` if you worked around it.

- **An unknown attribute on a 2-D SDF shape no longer silently meshes it.** `SdfShape2D` answered
  every name a 2-D distance field does not define by extruding a 0.01mm slab, meshing it and
  forwarding the attribute to the result — so from inside `use_backend("sdf")`,
  `circle2d(5).projection()` returned a raw PythonSCAD solid although `projection` is listed as
  CSG-only, `.repair`/`.render` returned its builtins, `copy.copy` of a 2-D field raised
  `RecursionError`, and on a machine with no mesher a plain `hasattr` probe raised instead of
  answering. All of those refuse now, naming the attribute and the explicit route
  (`.extrude(h).to_csg().<name>(...)`). The three other shape classes have behaved this way for
  some time; this one was the odd one out, and nothing in 9099 tests had wanted the old
  behaviour.

- **Six calls that built CSG geometry whatever backend was selected now follow the active one, or
  refuse under their own name.** `Path3D.dashed_stroke`, `chain_hull`, `minkowski_difference` and
  `masking.rounding_edge_mask` work on both backends; `extrude_from_to` and `cylindrical_extrude`
  are genuinely CSG-only and say so. Before this, four of the six handed back a CSG solid from
  inside `use_backend("sdf")` *silently*, and the other two failed from inside — one with the
  native parser's `TypeError`, one blaming a missing bounding box three frames from the call.
- `surfaces3d.fillet` is no longer CSG-only: it is a forward to `rounding_edge_mask`, which now
  builds through the façade.
- `SdfShape.minkowski_difference` works. It used to convert the receiver to CSG and leave the
  diffs as fields, so the CSG implementation got the wrong type and raised from inside. It is a
  negative offset now — which is what eroding a solid by a ball is — and exact for the sphere it
  is almost always called with.
- **`partition()` works on the SDF backend, as a field.** It used to mesh the solid and hand back
  two CSG pieces; a split is two intersections with a cut mask and a translate, and the mask is
  built through the 2-D façade now, so both backends run one implementation. The two agree on the
  piece's bounding box to the digit.
- **`repair()` and `oversample()` on an SDF solid return the solid.** A field has no mesh to repair
  and no facets to subdivide — the facet count is a render hint, which SPEC B-9 lets a backend
  ignore. Both used to mesh and return a CSG solid, which made `oversample` the one call where
  asking for a smoother result silently coarsened everything after it.
- **`separate()`, `wrap()` and `pull()` on an SDF solid refuse by name** instead of meshing. All
  three need mesh topology a distance field does not carry, and the refusal names the explicit
  route: `shape.to_csg().wrap(20)`. This is a behaviour change — the calls used to return a
  working CSG solid, silently, from inside `use_backend("sdf")`, which would not combine with the
  fields around it.
- **`minkowski()` on the SDF backend grew shapes by 73% too much.** It read each argument's radius
  as half its bounding-box *diagonal* rather than half its smallest extent, so a 4mm cube dilated
  by a 2mm ball came out 10.93 across where the answer is 8 — and it disagreed with
  `minkowski_difference`, so eroding and re-dilating one solid by one sphere did not return it.
- A `partition()` call now builds its cut mask on the backend of the solid being cut rather than
  the ambient one, so a solid built straight from a backend module, or held across a
  `use_backend` boundary, no longer meets a mask from the other backend.
- **`bounds()` on a turned SDF shape is exact where it used to over-claim.** A rotation recomputed
  the box from the old box's eight corners, which is right only for a shape that fills its box: an
  octagonal prism 20.48 across reported 28.97, a hexagonal one 50% over, a cylinder off its own
  axis spun 30° 37% over, and a 2-D star turned off its symmetry step 4.5mm over. A prism now
  carries its outline and a round shape its axis and radius, so the turn reads a tight box off
  those instead. `TrussFoot` and `TrussJoiner` agree with the CSG backend to the digit; the
  geometry is unchanged in every case, and nothing was ever clipped, because the old box was always
  a superset.

### Internals

- **The 2-D hull's `to_csg()` crossing is gone, and so is its entry in the boundary ratchet.**
  `CROSSES_AND_RETURNS` listed `sdf/shapes2d.py::hull` with a reason describing a code path that
  had never run — a justified exemption for dead code reads as checked. `mirror` and a positive
  `offset` now propagate the `Hull2D` extreme-point claim (a reflection is an isometry; growing by
  *a* adds *a* to the radius), so more shapes can be hulled rather than refused. The claim also
  carries a tightness flag: `bounds` only needs a claim that *contains* the shape and is happy
  with a loose one, while `hull` needs the *extreme set*, and the two requirements had been
  conflated since the claim was added.
- **Cross-backend mixing is checked for arguments, not only operands.**
  `pybosl2._backend.require_same_backend` is the argument form of `check_operand_backend`: it
  takes the caller's name, so the refusal reads `hull(): cannot take a 'sdf'-backend shape here`
  rather than naming an inner frame. `tests/test_a_shape_argument_cannot_cross_backends.py` runs
  34 cases **twice** — mixed, which must refuse under the call's own name, and same-backend, which
  must still build — and that second half is what found the three broken `CsgSolid` n-ary methods.
  Against unfixed `main` the file reports 40 failures. Its control
  neutralises the guard in every module that binds it, including `pybosl2._backend`'s own
  attribute, and a companion check asserts no module imports it inside a function, where patching
  could not reach it; a static scan requires
  every call to a shape coercer to pass `call=`, so a new coercion site cannot arrive unnamed.
- **The four shape classes' attribute fallbacks are now checked against each other** rather than
  one at a time. Five separate tests guarded that fallback and four of them asked the 3-D SDF
  solid; the fifth had been taught to ask the 2-D shape as well and skipped the failing name
  because it was not *declared* on the class. The new check derives its class list from the
  source, so a new `__getattr__` anywhere in the package joins it or fails.
- **The SDF backend's boundary ratchet watches both doors.** It held every `to_csg()` inside
  `pybosl2/sdf/` to a declared list and called that "the one declared door"; `mesh()` returns the
  `frep()` handle, which is a CSG solid in all but name, and is the one the 2-D fallback used.

- **The layering debt list is empty**, from 16 violations when it was first measured. The last
  three rows each claimed the edge could not close and each reason was wrong in a different way.
  Four upward edges remain and are architecture rather than debt, each pinned by a test that holds
  the capability in place.
- A new check asks, statically and dynamically, whether a call that looks backend-neutral is one.
  The same defect had been found five times before, once per task, always by accident.
- **A second check does the same for the SDF backend's own methods**, which the first one skips: it
  calls each of `SdfSolid`'s 53 public methods and requires what comes back to be a field or a
  refusal naming the call. Six were not, and four of those had a test asserting it — the defect was
  not unmeasured, it was pinned.
- Two skip markers reading "no libfive: a meshed SDF solid cannot enter the CSG operators" are
  gone, because nothing in the SDF shape tests meshes any more. The marker was right about the
  environment; what nobody asked was why a field was being meshed to split it.
- **Three lists of "this box is loose on purpose" went from nine entries to one.** The one that
  remains is a case added by looking rather than one left over: a rectangle rounded by a different
  radius per corner has no tight containment of the form the mechanism carries, and the reason is a
  proof instead of an absence of one. A new check measures the containment a shape claims rather
  than only the box one turn of it reports, since claiming too little is the direction that clips
  geometry silently.

### Documentation

- **A chamfered cylinder was published as not watertight. It is watertight.** The measurement
  the spec pages use re-identifies an STL's shared vertices by position, and a *degenerate*
  triangle — two of its three vertices the same point — has its collapsed side listed twice among
  its own three edges. That side is one two real faces already share, so the count went from 2 to
  4 and the solid read open. `cylinder(radius=10, chamfer=2)` carries 120 such slivers in 360
  triangles, from the fan its chamfered rim is tessellated as, and so does the chamfered cone;
  `ball_bearing("r8")` and `pco1810_neck()` carry a dozen each. All four are closed solids and now
  measure as ones.
- The bottlecap spec page's figures were stale and are regenerated.
- **The STL viewer renders the colours an example sets**, and releases its WebGL context with the
  tab rather than holding it open.

### CI

- The test suite runs in parallel in CI, the `mypy` legs cover the test suite as well as the
  package, duplicate runs on a push-plus-pull-request are gone, and the wheel is checked before it
  is published.

## 0.8.0 — 2026-11-24

153 commits since 0.7.13 — 48 fixes, 9 features. **This release changed rendered geometry** in a
dozen places: several constructors were building the wrong solid. Highlights:

- **Breaking:** `BottleThreadSpec.cap_thread_od` is now `cap_thread_base_d`. The field never held
  an outer diameter.
- Every tapered cylinder on the SDF backend had lost the half ending at its narrower rim.
- `ThreadHelix` added no thread — the ridge grew inward — so both bottle necks were built smooth.
- A scalar `scale=` on an extrusion was silently dropped, so anything tapered by one wasn't.
- `mask2d_groove` traced a channel's outline rather than the channel, and `mask2d_cove`'s arc was
  a roundover.
- Every quad in a VNF was wound inside out; a `halfspace` never closed.
- `bounds()` over-claimed on rotated 2-D shapes — 37% too wide for a circle turned 30 degrees.
- The public surface is fully typed, `py.typed` ships in the wheel, and `pythonscad` 1.2.0 is
  supported with the version ceiling gone.

Full notes: <https://github.com/pinkfish/pybosl2/releases/tag/v0.8.0>

## 0.7.13 and earlier

See the [releases page](https://github.com/pinkfish/pybosl2/releases).
