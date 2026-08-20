# pybosl2 — Conformance Work Queue

Ordered, checkable work to bring the code up to [SPEC.md](SPEC.md), with the Python mechanics in
[PLAN.md](PLAN.md). Every task names the requirements it closes, the files it touches, and how you
know it is done. **[SPEC.md §12.2](SPEC.md#122-open) stays the authoritative list of what is open**
— this file is how to close it. When a task lands, move its row from §12.2 to §12.1 in the same
commit.

Definition of done for **every** task: `pytest` green, `mypy --strict pybosl2` clean,
`ruff check . && ruff format .` clean, and the spec's conformance table updated.
Run with `TMPDIR` pointed at a volume with room (PLAN X-6).

## Order and why

```
  T1 Shape merge ──► T2 façade defaults ──► T3 SDF fallback ──► T4 parity records
   (contract)          (uses the contract)    (needs T1's Self)   (reconcile the lists)

  T5 facet backlog ─── independent, batchable by module
  T6 fn=0 · T7 min-arg check · T8 class-ify · T9 BOSL2 matrix ─── independent
```

T1 → T2 because the façade signatures are easier to change once `Shape` fixes what "a shared
argument" means. T2 → T3 because the fallback fix needs the shared surface to know what an SDF
shape *should* implement. T5–T9 are independent and can be picked up in any order or in parallel.

---

## T1 — Merge `Solid` and `Flat` into one `Shape` contract

**Closes:** C-15, C-16, C-17, C-18 · **Size:** M · **Risk:** low (contract change, not geometry)

Today `Solid` lives in `_backend.py` and `Flat` in `flat.py`, duplicating the `backend` tag, three
boolean operators, four transforms and `bounds()`. That duplication is why `Flat` was `Any`-typed
long after `Solid` was not, and why it lacked `bounds()` until recently.

1. In the L1 contract module declare `Shape(Protocol)` with the universal surface — `backend`,
   `__or__`/`__and__`/`__sub__`, `translate`/`rotate`/`scale`/`mirror`/`multmatrix`, `bounds()` —
   typing shared members `-> Self` (PLAN T-6a).
2. Redeclare `Flat(Shape, Protocol)` with only `linear_extrude`, `rotate_extrude`, `offset`, and
   `Solid(Shape, Protocol)` with only `projection` and the 3-D-only surface. Remove every member
   that is now inherited — a re-declaration re-opens the drift.
3. Re-point `flat.py` and `solid.py` at the new declarations; keep `Flat`/`Solid`/`Shape2D` exported
   (add `Shape` to `_LAZY_EXPORTS` and `__init__.pyi`).
4. Confirm the four implementations still satisfy the protocols: `CsgSolid`, `SdfSolid`,
   `CsgShape2D`, `PyShape2D`.

**Done when:** `mypy --strict` is clean; a test asserts `flat | solid` is rejected statically
(`assert_type` / a `# type: ignore[operator]` that mypy reports as unused if the error disappears);
`tests/test_init_stub.py` passes with `Shape` exported.

---

## T2 — Give the façade ownership of shared defaults

**Closes:** B-3, PAR-5 (§12.2 item 1) · **Size:** L · **Risk:** medium (behaviour-affecting)

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

---

## T3 — Stop the SDF fallback silently meshing

**Closes:** PAR-1, C-1, B-5 (§12.2 item 4) · **Size:** M · **Risk:** medium (changes SDF behaviour)

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

---

## T4 — Reconcile the parity records with the code

**Closes:** PAR-3 (§12.2 item 5) · **Size:** S · **Risk:** none

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

---

## T5 — Close the facet-control backlog

**Closes:** R-1 (§12.2 item 3) · **Size:** L, but fully batchable · **Risk:** low

50 pinned entries in `tests/test_facets.py`. First triage each against **R-1a**: does the output
have an observable facet count? If not, it is not debt — delete the entry with a one-line note.

*Likely not debt (placement/measurement only, ~13):* `distributors` (10 rot/arc/sphere copies),
`transforms.polar_to_xy`, `geometry.circle_circle_tangents`, `parts/wiring.hex_offsets`,
`parts/screw_drive.PhillipsSpec.depth`.

*Genuine debt, batched by module:*

- [ ] `regions.py` — `Region.offset`, `Region.round_corners` (2) — highest value: rounding a region is a headline operation
- [ ] `shapes3d/base.py` — `edge_profile`, `edge_profile_asym`, `offset3d`, `round3d` (4)
- [ ] `skin.py` — `spiral_sweep`, `os_circle`, `os_smooth`, `os_teardrop` (4)
- [ ] `shapes2d/curves.py` — `star`, `supershape`, `squircle_radius_fg` (3)
- [ ] `parts/polyhedra.py` — the five `RegularPolyhedron` factories (5)
- [ ] `isosurface.py` — `mb_sphere`, `mb_capsule`, `mb_disk`, `mb_connector` (4)
- [ ] `rounding.py` — `attach_prism`, `bent_cutout_mask`, `path_join` (3)
- [ ] `surfaces3d.py` — `cylindrical_heightfield`, `interior_fillet`, `plot_revolution` (3)
- [ ] `beziers.py` — `Bezier.begin`/`tang`/`joint`/`end` (4)
- [ ] `miscellaneous.py` — `offset3d`, `round3d` (2)
- [ ] `path2d.py` `minkowski_sum_circle`, `path3d.py` `helix` (2)

Each batch: add `fn`/`fa`/`fs` keyword-only defaulting to `None`, forward to every
sub-construction (PLAN R-P2), document the three in `Args:`, and remove the entries from
`KNOWN_WITHOUT_FACETS`.

**Done when:** `KNOWN_WITHOUT_FACETS` is empty and `tests/test_facets.py` still passes.

---

## T6 — Document and test the `fn=0` opt-out

**Closes:** R-5 (§12.2 item 6) · **Size:** S · **Risk:** none

`fn=0` means "ignore any ambient `fn`, use `fa`/`fs`" because `frag_count()` treats `fn < 3` as
unset — true but undocumented and untested.

1. Say so in `pybosl2/defaults.py`'s module docstring and in `use_defaults`' docstring.
2. Add a test: inside `use_defaults(fn=64)`, a call with `fn=0` produces the `fa`/`fs` result.
3. Mention it in the `fn` line of the `Args:` block of the most-used constructors (`cyl`, `sphere`,
   `circle`, `cuboid`).

---

## T7 — Generalise the minimum-argument check

**Closes:** Q-4 (§12.2 item 7) · **Size:** M · **Risk:** none

`test_argument_free_constructors_either_build_or_explain` covers only `pybosl2.solid`.

1. Extend it over `pybosl2.flat`, then the `pybosl2.parts` classes (construct with the catalogue
   name only), then `shapes2d`/`shapes3d`.
2. Keep the contract: build, or raise `ValueError` — never `AssertionError`/`TypeError`.
3. Expect finds: fix each as a P-1/E-4 defect rather than adding it to an exemption list.

---

## T8 — Class-ify the remaining function families

**Closes:** P-8 (§12.2 item 8) · **Size:** M · **Risk:** low, but API-visible

1. `masking.mask2d_*` / `mask3d_*` → a `Mask2D`/`Mask3D` class (or a `Profile` class with
   classmethod factories), keeping the free functions as thin aliases for one release.
2. `isosurface.mb_*` → `Metaball` subclasses or classmethod factories on `Metaball`.
3. `turtle2d`/`turtle3d` → one `Turtle` class with a 2-D and 3-D mode (`turtle3d.Turtle` exists —
   unify rather than duplicate).

Each needs a deprecation path (P-6, change-process rule 2) and docs updates.

---

## T9 — Track BOSL2 feature coverage

**Closes:** B2-1 (§12.2 item 9) · **Size:** M · **Risk:** none

B2-1 claims feature parity with BOSL2, and nothing measures it.

1. Generate a matrix of BOSL2 `.scad` modules against pybosl2 modules, marking ported / partial /
   unported with a note.
2. Put it under `docs/` so it publishes, and regenerate it in CI or via a script like
   `docs/_specgen.py`.
3. Cite it from SPEC B2-1 so the claim has evidence.

---

## T10 — Housekeeping

**Size:** S each

- [ ] `README.md` — mention `SPEC.md`/`PLAN.md`/`TASKS.md` in the contributor section (the reference links are already there).
- [ ] `pybosl2/__init__.py` — `from pybosl2.color import Color` is eager and pulls `webcolors` at import; make it lazy like everything else (A-4).
- [ ] `effective_defaults()` returns `dict[str, Any]` — narrow it once the façade owns its defaults (T2), since the value types become knowable.
