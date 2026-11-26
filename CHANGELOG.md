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
