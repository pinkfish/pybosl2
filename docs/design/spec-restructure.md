# Restructuring the spec around a requirements registry

**Status:** proposal · **Author:** architecture review, 2026-08-31
**Touches:** [SPEC.md](../../SPEC.md), [PLAN.md](../../PLAN.md), [TASKS.md](../../TASKS.md), [AGENTS.md](../../AGENTS.md)

This is the plan behind tasks T26–T33. It says what the review found, what the documents should
become, and in what order to get there. It is a design note, not a normative document: when a rule
here lands, it lands in the registry and this file stops being the place to read it.

---

## 1. What the review found

The measurement discipline in this project is unusual and worth keeping — coverage generated from
upstream, ratchets that only shrink, 304 docstring examples type-checked in CI, a contract test
that walks the object surface. What follows is not a criticism of that; it is the observation that
**the discipline has never been pointed at the documents themselves.**

### 1.1 SPEC.md is three documents fused into one

| Part | Share | What it is |
|---|---|---|
| Normative contract | ~35 % | The rules a contributor must obey |
| Embedded rationale | ~25 % | Why each rule exists, and the defect that motivated it |
| §12 conformance history | **40 %** (39 KB) | Closed-item postmortems |

The rationale is the best writing in the repository. It is also what makes the contract
unreadable: a reader looking for "what must I obey" reads 98 KB to find roughly a third of it.

### 1.2 The requirement ID namespace collides

171 numbered requirements in SPEC.md, 70 in PLAN.md, and **five prefixes are used by both
documents with different meanings**:

| Prefix | In SPEC.md | In PLAN.md |
|---|---|---|
| `S-` | Subsystem requirements (S-1 … S-55) | Style rules (S-1 … S-5) |
| `T` | Argument tiers (T1 … T5) | Typing rules (T-1 … T-10) |
| `L` | Architecture layers (L0 … L5) | Language baseline (L-1 … L-4) |
| `O` | — (but cites PLAN's `O-1c`, `O-2`) | Object design (O-0 … O-7) |
| `Q` | Quality gates (Q-1 … Q-6) | — (cites SPEC's) |

`S-2` means "every shape reports its bounds" and "functions stay under 50 lines". SPEC §13 rule 5
makes IDs permanent and citable in commit bodies, so an ambiguous citation is permanently
ambiguous.

### 1.3 The same rule is stated twice

C-7a↔T-4, S-19b↔T-6d, E-1↔E-P4a, C-14↔O-2, S-46a↔O-0a, A-6↔M-2a, R-1↔R-P2, D-5↔E-P5. Every one is
two edits per change and two chances to disagree.

### 1.4 Rules nothing measures have drifted — as the spec itself predicts

> *"A claim of parity that nothing measures is a wish."* — SPEC B2-1

| Rule | States | Reality |
|---|---|---|
| PLAN S-2 | Functions under 50 lines | **243 violations**, the longest 237 lines |
| SPEC C-21 | One operation, one name | `deduplicate`/`deduplicated`, `subdivide`/`subdivide_path`, `resample`/`resample_path` on both path types |
| SPEC A-1 | No lower layer imports a higher | **16 L0→L2 imports**, 4 at module level |
| SPEC A-6 / PAR-1 | No top-level name silently builds on the unselected backend | `Path2D.polygon()` imports `pythonscad` directly and returns a hardcoded `Bosl2Shape2D` |

C-21 and A-1 are *closed* in §12.1 — closed for the surface the test walks, and drifted everywhere
the test does not look. This is the argument for the registry: enforcement is a property of a
requirement, and it belongs in the requirement.

### 1.5 The typing investment does not reach users

The package ships no `py.typed`. Every rule in PLAN §2 — `mypy --strict`, the five `.pyi` stubs,
C-7a's "the point type is the contract" — is invisible to an installed consumer, because PEP 561
requires that marker. The gates Q-1…Q-6 test the source tree; nothing tests the artifact. The
committed `dist/` wheel still contains `solid.pyi`, deleted from the source under T-8.

### 1.6 The façade is the largest maintenance cost in the code

`cyl()` restates roughly 40 parameters in its signature, again in a dict literal, again in its
docstring — then the CSG backend restates them, then the SDF backend, then the stub. 146
parameters across about five sites each. Three stacked filters (`given_arguments` → `for_backend`
→ `refuse_unhonoured`) implement what B-3 describes as one. It has already drifted:
`cuboid(anchor=Anchor.CENTER)` against `cyl(anchor=None)`, where F-P1 says the façade owns the real
default.

### 1.7 `Shape` has become a god-protocol

About 60 members, most typed `*args: Any, **kwargs: Any`. C-20 is satisfied by name-presence and
not by type-safety, and the protocol is now a hand-maintained mirror of two concrete classes.

---

## 2. Decisions taken

Settled with the maintainer before this plan was written:

1. **The SDF backend keeps full-parity status.** PAR-1 stands. The parity apparatus is not trimmed;
   it is made cheaper to honour.
2. **The spec moves to a machine-readable requirements registry**, with SPEC.md and PLAN.md
   generated from it.
3. **The façade adopts argument-group objects.** This is what makes (1) affordable: a group
   forwarded whole is one thing to keep in step, not 146.
4. **0.x breakage stays sanctioned.** No deprecation policy, no stability tiers. A breaking change
   needs a release note.

---

## 3. Target document architecture

| File | Content | Written by |
|---|---|---|
| `spec/requirements.toml` | Every requirement as data: id, statement, keyword, section, enforced_by, status | Hand |
| `SPEC.md` | Normative contract prose | `docs/_reqgen.py` |
| `PLAN.md` | Python mechanics, same registry, `layer = "mechanics"` | `docs/_reqgen.py` |
| `docs/rationale/<ID>.md` | The war stories currently inside the bullets | Hand; linked from the generated prose |
| `CONFORMANCE.md` | §12.1 verbatim, append-only | Moved once, then appended |
| `TASKS.md` | Open work only | Hand |
| `docs/tasks-archive.md` | T0–T25 with their postmortems | Moved once |

TOML rather than YAML: `tomllib` is in the standard library from 3.11, which is this project's
floor, so the registry adds no dependency (PLAN L-4).

### Schema

```toml
[[requirement]]
id = "SPEC-C-7a"
aliases = ["C-7a"]
layer = "contract"            # contract -> SPEC.md, mechanics -> PLAN.md
section = "5. Core object model"
keyword = "MUST"
title = "A point sequence is a Path type"
statement = """
A public parameter meaning an ordered set of points is typed Path2D, Path3D or Path,
and does not accept a bare sequence or a NumPy array.
"""
rationale = "docs/rationale/C-7a.md"
enforced_by = ["tests/test_polyline_parameters.py::test_a_path_annotation_is_backed_by_a_guard"]
status = "enforced"           # enforced | reviewed | unenforced | withdrawn
```

`status = "reviewed"` is an honest third state: a human checks it at review time. It is not the
same as unenforced, and pretending otherwise is what let 1.4 happen.

### What the registry buys

Enforced by `tests/test_requirements.py`:

1. **IDs are unique across both documents.** `SPEC-S-2` and `PLAN-S-2` are the canonical forms;
   the bare spelling survives as an alias only where it is unambiguous.
2. **Every `enforced_by` target resolves** to a test that exists. A rule pointing at a deleted test
   fails the build.
3. **Every citation resolves.** An ID cited in code, a test, or a document must be in the registry.
4. **The documents and the registry do not drift** — every ID in SPEC.md/PLAN.md is in the
   registry and every registry entry appears in its document. Once `_reqgen.py` lands (T27) this
   strengthens into the generated-file equality check `_covgen.py` already uses (DOC-1a, D-P7).
5. **The unenforced backlog only shrinks.** The ratchet this project applies to facets, polyline
   parameters and docstring examples, applied to its own requirements.

**Migration safety:** the first registry is extracted mechanically from the current documents, so
no requirement is lost in transit. Statements are then trimmed by hand and the removed prose moves
to `docs/rationale/`. **No ID is renumbered** — SPEC §13 rule 5 survives intact.

---

## 4. Requirements this review adds or changes

### 4.1 Argument groups — a new `G-` series (SPEC §8)

* **G-1** A parameter family appearing on more than three public callables and always travelling
  together is a frozen group dataclass. The named groups: `Facets(fn, fa, fs, res)`,
  `Placement(anchor, spin, orient)`, `EdgeTreatment(rounding, chamfer, edges, except_edges)`,
  `Texturing(texture, tex_size, tex_reps, tex_depth, tex_inset)`. `CapSpec` (S-24) and `Resolution`
  are the existing precedent.
* **G-2** A group inherits ambiently and composes: `Facets(fn=64)`, `Facets.ambient()`,
  `place.with_(anchor=TOP)`. `None` still means "decide for me" (D-4 unchanged).
* **G-3** The loose BOSL2 spellings survive for the one- or two-member common case —
  `cuboid([60, 40, 12], rounding=4)` must keep working, it is the getting-started promise —
  resolved by one shared helper that raises when a group and its members are both supplied,
  mirroring D-5's conflict rule.
* **G-4** The façade forwards a group as one value. Per-parameter filtering applies only to
  backend-exclusive options, which collapses the three stacked filters into one path.
* **G-5** R-1's plumbing is a `Facets` value passed down, not four parameters re-declared at every
  level. R-1 is the rule most often broken; a group makes honouring it the path of least
  resistance.

### 4.2 Layering, made enforceable

* **A-10** An L0 object's geometry bridge (`Path2D.polygon()`, `linear_extrude`, `stroke`, the
  sweeps) returns `Flat`/`Solid` and builds through the L3 façade, never a backend module. This
  fixes `path2d.py:1465`, a live PAR-1 defect now that full parity is the goal.
* **A-1 restated as data.** The allowed edges live in `spec/layers.toml` and are enforced by a
  test. Module-level L0→L2 imports are errors (4 today); the deferred façade bridge is the one
  sanctioned edge (16 today).

### 4.3 The distribution is part of the contract

* **Q-7** `py.typed` ships, the stubs ship, and CI installs the built wheel into a clean virtualenv,
  imports it, and runs `mypy --strict` over a consumer snippet. Untrack `dist/`.

### 4.4 Two existing rules to settle rather than leave broken

* **C-21** extends to the geometry types, with one test walking every public class for synonym
  pairs.
* **PLAN S-2** is either ratcheted per module or loses its number and keeps "one job per
  function". A rule with 243 violations and no test teaches contributors that the document is
  optional.
* **C-23** (new) A protocol member is typed, or it is on a bounded, shrinking allowlist. Consider
  shared mixins both backends inherit, so the protocol declares what genuinely varies.

---

## 5. Order of work

| Task | Work | Size |
|---|---|---|
| **T26** | Registry + citation/uniqueness/enforcement tests. No behaviour change; produces the real enforced/unenforced number | M |
| **T27** | `docs/_reqgen.py`; doc split into `CONFORMANCE.md`, `docs/rationale/`, `docs/tasks-archive.md`; SPEC/PLAN regenerated | M |
| **T28** | `py.typed`, stub shipping, clean-venv CI gate, untrack `dist/` | XS |
| **T29** | `spec/layers.toml` + test; fix the 4 module-level violations; route L0 bridges through the façade | M |
| **T30** | Argument groups: `Facets` first, then `Placement`, then `EdgeTreatment`/`Texturing` | L |
| **T31** | Façade slimming: one filter path, groups forwarded whole | M |
| **T32** | C-21 sweep on the geometry types; settle S-2 | S |
| **T33** | Protocol typing ratchet (C-23) | M |

T26 first, because it is how everything after it is measured. T28 is an hour's work and is the only
item a user feels immediately. T29 before T30, because both rewrite the same signatures. T31 only
makes sense once the groups exist.
