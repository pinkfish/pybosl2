# AGENTS.md

Guidance for agents and contributors working in this repository. The rules that used to live here
have been merged into two documents, so there is one place for each kind of decision:

| Document | Answers |
|---|---|
| **[SPEC.md](SPEC.md)** | *What the system is and does* — purpose, the BOSL2 relationship (feature parity, not API parity), the API-ergonomics principles, architecture and layering, the shape/geometry/backend contracts, the defaults and curve-resolution model, the error contract. High level; no Python mechanics. |
| **[PLAN.md](PLAN.md)** | *How that is written in Python* — the language baseline, typing rules, class-oriented design, resolution plumbing, docstring and file-header rules, module/import layout, error mechanics, style, tests, commands, and the review checklist. |

**Read SPEC.md first, then PLAN.md.** Both are normative. Requirements are numbered (`P-1`, `D-3`,
`R-1`, `T-2`, `O-2`, …); cite them in reviews and commit bodies.

## The short version

1. **Ease of use is the product.** At most one required argument per constructor; every other
   parameter has a sensible default; derive anything derivable. (SPEC §3)
2. **Feature compatible with BOSL2, not API compatible.** Keep BOSL2's names and behaviour; use
   Python's design — objects, methods, enums, exceptions, keyword arguments. (SPEC §2)
3. **Objects over argument bags.** Parts, paths, regions and meshes are classes that own their
   operations and expose derived dimensions as properties. (SPEC P-8, PLAN §3)
4. **Curve resolution is universal.** Anything drawing an arc, circle, rounding or chamfer takes
   `fn`/`fa`/`fs` (or `res`) and passes them to everything it builds. (SPEC §7.2, PLAN §4)
5. **Type everything, `Any` almost never.** `mypy --strict` clean; full element types on every
   collection; stubs for anything bound dynamically. (PLAN §2)
6. **Google docstrings on every public callable**, with `Args:`/`Returns:`/`Raises:` and a
   rendering example for anything that produces geometry. (PLAN §5)
7. **Bad input raises `ValueError` naming the fix** — never `assert`, never silent coercion.
   (SPEC §8, PLAN §7)

## Before you finish

```bash
export TMPDIR=/Volumes/ExternalDocs/tmp/   # keep test scratch off a full system disk
pytest                                     # full suite; STL-render tests skip without the app
mypy --strict pybosl2                      # zero errors
ruff check . --fix && ruff format .
```

The full checklist is [PLAN.md §11](PLAN.md#11-review-checklist); open debt is tracked in
[SPEC.md §11](SPEC.md#11-conformance-status).
