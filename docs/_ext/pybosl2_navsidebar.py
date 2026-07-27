# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Sphinx extension that generates a per-page right-hand navigation sidebar
listing the current module's functions, classes, and methods.

Class names are bold; methods are shown as ``.method`` (without the class prefix)
and link into the page anchor.  The sidebar includes a collapse/expand toggle
and defaults to collapsed on narrow screens.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING

from sphinx.util import logging

if TYPE_CHECKING:
    from sphinx.application import Sphinx

logger = logging.getLogger(__name__)


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
        '<div class="ps-header">',
        '<p class="pysidebar-title">In this module</p>',
        '<button class="ps-toggle" title="Toggle sidebar">'
        '<svg width="14" height="14" viewBox="0 0 24 24"'
        ' fill="none" stroke="currentColor" stroke-width="2.5"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="15 18 9 12 15 6"/>'
        "</svg>"
        "</button>",
        "</div>",
        '<div class="ps-content">',
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
    lines.append("</ul></div></aside>")
    lines.append(
        "<script>"
        "(function(){"
        "var s=document.getElementById('pysidebar-global');"
        "if(!s)return;"
        "var d=document.querySelector('.document');"
        "if(d)d.insertBefore(s,d.querySelector('.clearer'));"
        "var btn=s.querySelector('.ps-toggle');"
        "var saved=localStorage.getItem('ps-collapsed');"
        "var narrow=window.matchMedia('(max-width:1060px)');"
        "function apply(v){if(v){s.classList.add('collapsed');}else{s.classList.remove('collapsed');}}"
        "function toggle(){"
        "var v=!s.classList.contains('collapsed');"
        "apply(v);localStorage.setItem('ps-collapsed',v?'1':'0');"
        "}"
        "if(narrow.matches){apply(saved==='0'?false:true);}"
        "else{apply(saved==='1');}"
        "btn.onclick=toggle;"
        "narrow.onchange=function(e){"
        "if(e.matches&&saved!=='0')apply(true);"
        "else if(!e.matches&&saved!=='1')apply(false);"
        "};"
        "})();"
        "</script>"
    )
    return "\n".join(lines)


def _on_html_page_context(
    app: Sphinx,
    pagename: str,
    templatename: str,
    context: dict,
    doctree,
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
    if parts[0] != "pybosl2" or len(parts) < 2:
        return

    filepath = Path(app.srcdir).parent / "pybosl2" / f"{parts[1]}.py"
    if not filepath.is_file():
        return

    members = _parse_module(filepath)
    if not members:
        return

    sidebar_html = _build_sidebar_html(members, module_ref)
    context["body"] = sidebar_html + body


def setup(app: Sphinx) -> None:
    app.connect("html-page-context", _on_html_page_context)
