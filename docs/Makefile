# Minimal sphinx-build Makefile for the pybosl2 (PythonSCAD port) API docs.
#
# Usage (from the repo root):
#   python3 -m pip install sphinx
#   make -C pybosl2/docs html
#
# The built HTML lands in pybosl2/wiki/ (a sibling of this docs/ source directory), which is meant
# to be CHECKED IN -- the browsable copy of the docs kept in the repo -- so rebuild and commit it
# together with any docstring/docs-source change. The doctree pickles (_build/), the rendered
# preview cache (_generated/) and the exported STL cache (_stl/) stay untracked.
#
# Set PYTHONSCAD_BIN to a real PythonSCAD binary to get rendered images and downloadable STL
# meshes in the pybosl2-example blocks; without it the build shows source only and never
# attempts a render (see docs/_ext/pybosl2_example.py). Unchanged examples reuse their cached
# image/STL, so only new or previously-failing ones are re-rendered.
#
# WARNINGS ARE ERRORS (-W). Sphinx exits 0 on warnings, which meant a docstring whose example
# no longer renders -- "pybosl2-example STL render FAILED" -- reported "build succeeded, N
# warnings" and `make html` returned success, so a broken example could be committed without
# anyone noticing. --keep-going still reports EVERY warning before exiting nonzero, so one
# build shows the whole list rather than dying on the first.
#
# Note this only bites where a PythonSCAD binary is present: without one the render is skipped
# (logged at info level, not warning), so a machine that cannot render cannot catch a broken
# example either. Treat a green build on such a machine as "the prose is fine", not "the
# examples work".
#
# To build past warnings anyway -- mid-refactor, when you already know examples are broken:
#   make html SPHINXOPTS=--keep-going

SPHINXOPTS    ?= -W --keep-going
SPHINXBUILD   ?= python3 -m sphinx
SOURCEDIR     = .
BUILDDIR      = _build
WIKIDIR       = ../wiki

.PHONY: help clean html specs check
help:
	@echo "make html   -- build the docs into $(WIKIDIR) (checked in); warnings are errors"
	@echo "make check  -- strict FULL rebuild into a scratch dir; use this in CI"
	@echo "make specs  -- (re)generate the visual spec sheets in _extra/specs/"
	@echo "make clean  -- remove $(WIKIDIR), the doctree cache, and the render caches"
	@echo ""
	@echo "make html SPHINXOPTS=--keep-going   -- build past warnings instead of failing"

clean:
	rm -rf "$(BUILDDIR)" "$(WIKIDIR)" _generated

specs:
	@python3 _specgen.py

html: specs
	@mkdir -p _generated
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(WIKIDIR)" -d "$(BUILDDIR)/doctrees" $(SPHINXOPTS) $(O)
	@cd .. && ruff check --fix . && ruff format .

# `make html` alone cannot promise "fails if anything is broken", because a warm build skips
# unchanged pages: their directives never re-run, so a broken example on a page Sphinx did not
# re-read raises nothing and the build passes. This target throws away the doctree cache and
# re-reads EVERY page, so the whole docs set is checked on every run. It writes to a scratch
# directory and leaves the checked-in $(WIKIDIR) alone, so it is safe to run at any time.
#
# Still bounded by one cache it does NOT clear: docs/_extra/_stl/ keys rendered meshes by the
# example's source text, so an example whose CODE is unchanged reuses its cached mesh and is
# not re-rendered, even if a library change since broke it. Delete that directory (or run
# `make clean`) to force every example to re-render from scratch.
check:
	@mkdir -p _generated
	@rm -rf "$(BUILDDIR)/check" "$(BUILDDIR)/check-doctrees"
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR)/check" -d "$(BUILDDIR)/check-doctrees" -W --keep-going $(O)
