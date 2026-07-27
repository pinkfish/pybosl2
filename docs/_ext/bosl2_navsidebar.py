# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Sphinx extension that generates a per-page fixed right-hand navigation sidebar
listing the current module's functions, classes, and methods.

Class names are bold; methods are shown as ``.method`` (without the class prefix)
and link into the page anchor.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from sphinx.application import Sphinx


def _parse_module(filepath: Path) -> list[tuple[str, str, str | None]]:
    """Return list of ``(type, name, parent)`` for public members.

    *type* is one of ``func``, ``class``, ``meth``.
    *parent* is the class name for methods, ``None`` otherwise.
    """
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


def _build_sidebar_html(members: list[tuple[str, str, str | None]], module_ref: str) -> str:
    """Build the sidebar HTML for a single module."""
    lines = [
        '<aside id="pysidebar-global">',
        '<p class="pysidebar-title">In this module</p>',
        '<ul class="pysidebar-list">',
    ]
    for mtype, name, parent in members:
        if mtype == "class":
            anchor = f"{module_ref}.{name}"
            lines.append(f'<li class="ps-class"><a href="#{anchor}"><strong>{name}</strong></a></li>')
        elif mtype == "meth":
            anchor = f"{module_ref}.{parent}.{name}"
            lines.append(f'<li class="ps-meth"><a href="#{anchor}">.{name}</a></li>')
        elif mtype == "func":
            anchor = f"{module_ref}.{name}"
            lines.append(f'<li class="ps-func"><a href="#{anchor}">{name}</a></li>')
    lines.append("</ul></aside>")
    return "\n".join(lines)


def _on_html_page_context(
    app: Sphinx,
    pagename: str,
    templatename: str,
    context: dict,
    doctree,  # noqa: ANN001
) -> None:
    """Inject a per-module sidebar into module pages only."""
    body = context.get("body")
    if not body:
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
    if parts[0] != "bosl2" or len(parts) < 2:
        return

    filepath = Path(app.srcdir).parent / "bosl2" / f"{parts[1]}.py"
    if not filepath.is_file():
        return

    members = _parse_module(filepath)
    if not members:
        return

    sidebar_html = _build_sidebar_html(members, module_ref)
    context["body"] = sidebar_html + body


def setup(app: Sphinx) -> None:
    app.connect("html-page-context", _on_html_page_context)
