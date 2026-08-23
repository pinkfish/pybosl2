# pybosl2 — Conformance Work Queue

Ordered, checkable work to bring the code up to [SPEC.md](SPEC.md), with the Python mechanics in
[PLAN.md](PLAN.md). **[SPEC.md §12.2](SPEC.md#122-open) is the authoritative list of what is open**
— this file is how to close it. When a task lands, move its row from §12.2 to §12.1 in the same
commit, and tick it here.

Definition of done for **every** task: the five gates in [PLAN.md §10](PLAN.md#10-gates-and-commands)
pass (`pytest`, `mypy --strict pybosl2`, `ruff check . && ruff format .`, the minimum-argument and
example checks, the contract tests), the new contract test named in the task exists, and the spec's
conformance tables are updated. Run with `TMPDIR` pointed at a volume with room (PLAN X-6).

## Spec item → task

✅ done · 🔶 in progress · (blank) not started

The first column is the item's number in §12.2 *as it stood when the task was written*; the
spec renumbers as items close, and all but S-46a have.

| §12.2 | Requirement | Task | Size |
|---|---|---|---|
| 1 | C-1 / E-3 | [T0](#t0--make-the-backend-tag-tell-the-truth) ✅ | S |
| 2 | A-6 | [T2b](#t2b--make-the-top-level-backend-neutral) ✅ | M |
| 3 | E-4 | [T0b](#t0b--convert-user-input-asserts-to-valueerror) ✅ | L |
| 4 | C-14 | [T0c](#t0c--make-partshape-a-property) ✅ | M |
| 5 | DOC-2 / D-P5 | [T0e](#t0e--document-the-façade) ✅ | M |
| 6 | A-7 | [T0d](#t0d--fix-the-broken-export) ✅ | XS |
| 7 | S-46a | [T0f](#t0f--make-parts-honour-the-active-backend) ✅ | L |
| 8 | S-51 | [T0f](#t0f--make-parts-honour-the-active-backend) step 3 ✅ | — |
| 9 | B-3 / PAR-5 | [T2](#t2--give-the-façade-ownership-of-shared-defaults) ✅ | L |
| 10 | C-15 … C-19 | [T1](#t1--merge-solid-and-flat-into-one-shape-contract) ✅ | M |
| 11 | R-1 | [T5](#t5--close-the-facet-control-backlog) ✅ | L |
| 12 | PAR-1 / C-1 / B-5 | [T3](#t3--stop-the-sdf-fallback-silently-meshing) ✅ | M |
| 13 | PAR-3 | [T4](#t4--reconcile-the-parity-records-with-the-code) ✅ | S |
| 14 | R-5 | [T6](#t6--document-and-test-the-fn0-opt-out) ✅ | S |
| 15 | Q-4 | [T7](#t7--generalise-the-minimum-argument-check) ✅ | M |
| 16 | P-8 | [T8](#t8--class-ify-the-remaining-function-families-) ✅ | M |
| 17 | B2-1 | [T9](#t9--track-bosl2-feature-coverage-) ✅ | M |
| — | housekeeping | [T10](#t10--housekeeping-) ✅ | S |
| — | E-4 follow-up | [T11](#t11--cover-the-rejection-paths--sdf-only-remainder) 🔶 | L |
| — | P-8 / coverage | [T12](#t12--partitions-cover-it-and-find-out-why-it-was-not-covered-) ✅ | M |
| — | test quality | [T13](#t13--replace-the-existence-only-tests-) ✅ | L |
| — | S-46a / PAR-1 | [T14](#t14--give-parts-an-sdf-form-where-they-have-one-) 🔶 | XL |
| — | bug | [T15](#t15--from_svg-loses-even-odd-holes-when-the-svg-has-a-viewbox-) ✅ | S |

**Everything above is done except T11**, whose last four rejection paths need a real
libfive install to reach. The open conformance item is S-46a / PAR-1: parts refuse on
the SDF backend rather than building — see [T14](#t14--give-parts-an-sdf-form-where-they-have-one-)
for what that would actually take. [T15](#t15--from_svg-loses-even-odd-holes-when-the-svg-has-a-viewbox-)
was a reported bug in the SVG importer, now fixed.

## Order and why

```
  T0 backend tag ──► everything else            the cross-backend guard must work first
       │
  T0b asserts · T0c parts.shape · T0d parts __all__ · T0e façade docs   user-visible, independent
       │
  T0f parts honour the backend (needs T0 + T2b)
       │
  T1 Shape merge ──► T2 façade defaults ──► T3 SDF fallback ──► T4 parity records
   (contract)          (uses the contract)     (needs T1's Self)   (reconcile the lists)
       │
  T2b top-level neutrality (needs T2's façade defaults)

  T5 facet backlog ─── independent, batchable by module
  T6 fn=0 · T7 min-arg check · T8 class-ify · T9 BOSL2 matrix ─── independent
```

**T0 goes first.** While the backend tag lies, every other backend-related change is being tested
against a guard that does not fire. T0b–T0e are what a user hits on day one and need nothing else
landed first. T1 → T2 because the façade signatures are easier to change once `Shape` fixes what
"a shared argument" means; T2 → T2b because promoting shapes to the façade means declaring their
defaults there.

---

## T0 — Make the backend tag tell the truth ✅

**Closes:** §12.2 item 1 (C-1, E-3) · **Implements:** PLAN O-6a, B-P3 · **Size:** S
**Risk:** low in itself, but it exposes latent mixing bugs that were passing silently

`CsgSolid.__init__` does `self.backend = current_backend()`, so a CSG solid built inside a
`use_backend("sdf")` block claims to be an SDF solid. `check_operand_backend` then waves it through
and the user gets `AssertionError: every argument must be a PyShape, got ['CsgSolid']` from inside
the SDF backend instead of `CrossBackendError` with the conversion hint.

1. Replace the assignment with a class constant `backend = "csg"` on `CsgSolid` (PLAN O-6a), the
   way `CsgShape2D` already does it.
2. Make CSG-only constructors refuse inside an SDF block: raise `UnsupportedByBackendError` naming
   the neutral equivalent (`pybosl2.solid.cyl` for `pybosl2.shapes3d.cyl`, …) rather than returning
   a shape the caller cannot combine.
3. Expect fallout — tests that build CSG shapes inside an SDF block on purpose now fail; each is a
   real mixing bug or a test that should say which backend it means.

**Done when:** a test asserts that a CSG shape built inside `use_backend("sdf")` reports
`backend == "csg"`, and that combining it with an SDF shape raises `CrossBackendError`.

---

**Landed.** `CsgSolid.backend` is the class constant `"csg"`; `backend_only("csg", neutral=…)`
guards 64 constructors in `shapes2d`/`shapes3d`/`surfaces3d` so they refuse on another backend and
name the neutral twin; `builds_with("csg")` is its counterpart for CSG internals (the strokes) that
legitimately build CSG whatever is selected. `stroke_3d` now reads the caller's backend before
entering that context, so the decorative-cap fallback warning still fires. Tests:
`test_a_csg_shape_built_inside_an_sdf_block_still_says_csg`,
`test_2d_shape_constructors_refuse_on_another_backend`.

---

## T0b — Convert user-input asserts to `ValueError` ✅

**Closes:** §12.2 item 1 (E-4) · **Implements:** PLAN E-P1, E-P2, E-P4a

**Landed — all 290 converted.** An AST pass rewrote every message-carrying `assert` in the public
modules (301 statements), then the stragglers: multi-line asserts, f-string messages, and the ones
in private modules whose message named a public function (`stroke()`, `minkowski()`,
`linear_extrude()`). What remains is 25 asserts stating genuine internal invariants — none names a
function call or a parameter.

The contract change rippled into **65 tests** that asserted `AssertionError`. Each was updated to
assert `ValueError` **and a slice of its message**, since E-4 is about the message naming the fix;
the patterns were generated from the messages the code actually raises, repaired by re-running the
affected files until every regex matched.

`tests/test_defaults.py::test_no_assert_validates_user_input` is the ratchet: it walks the package
AST and fails on any `assert` whose message contains a call or a parameter — PLAN E-P2's test for
"is this validation?" made executable.

---

## T0c — Make `part.shape` a property ✅

**Closes:** §12.2 item 4 (C-14) · **Implements:** PLAN O-2, O-5a · **Size:** M
**Risk:** low, but API-visible

All 37 part classes define `shape` as a method; the spec, the docs and every example say property.

1. Add `@property` with lazy caching to each part's `shape` (many already cache in `self._solid`).
2. Update docstring examples and the spec sheets that call `.shape()`.
3. Add a test walking `pybosl2.parts.__all__` asserting `shape` is a property on every class.
4. Keep the C-14a distinction visible in docstrings: a part's `shape` is the finished solid, a
   wrapper's is the native handle.


**Landed.** 50 part classes gained `@property` on `shape`; 551 call sites across the package,
tests and docs were rewritten from `.shape()` to `.shape`. All 50 `show()` methods now return the
shape instead of `None` (S-49/S-51, §12.2 item 7 closed with this one). Tests:
`test_every_part_exposes_shape_as_a_property`, `test_part_show_returns_the_shape`.

---

## T0d — Fix the broken export ✅

**Closes:** §12.2 item 6 (A-7) · **Implements:** PLAN M-2 · **Size:** XS · **Risk:** none

`pybosl2.parts.__all__` lists `Threading`, which does not exist, so `from pybosl2.parts import *`
raises. Remove it (or export the intended name), then add a test asserting every name in every
public module's `__all__` resolves.


**Landed.** `Threading` removed from `pybosl2.parts.__all__` (the module exports `ThreadedRod`,
`ThreadedNut` and `ThreadHelix`). `tests/test_exports.py` now walks every public module and
asserts each `__all__` entry resolves — 77 modules covered.

---

## T0e — Document the façade ✅

**Closes:** §12.2 item 5 (DOC-2) · **Implements:** PLAN D-P4a, D-P1, D-P5 · **Size:** M
**Risk:** none

27 façade callables have no `Args:` and no example, so `help(pybosl2.cuboid)` — the entry point the
spec recommends — documents nothing. Give each an `Args:` covering the parameters it declares, a
note on what an omitted argument resolves to (and `effective_defaults()`), and one
`.. pythonscad-example::`. Best done with or after T2, when the façade owns the defaults it would
be documenting.


**Landed.** All 19 shape constructors plus the four n-ary operations now carry a full `Args:`
block, a `Returns:`, and a rendering example — generated by lifting the descriptions and examples
from the backend constructors they delegate to, so the prose has one source. The old boilerplate
("only the arguments actually given are passed on") was wrong after T2 and is replaced by a
statement of what the façade now guarantees. `xcyl`/`ycyl`/`zcyl` and `union`/`difference`/
`intersection` became top-level exports along the way — their examples named imports that did not
exist. Tests: `test_every_facade_callable_documents_its_arguments_and_shows_an_example` and
`test_every_facade_example_runs`, which executes all 41 façade examples.

---

---

## T0f — Make parts honour the active backend ✅

**Closes:** §12.2 items 7 and 8 (S-46a, S-51) · **Implements:** PLAN O-0a, O-5a · **Size:** L
**Risk:** medium

Every part imports `pybosl2.shapes3d` directly, so `with use_backend("sdf"): Screw("M6", length=20)`
returns a CSG part that cannot be combined with the SDF geometry around it.

1. Re-point each part module's imports at `pybosl2.solid` / `pybosl2.flat` (PLAN O-0a).
2. Where a part needs something only CSG can express (threading helices, text, some masks), raise
   `UnsupportedByBackendError` naming the backend rather than returning the other backend's shape.
3. Fix the parts' `show()` while you are there: `self.shape.show()` after T0c, returning the shape
   (S-49, §12.2 item 8).
4. Add a test: every part class built inside `use_backend("sdf")` either yields `backend == "sdf"`
   or raises `UnsupportedByBackendError`.

**Depends on:** T0 (the backend tag must be truthful before this can be tested) and T2b (the façade
needs the shapes parts use).


**Landed.** T0's constructor guards had already stopped 36 of 53 parts from building CSG inside an
`sdf` block, but 17 still did — they reach geometry through `VNF.polyhedron()`, `Path2D.polygon()`
or raw `native()` calls that no constructor guard covers. The guard now sits where the contract
lives: `@csg_part` on every part's `shape` property, so all 53 refuse uniformly with a message
naming the way forward (`with use_backend("csg")` plus `.to_csg()`), instead of a mix of refusals
and silent CSG. Making parts actually *build* on SDF stays open — none of them has an SDF form yet.
Test: `test_every_part_refuses_on_another_backend`.

---

## T1 — Merge `Solid` and `Flat` into one `Shape` contract ✅

**Closes:** §12.2 item 10 (C-15 … C-18) · **Implements:** PLAN T-6a, T-6b · **Size:** M
**Risk:** low — a contract change, not a geometry change

Today `Solid` lives in `_backend.py` and `Flat` in `flat.py`, duplicating the `backend` tag, three
boolean operators, four transforms and `bounds()`. That duplication is why `Flat` was `Any`-typed
long after `Solid` was not, and why it lacked `bounds()` until recently.

1. In the L1 contract module declare `Shape(Protocol)` with the universal surface — `backend`,
   `__or__`/`__and__`/`__sub__`, `translate`/`rotate`/`scale`/`mirror`/`multmatrix`, `bounds()` —
   typing shared members `-> Self` (PLAN T-6a).
2. Redeclare `Flat(Shape, Protocol)` with only `linear_extrude`, `rotate_extrude`, `offset`, and
   `Solid(Shape, Protocol)` with only `projection` and the 3-D-only surface. Remove every member
   that is now inherited — a re-declaration re-opens the drift.
3. Re-point `flat.py` and `solid.py` at the new declarations; export `Shape` alongside
   `Flat`/`Solid` (`_LAZY_EXPORTS` + `__init__.pyi`). There is no `Shape2D` alias any more (C-18).
4. Confirm the four implementations still satisfy the protocols: `CsgSolid`, `SdfSolid`,
   `CsgShape2D`, `PyShape2D`.

**Done when:** `mypy --strict` is clean; a test asserts `flat | solid` is rejected statically
(`assert_type` / a `# type: ignore[operator]` that mypy reports as unused if the error disappears);
`tests/test_init_stub.py` passes with `Shape` exported.


**Landed.** `Shape` is declared in `_backend.py` with `Self`-returning members (`backend`, the
three boolean operators, `translate`/`scale`/`mirror`, `bounds()`, `show()`); `Solid(Shape)` adds
`rotate`'s 3-D signature and `Flat(Shape)` adds only `rotate` and `linear_extrude`. `Shape` is
exported at the top level and in the stub. C-19 (colour and distribution on the shared contract)
stays open until T3 gives the SDF shapes colour. Test:
`test_one_shape_contract_with_two_specialisations`, which also asserts no shared member is
re-declared on `Flat`.

---

## T2 — Give the façade ownership of shared defaults ✅

**Closes:** §12.2 item 9 (B-3, PAR-5) · **Implements:** PLAN F-P1 … F-P4 · **Size:** L
**Risk:** medium — behaviour-affecting

Façade constructors default every shared argument to `None` and forward only what the caller
passed, so an identical call can resolve differently per backend.

1. For each constructor in `solid.py` and `flat.py`, replace `None` with the real default for every
   argument **both** backends understand (PLAN F-P1). `effective_defaults()` reports today's values
   per backend — use it as the source, and where the two disagree, decide deliberately and record it.
2. Replace the blanket `given_arguments()` filter with a signature-aware one (PLAN F-P2), reusing
   the cached-signature approach `_takes_res` already uses.
3. Keep backend-exclusive options (`res`; `spin`/`orient`/`fn`/`fa`/`fs`) defaulting on the backend.
4. Extend `test_backends_agree_on_the_defaults_they_share` from its four shapes to every façade
   shape, so a future divergence fails.

**Done when:** the extended agreement test passes over all façade shapes; `effective_defaults()`
needs no change (PLAN F-P4); no golden STL shifts.


**Landed.** 64 shared defaults lifted into the façade signatures (`size=(1, 1, 1)`,
`anchor=Anchor.CENTER`, `orient=Anchor.TOP`, `spin=0`, `edges=Anchor.ALL`, `angle=45`, …), and both
backends now filter what they are handed by what their constructor declares (`for_backend()`), so
the façade can forward every default it owns without a backend choking on an option it lacks.
`effective_defaults()` reports the façade's value first and the backend's only for its exclusive
options. The audit found exactly one disagreement across 19 constructors — `anchor`, and only as
two spellings of the same vector — so no behaviour was chosen away. Tests:
`test_backends_agree_on_the_defaults_they_share` (now every façade shape, 100+ parameters),
`test_the_facade_owns_the_shared_defaults`,
`test_the_same_call_builds_the_same_geometry_on_both_backends`.

Two E-4 asserts in the SDF backend (`tube`, `rect_tube`) became reachable once defaults were
forwarded, and were converted to `ValueError` with them.

**PAR-5's remainder, closed later.** One shape was still exempt from the agreement test: the SDF
`pie_slice` stored the full disc's bounding box rather than the wedge's. At 30° that claimed four
times the area the shape occupies — 20×20 for a wedge living in 10×5 — on the backend whose whole
selling point is exact bounds, and the CSG side had been reporting the true box all along.
`_sector_xy_bounds()` now derives the sector's own box from the apex, the two arc endpoints, and
whichever of the four axis directions the sweep passes through. Anchoring deliberately still uses
the full cylinder, as the CSG `pie_slice` does — `anchor` names a point on the cylinder the slice
was cut from — so an anchored slice lands in the same place on both backends.

`BOUNDS_NOT_YET_EXACT` is now an empty frozenset with a comment saying it must stay that way, and
`pie_slice` joins `test_both_backends_agree_on_bounds` with a stated size instead of an opt-out.
The new tests pin all eight interesting angles (0, 30, 90, 180, 200, 270, 359, 360) and then sample
the field around the box: a tight box is only correct if nothing is left outside it.

---

## T2b — Make the top level backend-neutral ✅

**Closes:** §12.2 item 2 (A-6) · **Implements:** PLAN M-2a, B-P1 · **Size:** M · **Risk:** low

`star`, `cone`, `egg`, `roof`, `text3d`, `path_text` and most of `shapes2d` are exported from the
top level but only build on CSG.

1. Give each a façade constructor that dispatches on the active backend, using the SDF equivalents
   that already exist (`star2d`, `ellipse2d`, `regular_ngon2d`, `trapezoid2d`, `keyhole2d`, …).
2. Where the SDF backend has no equivalent (`roof`, `text3d`, `path_text`), raise
   `UnsupportedByBackendError` with a hint rather than silently building CSG.
3. Re-point `_LAZY_EXPORTS` at the façade and regenerate `__init__.pyi`.
4. Add a test: for every top-level shape name, building it inside `use_backend("sdf")` either
   returns an SDF-backed shape or raises `UnsupportedByBackendError` — never a CSG shape.

## T3 — Stop the SDF fallback silently meshing ✅

**Closes:** §12.2 item 12 (PAR-1, C-1, B-5) · **Implements:** PLAN E-P6, O-6a · **Size:** M
**Risk:** medium — changes SDF behaviour

`SdfSolid.__getattr__` forwards any unimplemented name to `self.mesh()`, so `shape.up(5)` and
`shape.color("red")` quietly convert an exact field to a mesh and hand back a raw native handle
with no `backend` tag — the implicit conversion B-5 forbids.

1. **Directional moves** (`up`, `down`, `left`, `right`, `back`, `forward`, `fwd`, `move`, `rot`):
   implement natively on the SDF shape as thin wrappers over its exact `translate`/`rotate`. These
   are pure wins — cheap, exact, and they keep the field.
2. **Colour and display** (`color`, `color_this`, `recolor`, `hsl`, `hsv`, `highlight`, `ghost`):
   make `SdfSolid` carry colour as metadata that survives transforms and is applied when the field
   is realized. This is what C-19 needs before colour can join the `Shape` contract.
3. **Attachment properties** (`attachments`, `diff_config`, `tag_name`): add to
   `CSG_ONLY_FEATURES` so they refuse rather than mesh.
4. Make the fallback's last resort an explicit refusal, not `getattr(self.mesh(), name)`.

**Done when:** no public CSG shape method reaches the meshing fallback; a test asserts
`use_backend("sdf")` + `.up(5)` returns an SDF-backed shape with `backend == "sdf"`; the 19-name
gap list in §12.2 item 4 is empty.


**Landed.** The nine directional moves are real methods on `SdfSolid` (exact wrappers over its own
`translate`/`rotate`); colour is metadata carried on the field and applied when it is realized, so
`SdfSolid` now satisfies `Colorable` and `.color()/.ghost()/.hsl()` keep the shape in SDF-land;
the three attachment properties joined `CSG_ONLY_FEATURES`. The fallback is now a documented
`_MESH_OPERATIONS` allowlist — operations that genuinely consume mesh topology — and everything
else refuses, naming `.to_csg()`. No public CSG shape method reaches the mesher any more. Tests:
`test_sdf_shapes_keep_their_backend_through_moves_and_colour`,
`test_an_unknown_operation_refuses_instead_of_meshing`.


**Landed.** T0's guards had already stopped the silent wrong-backend builds; this closed the other
half — `ellipse`, `star`, `regular_ngon` and `trapezoid` are now dispatching façade constructors
(the SDF backend already had `ellipse2d`/`star2d`/`regular_ngon2d`/`trapezoid2d`), and the
top-level exports point at the façade. The remaining backend-module names refuse on the other
backend with a hint rather than building. `regular_ngon` gained `rounding`/`fn`/`fa`/`fs` on the
way — the facet ratchet caught that the façade version had dropped them, and it refuses `rounding`
on SDF where there is no rounded-corner ngon. Test:
`test_no_top_level_name_builds_on_the_wrong_backend`.

---

## T4 — Reconcile the parity records with the code ✅

**Closes:** §12.2 item 13 (PAR-3) · **Implements:** PLAN B-P1, B-P4 · **Size:** S · **Risk:** none

`docs/design/sdf-csg-compatibility.md` lists `projection`, `bounding_box`, `distribute_on_path`,
`inside`, `chain_hull`, `half_of`, `partition`, `round3d` and `offset3d` as gaps — all nine are
implemented. `projection` is simultaneously implemented on `SdfSolid` and listed in
`CSG_ONLY_FEATURES`, so the refusal never fires.

1. Decide `projection` on SDF: if the sampling implementation is sound, remove it from
   `CSG_ONLY_FEATURES`; if not, remove the method. The two records must agree.
2. Rewrite the design doc as a *current* gap list, or delete it and let `CSG_ONLY_FEATURES` +
   `SDF_ONLY_FEATURES` be the single source of truth (PAR-3 says they are).
3. Give each remaining exclusive entry its one-line reason inline, as PAR-3 requires.
4. Add a test that every name in `CSG_ONLY_FEATURES` is genuinely absent from the SDF shape, so
   the lists can never drift from the implementations again.

**Done when:** that test passes and the design doc either matches reality or is gone.


**Landed.** `SdfSolid.projection()` was meshing and returning a CSG 2-D shape while `projection`
sat in `CSG_ONLY_FEATURES` — an implicit cross-backend conversion whose refusal never fired. The
method is gone, so the refusal fires and names `.to_csg().projection()`. Each exclusive entry now
carries its reason inline, and `tests/test_backend_parity.py` fails if a listed name is
implemented on the other backend. `docs/design/sdf-csg-compatibility.md` was rewritten from
scratch: it had listed nine features as missing that had all shipped, and that stale list misled a
design review — it now leads with that warning and states the four real gaps.

---

## T5 — Close the facet-control backlog ✅

**Closes:** §12.2 item 2 (R-1) · **Implements:** PLAN R-P2, R-P3, R-P5, R-P6

**Landed — the backlog is empty.** Of the 50 entries the audit found, R-1a triage moved **32** out
of scope in three documented categories, and **18** were genuine and are fixed:

* *placement or measurement* — the copy distributors, `polar_to_xy`, `circle_circle_tangents`,
  `hex_offsets`, `PhillipsSpec.depth`;
* *the caller supplies the sampling* — `plot_revolution` (explicit angle/z lists),
  `cylindrical_heightfield` (explicit xrange/yrange), `bent_cutout_mask` (wraps the path it is
  given), `star`/`regular_ngon`/`supershape` (an explicit vertex count);
* *descriptors, not geometry* — the bezier handles, the metaball fields, the Platonic solids,
  `squircle_radius_fg`, and the `os_*` rim profiles, whose consumer owns the facet count.

Fixed: `Region.offset`/`round_corners`, `offset3d`/`round3d` (both copies), `rect_tube`,
`interior_fillet`, `Path3D.helix`, `Path2D.minkowski_sum_circle`, `Roundable.path_join`,
`attach_prism`, `offset_sweep`, `_prism_connector`, `Sweepable.spiral_sweep`,
`CsgSolid.edge_profile`/`edge_profile_asym`.

**A trap worth recording.** Three of these had a hardcoded facet count — `steps=16` on the rim
sweeps, `quad_segs=16` on the minkowski rounding. Resolving them from `frag_count()`
unconditionally *coarsened* the default output (a 2 mm roundover becomes 4 segments at `$fa=12`,
a 5 mm minkowski radius becomes 3 per quadrant), which two tests caught. The rule now is: use the
derived value only when a resolution was actually asked for, explicitly or ambiently; otherwise
keep BOSL2's own default. Ambient settings reach the geometry without changing what an unchanged
call produces.

---

## T6 — Document and test the `fn=0` opt-out ✅

**Closes:** §12.2 item 14 (R-5) · **Implements:** PLAN R-P6 · **Size:** S · **Risk:** none

`fn=0` means "ignore any ambient `fn`, use `fa`/`fs`" because `frag_count()` treats `fn < 3` as
unset — true but undocumented and untested.

1. Say so in `pybosl2/defaults.py`'s module docstring and in `use_defaults`' docstring.
2. Add a test: inside `use_defaults(fn=64)`, a call with `fn=0` produces the `fa`/`fs` result.
3. Mention it in the `fn` line of the `Args:` block of the most-used constructors (`cyl`, `sphere`,
   `circle`, `cuboid`).


**Landed.** Documented in `defaults.py`'s module header (with a worked example), in
`use_defaults`' `Note:`, in `resolve_facets`' `Returns:` and in `frag_count`. Test:
`test_fn_zero_opts_out_of_an_ambient_fn`.

---

## T7 — Generalise the minimum-argument check ✅

**Closes:** §12.2 item 15 (Q-4) · **Implements:** PLAN X-3, T-9a · **Size:** M · **Risk:** none

`test_argument_free_constructors_either_build_or_explain` covers only `pybosl2.solid`.

1. Extend it over `pybosl2.flat`, then the `pybosl2.parts` classes (construct with the catalogue
   name only), then `shapes2d`/`shapes3d`.
2. Keep the contract: build, or raise `ValueError` — never `AssertionError`/`TypeError`.
3. Expect finds: fix each as a P-1/E-4 defect rather than adding it to an exemption list.


**Landed.** The check is parametrised over `pybosl2.solid`, `pybosl2.flat`, `pybosl2.shapes2d` and
`pybosl2.shapes3d`, plus a parts probe that builds each from its catalogue name alone. It found
eight more E-4 violations on its first run (`arc`, `trapezoid`, `ring`, `round2d`, `shell2d`,
`hull`, `cross`, `round_corners`) — all converted — and one M-2 violation: `pybosl2.flat` had no
`__all__`. Tests: `test_argument_free_constructors_either_build_or_explain[4 modules]`,
`test_parts_build_from_their_catalogue_name_alone`.

---

## T8 — Class-ify the remaining function families ✅

**Closed:** §12.2 item 16 (P-8) · **Implements:** PLAN O-1, O-4, O-6 · **Size:** M
**Risk:** low, but API-visible

1. **Masks.** `Mask2D` and `Mask3D` own the profile factories — `Mask2D.roundover(4)`,
   `Mask3D.chamfer(...)`. The nine `mask2d_*`/`mask3d_*` names are now aliases *of* those
   staticmethods (`mask2d_roundover is Mask2D.roundover`), so there is one implementation, not a
   copy. `masking.py` gained the `__all__` it was missing.
2. **Metaballs.** `Metaball.sphere/cuboid/torus/capsule/disk/octahedron/connector`, plus
   `Metaball.at(position)` which returns the `MetaballSpec` the mesher consumes — so a scene reads
   `VNF.from_metaballs([Metaball.sphere(12).at([-14, 0, 0]), ...])` instead of pairing bare
   positions with fields by hand. The classes were also *named* `_Metaball`/`_MetaballSpec` with
   public aliases, i.e. backwards: every repr leaked a private name. Now the classes are
   `Metaball`/`MetaballSpec` with `_Metaball`/`_MetaballSpec` as the compatibility aliases.
3. **Turtles.** These were already classes, so the real wart was the command *bag*:
   `TurtleCommand(TurtleCommandType.MOVE, size=40)` for every step. `TurtleCommands` (mixed into
   both `Turtle2D` and `Turtle3D`) gives a method per command, generated from one table so the
   two turtles cannot drift: `Turtle2D().set_length(40).move().arc_left(radius=8)`. The command
   objects still work and are what the methods build; `command()` runs one directly. The command
   language moved from `turtle3d.py` to `pybosl2/turtle/commands.py` — it was only there by
   accident, and the method form needs it without importing a turtle.

Every old spelling still works (P-6, change-process rule 2); docs pages for masking, isosurface
and drawing were rewritten around the classes, and the docs build stays at zero warnings.

---

## T9 — Track BOSL2 feature coverage ✅

**Closed:** §12.2 item 17 (B2-1) · **Implements:** PLAN D-P7 · **Size:** M · **Risk:** none

B2-1 claimed feature parity with BOSL2 and nothing measured it.

`docs/_covgen.py` now generates `docs/bosl2_coverage.rst`: every one of the **56** `.scad` files in
BOSL2 v2.0.751 against the pybosl2 module that ports it, with a status and a note — **42 ported, 3
partial** (attachments' module tree, isosurface's 2-D analogues, the deprecated metric-screws
wrapper), **0 unported**, and 11 with nothing to port (OpenSCAD plumbing that Python or NumPy
already provides). It is linked from the docs index and cited from SPEC B2-1.

The upstream file list is **pinned** with its tree sha, so the docs build never needs the network;
`python3 docs/_covgen.py --refresh` re-reads GitHub and reports anything added or removed upstream.

`tests/test_bosl2_coverage.py` keeps it honest, because this is precisely the kind of document that
rots: it imports every module a row names (a rename would otherwise leave a row pointing at
nothing), rejects a `partial` row that does not say what is missing, requires a note on every row,
and fails if the committed page has drifted from the generator.

---

## T10 — Housekeeping ✅

**Size:** S each

- [x] `README.md` — the development section now opens with SPEC/PLAN as the normative pair, points
      at TASKS.md for open work and AGENTS.md as the index, and lists the four commands a change
      must pass (including `TMPDIR`).
- [x] `pybosl2/__init__.py` — `Color` was eager and pulled `webcolors` at import time. Now lazy,
      and `color.py` imports `webcolors` only to resolve a CSS colour *name* (hex is parsed
      locally). This was breaking **89 docs examples**: the PythonSCAD app's bundled Python has no
      webcolors, so `import pybosl2` raised inside the app and every example reported "Current top
      level object is empty". Guarded by
      `test_import_pybosl2_needs_no_optional_dependency` (SPEC A-4).
- [x] `effective_defaults()` now returns `dict[str, DefaultValue]` — a published alias
      (`bool | int | float | str | tuple[float, ...] | Anchor | Point | None`) checked against
      every default across the whole shape surface, so callers no longer get `Any` back (PLAN
      T-2). `None` in that union means "decide for me", per T-9b.
- [x] C-7 was true at runtime and false in the type system: `Path2D` is iterable and array-like,
      so every polyline API *accepted* one, but the ~20 typed `Sequence[Sequence[float]]` made
      `mypy --strict` reject the library's own return values. Added the `PathLike` alias
      (`pybosl2.paths`, re-exported at top level), applied it through the polyline surface and the
      constructors underneath it (`Path2D`, `Path3D`, `Bezier`, `as_path_list`, `_skin`,
      `path_copies`, …), and lifted `__array__` onto `Path` so the `ArrayLike`-typed SDF entry
      points accept a `Path` too. Guarded by
      `tests/test_exports.py::test_every_polyline_parameter_accepts_a_path`, which pairs the
      parameter *name* with the raw-nesting annotation — a matrix or a bbox is nested floats too,
      so shape alone is not enough to tell a polyline from a transform.
- [x] Two more ratchets in `tests/test_defaults.py`, because the message-based one had two blind
      spots that were still letting validation through:
      `test_no_bare_assert_stands_in_for_validation` (a message-less `assert` on a parameter — the
      form that erases completely under `python -O`; allowed only where an earlier `raise` in the
      same function already named that parameter to the caller) and
      `test_no_assertion_error_is_raised_directly` (`raise AssertionError(...)`, which is worse
      than an assert: it survives `-O` *and* tells the caller their input is an internal bug).
      Between them they found **19 more validating asserts**, all now `ValueError`. The
      message-based rule also matches parameter names on word boundaries now — a one-character
      parameter like `h` was matching inside any word of any message.
- [x] `docs/_rstgen.py` — stub generation now skips a module a committed page already documents
      with an `automodule` block. Promoting `path2d`/`path3d` to public categories had generated a
      second page for each, and `docs/paths/paths.rst` already covered them with curated prose and
      `exclude-members` lists — **266 duplicate-object warnings**. Guarded by
      `test_no_module_is_documented_by_two_pages`.
- [x] `Resolution`'s fields use `#:` comments instead of a docstring `Attributes:` block, which
      napoleon and autodoc were both rendering; `rect_tube` no longer documents `length` twice.
      The docs build is at **0 warnings**.
- [x] `docs/design/` holds exactly one note (`sdf-csg-compatibility.md`), re-checked against the
      code: its "remaining gaps" list had drifted again — the meshing fallback (T3) and SDF colour
      (C-19) were both closed, and the directional moves are native now. What is actually left is
      2-D SDF distribution, parts having no SDF form, and `pie_slice` bounds; the closed items are
      kept in a short section so the next reader can see the file is maintained.

---

## T11 — Cover the rejection paths 🔶 (SDF-only remainder)

**Serves:** E-4, DOC-2 · **Implements:** PLAN E-P1, E-P2 · **Size:** L, batchable

T0b turned 290 validating `assert`s into `if`/`raise` pairs. An `assert` line counted as covered
because it executed on every call; a `raise` line only counts when something triggers it — so the
conversion left **329 uncovered rejection paths**. `tests/test_validation_messages.py` closes them
module by module, asserting the *message* as well as the type, because E-4 is about the message
naming the fix.

**Progress: 329 → 4, and every one of those four needs the SDF backend.** Each remaining line is a
rejection that only the F-Rep path can reach — `flat.regular_ngon(rounding=)` and the two
`sdf/__init__` backend refusals need `current_backend() == "sdf"`, and `hull()`'s empty-mesh guard
needs a libfive mesh — so they stay uncovered wherever `libfive` is not installed. They are real
guards, not dead ones, so they are *not* marked `# pragma: no cover`; cover them from a
libfive-enabled run instead.

Everything else is either exercised by `tests/test_validation_messages.py` (360 cases) or marked
`# pragma: no cover` with the reason it cannot fire.

**What the tests keep finding.** Nine defects so far, each invisible until something exercised the
path: a `raise AssertionError` the ratchet missed because it is not an `assert` statement;
`path_text(size=[...])` producing a `TypeError` from a numeric comparison; a multi-line collinear
`assert` both conversion passes had skipped; a duplicated identical check in `regular_ngon`;
`Path2D.offset()` not propagating its own `closed` flag, so the open-path rejection is unreachable
from the public API; and several guards that cannot fire at all, now marked `# pragma: no cover`
with the reason rather than left as permanent holes. Three more `raise AssertionError` statements
in `partitions` (an unknown section type, an invalid path descriptor, an unknown section option) —
the ratchet only inspects `assert` statements, so a bare `raise AssertionError(...)` slips past it
whatever the message says.

Later rounds found more, all fixed as they surfaced:

* **A string anchor died as a `TypeError`.** `square(2, anchor="left")` reached the arithmetic in
  `dir2()` and failed with `bad operand type for unary -`. The eight copies of the
  `anchor.vector if isinstance(anchor, Anchor) else list(anchor)` idiom now go through one
  `_helpers.anchor_vector()`, which rejects the string form naming what to pass (E-4).
* **`ring_hook(hole="square")` was silently accepted** — the guard only fired for `HoleType`
  members, and a `HoleType` can only ever be `CIRCLE` or `D`, so it could never fire at all.
* **`partition_path(["comb 0x20"])` raised `ZeroDivisionError`** from `tan(2°) * width / length`;
  the LENGTHxWIDTH modifier now requires both to be positive.
* **`mask3d_roundover(corners=Anchor.NONE)` said "failed to generate cutter"** — an internal
  symptom rather than the cause. Both mask builders now say the corner selection was empty.
* **`path_tangents(uniform=False)` divided by zero before its own guard**, emitting two numpy
  RuntimeWarnings on the way to the error. It checks the segment lengths first now.
* **Nineteen more validating `assert`s**, in the two forms the original ratchet could not see: a
  bare `assert` (`regular_ngon` sides, `reuleaux_polygon` sides, `knuckle_hinge` segs, `egg`
  length, `egg_path` length, `Bezier.derivative` order, `BezierPatch.flat` n_degree,
  `cut_points` distances, `corner_profile` radius, `path_copies` spacing, `rot_resample` method,
  three `turtle3d` arc radii, the four bezier path-degree asserts) and `raise AssertionError`
  (`vertex_array`/`tri_array` cap combinations, `close_to_axis` axis, `extrude_from_to` coincident
  points, `partition_path` cut type, `nut` shape, `path_sweep` method). Both forms now have their
  own ratchet.
* **`Path2D._round_corners` and `Path2D._vector_angle3` were dead code** — `rounding.py` has its
  own `_round_corners`, and nothing called the `Path2D` copies. Deleted rather than tested.
* **Every `# pragma: no cover` in the repo was inert.** They were written as a standalone comment
  line inside the guard's body; coverage matches the pragma against a *line*, and a comment line
  is not executable, so nothing was excluded. All eight moved onto the `if`/`else` header with the
  reasoning in a comment below, and `test_no_cover_pragmas_are_attached_to_a_statement` now fails
  the build if a bare one comes back.

Two rejections turned out to be correctly typed as something other than `ValueError`:
`polygon_prism` raises `TypeError` for a non-sequence, and the quaternion divide-by-zero paths
raise `ZeroDivisionError`. Both are what a Python caller expects, so the tests assert those types
rather than forcing everything into `ValueError`.

The ratchet in `tests/test_defaults.py` was also sharpened: it now flags an `assert` whose message
names any parameter of its enclosing function, not just one containing `()` or `=`. That found 13
more validating asserts, all converted.

---

## T12 — Partitions: cover it, and find out why it was not covered ✅

**Serves:** E-4, P-8 · **Implements:** PLAN O-1c, X-7 · **Size:** M

`pybosl2/partitions.py` sat at **60%**. The reason was not missing tests: `shapes3d/base.py`
carried its own copy of all nine cut operators (`_half_mask`, `half_of`, the six axis halves,
`partition`), and `CsgSolid` did not inherit `Partitionable` at all. The mixin — documented in the
module header, published in `__all__`, referenced by the docs page, and named in the test file —
**was never executed**. The two copies had already drifted: the mixin pads a 2-D `center=` to 3-D,
the duplicate did not.

Deleting the duplicate (236 lines) and inheriting the mixin took partitions from 60% to 78% with
no new tests, and the STL-render suite confirms the swap changed no geometry. `PLAN O-1c` now
states the rule, and `test_bosl2_solid_gets_its_cuts_from_the_partitions_mixin` asserts the
identity of each method so a second copy cannot come back quietly.

New tests then took it to **100%**: every cut profile (span, amplitude, vertex counts, the
dovetail's undercut, facet response), the whole modifier grammar (`xflip`, `addflip`/`wave`,
`pinch:` in percent and degrees, `skew:`, `flat N`, `invert`, left-to-right ordering), the unit
tiles the mask builders repeat, the cut row's gap and centring behaviour, `partition_path`'s
assembly, and the `Partitionable` operators.

Two live bugs surfaced, both in code that had never run:

* **`altpath=` crashed.** `_ptn_path_redirect` added a 3-vector normal to a 2-D point —
  `operands could not be broadcast together with shapes (2,) (3,)`. So bending a cut pattern along
  another path, a documented BOSL2 feature, did not work at all.
* **`half_of(offset=...)` crashed.** It called the *native* `offset()` with pybosl2's own
  `radius=` spelling, which that API does not take.

One upstream quirk is now pinned rather than smoothed over: BOSL2 documents cutpath tiles as
``Y between -0.5 and 0.5``, but its own `sawtooth` reaches 1. We reproduce it (B2-1), and the test
says why.

---

## T15 — `from_svg` loses even-odd holes when the SVG has a viewBox ✅

**Size:** S · **Status:** fixed · **Reported against:** pybosl2 0.7.10,
shapely 2.1.2, svgelements 1.9.6, Python 3.14.6

`Region.from_svg` flattens a shape's nested subpaths into a solid blob whenever the SVG declares a
`viewBox`. A donut's centre, a plate's windows, the gaps in a radar icon's rings — all come back
solid. `clip_to_viewbox` defaults to True and `Region.from_svg` does not expose it, so every caller
with a viewBox'd SVG hits this.

**Reproduced.** One `<path>`, an outer square with a nested inner square, inside a `viewBox`:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <path d="M0,0 L100,0 L100,100 L0,100 Z M25,25 L75,25 L75,75 L25,75 Z"/>
</svg>
```

| call | holes | area |
|---|---:|---:|
| `Region.from_svg(file)` | 0 | 10000.0 |
| `region_from_svg(file, clip_to_viewbox=False)` | 1 | 7500.0 |
| *expected* | *1* | *7500.0* |

**Root cause.** `svg_element_groups()` clips each shape's rings to the viewBox before the even-odd
rule is applied. `_clip_rings()` goes through `_rings_to_shapely()`, which builds every ring as a
*filled* polygon and merges them with `unary_union` — so a nested ring, which even-odd would read
as a hole, is absorbed into the outer shape. `Region.even_odd` runs afterwards, by which point the
hole no longer exists. The function's own docstring says "even-odd", which it does not do; that is
worth fixing in the same change.

**The fix.** Make `_rings_to_shapely()` honour even-odd nesting rather than unioning filled
polygons: sort the rings by containment depth (a ring inside an odd number of others is a hole,
inside an even number is a shell) and build each as `Polygon(shell, holes)`. That carries holes
through the `intersection(mask)` clip, and the existing `Region.even_odd` pass then does what it
was meant to. Applying even-odd to the raw rings *before* clipping would also work.

Also expose `clip_to_viewbox` on `Region.from_svg`, which today only the module-level
`region_from_svg` accepts — that is the only way to opt out, and it should not have to be.

**Fixed.** `_rings_to_shapely()` builds shells-with-holes by even-odd nesting instead of unioning
filled polygons, so holes survive the `intersection(mask)` clip. `Region.from_svg` takes
`clip_to_viewbox` now, and clipping a drawing that already sits inside its viewBox is a verified
no-op rather than a shape change.

The nesting itself is not a second implementation: `Region.even_odd` already had it, including a
winding-agnostic interior probe with a long comment about the 97 clockwise rings in Wikipedia's
Flag_of_Portugal that a one-sided probe gets wrong. That logic came out as `inward_probe()` and
`nesting_depths()`, which both callers now share -- writing a private copy in `svg.py` is how
`partitions.py` earned T12.

Tests assert the hole count and the area, not that a region came back (PLAN X-8): the donut (1
hole, 7500), the clip being a no-op, `clip_to_viewbox` being reachable, and a three-deep case
(shell, hole, island → 2 polygons, 1 hole, 6800) because a containment-depth fix can get two levels
right and still flatten the third. All three geometry tests were confirmed to fail with the fix
reverted. The Flag_of_Portugal fixture -- 324 polygons, 60 holes -- is unchanged.

---

## T14 — Give parts an SDF form where they have one 🔶

**Serves:** S-46a, PAR-1, B-9 · **Size:** XL, phased · **Status:** phase 1 in progress

All 53 parts refuse on the SDF backend (`@csg_part`). The refusal is honest — every part builds
CSG geometry today — but it is blanket, and closing it properly means closing the gap between the
two backends rather than papering over it per part.

### What the gap actually is

Three measurements, all reproducible from the probes in this task's history:

| gap | size | where |
|---|---|---|
| façade parameters | **146 CSG parameters across 15 of the 19 shared constructors** are unreachable through `pybosl2.solid`, because the façade exposes only the intersection of the two backends | `cyl`/`cylinder`/`xcyl`/`ycyl`/`zcyl` drop 18–19 each, `rect_tube` 15, `tube` 9, `teardrop` 7, `prismoid` 6 |
| solid methods | **21 public members** of `CsgSolid` that `PyShape` lacks; 7 more are forwarded to the mesh | attachments (`attach`, `align`, `position`, `anchor_point`, `attachments`, `reanchor`, `reorient`, `orient`, `realize`), tagging/diff (`tag`, `tag_name`, `tag_this`, `diff`, `diff_config`, `intersect`), profiles (`edge_profile`, `edge_profile_asym`, `edge_mask`, `corner_profile`, `face_profile`), and `projection` |
| the parts idiom | **28 hand re-wraps** (`Bosl2Solid(x.shape, size=...)`) across 13 of the 15 parts modules | reaches for the native handle, which an SDF solid does not have |

Of `cubetruss`'s 8 parts, none converts by changing imports alone: 4 need the re-wrap removed,
2 need a tapered `regular_prism` the SDF backend cannot build, 1 needs an SDF chamfer edge mask,
1 needs both.

### The mechanism that has to change first

The façade forwards its own defaults, and `for_backend()` filters them down to what the target
constructor declares — **silently**. That is right for a façade-owned default, and wrong for a
value the caller actually asked for: today `solid.regular_prism(radius1=8, radius2=4)` would not
raise on the SDF backend, it would drop the taper and hand back a straight prism. `given_arguments()`
already separates "the caller gave this" (non-`None`) from "nobody did", so the information is
there; nothing acts on it.

**So: the façade exposes the union, not the intersection, and a caller-supplied argument the
active backend cannot honour raises `UnsupportedByBackendError` naming the parameter, the backend,
and what to do instead.** Silence is the one outcome that is not allowed. This inverts the rule
recorded under B-7 (façade = shared surface), so SPEC changes with it.

### Phases

1. **Make the façade refuse rather than drop.** 🔶 *Mechanism landed; the widening is the
   remaining work.* `refuse_unhonoured()` in `pybosl2/_backend.py` runs at the top of both
   backends' `construct()` and raises `UnsupportedByBackendError` naming every caller-supplied
   argument the target constructor cannot take. It needs no sentinel and no call-site churn: a
   value counts as asked-for when it **differs from the façade's own default** for that parameter,
   which is exactly what separates it from a default the façade forwards on the caller's behalf.
   Tessellation parameters (`fn`/`fa`/`fs`/`res`/`realign`) stay silent per B-9's carve-out;
   `circumscribe` deliberately does not, because on `regular_prism` it decides whether the polygon
   encloses the circle or is inscribed in it, which is real geometry.

   **It found a bug on the first run: `solid.cube(10, spin=45)` came back unrotated on the SDF
   backend**, with no error — `spin` is CSG-only, and `for_backend()` dropped it. Every façade
   argument that only one backend understands had the same hole.

   **The widening that actually blocks T14 is finished.** Asking which façade-missing parameters
   the parts library *passes* — rather than widening all 146 alphabetically — gave a much shorter
   list than expected: `regular_prism`'s taper (`radius1`/`radius2`/`shift`/`circumscribe`) and
   `prismoid`'s edge treatments (`rounding`/`chamfer` and their per-end forms). Both are now on the
   façade, both refuse by name on SDF, and **no part passes a shape argument the façade cannot
   carry**. `test_no_part_needs_a_shape_argument_the_facade_cannot_carry` keeps it that way.

   The gap is 146 → 136. What is left is a completeness backlog, not a blocker: the `cyl` family's
   19 apiece, `rect_tube`'s 15, `tube`'s per-end radii, the `texture`/`tex_*` family. Each carries
   the same pair of tests: it builds on CSG, it refuses by name on SDF.
2. **Give the Shape contract a backend-neutral nominal box.** ✅ `with_nominal_size(size, anchor=)`
   is on the `Shape` protocol and implemented on both backends: it returns a new shape around the
   same geometry carrying the nominal anchor box, and — like colour — the box rides the field as
   metadata, so it survives every exact transform rather than forcing a mesh. `bounds()` keeps
   reporting geometry, per S-2a.

   This replaces `Bosl2Solid(other.shape, size=[...])`, the idiom used at 28 sites across 13 of the
   15 parts modules. That idiom reads `.shape` off the solid, which an SDF solid does not have —
   asking raises rather than returning a handle — so a part written that way is CSG-only whatever
   else it does. The 28 call sites are converted in phase 3, with the parts that use them.
3. **Convert parts, module by module.** 🔶 **`hinges` is done — all five parts build on either
   backend**, and `tests/test_part_show.py::BACKEND_NEUTRAL_PARTS` records them, with a companion
   test that the list matches what actually builds so it cannot drift in either direction.

   The conversion is three mechanical changes per module: import the primitives from
   `pybosl2.solid` instead of `pybosl2.shapes3d`; swap `Bosl2Solid(x.shape, size=...)` for
   `x.with_nominal_size(...)`; annotate against the `Solid` protocol. `@csg_part` then simply
   comes off — **the question of per-part guard versus letting the primitives refuse answers
   itself**: a converted part needs no guard, because everything it calls already refuses
   correctly on its own, and an unconverted one is still caught by the primitives it imports.
   The blanket decorator is only needed while a module is unconverted.

   One protocol gap turned up: `Solid` declared none of the directional moves (`up`, `down`,
   `left`, `right`, `forward`, `back`), though both backends have had them all along. Code written
   against the contract — which is what a backend-neutral part is — could not use them without the
   checker objecting. They are on `Solid` now, with `multmatrix` and the anchoring methods.

   **Six modules converted; the façade-routable set is now exhausted.** `hinges`, `joiners`,
   `nema_steppers`, `sliders`, `screws` and both bearing modules, giving **12 part classes plus
   the bearing factories** that build on either backend, all pinned by `BACKEND_NEUTRAL_PARTS` and
   a per-part geometry-parity test.

   The rest are genuinely CSG-only, and it is worth recording why so nobody re-derives it: `walls`,
   `hooks` and `gears` build from `polygon().linear_extrude()`; `bottlecaps` and `modular_hose`
   from native `rotate_extrude`; `sliders`' `Rail` and `walls` from `VNF.polyhedron()`, which hands
   back a bare native; `cubetruss` and `tripod_mounts` through `chamfer_edge_mask`/`edge_mask`;
   `threading` through `spiral_sweep`; `wiring` through `path_sweep`. Each needs its 2-D or
   sweeping operation to gain an SDF form — phase 5's profile/mask work, not phase 3's.

   **Two constructor arguments turned out to be avoidable rather than blocking.** `Slider` passed
   `orient=` to `prismoid`, which is CSG-only — but `reorient()` is now on both backends and does
   the same thing; the construction and method forms were verified to give identical bounds before
   the swap. `Dovetail` called the native `hull()` on `.shape` handles, which the façade's `hull()`
   does on either backend. Prefer the method form in a part: it is what makes the part portable.
4. **Re-word the refusal on the parts that keep it.** ✅ `@csg_part` takes the reason now, and all
   36 guards across 11 modules carry one, so the message names *this* part and the operation that
   is in the way — "WireBundle sweeps the bundle along its route with path_sweep(), which a
   distance field cannot express" rather than "the parts library builds exact CSG geometry", which
   stopped being true once a third of the library was converted. Two tests hold the line: no
   refusal may fall back to the library-wide wording, and the named reason has to reach the
   message the caller reads.

### Closing the method gap (phase 5, and the larger half)

The 21 CSG-only methods are not one problem. Triaged by what they would actually take:

* **Attachments — the anchor arithmetic is done** 🔶. `anchor_point`, `reanchor`, `reorient` and
  `orient` now work on both backends, from one shared `Anchorable` mixin
  (`pybosl2/_anchoring.py`) rather than a copy per backend — the mistake `partitions.py` made
  (T12). The CSG implementations were **deleted**, not left alongside it.

  The reason recorded for their being CSG-only was simply wrong. `CSG_ONLY_FEATURES` said
  anchoring *"needs a shape's face and edge structure, which a distance field does not retain --
  there is nothing to anchor TO"*. It needs the bounding box, which an SDF shape knows exactly.
  `tests/test_anchoring_parity.py` runs the same call on both backends and requires the same
  answer, so they cannot drift.

  Two things fell out of the move. `reanchor()`'s anchor bookkeeping was silently dropped and the
  **entire suite stayed green** — nothing covered it, and it now has a test. And a ragged `bbox=`
  used to surface numpy's *"inhomogeneous shape"* message instead of naming what to pass (E-4);
  the shared guard says it properly.

  What is left of attachments is the half that holds **children** — `attach`/`align`/`position`
  record a placed child, and `realize()` combines them. That is native-tree work, and it is the
  next slice. CSG-only members: 21 → **17**.
* **Tagging and diff (6 names) — implementable, lower value.** `tag`/`tag_this`/`tag_name`/`diff`/
  `diff_config`/`intersect` are a naming scheme over the same tree; they need no geometry. Worth
  doing only after attachments, since they exist to serve them.
* **Profiles and masks — the chamfer mask is done** 🔶. The thing actually keeping `cubetruss`
  CSG-only was `chamfer_edge_mask()`, and it turned out not to need the profile machinery at all:
  a diamond bar is a square prism turned 45 degrees, so it builds from `cuboid().rotate()` on
  either backend instead of `polygon().linear_extrude()`. The two forms were checked to give the
  same solid and the same cut before the swap.

  The masking module's cutter pipeline is typed against the `Solid` contract now, so a mask made
  on either backend flows through `_orient_mask_along_edge`, `corner_profile(return_cutter=)` and
  the `Mask3D` factories. **`cubetruss` is converted: 5 of its 8 parts build on either backend**,
  `TrussFoot`/`TrussJoiner` refuse correctly on the tapered `regular_prism` they need, and
  `TrussClip` is guarded pending the discrepancy below.

  What is left of this bullet is the profile *family* — `edge_profile`/`corner_profile`/
  `face_profile` with an arbitrary `Path2D` mask, which stays CSG-only since 2-D geometry is a CSG
  notion; `edge_profile`'s named roundover maps onto the SDF's own `round()`/`chamfer()` and is
  the next easy piece.

* **`TrussClip`'s 6mm discrepancy: found, and it was PAR-5 again.** Bisecting the clip stage by
  stage on both backends put the divergence on one line -- the two box cuts that square off its
  ends. The field was right the whole time; `bounds()` was stale. `SdfSolid.difference()` returned
  `PyShape(sdf_fn, shape.mn, shape.mx, ...)`, keeping the base's box verbatim, so a cut that trims
  an end never showed up in the bounds.

  Trimming an arbitrary cut is not possible without the geometry, but one case is provable: a
  cutter that is a plain axis-aligned box, spanning the base's full cross-section on two axes and
  overhanging one end on the third, removes everything past that end. `_box_after_cutting()` does
  exactly that and nothing more -- a through-hole, a too-narrow cut, or a rotated cutter all leave
  the conservative box alone, and the tests check each of those, because **under**-reporting is
  worse than over-reporting: `mn`/`mx` is the meshing domain, so too small a box clips geometry.

  What makes the cutter recognisable is `cuboid_size`/`cuboid_center`, which only `cuboid()` sets
  and which rotate/scale/booleans all drop -- so a shape still carrying them is axis-aligned. One
  gap had to be closed for the clip: `multmatrix()` dropped the metadata even for a pure
  translation, which is just `translate()` spelt as a matrix. It keeps it now when the upper-left
  3x3 is the identity, and drops it for anything else.

  `TrussClip` agrees exactly on both backends now (33.18 x 7.8 x 19.6) and is in
  `BACKEND_NEUTRAL_PARTS`; **6 of cubetruss's 8 parts** build on either backend.

* **`walls`: 3 of 6 converted, via `Path2D.linear_extrude()`.** After the census put 2-D profile
  extrusion at the top of the remaining blockers, it turned out the SDF backend already implements
  the `linear_extrude` backend hook (`polygon_prism`) -- so `Path2D(profile).linear_extrude()`
  dispatches, where the native `polygon().linear_extrude()` pair the parts used is CSG-only.
  `NarrowingStrut`, `CorrugatedWall` and `ThinningTriangle` build on either backend now.

  **Checking the backend *tag*, not just that it built, caught two silent leaks.** Lifting the
  guards made `SparseWall` and `ThinningWall` "succeed" on the SDF backend while handing back
  `CsgSolid` geometry tagged `csg` -- precisely what S-46a exists to stop, and invisible to a
  bounds check. `SparseWall` unions 2-D polygons into a region before extruding (a region is a CSG
  notion) and `ThinningWall` builds from a VNF; both keep a guard, now naming those reasons, and
  `SparseCuboid` keeps one because it is a `SparseWall` clipped to a box.

* **`rotate_extrude()` on the SDF backend.** A revolve is the 2-D -> 3-D operation a distance
  field handles *best*: the solid's field at `(x, y, z)` is the profile's own 2-D field read at
  `(hypot(x, y), z)`, because every point's distance to a surface of revolution is its distance
  within the half-plane it lies in. So it is exact wherever `_polygon_sdf_xy` is -- no meshing, no
  approximation of the revolve -- and it handles concave profiles for the same reason. Partial
  angles reuse the sector cut and the exact sector bounds written for PAR-5's `pie_slice`.

  It is a backend hook now (`SolidBackend.rotate_extrude`), implemented on both, and
  `Path2D.rotate_extrude()` dispatches instead of calling `_require_csg`. `modular_hose` and
  `bottlecaps` are converted onto it; `HoseSegment` builds on either backend, while the bottle
  necks and caps still refuse -- their threads reach `spiral_sweep`, and the refusal now comes
  from the primitive that is actually missing rather than from a blanket part guard.

  One native quirk found on the way: `rotate_extrude(360.0)` positionally raises `TypeError: error
  during parsing`, while `rotate_extrude(angle=360.0)` is fine. The CSG backend passes it by
  keyword.

  With both extruders dispatching, `hooks` and `screw_drive`'s `PhillipsMask` converted too --
  the Phillips recess is a revolved profile with four extruded wings cut out of it, so it needed
  both. `RingHook` still refuses, but on `prismoid(rounding=)` now: the SDF prismoid has no
  vertical-edge rounding, which is a named gap in a constructor rather than a blanket part guard.

* **`SpurGear2d.shape` returns a `Path2D`.** It was a `Bosl2Shape2D` -- 2-D *geometry*, which is
  a CSG notion -- and that single return type was what kept all five gears CSG-only, since every
  3-D gear extrudes it. A gear perimeter is a closed outline, so a path is the more honest type
  anyway, and `Path2D.linear_extrude()` dispatches.

  A bore cannot ride along: one path cannot describe an outline with a hole in it. So `shape` is
  the perimeter, `bore` reports the diameter asked for, `region()` gives the outline-plus-hole as
  a `Region` for when 2-D geometry really is wanted, and `SpurGear` subtracts the bore as a
  cylinder -- the same solid the 2-D difference produced. `show()` renders the region's geometry
  and returns the path, so S-51 still holds.

  Two smaller things had to move with it. `convexity` was being *refused* by the SDF
  `linear_extrude` -- it is a preview hint for the CSG renderer, not geometry, so it now falls
  under B-9's tessellation carve-off; refusing it was keeping a plain spur gear off the backend
  over a rendering flag. And `HerringboneGear` mirrored its lower half with `scale([1, 1, -1])`,
  which the SDF `scale()` rejects as a non-positive factor; it uses `mirror([0, 0, 1])` now, which
  is what it meant and which both backends have.

  `SpurGear` and `HerringboneGear` build on either backend; a *helical* gear still refuses, on
  `linear_extrude(twist=)`, which a constant-cross-section prism genuinely cannot express.

* **`VNF.polyhedron()` dispatches through the backend.** It called `pythonscad.polyhedron`
  directly and handed back a bare native -- the same wart `chamfer_edge_mask` had -- so every mesh
  in the library was CSG-only by construction. It goes through `get_backend().polyhedron()` now,
  which means a **convex** mesh builds on either backend and a concave one is refused by the
  convexity check rather than quietly coming back as its own hull.

  The refusal turns out to be load-bearing: `WireBundle`'s swept tube and `Rail`'s V-groove are
  both non-convex, and both now say so precisely, at the operation that cannot do it, instead of
  through a part-level guard. `RegularPolyhedron` is the case that crosses over -- a Platonic
  solid is convex by definition.

  The change rippled: 14 sites wrapped the result again (`Bosl2Solid(vnf.polyhedron(), size=...)`),
  which double-wrapped once the call returned a wrapper, and about 30 signatures carried
  `Bosl2Solid` where a backend-neutral solid now flows. Two rounds of full-suite runs caught them
  all -- the second only after the first had been declared clean, which is the argument for
  running the whole suite rather than the touched files.

* **The SDF `regular_prism` anchored half a height too high — on every anchor, since it was
  written.** Found while converting `HexDriveMask`, whose hex recess is a hexagonal prism rather
  than an extruded hexagon: `regular_prism(6, radius=5, height=10, anchor=CENTER)` put the prism
  entirely *above* the origin on SDF and straddling it on CSG, so the same call placed the shape
  differently on the two backends. `polygon_prism()` builds sitting on z=0, and the anchor offset
  was applied to it as though it were already centred; it is centred first now.

  **The convergence test should have caught this and could not**: it skipped any façade
  constructor with a required argument, and `regular_prism` takes `sides`. It supplies arguments
  from a small table now instead of skipping, and I checked the widened test *does* fail with the
  bug put back before fixing it again.

  Three SDF tests had encoded the wrong placement -- they sampled at `z = height/2` for
  "interior", which is the top face once the prism is centred. They sample the centre now, and a
  new test pins the placement itself.

* **`RegularPolyhedron` crosses over**, and it is the case that shows why the convexity check was
  worth writing: a Platonic solid is convex by definition, so it is one of the few meshes in the
  library with an exact distance-field form. All five agree to 1e-6 on both backends. The nine
  meshes that stay CSG-only are refused *by the check*, at the operation that cannot do it,
  rather than by a blanket part guard.

**36 part classes** build on either backend, with no CSG leaks. What is left is no longer routing
work -- every remaining refusal names a specific missing capability:

| missing capability | parts |
|---|---|
| a non-convex mesh (no distance-field form) | 9 — `BevelGear`, `Rail`, `ThinningWall`, `ThreadHelix`, `WireBundle`, `Worm`, `WormGear`, both Manfrotto plates |
| `spiral_sweep` | 4 — `Screw`, `Nut`, `ThreadedRod`, `ThreadedNut` |
| 2-D geometry (hulls of circles) | 2 — `TorxMask`, `TorxMask2d` |
| `prismoid(rounding=)` | 0 — see below |

* **`RingGear` imported the CSG `cylinder` directly**, which is all that stopped it: its cavity is
  a `SpurGear`, which already built on either backend. Routing the body through the façade was the
  whole fix.

* **`Rack2d` follows `SpurGear2d` in returning a `Path2D`**, so `Rack` builds on either backend
  too. `RobertsonMask` needed nothing but its guard lifting -- it is a tapered prismoid
  intersected with a cone, and both have dispatched for a while; the guard was stale.

* **An explicit zero was being read as a request.** `RingHook` normalises `None` to `0` before
  forwarding -- `rounding=rounding if rounding else 0`, which parts do routinely -- and B-9's
  refusal treated that as an option the backend had to honour, turning the part away over a
  treatment it was *declining*. `refuse_unhonoured()` now skips a value that asks for nothing
  (`None`, `False`, or a numeric zero), which is the same no-op set the SDF `linear_extrude` has
  always used for `twist`/`scale`. A non-zero `rounding=` is still refused, and both halves have
  a test.

  `RingHook` builds on either backend now, verified by probing 30 points through the hook rather
  than trusting the envelope.

* **`SparseWall` builds its lattice from outlines, not a 2-D region.** `sparse_wall2d()` unioned
  native 2-D polygons and extruded the region, and a region is a CSG notion. It returns the list
  of outlines now, each extruded and unioned in 3-D -- the same solid, because extruding a union
  of overlapping outlines equals unioning their extrusions -- so `SparseWall` and `SparseCuboid`
  build on either backend.

  Matching bounds prove nothing for a lattice (a solid block has the same envelope), so the test
  probes the pattern itself: 120 points across struts and gaps, all agreeing. The probes are
  deliberately offset off the lattice pitch -- on the pitch a sixth of them land exactly on a
  strut edge, where a box probe catches a sliver the point sample misses, which reads as a
  disagreement and is not one.

* **The SDF `regular_prism` tapers now**, which was the last two parts' blocker.
  `tapered_polygon_prism()` applies the same construction the box `prismoid` uses -- interpolate
  the cross-section scale with height (clamped at the ends, so no per-point branch) and read the
  profile's own 2-D field in that scaled frame, dividing the sample point by the scale and
  multiplying the distance back, which is the standard rule for a uniform scale. Verified against
  CSG by sampling: wide at the bottom, gone at the top, with the same envelope.

* **Open: a rotated non-box shape reports a conservative SDF box.** `TrussFoot` and `TrussJoiner`
  turn their octagonal plugs half a facet, and the SDF `rotate()` computes the new box by
  transforming the old box's *corners* -- exact for a shape that fills its box (a cuboid does; a
  rotated cube agrees with CSG to the digit) and loose for one that does not. The octagonal prism
  comes out 31.36 across where CSG measures 22.17.

  The geometry is right and the box is a superset, so nothing is clipped -- `test_a_conservative_
  bounds_part_still_builds_the_right_solid` asserts exactly that, since **under**-reporting would
  clip the mesh. Closing it properly means carrying the profile outline on the shape, the way
  `cuboid_size` is carried, so a rotation can recompute the box from the outline rather than from
  the box.

* **Two more parity bugs came out of converting cubetruss.** `SdfSolid.half_of()` rejected the
  scalar `center=` form with `TypeError: 'float' object is not subscriptable` -- the CSG one
  documents and supports it ("a scalar distance to shift the plane along *v*"), so the same call
  worked on one backend and crashed on the other. And the `Solid` contract declared none of the
  partition family (`half_of`, `left_half` … `bottom_half`) though both backends implement all
  seven.
* **A silent-approximation bug came out of this triage, and is fixed.** `SdfBackend.polyhedron()`
  accepted a `faces` list and ignored it — its docstring said so — building the convex hull
  instead. Asking for an L-shaped prism gave back a solid with the notch filled, **the same
  bounding box**, and no sign anything was wrong; a probe in the notch reads solid on SDF and
  empty on CSG. It now tests convexity (every vertex on the inner side of every face plane) and
  refuses with `.to_csg()` when the faces bound anything else. For convex input the face
  half-spaces are exact, so both backends agree and nothing changes.
* **`projection` — permanently CSG-only.** A 2-D shadow is not derivable from a distance field,
  and meshing to answer it would cross backends silently. Already recorded and already refused
  (PAR-3); it stays a documented exclusion, not a gap.
* **The 146 parameters — triage into three.** (i) *Expressible*: tapers, chamfers and roundings
  that are ordinary SDF constructions (`prismoid` chamfer/rounding, `regular_prism`/`tube` per-end
  radii, `teardrop` caps). (ii) *Meaningless in a field*: `realign`, `circumscribe`, `fn`/`fa`/`fs`
  — these describe tessellation, and an SDF has none; the façade should accept and ignore them on
  SDF, with `effective_defaults()` saying so. (iii) *Mesh-only*: the `texture`/`tex_*` family, which
  needs a mesh to displace and belongs with the forwarded mesh operations.

**Order matters:** phase 1 unblocks phase 3, phase 2 unblocks phase 3, and attachments (phase 5a)
unblock more parts than phases 1–3 together. A reasonable first cut is 1 → 2 → 5a → 3, leaving the
long tail of parameters and the profile family for last.

---

## T13 — Replace the existence-only tests ✅

**Serves:** PLAN X-8 · **Size:** L, batchable per module

`assert isinstance(result, Bosl2Solid)` passes for every wrong answer that is still a solid, and
proves only that the call returned — which the absence of an exception already proved. T12 showed
what that costs: `partitions.py` had a suite of such checks that all passed while the code they
claimed to cover was never executed, and two of its features were outright broken.

**Done: 303 → 13 exempt, with a ratchet holding the line.** The eight biggest files went first:

| File | Before | After |
|---|---:|---:|
| `tests/test_shapes2d_object.py` | 50 | 12 (all deliberate type contracts, each paired with a measuring sibling) |
| `tests/test_regions.py` | 25 | 0 |
| `tests/test_shapes3d.py` | 22 | 0 |
| `tests/test_drawing.py` | 21 | 0 |
| `tests/test_miscellaneous.py` | 17 | 0 |
| `tests/test_sdf_shapes3d.py` | 15 | 0 |
| `tests/test_gears.py` | 10 | 0 |
| `tests/test_svg.py` | 10 | 0 |

`test_color.py`, `test_rounding.py`, `test_profiles.py`, `test_tripod_mounts.py`,
`test_screws.py`, `test_skin.py`, `turtle/test_turtle3d.py`, `test_sdf_skin.py`,
`test_shapes2d.py`, `test_native_ops.py`, `test_distributors.py`, `test_threading.py`,
`test_helpers.py`, `test_isosurface.py`, `test_masking_primitives.py` and `test_screw_drive.py`
followed — all to 0, then `test_hinges.py`, `test_hooks.py`, `test_joiners.py`,
`test_linear_bearings.py`, `test_nema_steppers.py`, `test_nurbs.py`, `test_polyhedra.py`,
`test_texture.py`, `test_walls.py`, `test_backend_matrix.py`, and then the whole tail —
`test_transforms.py`, `test_ball_bearings.py`, `test_bottlecaps.py`, `test_comparisons.py`,
`test_constants.py`, `test_cubetruss.py`, `test_defaults.py`, `test_init_stub.py`, `test_math.py`,
`test_modular_hose.py`, `test_part_show.py`, `test_paths.py`, `test_sliders.py`, `test_wiring.py`,
`test_backend_parity.py`, `test_backend_sdf.py` and `test_sdf_shapes2d.py`.

**303 → 13, and the rule now enforces itself.** `tests/test_assertion_quality.py` walks every test
in the suite and fails on any whose assertions are all `isinstance(...)` or `is not None`, unless
the test is named in its `_ALLOWED` table with a reason. A second test checks the table for stale
entries, so the exemption list can only shrink; a third feeds the detector the shapes it must
catch, since a ratchet that cannot fire is worth nothing (the same pattern as the polyline ratchet
in `test_exports.py`).

The 13 exemptions are the honest ones. Twelve are in `test_shapes2d_object.py`, where every 2-D
constructor and operator must hand back the `Bosl2Shape2D` wrapper rather than a bare native
object — and a bare native has a bounding box too, so no measurement can tell them apart; the
geometry is measured by the sibling test sharing each table. The thirteenth is `wrap()`, whose
bounds re-enter the native op and never return; `test_stl_render.py` measures it against the
real app instead.

**Nine bugs came out of the sweep**, every one behind a test that could not fail: all eight
`# pragma: no cover` markers were inert (comment-line placement); `Partitionable` was dead code
duplicated in `shapes3d/base.py`; `altpath=` and `half_of(offset=)` both crashed;
`right_triangle(chamfer=)` was a no-op and `rounding=` grew the triangle; `linear_extrude(scale=2)`
silently dropped a scalar; `cone(chamfer=)` produced invalid geometry; every SDF half-cut kept an
octant rather than a half; `corner_profile()` cut inside out; and `Mask3D.chamfer()` returned the
roundover cutter verbatim.

Two measuring techniques came out of the parts files and are worth reusing. **Slice to see a
taper**: `solid & cuboid([100, 0.2, 100]).translate([0, y, 0])` gives the local width at *y*, so
`Dovetail(taper=)` — invisible to a bounding box, which is the wide end either way — is now pinned
at three stations along the slide. **Probe to see a hole**: `_native_bounds()` returns `None` for
an empty solid, so intersecting a small cube with the model says whether material is there. That
turns `NemaMountMask` from "returns a solid" into "all four screw holes are open, the plate corner
is not, and `atype=FULL` bores the centre while `SCREWS` leaves it solid".

The same probe generalises to **thickness**, not just presence: reading `size[0]` of the probe
intersection gives the wall thickness at a point, which is what finally pinned
`ThinningTriangle(diagonly=True)` — same outline, same bounding box as the full form, but the
upright and the base thin back from 4 mm to the 3 mm web while the hypotenuse keeps its rim.
Where the difference is a *count* rather than a dimension, the emitted program is cheaper than
probing: each `SparseWall` strut is one `polygon(`, so the lattice's response to `maxang`,
`max_bridge` and `strut` is 16/12/10 ribs against the limits that produced them.

`Mask3D.chamfer()` was the ninth bug the sweep turned up, and the worst-hidden: it called
`corner_profile(children=mask2d_chamfer(...))`, but `corner_profile()` documents `children` as
"accepted for call-site compatibility; unused" and drops it on the floor. So the chamfer factory
returned the *roundover* cutter — `repr()`-identical, bbox-identical, three existence-only tests
green. It now builds its own cutter (the corner block intersected with the three edge-chamfer
bars, which is the surface `cuboid(chamfer=)` produces), and `test_stl_render.py` renders both
cutters and checks the volume each takes off a 20 mm cube: 384 for the chamfer against the
closed form, ~244 for the roundover.

One op resists measurement entirely: **`Bosl2Solid.wrap()` never returns its bounds.** The call
itself is instant (the native op is lazy), but asking the wrapped solid for `bounds()` -- or even
its program text -- re-enters the native `wrap` and hangs. Its test keeps the type assertion, says
why, and points at `test_stl_render.py`, which measures it against the real app.

The count also excludes `assert x is None` now: that *is* a content assertion (the helper returns
None for bad input), unlike `is not None`. That correction alone accounted for 20 of the
apparent 110.

Parts get catalogue arithmetic rather than magic numbers: an M6 nut measures 10mm across the
flats and `10 * 2/sqrt(3)` across the hex points, a tapped hole is cut at the thread diameter
while a clearance hole is wider, and `close < normal < loose` fits are ordered. Sweeps and prisms
that return a **VNF** are measured through `vertices` / `faces` / `volume()`: a rim treatment must
take material off (`volume` down) and add points to the rim, without moving the prism's envelope.

The masking family (`corner_profile`, `face_profile`, `edge_profile`, `edge_mask`) is measured by
`realize()`ing the lazy attachment and probing with `inside()`: assert the treated edge or corner
is gone *and* that the faces, the neighbouring untreated edges and the interior all survive. That
pairing is what catches an inverted cutter.

**`corner_profile()` cut inside out** — found and fixed. `masking._corner_cutter()` built a
`2 * radius` block and put the subtracted sphere on the body's *corner* instead of one radius in,
so the cutter was the corner block *minus a ball at the corner*: subtracting it scooped out the
inside of the solid and left the corner standing. Measuring
`cuboid([20, 20, 20]).corner_profile(radius=3).realize()` showed (5,5,5) and (8,8,8) reported
outside while the corner region stayed solid. The cutter is now the radius-sided block filling the
corner minus the sphere at the inner point, and `test_profiles.py` asserts the corner is gone
while the interior, the neighbouring edge and the face centres all survive.

Convert them per X-8, module by module — bounds for solids, point counts and spans for paths,
area for regions, vertex counts and volume for meshes. Where the subject carries no tracked size
(the partition mask builders, a 3-D stroke's union of primitives), read the emitted OpenSCAD back
instead: the polygon outline, or the count of `cylinder(`/`sphere(`/`rotate_extrude` calls against
the path's own point count.

Keep the type assertion where the *type* is the claim — "every constructor returns the wrapper",
"a Region enters the same pipeline as a shape" — say so in the test name, and pair it with a
sibling that measures.

**What the conversion keeps finding.** Every file so far has hidden at least one real defect:

* **`right_triangle(chamfer=)` did nothing, and `rounding=` grew the triangle** instead of
  rounding it. Both went through `offset(delta=+n).offset(delta=-n)`, which restores the sharp
  corner; the rounding case only did the outward half, so `right_triangle([15, 10], rounding=2)`
  came back 18.95 x 13.9. Both now treat the corners in place, like `square()` does.
* **`linear_extrude(scale=2)` silently ignored the scale.** The native honours a *vector* scale
  and drops a scalar, so a uniform taper came out a plain prism. The wrapper normalises it now.
* **`cone(..., chamfer=)` / `cone(..., rounding=)` produced invalid geometry.** A cone's top
  radius is 0, so treating that rim pushed the revolved profile across the axis: OpenSCAD printed
  "Children of rotate_extrude() may not lie across the Y axis" to stderr and returned a solid with
  no bounding box. The old test asserted `isinstance` and passed — one even carried the comment
  *"bounds() on chamfered cone requires valid rotate_extrude params"*. `cyl()` now rejects any rim
  treatment larger than that end's radius (E-4), which also catches `cyl(radius=10, rounding=12)`.
* **`osimport()` is lazy**, so its geometry must be measured while the file still exists — the
  first conversion measured after the `with tempfile...` block and got `-inf` bounds.
* **Every SDF half-cut kept an eighth of the solid, not a half.** `SdfSolid.half_of()` built its
  mask by shifting a cube `-s/2` on *all three* axes rather than along the cut normal, so
  `left_half()` returned an octant — and `right_half()` and `back_half()` returned the *same*
  octant as each other. `left_half()` even kept the +X side. All six were covered only by
  `assert half is not None`; they now assert the exact box, and that the box is 5 x 10 x 10 rather
  than an eighth's 5 x 5 x 5.
* **Two SDF tests could not fail.** `test_minkowski_difference_delegates` and
  `test_partition_returns_two_parts` wrapped their bodies in
  `except (AttributeError, ValueError, TypeError): pass`. The cause is environmental — without
  libfive the numeric mock's `to_csg()` yields a stand-in the CSG operators reject — so they now
  measure properly and carry a `needs_csg_operable_mesh` skip that says so out loud.

---

## Keeping this file honest

The mapping table at the top is the contract between this file and the spec. Two ways it goes
stale, both cheap to prevent:

* A task lands but §12.2 keeps its row — fix by moving the row to §12.1 **in the same commit** as
  the code, per SPEC §13 rule 4.
* A new defect is found and only lands here — always add the §12.2 row first; this file never
  holds work the spec does not know about.

When a review turns up something new, the order is: reproduce it as a user would, add the §12.2
row citing the requirement it violates, then add the task here with its plan rules and its test.
