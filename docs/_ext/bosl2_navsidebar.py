# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Sphinx extension that auto-generates a right-hand navigation sidebar on every
module page from the Python source.  No manual RST updates needed.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import ClassVar

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.transforms import SphinxTransform
from sphinx.util import logging

logger = logging.getLogger(__name__)

ANCHOR = '<div class="pysidebar"><p class="pysidebar-title">Navigation</p><ul class="pysidebar-list">'
ANCHOR_END = "</ul></div>"


def _parse_module(filepath: Path):
    """Return sorted list of (type, name, parent) for public members."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except Exception:
        return []
    members = []
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
    """Build raw HTML for the sidebar."""
    html = ANCHOR
    for mtype, name, parent in members:
        if mtype == "class":
            anchor = f"{module_ref}.{name}"
            html += f'<li class="ps-class"><strong>{name}</strong></li>'
        elif mtype == "meth":
            anchor = f"{module_ref}.{parent}.{name}"
            html += f'<li class="ps-meth"><a href="#{anchor}">{parent}.{name}</a></li>'
        elif mtype == "func":
            anchor = f"module-{module_ref}.{name}"
            html += f'<li class="ps-func"><a href="#{anchor}">{name}</a></li>'
    html += ANCHOR_END
    return html


class NavSidebarTransform(SphinxTransform):
    """Inject a sidebar listing the module's public API."""

    default_priority: ClassVar[int] = 500

    def apply(self, **kwargs) -> None:  # noqa: ARG002
        env = self.env
        docname = env.docname
        src = env.doc2path(docname)
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
            filepath = Path(env.srcdir).parent / "bosl2" / f"{parts[1]}.py"
        else:
            return

        if not filepath.is_file():
            return

        members = _parse_module(filepath)
        if not members:
            return

        html = _build_html(members, module_ref)
        raw_node = nodes.raw("", html, format="html")
        document = self.document
        for i, child in enumerate(document.children):
            if isinstance(child, nodes.section):
                document.children.insert(i, raw_node)
                break
        else:
            document.insert(0, raw_node)


def setup(app: Sphinx) -> None:
    app.add_transform(NavSidebarTransform)
