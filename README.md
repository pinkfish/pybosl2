# pybosl2

Python ports of the [BOSL2](https://github.com/BelfrySCAD/BOSL2) OpenSCAD library,
for use with [PythonSCAD](https://pythonscad.org). The package is imported as
`pybosl2`, with one module per wrapped/ported `.scad` file so each Python module can
be read side by side with its OpenSCAD source.

Most modules (constants, math, vectors, paths, shapes2d, …) are standalone pure-Python
ports that work in plain CPython. The modules that build native geometry
(`shapes3d`, `masking`, and the `.polygon()`/`.polyhedron()` boundaries) import the
`pythonscad`/`openscad` native modules at load time.

## Reference

* [Docs](https://pinkfish.github.io/pybosl2/)
* [Specs](https://pinkfish.github.io/pybosl2/specs/index.html) of the various parts
* [SPEC.md](SPEC.md) — what the system is and does, and the contracts it honours
* [PLAN.md](PLAN.md) — how that is implemented in Python (typing, classes, docs, tests)
* [TASKS.md](TASKS.md) — the ordered queue of conformance work

## Installation

```bash
pip install pybosl2
```

This pulls in `numpy`. To build native geometry you also need PythonSCAD:

```bash
pip install pythonscad
```

## Usage

Import by submodule (the `square`/`circle`/`cube`/`text` names intentionally shadow
the plain OpenSCAD builtins with BOSL2's anchor/spin/orient-aware versions, so the
package is deliberately not wildcard-re-exported):

```python
from pybosl2 import cuboid

part = cuboid([20, 20, 10]).up(5)
```

## Development & tests

The test-suite runs against a real, pip-installed `pythonscad` in a virtualenv:

```bash
python -m venv .venv          # create from outside the repo dir, or the local
                              # pybosl2/math.py etc. can shadow stdlib modules
source .venv/bin/activate
pip install -e '.[test]'      # installs pybosl2 + pytest + numpy + pythonscad
pytest
```

The `[test]` extra installs the `pythonscad` wheel, which provides the real
`pythonscad`/`openscad` native modules the geometry code imports.

A small number of tests exercise the full **PythonSCAD app** rather than the pip
wheel:

- STL-render tests (`tests/test_stl_render.py`) drive the real PythonSCAD binary
  in a subprocess to export and measure meshes. They skip unless a binary is found
  (set `PYTHONSCAD_BIN`, or install the app to `/Applications`).
- App-only native ops (e.g. `roof()`) skip when the pip wheel does not provide them.

## Documentation

The API docs are built with Sphinx (autodoc + napoleon) straight from the module
docstrings:

```bash
pip install -e '.[docs]'
make -C docs html      # renders into wiki/
```

On push to `main`, the `docs` GitHub Actions workflow builds and publishes them to
**GitHub Pages** (enable Pages with *Settings → Pages → Source: GitHub Actions*).
Examples in the docs embed interactive 3-D STL viewers; the renders are cached under
`docs/_generated/` and `docs/_extra/_stl/` — commit those caches so the images appear
on Pages, since CI has no PythonSCAD binary to render them.

## License

BSD 2-Clause License — see [LICENSE](LICENSE).
