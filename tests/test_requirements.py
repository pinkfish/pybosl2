# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The requirements registry keeps itself honest.

``spec/requirements.toml`` is the normative source for SPEC.md and PLAN.md. These tests are to
the registry what ``tests/test_facets.py`` is to the facet backlog: the rules this project writes
about measuring its claims, applied to the claims themselves.

Guarded here:

* ids are unique across both documents, which the bare spellings were not -- ``S-2`` meant
  "every shape reports its bounds" in SPEC.md and "functions stay under 50 lines" in PLAN.md,
  and five prefixes collided that way;
* every ``enforced_by`` target is a test that exists, so a rule cannot go on claiming a guard
  that was deleted or renamed;
* every requirement in the prose is in the registry and vice versa, until ``docs/_reqgen.py``
  (T27) replaces this with the stronger generated-file check ``_covgen.py`` already uses;
* every id cited in the package or the tests resolves;
* the untriaged backlog only shrinks -- it is empty since T38, so the rule now reads "a new
  requirement says what checks it before it lands";
* an `unenforced` or `reviewed` requirement says *why*, so the gap is legible rather than a status.
"""

from __future__ import annotations

import pathlib
import re
import tomllib
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "spec" / "requirements.toml"

#: A requirement id as the documents spell it. Kept in step with scripts/extract_requirements.py.
ID = r"[A-Z][A-Z0-9]*-P?\d+[a-z]?(?:\(i\))?"

#: A citation that names its document -- the spelling new code should use, and the only one this
#: test can check without guessing, since a bare `S-2` is ambiguous by construction.
CITATION = re.compile(rf"\b(SPEC|PLAN)[ -]({ID})\b")

VALID_STATUS = frozenset({"enforced", "reviewed", "unenforced", "untriaged", "withdrawn"})

#: How many requirements nobody has triaged yet. **Zero**, since T38. It stays as a ratchet: a new
#: requirement arrives `untriaged` and has to be decided before it can land, which is the point --
#: writing a rule and saying nothing about what checks it is how 250 of them accumulated.
UNTRIAGED_BUDGET = 0


def _registry() -> list[dict[str, Any]]:
    """Return every requirement in the registry."""
    return list(tomllib.loads(REGISTRY.read_text())["requirement"])


REQUIREMENTS = _registry()
BY_ID = {entry["id"]: entry for entry in REQUIREMENTS}
BY_ALIAS: dict[str, list[dict[str, Any]]] = {}
for _entry in REQUIREMENTS:
    for _alias in _entry["aliases"]:
        BY_ALIAS.setdefault(_alias, []).append(_entry)


def test_the_registry_is_not_empty() -> None:
    """A parse failure or a bad path must not read as a clean run."""
    assert len(REQUIREMENTS) > 200, f"only {len(REQUIREMENTS)} requirements read from {REGISTRY}"


def test_every_id_is_unique() -> None:
    """The whole point of the document prefix: one id, one requirement."""
    seen: dict[str, int] = {}
    for entry in REQUIREMENTS:
        seen[entry["id"]] = seen.get(entry["id"], 0) + 1
    duplicates = sorted(name for name, count in seen.items() if count > 1)
    assert not duplicates, f"ids used twice: {duplicates}"


def test_a_bare_id_says_which_document_it_belongs_to() -> None:
    """Where a bare id is ambiguous, both entries must be reachable through their prefixed form.

    This does not forbid the collision -- the ids are permanent (SPEC 13 rule 5) and both
    documents keep theirs. It records which bare spellings a reviewer must not use unqualified.
    """
    ambiguous = {alias: sorted(e["id"] for e in entries) for alias, entries in BY_ALIAS.items() if len(entries) > 1}
    for alias, ids in ambiguous.items():
        assert len(set(ids)) == len(ids), f"{alias} maps to duplicate ids {ids}"
        for identifier in ids:
            assert identifier in BY_ID, f"{alias} points at a missing entry {identifier}"


@pytest.mark.parametrize("entry", REQUIREMENTS, ids=lambda e: str(e["id"]))
def test_every_entry_is_well_formed(entry: dict[str, Any]) -> None:
    """Each requirement carries the fields the generator and the reviewer both need."""
    identifier = entry["id"]
    assert entry["status"] in VALID_STATUS, f"{identifier}: unknown status {entry['status']!r}"
    assert entry["layer"] in ("contract", "mechanics"), f"{identifier}: unknown layer {entry['layer']!r}"
    assert entry["statement"].strip(), f"{identifier}: empty statement"
    assert entry["section"].strip(), f"{identifier}: no section"


@pytest.mark.parametrize("entry", REQUIREMENTS, ids=lambda e: str(e["id"]))
def test_a_status_is_backed_by_what_it_claims(entry: dict[str, Any]) -> None:
    """`enforced` needs a test; `unenforced` and `withdrawn` need a reason."""
    identifier, status = entry["id"], entry["status"]
    if status == "enforced":
        assert entry["enforced_by"], f"{identifier} claims enforcement with no test named"
    else:
        assert not entry["enforced_by"], f"{identifier} names a test but is not marked enforced"
    if status in ("unenforced", "withdrawn"):
        assert entry.get("note", "").strip(), f"{identifier} is {status} and says nothing about why"


@pytest.mark.parametrize("entry", [e for e in REQUIREMENTS if e["enforced_by"]], ids=lambda e: str(e["id"]))
def test_every_enforced_by_target_exists(entry: dict[str, Any]) -> None:
    """A rule cannot claim a guard that was deleted or renamed."""
    for node in entry["enforced_by"]:
        path, *qualifiers = node.split("::")
        target = ROOT / path
        assert target.exists(), f"{entry['id']}: {path} does not exist"
        source = target.read_text()
        # A node id may name a class as well as a function (`file.py::Class::test_x`), so check
        # each part against the definition it should name.
        for qualifier in qualifiers:
            keyword = "class" if qualifier[:1].isupper() else "def"
            assert re.search(rf"^\s*{keyword} {re.escape(qualifier)}\b", source, re.M), (
                f"{entry['id']}: {path} has no {keyword} named {qualifier}"
            )


def _ids_in(document: str) -> set[str]:
    """Return every requirement id the prose of *document* declares."""
    bullet = re.compile(rf"^\* \*\*(?:~~)?({ID})")
    return {m.group(1) for line in (ROOT / document).read_text().splitlines() if (m := bullet.match(line))}


@pytest.mark.parametrize(("document", "layer"), [("SPEC.md", "contract"), ("PLAN.md", "mechanics")])
def test_the_registry_and_the_prose_agree(document: str, layer: str) -> None:
    """Neither document nor registry may carry a requirement the other has never heard of.

    Since T27 the documents are generated from the registry, so this cannot fail on its own --
    `tests/test_reqgen.py` is the equality check that does the real work. It stays because it
    fails *legibly*: "the registry has an id SPEC.md lacks" names the missing placeholder, where
    a whole-file diff would only say the file is stale.
    """
    prose = _ids_in(document)
    registry = {alias for entry in REQUIREMENTS if entry["layer"] == layer for alias in entry["aliases"]}
    assert prose - registry == set(), f"{document} declares ids the registry lacks: {sorted(prose - registry)}"
    assert registry - prose == set(), f"the registry has {layer} ids {document} lacks: {sorted(registry - prose)}"


def _citation_sources() -> list[pathlib.Path]:
    """Every file whose citations this test checks."""
    return [
        *sorted((ROOT / "pybosl2").rglob("*.py")),
        *sorted((ROOT / "tests").rglob("*.py")),
        ROOT / "AGENTS.md",
    ]


def test_every_qualified_citation_resolves() -> None:
    """`(SPEC B-3)` in a comment must name a requirement that exists.

    Only document-qualified citations are checked. A bare `B-3` cannot be checked without
    guessing which document it means, which is the ambiguity the prefixed form removes.
    """
    unknown: dict[str, list[str]] = {}
    for path in _citation_sources():
        if path == pathlib.Path(__file__) or not path.exists():
            continue
        for document, identifier in CITATION.findall(path.read_text()):
            if f"{document}-{identifier}" not in BY_ID:
                unknown.setdefault(f"{document} {identifier}", []).append(path.relative_to(ROOT).as_posix())
    assert not unknown, f"citations naming no requirement: { {k: v[:3] for k, v in unknown.items()} }"


def test_the_untriaged_backlog_only_shrinks() -> None:
    """Triage each requirement once: does a test guard it, does a human, or does nothing?

    The count is the honest measure of how much of this project's own contract is checked. It
    started at 251 of 263 -- the citations collected during the migration are candidates, and a
    test that mentions a rule is not a test that guards it.
    """
    untriaged = [entry["id"] for entry in REQUIREMENTS if entry["status"] == "untriaged"]
    assert len(untriaged) <= UNTRIAGED_BUDGET, (
        f"{len(untriaged)} untriaged requirements, budget {UNTRIAGED_BUDGET}: {untriaged}. "
        f"A new rule has to say what checks it -- name the test and mark it `enforced`, or say "
        f"`reviewed`/`unenforced` with the reason. Writing the rule and saying nothing is how "
        f"250 of these accumulated."
    )
    if len(untriaged) < UNTRIAGED_BUDGET:
        pytest.fail(
            f"{len(untriaged)} untriaged, budget {UNTRIAGED_BUDGET} -- lower UNTRIAGED_BUDGET to "
            f"{len(untriaged)} so the backlog cannot grow back"
        )


#: How many requirements nothing checks. Each carries a `note` saying what is missing, so this is
#: a work list rather than a status. It only shrinks: writing the guard removes one, and a rule
#: that stops being checked has to be argued for rather than quietly downgraded.
UNENFORCED_BUDGET = 2


def test_the_unenforced_list_only_shrinks() -> None:
    """The honest measure of how much of this project's contract nothing checks.

    250 requirements were untriaged until T38; the triage found 19 that were mechanically checkable
    and simply unchecked. T39 closed 16 with three scans -- signatures, code hygiene, and the claims
    the package makes about itself -- and S-35 followed once the bottle caps stopped ignoring the
    texture they accepted. The two left are parity measured per option rather than per shape
    (PAR-4), and "every new callable arrives with three tests" (X-3), which is a reviewer's count.
    """
    unenforced = sorted(e["id"] for e in REQUIREMENTS if e["status"] == "unenforced")
    assert len(unenforced) <= UNENFORCED_BUDGET, (
        f"{len(unenforced)} unenforced requirements, budget {UNENFORCED_BUDGET}: {unenforced}. "
        f"A rule that was checked and is not any more needs its guard back, not a lower status."
    )
    if len(unenforced) < UNENFORCED_BUDGET:
        pytest.fail(
            f"{len(unenforced)} unenforced, budget {UNENFORCED_BUDGET} -- lower UNENFORCED_BUDGET "
            f"to {len(unenforced)} so the gap cannot reopen."
        )


def test_every_unenforced_requirement_says_what_is_missing() -> None:
    """An `unenforced` status without a reason is just a shrug with a label on it."""
    silent = sorted(
        e["id"] for e in REQUIREMENTS if e["status"] in ("unenforced", "reviewed") and not e.get("note", "").strip()
    )
    assert not silent, f"these say nothing about why nothing checks them: {silent}"
