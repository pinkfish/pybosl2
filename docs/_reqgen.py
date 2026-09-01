# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Render SPEC.md and PLAN.md from the requirements registry.

The registry (`spec/requirements.toml`) owns the requirements; the frames (`spec/spec.md.in`,
`spec/plan.md.in`) own everything else -- section prose, the architecture diagram, the tables, the
conformance status. A frame carries `{{requirements: <section>}}` placeholders where the bullets
for that section go, so prose stays hand-written and requirements stay data, and neither is a copy
of the other (SPEC DOC-1, PLAN D-P7).

Usage:
    python docs/_reqgen.py            # write SPEC.md and PLAN.md
    python docs/_reqgen.py --check    # exit non-zero if the committed files are stale
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import textwrap
import tomllib
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "spec" / "requirements.toml"

#: Where each document's frame lives, and which registry layer fills it.
DOCUMENTS = {
    "SPEC.md": ("spec/spec.md.in", "contract"),
    "PLAN.md": ("spec/plan.md.in", "mechanics"),
}

PLACEHOLDER = re.compile(r"^\{\{requirements: (?P<section>.+)\}\}$")

WIDTH = 100


def requirements() -> list[dict[str, Any]]:
    """Return every requirement in the registry, in registry order."""
    return list(tomllib.loads(REGISTRY.read_text())["requirement"])


def _wrap(text: str, first: str, rest: str) -> list[str]:
    """Wrap *text* to the document width, prefixing the first line and the continuations."""
    return textwrap.wrap(
        text,
        width=WIDTH,
        initial_indent=first,
        subsequent_indent=rest,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [first.rstrip()]


def render_statement(statement: str, indent: str) -> list[str]:
    """Render a statement body: paragraphs wrapped, sub-bullets indented, fences left alone."""
    lines: list[str] = []
    fenced = False
    for block in statement.split("\n"):
        if block.startswith("```"):
            fenced = not fenced
            lines.append(f"{indent}{block}")
            continue
        if fenced:
            lines.append(f"{indent}{block}" if block else "")
            continue
        if not block.strip():
            lines.append("")
            continue
        if block.startswith("* "):
            lines.extend(_wrap(block[2:], f"{indent}* ", f"{indent}  "))
            continue
        lines.extend(_wrap(block, indent, indent))
    return lines


def render(entry: dict[str, Any]) -> str:
    """Render one requirement as its markdown bullet."""
    bare = entry["aliases"][0]
    title = entry.get("title", "")
    inner = f"{bare} {title}" if title else bare
    # A withdrawn requirement keeps its id and is struck through, never deleted (SPEC 13 rule 5).
    head = f"**~~{inner}~~**" if entry["status"] == "withdrawn" else f"**{inner}**"
    statement = str(entry["statement"]).strip()

    body = render_statement(statement, "  ")
    # The head joins the first line of the statement, as the documents have always written it.
    first = body[0].strip() if body and body[0].strip() and not body[0].strip().startswith(("*", "```")) else ""
    if first:
        merged = _wrap(f"{head} {first}", "* ", "  ")
        return "\n".join(merged + body[1:])
    return "\n".join([f"* {head}"] + body)


def render_document(name: str) -> str:
    """Return *name* rendered from its frame and the registry."""
    frame_path, layer = DOCUMENTS[name]
    entries = [e for e in requirements() if e["layer"] == layer]
    by_section: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_section.setdefault(str(entry["section"]), []).append(entry)

    out: list[str] = []
    used: set[str] = set()
    for line in (ROOT / frame_path).read_text().splitlines():
        match = PLACEHOLDER.match(line)
        if not match:
            out.append(line)
            continue
        section = match.group("section")
        if section not in by_section:
            raise SystemExit(f"{frame_path}: no requirements in section {section!r}")
        used.add(section)
        out.extend(render(entry) for entry in by_section[section])
    missing = sorted(set(by_section) - used)
    if missing:
        raise SystemExit(f"{frame_path}: sections with no placeholder, so their requirements would vanish: {missing}")
    return "\n".join(out) + "\n"


def main() -> int:
    """Write both documents, or check that the committed copies are current."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit non-zero if a document is stale")
    arguments = parser.parse_args()

    stale: list[str] = []
    for name in DOCUMENTS:
        rendered = render_document(name)
        target = ROOT / name
        if arguments.check:
            if target.read_text() != rendered:
                stale.append(name)
        else:
            target.write_text(rendered)
            print(f"wrote {name}")
    if stale:
        print(f"stale (run `python docs/_reqgen.py`): {', '.join(stale)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
