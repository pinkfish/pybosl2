:icon: material/wrench-outline

.. _spec-shapes3d:

shapes3d
========

.. raw:: html

    <p class="spec-lede">BOSL2 3-D primitives: cuboid, sphere, cylinder, cone, prismoid, torus, tube, teardrop, and more — anchored and rounded for direct fabrication.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">cuboid([30, 20, 15])</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="3-D primitives schematic" xmlns="http://www.w3.org/2000/svg"><rect width="460" height="240" fill="var(--ground)"/><path d="M80,120 L120,60 L180,60 L220,120 L180,180 L120,180 Z M120,60 L120,180 M220,120 L180,180" fill="none" stroke="var(--ink-dim)" stroke-width="2" stroke-linecap="round"/></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>Every shape is <b>anchorable</b>: position with ``anchor=``, spin with ``spin=``, and orient with ``orient=``. Rounding, chamfering, and edge-selection work consistently across all primitives.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">cuboid</button> <button class="spec-tag" type="button">sphere</button> <button class="spec-tag" type="button">cylinder</button> <button class="spec-tag" type="button">cone</button> <button class="spec-tag" type="button">prismoid</button> <button class="spec-tag" type="button">torus</button> <button class="spec-tag" type="button">tube</button> <button class="spec-tag" type="button">teardrop</button> <button class="spec-tag" type="button">capsule</button> <button class="spec-tag" type="button">rounded cuboid</button> <button class="spec-tag" type="button">chamfered cyl</button> <button class="spec-tag" type="button">octahedron</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">12</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">9,000.0</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">30×20×15</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; pybosl2.<span class="k">cuboid</span>([30, 20, 15])</div>
        </div>

        <div class="spec-tests">32 tests</div>
      </div>
    </div>

.. raw:: html

    <script type="module">
<script type="module">
import * as THREE from "https://esm.sh/three@0.160.0";
import { STLLoader } from "https://esm.sh/three@0.160.0/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js";
const V = [{"id": "cuboid", "label": "cuboid", "uri": "_stl/shapes3d-cuboid.stl", "code": "pybosl2.<span class=\"k\">cuboid</span>([30, 20, 15])", "part": "cuboid([30, 20, 15])", "tris": 12, "vol": "9,000.0", "bbox": "30\u00d720\u00d715", "wt": true}, {"id": "sphere", "label": "sphere", "uri": "_stl/shapes3d-sphere.stl", "code": "pybosl2.<span class=\"k\">sphere</span>(radius=15)", "part": "sphere(radius=15)", "tris": 896, "vol": "13,880.9", "bbox": "30\u00d730\u00d730", "wt": true}, {"id": "cylinder", "label": "cylinder", "uri": "_stl/shapes3d-cylinder.stl", "code": "pybosl2.<span class=\"k\">cylinder</span>(height=20, radius=8)", "part": "cylinder(height=20, radius=8)", "tris": 100, "vol": "3,982.2", "bbox": "16\u00d716\u00d720", "wt": true}, {"id": "cone", "label": "cone", "uri": "_stl/shapes3d-cone.stl", "code": "pybosl2.<span class=\"k\">cone</span>(height=20, radius1=10, radius2=3, chamfer=1)", "part": "cone(height=20, radius1=10, radius2=3, chamfer=1)", "tris": 360, "vol": "2,902.4", "bbox": "20\u00d720\u00d720", "wt": false}, {"id": "prismoid", "label": "prismoid", "uri": "_stl/shapes3d-prismoid.stl", "code": "pybosl2.<span class=\"k\">prismoid</span>(size1=[20, 20], size2=[10, 10], height=15)", "part": "prismoid(size1=[20, 20], size2=[10, 10], height=15)", "tris": 12, "vol": "3,500.0", "bbox": "20\u00d720\u00d715", "wt": true}, {"id": "torus", "label": "torus", "uri": "_stl/shapes3d-torus.stl", "code": "pybosl2.<span class=\"k\">torus</span>(major_radius=12, minor_radius=4)", "part": "torus(major_radius=12, minor_radius=4)", "tris": 780, "vol": "3,617.5", "bbox": "32\u00d732\u00d78", "wt": true}, {"id": "tube", "label": "tube", "uri": "_stl/shapes3d-tube.stl", "code": "pybosl2.<span class=\"k\">tube</span>(height=20, outer_radius=10, inner_radius=6)", "part": "tube(height=20, outer_radius=10, inner_radius=6)", "tris": 196, "vol": "4,016.4", "bbox": "20\u00d720\u00d720", "wt": true}, {"id": "teardrop", "label": "teardrop", "uri": "_stl/shapes3d-teardrop.stl", "code": "pybosl2.<span class=\"k\">teardrop</span>(height=20, radius=10)", "part": "teardrop(height=20, radius=10)", "tris": 92, "vol": "6,676.4", "bbox": "20\u00d720\u00d724", "wt": true}, {"id": "capsule", "label": "capsule", "uri": "_stl/shapes3d-capsule.stl", "code": "pybosl2.<span class=\"k\">spheroid</span>(radius=12)", "part": "spheroid(radius=12)", "tris": 896, "vol": "7,107.0", "bbox": "24\u00d724\u00d724", "wt": true}, {"id": "rounded-cuboid", "label": "rounded cuboid", "uri": "_stl/shapes3d-rounded-cuboid.stl", "code": "pybosl2.<span class=\"k\">cuboid</span>([30, 20, 15], rounding=4, edges=Anchor.Z, except_edges=TOP+FRONT+RIGHT)", "part": "cuboid([30, 20, 15], rounding=4, edges=Anchor.Z, except_edges=TOP+FRONT+RIGHT)", "tris": 36, "vol": "8,943.7", "bbox": "30\u00d720\u00d715", "wt": true}, {"id": "chamfered-cylinder", "label": "chamfered cyl", "uri": "_stl/shapes3d-chamfered-cylinder.stl", "code": "pybosl2.<span class=\"k\">cylinder</span>(height=20, radius=10, chamfer=2)", "part": "cylinder(height=20, radius=10, chamfer=2)", "tris": 360, "vol": "6,004.5", "bbox": "20\u00d720\u00d720", "wt": false}, {"id": "octahedron", "label": "octahedron", "uri": "_stl/shapes3d-octahedron.stl", "code": "pybosl2.<span class=\"k\">octahedron</span>(20)", "part": "octahedron(20)", "tris": 8, "vol": "1,333.3", "bbox": "20\u00d720\u00d720", "wt": true}];
const box = document.getElementById("viewer"), poster = document.getElementById("poster");
let renderer, scene, camera, controls, mesh, ready = false;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || null;
const primaryColor = css("--model") || "#6f9ac9";
function resize() { const w = box.clientWidth, h = box.clientHeight || 300;
  renderer.setSize(w, h, false); camera.aspect = w / Math.max(1, h); camera.updateProjectionMatrix(); }
function init() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(38, 1, 0.01, 1e6); camera.up.set(0, 0, 1);
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio); box.appendChild(renderer.domElement);
  scene.add(new THREE.AmbientLight(0xffffff, 0.7));
  const k = new THREE.DirectionalLight(0xffffff, 0.85); k.position.set(1, 0.6, 1); scene.add(k);
  const f = new THREE.DirectionalLight(0xffffff, 0.4); f.position.set(-1, -0.8, 0.5); scene.add(f);
  controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true;
  window.addEventListener("resize", resize); ready = true;
  (function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();
}
const loader = new STLLoader();
function load(uri) {
  if (!ready) init();
  loader.load(uri, geo => {
    if (mesh) { scene.remove(mesh); mesh.geometry.dispose(); }
    geo.computeVertexNormals(); geo.computeBoundingBox();
    const c = new THREE.Vector3(); geo.boundingBox.getCenter(c);
    const s = new THREE.Vector3(); geo.boundingBox.getSize(s);
    geo.translate(-c.x, -c.y, -c.z);
    mesh = new THREE.Mesh(geo,
      new THREE.MeshPhongMaterial({ color: primaryColor, specular: 0x222222, shininess: 22 }));
    scene.add(mesh);
    const r = Math.max(s.x, s.y, s.z) || 1;
    camera.position.set(r * 1.4, -r * 1.8, r * 1.15); controls.target.set(0, 0, 0);
    poster.style.display = "none"; box.querySelector(".hint")?.remove(); resize();
  }, undefined, () => {
    if (!box.querySelector(".hint")) { const h = document.createElement("div");
      h.className = "hint";
      h.textContent = "serve the docs over HTTP for the interactive 3-D view";
      box.appendChild(h); }
  });
}
function select(i) {
  const v = V[i];
  document.querySelectorAll(".spec-tags button.spec-tag").forEach((b, j) =>
    b.setAttribute("aria-selected", j === i ? "true" : "false"));
  document.getElementById("code").innerHTML = "&gt;&gt;&gt; " + v.code;
  document.getElementById("s-tris").textContent = v.tris == null ? "\u2014" : v.tris.toLocaleString();
  document.getElementById("s-vol").textContent = v.vol; document.getElementById("s-bbox").textContent = v.bbox;
  document.getElementById("vpart").textContent = v.part;
  document.getElementById("wtpill").style.display = v.wt ? "" : "none";
  load(v.uri);
}
document.querySelectorAll(".tags button.tag").forEach((b, i) => b.addEventListener("click", () => select(i)));
select(0);
</script>
    </script>
    <script>
    function copySpecCode(btn) {var code=btn.nextElementSibling.textContent.trim().replace(/^>>> /,'');
    navigator.clipboard.writeText(code).then(function(){btn.title='Copied!';btn.classList.add('copied');
    setTimeout(function(){btn.title='Copy to clipboard';btn.classList.remove('copied');},1500);});}
    </script>
