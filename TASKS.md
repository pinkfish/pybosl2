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

| §12.2 | Requirement | Task | Size |
|---|---|---|---|
| 1 | C-1 / E-3 | [T0](#t0--make-the-backend-tag-tell-the-truth) ✅ | S |
| 2 | A-6 | [T2b](#t2b--make-the-top-level-backend-neutral) | M |
| 3 | E-4 | [T0b](#t0b--convert-user-input-asserts-to-valueerror) | L |
| 4 | C-14 | [T0c](#t0c--make-partshape-a-property) | M |
| 5 | DOC-2 / D-P5 | [T0e](#t0e--document-the-façade) | M |
| 6 | A-7 | [T0d](#t0d--fix-the-broken-export) | XS |
| 7 | S-46a | [T0f](#t0f--make-parts-honour-the-active-backend) | L |
| 8 | S-51 | [T0f](#t0f--make-parts-honour-the-active-backend) step 3 | — |
| 9 | B-3 / PAR-5 | [T2](#t2--give-the-façade-ownership-of-shared-defaults) | L |
| 10 | C-15 … C-19 | [T1](#t1--merge-solid-and-flat-into-one-shape-contract) | M |
| 11 | R-1 | [T5](#t5--close-the-facet-control-backlog) | L |
| 12 | PAR-1 / C-1 / B-5 | [T3](#t3--stop-the-sdf-fallback-silently-meshing) | M |
| 13 | PAR-3 | [T4](#t4--reconcile-the-parity-records-with-the-code) | S |
| 14 | R-5 | [T6](#t6--document-and-test-the-fn0-opt-out) | S |
| 15 | Q-4 | [T7](#t7--generalise-the-minimum-argument-check) | M |
| 16 | P-8 | [T8](#t8--class-ify-the-remaining-function-families-) ✅ | M |
| 17 | B2-1 | [T9](#t9--track-bosl2-feature-coverage-) ✅ | M |
| — | housekeeping | [T10](#t10--housekeeping-) ✅ | S |
| — | E-4 follow-up | [T11](#t11--cover-the-rejection-paths--sdf-only-remainder) 🔶 | L |

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

## Keeping this file honest

The mapping table at the top is the contract between this file and the spec. Two ways it goes
stale, both cheap to prevent:

* A task lands but §12.2 keeps its row — fix by moving the row to §12.1 **in the same commit** as
  the code, per SPEC §13 rule 4.
* A new defect is found and only lands here — always add the §12.2 row first; this file never
  holds work the spec does not know about.

When a review turns up something new, the order is: reproduce it as a user would, add the §12.2
row citing the requirement it violates, then add the task here with its plan rules and its test.
