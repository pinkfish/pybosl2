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
| 1 | C-1 / E-3 | [T0](docs/tasks-archive.md#t0--make-the-backend-tag-tell-the-truth) ✅ | S |
| 2 | A-6 | [T2b](#t2b--make-the-top-level-backend-neutral) ✅ | M |
| 3 | E-4 | [T0b](#t0b--convert-user-input-asserts-to-valueerror) ✅ | L |
| 4 | C-14 | [T0c](#t0c--make-partshape-a-property) ✅ | M |
| 5 | DOC-2 / D-P5 | [T0e](#t0e--document-the-façade) ✅ | M |
| 6 | A-7 | [T0d](#t0d--fix-the-broken-export) ✅ | XS |
| 7 | S-46a | [T0f](#t0f--make-parts-honour-the-active-backend) ✅ | L |
| 8 | S-51 | [T0f](#t0f--make-parts-honour-the-active-backend) step 3 ✅ | — |
| 9 | B-3 / PAR-5 | [T2](docs/tasks-archive.md#t2--give-the-façade-ownership-of-shared-defaults) ✅ | L |
| 10 | C-15 … C-19 | [T1](docs/tasks-archive.md#t1--merge-solid-and-flat-into-one-shape-contract) ✅ | M |
| 11 | R-1 | [T5](docs/tasks-archive.md#t5--close-the-facet-control-backlog) ✅ | L |
| 12 | PAR-1 / C-1 / B-5 | [T3](docs/tasks-archive.md#t3--stop-the-sdf-fallback-silently-meshing) ✅ | M |
| 13 | PAR-3 | [T4](docs/tasks-archive.md#t4--reconcile-the-parity-records-with-the-code) ✅ | S |
| 14 | R-5 | [T6](docs/tasks-archive.md#t6--document-and-test-the-fn0-opt-out) ✅ | S |
| 15 | Q-4 | [T7](docs/tasks-archive.md#t7--generalise-the-minimum-argument-check) ✅ | M |
| 16 | P-8 | [T8](docs/tasks-archive.md#t8--class-ify-the-remaining-function-families-) ✅ | M |
| 17 | B2-1 | [T9](docs/tasks-archive.md#t9--track-bosl2-feature-coverage-) ✅ | M |
| — | housekeeping | [T10](docs/tasks-archive.md#t10--housekeeping-) ✅ | S |
| — | E-4 follow-up | [T11](docs/tasks-archive.md#t11--cover-the-rejection-paths-) ✅ | L |
| — | P-8 / coverage | [T12](docs/tasks-archive.md#t12--partitions-cover-it-and-find-out-why-it-was-not-covered-) ✅ | M |
| — | test quality | [T13](docs/tasks-archive.md#t13--replace-the-existence-only-tests-) ✅ | L |
| — | S-46a / PAR-1 | [T14](docs/tasks-archive.md#t14--give-parts-an-sdf-form-where-they-have-one-) 🔶 | XL |
| — | bug | [T15](docs/tasks-archive.md#t15--from_svg-loses-even-odd-holes-when-the-svg-has-a-viewbox-) ✅ | S |
| 2 | S-2b | [T16](docs/tasks-archive.md#t16--one-bounds-type-everywhere) ✅ | M |
| 3 | C-20 / C-21 / C-22 | [T17](docs/tasks-archive.md#t17--make-the-contract-the-whole-object) ✅ | L |
| 4 | S-19a / S-19b / S-19c | [T18](docs/tasks-archive.md#t18--make-a-sweep-return-a-solid) ✅ | M |
| 5 | S-53 / S-54 / S-55 | [T19](docs/tasks-archive.md#t19--give-the-library-a-way-out) ✅ | M |
| 6 | E-1 / E-5 / E-6 / E-7 | [T20](docs/tasks-archive.md#t20--make-the-error-contract-usable) ✅ | M |
| 7 | A-8 / A-9 | [T21](docs/tasks-archive.md#t21--export-the-families-whole) ✅ | S |
| 8 | S-26a … S-26c | [T22](docs/tasks-archive.md#t22--make-the-masks-obey-the-librarys-own-rules) ✅ | L |
| 9 | DOC-5 / DOC-6 / Q-6 | [T23](docs/tasks-archive.md#t23--type-check-the-examples-and-build-a-front-door) ✅ | M |
| 3 | spec maintainability | [T26](#t26--make-the-requirements-measurable) ✅ | M |
| 3 | spec maintainability | [T27](#t27--generate-the-prose-from-the-registry) ✅ | M |
| 3 | spec maintainability | [T38](#t38--triage-every-requirement) ✅ | L |
| 3a | 19 unchecked rules | [T39](#t39--close-the-nineteen) ✅ | M |
| 5 | Q-7 | [T28](#t28--test-what-ships) ✅ | XS |
| 4 | A-1 / A-6 / A-10 / PAR-1 | [T29](#t29--make-the-layering-true) ✅ | M |
| 9 | PAR-3 / B-5 / B-P4 | [T34](#t34--decide-what-fill-means-on-a-distance-field) ✅ | S |
| 7 | G-1 … G-5 | [T30](#t30--group-the-arguments-that-travel-together) 🔶 | L |
| 7a | PLAN D-P4 / DOC-2 | [T35](#t35--give-every-public-callable-an-args-section) ✅ | M |
| 7b | PLAN O-6b | [T36](#t36--give-text-the-anchor-language) ✅ | S |
| 7c | G-8 / S-34 / S-35 | [T37](#t37--build-texture-or-stop-advertising-it) ✅ | L |
| 7 | B-3 / G-4 | [T31](#t31--slim-the-façade) ✅ | M |
| 6 | C-21 / PLAN S-2 | [T32](#t32--close-the-two-rules-that-only-half-closed) ✅ | S |
| 8 | C-23 / C-20 | [T33](#t33--type-the-contract) ✅ | M |
| 10 | PAR-4 / PAR-5 / S-2b | [T40](#t40--close-the-sdf-option-gaps) 🔶 | L |
| 11 | C-21 / B2-3 | [T40](#t40--close-the-sdf-option-gaps) ✅ | S |
| 12 | PAR-4 / PAR-5 / S-34 | [T41](#t41--build-texture-on-the-sdf-backend) ✅ | M |
| 13 | C-21 | [T41](#t41--build-texture-on-the-sdf-backend) ✅ | S |
| 14 | PAR-4 / PAR-5 | [T42](#t42--close-the-cylinder-rim-options) 🔶 | M |
| 15 | PAR-4 / PAR-5 / S-2b | [T43](#t43--give-prismoid-its-edge-treatments) ✅ | S |
| 16 | PAR-4 / PAR-5 / S-2b / C-21 | [T44](#t44--build-rect_tube-from-the-two-prismoids-it-is) ✅ | M |
| 17 | PAR-4 / PAR-5 / E-5 | [T45](#t45--clip-the-fillet) ✅ | S |
| 18 | PAR-4 / PAR-5 / C-21 / B2-1 | [T46](#t46--the-teardrops-own-ends) ✅ | S |
| 19 | PAR-4 / PAR-5 / B2-1 | [T47](#t47--trimcorners-and-the-instrument-that-was-there-all-along) ✅ | S |
| 20 | PAR-4 / PAR-5 / S-2b | [T48](#t48--the-last-option-gap) ✅ | S |
| 21 | S-2b / PAR-5 | [T49](#t49--measure-the-bounds-instead-of-writing-them) ✅ | M |
| 22 | A-1 / PAR-1 / B-4 | [T50](#t50--audit-the-layering-debt) 🔶 | M |

**T0–T23 are all done**, and every item from the API review that opened this wave is closed —
including the last one, `Path2D.stroke()` returning a path rather than the area it covers (S-23a).

T14 (parts on the SDF backend) is the one remaining conformance item, and it is bounded by
mathematics rather than effort. Its numbers are now **measured**, by
`tests/test_parts_backend_coverage.py`, rather than written by hand: 40 of 51 parts build on either
backend and 11 refuse, where the spec had long claimed 38 of 53 with 15 refusing. The total had
double-counted an alias and neither figure had been rerun since parts were ported. The *reason*
survived the audit intact — all 11 refusals were checked one by one and every one cites
non-convexity — so what was wrong was the arithmetic, not the argument. That is the shape of most
of what this wave found.

T16–T23 came from using the library as a caller rather than reading it: every one is a rule the
spec already stated that nothing measured — which is why T23's gate went in even though its
backlog is not empty. It is the thing that catches the next one.

**These are breaking changes, and that is sanctioned** — `bounds()` changes return type, the sweeps
change theirs, `move`/`rot`/`fwd`/`bounding_box` disappear. The version is 0.x; §13.2 applies
(a breaking change needs a note in the release, not a deprecation cycle).

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

The T16–T23 wave, which is about the object surface rather than the constructors:

```
  T20 errors ──► everything else          Bosl2ValueError touches ~290 raise sites; land it
       │                                  first so later tasks write the new type from the start
       │
  T16 bounds type ──► T17 contract        bounds() is a protocol member; fix what it returns
       │                (needs T16's type)  before declaring the contract complete
       │
  T18 sweeps ──► T19 export               a sweep must return a Solid before "export a Solid"
       │          (needs T18's .vnf())      is the whole story
       │
  T21 exports ─── independent, and cheap
  T22 masks   ─── independent (touches masking.py + the edge_* methods on the solid)
       │
  T23 examples under mypy ◄── LAST         it is the gate that proves the rest; running it
                                           earlier just reports T16–T22's known breakage
```

**T20 goes first** because `Bosl2ValueError` is a mechanical change across every module, and doing
it after T16–T22 means writing `ValueError` into new code and converting it twice. **T23 goes
last** for the opposite reason: it is the ratchet that catches signature defects through their
examples, so it should first run against a surface that is already fixed — its value is stopping
the *next* one, not re-reporting these.

**T0 goes first.** While the backend tag lies, every other backend-related change is being tested
against a guard that does not fire. T0b–T0e are what a user hits on day one and need nothing else
landed first. T1 → T2 because the façade signatures are easier to change once `Shape` fixes what
"a shared argument" means; T2 → T2b because promoting shapes to the façade means declaring their
defaults there.

---

## Finished work

T0–T25 and their postmortems are in [docs/tasks-archive.md](docs/tasks-archive.md); the
requirement each one closed is in [CONFORMANCE.md](CONFORMANCE.md). This file is the queue.

---

## T26 — Make the requirements measurable ✅

**Closes:** §12.2 item 3 (first half) · **Implements:** the registry in `docs/design/spec-restructure.md` · **Size:** M
**Risk:** low — nothing in `pybosl2/` changes

The project measures everything except the document that tells it to. 263 numbered requirements
across SPEC.md and PLAN.md; five prefixes that mean different things in each; eight rules written
twice; and no way to ask "what checks this?" of any of them.

1. `spec/requirements.toml` — every requirement as data: `id` (document-prefixed, so `SPEC-S-2`
   and `PLAN-S-2` stop being the same string), `aliases` (the bare spelling, for the citations
   already in the tree), `layer`, `section`, `keyword`, `statement`, `enforced_by`, `status`,
   `note`. TOML rather than YAML: `tomllib` is standard library from 3.11, this project's floor,
   so the registry adds no dependency (PLAN L-4).
2. `scripts/extract_requirements.py` — the one-shot migration, so no requirement is lost in
   transit. It parses the bullets, unwraps the hard-wrapped prose, and collects every test that
   mentions each id.
3. **Those mentions are `candidates`, never `enforced_by`.** A test that names a rule may guard it
   or may merely cite it, and only reading it tells you which — inferring the first from the second
   is the exact failure this registry exists to catch. Everything starts `untriaged`; the twelve
   confirmed by hand during the migration carry their test or their reason.
4. `tests/test_requirements.py` — ids are unique; a status is backed by what it claims (`enforced`
   names a test, `unenforced` and `withdrawn` say why); every `enforced_by` target is a test that
   exists; the registry and the prose declare the same ids in both directions; every
   document-qualified citation resolves; and the untriaged backlog only shrinks.

**Done when:** all of the above pass, and the triage number is written down where it cannot grow.

**Landed.** 263 requirements — 167 contract, 96 mechanics — with **251 untriaged**, which is the
honest measure of how much of this project's own contract is checked by something. Six are
confirmed enforced (B2-1, C-7a, C-20, D-3, R-1, S-2b) and five confirmed *un*enforced with the
evidence in their `note`: A-1 (16 L0→L2 imports), A-6 (`Path2D.polygon()` returns CSG on either
backend), C-21 (three synonym pairs on the path types), PLAN S-2 (243 functions over 50 lines).
One is withdrawn (S-26d), which keeps its id per §13 rule 5.

`test_every_qualified_citation_resolves` checks **547 citations across 104 files** — worth the
number, because it is what stops an id from being renamed out from under a comment. The drift guard
was verified against a negative control rather than assumed: renaming one id in the registry fails
`test_the_registry_and_the_prose_agree`, as it must.

The five prefix collisions are recorded rather than fixed: `S-`, `T`, `L`, `O` and `Q` mean
different things in the two documents, the ids are permanent (§13 rule 5), so both keep theirs and
the prefixed form is what a citation uses from here.

---

## T27 — Generate the prose from the registry ✅

**Closes:** §12.2 item 3 (second half) · **Needs:** T26 · **Size:** M
**Risk:** medium — SPEC.md and PLAN.md become generated files

1. `docs/_reqgen.py` renders both documents from the registry plus a **frame** — `spec/spec.md.in`
   and `spec/plan.md.in`, which hold the section prose, the tables and the architecture diagram
   with a `{{requirements: <section>}}` placeholder wherever bullets go. Prose stays hand-written,
   requirements stay data, and neither is a copy of the other.
2. `scripts/build_spec_frames.py` performed the split, and **refused to leave a frame behind
   unless the migration was lossless**: it regenerates from frame + registry and compares against
   the original word for word. Wrapping may move; no word may.
3. §12.1 → [CONFORMANCE.md](CONFORMANCE.md), append-only. T0–T25 → `docs/tasks-archive.md`.
4. `tests/test_reqgen.py`: the committed documents match the generator, each says it is generated,
   and every registry entry reaches its document. CI runs `docs/_reqgen.py --check`.

**Done when:** both documents are generated, a hand-edit fails the build, and the history is out of
the spec with nothing lost.

**Landed.** SPEC.md and PLAN.md are generated. **16,438 and 7,364 words respectively, preserved
word for word** through the split — the migration script checks that and exits non-zero otherwise,
which is the only reason to trust a change this size. SPEC.md is 74 KB from 98 KB; TASKS.md is 427
lines from 2,077.

**The lossless check paid for itself four times over**, each time on something I had done and would
not have found by reading:

* Titles were being stored with their trailing period stripped, so `**B2-1 Feature compatible.**`
  would have regenerated as `**B2-1 Feature compatible**` — 109 titles, silently repunctuated.
* The withdrawn requirement S-26d would have lost its strikethrough, which is how §13 rule 5 shows
  a requirement that keeps its id.
* The T26 extractor treated an *unindented* paragraph after a bullet as part of it, so SPEC §3's
  "Review test:" note was swallowed into P-8 — and would have been emitted twice, once from the
  registry and once from the frame. Six statements were affected.
* Three statements (A-1, A-10, Q-7) had drifted between prose and registry during T28 and T29,
  because until this task there were two homes for a requirement and I edited one of them. That is
  precisely the drift the registry was built to end, appearing inside the two tasks that built it.

And one that is worth more than the other four: **the drift-detection script I wrote to find those
keyed requirements by their bare id, so PLAN's `S-1…S-5` silently overwrote SPEC's, and the first
run reported five phantom drifts.** The prefix collision that motivated the prefixed ids in T26
caught out the tooling built to fix it, a hundred lines after the rule was written down. Keyed by
`SPEC-S-2`/`PLAN-S-2` the report came back correct.

---

## T28 — Test what ships ✅

**Closes:** §12.2 item 5 (Q-7) · **Size:** XS
**Risk:** low, and it is the first gate in this project that reads the artifact rather than the tree

Every gate here reads the working copy. Nothing builds the wheel, installs it, or imports it, so
the first person to learn what a release contains is whoever installed it.

1. `pybosl2/py.typed`, declared under `[tool.setuptools.package-data]` — setuptools ships the
   `.pyi` stubs unasked and never ships that marker unasked.
2. `tests/test_packaging.py` — the cheap half: the declarations that decide what the build
   collects, checked at pytest speed.
3. **Q-7** (new, §11) — the full half: an `artifact` job that builds the wheel, asserts it carries
   the marker and every stub in the tree, installs it into an empty virtualenv, imports it, and
   type-checks a consumer snippet against the installed package.

**Done when:** the wheel carries `py.typed` and all five stubs; a clean-venv install imports and
type-checks a snippet using `Path2D`, a façade constructor and `bounds()`.

**Landed.** The wheel carries `py.typed` and all five stubs; a clean virtualenv with nothing but
the wheel and mypy imports it and type-checks the consumer snippet.

**The premise this task was written on was wrong, and the gate is what found it.** §12.2 item 5
claimed the missing marker made the library's types invisible to installed users — that PEP 561
would make every checker skip it. Measured rather than asserted: against **mypy 1.20.2, mypy 2.3.1
and pyright at default settings**, a consumer in a clean virtualenv gets full type information from
this package **with or without** `py.typed` — each of them reads a library's inline types whether
or not the library declares them, and a wrong attribute name (`Path2D.as_region`) is caught either
way. The marker is hygiene, not a defect that was costing anyone type checking.

Two smaller corrections went with it. The claim that a *committed* `dist/` wheel carried a deleted
stub was wrong — `dist/` is gitignored and untracked, and what I read was local build output. And
the first negative control appeared to prove the marker did nothing, which was mypy's incremental
cache answering from the previous run; the real answer needed `rm -rf .mypy_cache` between probes.
A control that agrees with you too easily has usually not run.

So the marker stays — it is what a typed library ships, and it is the difference between a
declaration and each checker's default — but the value of this task is the gate, not the file it
added. That generalises: the artifact was never measured, so what it contained was whatever
setuptools happened to do, and nobody would have found out from a green suite.

---

## T29 — Make the layering true ✅

**Closes:** §12.2 item 4 · **Implements:** A-10 (new), A-1, A-6, PAR-1 · **Size:** M
**Risk:** medium — `Path2D.polygon()` and three neighbours change their return type

1. `spec/layers.toml` — the layers, their members, and every upward edge, as data.
2. `tests/test_layering.py` — walks the import graph and classifies each upward edge as runtime
   (debt, ratcheted), type-checking-only (free, PLAN M-4), deferred-and-a-cycle (PLAN M-5), or a
   façade bridge (A-10).
3. **A-10** (new, §4): a geometry type builds through the façade and returns `Flat`/`Solid`.
4. Fix `Path2D.polygon()`, the case A-10 was written for.

**Done when:** the layer test passes with every edge accounted for, and
`Path2D(...).polygon()` inside `use_backend("sdf")` returns an SDF shape.

**Landed.** `Path2D(...).polygon()` inside `use_backend("sdf")` now returns an `SdfShape2D` with
the right bounds; it previously returned a `CsgShape2D` whatever backend was selected. `geometry()`,
`fill()` and `Region.geometry()`/`fill()`/`rotate_extrude()` follow it to the contract types.
`Gender` moved from `pybosl2.parts.enums` to `pybosl2.enums` — the SDF backend needed it, and an L3
module may not import L5 — re-exported from its old home so every existing import still works.

**The rule could not have been enforced against the table that stated it.** SPEC §4 put
`exceptions`, `enums` and `_edges_lang` in a layer *above* pure geometry, and every geometry module
raises `Bosl2ValueError` and takes an `Anchor` — so A-1 was violated by construction, by every
module, from the day it was written. It also omitted six modules, which is the other way a rule
becomes unenforceable: there is nothing to apply it to. The table in §4 is corrected, and the
measurement only became possible afterwards.

Against the corrected model: **16 runtime upward edges** (down from 18 — two died when the last
runtime use went, and ruff moved the imports to type-only), **9 deferred edges that break a genuine
cycle**, and **2 façade bridges**. The cycle claim is *checked*: the test resolves the cycle in the
import graph and rejects an entry whose claim does not hold, which is how six deferred edges that
were dodging a layer rather than breaking a cycle ended up in the debt list where they belong.

Two things the work turned up that were not in the plan:

* **The façade bridge needed its own category**, and the ratchet is what said so. Routing
  `Path2D.polygon()` through `flat` replaced one upward edge with another — `regions -> flat` is
  not a cycle, and listing it as one would have been a lie the cycle check would have caught. It is
  the door A-10 says to use, so it is justified by its *target* being a façade module, which the
  test verifies.
* **`fill` on the SDF backend is a refusal that never fires** (§12.2 item 9, T34), found because
  `Path2D.fill()` chains off `polygon()`. It needs a decision, not a fix, so it is recorded rather
  than settled here.

One test asserted the opposite of A-10 — `test_path_2d_geometry_is_csg_only`, on the grounds that
"2-D geometry is a CSG notion". That stopped being true when the SDF backend gained `PyShape2D`,
which §12.1 already records under PAR-3; the test outlived the belief. It now asserts that both
backends build, with the bounds to prove it. Writing it also produced a small demonstration of why
X-8 asks for content assertions: my first version asserted 20×20 for a fixture that is 20×12, and
the test failed on my mistake rather than the code's.

---

## T34 — Decide what `fill` means on a distance field ✅

**Closes:** §12.2 item 9 · **Implements:** PAR-3, B-5, PLAN B-P4 · **Size:** S

**Decided: `fill` refuses on the SDF backend**, naming `.to_csg()`. Of the two coherent answers,
this is the one consistent with the rules already written — PAR-3 says an exclusive feature is
declared and refuses, B-5 says a lossy conversion is never implicit, and `projection` was made to
behave exactly this way in T4. The round trip is not lost, only made explicit: `.to_csg()` crosses
the boundary and `fill` there does the same work without pretending to be a field operation.

`tests/test_sdf_shapes2d.py::TestFill` asserted the meshing margin, so the old behaviour was
deliberate rather than accidental; it now asserts the refusal and that the list and the shape
agree.

**The general finding is worth more than the decision.** `test_every_csg_only_feature_refuses_on_the_sdf_shape`
walked `SdfSolid` and nothing else. `fill` is a *2-D* operation, so `SdfSolid` never had it and the
check never looked at `PyShape2D` — where it was quietly working for as long as the exclusive list
has said it could not. The test is parametrised over both shapes now, and a negative control
confirms it fails when a listed feature works: restoring the old `fill` fails it, which is what the
original never did.


## T30 — Group the arguments that travel together 🔶

**Closes:** §12.2 item 7 (in part) · **Implements:** G-1 … G-5 (new) · **Size:** L

**Landed: `Placement`, the ambient-default documentation, and one resolution rule.**

`pybosl2/groups.py` holds the frozen groups. `Placement(anchor, spin, orient)` is wired into all 19
façade solid constructors: build it once, pass it to everything, and `with_()` derives a variant
without mutating the original. Giving it beside one of its own members raises, naming both — the
same rule and the same reasoning as a radius given beside its own diameter (D-5).

**Resolution went the other way, and that is G-4.** `Facets` exists but as *plumbing*, not as a
spelling a caller reaches for: `use_defaults(fn=64)` already sets resolution for a whole block
without threading anything through any call (R-4), so a group passed to every call would be
strictly worse than what the library already has. Keeping `use_defaults` as the public answer was
the maintainer's call and it is the right one.

What `Facets` does buy is **G-5**: "an explicit value beats the ambient one" was implemented twice —
once in `resolve_facets` for the CSG controls, once in `resolve_res` for the SDF one — and two
implementations of one rule is two things to keep in step. Both go through `Facets.resolved()` now,
and a test asserts they agree.

**The documentation sweep.** 209 public callables take `fn`/`fa`/`fs`/`res`; **38 said where the
default came from.** The façade had it everywhere (T0e), and nothing else did — so a reader met
`fn` at a signature with no hint that `use_defaults` existed. 171 parameter entries gained the
clause, and `tests/test_ambient_docs.py` keeps it true.

**The sweep broke the tree first, and the recovery is the part worth recording.** The script
collected its edits with `ast.walk`, which is breadth-first, then applied them with `reversed()` —
so the edits were not in source order, a low-line edit shifted every index after it, and later
edits landed on the wrong lines and **overwrote other parameters' documentation**. 36 lines of
unrelated `Args:` entries were destroyed. Nothing in the tree was committed, so recovery meant
separating 23 files where the sweep was the only change (revert from HEAD) from 6 that also carried
T29/T32/T33 work, and repairing those by hand. Three lessons, and only the first was about the bug:
sort edits by position before applying them; **verify a mechanical rewrite is lossless before
writing it** — the second attempt asserts the set of documented parameter names is unchanged and
refuses to write otherwise, which is the same guard T27's frame migration had and this script
lacked; and commit before a scripted sweep, because the cost of a mistake is set by what you have
to untangle it from.

**One rule turned out to be measuring the wrong thing.** The docstring expansion pushed a function
over its PLAN S-2 budget without touching a line of its code, because T32's metric counted
docstring lines. S-2 is about a function doing too much — "split it rather than commenting it into
sections" — and DOC-2 asks for `Args:`, `Returns:` and an example on everything public, so counting
those lines put the two rules in direct conflict and made S-2 penalise documentation. The metric
counts code lines now, and **the honest backlog is 131 functions across 47 files, not 243 across
57**: 112 of the original "violations" were documentation.

**`Placement` grew a 2-D reading** (second pass). The plane has an anchor and a spin but nothing to
orient, so `Placement` is honoured on 8 of the 9 `flat.py` constructors and one placement now serves
a 2-D profile and the solid extruded from it — the case that makes the group worth having. A
placement setting a real `orient` **refuses** there rather than honouring two of its three members,
because dropping it silently is the wrong answer E-5 forbids; the *default* orient is not a request,
so `Placement()` and `Placement(anchor=...)` stay dimension-neutral (G-6). `resolve_placement_2d` is
a separate function rather than a flag on the 3-D one, since a boolean selecting how many values
come back is the defect S-19b names.

Two things fell out of the wiring:

* **`text()` is the ninth constructor and could not be wired**, because its `anchor` is typed `str`
  and defaults to `"baseline"` — a typographic vocabulary, not the anchor language O-6b requires.
  Recorded as §12.2 item 7b and T36; retyping it is not enough, since the typographic anchors mean
  something `Anchor` has no member for.
* **The un-wiring of `text()` removed the wrong docstring.** `s.replace(block, "", 1)` matched
  `circle()`'s identical `Args:` block first, so `circle` lost its `placement:` entry while `text`
  kept one for a parameter it no longer had. Caught by ruff's D417 and then by a check asserting
  that *parameter and documentation agree for every constructor* — which is the check that should
  have been there from the start, and is the same lesson as T30's first sweep: verify the
  invariant, do not trust the edit.

**Still open**, and why:

**`EdgeTreatment` (third pass).** Built and wired into the 13 façade constructors taking both
`rounding` and `chamfer`. Three things the measurement changed about the plan:

* **The family is two groups, not one.** The plan named
  `EdgeTreatment(rounding, chamfer, edges, except_edges)`. In fact `rounding`+`chamfer` travels on
  38 callables and `edges`+`except_edges` on 9, and only 5 take all four — so the group as planned
  would have lumped two families that mostly appear apart. `EdgeTreatment` is the treatment;
  the edge *selection* is a separate group and still unbuilt.
* **The win is G-7, not the reuse.** Rounding and chamfer are mutually exclusive, and the library
  checked that in **six** places with six wordings — "Cannot set both rounding and chamfer at the
  same time.", "Cannot specify nonzero value for both chamfer and rounding", and four more — not
  one of which said what to do instead. One kind with one size leaves nothing to disagree, and the
  loose spellings' check is now written once, with a message that names the fix.
* **It found a live E-1 defect.** A per-corner treatment (`EdgeTreatment.rounding([1, 2, 3, 4])`,
  legal on `rect`) handed to a scalar constructor reached the backend and surfaced as
  `TypeError: '>' not supported between instances of 'list' and 'int'` — not a `Bosl2Error`, not
  naming a parameter. The resolver is told whether its constructor takes a size per corner, read
  from the annotation rather than guessed, and refuses with the fix.

**And the length metric was still wrong in the same way.** Adding two dispatch lines pushed
`prismoid` over its S-2 budget — a function whose 51 lines were thirty-odd of *signature* around a
body of twenty. Counting the signature makes S-2 report B-3's duplication: splitting the body could
not have helped, because the body was never the problem. The metric now measures the body alone,
and the honest backlog is **84 functions across 37 files** — not the 131 reported after the
docstring fix, and not the 243 originally. Docstrings accounted for 112 of that first figure and
signatures for another 47.

**`EdgeSelection` (fourth pass).** `edges` + `except_edges`, 15 callables, wired into the two
façade constructors that take the pair. Unlike a treatment its members *compose* — the second
narrows the first — so G-7 does not apply and there is no conflict to model away.

**`Texturing` was not built, and finding out why was the more useful result.** Its five parameters
travel together on 11 callables, which is the cleanest group of the four by that measure. They are
also **advertised on 13 public constructors and every one of them refuses**: `cyl(texture=...)`
raises. Grouping five parameters no call can honour would be polish on a promise nothing keeps.

Pulling that thread found four such promises, each refusing in a way `except Bosl2Error` could not
catch: `texture=`, `cuboid(teardrop=...)`, `CapType.CIRCLE`, and `VNF.from_field` with a range —
all bare `NotImplementedError`, so not a `Bosl2Error` (E-1), and none naming an alternative (E-2).
**G-8** is the new rule, `Bosl2NotImplementedError` the new type (both bases, exactly as
`Bosl2ValueError` is), and `tests/test_unimplemented.py` the ratchet.

`texture=` is the substantial one: S-34 and S-35 specify textures as a working subsystem and the
*registry* is built — `texture("diamonds")` returns its tile — so what is missing is the
application, not the vocabulary. T37.

* **The per-end variants are unbuilt** (`rounding1`, `chamfer_angle`, …), which is B-3's
  duplication rather than a missing group — T31.
* **The façade's parameter duplication (B-3) is untouched.** A group removes three parameters from
  a signature that has forty; T31 is still the task that addresses the rest.

---

## T35 — Give every public callable an `Args:` section ✅

**Closes:** §12.2 item 7a (in part) · **Implements:** PLAN D-P4, DOC-2 · **Size:** M

**Landed: the 57 that blocked the ambient-resolution documentation.** `KNOWN_GAPS` in
`tests/test_ambient_docs.py` is empty, so all **498** facet parameters in the library now say that
omitting them inherits `use_defaults` — which was the point of G-4 and could not be finished while
97 of them had no `Args:` section to put the clause in.

**The measured debt is larger than the task assumed.** T35 was written as "57 callables"; those
were only the ones that also take a facet control. D-P4 has asked for a complete `Args:` since it
was written and nothing had ever checked, and the real figure is **313 public callables taking
1307 parameters and documenting none of them**. 256 across 38 files remain, as a per-file budget in
`tests/test_documented_arguments.py` that only shrinks.

**How they were written is the part worth keeping**, because the same job remains for the other
256. The first attempt harvested, for each parameter name, the most common description of it
elsewhere in the library. That is unsound and the output proved it immediately: it put a
polyhedron's insphere radius on `cylindrical_extrude`'s `inner_radius` and a cube-truss size on its
`size`, and it truncated every description that wrapped onto a second line. **A confidently wrong
docstring is worse than a missing one**, so that attempt was reverted whole.

What is sound is a *specific* counterpart rather than a popular one:

* **the same-named function elsewhere.** The SDF backend deliberately mirrors the CSG API (PAR-1),
  so `sdf.tube`'s parameters mean what `shapes3d.tube`'s do and its wording is the right wording.
* **the function a wrapper delegates to.** `pentagon` forwards to `regular_ngon`, so that is where
  its seventeen parameters are already described.
* **a small hand-written set for the genuinely universal names** — `fn`, `fa`, `fs`, `res`,
  `anchor`, `spin`, `orient`, `center`, `convexity` — which do mean one thing everywhere. Written
  out rather than harvested, because a name being *common* does not make its meaning uniform, and
  that is exactly the assumption that failed.

Those three covered 416 of 586 parameters. **The remaining 170, across 30 callables, were written
by hand after reading each function** — the hinges' `seg_ratio` and `clear_top`, the rabbit clip's
`compression` and `lock_clearance`, the SDF tube's eight per-end radius spellings, the
superformula's `m1`/`n1`/`n2`/`n3`. One of them, `knuckle_hinge(fill=)`, turned out to be accepted
and ignored (`_ = fill` in the body), which the docstring now says.

Two smaller things the generator had to be taught, each caught by verifying before writing rather
than by reading the result: a one-line docstring has nowhere to insert a section and has to be
reopened as a multi-line one, and `Args:` belongs *before* `Returns:`/`Examples:`, not appended at
the end.

**The remaining 256 landed too** (second pass). 439 descriptions written, and the method held: the
same-named counterpart and the delegation target covered what they could, and the rest came from a
vocabulary written **per module** rather than per name — because a name is reliably one thing inside
one module and demonstrably not across the library, which is what the reverted first attempt proved.
`distributors.py` alone repeated one vocabulary of 38 across fifteen functions.

**Reviewing the output still caught things a scan would not.** `quaternion_slerp(q1, q2, t)` came
out documented as "the second quaternion" and "the third", because the vocabulary assumed a `q0`
that only `absolute_distance` has; three varargs (`*diffs`, `**kwargs`) were invisible to the
generator, which read `args` and `kwonlyargs` only; and two properties ended up with an empty
`Args:` section whose sole parameter was `self`.

`tests/test_documented_arguments.py` is a plain assertion now rather than a budget: **every public
callable in the package documents its arguments**, and a new one that does not has nowhere to be
written down.

---

## T31 — Slim the façade ✅

**Closes:** §12.2 item 7 (second half) · **Needs:** T30 · **Size:** M

**Landed. 67 shared defaults moved from the backends into the façade signature**, which is what
B-3 has always asked for: the façade declares the default and forwards it, so an identical call
builds identical geometry on either backend. It did not. *Every* façade default was `None`, so the
backend's own default decided anything the caller left out, and the two backends could and did
disagree — `cuboid`'s `rounding` defaulted to `None` on CSG and `0` on SDF.

`test_the_facade_owns_every_shared_default` keeps them there, and 24 remain `None` for a reason,
in two groups named with it: `res` (an ambient control, so nothing set anywhere means the
backend's own facet default is the answer, R-7) and `anchor` on the cylinders and `regular_prism`
(the right value depends on `center`, so the backend computes it and no constant would be right).

**The task's own step 1 was wrong, and running it is what showed that.** It said to remove the
façade's `None`-dropping so that "the façade forwards everything it declares". I did, and 48 tests
failed: `res=None` reached the SDF backend and overrode its real default of 10 with nothing, and
`anchor=None` reached a constructor that cannot take it. The plan had it backwards. `None` is not
a value the façade owns and forwards — **SPEC D-4 defines it as "not supplied, decide for me"**, so
forwarding it overrides the backend's answer with the absence of one.

So there was never a third filter to remove. What there was is a façade that declined to decide
*everything*, which is why the backend's default always won. Fixing that is the F-P1 sweep, and
once the defaults are real the `None`-drop stops deciding anything for shared arguments: it only
passes through the genuine "decide for me" cases, which is D-4 working, not a filter. It is
`_forward()` now, with the two cases documented at the definition instead of a bare
`given_arguments`.

Two things fell out on the way:

* **`cube(edges=...)` was annotated `Sequence[float]`** where `cuboid`'s is
  `EdgeAtom | list[EdgeAtom]`. An edge selector is the anchor language (O-6b) and `cube` was the
  odd one out; `mypy` found it the moment `Anchor.ALL` became its default.
* **TASKS.md had five duplicated sections** — T30 through T34 each appearing twice, with `T33`
  marked done in one copy and open in the other. Editing a task by `text.index("## T30")` always
  finds the *first* copy, so once a duplicate existed every later edit updated one and left the
  other stale: the queue was lying about its own state. Removed, and
  `test_no_task_appears_twice` now guards it. The archived tasks' links had also dangled since
  T27 moved them out of this file; they point at `docs/tasks-archive.md` now.

**Still open:** the per-end variants themselves (`rounding1`, `chamfer_angle`, …) are still
declared one-by-one on ten constructors. Their *defaults* are the façade's now, which is the half
B-3 is about; the transcription that remains is the half a generated façade would remove, and that
was the original T31 alternative this project did not take.

---

## T32 — Close the two rules that only half-closed ✅

**Closes:** §12.2 item 6 · **Size:** S

**Landed.** Both rules were true of the surface a test walked and false everywhere else.

**C-21 on the geometry types.** `Path2D` and `Path3D` each carried three synonym pairs. BOSL2's
spelling survives in each (B2-3): `deduplicate`, `subdivide_path`, `resample_path`. Two details
that a blind delete would have got wrong — `subdivide` was not a pure duplicate, it carried a
`refine=` parameter that BOSL2's own `subdivide_path` has and this port had dropped, so `refine`
moved onto the survivor rather than disappearing with the wrapper; and the *fuller* docstrings,
with the `Args:` sections and the rendering examples, were on the spellings being removed, so they
moved across too. Deleting a synonym is not the same as deleting the code behind it.

`tests/test_shape_contract.py::test_no_public_class_carries_both_spellings_of_one_operation` now
walks **every public class reachable from the top level**, not one class family, which is what let
this sit closed and untrue.

**PLAN S-2.** 243 functions over 50 lines, the longest at 237, across 57 files. Retiring the rule
was the alternative and it is the wrong one: the rule is right, the code has simply never been held
to it, and a rule with 243 violations and no test teaches contributors that the document is
optional. So it becomes what every other backlog here already is — a per-file budget that can only
shrink, in `tests/test_function_length.py`. Per file rather than one total, because locality is
what makes it actionable: the failure names the file you are in, not a global counter you have no
way to move. A file with no row may not grow a long function at all.

Both guards were checked against negative controls rather than assumed: restoring one synonym fails
the first, and adding a 61-line function to a file with no budget row fails the second.

---

## T33 — Type the contract ✅

**Closes:** §12.2 item 8 · **Implements:** C-23 (new) · **Size:** M

**Landed.** 42 of 90 protocol members were typed; 63 are now, and the rest are a list that only
shrinks (`tests/test_contract_typing.py`).

C-20 required the contract to cover the whole object and said nothing about the cover meaning
anything, so 48 members arrived as `(*args: Any, **kwargs: Any)` — present by name, checked not at
all. That is worse than a missing member, because it reads as a promise: the method is found and
every argument is accepted, including the wrong ones.

**Both families were loose for the same reason, though one of them took a wrong turn to find out.**

* **The distribution family (16 members).** All four implementations inherit one `Distributable`
  mixin, so they agree exactly and there was nothing to bridge. Pure transcription.
* **The attachment family (7 members).** This looked like the harder case: PAR-3 asks a CSG-only
  feature to be *declared and refuse* on the SDF backend, those refusals are written
  `(*_args: Any, **_kwargs: Any) -> NoReturn`, and a loose implementation appears to force a loose
  contract. **I acted on that reading and it was wrong.** I gave all fourteen refusal stubs the
  real CSG signatures — which broke them, because a refusal must fire *however* it is called and
  `sdf_shape.attach()` then raised `TypeError` about missing arguments instead of the error that
  teaches (E-2); eight tests said so. Defaulting every parameter fixed that and drew 42 ARG002
  warnings for arguments a refusal never reads. Only then did I check the premise: `(*args: Any,
  **kwargs: Any)` **satisfies any protocol signature**, so the contract was always free to declare
  the real one. The stubs are back to the loose form, unchanged from before this task, and the
  protocol carries the types. The loose stub was a fact about the refusal, never a constraint on
  the contract — and reading it as one is what left the family unchecked.

The check that matters: `def with_boss(base: Solid) -> Solid: return base.attach(Anchor.TOP, boss)`
compiles, and the same call with `"top"` in place of the anchor is now a checker error where it
used to pass silently. That is C-20's own worked example, finally checked rather than merely
permitted.

The scan behind the ratchet is keyed by `Protocol.member`, not by member name — `rotate` is loose
on `Shape` and typed on `Flat`, and the first version keyed by name let one answer for the other.
The same collision as the bare requirement ids, in a third place.

---

## T36 — Give `text()` the anchor language ✅

**Closes:** §12.2 item 7b · **Implements:** PLAN O-6b, SPEC C-10 · **Size:** S

**Landed, and it was smaller than it looked.** The task was written expecting a design decision —
a text-specific enum, or folding the typographic spellings into `halign`/`valign` — because
`anchor="baseline"` seemed to mean something the anchor language has no member for.

**Reading the body settled it in one line.** `text()` computed
`v = valign if valign is not None else anchor`, so its `anchor` was never an anchor at all: it was
a **second spelling of `valign`** with a different default. Not a parallel vocabulary standing in
for a missing concept, just a duplicate of the parameter next to it — which is C-21's defect as
well as O-6b's, in the one place neither rule was looking.

So: `valign` carries the `"baseline"` default it always really owned, and `anchor` is
`Anchor | Sequence[float] | None` like everywhere else, applied to the finished text's bounding box
after the typographic alignment has placed it. `None` means "leave it where halign/valign put it",
which is the usual answer for text and what every existing call already gets — and no caller in the
package or the tests passed `anchor=` to `text()`, so nothing had to change. All nine 2-D façade
constructors take `placement=` now.

**One near-miss worth recording.** The test that documented this as an exception sat above two
other classes, and deleting it by "from here to the next `class TestFacets`" took
`TestEdgeTreatment` and `TestEdgeSelection` with it. Nothing in the suite noticed — the tests were
simply gone — but `test_every_enforced_by_target_exists` failed, because G-7 names one of the
deleted tests as what enforces it. **The registry caught a deletion the test suite could not**,
which is an argument for `enforced_by` that had not occurred to me when writing it.


## T37 — Build `texture=` ✅

**Closes:** §12.2 item 7c · **Implements:** SPEC S-34, S-35, G-1, G-9 · **Size:** L

**Built, for the cylinder family.** `cyl(texture="ribs", tex_reps=[12, 1], tex_depth=1.5)` returns
a watertight ribbed cylinder measuring 23 × 23 × 20 — the ribs standing 1.5 mm proud of a radius of
10, which is what the parameters say and what nothing checked before, because every call refused.

The mesh is built in pure Python and crosses to geometry once, at the end:
`textured_cylinder_vnf()` samples the side on a grid of one column per texture cell around and one
row per cell along, displaces each vertex radially by the texture's height there, and closes the
ends. **Both kinds of texture work**, which is the part S-34 actually asks for: a VNF tile is
rasterised to a height field first, so a caller passing `"dots"` (a VNF tile) and one passing
`"ribs"` (a height field) get the same treatment and never learn which they had.

Three things the work decided rather than assumed:

* **The facet controls own the roundness.** A two-cell texture would otherwise give a two-sided
  cylinder. `fn`/`fa`/`fs` raise the column count and each texture cell is repeated over as many
  columns as that takes, so the texture stays crisp and the curve gets smooth (R-1). A textured
  cylinder measures the same as the plain one it replaces, and follows `use_defaults(fn=...)`.
* **Omitting both `tex_size` and `tex_reps` decides rather than refuses** (D-4, P-1): the repeats
  come from the geometry, as many around as the circumference holds at the cylinder's own height,
  so one tile is roughly square. One tile around a whole cylinder is not a texture.
* **`Texturing` landed with it** (G-1). It is the cleanest group in the library by G-1's own
  measure — all five members travel together on every callable taking more than one — and it was
  the last to be built, because until now grouping them would have been polish on a promise
  nothing kept. `size` and `reps` are alternatives, so the group holds at most one and the pair
  cannot disagree (G-7).

**The length ratchet made this harder and was right to.** Adding `texturing=` pushed five
constructors past PLAN S-2, so the three group-resolution calls were collapsed into one that works
**on the forwarding dict itself** rather than beside it — the loose members are already listed
there, so resolving in place costs a constructor one wrapper instead of thirteen lines of
unpacking. `cube` and `cuboid` went from 53 lines to 28. That is **G-9**.

**What it could not fix, and what I did instead.** The five cylinder constructors are still 55
lines, of which **44 is the forwarding dict — one line per parameter**. That is B-3's transcription,
not a function doing too much, and the same thing the signature is. I raised `solid.py`'s budget
from 0 to 5 with the reason written at the entry rather than redefine the metric a third time: the
docstring and the signature already do not count toward it, and a rule that keeps shrinking to fit
stops measuring anything. It returns to 0 when the façade duplication does.

**S-35 closed in T39.** `textured_tile` already honoured its parameters; the **bottle caps did not** —
they accepted a `BottleCapTexture` and built a plain wall, and the module comment said so, which
makes it a documented silent wrong answer rather than an excuse for one (E-5). The named styles go
on the cap's outer wall now, inset so the knurl is cut *into* the nominal diameter rather than grown
outside it: a ribbed PCO-1881 cap measures the same across as the plain one and holds less material.
An unrecognised style raises, naming the registry's names (E-4), instead of falling back.

The guard is a scan rather than a list: every callable declaring `texture=` is built with and
without one and required to differ, and the scan walks the package, so a new declarer that ignores
it fails instead of joining quietly. That is what would have caught the caps.

**Still open:** the three remaining gaps in `tests/test_unimplemented.py`.


## T38 — Triage every requirement ✅

**Closes:** §12.2 item 3 (the last third) · **Needs:** T26 · **Size:** L

**All 275 requirements are triaged.** This is the number the registry was built to produce, and
until now it was 250 unknowns and a promise to look.

| | |
|---|---|
| **enforced** | 208 — a named test that walks the package and fails when the rule is broken |
| **reviewed** | 47 — judgements no test can make, each saying why |
| **unenforced** | 19 — mechanically checkable and simply unchecked, each naming its missing guard |
| **withdrawn** | 1 — S-26d, keeping its id per §13 rule 5 |

**The method mattered, because the obvious one is wrong.** A test that *mentions* a requirement is
not a test that *guards* it — that is exactly what T26 refused to infer, and doing the triage
confirmed the refusal was right. Three passes of evidence, each narrower than the last:

1. **A test whose own docstring cites the requirement.** 73 of the 250 — a deliberate claim, not
   proximity.
2. **…and which walks the package.** 39 of those 73. The other 34 cite the rule and exercise *one
   case*: `test_size_only_rect_tube_gets_a_wall` is a real test of P-3 at one call site, and P-3 is
   a rule about every call site. Those became `reviewed` or `unenforced` with the spot check named.
3. **Reading the remainder.** For the subsystem series a mechanical check did the work honestly:
   extract the symbols each requirement names, confirm they exist, and confirm tests exercise them
   — deleting the feature then fails the suite, which is what "enforced" has to mean. 46 of 63 came
   out fully covered; `S-22` came out one symbol short, and that symbol (`text3d`) is now a
   recorded gap.

**Even the citation evidence needed correcting by hand.** Of the 39 that passed both filters, about
a quarter were mis-assigned: `Q-6` ("every docstring example type-checks") pointed at a test that
checks CI *configuration*, and `B2-2` and `D-2` at scans covering one module of the surface they
claim. Twelve of the tests I named while correcting them **did not exist** — wrong file, wrong name,
or in one case a guard PLAN X-4 has always claimed and that has never been written
(`test_no_public_return_type_is_a_flag_selected_union`, now recorded as T-6d's gap). The validation
pass caught all twelve before anything was written, which is the only reason to run one.

**Two ratchets replace the one.** `UNTRIAGED_BUDGET` is 0 and stays as a gate: a new requirement
arrives untriaged and has to say what checks it before it can land. `UNENFORCED_BUDGET` is 19 and
only shrinks — the work list is §12.2 item 3a, and T39 is closing it.

---

## T39 — Close the nineteen ✅

**Closes:** §12.2 item 3a · **Needs:** T38 · **Size:** M

**16 of 19 closed**, by three scans rather than nineteen fixes:

* **`tests/test_signatures.py`** — one pass over the public signatures closing six rules: P-5, D-1
  and T-9a (keyword-only past the subject argument, 114 ratcheted), D-2 (three required parameters,
  8 ratcheted), R-P1 (the facet controls' spelling, clean) and O-6b (anchors in the anchor
  language, clean after one fix).
* **`tests/test_code_hygiene.py`** — S-3 (TODO comments and stubbed bodies), L-2 (legacy `typing`
  spellings), T-9 (dynamic globals) and T-6d (flag-selected return unions). All four clean, so none
  has a budget.
* **`tests/test_declared_surface.py`** — the claims the package makes about itself: C-6 (the
  passthrough allowlist names real attributes), L-4 (the dependency list matches the plan), O-5
  (spec objects are frozen) and A-5 (no wildcard re-export).

**Writing a check you expect to pass is still worth it**, which is the case these made four times:

* **`text3d` took `anchor: str = "baseline[-1,0,-1]"`** — the same defect `flat.text()` had until
  T36, sitting in `shapes3d/extrusions.py`, which has no `__all__`, so the scan's first version
  skipped the module entirely even though `text3d` is a *top-level export*. Widening the scan to
  resolve the lazy export table to where each name is **defined** rather than re-exported is what
  found it. `valign` carries the typographic half now and the geometry is unchanged.
* **Six `typing.Union` aliases** survived L-2 — and five were the *same* `Shape2DLike` alias copied
  into five modules, of which **only `base.py` imported the names its own copy referenced**. They
  are one definition now.
* **`ScrewSpec` is not a frozen dataclass**: an 87-line constructor that parses a trade name, so it
  is the one named exception rather than a decorator away.
* **`roof` is in the native passthrough allowlist and not on the pip wheel** — an app-only op, now
  named as such, which is why the render tests skip rather than fail.

**And the prefix collision bit a third time, in my own data.** `SPEC-S-2` ("every shape and mesh
reports its bounds") has carried **`PLAN-S-2`'s note** — about functions over 50 lines — since T26,
because that task's confirmed-enforcement table was keyed by the *bare* id and `S-2` matched
whichever entry came first. It is enforced by `test_bounds_contract.py`, and has been all along.
The collision the prefixed ids exist to prevent, landing in the data written to record it.

**One rule was scoped rather than satisfied.** D-2 ("three required parameters is never
acceptable") reads under §8.1's argument tiers, which are about what is being *made*; applied to
every exported callable it flags `slerp(a, b, t)`, which is three operands and not a constructor
with two parameters too many. The check covers callables that return geometry, which is the frame
the rule argues in and what its own examples are.

**S-35 and PAR-4 followed, and both found live defects.** S-35's was a bottle cap that accepted a
texture style and built a plain wall. PAR-4's was sharper: the two backends' *shapes* had been
compared since the matrix was written, and their *options* never — so 176 options one backend has
and the other lacks were invisible, and `tube(outer_radius1=8)` **built on CSG and refused on SDF**,
whose `outer_r1` is the same option under another name. A test asserted that refusal as correct
behaviour. The missing options are honest debt and are ratcheted per shape; a missing *translation*
is not, and has no budget, because it tells a caller the backend cannot do something it can.

**One remains**, and it is not a missing check: X-3 asks that every new public callable arrive with
three tests, which is a count a reviewer makes and no scan can — the minimum-argument third of it is
enforced (Q-4). `UNENFORCED_BUDGET` is 1.


## T40 — Close the SDF option gaps 🔶

**§12.2 items 10 and 11. PAR-4, PAR-5, S-2b, C-21, B2-3.**

T39 measured parity per *option* for the first time and found **176** the SDF backend lacked. This
closes **63** of them, and the interesting result is not the number:

**Not one of the 63 needed a distance field anyone had to invent.**

| What | How many | Why it was missing |
|---|---|---|
| `spin`, `orient` | 38 | Never written. A rotation about Z and a rotation of +Z onto a direction are exact in a field. |
| `center` | 11 | Not a shape option — `anchor` spelled as a boolean. |
| alias forwarding | 14 | `cube` is `cuboid`; `cylinder` and `zcyl` are `cyl`. Each SDF alias had its own field and passed nothing on. |

`_place(shape, offset, spin, orient)` applies the three in the order `_finish3` does on the CSG
side, and every SDF constructor's tail now goes through it. Nine of them declared `spin`/`orient`
and ignored them in the first pass — caught by `ruff`'s ARG001, the same silent no-op T39 had just
fixed in the bottle caps, which is the argument for keeping that rule on.

**113 remain and they are the honest ones**: the cylinder family's `texture`/`tex_*` (a textured
field is not a mesh with a texture applied to it, so B-5 forbids the cheap route), and the chamfer
geometry variants `chamfer_angle`, `from_end`, `extra`, `clip_angle`, `teardrop`.

### What writing the tests found

**Three defects in `shift=`, every one of which a symmetric test case would have passed.**

1. The SDF backend sheared from the **bottom face** where CSG shears about the **mid-plane**
   (`x' = x + shift_x * z / length`, on a cylinder spanning `-h/2 .. h/2`), so it built the same
   lean half a shift from where CSG built it. The *relative* offset — the thing the option is
   defined as, and the thing anyone would check — was correct.
2. The reported box was widened by the **whole** shift at **both** ends, when each end disc slides
   half a shift and carries its own radius: a 10-wide solid reported 13 wide.
3. `_AXIS_LEAN`, which carries `shift` through the rotation that turns a `cyl` into an `xcyl`, had
   **every sign inverted** in its first version. `shift=[3, 3]` on a symmetric cone passes with the
   signs backwards. Every case in the tests is asymmetric for that reason.

**And the negative controls found that a bounds comparison can only see two of the three.** An SDF
shape's `bounds()` is the box it *declares*, not a measurement of its field: putting defect 1 back
moves the geometry three units and leaves the reported box — and the cross-backend bounds test —
untouched. Closing it took a test that asks the *field* where the material is, sampling either side
of each end disc through the numeric mock. That is a limit on how far a bounds comparison can reach
on this backend generally, not a fact about `shift`, and it is the reason every guard in this
session gets its defect planted rather than being trusted because it passes.

**And `center=` was written in eleven places, in three spellings and two contradicting
precedences.** BOSL2's rule is `anchor = center==true ? CENTER : center==false ? uncentred :
anchor` — `center` wins. Seven sites do that (six through a private helper, one spelling it out).
The other four spelled it inline as `use_anchor = anchor; if use_anchor is None: ...`, which lets
`anchor` win — **while their own docstrings said "center: if given, overrides anchor"**. `cyl(height=10, radius=5, anchor=TOP, center=False)` sat on its top
face with the documentation beside it saying it would sit on the bottom one. That is E-5's silent
wrong answer, and it survived because the rule had no single home to be right in.

It has one now: `pybosl2.groups.resolve_center_anchor`. `centred` and `uncentred` are named at each
call site rather than defaulted, because the CSG backend anchors with `Anchor` members and the SDF
backend with the raw direction vectors of `pybosl2/sdf/_constants.py` — that vocabulary was the
only thing that ever differed between the two, which is why one function can serve both.

### Two more the guards caught on the way

**A test asserted the `shift` defect as correct behaviour** — the fourth this session.
`test_oblique_cone_top_lands_at_shift` required the top to land at the *full* shift with the bottom
left on the axis, which is what the SDF backend did and what CSG has never done. It is
`test_the_ends_slide_half_a_shift_each_way` now.

**B-9's no-op carve-out was dropping a request.** A falsy value is normally nothing to honour —
`prismoid(rounding=0)` is "no rounding", and refusing it turned `RingHook` away from the SDF
backend for nothing. But where the façade's default is `True`, `False` is the caller turning
something *off*: `cuboid(trimcorners=False)` leaves the chamfer running past the corners, and the
SDF backend trims them regardless. It was being dropped in silence — the wrong answer arriving
*through* the guard against false alarms rather than around it. `_is_no_op` now takes the façade's
default and only calls a falsy value nothing when the default is falsy too. Two parameters in the
whole façade have a truthy default a backend lacks, and both of them are this one.

**And `spin=` had been this rule's worked example.** `test_an_argument_the_backend_cannot_honour_is_
refused_not_dropped` used `cube(10, spin=45)` as its CSG-only option; T40 built it, so the test
needed a gap that is still a gap (`cuboid(p1=, p2=)`). Worth noting because the example was
carrying an implicit claim — that `spin` was CSG-only — which was never true. It was unwritten.

### Recorded rather than fixed

A shape that is **round about Z reports a looser box after a spin that cannot move it**:
`sphere(spin=30)` says 27.3 across where it is still 20. `PyShape.rotate` recomputes the bound as
the axis-aligned box of the rotated *corner box* — exact for a cuboid, loose for a disc. The field
is untouched: rotating `|p| − r` gives back `|p| − r`, and only the stored bound grew. It is
pre-existing in `rotate` and became reachable when spin reached these shapes (S-2b).

`ROUND_ABOUT_Z` lists them and `test_a_spin_about_z_leaves_a_round_shape_where_it_was` fails when
the list goes stale, so a shape comes off it rather than sitting there as an excuse. Fixing it
means giving `rotate` a bound that tracks the shape rather than its corner box, which is its own
task and touches every rotated shape, not just these.


## T41 — Build `texture=` on the SDF backend ✅

**§12.2 item 12. PAR-4, PAR-5, S-34.**

The five texture options were 25 of the 176 gaps, and T40 left them as the honest remainder with a
reason attached: *"a textured field is not a mesh with a texture applied, so B-5 rules out the
cheap route."* Three documents said it — that §12.2 row, `docs/design/sdf-csg-compatibility.md`,
and PAR-4's own note.

**All three were written by reading the CSG signature rather than the CSG code.**

`textured_cylinder_vnf` has no texture primitive either. It reduces a texture — a named height
field, a rasterised VNF tile, or a caller's own array — to a **grid of heights in 0..1**, and only
then places a vertex per cell pushed out radially by `depth * h`. The displacement map exists
before either backend sees it. There was nothing to convert and no backend to cross; the work was
evaluating the same map at every point instead of at sample points.

The claim the tests make is exact: **the field is zero at every vertex the mesh is built from**,
for all 21 registry textures. Not close — zero. Both read the same tile, the same repeat counts
and the same radius formula.

### What made it affordable

* **The repeats are folded, not unrolled.** A texture repeating 20 times around and 4 along would
  be a 480-column grid written out. It is periodic, so `atan2(-sin(n·θ), -cos(n·θ))` recovers
  `frac(n·θ/2π)` exactly, and `sin`/`cos` of a multiple angle come from the Chebyshev recurrence
  on `x/r` and `y/r`. The tree is the size of one *tile*, whatever the counts are.
* **Interpolation is a sum of hats.** `max(0, 1 − |t − c|)` is a triangular basis function, so
  `Σ h[c]·hat(t − c)` is linear interpolation with no comparison operator — which matters, because
  libfive gives `min`, `max` and `abs` and no `if`. Zero-height cells drop out of the sum.
* **`_AXIS_LEAN` is read backwards.** `xcyl` is a `cyl` turned, and on the CSG side that is
  literal — it builds a `cyl` and rotates the result. A field has nothing to rotate, so the angle
  goes into the cylinder's own frame instead, using the same table `shift=` reads forwards. One
  rotation written down once, rather than two derivations that can disagree.

A tile past ~1600 cells refuses and names what to do; the largest in the registry is `rough` at
32×32, so no named texture reaches it.

### What the guards found

**`default_tex_reps` was written twice for one turn.** "Repeat the tile so one comes out roughly
square" is the D-4 answer when the caller gives neither `tex_size` nor `tex_reps`, and it existed
once in the CSG `_textured_cyl` and once in the SDF one — the same duplication, in the same shape,
as `center=` in item 11, and the same way two backends come to answer one undecorated call with
two different surfaces. It lives in `pybosl2.textures` now.

**And the test written to catch that sampled zero points.** The first and last grid rows sit on the
rims, where the slab term is zero whatever the texture does, so the sampler skips them — but the
undecorated case repeats a one-row tile *once* along, which is a two-row grid whose only rows are
those two. The loop ran zero times and reported a pass. It went green with the SDF backend's
default replaced by `[1, 1]`, which is the one thing it existed to catch.

Planting the defect found it; running the test did not. The helper now refuses to report a pass it
did not measure, and the case uses a texture with rows between the rims. **A test that measures
nothing looks exactly like a test that passes** — which is the argument for the negative control
being part of writing a guard rather than a thing done afterwards if there is time.

### And a name that reached two different things

`texture` was a top-level export — BOSL2's function that builds a tile — **and** the module holding
the texture machinery. Python binds a submodule onto its package as an attribute when the submodule
is imported, and that wins over the package's own lazy export table:

```python
from pybosl2 import texture  # the function
from pybosl2.texture import TEXTURES  # ... and now `pybosl2.texture` is the module
```

So `from pybosl2 import texture` returned the function or the module depending on import order.
It survived every test that imported one way, and came out when a *new* test module imported the
other way and two unrelated tests three files later started calling a module. C-21 exactly — one
name, two things — and the one case in the package where the language decides which you get rather
than the library.

The module is `pybosl2.textures` now; the function keeps BOSL2's spelling (B2-3), it being the half
a caller reads. Exactly one name in the package collided, which is why the guard is a plain
assertion and not a budget.


## T42 — Close the cylinder rim options 🔶

**§12.2 item 14. PAR-4, PAR-5.**

`chamfer_angle`, `from_end` and `extra` — each an overall/bottom/top triple — across the five
cylinder spellings: **45 of the 88 gaps, and one implementation.** `cylinder` and `zcyl` *are*
`cyl`; `xcyl` and `ycyl` are the same field about another axis. Counting per option and per shape
is what made it look like 45 things to do. `cuboid(p1=, p2=)` followed, 2 more. **88 → 41.**

The chamfer plane had been hard-coded to 45° — `(qu + qv + c)/√2`, with the angle nowhere in it.
BOSL2 states a chamfer either as its radial leg with an angle (`from_end=False`) or as the cut's
own length split by that angle (`from_end=True`); the general plane through `(−dx, 0)` and
`(0, −dy)` covers both, and reduces to exactly the old expression when `dx == dy`, so the default
case is unchanged by construction.

`extra=` unions a straight stub of that end's radius past the end, the way CSG does — changing
neither the length nor the anchoring, which is the part worth a test.

### A third instrument, and a third defect

The CSG backend states a cylinder's rim as a **2-D profile it revolves**, which gives an exact
question: *is the field zero at every vertex of that profile?* On a taper it was not.

**BOSL2 puts a treated rim's inner endpoint at the nominal end radius and runs the wall from there
to the other end's endpoint.** So a chamfered cone's wall is not the line through its two nominal
corners. This backend measured against that nominal line and built a different cone from the same
call — 0.39 mm out on an 8→4 taper with a 2 mm chamfer, and the same for a rounding. It had been
wrong since the rim treatment was written.

Neither instrument used before could have found it:

| | why it is blind here |
|---|---|
| cross-backend `bounds()` | the box is set by the widest ring; the wall between the rims never touches it |
| the field-probe at mesh vertices (T41) | those are on the *texture*, not the rim, and every case was a plain cylinder |
| a plain cylinder, any test | the wall is vertical and an axial inset cannot move it — the two constructions coincide |

Three defects across T40–T42, three instruments, and **each was invisible to the other two.** That
is the argument for asking what a check *cannot* see before trusting that it passed.

### And the worked example went stale for the second time

`test_an_argument_the_backend_cannot_honour_is_refused_not_dropped` used `cube(10, spin=45)` as
its CSG-only option until T40 built `spin`; T40 repointed it at `cuboid(p1=, p2=)` and T42 built
that. **Neither was ever CSG-only** — both were unwritten, and naming one in the test quietly
asserted otherwise. What B-9 governs is the refusal, not any particular gap, so the example is now
picked from whatever the parity budget still counts and is expected to keep moving.

### What remains

41 gaps: `rect_tube`'s tapered form (15), `prismoid`'s edge treatments (6), `teardrop`'s cap and
chamfer (5), `teardrop`/`clip_angle` on the cylinders (10), `trimcorners` (2), `regular_prism`'s
`shift` (1), and `cuboid`/`cube`'s `teardrop` (2, which raises `Bosl2NotImplementedError` on CSG
too). `teardrop`/`clip_angle` is the interesting one: a rounding clipped at an angle is a
**non-convex** corner — the arc runs to the clip angle and then goes straight to the cap — so it is
a union of two regions rather than one expression, unlike everything closed so far.


## T43 — Give `prismoid` its edge treatments ✅

**§12.2 item 15. PAR-4, PAR-5, S-2b.**

Six options, refused with a docstring caveat saying that "deriving an exact SDF for a *tapered*
box's independently-radiused vertical edges was out of scope".

**No derivation was needed, because the CSG backend does not derive one either.** It builds the
two end cross-sections and takes their **convex hull** — and a hull's slice at height *t* is the
Minkowski blend `(1−t)A ⊕ tB`. For these shapes that blend is the same shape again:

* a rounded rectangle is `box ⊕ disc`, and Minkowski addition distributes → the slice is a rounded
  rectangle with the half-size **and** the corner radius each linearly interpolated;
* a chamfered rectangle is an octagon whose support function is linear in the size and the
  chamfer → likewise.

So the cross-section is *exact*. The only approximation left is the one this function already
carried: measuring across a taper is not the Euclidean distance to it, though the zero set is
right. **A caveat that says a thing is out of scope is a claim like any other**, and this one had
never been checked against the code it was deferring to.

### The bound was wrong again, in the same way

`shift` moves the **top** section only, and the bound added it to the **bottom** half-size —
reporting a 28-wide box for a solid 20 wide. That is the defect `cyl` carried until T40, in a
second shape. Twice is a pattern, and the cause is structural: every SDF constructor writes its
bound *beside* its field by hand rather than measuring one from the other, so a bound is only as
good as whoever last read the formula next to it.

### Three of five negative controls went green

The first test asked whether every point of the hull's own cross-section is inside the field, and
whether the field's boundary touches it. Both pass **with `rounding=` ignored altogether** — a
plain box contains every rounded version of itself, and the rounded shape touches the box along
its flat edges, which is where the "boundary is touched" check lands. The rounded corners are
interior, and interior points were exactly what the test skipped.

What separates them is the **sharp corner the treatment cuts away**, whose distance outside is
known in closed form: `r(√2 − 1)` for a rounding, `c/√2` for a chamfer. Both linear in the amount,
so asserting the *value* rather than the sign also pins the interpolation between the two ends —
which is what caught the two "not interpolated" controls.

**Containing the right shape is easy if you are simply too big.** Every parity check of this kind
needs the other half, and it is not the half that comes to mind first.

### And four tests asserted the gap as correct behaviour

The fifth instance this session. `test_the_facade_carries_prismoid_edge_treatments_and_refuses_them_on_sdf`
did what its name says, with the docstring *"The SDF prismoid has no exact form for a tapered box's
radiused vertical edges"* — the same claim the constructor's own caveat made, and wrong for the
same reason. **A test that pins a gap in place is only as good as the reason it cites**, and this
one outlived its.

`test_a_real_treatment_is_still_refused` was the other half of B-9's zero-is-not-a-request pairing
and used `prismoid(rounding=5)` as its still-refused example. Like B-9's own worked example, it now
takes one from whatever the parity budget still counts — the third such example to go stale as the
gaps close, which is what it looks like when a suite's examples are drawn from a shrinking list.


## T44 — Build `rect_tube` from the two prismoids it is ✅

**§12.2 item 16. PAR-4, PAR-5, S-2b, C-21. 35 → 20.**

Fifteen arguments, and **every one an argument of the two prismoids the shape is made of.**
`rect_tube` is an outer prismoid with an inner one taken out of it — on both backends — so once
T43 gave the prismoid its taper, shear and edge treatments, there was nothing left to write but
the subtraction.

What there *was* to write was somewhere to put the eighty lines of rule that get from its
twenty-odd arguments to those two shapes: an outer size or a bore plus a wall, either deriving the
other; per-end sizes falling back to the overall one; bore roundings derived from the outer ones
set back by the wall unless named, and cancelled by a chamfer on the same corner.

**This was the third time the same duplication was about to be created.** `center=` ended up in two
contradicting precedences (T40); `default_tex_reps` answered one undecorated call two ways (T41).
It went to `pybosl2._helpers.resolve_rect_tube` instead.

### The bound was wrong for the third time — and the second attempt was wrong in a new way

| attempt | what it said | why it was wrong |
|---|---|---|
| original | bottom half-size + the whole shift | 28 wide for a solid 20 wide |
| T43 | the wider end, symmetric about the origin | a sheared solid is not centred |
| T44 | measured from the eight corners | — |

T43's fix corrected the magnitude and kept the box **symmetric**, which holds only when one end
dominates in both directions — and T43's own tests used exactly that case, so they passed. Three
attempts at a four-line formula, two of them wrong. The cause is structural: every SDF constructor
writes its bound *beside* its field by hand rather than measuring one from the other.

### Two of six negative controls went green, for one reason

Building the bore **without the shear**, and deriving the bore's rounding **without the wall
set-back**, both left the suite green. Both are invisible to a bounding box (which is the outer
prismoid's), to a wall probe on the axis (the shifted centre stays inside the bore either way),
and to anything that never asks about the hole's own corner.

**The tests were all looking at the outside of a shape whose subject is the inside.**

### And two more tests asserted a gap as correct behaviour

`rect_tube(size=20)` with nothing said about the bore raised on the SDF backend and has always
built on CSG — an outer size alone means "just make it a tube", with a 1 mm wall assumed (P-3).
`test_sdf_solid_rejections_say_what_to_pass` asserted the refusal. Sharing the resolver fixed it
by construction; the test had to be repointed.

And B-9's worked example went stale for the **third** time: `spin=` (T40), `cuboid(p1=, p2=)`
(T42), `rect_tube(size1=)` (T44). Not one of the three was ever CSG-only — all three were
unwritten, and naming one in a test quietly asserted otherwise. It is `cyl(teardrop=)` now, and
that is the last kind left: a rounding clipped at an angle is a non-convex corner, so it is the
first gap on that list whose reason is about the field rather than about nobody having written it. Closing them
took a probe at the bore's edge on the side the shear moves it toward, and one at the bore's own
sharp corner — the latter asserted against `max(outer, −bore)` from both closed forms, because
with a thin wall the *outer* surface is the nearer of the two there and an assertion naming only
the bore would have been checking the wrong number.


## T45 — Clip the fillet ✅

**§12.2 item 17. PAR-4, PAR-5, E-5. 20 → 10.**

Ten gaps: one option pair (`teardrop=`, `clip_angle=`) on the five cylinder spellings. **The first
that was different in kind.**

Everything closed on this backend before it was an intersection of convex pieces. A fillet clipped
at an angle is not — the arc runs from the wall down to the clip angle and then goes *straight* to
the end face, leaving a concave vertex where the two meet. It is the full fillet **unioned** with
the wedge between the chord and the end face: `min` of two expressions rather than `max` of
several.

### `teardrop=True` was a one-degree teardrop

`bool` is a subclass of `int`. `cyl_profile` tested `isinstance(teardrop, (int, float))` before
ruling the flag out, so `True` was read as **the angle itself** — a 1° teardrop where the flag
means 45. A rounding with a flat too small to see.

```python
>>> cyl_profile(8, 8, 20, rounding1=2, rounding2=2, teardrop=True)[1]
[6.035, -10.0]     # ... which is teardrop=1
>>> cyl_profile(8, 8, 20, rounding1=2, rounding2=2, teardrop=45)[1]
[7.414, -10.0]     # ... which is what the flag means
```

Nothing caught it because the shape still builds, still looks round, and **its bounding box is
identical either way**. It took writing the rule down somewhere both backends could read it
(`effective_clip`) to notice that the two spellings of "yes" disagreed — the fourth time this
session that sharing a rule found the rule was wrong.

### The profile probe was blind in the middle

`_worst_on_profile` sampled the profile's **vertices**, and everything about the clip flat except
its two endpoints lives in its *interior*. Two of six negative controls passed:

* the wedge's depth wrong (`sin` for `cos`) — invisible at both endpoints;
* its union turned into an intersection — likewise.

It samples the midpoints of **straight** segments too now: the end faces, the wall, and the clip
flat. Chords of the arc are excluded, because a chord sits inside the true circle and that is
faceting rather than a defect. A strictly better instrument for every shape it checks, not only
this one.

### And B-9's worked example went stale a fourth time

`spin=` (T40) → `cuboid(p1=, p2=)` (T42) → `rect_tube(size1=)` (T44) → `cyl(teardrop=)` (T45).
**Not one of the four was ever CSG-only** — all four were unwritten, and naming one in a test
quietly asserted otherwise. Each time it surfaced as a confusing `DID NOT RAISE` three tests away
from the thing that changed.

`test_the_examples_here_are_still_gaps` now reads the *measured* gap table and fails with "both
backends build them now: [...]. Pick another from the budget." A list of examples drawn from a
shrinking set needs something that notices when the set moves out from under it.

### What remains

10 gaps: the `teardrop` *shape*'s own cap and chamfer options (5), `trimcorners` (2),
`regular_prism`'s `shift` (1), and `cuboid`/`cube`'s `teardrop` (2) — the last of which raises
`Bosl2NotImplementedError` on the CSG backend too, so it is a feature neither backend has rather
than a parity gap.


## T46 — The teardrop's own ends ✅

**§12.2 item 18. PAR-4, PAR-5, C-21, B2-1. 10 → 5.**

`cap_h1`, `cap_h2`, `chamfer`, `chamfer1`, `chamfer2` on the `teardrop` shape — `prismoid`'s
argument for the third time. The CSG backend hulls a chain of cross-sections, so the section runs
**piecewise-linearly** along the axis, and a chamfered end is one more station in that chain: set
in by the chamfer, and smaller by it in *both* the radius and the cap. That is what makes the end
a bevel rather than a step.

A teardrop section is convex, and each of its three features — the disc, the two roof planes, the
cap — has a support function linear in the radius and the cap height, so the blend of two of them
is another one with both interpolated. `teardrop_stations` is shared with the CSG backend, the
fourth such rule after `resolve_center_anchor`, `default_tex_reps` and `resolve_rect_tube`.

### The finding is a limit, not a slip

The cross-section check verifies the field against the CSG backend's own outline builder — but **at
the stations `teardrop_stations` computes.** A defect in the stations themselves is invisible to
it: the expectation is derived from the thing under test.

Planting *"the chamfer does not lower the cap"* left **every test green**, including the
cross-backend box, because the middle station still carries the full cap and the box does not
move.

**And sharing the function does not fix it.** A shared defect moves both backends together, so no
parity check can ever see it. That is the limit of the instrument this session has leaned on
hardest.

What covers it is one test that writes the rule out and asserts it directly:

```
front chamfer 1.5 → station at y=-10, radius 6.5, cap 5.5
                    (set in by 1.5, smaller by 1.5 in both)
```

Not a derivation, just the rule — but it fails when the code stops obeying it, which is what a
comparison between two things obeying the same wrong rule cannot do. **Every "both backends agree"
check needs one of these beside it.**

### The staleness guard earned its keep on its first outing

T45 added `test_the_examples_here_are_still_gaps` because B-9's worked example had gone stale four
times, each as a confusing `DID NOT RAISE` three tests away from the change. This run it fired for
real and said which:

```
assert not ['teardrop(cap_h1=)', 'teardrop(chamfer=)']
```

**The pool is nearly empty now** — three options left that one backend builds and the other
refuses, and two more that neither builds. When the last goes, that test and the ones it guards
should be *deleted* rather than kept limping: B-9 will be enforced by there being nothing left to
refuse.

### What remains

5 gaps, none of them "nobody wrote it": `trimcorners` (2, per-corner edge selection on a chamfer),
`regular_prism`'s `shift` (1, needs shear in `polygon_prism`), and `cuboid`/`cube`'s `teardrop`
(2), which raises `Bosl2NotImplementedError` on the **CSG** backend too — a feature neither backend
has rather than a parity gap.


## T47 — `trimcorners`, and the instrument that was there all along ✅

**§12.2 item 19. PAR-4, PAR-5, B2-1. 5 → 3.**

Two gaps. **The finding is the instrument, not the option.**

Every cross-backend check written in T40–T46 was one of two things:

| instrument | what it compares | the hole in it |
|---|---|---|
| `bounds()` on both backends | two analytically computed triples | a box cannot see the shape inside it |
| field vs. a CSG-side builder | `cyl_profile`, `rect_path`, `teardrop_stations` | cannot see what the backend does with what it builds |

**`PyOpenSCAD.mesh()` returns real vertices, and has all along.** The strongest available statement
is simply: *is the field zero at every vertex of the mesh the other backend produces?* I had said
earlier in this session that meshing wasn't available — that was true of the **SDF** side (no
libfive here) and I never checked the CSG side, which can.

### What it settled

No box could distinguish `trimcorners`: the trimmed and untrimmed chamfered cubes have the **same
bounding box** and differ by one vertex out of 24 — the point where three chamfer planes would
otherwise meet. This backend had been building the **untrimmed** solid for a uniform chamfer, with
no way to say so, while CSG trims by default.

The trim is one more plane, `x + y + z = Σhalf − 2c`, read straight off those vertices at four
chamfer sizes.

### And it corrected a wrong guess in the same sitting

The flag reads as though it should apply to a rounding too — BOSL2's own edge-mask code picks a
sphere for the corner when set and three intersecting cylinders when not. But:

```
cuboid(rounding=2, trimcorners=True ).mesh()   ┐ byte-identical,
cuboid(rounding=2, trimcorners=False).mesh()   ┘ at every facet count checked
```

The first version honoured it there, and would have made the two backends disagree on a call they
already agree on. **A plausible reading of the source lost to a measurement of the output**, which
is the same shape as every other finding in this run.

### The pool of refusal examples is down to one

The staleness guard fired again, naming `cube(trimcorners=)` and `cuboid(trimcorners=)`. Three
tests had to be repointed and **one had its premise removed entirely**:
`test_turning_something_off_is_a_request_the_backend_has_to_honour` needed a façade argument with
a *truthy* default that a backend lacks, and `trimcorners` was the only one — two parameters, both
it. There is now no end-to-end call that reaches that branch of `_is_no_op`.

It is a unit test of `_is_no_op` now, saying so. **A unit test that admits what it is beats an
integration test that quietly stopped being one.**

`regular_prism(shift=)` is the last option one backend builds and the other refuses.
`cuboid`/`cube`'s `teardrop` is unbuilt on *both*, so it cannot stand in as an example of a
refusal. When that last one goes, these tests should be **deleted** rather than kept limping —
B-9 enforced by there being nothing left to refuse is the outcome the rule is for.

### Where the parity work stands

**176 → 3.** What closed them was almost never a distance field somebody had to invent; it was
reading what the CSG backend actually does, which more often than not turned out to be "reduce it
to something simple and then build that". The three left are `regular_prism`'s `shift`, and
`cuboid`/`cube`'s `teardrop` — which raises `Bosl2NotImplementedError` on the CSG backend too, so
it is a feature neither backend has rather than a parity gap.


## T48 — The last option gap ✅

**§12.2 item 20. PAR-4, PAR-5, S-2b. 3 → 2, and neither of the two is a parity gap.**

`regular_prism(shift=)` was not a port of the shear — it *is* the shear: the same 4×4 matrix the
CSG backend applies, to a shape in the same frame. What needed reading was **which convention**:

| shape | shear about |
|---|---|
| `cyl`, `regular_prism` | the **mid-plane** — bottom `−shift/2`, top `+shift/2` |
| `prismoid`, `rect_tube` | the **bottom** — only the top moves |

BOSL2 uses both, and the matrix is the only place that says which.

### Two defects came out of it, and neither was about the shear

**The box.** `multmatrix` recomputes it as the transform of the *old box* — the old corners
carried along. Right for a plain prism, too wide for one whose rims are treated: a rounded prism
does not reach full radius at its end faces, and those are exactly the points a shear carries
furthest. 14 wide for a solid 13.2 wide. A loose box is **safe** — it contains the solid, and an
SDF's box is the domain it gets meshed over — which is why it had to be asked about rather than
waited for.

**The anchor, which was measured on the wrong thing entirely.** This backend anchored a regular
prism on its *polygon hull*; the CSG backend anchors it on its **circumscribed cylinder**. So
`regular_prism(sides=6, anchor=BACK)` placed the shape 0.67 mm apart on the two. A hexagon reaches
its circumradius towards a vertex and less towards a face, and BOSL2 anchors a regular prism the
way it anchors the cylinder it is cut from (B2-3).

Pre-existing, nothing to do with `shift` — and **invisible until a test used an anchor other than
`CENTER`.** A sheared hull is still symmetric about the origin, so the centre anchor cannot tell
the two measurements apart. It was the fifth of six negative controls that exposed it: planting
"the anchor follows the shear" left the suite green.

### 176 → 2

The parity measure that opened this run found 176 options one backend had and the other did not.
Two are left, and **neither is something one backend can do and the other cannot**:
`cuboid`/`cube`'s `teardrop` raises `Bosl2NotImplementedError` on the CSG backend as well.

That empties `tests/test_backend_matrix.py`'s refusal examples, exactly as T45 predicted when it
added the staleness guard — and this commit acts on it rather than repointing them a seventh time.

| was | is |
|---|---|
| `test_an_argument_the_backend_cannot_honour_is_refused_not_dropped`, on a real CSG-only option | a test of `refuse_unhonoured` itself, on a synthetic constructor |
| `test_a_newly_reachable_option_builds_on_csg_and_refuses_by_name_on_sdf`, parametrised over gaps | `test_no_option_is_left_that_one_backend_builds_and_the_other_refuses` |
| `test_the_examples_here_are_still_gaps` | deleted — nothing left to go stale |

The examples went stale **six** times (`spin=`, `cuboid(p1=)`, `rect_tube(size1=)`,
`cyl(teardrop=)`, `cuboid(trimcorners=)`, `regular_prism(shift=)`) and **not one of the six was
ever CSG-only** — every one was simply unwritten. The rule was always about the refusal; the
examples were illustrations, and the illustrations kept turning out to be wrong.

The new test does not take "neither backend does it" on trust either: it *calls* `cuboid(teardrop=)`
and requires `Bosl2NotImplementedError`, because that is exactly the kind of claim that quietly
stops being true.


## T49 — Measure the bounds instead of writing them ✅

**§12.2 item 21. S-2b, PAR-5.**

Five bound defects came up in T40–T48, in five places, **each found by accident while doing
something else**:

| where | what it claimed |
|---|---|
| `cyl(shift=)` | widened by the whole shift at *both* ends — 13 wide for a solid 10 wide |
| `prismoid(shift=)` | added the shift to the *bottom* half-size — 28 for a solid 20 |
| the fix for that | kept the box **symmetric**, which a sheared solid is not |
| `multmatrix` after a shear | old box's corners carried along — 14 for a solid 13.2 |
| `rotate` | the rotated corner box — **37% too wide for a sphere** |

Every one is the same mistake: **the box is written by hand beside the field rather than measured
from it**, so it is only as good as whoever last read the formula next to it.

### The fix, and then the instrument

`rotate` now records, per shape, the line or point it may be turned about without moving —
consulted only when the rotation line *is* that line, so a cylinder shifted off the axis and spun
still gets the honest conservative box. `sphere(spin=30)` reports 20 across instead of 27.3.

But the point of this task is the second half. `tests/test_sdf_bounds_are_tight.py` asks, of every
constructor and every option combination that moves a box, two questions:

* does the solid **reach** each face it declares?
* does any of it **escape**?

### The escape half was missing, and two of four controls passed without it

Both were defects that make the box too **small** — a shape keeping its symmetry after being moved
off its own axis, and a sheared cylinder claiming to be rotationally symmetric. That is the
direction that **clips geometry when the field is meshed**: not with an error, but with a shape
that is quietly wrong.

I had written the check for the direction I had been finding defects in, which was the safe one.

A third control was unobservable until its fixture was made asymmetric enough to show it: a
sheared cylinder with a *short* shift fits inside its own unspun box either way, so claiming a
symmetry it does not have changed nothing. `shift=[20, 0]` shows it.

### A guard retired itself

The §12.2 row recording the rotation defect told whoever fixed it to delete `ROUND_ABOUT_Z`, its
test and the row. T40 wrote that test to fail *when the defect went away*:

```
assert spun[0] > plain[0], (
    "the SDF bound is no longer conservative after a spin -- delete ROUND_ABOUT_Z, this test, "
    "and the §12.2 row that records it")
```

It fired, and all three went. The round shapes are compared on `spin` as well as `orient` now,
which is what the exclusion existed to wait for.


## T50 — Audit the layering debt 🔶

**§12.2 item 22. A-1, PAR-1, B-4. 16 → 12 known violations.**

### A quarter of the debt was not debt

`color -> _shape`, `distributors -> _shape`, `path3d -> shapes3d` and `turtle3d -> shapes3d` exist
**only** under `if TYPE_CHECKING`, which the model itself calls *"allowed and unlisted"*. They had
been counted as violations, making the debt look a quarter worse than the code was — which is
precisely what `test_the_debt_lists_are_not_stale` says it exists to prevent.

That test could not see it. It asked whether the edge **existed**:

```python
live = {edge.name for edge in UPWARD}  # every upward edge, of any kind
```

and got "yes" for all four. It asks whether the edge is the right *kind* now. **A check that reads
the right table and asks it the wrong question passes for the wrong reason** — the same shape as
T46's stations and T49's escape half.

### Three functions gated on where they live, not what they do

Measuring the rest turned up something else. `pybosl2.shapes2d` has three `@backend_only("csg")`
functions that build no geometry at all:

| | returns |
|---|---|
| `arc()` | a `Path2D` — 205 lines of plane trigonometry, no native call in it |
| `rect_path()` | a list of points |
| `jittered_poly()` | a list of points |

All three refused under `use_backend("sdf")`. The marker had followed the **module** rather than
the function: they live in `shapes2d` because that is where BOSL2 puts them (B2-3).

### And the false refusal was hiding a real one

`partition_mask` and `partition_cut_mask` call `arc()` for their cut path, so they refused too —
and **looked correctly backend-isolated**. They are not. They build with `pythonscad.polygon`,
`.offset(delta=)` and `.linear_extrude`, and handed back a `CsgSolid` **inside an `sdf` block** the
moment `arc` stopped refusing on their behalf.

They carry the marker themselves now, which is where the reason is true.

**A wrong refusal is worse than no refusal, because it looks like the thing that is missing.**
Nothing was going to find this while a helper three modules away was answering for them.

### What remains

### `arc` moved to the layer it belongs in

`turtle2d -> shapes2d` existed because the turtle needs an arc, and the arc lived in a backend
module. It is path geometry, so it moved to `pybosl2.path2d`, taking `circle_from_corner`, `det2`
and `sign` down to `_helpers` with it. Nothing was left to reach up for. **12 → 11.**

`pybosl2.shapes2d` re-exports it: BOSL2 puts `arc()` there, and B2-3 says a reader following BOSL2
should find it where BOSL2 says it is. All three spellings — `pybosl2.arc`, `pybosl2.shapes2d.arc`,
`pybosl2.path2d.arc` — are the same object.

The per-file budgets moved with it rather than growing: `path2d.py` +1 over-long function and one
more positional tier parameter, `shapes2d/circle.py` −1 of each. **A move is not new debt, and the
totals say so** — which is why these are per-file counts with a checked total rather than one
number that a move could quietly inflate.

### What remains

11 violations, of which **three are runtime module-level** and the rest deferred-but-not-cycles:

* `path2d -> miscellaneous` and `path3d -> miscellaneous` — the `Extrudable` mixin lives in L3 and
  is inherited by L2 types;
* `regions -> shapes3d` — `Region.text3d` reaches the CSG module directly (A-10).


## Keeping this file honest

The mapping table at the top is the contract between this file and the spec. Two ways it goes
stale, both cheap to prevent:

* A task lands but §12.2 keeps its row — fix by moving the row to §12.1 **in the same commit** as
  the code, per SPEC §13 rule 4.
* A new defect is found and only lands here — always add the §12.2 row first; this file never
  holds work the spec does not know about.

When a review turns up something new, the order is: reproduce it as a user would, add the §12.2
row citing the requirement it violates, then add the task here with its plan rules and its test.
