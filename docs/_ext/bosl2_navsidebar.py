# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Sphinx extension that generates a global fixed right-hand navigation sidebar with
links to every public function, class, and method across all ``bosl2`` modules.
Class names are bold; methods are shown as ``.method`` (without the class prefix)
and link into the parent module's page anchor.
"""

from __future__ import annotations

import ast
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


def _scan_all_modules(srcdir: Path) -> dict[str, list[tuple[str, str, str | None]]]:
    """Scan all ``bosl2/*.py`` files and return ``{module_name: members}``."""
    bosl2_dir = srcdir.parent / "bosl2"
    if not bosl2_dir.is_dir():
        return {}
    result: dict[str, list[tuple[str, str, str | None]]] = {}
    for pyfile in sorted(bosl2_dir.glob("*.py")):
        if pyfile.name.startswith("_"):
            continue
        members = _parse_module(pyfile)
        if members:
            result[pyfile.stem] = members
    return result


def _build_global_html(
    all_modules: dict[str, list[tuple[str, str, str | None]]],
) -> str:
    """Build the global sidebar HTML with cross-page links."""
    lines = [
        '<aside class="sidebar" id="pysidebar-global">',
        '<p class="sidebar-title">All Functions</p>',
        '<ul class="pysidebar-list">',
    ]
    for mod_name, members in all_modules.items():
        module_ref = f"bosl2.{mod_name}"
        page = f"{mod_name}.html"
        for mtype, name, parent in members:
            if mtype == "class":
                anchor = f"{module_ref}.{name}"
                lines.append(f'<li class="ps-class"><a href="{page}#{anchor}"><strong>{name}</strong></a></li>')
            elif mtype == "meth":
                anchor = f"{module_ref}.{parent}.{name}"
                lines.append(f'<li class="ps-meth"><a href="{page}#{anchor}">.{name}</a></li>')
            elif mtype == "func":
                anchor = f"{module_ref}.{name}"
                lines.append(f'<li class="ps-func"><a href="{page}#{anchor}">{name}</a></li>')
    lines.append("</ul></aside>")
    return "\n".join(lines)


_sidebar_html: str | None = None


def _get_sidebar_html(app: Sphinx) -> str:
    """Build the global sidebar once and cache it."""
    global _sidebar_html
    if _sidebar_html is None:
        all_modules = _scan_all_modules(app.srcdir)
        _sidebar_html = _build_global_html(all_modules)
    return _sidebar_html


def _on_html_page_context(
    app: Sphinx,
    pagename: str,
    templatename: str,
    context: dict,
    doctree,  # noqa: ANN001
) -> None:
    """Inject the global sidebar into every HTML page."""
    body = context.get("body")
    if not body:
        return
    context["body"] = _get_sidebar_html(app) + body


def setup(app: Sphinx) -> None:
    app.connect("html-page-context", _on_html_page_context)
