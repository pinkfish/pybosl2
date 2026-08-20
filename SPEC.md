# pybosl2 — System Specification

**Status:** normative for new and modified code · **Version:** matches `pybosl2/version.py` (0.7.10)
**Audience:** contributors and agents working in this repository.

This document specifies *what pybosl2 is*, *how its pieces fit together*, and *the rules every
public API must follow*. `AGENTS.md` specifies style, typing, and docstring mechanics; this
document specifies structure and API shape. Where they overlap, `AGENTS.md` wins on formatting and
this document wins on design.

Requirement keywords: **MUST**, **MUST NOT**, **SHOULD**, **MAY** (RFC 2119 sense). Requirements
are numbered (`D-3`, `A-7`, …) so reviews and commit messages can cite them.

---

## 1. Purpose and scope

pybosl2 is a pure-Python / NumPy port of the [BOSL2](https://github.com/BelfrySCAD/BOSL2)
OpenSCAD library for use with [PythonSCAD](https://pythonscad.org). It provides:

* **Geometry data types** that work in plain CPython with no CAD kernel — points, paths, regions,
  beziers, NURBS, VNF meshes, quaternions, textures.
* **Solid and flat constructors** that realize real geometry through one of two interchangeable
  backends: exact CSG (PythonSCAD native) or F-Rep/signed-distance fields (libfive).
* **A parts library** — gears, screws, bearings, hinges, joiners, truss, hoses, steppers — built
  from those primitives and driven by trade-size names rather than raw measurements.

Non-goals: pybosl2 does **not** depend on the BOSL2 OpenSCAD runtime (`osuse()`), does not ship a
mesh kernel of its own, and does not attempt bit-exact parity with BOSL2's `.scad` output where a
better-typed Python design exists.

---

## 2. Driving principle: the API is the product

> **A caller who knows what they want to build, but nothing about the library, MUST be able to
> build it. Every parameter a caller is forced to supply is a defect budgeted against the design.**

This is the top-priority constraint on every public function, class, and method. Concretely:

* **P-1 — One required idea per call.** A constructor MUST be usable with at most **one** required
  argument (the thing being made: a size, a trade-size name, a path). Everything else MUST have a
  default. `sphere()`, `cuboid()`, `star(n=5, r=10)` are correct; a constructor requiring four
  measurements to produce a first result is not.
* **P-2 — Defaults are the common case, not the neutral case.** A default MUST be the value most
  callers would have chosen, not the mathematically empty one. `anchor=CENTER`, `orient=TOP`,
  `trimcorners=True`, `head=SOCKET`, `thread=COARSE` are correct defaults because they are what
  people mean.
* **P-3 — Derive, do not demand.** Any value computable from the others MUST be optional and
  computed. Thread pitch derives from the screw spec; gear module derives from circular pitch;
  `thread_len` derives from `length`; the second radius of a cylinder derives from the first.
* **P-4 — Name the thing, not its measurements.** Where a real-world catalogue exists, the primary
  input MUST be the catalogue name — `Screw("M6", length=20)`, `BallBearings.ball_bearing("608")`,
  `NemaMotor(size=17)` — with numeric override still available.
* **P-5 — Progressive disclosure.** Positional arguments are for the one or two things everyone
  supplies; everything else is keyword-only. A caller MUST NOT have to read past the first line of a
  signature to make a shape.
* **P-6 — Every default is overridable.** No behaviour may be reachable only through a default.
  There is always an explicit spelling.
* **P-7 — Errors teach.** A rejected call MUST say what was wrong *and* what to do instead
  (see §8).

**Review test:** if the example in a new function's docstring passes more than three arguments to
show the basic case, the defaults are wrong, not the example.

---

## 3. Architecture

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

### 3.1 Layers

| Layer | Modules | Contract |
|---|---|---|
| **L0 Pure geometry** | `math`, `vectors`, `points`, `geometry`, `paths`, `path2d`, `path3d`, `regions`, `beziers`, `nurbs`, `quaternions`, `vnf`, `rounding`, `skin`, `texture`, `bounds`, `constants` | MUST import cleanly in plain CPython with only `numpy`/`shapely`/`svgelements`. MUST NOT import `pythonscad`, `openscad`, or `libfive` at module scope. |
| **L1 Backend contract** | `_backend`, `exceptions`, `caps`, `enums`, `_edges_lang` | Selection machinery and shared protocols only. MUST stay FFI-free. |
| **L2 Backend implementations** | `shapes2d/`, `shapes3d/`, `masking`, `_shape`, `_csg`, `_native`, `_stroke2d`, `_stroke3d` (CSG); `sdf/` (F-Rep) | MAY import their native runtime lazily. Each registers itself under a backend name. |
| **L3 Neutral façade** | `solid.py`, `flat.py` | Backend-agnostic constructors returning `Solid` / `Flat`. This is the recommended entry point for new user code. |
| **L4 Parts library** | `parts/` | Built strictly on L0–L3. MUST NOT reach into a native runtime directly. |
| **L5 Presentation** | `docs/`, `docs/_specgen.py`, `docs/_rstgen.py` | Generated from module headers and docstrings; never hand-maintained lists of APIs. |

**A-1** A lower layer MUST NOT import a higher one. `parts/` may import `solid`; `solid` may not
import `parts`.
**A-2** L0 modules MUST remain usable (and tested) without any CAD runtime installed.
**A-3** New geometry algorithms belong in L0 with the native call sites isolated in L2.

### 3.2 Import surface

* `import pybosl2` MUST stay cheap. The top-level package resolves names through
  `_LAZY_EXPORTS` + `__getattr__`, so no submodule (and no native runtime) loads until a name is
  first touched.
* **A-4** Every lazily exported name MUST also appear in `__all__` and MUST be declared in a
  `.pyi` stub so IDEs and `mypy --strict` see it statically (as `shapes2d/__init__.pyi` and
  `shapes3d/__init__.pyi` already do). Dynamic export without a stub is a violation of
  `AGENTS.md`'s "no magic `__getattr__`" rule.
* **A-5** `square`/`circle`/`cube`/`text` intentionally shadow OpenSCAD builtins with the
  anchor-aware versions. The package therefore MUST NOT be wildcard re-exported, and docstrings
  MUST use explicit imports.

---

## 4. Core type contracts

### 4.1 `Solid` (3-D) and `Flat` (2-D)

Both are `Protocol`s in `_backend.py` / `flat.py`, satisfied by `CsgSolid` (`shapes3d/base.py`) and
`PyShape` (`sdf/shapes3d.py`).

* **C-1** Every shape carries a `backend: str` tag. Booleans and transforms return a shape on the
  *same* backend; mixing raises `CrossBackendError` with the conversion that fixes it.
* **C-2** Operators are the primary spelling: `|` union, `&` intersection, `-` difference. Named
  methods exist as synonyms for readability, never as the only spelling.
* **C-3** Shapes are **immutable by convention**: every transform returns a new shape, so calls
  chain (`cuboid([20,20,10]).up(5).color("red")`). A method that mutates in place is a defect.
* **C-4** 2-D and 3-D never mix implicitly. A `Flat` reaches 3-D only through an explicit
  `linear_extrude` / `rotate_extrude` / sweep. Docstring examples that export STL MUST extrude
  first.
* **C-5** Shared behaviour (transforms, directional moves, CSG, colour, distributors, tags) lives
  once in `_shape.BaseShape`. Duplicating it in a subclass is a defect.
* **C-6** Native-object forwarding is limited to the explicit `_NATIVE_PASSTHROUGH` allowlist, and
  every forwarded name MUST exist on the wrapped native object and be typed in `_shape.pyi`.

### 4.2 Paths, regions, meshes

* **C-7** `Path` is abstract; `Path2D` and `Path3D` are the concrete types, selected by
  `Path.__new__` from the point dimension. Any API taking a polyline MUST accept a `Path` object —
  not a bare `list[Sequence[float]]` — per `AGENTS.md`.
* **C-8** `Region` is outlines-with-holes; `VNF` is the vertex/face mesh interchange type. Anything
  that can produce a mesh SHOULD be able to produce a `VNF`, so it can be inspected without a CAD
  runtime.
* **C-9** Path/region/mesh operations are fluent and return new objects, matching C-3.

### 4.3 The anchor language

`_edges_lang.Anchor` is a single enum covering faces, edges, corners, and axis presets, each member
carrying its own 3-D vector.

* **C-10** Any parameter meaning "which face/edge/corner" MUST accept `Anchor` (and MAY additionally
  accept a raw vector for BOSL2 compatibility). New APIs MUST NOT invent a parallel string or
  integer vocabulary.
* **C-11** `constants.py` names (`TOP`, `LEFT`, `CENTER`, …) are aliases of `Anchor` members kept
  for BOSL2 familiarity; `Anchor.TOP` is the preferred spelling in new code and in examples.

---

## 5. Backend contract

* **B-1** The active backend is a `contextvars.ContextVar`, default `"csg"`. It is selected with
  `use_backend("sdf")` (block-scoped, async/thread safe) or `set_default_backend()` (global).
* **B-2** A backend implements the `SolidBackend` protocol: `construct(shape, arguments)`,
  `polyhedron`, `union` / `difference` / `intersection`, `linear_extrude`, `stroke`. It registers
  itself with `register_backend(name, impl)` at import.
* **B-3** Façade constructors MUST forward **only the arguments the caller actually supplied**, via
  `given_arguments()`. This is the mechanism that lets each backend keep its own defaults and lets
  the façade stay silent about options a backend has never heard of. It is required, not optional.
* **B-4** A backend MUST NOT silently approximate a feature it cannot express. It raises
  `UnsupportedByBackendError(feature, backend, hint=...)`. `CSG_ONLY_FEATURES` in `_backend.py` is
  the authoritative list of the attachment/anchor and 2-D operations the SDF backend refuses.
* **B-5** Conversion is one-directional and honest: `sdf_solid.to_csg()` is an exact
  mesh→polyhedron; CSG→SDF is lossy and not offered implicitly.
* **B-6** Backend-specific extras stay on the backend's own module (`pybosl2.shapes3d`,
  `pybosl2.sdf`). The façade carries only what both can honour, plus per-backend resolution knobs
  (`fn`/`fa`/`fs` for CSG, `res` for SDF) which are ignored-by-omission on the other side.
* **B-7** Adding a shape to the façade requires: the constructor in `solid.py`/`flat.py`, a matching
  `construct` name in both backends (or an explicit `UnsupportedByBackendError`), and a row in the
  backend matrix tests (`tests/test_backend_matrix.py`).

---

## 6. Default-value specification

This section makes §2 mechanical. It applies to every public callable.

### 6.1 Argument tiers

Every parameter falls in exactly one tier:

| Tier | Meaning | Rule |
|---|---|---|
| **T1 — Subject** | *what* is being made: size, spec name, path | At most one, positional, MAY still have a default (`cuboid()` → unit cube) |
| **T2 — Shaping** | changes the result's form: `rounding`, `chamfer`, `teeth`, `length` | Keyword, defaults to "off" or to the catalogue value |
| **T3 — Placement** | `anchor`, `spin`, `orient`, `center` | Keyword, defaults `CENTER` / `0` / `TOP` |
| **T4 — Resolution** | `fn`, `fa`, `fs`, `res`, `slices`, `steps` | Keyword, defaults `None` = inherit ambient (§6.3) |
| **T5 — Escape hatch** | `convexity`, `eps`, `method`, `style` | Keyword, defaults to the value 95 % of callers want; documented as advanced |

* **D-1** T3, T4, and T5 parameters MUST be keyword-only (`*` in the signature). T2 SHOULD be.
* **D-2** A public callable MUST NOT have more than one required parameter without a written
  justification in its docstring. Two is the absolute ceiling (e.g. `Screw(spec, length)`).
* **D-3** Defaults MUST be immutable: `None`, a number, a string, a tuple, or an enum member.
  A mutable default (`[1, 1, 1]`, `{}`) is a defect even when not mutated — use a tuple.
* **D-4** `None` means "not supplied, decide for me" — never "off". "Off" is `0`, `False`, or an
  enum member such as `ScrewDriveType.NONE`.

### 6.2 Redundant and derived spellings

* **D-5** Where a dimension has two conventional spellings (`radius`/`diameter`,
  `radius1`/`radius2` vs `diameter1`/`diameter2`), the API MUST accept both, require neither, and
  raise `ValueError` naming both parameters when they conflict.
* **D-6** A parameter derivable from others MUST default to `None` and be derived. Examples in the
  current code that are correct and MUST be preserved as the pattern: `ScrewSpec` deriving pitch
  from `"M6"`/`"M8x1"`, `GearSpec` deriving module/pitch radius/root radius from teeth+module,
  `Path.tangents()` deriving `closed` from the path itself.
* **D-7** A spec argument SHOULD accept a widening union of *convenience* forms — trade name
  (`"M6"`), plain number (bare diameter), or a dict of explicit fields — resolved into one internal
  frozen spec object (`ScrewSpec`, `BearingSpec`, `GearSpec`, `NemaSpec`, `CapSpec`,
  `LinearBearingSpec`). This is the sanctioned exception to `AGENTS.md`'s no-type-mixing rule: it
  applies to *entry points only*, and the union MUST collapse to a single typed object on the first
  line of the constructor.

### 6.3 Ambient defaults (resolution)

Today `fn`/`fa`/`fs`/`res` default to `None` at every layer and are dropped by `given_arguments()`,
so smoothness falls through to the CAD runtime's own `$fa=12 / $fs=2`. That is the correct
*mechanism*; the missing piece is a Python-side ambient override.

* **D-8** Resolution MUST never be a required argument, anywhere, at any layer.
* **D-9** Resolution SHOULD be settable ambiently for a block, mirroring `use_backend`:
  a `contextvars`-backed `pybosl2.defaults` module exposing `use_defaults(fn=…, fa=…, fs=…, res=…)`
  and `set_defaults(...)`, consulted by `given_arguments()` when the caller passed nothing. This is
  the one remaining place where callers currently thread the same values through every call.
* **D-10** Ambient values MUST be resolved at construction time, never captured lazily, so a shape's
  smoothness is fixed by where it was built.

### 6.4 Units and frame

* **D-11** Lengths are millimetres, angles are degrees, the frame is right-handed Z-up. No API takes
  a unit argument; `constants.INCH` converts at the call site.
* **D-12** Shapes are centred on the origin by default (`anchor=CENTER`), oriented `+Z`
  (`orient=TOP`), unrotated (`spin=0`).

---

## 7. API conventions

* **A-6** Names track BOSL2 (`cuboid`, `prismoid`, `rect_tube`, `path_sweep`) so ported `.scad`
  reads side by side, except where the OpenSCAD name is a Python keyword (`except` → `except_edges`)
  or a builtin clash requiring the anchor-aware version (§3.2).
* **A-7** Verbs return new objects; nouns are properties. `screw.shape` is a property,
  `solid.up(5)` is a transform, `part.show()` is the only sanctioned side-effecting call.
* **A-8** Enums, not strings, for closed vocabularies. `enums.py` and `parts/enums.py` hold them;
  they are `StrEnum` so the legacy string spelling still compares equal.
* **A-9** Parts are classes with a resolved spec property and a `shape` property returning a
  `Solid`/`Flat`, plus `show()`. Stateless families expose classmethod factories
  (`BallBearings.ball_bearing("608")`). Geometry is built lazily on first `shape` access and cached.
* **A-10** Every public callable that produces 2-D or 3-D geometry MUST carry a
  `.. pythonscad-example::` docstring block that renders to STL — this is what the docs, the spec
  sheets, and `tests/validate_examples.py` consume.

---

## 8. Error contract

* **E-1** All library errors derive from `exceptions.Bosl2Error`.
* **E-2** `UnsupportedByBackendError` carries `feature`, `backend`, and a `hint` naming the
  alternative call or the backend that does support it.
* **E-3** `CrossBackendError` names both operands' backends and the conversion that resolves it.
* **E-4** Argument validation raises `ValueError` naming the offending parameter(s) and the
  constraint. Never `assert` on user-supplied input in a public entry point.
* **E-5** Silent coercion of a nonsensical argument is forbidden — a call that cannot mean what it
  says MUST fail loudly (per B-4).

---

## 9. Documentation contract

Docs are generated, so the source *is* the spec sheet.

* **DOC-1** Every module carries the header tags from `AGENTS.md`: `LibFile`, `FileSummary`,
  `DocCategory` (`Foundational`, `Paths, regions & surfaces`, `Math & geometry`, `Parts library`,
  `Extras`, `internal`), `FileGroup`.
* **DOC-2** Google-style docstrings, no types repeated in prose, `Raises:` for every explicitly
  raised exception.
* **DOC-3** `docs/_rstgen.py` builds the API reference from those headers; `docs/_specgen.py` builds
  the visual parts catalogue, rendering each featured part through the real PythonSCAD binary and
  measuring triangles / volume / bbox / watertightness. Rendered STL caches under
  `docs/_generated/` and `docs/_extra/specs/_stl/` are committed, because CI has no CAD binary.
* **DOC-4** A part added to `parts/` with a spec-sheet entry MUST ship its rendered STL cache in the
  same change.

---

## 10. Testing contract

* **T-1** `pytest` runs against a pip-installed `pythonscad` in a venv; L0 tests MUST pass without
  it.
* **T-2** Tests that need the full PythonSCAD **app** (`tests/test_stl_render*.py`) skip when no
  binary is found via `PYTHONSCAD_BIN` or `/Applications`. They MUST skip, never fail.
* **T-3** Every façade shape appears in the backend matrix test with its expected support status per
  backend — including the ones expected to raise `UnsupportedByBackendError`.
* **T-4** Every new public callable gets: a construction test, a defaults test that calls it with
  the **minimum** arguments (this is how P-1 is enforced mechanically), and a docstring-example
  validation via `tests/validate_examples.py`.
* **T-5** Before completing geometry/backend/path changes: `pytest`, `mypy --strict .`,
  `ruff check . --fix`, `ruff format .`.

---

## 11. Conformance status

Gaps between this specification and the code as it stands, in priority order. Each is a defect
against a numbered requirement, not a feature request.

| # | Requirement | Current state |
|---|---|---|
| 1 | **D-9** | No ambient resolution defaults. `fn`/`fa`/`fs`/`res` must be threaded through every call by hand; only `svg.py` has module-level `DEFAULT_FN`/`DEFAULT_FA`/`DEFAULT_FS`. |
| 2 | **A-4** | The top-level package has no `__init__.pyi`, so its 142 lazy exports are invisible to `mypy --strict` and IDE completion, unlike `shapes2d`/`shapes3d` which do ship stubs. |
| 3 | **A-4 / P-5** | `use_backend`, `set_default_backend`, and `current_backend` are not in `_LAZY_EXPORTS` — backend switching, a headline feature, is reachable only via `pybosl2.solid` or `pybosl2._backend`. |
| 4 | **D-3** | `shapes3d/cuboid.py::cuboid(size=[1, 1, 1])` uses a mutable list default, as do `prismoid`, `rect_tube`, `cuboid` (`shift=`) and
`shapes3d/extrusions.py`. |
| 5 | **P-2** | Façade defaults and backend defaults disagree: `solid.cuboid(size=None)` vs `shapes3d.cuboid(size=[1,1,1])`. The façade should carry the same documented default rather than deferring silently. |
| 6 | **C-1 / typing** | `flat.Flat`'s protocol methods are typed `Any -> Any`, so 2-D chains lose static checking that 3-D chains keep. |
| 7 | packaging | `pyproject.toml` declares `requires-python = ">=3.10"` and a 3.10 classifier, but the code uses `enum.StrEnum` (3.11+) in ~30 places and `AGENTS.md` states 3.11+. The floor is 3.11. |
| 8 | hygiene | `pybosl2/distributors.py.bak` is shipped inside the package directory. |

---

## 12. Change process

1. A change that alters a public signature MUST state which requirement it serves in the commit
   body (`feat(solid): ambient resolution defaults — D-9`).
2. Adding a required parameter to an existing public callable is a breaking change and needs a
   default or a deprecation path.
3. Adding a façade shape follows B-7.
4. This document is updated in the same commit as any change to §3 (layering), §5 (backend
   contract), or §6 (defaults).
