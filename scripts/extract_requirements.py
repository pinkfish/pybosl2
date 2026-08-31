# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""One-shot migration: build ``spec/requirements.toml`` from SPEC.md and PLAN.md.

This runs once, for T26. The registry it writes is hand-maintained from then on, and
``tests/test_requirements.py`` is what keeps it honest. Re-running is safe -- it is a pure
function of the two documents -- but it will discard any hand-editing done since, so run it
only while migrating.

Usage:
    python scripts/extract_requirements.py [--check]

``--check`` re-extracts and diffs against the committed registry's *statements* without writing,
so the migration can be verified without clobbering the file.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: A requirement id as the documents spell it: `S-2`, `B2-1`, `PAR-3`, `D-P5b`, `T-4b(i)`.
ID = r"[A-Z][A-Z0-9]*-P?\d+[a-z]?(?:\(i\))?"

#: The opening line of a requirement bullet, with the id and (optionally) a bold title.
BULLET = re.compile(rf"^\* \*\*(?P<struck>~~)?(?P<id>{ID})(?P<rest>.*)$")

#: A markdown heading, which both ends the previous requirement and names the section.
HEADING = re.compile(r"^(?P<level>#{2,4}) +(?P<title>.+?)\s*$")

#: RFC 2119 keywords, strongest first -- a requirement is filed under the strongest it uses.
KEYWORDS = ("MUST NOT", "MUST", "SHOULD NOT", "SHOULD", "MAY")

DOCUMENTS = {"SPEC.md": "contract", "PLAN.md": "mechanics"}


def _title_and_body(rest: str) -> tuple[str, str]:
    """Split a bullet's remainder into its bold title and the first line of its statement.

    Two shapes appear in the documents: ``**C-15 One contract, two specialisations.** Shape
    declares...`` and ``**A-1** A lower layer MUST NOT...``. The first has a title inside the
    bold span; the second has none.
    """
    if rest.startswith("**"):
        return "", rest[2:].strip()
    title, _, remainder = rest.partition("**")
    return title.strip(" —-.").replace("~~", ""), remainder.strip()


def _unwrap(lines: list[str]) -> str:
    """Join the hard-wrapped prose back into paragraphs.

    The documents wrap at 100 characters, which is a rendering detail; the registry holds the
    statement, so the wrapping goes. Sub-bullets, blank lines and fenced code keep their shape.
    """
    out: list[str] = []
    fenced = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            fenced = not fenced
            out.append(stripped)
            continue
        if fenced:
            out.append(line)
            continue
        if not stripped:
            out.append("")
            continue
        is_item = re.match(r"\s*[*-] ", line) is not None
        if is_item or not out or out[-1] == "" or out[-1].startswith("```"):
            out.append(stripped if not is_item else "* " + re.sub(r"^\s*[*-] ", "", line).strip())
            continue
        out[-1] = f"{out[-1]} {stripped}"
    return "\n".join(out).strip()


def _keyword(text: str) -> str:
    """Return the strongest RFC 2119 keyword the statement uses, or an empty string."""
    for word in KEYWORDS:
        if re.search(rf"\b{word}\b", text):
            return word
    return ""


def parse(document: str) -> list[dict[str, object]]:
    """Return every numbered requirement in *document*, in document order."""
    lines = (ROOT / document).read_text().splitlines()
    requirements: list[dict[str, object]] = []
    section = ""
    current: dict[str, object] | None = None
    body: list[str] = []

    def flush() -> None:
        if current is not None:
            current["statement"] = _unwrap(body)
            requirements.append(current)

    for line in lines:
        heading = HEADING.match(line)
        if heading:
            flush()
            current, body = None, []
            if heading.group("level") in ("##", "###"):
                section = heading.group("title").replace("*", "")
            continue
        bullet = BULLET.match(line)
        if bullet:
            flush()
            title, first = _title_and_body(bullet.group("rest"))
            current = {
                "id": bullet.group("id"),
                "title": title,
                "section": section,
                "struck": bool(bullet.group("struck")),
            }
            body = [first] if first else []
            continue
        if current is not None:
            if line.startswith("* ") or line.strip() in ("---", "```"):
                # A non-requirement bullet or a fence ends the statement; tables and prose
                # between requirements belong to the section, not to the requirement above.
                flush()
                current, body = None, []
                continue
            body.append(line.strip() if not line.startswith("  ") else line)
    flush()
    return requirements


#: Requirements whose enforcement was confirmed by hand during the T26 migration, by reading the
#: named test and checking it fails when the rule is broken. Everything else starts `untriaged`:
#: a citation is evidence that a test *mentions* a rule, never that it *guards* it, and inferring
#: the second from the first would repeat the failure this registry exists to catch.
CONFIRMED: dict[str, tuple[str, str, str]] = {
    "B2-1": ("enforced", "tests/test_bosl2_coverage.py::test_every_named_module_exists", ""),
    "C-7a": ("enforced", "tests/test_polyline_parameters.py::test_no_new_parameter_takes_raw_points", ""),
    "C-20": ("enforced", "tests/test_shape_contract.py::test_the_contract_is_the_whole_object", ""),
    "D-3": ("enforced", "tests/test_defaults.py::test_no_mutable_defaults_anywhere_in_the_package", ""),
    "R-1": ("enforced", "tests/test_facets.py::test_no_new_curved_api_without_facet_controls", ""),
    "S-2b": ("enforced", "tests/test_bounds_contract.py::test_every_bounds_is_a_bounds_object", ""),
    "A-1": (
        "unenforced",
        "",
        "No test walks the import graph. 16 L0 modules import L2 today, 4 of them at module level "
        "(regions -> shapes3d, path2d/path3d -> miscellaneous, turtle2d -> shapes2d). T29.",
    ),
    "A-6": (
        "unenforced",
        "",
        "The top-level export table is checked, but the L0 geometry bridges are not: "
        "Path2D.polygon() imports pythonscad directly and returns a CsgShape2D whatever backend "
        "is active. T29.",
    ),
    "C-21": (
        "unenforced",
        "",
        "Guarded on the shape surface only. The path types carry three synonym pairs -- "
        "deduplicate/deduplicated, subdivide/subdivide_path, resample/resample_path. T32.",
    ),
    "S-2": (
        "unenforced",
        "",
        "243 functions exceed 50 lines, the longest at 237. Either ratchet it per module or retire the number. T32.",
    ),
}


def citations_in_tests() -> dict[str, set[str]]:
    """Map each requirement id to the tests that name it.

    These are *candidates* for ``enforced_by``, not enforcement. A test that cites a requirement
    often guards it and often merely mentions it in passing, and telling the two apart means
    reading the test -- so the registry records the proposal and the triage backlog, and a human
    moves each one to ``enforced``, ``reviewed`` or ``unenforced``.
    """
    found: dict[str, set[str]] = {}
    pattern = re.compile(rf"(?<![\w-]){ID}(?![\w-])")
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        relative = path.relative_to(ROOT).as_posix()
        test = ""
        for line in path.read_text().splitlines():
            definition = re.match(r"\s*def (test_\w+)", line)
            if definition:
                test = definition.group(1)
            for identifier in pattern.findall(line):
                node = f"{relative}::{test}" if test else relative
                found.setdefault(identifier, set()).add(node)
    return found


def _useful_candidates(candidates: list[str], confirmed: str) -> list[str]:
    """Drop the confirmed node and any bare file path a node id from the same file already covers."""
    nodes = [c for c in candidates if "::" in c and c != confirmed]
    files = {c.split("::")[0] for c in nodes} | ({confirmed.split("::")[0]} if confirmed else set())
    return sorted(nodes + [c for c in candidates if "::" not in c and c not in files])


def _literal(text: str) -> str:
    """Render *text* as a TOML multi-line literal string (no escape processing)."""
    if "'''" in text:  # pragma: no cover - no statement in either document contains one
        raise SystemExit(f"cannot serialise a statement containing ''': {text[:60]}")
    return "'''\n" + text.rstrip() + "\n'''"


def render(entries: list[dict[str, object]]) -> str:
    """Render the whole registry as TOML."""
    out = [
        "# The pybosl2 requirements registry -- the normative source for SPEC.md and PLAN.md.",
        "#",
        "# Generated once from the prose by scripts/extract_requirements.py (T26) and hand-maintained",
        "# since. tests/test_requirements.py keeps it honest: ids are unique across both documents,",
        "# every enforced_by target exists, every citation resolves, and the untriaged backlog only",
        "# shrinks. Ids are permanent (SPEC 13 rule 5) -- a new requirement appends to its series, and",
        "# a withdrawn one keeps its id.",
        "#",
        "# layer:   contract -> SPEC.md, mechanics -> PLAN.md",
        "#",
        "# status:  enforced   (the test in enforced_by fails when the rule is broken)",
        "#          reviewed   (a human checks it at review time; no test can)",
        "#          unenforced (nothing checks it, and the note says what is broken)",
        "#          untriaged  (nobody has decided yet -- the backlog, which only shrinks)",
        "#          withdrawn  (kept for its id, with the reason)",
        "#",
        "# candidates: tests that mention the id. Evidence for triage, never enforcement -- a test",
        "#             that mentions a rule may guard it or may merely cite it, and only reading it",
        "#             tells you which.",
        "",
    ]
    for entry in entries:
        out.append("[[requirement]]")
        out.append(f'id = "{entry["id"]}"')
        out.append(f'aliases = ["{entry["bare"]}"]')
        out.append(f'layer = "{entry["layer"]}"')
        out.append(f'section = "{entry["section"]}"')
        if entry["title"]:
            out.append(f'title = "{str(entry["title"]).replace(chr(34), chr(39))}"')
        if entry["keyword"]:
            out.append(f'keyword = "{entry["keyword"]}"')
        out.append(f"statement = {_literal(str(entry['statement']))}")
        enforced = entry["enforced_by"]
        assert isinstance(enforced, list)
        if enforced:
            out.append("enforced_by = [")
            out.extend(f'    "{node}",' for node in enforced)
            out.append("]")
        else:
            out.append("enforced_by = []")
        candidates = entry["candidates"]
        assert isinstance(candidates, list)
        if candidates:
            out.append("candidates = [")
            out.extend(f'    "{node}",' for node in candidates)
            out.append("]")
        out.append(f'status = "{entry["status"]}"')
        if entry["note"]:
            out.append(f"note = {_literal(str(entry['note']))}")
        out.append("")
    return "\n".join(out)


def build() -> list[dict[str, object]]:
    """Return every requirement from both documents, ready to render."""
    citations = citations_in_tests()
    entries: list[dict[str, object]] = []
    for document, layer in DOCUMENTS.items():
        prefix = document.removesuffix(".md")
        for requirement in parse(document):
            bare = str(requirement["id"])
            candidates = sorted(citations.get(bare, ()))
            status, node, note = CONFIRMED.get(bare, ("untriaged", "", ""))
            if requirement["struck"]:
                status, note = "withdrawn", note or "Withdrawn in the prose; see the statement."
            entries.append(
                {
                    "id": f"{prefix}-{bare}",
                    "bare": bare,
                    "layer": layer,
                    "section": requirement["section"],
                    "title": requirement["title"],
                    "keyword": _keyword(str(requirement["statement"])),
                    "statement": requirement["statement"],
                    "enforced_by": [node] if node else [],
                    "candidates": _useful_candidates(candidates, node),
                    "status": status,
                    "note": note,
                }
            )
    return entries


def main() -> int:
    """Write (or check) the registry, and report what the migration found."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report without writing")
    arguments = parser.parse_args()

    entries = build()
    target = ROOT / "spec" / "requirements.toml"
    text = render(entries)
    if not arguments.check:
        target.write_text(text)

    contract = sum(1 for e in entries if e["layer"] == "contract")
    counts: dict[str, int] = {}
    for entry in entries:
        counts[str(entry["status"])] = counts.get(str(entry["status"]), 0) + 1
    print(f"{len(entries)} requirements: {contract} contract, {len(entries) - contract} mechanics")
    print("  " + "   ".join(f"{status}: {count}" for status, count in sorted(counts.items())))
    print(f"  with a candidate test to triage: {sum(1 for e in entries if e['candidates'])}")
    print(f"  {'checked' if arguments.check else 'written'}: {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
