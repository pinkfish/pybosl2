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
| — | E-4 follow-up | [T11](#t11--cover-the-rejection-paths-) ✅ | L |
| — | P-8 / coverage | [T12](#t12--partitions-cover-it-and-find-out-why-it-was-not-covered-) ✅ | M |
| — | test quality | [T13](#t13--replace-the-existence-only-tests-) ✅ | L |
| — | S-46a / PAR-1 | [T14](#t14--give-parts-an-sdf-form-where-they-have-one-) 🔶 | XL |
| — | bug | [T15](#t15--from_svg-loses-even-odd-holes-when-the-svg-has-a-viewbox-) ✅ | S |
| 2 | S-2b | [T16](#t16--one-bounds-type-everywhere) ✅ | M |
| 3 | C-20 / C-21 / C-22 | [T17](#t17--make-the-contract-the-whole-object) ✅ | L |
| 4 | S-19a / S-19b / S-19c | [T18](#t18--make-a-sweep-return-a-solid) ✅ | M |
| 5 | S-53 / S-54 / S-55 | [T19](#t19--give-the-library-a-way-out) ✅ | M |
| 6 | E-1 / E-5 / E-6 / E-7 | [T20](#t20--make-the-error-contract-usable) ✅ | M |
| 7 | A-8 / A-9 | [T21](#t21--export-the-families-whole) ✅ | S |
| 8 | S-26a … S-26c | [T22](#t22--make-the-masks-obey-the-librarys-own-rules) ✅ | L |
| 9 | DOC-5 / DOC-6 / Q-6 | [T23](#t23--type-check-the-examples-and-build-a-front-door) ✅ | M |
| 3 | spec maintainability | [T26](#t26--make-the-requirements-measurable) ✅ | M |
| 3 | spec maintainability | [T27](#t27--generate-the-prose-from-the-registry) ✅ | M |
| 5 | Q-7 | [T28](#t28--test-what-ships) ✅ | XS |
| 4 | A-1 / A-6 / A-10 / PAR-1 | [T29](#t29--make-the-layering-true) ✅ | M |
| 9 | PAR-3 / B-5 / B-P4 | [T34](#t34--decide-what-fill-means-on-a-distance-field) | S |
| 7 | G-1 … G-5 | [T30](#t30--group-the-arguments-that-travel-together) 🔶 | L |
| 7a | PLAN D-P4 / DOC-2 | [T35](#t35--give-every-public-callable-an-args-section) | M |
| 7b | PLAN O-6b | [T36](#t36--give-text-the-anchor-language) | S |
| 7c | G-8 / S-34 / S-35 | [T37](#t37--build-texture-or-stop-advertising-it) | L |
| 7 | B-3 / G-4 | [T31](#t31--slim-the-façade) | M |
| 6 | C-21 / PLAN S-2 | [T32](#t32--close-the-two-rules-that-only-half-closed) ✅ | S |
| 8 | C-23 / C-20 | [T33](#t33--type-the-contract) ✅ | M |

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

## T34 — Decide what `fill` means on a distance field

**Closes:** §12.2 item 9 · **Implements:** PAR-3, B-5, PLAN B-P4 · **Size:** S
**This one needs a decision before any code moves.**

`fill` is in `CSG_ONLY_FEATURES` and `PyShape2D.fill()` works anyway, by extruding the field,
meshing it, crossing to CSG, projecting, and rebuilding a polygon. Two records disagree:

* **PAR-3 / B-P4** say an exclusive feature is *declared and refuses*, and name this exact case as
  the one that must never happen.
* **B-5** says a lossy backend conversion is never implicit, and a mesh round trip is one.
* **`tests/test_sdf_shapes2d.py::TestFill`** asserts the meshing margin, so the behaviour is
  deliberate and someone wanted it.

Either answer closes it, and they are genuinely different products:

1. **`fill` refuses on SDF**, naming `.to_csg()`, as `projection` does after T4. Consistent with
   PAR-3 and B-5; costs the SDF backend a working operation.
2. **`fill` leaves `CSG_ONLY_FEATURES`**, and the round trip is documented as what it is. Honest
   about what the code does; needs B-5 to say that an *explicit, documented* round trip inside one
   named operation is not the implicit conversion it forbids.

**Whichever is chosen, the general finding stands and is worth more than either:** the backend
parity tests walk the solid classes and not the 2-D ones, so nothing was ever going to catch this.
That gap is the first thing to close.

**Done when:** the lists and the code agree, and the parity tests cover `CsgShape2D`/`PyShape2D`
the way they cover the solids.

---

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

## T35 — Give every public callable an `Args:` section

**Closes:** §12.2 item 7a · **Implements:** PLAN D-P4, DOC-2 · **Size:** M

57 public callables document no arguments at all. Found by T30's sweep: 97 facet parameters could
not be documented because their callable has no `Args:` section to put them in, and adding a partial
one listing only `fn`/`fa`/`fs` would read as though the others are not parameters.

D-P4 has asked for complete `Args:` since it was written and nothing has ever checked, which is the
same story as A-1, C-21 and S-2 before them.

1. The list is in `tests/test_ambient_docs.py::KNOWN_GAPS`, 97 rows across 57 callables.
2. Write the sections. The facet clause then lands with the rest, and the rows come off the list.
3. Generalise the check: every public callable's `Args:` covers every parameter it declares.

**Done when:** `KNOWN_GAPS` is empty and the general D-P4 check replaces it.

---

## T31 — Slim the façade

**Closes:** §12.2 item 7 (second half) · **Needs:** T30 · **Size:** M
**Risk:** medium

Three filters stack where B-3 describes one, and F-P1's "the façade owns the real default" is
already untrue: `cuboid(anchor=Anchor.CENTER)` beside `cyl(anchor=None)`.

1. One filter path: the façade forwards everything it declares, groups whole, and the backend
   filters by what it declares (F-P2). `given_arguments`'s None-dropping goes.
2. Sweep the façade for defaults that are `None` where the backend has a real one, which is what
   `effective_defaults()` already knows and can be asserted against.
3. A test asserts every façade constructor's shared defaults match the backends' agreed value —
   the existing `test_backends_agree_on_the_defaults_they_share` extended to the façade itself.

**Done when:** one forwarding path remains; no shared argument defaults to `None` at the façade
unless `None` genuinely means "decide for me" (T-9b).

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

## T34 — Decide what `fill` means on a distance field

**Closes:** §12.2 item 9 · **Implements:** PAR-3, B-5, PLAN B-P4 · **Size:** S
**This one needs a decision before any code moves.**

`fill` is in `CSG_ONLY_FEATURES` and `PyShape2D.fill()` works anyway, by extruding the field,
meshing it, crossing to CSG, projecting, and rebuilding a polygon. Two records disagree:

* **PAR-3 / B-P4** say an exclusive feature is *declared and refuses*, and name this exact case as
  the one that must never happen.
* **B-5** says a lossy backend conversion is never implicit, and a mesh round trip is one.
* **`tests/test_sdf_shapes2d.py::TestFill`** asserts the meshing margin, so the behaviour is
  deliberate and someone wanted it.

Either answer closes it, and they are genuinely different products:

1. **`fill` refuses on SDF**, naming `.to_csg()`, as `projection` does after T4. Consistent with
   PAR-3 and B-5; costs the SDF backend a working operation.
2. **`fill` leaves `CSG_ONLY_FEATURES`**, and the round trip is documented as what it is. Honest
   about what the code does; needs B-5 to say that an *explicit, documented* round trip inside one
   named operation is not the implicit conversion it forbids.

**Whichever is chosen, the general finding stands and is worth more than either:** the backend
parity tests walk the solid classes and not the 2-D ones, so nothing was ever going to catch this.
That gap is the first thing to close.

**Done when:** the lists and the code agree, and the parity tests cover `CsgShape2D`/`PyShape2D`
the way they cover the solids.

---

## T30 — Group the arguments that travel together

**Closes:** §12.2 item 7 (first half) · **Implements:** G-1 … G-5 (new) · **Size:** L
**Risk:** high — public signatures change across the façade, both backends and the parts library

`cyl()` takes about 40 keywords in one flat namespace. The same four facet controls are
re-declared at every level of every call chain, which is why R-1 is the rule most often broken.

1. **G-1 … G-5** (new, §8) land in the registry first, per T26's rules.
2. `Facets(fn, fa, fs, res)` first: frozen, with `Facets.ambient()` resolving the block defaults
   (R-4) once. It is the least visible group and the one that fixes the most R-1 plumbing.
3. Then `Placement(anchor, spin, orient)`, then `EdgeTreatment` and `Texturing`.
4. One shared resolver accepts either the group or its loose members and raises when given both,
   mirroring D-5's conflict rule — so `cuboid([60, 40, 12], rounding=4)` keeps working, because it
   is the getting-started promise and P-1 itself.
5. Each group is one value through the façade → backend boundary (G-4).

**Done when:** a test asserts a group and its loose members together raise, naming both; ambient
resolution reaches a leaf constructor through one `Facets` rather than four parameters; the facet
backlog in `tests/test_facets.py` has not grown.

---

## T31 — Slim the façade

**Closes:** §12.2 item 7 (second half) · **Needs:** T30 · **Size:** M
**Risk:** medium

Three filters stack where B-3 describes one, and F-P1's "the façade owns the real default" is
already untrue: `cuboid(anchor=Anchor.CENTER)` beside `cyl(anchor=None)`.

1. One filter path: the façade forwards everything it declares, groups whole, and the backend
   filters by what it declares (F-P2). `given_arguments`'s None-dropping goes.
2. Sweep the façade for defaults that are `None` where the backend has a real one, which is what
   `effective_defaults()` already knows and can be asserted against.
3. A test asserts every façade constructor's shared defaults match the backends' agreed value —
   the existing `test_backends_agree_on_the_defaults_they_share` extended to the façade itself.

**Done when:** one forwarding path remains; no shared argument defaults to `None` at the façade
unless `None` genuinely means "decide for me" (T-9b).

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

## T33 — Type the contract

**Closes:** §12.2 item 8 · **Implements:** C-23 (new) · **Size:** M

`Shape` declares about 60 members and most are `*args: Any, **kwargs: Any`, so C-20 holds by
name-presence rather than by type-safety, and the protocol is a hand-maintained mirror of two
concrete classes.

1. **C-23** (new, §5.1): a protocol member is typed, or it is on a bounded allowlist that only
   shrinks — the same shape as every other ratchet here.
2. Type the members whose two backend signatures already agree; those are free.
3. For the rest, consider what T-6c hints at from the other side: a shared mixin both backends
   inherit means the protocol declares what genuinely varies rather than everything both do.

**Done when:** the `Any`-typed member count is written down and only shrinks.

---

## T36 — Give `text()` the anchor language

**Closes:** §12.2 item 7b · **Implements:** PLAN O-6b · **Size:** S

`flat.text()` declares `anchor: str = "baseline"`. O-6b requires a parameter meaning "which face,
edge or corner" to be `Anchor | Sequence[float]` and resolved through `resolve_anchor()`, and the
other eight 2-D façade constructors do exactly that. This one is a parallel vocabulary the reader
has to learn twice — the defect O-6b exists to prevent.

Found because it is the one 2-D constructor `placement=` could not be wired into (T30): a
`Placement` carries an `Anchor`, and this does not.

**Retyping it is not the fix.** The typographic anchors — `"baseline"`, and the `halign`/`valign`
vocabulary beside it — mean things `Anchor` has no member for, and a baseline is genuinely not a
bounding-box anchor. So the options are a text-specific enum (O-6) alongside the ordinary `anchor`,
or folding the typographic ones into `halign`/`valign` where they belong and leaving `anchor` to
mean what it means everywhere else. That is a design decision, which is why this is its own task.

**Done when:** `text()` takes the anchor language like every other constructor, `placement=` is
wired into all nine, and the typographic vocabulary has a home of its own.

---

## T37 — Build `texture=`, or stop advertising it

**Closes:** §12.2 item 7c · **Implements:** SPEC S-34, S-35, G-8 · **Size:** L

Thirteen public constructors declare `texture`, `tex_size`, `tex_reps`, `tex_depth` and
`tex_inset`. Every call that sets them refuses. S-34 and S-35 do not describe an aspiration — they
say named textures come from one registry and that *anything that can be textured* accepts them —
so the spec and the signatures agree with each other and disagree with the code.

The registry half is built: `texture("diamonds")` returns its tile, and `textured_tile()` exists.
What is missing is applying a tile to a curved surface, which is BOSL2's `vnf_vertex_array` path.

1. Apply a height-field or VNF tile to a cylinder's side, which is what all five cylinder
   constructors want.
2. Then the rest of the thirteen, or narrow the signatures to the ones that work.
3. `Texturing` (G-1) lands with it: the five parameters travel together on all 11 callables that
   take more than one, which is the cleanest group in the library — once there is something to
   group.
4. Remove the row from `tests/test_unimplemented.py::KNOWN_GAPS`.

**The alternative is honest too:** withdraw the parameters from the signatures and say in S-34/S-35
that this port ships the registry and not the application. What is not tenable is the present
state, where a signature promises something no call delivers.

**Done when:** either `cyl(texture="diamonds")` builds a textured cylinder, or the parameter is
gone and the spec says so.

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
