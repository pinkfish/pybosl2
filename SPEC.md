# pybosl2 — System Specification

**Status:** normative for new and modified code · **Version:** tracks `pybosl2/version.py`
**Companion:** [PLAN.md](PLAN.md) — the Python-level implementation plan.

This document is the **high-level** specification: what pybosl2 is, what it does, how its pieces
fit together, and the contracts every part of it honours. It deliberately says nothing about
Python syntax, typing mechanics, docstring layout, or tooling — those live in
[PLAN.md](PLAN.md), which says *how* these contracts are implemented in Python. When the two
overlap, this document wins on design and the plan wins on mechanics.

Requirement keywords: **MUST**, **MUST NOT**, **SHOULD**, **MAY** (RFC 2119 sense). Requirements
are numbered (`D-3`, `A-7`, …) so reviews and commit messages can cite them.

---

## 1. What the system is

pybosl2 is a **pure-Python 3-D modelling toolkit**: a Python-native port of the
[BOSL2](https://github.com/BelfrySCAD/BOSL2) OpenSCAD library, built to drive
[PythonSCAD](https://pythonscad.org). It provides:

* **Geometry data types** that work in plain CPython with no CAD kernel — points, paths, regions,
  beziers, NURBS, VNF meshes, quaternions, colours, textures, bounds.
* **Shape constructors** — 2-D outlines and 3-D solids — that realize real geometry through one of
  two interchangeable backends: exact CSG (PythonSCAD native) or F-Rep signed-distance fields
  (libfive).
* **A parts library** — gears, screws, bearings, hinges, joiners, truss, hoses, stepper motors,
  bottle caps, threading — driven by trade-size names rather than raw measurements.
* **A generated reference**: API documentation and a visual parts catalogue with metrics measured
  from real rendered STL.

What a user does with it: build a part by naming it, chain operations on it, attach and cut other
parts against it, and render or export the result.

Non-goals: pybosl2 does **not** depend on the BOSL2 OpenSCAD runtime (`osuse()`), does not ship a
mesh kernel of its own, and does not aim for byte-identical output with the original `.scad`.

---

## 2. Relationship to BOSL2: feature parity, not API parity

* **B2-1 Feature compatible.** Anything BOSL2 can build, pybosl2 aims to build — the same shapes,
  the same masks and roundings, the same parts catalogue, the same attachment model. Coverage of
  BOSL2's capabilities is the measure of completeness.
* **B2-2 Not API compatible.** pybosl2 MUST NOT copy OpenSCAD's calling conventions where Python
  has a better answer. A ported `.scad` module is a *specification of behaviour*, not of signature.
  Specifically:
  * Objects and methods replace module-with-children: `solid.attach(TOP, child)`, not nested
    module calls.
  * Chained methods replace transform wrappers: `cuboid(...).up(5).color("red")`, not
    `translate([0,0,5]) color("red") cuboid(...)`.
  * Enums replace magic strings and numbers; `Anchor.TOP` replaces `[0,0,1]`.
  * Python exceptions replace `assert`/`echo` diagnostics.
  * Ambient context (`use_backend`, `use_defaults`) replaces OpenSCAD's `$`-special variables.
  * Keyword-only arguments and real defaults replace long positional argument lists.
* **B2-3 Names are kept where they help.** BOSL2's *names* (`cuboid`, `prismoid`, `rect_tube`,
  `path_sweep`, `rounding=`, `chamfer=`) are retained so a reader can hold the `.scad` source and
  the Python side by side — except where Python forbids the name (`except` → `except_edges`) or a
  clearer Python spelling exists. The names are familiar; the *call shape* is Python's.
* **B2-4 Departures are documented.** Where behaviour deliberately differs from BOSL2, the
  docstring says so and why.

---

## 3. Driving principles

> **A caller who knows what they want to build, but nothing about the library, MUST be able to
> build it. Every parameter a caller is forced to supply is a defect budgeted against the design.**

* **P-1 — One required idea per call.** A constructor MUST be usable with at most **one** required
  argument (the thing being made: a size, a trade-size name, a path). Everything else has a
  default. `sphere()`, `cuboid()`, `star(n=5, r=10)` are correct.
* **P-2 — Defaults are the common case, not the neutral case.** A default MUST be the value most
  callers would have chosen: `anchor=CENTER`, `orient=TOP`, `trimcorners=True`, `head=SOCKET`,
  `thread=COARSE`.
* **P-3 — Derive, do not demand.** Any value computable from the others MUST be optional and
  computed: thread pitch from the screw spec, gear module from circular pitch, a tube's bore from
  its wall.
* **P-4 — Name the thing, not its measurements.** Where a real-world catalogue exists, the primary
  input is the catalogue name — `Screw("M6", length=20)`, `BallBearings.ball_bearing("608")`,
  `NemaMotor(size=17)` — with numeric override still available.
* **P-5 — Progressive disclosure.** Positional arguments are for the one or two things everyone
  supplies; everything else is keyword-only. A caller MUST NOT have to read past the first line of
  a signature to make a shape.
* **P-6 — Every default is overridable.** No behaviour is reachable only through a default.
* **P-7 — Errors teach.** A rejected call MUST say what was wrong *and* what to do instead (§8).
* **P-8 — Objects, not argument bags.** The library is object-oriented by preference: parts,
  paths, regions, meshes, and colours are **classes** that own their operations and expose their
  derived dimensions as properties. A family of free functions sharing a prefix and a pile of
  parameters MUST instead be a class. This is what "a Python port" means here — the *design* is
  Python's, not a transliteration of `.scad` modules.

**Review test:** if the example in a new function's docstring passes more than three arguments to
show the basic case, the defaults are wrong, not the example.

---

## 4. Architecture

```
                      ┌──────────────────────────────────────────────┐
   user code ───────► │ pybosl2/__init__.py — lazy convenience façade │
                      └───────────────┬──────────────────────────────┘
                                      │
        ┌─────────────────────────────┼──────────────────────────────┐
        ▼                             ▼                              ▼
┌────────────────┐          ┌──────────────────┐          ┌────────────────────┐
│ pure geometry  │          │ backend-neutral  │          │  parts library     │
│ paths, path2d, │          │ façade           │          │  pybosl2.parts.*   │
│ path3d, region,│  ◄─────► │ solid.py flat.py │ ◄──────► │  gears, screws,    │
│ beziers, nurbs,│          │ + _backend.py    │          │  bearings, hinges  │
│ vnf, texture,  │          └────────┬─────────┘          └────────────────────┘
│ math, geometry │                   │  dispatch on current_backend()
└────────────────┘          ┌────────┴─────────┐
   no FFI, plain            ▼                  ▼
   CPython + numpy   ┌─────────────┐    ┌─────────────┐
                     │ "csg"       │    │ "sdf"       │
                     │ shapes3d/   │    │ sdf/        │
                     │ shapes2d/   │    │ libfive     │
                     │ PythonSCAD  │    │ F-Rep       │
                     └─────────────┘    └─────────────┘
```

### 4.1 Layers

| Layer | Modules | Contract |
|---|---|---|
| **L0 Pure geometry** | `math`, `vectors`, `points`, `geometry`, `paths`, `path2d`, `path3d`, `regions`, `beziers`, `nurbs`, `quaternions`, `vnf`, `rounding`, `skin`, `texture`, `bounds`, `constants`, `color`, `defaults` | Works in plain CPython with no CAD runtime. MUST NOT import a native module at load time. |
| **L1 Backend contract** | `_backend`, `exceptions`, `caps`, `enums`, `_edges_lang` | Selection machinery and shared protocols only. MUST stay FFI-free. |
| **L2 Backend implementations** | `shapes2d/`, `shapes3d/`, `masking`, `_shape`, `_csg`, `_native`, `_stroke2d`, `_stroke3d` (CSG); `sdf/` (F-Rep) | Reach their native runtime lazily. Each registers itself under a backend name. |
| **L3 Neutral façade** | `solid.py`, `flat.py` | Backend-agnostic constructors returning `Solid` / `Flat`. The recommended entry point for new code. |
| **L4 Parts library** | `parts/` | Built strictly on L0–L3. MUST NOT reach a native runtime directly. |
| **L5 Presentation** | `docs/` | Generated from module headers and docstrings; never a hand-maintained API list. |

**A-1** A lower layer MUST NOT import a higher one.
**A-2** L0 MUST remain usable and tested without any CAD runtime installed.
**A-3** New geometry algorithms belong in L0, with native call sites isolated in L2.

### 4.2 Import surface

* **A-4** `import pybosl2` MUST stay cheap: the top-level names resolve lazily, so no submodule
  (and no native runtime) loads until a name is first touched. Every lazily exported name MUST
  still be statically declared, so editors and type checkers see the full API.
* **A-5** `square`/`circle`/`cube`/`text` intentionally shadow the OpenSCAD builtins with the
  anchor-aware versions, so the package MUST NOT be wildcard re-exported.

---

## 5. Core contracts

### 5.1 Shapes

* **C-1** Every shape carries a `backend` tag. Booleans and transforms return a shape on the
  *same* backend; mixing raises `CrossBackendError` naming the conversion that fixes it.
* **C-2** Operators are the primary spelling: `|` union, `&` intersection, `-` difference.
* **C-3** Shapes are immutable by convention: every operation returns a new shape, so calls chain.
* **C-4** 2-D and 3-D never mix implicitly; a flat shape reaches 3-D only through an explicit
  extrude or sweep.
* **C-5** Shared behaviour (transforms, moves, CSG, colour, tags, distributors) lives once in the
  common base.
* **C-6** Forwarding to a native object is limited to an explicit allowlist, and every forwarded
  name MUST exist on the wrapped object and be statically declared.

### 5.2 Geometry objects

* **C-7** `Path` is abstract; `Path2D`/`Path3D` are selected by point dimension. Any API taking a
  polyline MUST accept a `Path`.
* **C-8** `Region` is outlines-with-holes; `VNF` is the vertex/face mesh interchange type. Anything
  that can produce a mesh SHOULD be able to produce a `VNF`, so it can be inspected with no CAD
  runtime present.
* **C-9** Geometry objects own their operations as methods and return new objects (C-3).

### 5.3 The anchor language

* **C-10** One enum (`Anchor`) covers faces, edges, corners, and axis presets, each member carrying
  its own vector. Any "which face/edge/corner" parameter MUST accept it; new APIs MUST NOT invent a
  parallel string or integer vocabulary.
* **C-11** The `constants.py` names (`TOP`, `LEFT`, `CENTER`, …) are aliases kept for BOSL2
  familiarity; `Anchor.TOP` is preferred in new code and examples.

### 5.4 Parts

* **C-12** Every part is a class (P-8) that resolves its inputs into a frozen **spec object**,
  exposes its derived dimensions as read-only properties, builds geometry lazily under a `shape`
  property, and offers `show()`. Callers can therefore *measure* a part without building it.

---

## 6. Backend model

* **B-1** The active backend is block-scoped and thread-safe, default `"csg"`; `use_backend("sdf")`
  switches it for a block, `set_default_backend()` globally.
* **B-2** A backend implements a small contract: hand back the constructor for a named shape, build
  it, do n-ary booleans, extrude paths, and stroke a path.
* **B-3** Façade constructors MUST forward **only the arguments the caller actually supplied**, so
  each backend keeps its own defaults and never sees an option it has no notion of.
* **B-4** A backend MUST NOT silently approximate a feature it cannot express; it raises
  `UnsupportedByBackendError` with a hint. The CSG-only feature set (attachment/anchoring, 2-D
  geometry, projection) is declared in one place.
* **B-5** Conversion is one-directional and honest: SDF → CSG is an exact mesh; CSG → SDF is lossy
  and not offered implicitly.
* **B-6** Backend-specific extras stay on the backend's own module.
* **B-7** Adding a façade shape requires: the façade constructor, a matching constructor in both
  backends (or an explicit refusal), and a row in the backend matrix tests.
* **B-8** What a caller gets when they leave an argument out MUST be inspectable, not silent:
  `effective_defaults(shape)` reports the active backend's real defaults.

---

## 7. Defaults and resolution

### 7.1 Argument tiers

| Tier | Meaning | Rule |
|---|---|---|
| **T1 — Subject** | *what* is being made: size, spec name, path | At most one, positional, MAY still have a default |
| **T2 — Shaping** | changes the form: `rounding`, `chamfer`, `teeth`, `length` | Keyword; defaults to "off" or to the catalogue value |
| **T3 — Placement** | `anchor`, `spin`, `orient`, `center` | Keyword; defaults `CENTER` / `0` / `TOP` |
| **T4 — Resolution** | `fn`, `fa`, `fs`, `res` | Keyword; defaults to "inherit the ambient value" (§7.3) |
| **T5 — Escape hatch** | `convexity`, `eps`, `method`, `style` | Keyword; defaults to what 95 % of callers want |

* **D-1** T3–T5 MUST be keyword-only; T2 SHOULD be.
* **D-2** A public callable MUST NOT have more than one required parameter without a written
  justification in its docstring. Two is the absolute ceiling.
* **D-3** Defaults MUST be immutable.
* **D-4** `None` means "not supplied, decide for me" — never "off". "Off" is `0`, `False`, or an
  explicit enum member.
* **D-5** Where a dimension has two conventional spellings (`radius`/`diameter`), the API MUST
  accept both, require neither, and reject a conflicting pair by name.
* **D-6** A derivable parameter MUST default to "not given" and be derived.
* **D-7** A spec argument SHOULD accept the convenient forms — trade name, plain number, or an
  explicit mapping — and collapse them immediately into one frozen spec object.
* **D-8** A façade MUST NOT present as optional an argument its backend requires.

### 7.2 Curve resolution is universal

* **R-1** Every constructor that produces a **circle, arc, rounding, chamfer arc, sphere,
  cylinder, sweep, or any other tessellated curve** MUST accept the facet controls — `fn`/`fa`/`fs`
  on the CSG side, `res` on the SDF side — and MUST **pass them through to every sub-construction
  it builds**. A part that rounds its corners hands its `fn` to the rounding; a gear hands it to
  its tooth arcs; a mask hands it to its profile. Dropping them part-way down is a defect.
* **R-2** These controls MUST never be required (D-8 applies): omitted, they inherit (§7.3).
* **R-3** A backend that cannot honour a control MUST NOT be handed it.

### 7.3 Ambient defaults

* **R-4** Resolution SHOULD be settable once for a block rather than threaded through every call:
  `use_defaults(fn=64)` (block-scoped, nesting, thread-safe) and `set_defaults(...)` (process-wide).
* **R-5** An explicitly passed value always wins over the ambient one.
* **R-6** Ambient values are resolved at **construction** time, so a shape's smoothness is fixed by
  where it was built.
* **R-7** With nothing set anywhere, the renderer's own defaults apply (`$fa=12`, `$fs=2`).

### 7.4 Units and frame

* **D-9** Lengths are millimetres, angles are degrees, the frame is right-handed Z-up. No API takes
  a unit argument; `INCH` converts at the call site.
* **D-10** Shapes are centred on the origin, oriented `+Z`, unrotated by default.

---

## 8. Error contract

* **E-1** All library errors derive from one base error type.
* **E-2** A refusal names the feature, the backend, and the alternative.
* **E-3** Cross-backend mixing names both operands and the conversion that resolves it.
* **E-4** Argument validation raises `ValueError` naming the offending parameter(s) and the
  accepted spellings. A public entry point MUST NOT `assert` on user input.
* **E-5** A call that cannot mean what it says MUST fail loudly rather than build something else.

---

## 9. Documentation and catalogue

* **DOC-1** Docs are **generated** from the source: module header tags drive the API reference, and
  docstring examples drive the rendered figures. An API list is never hand-maintained.
* **DOC-2** Every public module, class, and callable is documented, and every callable that
  produces geometry carries an example that renders.
* **DOC-3** The visual parts catalogue renders each featured part through the real PythonSCAD
  binary and reports measured metrics — triangles, volume, bounding box, watertightness. Its
  caches are committed, because CI has no CAD binary.
* **DOC-4** Mechanics — docstring style, header tag values, build commands — are specified in
  [PLAN.md §5](PLAN.md).

---

## 10. Quality gates

A change is done when all of these hold (mechanics in [PLAN.md §9–§11](PLAN.md)):

* **Q-1** The full test suite passes; pure-geometry tests pass with no CAD runtime present.
* **Q-2** Strict static type checking passes with zero errors.
* **Q-3** Lint and format are clean.
* **Q-4** Every new public callable has a minimum-argument test — the mechanical enforcement of
  P-1 — and a validated docstring example.
* **Q-5** The contract tests guarding these rules (mutable defaults, façade honesty, stub parity,
  facet coverage, backend matrix) still pass.

---

## 11. Conformance status

### 11.1 Closed

| Requirement | What was wrong | Resolution |
|---|---|---|
| **R-4** | No ambient resolution defaults; `fn`/`fa`/`fs`/`res` had to be threaded through every call | `pybosl2/defaults.py`: `use_defaults()` / `set_defaults()` / `reset_defaults()`, resolved in `frag_count`, the native cylinder/sphere/circle wrappers, and both backends' `construct` |
| **A-4** | The top-level package had no stub, so its lazy exports were invisible to type checkers and IDEs | `pybosl2/__init__.pyi`, kept in step by `tests/test_init_stub.py` |
| **A-4 / P-5** | Backend switching was reachable only through a private module | `use_backend`, `set_default_backend`, `current_backend`, `known_backends` (plus the defaults API and the error types) are now top-level exports |
| **D-3** | 19 mutable list defaults in signatures, 9 more in stubs | All converted to tuples; guarded by a test that scans the package |
| **B-8 / P-2** | The façade deferred to backend defaults silently | `effective_defaults(shape, backend=None)` reports them live off the constructor |
| **D-8** | `prismoid()` and `regular_prism()` presented backend-required arguments as optional | Made honestly required; guarded by a façade-honesty test |
| **E-4 / P-1** | `rect_tube()`, `torus()`, `tube()` asserted on user input; empty booleans raised `reduce()` errors | All replaced with `ValueError`s naming the accepted spellings; `rect_tube` now derives a 1 mm wall from an outer size alone |
| **C-1** | The 2-D shape protocol was typed `Any -> Any`, so 2-D chains lost static checking | `Flat` and `Solid` protocols fully typed |
| packaging | `requires-python = ">=3.10"` with a 3.10 classifier, but `StrEnum` (3.11+) is used in ~30 places | Floor raised to 3.11 |
| hygiene | `pybosl2/distributors.py.bak` shipped inside the package; 854 MB of pytest scratch in the repo root | Removed; `pytest-of-*/` added to `.gitignore` |

### 11.2 Open

| # | Requirement | Current state |
|---|---|---|
| 1 | **R-1** | **50 of 119** public curved-geometry callables do not accept `fn`/`fa`/`fs`, so ambient defaults are their only resolution control — among them `Region.offset`/`round_corners`, `Path2D.minkowski_sum_circle`, `shapes2d.star`/`supershape`, the `RegularPolyhedron` factories, and `edge_profile`/`edge_profile_asym`. `tests/test_facets.py` pins the list so it can only shrink. |
| 2 | **P-8** | The parts library is fully class-based, but a few geometry areas remain function-families that would read better as classes — `masking.mask2d_*`/`mask3d_*`, `isosurface.mb_*`, and the `turtle2d`/`turtle3d` pair. |
| 3 | **B2-1** | BOSL2 feature coverage is not yet tracked anywhere; there is no gap list saying which `.scad` modules remain unported. |

---

## 12. Change process

1. A change altering a public signature MUST cite the requirement it serves in the commit body
   (`feat(solid): ambient resolution defaults — R-4`).
2. Adding a required parameter to an existing public callable is a breaking change and needs a
   default or a deprecation path.
3. Adding a façade shape follows B-7.
4. This document is updated in the same commit as any change to §4 (layering), §6 (backend
   contract), or §7 (defaults). Language-level rules change in [PLAN.md](PLAN.md) instead.
