# pybosl2 — Python Implementation Plan

**Companion to [SPEC.md](SPEC.md).** The spec says *what the system is and does*; this plan says
*how it is written in Python*. Where the spec states a contract, this plan states the language
mechanics that satisfy it. Both are normative for new and modified code.

Requirement keywords: **MUST**, **MUST NOT**, **SHOULD**, **MAY**. Requirements are numbered
(`L-3`, `T-7`, …) so reviews and commit messages can cite them.

---

## 1. Language baseline

* **L-1** Python **3.11+**. `enum.StrEnum` and `typing.Self` are used throughout;
  `requires-python` and the classifier list MUST agree with that floor.
* **L-2** Modern syntax only: `X | Y` unions (never `typing.Union`/`Optional`), built-in generics
  (`list[str]`, `dict[str, float]`), `from __future__ import annotations` at the top of every
  module so annotations stay cheap and forward references work.
* **L-3** Use the standard library rather than re-deriving it: `math`, `itertools`, `functools`,
  `dataclasses`, `contextlib`, `contextvars`, and NumPy for array maths. A hand-rolled `lerp`,
  angle-wrap, or matrix multiply that duplicates `math`/NumPy is a defect.
* **L-4** Third-party runtime dependencies are exactly: `numpy`, `typing-extensions`, `webcolors`,
  `svgelements`, `shapely`. Adding one is an architectural decision, not a convenience.

---

## 2. Typing

Static safety is enforced by `mypy --strict` over the whole package; it MUST pass with zero errors.

* **T-1 Total coverage.** Every function, method, parameter, and return value carries an explicit
  annotation — including `-> None`.
* **T-2 No implicit `Any`.** `Any` appears only where it is genuinely unavoidable: the PythonSCAD
  FFI boundary and `**kwargs` passthrough to it. Everywhere else it is a defect. When a value
  arrives as `Any` from the FFI, `cast()` it to a real type on the first line that touches it, and
  wrap native callables obtained via `native("…")` in a typed `Callable`/`Protocol` signature.
* **T-3 Full element types.** A bare `list`, `dict`, `tuple`, or `Sequence` is never acceptable —
  always `list[float]`, `dict[str, Anchor]`, `tuple[list[float], list[float]]`,
  `Sequence[Sequence[float]]`. This applies to local variables holding collections, to empty
  initialisations (`results: list[str] = []`), and to `.pyi` stubs.
* **T-4 Inputs widen, outputs narrow.** Accept `Sequence[float]`, return `list[float]`. Accept a
  `Path` object rather than `list[Sequence[float]]` or a raw NumPy array wherever a polyline is
  meant (SPEC C-7).
* **T-5 No union-widening in overrides.** An override MUST NOT broaden a parameter to
  `float | list[float]` to cover both callers; pick the collection form and convert at the entry
  point. The one sanctioned union is a *spec argument* at a public constructor (SPEC D-7), which
  MUST collapse to a single typed object on the first line.
* **T-6 Structure with `Protocol`.** Cross-backend contracts (`Solid`, `Flat`, `SolidBackend`) are
  `Protocol`s with fully typed members — never `Any -> Any` placeholders. Use `@runtime_checkable`
  only when an `isinstance` check actually exists.
* **T-7 Variance is explicit.** `TypeVar("T", covariant=True)` / `contravariant=True` where a
  generic is exposed publicly.
* **T-8 Stubs for dynamic surfaces.** Any module whose public names are bound dynamically MUST ship
  a `.pyi` that declares them statically — `pybosl2/__init__.pyi`, `shapes2d/__init__.pyi`,
  `shapes3d/__init__.pyi`, `solid.pyi`, `_shape.pyi`. A stub and its module MUST NOT drift; parity
  is enforced by `tests/test_init_stub.py`.
* **T-9 No dynamic globals.** Never `globals()[name] = …` or `setattr(module, …)` to register an
  API. The one permitted `__getattr__` is the top-level lazy re-export table, which is backed by
  its stub (T-8).
* **T-10 Immutable defaults.** Parameter defaults are `None`, numbers, strings, tuples, or enum
  members — never a list, dict, or set, in `.py` or `.pyi` (SPEC D-3). Guarded by
  `tests/test_defaults.py::test_no_mutable_defaults_anywhere_in_the_package`.

---

## 3. Objects over functions

The library is object-oriented by preference (SPEC P-8): a caller holds a *thing* and asks it for
what they need, rather than passing a bag of numbers through free functions.

* **O-1 Parts are classes.** Every entry in `pybosl2/parts/` is a class — `Screw`, `SpurGear`,
  `KnuckleHinge`, `RegularPolyhedron`, `NemaMotor` — not a family of functions. A stateless family
  of catalogue lookups MAY instead be a class holding classmethod factories
  (`BallBearings.ball_bearing("608")`).
* **O-2 The standard part shape.** A part class has:
  1. a `__init__` taking the catalogue name / defining dimension first and everything else
     defaulted (SPEC P-1),
  2. a resolved, frozen **spec object** — `ScrewSpec`, `GearSpec`, `BearingSpec`, `NemaSpec` — built
     on the first line of `__init__`,
  3. read-only `@property` accessors for every derived dimension (`diameter`, `pitch`,
     `pitch_radius`, `head_height`) so callers can measure without building geometry,
  4. a `shape` property returning the `Solid`/`Flat`, built lazily and cached,
  5. a `show()` for the interactive/preview case.
* **O-3 Geometry types are classes too.** `Path2D`, `Path3D`, `Region`, `VNF`, `Bezier`,
  `NurbsCurve`, `Color`, `Bounds2D/3D` own their operations as methods, so work reads as a fluent
  chain rather than nested calls.
* **O-4 Free functions are for shape constructors and pure maths.** `cuboid()`, `circle()`,
  `slerp()`, `frag_count()` stay functions; anything with state, derived values, or a catalogue
  behind it becomes a class.
* **O-5 Immutability.** Spec objects are frozen dataclasses. Shapes and paths return new objects
  from every operation (SPEC C-3); no public method mutates `self`.
* **O-6 Enums for closed vocabularies.** `StrEnum` in `pybosl2/enums.py` and
  `pybosl2/parts/enums.py`, so the legacy string spelling still compares equal. A new bare-string
  parameter with a fixed set of accepted values is a defect.
* **O-7 Composition at the FFI boundary.** `Bosl2Solid`/`Bosl2Shape2D` wrap the native handle by
  composition, never inheritance, and proxy operations through the explicit
  `_NATIVE_PASSTHROUGH` allowlist (SPEC C-6).

---

## 4. Resolution plumbing (`fn` / `fa` / `fs` / `res`)

SPEC R-1 requires every curved construction to accept the facet controls and pass them down. In
Python that means:

* **R-P1** The parameters are spelled `fn: int | None = None`, `fa: float | None = None`,
  `fs: float | None = None` (CSG) and `res: int | None = None` (SDF), keyword-only, defaulting to
  `None`. Never `$fn`, never a positional.
* **R-P2** A function that builds an arc, circle, rounding, chamfer arc, sphere, or cylinder MUST
  declare them, and MUST forward them to every sub-construction it calls — including path
  helpers (`round_corners`, `arc_points`), masks, and part sub-assemblies. Dropping them silently
  half-way down is the defect this rule exists to prevent.
* **R-P3** Resolve them exactly once, at the point of use, through
  `pybosl2.defaults.resolve_facets()` / `resolve_res()`, which fill in the ambient block values
  (`use_defaults(fn=64)`). The central resolvers are `_helpers.frag_count()`,
  `shapes3d/base._ocylinder`/`_osphere`, `shapes2d/circle.circle`, and each backend's
  `construct()`; new leaf constructors SHOULD route through those rather than re-implementing the
  `$fa`/`$fs` arithmetic.
* **R-P4** Never forward a facet argument to a callee that does not declare it — check the
  signature (as `SdfBackend.construct` does) rather than passing blindly.
* **R-P5** New public curved geometry MUST NOT be added to the known-gap list in
  `tests/test_facets.py`; the list only shrinks.

---

## 5. Documentation

* **D-P1 Google style, always.** One-line summary, blank line, then the description. `Args:`,
  `Returns:`, `Raises:` sections separated by blank lines. No reStructuredText `:param:` fields.
* **D-P2 Every public module, class, method, and function has a docstring.** No exceptions for
  "obvious" properties.
* **D-P3 No type redundancy.** Types live in the annotations; the prose describes meaning, units,
  and the default's effect.
* **D-P4 `Raises:` is complete.** Every exception raised in the body appears there, including the
  `ValueError`s from argument validation.
* **D-P5 Examples that build geometry.** Every function producing 2-D or 3-D output carries a
  `.. pythonscad-example::` block that renders to STL. A 2-D example MUST extrude
  (`.linear_extrude(...)`) before `.show()`, since STL has no 2-D form.
* **D-P6 File header tags.** Immediately after the licence header, every module carries:

  ```
  # LibFile: pybosl2/<name>.py          # required for public modules
  # FileSummary: <one line, < 120 chars>  # required for public modules
  # DocCategory: <section>              # required
  # FileGroup: BOSL2
  ```

  `DocCategory` is one of `Foundational`, `Paths, regions & surfaces`, `Math & geometry`,
  `Parts library`, `Extras`, or `internal` (excluded from the public docs).
* **D-P7** Docs are generated from these headers and docstrings by `docs/_rstgen.py`, and the
  visual catalogue by `docs/_specgen.py`. Never hand-maintain a list of APIs in `.rst`.

---

## 6. Modules, imports, and laziness

* **M-1** One module per ported `.scad` file, named after it, so the Python and OpenSCAD sources
  read side by side. Support modules are `_`-prefixed and marked `DocCategory: internal`.
* **M-2** Every public module declares `__all__`.
* **M-3** No native runtime at import time. PythonSCAD primitives are reached through
  `pybosl2._native.native("cube")`, which defers `import pythonscad` to the first call; libfive is
  a lazy handle in `pybosl2/sdf/_libfive.py`. `import pybosl2` MUST work with neither installed.
* **M-4** Type-only imports go under `if TYPE_CHECKING:`.
* **M-5** Import direction follows the spec's layering (SPEC A-1); a cycle is resolved by moving
  the shared piece down a layer, not by a function-local import — those are reserved for genuine
  cycles and are commented when used.

---

## 7. Errors

* **E-P1** Raise `ValueError` for bad arguments, naming the parameter(s) and the accepted
  spellings: *"tube(): needs two of the three sizes — an inner radius/diameter, an outer
  radius/diameter, and a wall thickness."*
* **E-P2** `assert` is for internal invariants only. An `assert` that a user's argument combination
  is valid is a defect: asserts vanish under `python -O`, and `AssertionError` tells the caller
  nothing about what to pass.
* **E-P3** Library errors derive from `pybosl2.exceptions.Bosl2Error`; backend refusals use
  `UnsupportedByBackendError(feature, backend, hint=…)` and cross-backend mixing uses
  `CrossBackendError`. Both MUST carry an actionable hint.
* **E-P4** Never swallow an exception to return a degenerate shape.

---

## 8. Style

* **S-1** `ruff format` is the formatter; line length 120; double quotes.
* **S-2** Functions stay short and cohesive — under 50 lines. A longer one is split, not commented
  into sections.
* **S-3** No `TODO` comments and no stubbed bodies in committed code. Unfinished work lives in
  SPEC §11 (conformance), not in the source.
* **S-4** Comments explain *why*, and are kept truthful when the code changes; a comment that
  describes behaviour the code no longer has is a defect.
* **S-5** BOSL2 parameter names are kept unless Python forbids them (`except` → `except_edges`) or
  a better Python spelling exists (SPEC B-8) — but the *call shape* is Python's, not OpenSCAD's.

---

## 9. Tests

* **X-1** `pytest` is the runner; tests live in `tests/`, one module per source module.
* **X-2** Pure-geometry (L0) tests MUST pass with no CAD runtime installed. Tests needing the
  PythonSCAD **app** (`tests/test_stl_render*.py`) skip when no binary is found via
  `PYTHONSCAD_BIN` or `/Applications` — they skip, never fail.
* **X-3** Every new public callable gets three tests: it builds, it builds **with the minimum
  arguments** (this is how SPEC P-1 is enforced mechanically), and its docstring example validates
  (`tests/validate_examples.py`).
* **X-4** Contract tests that guard the rules in this plan, and MUST keep passing:
  | Test | Guards |
  |---|---|
  | `tests/test_defaults.py::test_no_mutable_defaults_anywhere_in_the_package` | T-10 / SPEC D-3 |
  | `tests/test_defaults.py::test_argument_free_constructors_either_build_or_explain` | SPEC P-1, E-P2 |
  | `tests/test_defaults.py::test_facade_never_defaults_an_argument_its_backend_requires` | SPEC P-1 |
  | `tests/test_defaults.py::test_backends_agree_on_the_defaults_they_share` | SPEC P-2 |
  | `tests/test_init_stub.py` | T-8 |
  | `tests/test_facets.py` | R-P2 / R-P5 |
  | `tests/test_backend_matrix.py` | SPEC B-7 |
* **X-5** Changing geometry, backends, or paths means running the full suite — including
  `pytest tests/test_stl_render.py` when a PythonSCAD binary is available — before the work is
  called done.

---

## 10. Commands

```bash
python -m venv .venv                 # create from OUTSIDE the repo: pybosl2/math.py can shadow stdlib
source .venv/bin/activate
pip install -e '.[test]'             # pybosl2 + pytest + numpy + pythonscad

export TMPDIR=/Volumes/ExternalDocs/tmp/   # scratch on the big volume, not the system disk
pytest                               # full suite
pytest tests/test_stl_render.py      # real-binary render checks (skips without the app)
mypy --strict pybosl2                # zero errors required
ruff check . --fix && ruff format .  # lint + format
make -C docs html                    # docs into wiki/
```

**X-6 Scratch space.** The STL-render tests write meshes through `tmp_path` and `tempfile`, which
follow `TMPDIR`. Point `TMPDIR` at a volume with room — on the system disk a full run can exhaust
free space, and when `TMPDIR` is unwritable pytest falls back to the working directory and leaves a
`pytest-of-*` tree in the repo (ignored by `.gitignore`, but still hundreds of megabytes). Retention
is capped in `pyproject.toml` (`tmp_path_retention_policy = "failed"`), so passing tests clean up
after themselves.

Commits follow Conventional Commits (`.commitlintrc.yml`): `fix(docs): …`, `feat(solid): …`.
A change that serves a numbered requirement SHOULD cite it in the body
(`feat(solid): ambient resolution defaults — D-9`).

---

## 11. Review checklist

Before calling a change done:

1. Does the new API work with **one** argument? (SPEC P-1)
2. Are all optional parameters keyword-only, with immutable defaults? (T-10)
3. If it draws a curve, does it take `fn`/`fa`/`fs` *and pass them down*? (R-P2)
4. Is there a class where a family of functions was tempting? (O-1, O-4)
5. `mypy --strict` clean, with no new `Any`? (T-1, T-2)
6. Google docstring with `Args:`/`Returns:`/`Raises:` and a rendering example? (D-P1, D-P5)
7. Bad input → `ValueError` naming the fix, not `assert`? (E-P1, E-P2)
8. Minimum-argument test added? (X-3)
9. `ruff check` / `ruff format` clean, functions under 50 lines? (S-1, S-2)

---

## 12. Known debt

Tracked in [SPEC.md §11](SPEC.md#11-conformance-status). The active language-level item is the
facet audit: **50 of 119** public curved-geometry callables do not yet accept `fn`/`fa`/`fs`
(R-P2). Re-run the audit with:

```bash
pytest tests/test_facets.py -q      # fails only if the list grows
```
