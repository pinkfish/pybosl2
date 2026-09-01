# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""One-shot migration (T27): split SPEC.md and PLAN.md into frame + registry.

Every run of requirement bullets becomes a `{{requirements: <section>}}` placeholder; everything
else -- prose, tables, the architecture diagram, the conformance status -- stays in the frame,
verbatim. The registry already holds the requirements themselves (T26).

The check that matters is at the end: regenerate from frame + registry and compare against the
original with whitespace normalised. Wrapping moves, because the generator re-wraps; **no word
may.** If any does, the migration is not safe to commit and this exits non-zero.

Usage:
    python scripts/build_spec_frames.py
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "docs"))

ID = r"[A-Z][A-Z0-9]*-P?\d+[a-z]?(?:\(i\))?"
BULLET = re.compile(rf"^\* \*\*(?:~~)?({ID})")
HEADING = re.compile(r"^(#{2,4}) +(.+?)\s*$")

DOCUMENTS = {"SPEC.md": "spec/spec.md.in", "PLAN.md": "spec/plan.md.in"}


def _is_continuation(line: str) -> bool:
    """Whether *line* continues the requirement bullet above it."""
    return line.startswith(("  ", "\t")) or not line.strip()


def build_frame(document: str) -> str:
    """Return *document* with each run of requirement bullets replaced by a placeholder."""
    lines = (ROOT / document).read_text().splitlines()
    out: list[str] = []
    section = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        heading = HEADING.match(line)
        if heading:
            section = heading.group(2).replace("*", "")
            out.append(line)
            index += 1
            continue
        if BULLET.match(line):
            # Swallow this bullet and every one that follows it in the same run.
            while index < len(lines):
                if BULLET.match(lines[index]):
                    index += 1
                    while index < len(lines) and not BULLET.match(lines[index]) and _is_continuation(lines[index]):
                        index += 1
                    continue
                break
            placeholder = f"{{{{requirements: {section}}}}}"
            if placeholder not in out:
                out.append(placeholder)
            # A run that ends on blank lines keeps one, as the prose reads today.
            while out and out[-1] == "":
                out.pop()
            out.append("")
            continue
        out.append(line)
        index += 1
    return "\n".join(out) + "\n"


def words(text: str) -> list[str]:
    """Return the text as a bare word sequence: what must survive the migration exactly."""
    return text.split()


def main() -> int:
    """Build both frames and refuse to leave them behind if a word was lost."""
    import _reqgen  # the generator lives in docs/, which main() put on the path above

    for document, frame in DOCUMENTS.items():
        original = (ROOT / document).read_text()
        (ROOT / frame).write_text(build_frame(document))
        rendered = _reqgen.render_document(document)

        before, after = words(original), words(rendered)
        if before != after:
            lost = [w for w in before if w not in set(after)]
            gained = [w for w in after if w not in set(before)]
            print(f"{document}: MIGRATION IS NOT LOSSLESS", file=sys.stderr)
            print(f"  {len(before)} words before, {len(after)} after", file=sys.stderr)
            print(f"  first 12 words only in the original: {lost[:12]}", file=sys.stderr)
            print(f"  first 12 words only in the render:   {gained[:12]}", file=sys.stderr)
            for i, (a, b) in enumerate(zip(before, after, strict=False)):
                if a != b:
                    print(f"  diverges at word {i}: {before[max(0, i - 8) : i + 8]}", file=sys.stderr)
                    print(f"                  vs: {after[max(0, i - 8) : i + 8]}", file=sys.stderr)
                    break
            return 1
        print(f"{document}: {len(before)} words preserved exactly ({frame})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
