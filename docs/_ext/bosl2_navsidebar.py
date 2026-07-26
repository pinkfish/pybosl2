# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Sphinx extension that auto-generates a right-hand navigation sidebar on every
module page from the Python source.  Class names link to their section anchor;
method/function names are listed as plain labels (the Sphinx HTML builder for
``autoclass`` does not emit per-method fragment IDs).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util import logging

logger = logging.getLogger(__name__)


def _parse_module(filepath: Path) -> list[tuple[str, str, str | None]]:
    """Return list of ``(type, name, parent)`` for public members."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except Exception:
        return []
    members: list[tuple[str, str, str | None]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            members.append(("func", node.name, None))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            members.append(("class", node.name, None))
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.FunctionDef) and not child.name.startswith("_"):
                    members.append(("meth", child.name, node.name))
    return members


def _build_html(members: list[tuple[str, str, str | None]], module_ref: str) -> str:
    """Build the sidebar HTML."""
    lines = ['<aside class="sidebar"><p class="sidebar-title">Navigation</p>', '<ul class="pysidebar-list">']
    for mtype, name, parent in members:
        if mtype == "class":
            target = f"{module_ref}.{name}"
            lines.append(f'<li class="ps-class"><a href="#{target}"><strong>{name}</strong></a></li>')
        elif mtype == "meth":
            lines.append(f'<li class="ps-meth"><span>{parent}.{name}</span></li>')
        elif mtype == "func":
            lines.append(f'<li class="ps-func"><span>{name}</span></li>')
    lines.append("</ul></aside>")
    return "\n".join(lines)


def _on_html_page_context(
    app: Sphinx, pagename: str, templatename: str, context: dict, doctree: nodes.document
) -> None:
    """Inject the sidebar HTML into the page body at build time."""
    if not context.get("body"):
        return

    src = app.env.doc2path(pagename)
    try:
        text = Path(src).read_text(encoding="utf-8")
    except Exception:
        return

    m = re.search(r"\.\. auto(?:module|class|function)::\s*([\w.]+)", text)
    if not m:
        return

    module_ref = m.group(1)
    parts = module_ref.split(".")
    if parts[0] == "bosl2" and len(parts) >= 2:
        filepath = Path(app.srcdir).parent / "bosl2" / f"{parts[1]}.py"
    else:
        return

    if not filepath.is_file():
        return

    members = _parse_module(filepath)
    if not members:
        return

    sidebar_html = _build_html(members, module_ref)
    context["body"] = sidebar_html + context["body"]


def setup(app: Sphinx) -> None:
    app.connect("html-page-context", _on_html_page_context)
