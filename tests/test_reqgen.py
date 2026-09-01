# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""SPEC.md and PLAN.md are generated, and the committed copies are current (SPEC DOC-1, DOC-1a).

The requirements live in `spec/requirements.toml`; the prose around them lives in the frames
`spec/spec.md.in` and `spec/plan.md.in`, with a `{{requirements: <section>}}` placeholder wherever
bullets go. `docs/_reqgen.py` puts the two together.

The point of generating them is that a requirement now has exactly one home. Before T27 a rule
existed twice -- once as prose and once as registry data -- which is the arrangement the registry
was built to end, not to create. These tests are what make the single home real: edit the prose and
the build fails, telling you to edit the registry instead.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "docs"))

import _reqgen  # noqa: E402


@pytest.mark.parametrize("document", sorted(_reqgen.DOCUMENTS))
def test_the_committed_document_matches_the_generator(document: str) -> None:
    """A hand-edit to a generated document is lost on the next build, so it fails here instead."""
    rendered = _reqgen.render_document(document)
    committed = (ROOT / document).read_text()
    if committed != rendered:
        pytest.fail(
            f"{document} is out of date with spec/requirements.toml and its frame.\n"
            f"If you edited {document} by hand, move the change into the registry (a requirement) "
            f"or into spec/{document.lower().replace('.md', '')}.md.in (prose), then run:\n"
            f"    python docs/_reqgen.py"
        )


@pytest.mark.parametrize("document", sorted(_reqgen.DOCUMENTS))
def test_the_generated_document_says_it_is_generated(document: str) -> None:
    """PLAN D-P7: a generated page carries a line saying so, or someone will edit it."""
    head = (ROOT / document).read_text()[:2000]
    assert "docs/_reqgen.py" in head, f"{document} does not say it is generated, near the top"


@pytest.mark.parametrize("document", sorted(_reqgen.DOCUMENTS))
def test_every_requirement_reaches_its_document(document: str) -> None:
    """A registry section with no placeholder would silently drop its requirements.

    `render_document` raises rather than dropping them; this states it as a test so the guarantee
    is visible, and covers the reverse -- every id in the registry appears in the rendered text.
    """
    _, layer = _reqgen.DOCUMENTS[document]
    rendered = _reqgen.render_document(document)
    for entry in _reqgen.requirements():
        if entry["layer"] != layer:
            continue
        bare = entry["aliases"][0]
        assert re.search(rf"^\* \*\*~?~?{re.escape(bare)}[ ~*]", rendered, re.M), (
            f"{entry['id']} is in the registry but does not appear in {document}"
        )


def test_the_history_moved_out_and_stayed_whole() -> None:
    """§12.1 became CONFORMANCE.md: 40 % of the spec, none of it contract."""
    conformance = ROOT / "CONFORMANCE.md"
    assert conformance.exists(), "CONFORMANCE.md is missing"
    assert "## Closed" in conformance.read_text()
    spec = (ROOT / "SPEC.md").read_text()
    assert "### 12.1 Closed" not in spec, "the history is back in the spec"
    assert "CONFORMANCE.md" in spec, "the spec does not point at where the history went"


def test_the_task_archive_moved_out_and_stayed_whole() -> None:
    """TASKS.md is the queue; the finished work is the archive."""
    archive = ROOT / "docs" / "tasks-archive.md"
    assert archive.exists(), "docs/tasks-archive.md is missing"
    tasks = (ROOT / "TASKS.md").read_text()
    assert "## T0 — Make the backend tag tell the truth" not in tasks, "finished tasks are back in the queue"
    assert "tasks-archive.md" in tasks, "TASKS.md does not point at the archive"
