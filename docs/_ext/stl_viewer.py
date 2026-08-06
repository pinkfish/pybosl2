# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/docs/_ext/stl_viewer.py
#    Sphinx extension providing an ``.. stl:: <uri>`` directive that embeds an INTERACTIVE 3-D
#    viewer (rotate / pan / zoom) for an STL mesh, the same idea as the PyPI ``sphinxstl``
#    package's directive -- but self-contained and working on current Sphinx.
#
#    The real ``sphinxstl`` (0.1.1) cannot be used here: it calls the ``app.add_javascript()``
#    API that Sphinx removed in 4.0, and its wheel ships without the thingiview.js/three.min.js
#    assets it depends on. This drop-in registers the same ``stl`` directive name, but renders
#    with three.js (loaded as ES modules from a CDN via esm.sh, so no importmap or vendored
#    bundle is needed) and needs no build-finished asset copying.
#
#    The directive only emits a placeholder ``<div class="stl-viewer" data-stl-uri="...">``; all the
#    three.js work lives in the single page-wide module ``docs/_static/stl_viewer.js``. That split is
#    deliberate: an API page can hold dozens of examples (paths.html has 36), and the previous
#    one-inline-script-and-one-WebGLRenderer-per-viewer layout exhausted the browser's live-WebGL
#    -context limit, so contexts were force-lost and canvases flashed blank. The shared runtime uses
#    one context for the whole page, loads meshes only as they scroll into view, and redraws a
#    viewer only when it actually changed.
#
#    ``pybosl2/docs/_ext/pybosl2_example.py`` reuses :func:`stl_viewer_html` to show an interactive
#    viewer for each rendered example's exported STL, right beside its source and a download link.
#
# FileGroup: pybosl2

from __future__ import annotations

import json
from html import escape

from docutils import nodes
from docutils.parsers.rst import Directive, directives

_TEMPLATE = (
    '<div class="stl-viewer" data-stl-uri="{uri}" data-stl-color="{color}" style="{style}">'
    '<div class="stl-viewer-status">Loading 3-D preview&hellip;</div>'
    "</div>"
)


def stl_viewer_html(
    uri: str,
    width: str = "100%",
    height: str = "360px",
    color: str = "#6f9ac9",
    background: str = "",
) -> str:
    """The raw HTML placeholder that ``_static/stl_viewer.js`` turns into a viewer for *uri*.

    *background* defaults to empty, which leaves the panel colour to the stylesheet's theme-aware
    ``.stl-viewer`` rule (the viewer renders with a transparent clear colour, so the element's own
    background shows through and follows the light/dark toggle).
    """
    style = f"width:{width};height:{height}"
    if background:
        style += f";background:{background}"
    return _TEMPLATE.format(
        uri=escape(uri, quote=True), color=escape(color, quote=True), style=escape(style, quote=True)
    )


def spec_viewer_html(
    variants: list[dict[str, str]],
    width: int = 640,  # noqa: ARG001
    height: int = 400,  # noqa: ARG001
) -> str:
    """Return variant data as a JSON string for embedding in a script element.

    Each variant entry has:
    - label: button label
    - uri:  relative URL to the STL file
    - metrics: optional dict with "ntris", "volume", "watertight", "size_x", "size_y", "size_z"

    The actual viewer logic is in ``_specgen.py``'s ``_RST_SCRIPT`` template (the spec sheets run
    their own single-viewer script, not the multi-viewer runtime in ``docs/_static/stl_viewer.js``).
    """
    return json.dumps(variants)


class STLDirective(Directive):
    """``.. stl:: <uri>`` -- embed an interactive 3-D viewer for an STL file (sphinxstl-compatible)."""

    required_arguments = 1
    final_argument_whitespace = True
    option_spec = {
        "color": directives.unchanged,
        "background": directives.unchanged,
        "width": directives.unchanged,
        "height": directives.unchanged,
    }

    def run(self) -> list[nodes.Node]:
        html = stl_viewer_html(
            self.arguments[0],
            width=self.options.get("width", "100%"),
            height=self.options.get("height", "360px"),
            color=self.options.get("color", "#6f9ac9"),
            background=self.options.get("background", ""),
        )
        return [nodes.raw("", html, format="html")]


def setup(app) -> dict:
    app.add_directive("stl", STLDirective)
    # The shared runtime and its styling ride along on every page; the module is a no-op on pages
    # without a .stl-viewer element. ``type="module"`` also makes it defer, so the DOM is ready.
    app.add_js_file("stl_viewer.js", type="module")
    app.add_css_file("stl_viewer.css")
    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
