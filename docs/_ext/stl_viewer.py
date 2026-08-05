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
#    ``pybosl2/docs/_ext/pybosl2_example.py`` reuses :func:`stl_viewer_html` to show an interactive
#    viewer for each rendered example's exported STL, right beside its source and a download link.
#
# FileGroup: pybosl2

from __future__ import annotations

import json
from uuid import uuid4

from docutils import nodes
from docutils.parsers.rst import Directive, directives

# three.js pulled from esm.sh, which rewrites the addon modules' bare ``import ... from "three"``
# to the matching pinned build, so STLLoader/OrbitControls share the same THREE instance without
# needing a page-level importmap.
_THREE = "https://esm.sh/three@0.160.0"

_TEMPLATE = """
<div class="stl-viewer" id="{vid}" style="width:{width};height:{height};border:1px solid #ddd;\
border-radius:4px;background:{background};touch-action:none"></div>
<script type="module">
import * as THREE from "{three}";
import {{ STLLoader }} from "{three}/examples/jsm/loaders/STLLoader.js";
import {{ OrbitControls }} from "{three}/examples/jsm/controls/OrbitControls.js";

const el = document.getElementById("{vid}");
const scene = new THREE.Scene();
scene.background = new THREE.Color("{background}");
const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 1e6);
camera.up.set(0, 0, 1);
const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setPixelRatio(window.devicePixelRatio);
el.appendChild(renderer.domElement);

scene.add(new THREE.AmbientLight(0xffffff, 0.65));
const key = new THREE.DirectionalLight(0xffffff, 0.85); key.position.set(1, 0.6, 1); scene.add(key);
const fill = new THREE.DirectionalLight(0xffffff, 0.4); fill.position.set(-1, -0.8, 0.5); scene.add(fill);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

function resize() {{
  const w = el.clientWidth, h = el.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / Math.max(1, h);
  camera.updateProjectionMatrix();
}}

new STLLoader().load("{uri}", function (geo) {{
  geo.computeVertexNormals();
  geo.computeBoundingBox();
  const center = new THREE.Vector3(); geo.boundingBox.getCenter(center);
  const size = new THREE.Vector3(); geo.boundingBox.getSize(size);
  geo.translate(-center.x, -center.y, -center.z);
  const mesh = new THREE.Mesh(geo, new THREE.MeshPhongMaterial({{
    color: "{color}", specular: 0x222222, shininess: 25, flatShading: false,
  }}));
  scene.add(mesh);
  const r = Math.max(size.x, size.y, size.z) || 1;
  camera.position.set(r * 1.3, -r * 1.7, r * 1.1);
  controls.target.set(0, 0, 0);
  resize();
  (function animate() {{ requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); }})();
}}, undefined, function (err) {{
  el.innerHTML = '<p style="padding:1em;color:#a00">Could not load STL (serve the docs over HTTP to view).</p>';
}});
window.addEventListener("resize", resize);
</script>
"""


def stl_viewer_html(
    uri: str,
    width: str = "100%",
    height: str = "360px",
    color: str = "#6f9ac9",
    background: str = "#f7f7f9",
) -> str:
    """The raw HTML embedding an interactive three.js viewer for the STL at *uri*."""
    return _TEMPLATE.format(
        vid="stlviewer-" + uuid4().hex,
        uri=uri,
        three=_THREE,
        width=width,
        height=height,
        color=color,
        background=background,
    )


_SPEC_VIEWER_SCRIPT = """<script type="module">
import * as THREE from "{three}";
import {{ STLLoader }} from "{three}/examples/jsm/loaders/STLLoader.js";
import {{ OrbitControls }} from "{three}/examples/jsm/controls/OrbitControls.js";
const V = {data};
const box = document.getElementById("viewer"), poster = document.getElementById("poster");
let renderer, scene, camera, controls, mesh, ready = false;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || null;
const primaryColor = css("--model") || "{color}";
function resize() {{ const w = box.clientWidth, h = box.clientHeight || 300;
  renderer.setSize(w, h, false); camera.aspect = w / Math.max(1, h); camera.updateProjectionMatrix(); }}
function init() {{
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(38, 1, 0.01, 1e6); camera.up.set(0, 0, 1);
  renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
  renderer.setPixelRatio(window.devicePixelRatio); box.appendChild(renderer.domElement);
  scene.add(new THREE.AmbientLight(0xffffff, 0.7));
  const k = new THREE.DirectionalLight(0xffffff, 0.85); k.position.set(1, 0.6, 1); scene.add(k);
  const f = new THREE.DirectionalLight(0xffffff, 0.4); f.position.set(-1, -0.8, 0.5); scene.add(f);
  controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true;
  window.addEventListener("resize", resize); ready = true;
  (function loop() {{ requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); }})();
}}
const loader = new STLLoader();
function load(uri) {{
  if (!ready) init();
  loader.load(uri, geo => {{
    if (mesh) {{ scene.remove(mesh); mesh.geometry.dispose(); }}
    geo.computeVertexNormals(); geo.computeBoundingBox();
    const c = new THREE.Vector3(); geo.boundingBox.getCenter(c);
    const s = new THREE.Vector3(); geo.boundingBox.getSize(s);
    geo.translate(-c.x, -c.y, -c.z);
    mesh = new THREE.Mesh(geo,
      new THREE.MeshPhongMaterial({{ color: primaryColor, specular: 0x222222, shininess: 22 }}));
    scene.add(mesh);
    const r = Math.max(s.x, s.y, s.z) || 1;
    camera.position.set(r * 1.4, -r * 1.8, r * 1.15); controls.target.set(0, 0, 0);
    poster.style.display = "none"; box.querySelector(".hint")?.remove(); resize();
  }}, undefined, () => {{
    if (!box.querySelector(".hint")) {{ const h = document.createElement("div");
      h.className = "hint";
      h.textContent = "serve the docs over HTTP for the interactive 3-D view";
      box.appendChild(h); }}
  }});
}}
function select(i) {{
  const v = V[i];
  document.querySelectorAll(".spec-tags button.spec-tag").forEach((b, j) =>
    b.setAttribute("aria-selected", j === i ? "true" : "false"));
  document.getElementById("code").innerHTML = "&gt;&gt;&gt; " + v.code;
  document.getElementById("s-tris").textContent = v.tris == null ? "\\u2014" : v.tris.toLocaleString();
  document.getElementById("s-vol").textContent = v.vol; document.getElementById("s-bbox").textContent = v.bbox;
  document.getElementById("vpart").textContent = v.part;
  document.getElementById("wtpill").style.display = v.wt ? "" : "none";
  load(v.uri);
}}
document.querySelectorAll(".tags button.tag").forEach((b, i) => b.addEventListener("click", () => select(i)));
select(0);
</script>"""


def spec_viewer_html(
    variants: list[dict[str, str]],
    width: int = 640,  # noqa: ARG001
    height: int = 400,  # noqa: ARG001
    color: str = "#6f9ac9",
) -> str:
    """Return HTML for an interactive STL viewer with variant-switching buttons.

    Each variant entry has:
    - label: button label
    - stl:  relative URL to the STL file
    - metrics: optional dict with "ntris", "volume", "watertight", "size_x", "size_y", "size_z"

    The caller must provide these DOM elements on the page:
      #viewer  — container for the three.js canvas
      #poster  — static poster image hidden after first load
      .spec-tags button.spec-tag  — variant-switching buttons (one per variant)
      #code    — element displaying the current variant's Python code
      #s-tris  — triangle count display
      #s-vol   — volume display
      #s-bbox  — bounding-box display
      #vpart   — part description display
      #wtpill  — watertight pill indicator
    """
    data_json = json.dumps(variants)
    return _SPEC_VIEWER_SCRIPT.format(three=_THREE, data=data_json, color=color)


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
            background=self.options.get("background", "#f7f7f9"),
        )
        return [nodes.raw("", html, format="html")]


def setup(app) -> dict:
    app.add_directive("stl", STLDirective)
    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
