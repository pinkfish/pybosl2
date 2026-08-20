# pybosl2 — System Specification

**Status:** normative for new and modified code · **Version:** tracks `pybosl2/version.py`
**Companion:** [PLAN.md](PLAN.md) — the Python-level implementation plan.

This document is the **high-level** specification: what pybosl2 is, what every subsystem does, and
the contracts they honour. It deliberately says nothing about Python syntax, typing mechanics,
docstring layout, or tooling — those live in [PLAN.md](PLAN.md), which says *how* these contracts
are implemented in Python. Where the two overlap, this document wins on design and the plan wins
on mechanics.

Requirement keywords: **MUST**, **MUST NOT**, **SHOULD**, **MAY** (RFC 2119 sense). Requirements
are numbered (`P-1`, `S-12`, `R-1`, …) so reviews and commit messages can cite them.

---

## 1. What the system is

pybosl2 is a **pure-Python 3-D modelling toolkit**: a Python-native port of the
[BOSL2](https://github.com/BelfrySCAD/BOSL2) OpenSCAD library, built to drive
[PythonSCAD](https://pythonscad.org). It provides:

* **Geometry data types** that work in plain CPython with no CAD kernel — points, vectors, paths,
  regions, beziers, NURBS, quaternions, meshes, bounds, colours, textures.
* **Shape constructors** — 2-D outlines and 3-D solids — realized through one of two
  interchangeable backends: exact CSG (PythonSCAD native) or F-Rep signed-distance fields
  (libfive).
* **Modelling operations** — sweeps and skins, roundings and chamfers, masks and profiles,
  partitions, distribution and copying, strokes, textures, colour and display modifiers.
* **A parts library** — gears, screws, bearings, hinges, joiners, truss, hoses, stepper motors,
  bottle caps, threading, walls, wiring — driven by trade-size names rather than measurements.
* **Import and interchange** — SVG drawings, mesh import, VNF meshes, polyhedra.
* **A generated reference** — API documentation and a visual parts catalogue with metrics measured
  from real rendered STL.

Non-goals: pybosl2 does **not** depend on the BOSL2 OpenSCAD runtime (`osuse()`), does not ship a
mesh kernel of its own, and does not aim for byte-identical output with the original `.scad`.

---

## 2. Relationship to BOSL2: feature parity, not API parity

* **B2-1 Feature compatible.** Anything BOSL2 can build, pybosl2 aims to build — the same shapes,
  masks, roundings, sweeps, parts catalogue, and attachment model. Coverage of BOSL2's
  capabilities is the measure of completeness.
* **B2-2 Not API compatible.** pybosl2 MUST NOT copy OpenSCAD's calling conventions where Python
  has a better answer. A ported `.scad` module specifies *behaviour*, not signature:
  * objects and methods replace module-with-children,
  * chained methods replace transform wrappers,
  * enums replace magic strings and numbers,
  * exceptions replace `assert`/`echo` diagnostics,
  * ambient context (`use_backend`, `use_defaults`) replaces `$`-special variables,
  * keyword arguments with real defaults replace long positional lists.
* **B2-3 Names are kept where they help.** BOSL2's *names* (`cuboid`, `prismoid`, `path_sweep`,
  `rounding=`, `chamfer=`) are retained so the `.scad` source and the Python read side by side —
  except where Python forbids the name (`except` → `except_edges`) or a clearer spelling exists.
* **B2-4 Departures are documented.** Where behaviour deliberately differs, the docstring says so.

---

## 3. Driving principles

> **A caller who knows what they want to build, but nothing about the library, MUST be able to
> build it. Every parameter a caller is forced to supply is a defect budgeted against the design.**

* **P-1 — One required idea per call.** A constructor SHOULD be usable with one required
  argument — the thing being made — and MUST NOT require more than two (D-2). Everything else has
  a default.
* **P-2 — Defaults are the common case, not the neutral case:** `anchor=CENTER`, `orient=TOP`,
  `trimcorners=True`, `head=SOCKET`, `thread=COARSE`.
* **P-3 — Derive, do not demand.** Any value computable from the others MUST be optional and
  computed: thread pitch from the screw spec, gear module from circular pitch, a tube's bore from
  its wall.
* **P-4 — Name the thing, not its measurements:** `Screw("M6", length=20)`,
  `BallBearings.ball_bearing("608")`, `NemaMotor(size=17)`.
* **P-5 — Progressive disclosure.** Positional arguments are for the one or two things everyone
  supplies; everything else is keyword-only.
* **P-6 — Every default is overridable.** No behaviour is reachable only through a default.
* **P-7 — Errors teach.** A rejected call MUST say what was wrong *and* what to do instead (§9).
* **P-8 — Objects, not argument bags.** The library is object-oriented by preference: parts,
  paths, regions, meshes, colours and quaternions are **classes** that own their operations and
  expose derived values as properties. A family of free functions sharing a prefix and a pile of
  parameters MUST instead be a class. The *design* is Python's, not a transliteration of `.scad`.

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

| Layer | Modules | Contract |
|---|---|---|
| **L0 Pure geometry** | `math`, `vectors`, `points`, `geometry`, `paths`, `path2d`, `path3d`, `regions`, `beziers`, `nurbs`, `quaternions`, `vnf`, `rounding`, `skin`, `texture`, `bounds`, `constants`, `color`, `defaults`, `transforms`, `svg`, `turtle` | Works in plain CPython with no CAD runtime. MUST NOT import a native module at load time. |
| **L1 Backend contract** | `_backend`, `exceptions`, `caps`, `enums`, `_edges_lang` | Selection machinery and the shape protocols (`Shape`, `Flat`, `Solid`) only. MUST stay FFI-free. |
| **L2 Backend implementations** | `shapes2d/`, `shapes3d/`, `masking`, `partitions`, `surfaces3d`, `isosurface`, `miscellaneous`, `_shape`, `_csg`, `_native`, `_stroke2d`, `_stroke3d` (CSG); `sdf/` (F-Rep) | Reach their native runtime lazily. Each backend registers itself under a name. |
| **L3 Neutral façade** | `solid.py`, `flat.py` | Backend-agnostic constructors returning `Solid` / `Flat`. The recommended entry point. |
| **L4 Parts library** | `parts/` | Built strictly on L0–L3. MUST NOT reach a native runtime directly. |
| **L5 Presentation** | `docs/` | Generated from module headers and docstrings. |

* **A-1** A lower layer MUST NOT import a higher one.
* **A-2** L0 MUST remain usable and tested with no CAD runtime installed.
* **A-3** New geometry algorithms belong in L0, with native call sites isolated in L2.
* **A-4** `import pybosl2` MUST stay cheap: top-level names resolve lazily, and every lazily
  exported name MUST still be statically declared so editors and type checkers see the full API.
* **A-5** `square`/`circle`/`cube`/`text` intentionally shadow the OpenSCAD builtins with the
  anchor-aware versions, so the package MUST NOT be wildcard re-exported.
* **A-6** Everything exported from the top level MUST honour the active backend. A constructor that
  only one backend can build belongs on that backend's module, not on `pybosl2`, so that
  `from pybosl2 import …` never silently produces a shape on the backend the caller did not
  select. Mixed neutral and backend-specific names at the top level is the defect this rule
  exists to prevent.
* **A-7** A name in a module's `__all__` MUST resolve. An `__all__` entry with no matching
  attribute breaks `import *` and every tool that walks the export list.

---

## 5. Core object model

### 5.1 Shapes

A 2-D outline and a 3-D solid are the same *kind of thing* seen in two dimensions: both are
built, combined, moved and measured identically. They are therefore specified as **one contract
with two dimensional specialisations**, not as two parallel contracts that happen to look alike.

```
                    Shape                     the universal contract
              backend tag · | & -             (§5.1, C-15)
        translate/rotate/scale/mirror
              bounds() · show()
                 ╱          ╲
             Flat            Solid            the dimensional specialisations
      linear_extrude         projection  →  Flat
      rotate_extrude         attachment, half-cuts,
      offset  →  Solid       masks (CSG backend)
```

* **C-15 One contract, two specialisations.** `Shape` declares everything true of every shape on
  every backend: the `backend` tag, the boolean operators, the transforms, `bounds()`, and
  `show()` (§6.16). `Flat`
  and `Solid` extend it and add **only** what is genuinely dimensional. A member that both would
  declare identically MUST live on `Shape` instead — that duplication is how `Flat` came to be
  missing `bounds()` (S-2) and to be typed `Any` long after `Solid` was not.
* **C-16 Operations preserve the kind.** Every operation on a shape returns *the same kind of
  shape*, and an operand of a boolean MUST be the same kind: `flat | flat` and `solid | solid` are
  the only spellings, and `flat | solid` is a static error, not a runtime surprise. This is C-4
  enforced by the contract rather than by convention.
* **C-17 Crossing dimensions is explicit and named.** `Flat` → `Solid` happens only through an
  extrusion or sweep; `Solid` → `Flat` only through `projection`. Each direction is a method a
  reader can see at the call site; neither happens implicitly.
* **C-18 One declaration site, one name each.** All three protocols are declared together in the
  backend-contract layer (L1), so a change to the shared surface cannot land on one dimension and
  miss the other. `Shape`, `Flat` and `Solid` are the only names for them — no aliases: a second
  spelling of a contract is a second thing to keep in step, and `Shape2D` was exactly that.
* **C-19 Colour and distribution belong to the shared contract.** Both are operations on "any
  shape", not on solids specifically, so they SHOULD be members of `Shape` (S-37, S-31). They are
  not yet universal — the SDF backend's shapes carry no colour, and its 2-D shapes no distribution
  — which is a parity gap (§12.2), not a reason to split the contract.
* **C-1** Every shape carries a `backend` tag naming the backend that **produced** it. It is a
  property of the object, never a reading of the ambient backend at construction time — a CSG
  shape built inside a `use_backend("sdf")` block is still a CSG shape, and must say so. Booleans
  and transforms return a shape on the same backend; mixing raises `CrossBackendError` naming the
  conversion that fixes it. A tag that reports the ambient backend defeats that guard entirely and
  turns a clear error into an internal one.
* **C-2** Operators are the primary spelling: `|` union, `&` intersection, `-` difference.
* **C-3** Shapes are immutable by convention: every operation returns a new shape, so calls chain.
  `attach()` and `tag()` copy rather than mutate; the `attachments` / `tag_name` setters exist for
  those copies to use and are not part of the public contract.
* **C-4** 2-D and 3-D never mix implicitly; a flat shape reaches 3-D only through an explicit
  extrude or sweep, and the contract itself enforces it (C-16, C-17).
* **C-5** Shared behaviour (transforms, directional moves, CSG, colour, tags, distribution) lives
  once in the common base, not duplicated per dimension.
* **C-6** Forwarding to a native object is limited to an explicit allowlist, and every forwarded
  name MUST exist on the wrapped object and be statically declared.

### 5.2 Geometry objects

* **C-7** `Path` is abstract; `Path2D`/`Path3D` are selected by point dimension. Any API taking a
  polyline MUST accept a `Path`.
* **C-8** `Region` is outlines-with-holes; `VNF` is the vertex/face mesh interchange type. Anything
  that can produce a mesh SHOULD be able to produce a `VNF`, so it can be inspected and measured
  with no CAD runtime present.
* **C-9** Geometry objects own their operations as methods and return new objects (C-3).

### 5.3 The anchor language

* **C-10** One enum (`Anchor`) covers faces, edges, corners, and axis presets, each member carrying
  its own vector. Any "which face/edge/corner" parameter MUST accept it; new APIs MUST NOT invent a
  parallel string or integer vocabulary.
* **C-11** The `constants.py` names (`TOP`, `LEFT`, `CENTER`, …) are aliases kept for BOSL2
  familiarity; `Anchor.TOP` is preferred in new code and examples.

### 5.4 Attachment

* **C-12** A solid can carry attached children, positioned by anchor (`attach`, `position`,
  `align`, `reorient`, `orient`), tagged for boolean resolution (`AttachTag.KEEP` / `REMOVE` /
  `INTERSECT`), and resolved with `diff()` / `intersect()` at realize time.
* **C-13** Attachment is a CSG-backend feature; the SDF backend refuses it explicitly (§7.1).

### 5.5 Parts

* **C-14** Every part is a class (P-8) that resolves its inputs into a frozen **spec object**,
  exposes derived dimensions as read-only properties, builds geometry lazily under a `shape`
  **property** (`Screw("M6", length=20).shape`, not `.shape()`), and offers `show()`. Callers can
  therefore *measure* a part without building it.
* **C-14a** Note the deliberate difference in what `.shape` means either side of the FFI boundary:
  on a part it is the finished `Solid`/`Flat`; on a backend wrapper (`CsgSolid.shape`) it is the
  raw native handle being wrapped. Docstrings MUST say which one they mean.

---

## 6. Subsystems

Every subsystem below is part of the specified system; each MUST honour the principles in §3, the
resolution rules in §8, and the error contract in §9.

### 6.1 Maths, points and vectors

`math`, `vectors`, `points`, `geometry`, `bounds`

* **S-1** Scalar and vector helpers (`slerp`, `modang`, `quant`, `constrain`, `mean`, `EPSILON`)
  mirror BOSL2's maths, implemented on Python/NumPy primitives rather than re-derived.
* **S-2** `Point`/`Vector` are the point types; `Bounds2D`/`Bounds3D` are the axis-aligned box
  types. Every shape and mesh MUST report its bounds without rendering — this is part of both the
  `Solid` and the `Flat` contract, not just the 3-D one.
* **S-3** Line/plane/polygon predicates and intersections (`geometry`) operate on `Point`s and
  `Path`s, and honour the `SEGMENT`/`RAY`/`LINE` specifiers.

### 6.2 Transforms and rotations

`transforms`, `quaternions`

* **S-4** Affine transforms are 4×4 matrices; the library provides construction
  (`axis_angle_matrix`, `rot_from_to`, `rot_about_axis`), inversion, decoding, and application
  (`apply`, `reorient`).
* **S-5** `Quaternion` is a class with the full rotation algebra (multiply, slerp, to-matrix,
  to-axis, rotate-point), and is the preferred spelling for interpolated rotation.
* **S-6** Shapes expose the common transforms as chainable methods — `translate`, `rotate`,
  `scale`, `mirror`, `multmatrix`, and the directional moves `up`/`down`/`left`/`right`/
  `forward`/`back`.

### 6.3 Paths and curves

`paths`, `path2d`, `path3d`, `beziers`, `nurbs`, `rounding`, `turtle`

* **S-7** A `Path` is an ordered point list with an open/closed flag, and owns its measurement
  (length, perimeter, tangents, normals, curvature, torsion), its sampling (`subdivide_path`,
  `resample_path`, `select`, `cut`, `closest_point`), and its cleanup (`deduplicate`,
  `merge_collinear`).
* **S-8** Corner treatment (`round_corners`, `smooth_path`) MUST support BOSL2's rounding methods
  (circle / smooth / chamfer) and size measures (radius / cut / joint / width) as enums.
* **S-9** Bezier curves and patches (`Bezier`, `BezierPatch`) and NURBS curves and patches
  (`NurbsCurve`, `NurbsPatch`) are classes that evaluate, subdivide, and convert to `Path`s or
  `VNF`s, so they interoperate with everything else.
* **S-10** Turtle graphics (`turtle2d`, `turtle3d`) build paths from a command list, and their
  output is an ordinary `Path`.
* **S-11** A path MUST be able to become geometry: polygon/region fill, extrusion, sweep, or
  stroke (§6.7).

### 6.4 Regions

`regions`

* **S-12** A `Region` is a set of outlines with holes, supporting boolean union/difference/
  intersection, offset, and decomposition back into `Path2D`s.
* **S-13** Region booleans MUST be exact and independent of any CAD runtime.
* **S-14** A `Region` MUST be able to render as a 2-D shape or extrude to a solid, and to carry
  colour through that conversion (§6.12).

### 6.5 Meshes and surfaces

`vnf`, `surfaces3d`, `isosurface`

* **S-15** `VNF` (vertices + faces) is the mesh interchange type: constructed from grids
  (`vertex_array`, `tri_array`), from fields (`from_field`), from metaballs (`from_metaballs`),
  or from skinned profiles (`from_skin`); combined (`union`, `join`); cut (`halfspace`, `slice`);
  measured (`bounds`, `volume`); and realized (`polyhedron`).
* **S-16** Height fields and function plots (`heightfield`, `cylindrical_heightfield`, `plot3d`,
  `plot_revolution`) produce meshes from data or a callable, with an explicit sampling range.
* **S-17** Implicit surfaces — metaballs (`mb_sphere`, `mb_cuboid`, `mb_torus`, `mb_capsule`,
  `mb_disk`, `mb_octahedron`, `mb_connector`), `metaballs2d`, and `contour` — take an isovalue and
  a bounding box, and MUST expose their sampling resolution as an ordinary resolution argument
  (§8).
* **S-18** Fillets and textured tiles (`fillet`, `interior_fillet`, `textured_tile`) and the
  `ruler` annotation are part of the surface toolkit.

### 6.6 Sweeps, skins and extrusions

`skin`, `miscellaneous`, `shapes3d/extrusions`

* **S-19** The sweep family MUST cover BOSL2's: `path_sweep`, `path_sweep2d`, `linear_sweep`,
  `rotate_sweep`, `spiral_sweep`, `offset_sweep`, generic `sweep`, and `skin` across profiles.
* **S-20** Sweeps take their cross-section orientation method, sampling type, and skin
  vertex-matching method as enums (`SweepMethod`, `SamplingType`, `SkinMethod`), never as strings.
* **S-21** Offset-sweep end treatments are objects (`os_circle`, `os_smooth`, `os_teardrop`,
  `os_chamfer`, `os_flat`, `os_profile`), so a rim treatment is passed as one value rather than
  several loose parameters.
* **S-22** Other extrusions — `extrude_from_to`, `cylindrical_extrude`, `text3d`, `path_text`,
  `chain_hull`, `minkowski_difference` — are part of the specified surface.

### 6.7 Strokes and end caps

`_stroke2d`, `_stroke3d`, `caps`

* **S-23** Any path MUST be strokeable: `stroke(width, closed, endcaps, endcap1, endcap2, joints)`
  yields a filled outline in 2-D and a solid tube in 3-D, and `dashed_stroke` yields the dashed
  form. Both are also part of the backend contract, so a stroke works on either backend.
* **S-24** End caps and joints are described by one type — `CapType` for the named styles (butt,
  round, sphere, circle, arrow variants, diamond, dot, tail, custom) and `CapSpec` for a
  parameterised or custom-path cap. A cap MUST be expressible as a single value passed to
  `endcap1=`/`endcap2=`/`joints=`.
* **S-25** Stroke width, cap geometry and joint geometry MUST scale together, and a decorative cap
  MUST trim the body so the finished stroke keeps the requested end position.

### 6.8 Masks, profiles and edge treatments

`masking`, `_edges_lang`

* **S-26** 2-D mask profiles (`mask2d_roundover`, `mask2d_chamfer`, `mask2d_cove`, `mask2d_tear`,
  `mask2d_step`, `mask2d_groove`, …) and 3-D masks (`mask3d_roundover`, `mask3d_chamfer`,
  `mask3d_groove`) are first-class shapes, usable on their own or through a solid's
  `edge_mask`/`edge_profile`/`edge_profile_asym`/`corner_profile`/`face_profile`.
* **S-27** Which edges or corners a treatment applies to MUST be expressed in the anchor language
  (C-10), including the `edges=`/`except_edges=` selectors and the axis presets.
* **S-28** Rounding and chamfering MUST be available both as constructor parameters
  (`rounding=`, `chamfer=`, and their per-end variants) and as masks, and the two MUST agree
  geometrically.

### 6.9 Partitions and joinery

`partitions`

* **S-29** A solid MUST be splittable for printing: `partition`, `partition_mask`,
  `partition_cut_mask`, `partition_path`, and the half-cuts (`half_of`, `left_half`, `top_half`, …).
* **S-30** The cut profile is an enum (`PartitionCutType`: flat, sawtooth, sinewave, comb, finger,
  dovetail, hammerhead, jigsaw, square, triangle, halfsine, semicircle), with spread, gap and slop
  as defaulted parameters.

### 6.10 Distribution and copies

`distributors`

* **S-31** Copying is available in two forms that MUST stay in step: methods on a shape
  (`Distributable`: `line_copies`, `xcopies`/`ycopies`/`zcopies`, `grid_copies`, `rot_copies` and
  its axis variants, `arc_copies`, `sphere_copies`, `path_copies`, `mirror_copy`, flips) and the
  matrix-producing form (`DistributableMatrix`) for callers that want the transforms themselves.
* **S-32** `xdistribute`/`ydistribute`/`zdistribute` spread a set of shapes along an axis by their
  own sizes; `distribute_on_path` places copies along a path with correct orientation.
* **S-33** Distribution MUST work on paths and 2-D shapes as well as solids.

### 6.11 Textures

`texture`

* **S-34** Named textures (`texture("diamonds")`, ribs, bricks, pyramids, hills, rough, …) come
  from one registry, and each is either a height field or a VNF tile — the caller does not need to
  know which.
* **S-35** Anything that can be textured MUST accept the texture by name or object plus the same
  set of controls: tile size or repeat count, depth, inset, rotation, and per-texture options.

### 6.12 Colour and display modifiers

`color`

* **S-36** `Color` normalises every input form — CSS name, `#rrggbb`, RGB/RGBA sequences in 0–1 or
  0–255 — into one RGBA value, and exposes `rgb`, `rgba`, `alpha`, `hex`.
* **S-37** Colour is applied through chainable methods on anything drawable: `color`, `recolor`
  (recursive), `color_this` (this shape only), plus `hsl`/`hsv` construction. Opacity travels with
  the colour.
* **S-38** The preview modifiers `highlight` (`#`) and `ghost` (`%`) are methods on the same
  contract, so a debugging aid is a chained call rather than a different API.
* **S-39** `rainbow` / `rainbow_colors` colour a sequence of objects around the hue wheel.
* **S-40** Colour MUST be available on paths and regions as well as solids, and MUST survive the
  conversions between them where the target can carry it.

### 6.13 Import, export and interchange

`svg`, `vnf`, `shapes2d/ops`, `shapes3d/base`

* **S-41** SVG import produces ordinary geometry: outlines (`svg_outlines`), a `Region`
  (`region_from_svg`), grouped elements (`svg_element_groups`), and colour-carrying rings
  (`svg_rings_with_colors`) — with curve flattening controlled by the ordinary resolution
  arguments (§8).
* **S-42** Mesh import (`osimport`, 2-D and 3-D) returns a wrapped shape that joins the fluent
  API, not a raw native handle.
* **S-43** `polyhedron()` and `VNF.polyhedron()` are the mesh-to-solid boundary; `VNF` is the
  interchange type for anything that wants to inspect or measure geometry without a CAD runtime.

### 6.14 Parts library

`parts/`

* **S-44** Every part is a class per C-14, driven by a catalogue name or nominal size (P-4).
* **S-45** The library MUST cover the BOSL2 parts set: gears (spur, helical, herringbone, rack,
  ring, bevel, worm), screws/nuts/holes and threading (ISO, trapezoidal, acme, square, buttress),
  drive recesses (Phillips, hex, Torx, Robertson), ball and linear bearings, hinges and snap
  connectors, dovetails and snap pins, cube truss, modular hose, NEMA steppers, bottle caps,
  sliders and rails, tripod plates, Platonic solids, FDM walls, wiring bundles, hooks.
* **S-46** Parts MUST expose their catalogue as data (spec objects and tables), so a caller can
  query dimensions — and the docs can tabulate them — without building geometry.
* **S-46a Parts honour the active backend.** A part builds through the backend-neutral façade
  (L3), not by importing a backend's module directly, so `with use_backend("sdf"): Screw(…)`
  produces an SDF part. Where a part needs an operation only one backend can express, it raises
  `UnsupportedByBackendError` naming that backend (B-4) rather than quietly returning a shape from
  the other one. Parts are not exempt from PAR-1.

### 6.15 Documentation surface

* **S-47** Every subsystem above MUST appear in the generated API reference under a
  `DocCategory`, and every geometry-producing callable MUST carry a rendering example (§10).

### 6.16 Display and output

* **S-48 `show()` is how a shape leaves the library.** It hands the shape to the renderer: inside
  the PythonSCAD app it displays in the viewer, and in a script it marks the shape as what the run
  produces. It is the one call in the library with a side effect on the session, and the
  convention every docstring example ends with.
* **S-49 `show()` returns the shape.** It closes a chain without swallowing the value —
  `part = cuboid([20, 20, 10]).up(5).show()` both displays and binds. It MUST NOT return `None`.
* **S-50 `show()` is on the shared contract.** Every shape can be shown, 2-D or 3-D, on either
  backend (C-15). Showing an SDF solid meshes its field — that is not the implicit conversion B-5
  forbids, because rendering *is* meshing and nothing meshed is handed back. Showing a 2-D
  distance field refuses instead, naming the extrusion that would make it renderable: a field over
  the plane has no rendering of its own.
* **S-51 Builders delegate.** A part or any other builder exposes `show()` as a convenience that
  shows its `shape`, so a caller never has to reach inside to display something.
* **S-52 `show()` needs a renderer.** With the pip wheel alone it marks the object for output; the
  PythonSCAD **app** is what puts it on screen. Documentation examples therefore end in `.show()`
  and are rendered by the docs build, not by the test suite.

---

## 7. Backend model

* **B-1** The active backend is block-scoped and thread-safe, default `"csg"`; `use_backend("sdf")`
  switches it for a block, `set_default_backend()` globally.
* **B-2** A backend implements a small contract: hand back the constructor for a named shape, build
  it, do n-ary booleans, extrude paths, and stroke a path.
* **B-3** The **façade owns the default** for every argument both backends understand: it declares
  that default in its own signature and always forwards it, so an identical call produces identical
  geometry on either backend (PAR-5). A backend keeps its own defaults only for options exclusive
  to it. Arguments a backend has no notion of MUST NOT be forwarded to it — that filtering is by
  *what the backend declares*, not by *what the caller happened to pass*.
* **B-4** A backend MUST NOT silently approximate a feature it cannot express; it raises
  `UnsupportedByBackendError` with a hint naming the alternative or the backend that does support it.
* **B-5** Conversion is one-directional and honest: SDF → CSG is an exact mesh; CSG → SDF is lossy
  and not offered implicitly.
* **B-6** Backend-specific extras stay on the backend's own module.
* **B-7** Adding a façade shape requires: the façade constructor, a matching constructor in both
  backends (or an explicit refusal), and a row in the backend matrix tests.
* **B-8** What a caller gets when they leave an argument out MUST be inspectable, not silent:
  `effective_defaults(shape)` reports the active backend's real defaults.

### 7.1 Backend parity

The two backends are meant to be **interchangeable for as much of the library as is viable**. The
same source should build on either, and the set of things that only work on one MUST stay as small
as the mathematics allows.

* **PAR-1 Parity is the default expectation.** Anything that can be expressed as a signed-distance
  field MUST be available on the SDF backend, with the same name, the same argument names, and the
  same meaning as its CSG counterpart. Divergence needs a reason, not a shrug.
* **PAR-2 New shared features land on both.** A new façade shape, option, or operation MUST be
  implemented on both backends, or MUST be accompanied by an explicit refusal (B-4) and an entry in
  the gap list. "CSG only for now" is a tracked decision, never a silent omission.
* **PAR-3 The exclusive lists are minimal and justified.** `CSG_ONLY_FEATURES` and
  `SDF_ONLY_FEATURES` are the single source of truth for what is exclusive, and each entry MUST
  carry the reason it cannot cross over. Today that is the attachment/anchor system (CSG-only,
  because anchoring needs a shape's face and edge structure, which a distance field does not
  retain), `projection` and `fill` (CSG-only, because a 2-D shadow of a solid and a filled outline
  are not derivable in closed form from a field — both backends *do* build 2-D shapes otherwise),
  and the implicit-surface `round`/`chamfer` methods that survive transforms (SDF-only, because CSG
  expresses those as constructor parameters). An entry that becomes implementable MUST be removed
  from the list, not left as a permanent excuse; the list is re-reviewed whenever either backend
  gains a capability.
* **PAR-4 Equivalent options, not just equivalent shapes.** Parity is measured per *option*: if the
  CSG cuboid takes `rounding`, `chamfer`, `edges` and `except_edges`, the SDF cuboid MUST take the
  same ones with the same selector semantics. The **façade** spelling is identical on both
  backends; where a backend's own module spells a parameter differently, the difference MUST be
  declared in one central translation table rather than leaking into the façade. The only
  sanctioned backend-specific control is the resolution knob (`fn`/`fa`/`fs` vs `res`).
* **PAR-5 Same code, same result.** For any construction both backends support, the two MUST agree
  on placement, orientation, anchoring, bounds, and units — differing only in tessellation detail.
  This holds for calls that omit arguments as well as calls that pass them, which is why the façade
  owns the shared defaults (B-3). The backend matrix tests record what each backend supports, and
  `docs/design/sdf-csg-compatibility.md` is the working plan for closing the remainder.
* **PAR-6 Crossing is explicit.** Mixing operands from two backends raises `CrossBackendError`
  naming the conversion (B-5); the library MUST NOT convert silently to make a call succeed.

---

## 8. Defaults and resolution

### 8.1 Argument tiers

| Tier | Meaning | Rule |
|---|---|---|
| **T1 — Subject** | *what* is being made: size, spec name, path | At most one, positional, MAY still have a default |
| **T2 — Shaping** | changes the form: `rounding`, `chamfer`, `teeth`, `length` | Keyword; defaults to "off" or to the catalogue value |
| **T3 — Placement** | `anchor`, `spin`, `orient`, `center` | Keyword; defaults `CENTER` / `0` / `TOP` |
| **T4 — Resolution** | `fn`, `fa`, `fs`, `res` | Keyword; defaults to "inherit the ambient value" (§8.3) |
| **T5 — Escape hatch** | `convexity`, `eps`, `method`, `style` | Keyword; defaults to what 95 % of callers want |

* **D-1** T3–T5 MUST be keyword-only; T2 SHOULD be.
* **D-2** One required parameter is the target; a second needs a written justification in the
  docstring; three is never acceptable. The justified two-argument cases today are
  `Screw(spec, length)`, `prismoid(size1, size2)` and `regular_prism(sides, …)` — each names two
  independent dimensions that no default can invent.
* **D-3** Defaults MUST be immutable.
* **D-4** `None` means "not supplied, decide for me" — never "off". "Off" is `0`, `False`, or an
  explicit enum member.
* **D-5** Where a dimension has two conventional spellings (`radius`/`diameter`), the API MUST
  accept both and require neither. Giving both spellings of the **same** dimension is an error, not
  a silent preference: it raises `ValueError` naming both parameters and their values. Spellings at
  different levels of specificity are not a conflict — `radius1` legitimately overrides `radius` —
  and resolve most-specific-first: `(radius1, diameter1) > (radius2, diameter2) > (radius, diameter)`.
  This is a deliberate departure from BOSL2's `get_radius()`, which silently prefers the radius
  (B2-2, E-5).
* **D-6** A derivable parameter MUST default to "not given" and be derived.
* **D-7** A spec argument SHOULD accept the convenient forms — trade name, plain number, or an
  explicit mapping — and collapse them immediately into one frozen spec object.
* **D-8** A façade MUST NOT present as optional an argument its backend requires.

### 8.2 Curve resolution is universal

* **R-1** Every construction that produces a **circle, arc, rounding, chamfer arc, sphere,
  cylinder, sweep, texture tile, flattened SVG curve, sampled field, or any other tessellated
  curve** MUST accept the facet controls — `fn`/`fa`/`fs` on the CSG side, `res` on the SDF side —
  and MUST **pass them through to every sub-construction it builds**. A part that rounds its
  corners hands its `fn` to the rounding; a gear hands it to its tooth arcs; a mask hands it to
  its profile; a sweep hands it to its cross-section. Dropping them part-way down is a defect.
* **R-1a** The trigger is *generating points that approximate a curve*, not *taking a radius*. A
  callable that places or measures geometry from a radius — arc/rot/sphere copy distributors,
  `polar_to_xy`, circle-tangent geometry — is outside R-1, because nothing it returns is
  tessellated. When it is genuinely ambiguous, the deciding question is whether a caller could
  observe a facet count in the output.
* **R-2** These controls MUST never be required: omitted, they inherit (§8.3).
* **R-3** A backend that cannot honour a control MUST NOT be handed it.

### 8.3 Ambient defaults

* **R-4** Resolution SHOULD be settable once for a block rather than threaded through every call:
  `use_defaults(fn=64)` (block-scoped, nesting, thread-safe) and `set_defaults(...)` (process-wide).
* **R-5** An explicitly passed value always wins over the ambient one, and there MUST be a way to
  opt out of an ambient value rather than only override it: passing `fn=0` means "ignore any
  ambient `fn`, use `fa`/`fs`", matching OpenSCAD's own `$fn=0`. P-6 applies to ambient defaults
  as much as to signature defaults.
* **R-6** Ambient values are resolved at **construction** time, so a shape's smoothness is fixed by
  where it was built.
* **R-7** With nothing set anywhere, the renderer's own defaults apply (`$fa=12`, `$fs=2`).

### 8.4 Units and frame

* **D-9** Lengths are millimetres, angles are degrees, the frame is right-handed Z-up. No API takes
  a unit argument; `INCH` converts at the call site.
* **D-10** Shapes are centred on the origin, oriented `+Z`, unrotated by default.

---

## 9. Error contract

* **E-1** All library errors derive from one base error type.
* **E-2** A refusal names the feature, the backend, and the alternative.
* **E-3** Cross-backend mixing names both operands and the conversion that resolves it.
* **E-4** Argument validation raises `ValueError` naming the offending parameter(s) and the
  accepted spellings. A public entry point MUST NOT `assert` on user input.
* **E-5** A call that cannot mean what it says MUST fail loudly rather than build something else.

---

## 10. Documentation and catalogue

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

## 11. Quality gates

A change is done when all of these hold (mechanics in [PLAN.md §9–§11](PLAN.md)):

* **Q-1** The full test suite passes; pure-geometry tests pass with no CAD runtime present.
* **Q-2** Strict static type checking passes with zero errors.
* **Q-3** Lint and format are clean.
* **Q-4** Every new public callable has a minimum-argument test — the mechanical enforcement of
  P-1 — and a validated docstring example. For façade shape constructors this is enforced
  automatically by the contract tests; elsewhere it is a review obligation until the check is
  generalised (§12.2).
* **Q-5** The contract tests guarding these rules (mutable defaults, façade honesty, stub parity,
  facet coverage, backend matrix) still pass.

---

## 12. Conformance status

### 12.1 Closed

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
| **R-1** | `rect_tube` rounds corners but took no facet controls | `fn`/`fa`/`fs` accepted and passed to both prismoids |
| **D-5** | A conflicting `radius=`/`diameter=` pair was resolved silently by priority, so a typo built the wrong size | `pick_radius()` raises `ValueError` naming both parameters; all 34 inline resolutions across the package now route through it |
| **S-2 / C-1** | The `Flat` contract had no `bounds()`, so 2-D shapes could not be measured through the protocol | `bounds()` added to `Flat`; both 2-D implementations already provided it |
| **S-47 / DOC-1** | `path2d`, `path3d`, `points`, `bounds`, `caps` and `surfaces3d` were tagged `internal` while holding top-level public API, so paths, strokes/caps, bounds and heightfields had no reference page | Retagged into public categories; seven reference stubs generated |
| **PAR-3** | The CSG-only list claimed 2-D geometry as CSG-only, which stopped being true when the SDF backend gained `PyShape2D` | Rationale corrected in the spec and in the code comment: only `projection` and `fill` are CSG-only |
| **C-14 / S-51** | `shape` was a method on all 50 part classes while the spec specified a property, and `show()` returned `None` | `@property` with the existing lazy cache; 551 call sites rewritten; every `show()` returns the shape |
| **A-7** | `pybosl2.parts.__all__` advertised `Threading`, which does not exist | Removed; `tests/test_exports.py` walks every public module's `__all__` |
| **C-15 … C-18** | `Solid` and `Flat` were parallel contracts that had already drifted (`Flat` lacked `bounds()`, was typed `Any`) | One `Shape` protocol with `Self`-returning members; `Flat` and `Solid` extend it and declare only what is dimensional |
| **PAR-3** | `projection` was listed CSG-only *and* implemented on `SdfSolid` by meshing, so the refusal never fired and an SDF shape silently produced CSG geometry | Method removed, refusal names `.to_csg()`; every exclusive entry carries its reason; `tests/test_backend_parity.py` checks the lists against the classes; the stale design doc rewritten |
| **PAR-1 / C-19 / B-5** | The SDF shape's `__getattr__` meshed the field to answer any method it lacked, returning a raw native handle — 19 names, including every directional move and all of colour | Moves and colour implemented natively (colour rides the field as metadata); attachment state moved to the CSG-only list; the fallback is a documented mesh-operations allowlist and everything else refuses, naming `.to_csg()` |
| **R-5** | `fn=0` as the opt-out from an ambient `fn` was undocumented and untested | Documented in four places and covered by a test |
| **Q-4** | The minimum-argument check covered only `pybosl2.solid` | Parametrised over the four public shape modules plus a parts probe; it immediately found eight more E-4 violations and one missing `__all__` |
| **DOC-2 / D-P5** | 27 façade callables — the recommended entry point — had no `Args:` and no example, so `help(pybosl2.cuboid)` taught nothing | Descriptions and examples lifted from the backend constructors they delegate to; two tests keep them present and runnable |
| **S-46a** | 17 parts still built CSG geometry inside an `sdf` block through paths no constructor guard covers | `@csg_part` on every part's `shape` property: all 53 refuse uniformly, naming the way forward |
| **A-6** | The top level mixed neutral names with CSG-only ones, so an `sdf` block quietly built CSG geometry | The four with SDF twins dispatch through the façade; the rest refuse with a hint. A test asserts no top-level name returns a CSG shape inside an `sdf` block |
| **B-3 / PAR-5** | The façade defaulted shared arguments to `None` and forwarded only what the caller passed, so an identical call could resolve differently per backend | 64 shared defaults lifted into the façade; backends filter by what their constructor declares; `effective_defaults()` reports the façade first. A convergence test asserts both backends place and size a bare call alike |
| **A-4 / DOC-1** | `import pybosl2` pulled `webcolors` eagerly, so it failed inside the PythonSCAD app and broke 89 rendered examples; promoting path2d/path3d generated second pages for modules `paths.rst` already documented, giving 266 duplicate-object warnings | `Color` and `webcolors` are lazy (hex parsed locally); `_rstgen` skips modules a committed page documents; dataclass fields use `#:` comments. Docs build: 0 warnings |
| **C-1 / E-3** | `CsgSolid` read `current_backend()` into its own tag, so a CSG solid built inside a `use_backend("sdf")` block claimed to be SDF and the cross-backend guard never fired | The tag is a class constant; `backend_only()` makes a backend's own constructors refuse elsewhere (64 of them) and `builds_with()` scopes CSG internals that legitimately build CSG |
| **S-48 … S-50** | `show()` was reachable only through the native passthrough, so it was in no contract and — under Python 3.12's protocol rules — `isinstance(shape, Flat)` was false for every CSG shape | Declared on `Flat`/`Solid` and implemented as a real method on the CSG base, on `SdfSolid` (meshes, as rendering must) and on the 2-D SDF shape (refuses, naming the extrusion) |
| **C-18** | `Shape2D` was a second name for `Flat`, exported alongside it | Removed; `Flat` is the only spelling |
| packaging | `requires-python = ">=3.10"` with a 3.10 classifier, but `StrEnum` (3.11+) is used in ~30 places | Floor raised to 3.11 |
| hygiene | `distributors.py.bak` shipped inside the package; 854 MB of pytest scratch in the repo root | Removed; `pytest-of-*/` ignored and scratch retention capped |

### 12.2 Open

| # | Requirement | Current state |
|---|---|---|
| 1 | **E-4** | **238** `assert`s carry user-facing messages (52 converted so far) (`star(): must specify tips`, `base= must be a finite positive number`). Under `python -O` every one vanishes, so bad input silently yields wrong geometry. Public entry points are converted first; asserts stay only as genuine internal invariants. |
| 2 | **R-1** | **29 of 119** public curved-geometry callables still do not accept `fn`/`fa`/`fs` (50 at the start; 14 were reclassified as placement-only under R-1a and 6 fixed) — among them `Region.offset`/`round_corners`, `Path2D.minkowski_sum_circle`, `shapes2d.star`/`supershape`, the `RegularPolyhedron` factories, and `edge_profile`/`edge_profile_asym`. `tests/test_facets.py` pins the list so it can only shrink; R-1a is the rule for deciding which of the pinned entries are genuine debt rather than placement radii. |
| 3 | **P-8** | The parts library is fully class-based, but a few geometry areas remain function-families that would read better as classes: `masking.mask2d_*`/`mask3d_*`, `isosurface.mb_*`, and the `turtle2d`/`turtle3d` pair. |
| 4 | **B2-1** | BOSL2 feature coverage is not tracked anywhere; there is no gap list saying which `.scad` modules remain unported. |
| 5 | **PAR-5** | The SDF `pie_slice` stores the full disc's bounding box rather than the wedge's, so `bounds()` over-reports on a shape whose selling point is exact bounds. `tests/test_backend_parity.py::BOUNDS_NOT_YET_EXACT` pins it. |
| 6 | **S-46a / PAR-1** | Parts refuse on the SDF backend rather than building: none of the 53 has an SDF form. Closing this means expressing the ones that can be (simple prisms, bearings, hoses) through the façade, and keeping the refusal only where a part genuinely needs CSG-only operations. |



## 13. Change process
1. A change altering a public signature MUST cite the requirement it serves in the commit body
   (`feat(solid): ambient resolution defaults — R-4`).
2. Adding a required parameter to an existing public callable is a breaking change and needs a
   default or a deprecation path.
3. Adding a façade shape follows B-7 and the parity rules in §7.1.
4. This document is updated in the same commit as any change to §4 (layering), §6 (subsystems),
   §7 (backends), or §8 (defaults). Language-level rules change in [PLAN.md](PLAN.md) instead.
5. **Requirement IDs are permanent.** Numbers are never reused or renumbered: a new requirement
   appends to its series, and a withdrawn one is struck through with the reason. Section numbers
   may move; IDs are what commits, tests and reviews cite.
