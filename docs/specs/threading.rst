:icon: material/wrench-outline

.. _spec-threading:

threading
=========

.. raw:: html

    <p class="spec-lede">Screw-thread generators — ISO, ACME, trapezoidal, buttress, and square threads for both rods and nuts, with multi-start and left-handed options.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">threaded_rod(d=20, l=30, pitch=2.5, fa=6, fs=1)</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Threaded rod and nut schematic" xmlns="http://www.w3.org/2000/svg"><rect width="460" height="240" fill="var(--ground)"/><path d="M80,120 L120,60 L140,60 L100,120 M110,150 L160,80 L180,80 L130,150 M190,90 L210,120 M230,30 L250,60 M260,20 L260,50 M280,150 L320,90 L340,90 L300,150" fill="none" stroke="var(--ink-dim)" stroke-width="2" stroke-linecap="round"/></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>Every thread form builds the rod (core + helical thread) as one manifold polyhedron — an angular sweep of the thread profile stacked over every turn — so the result is always watertight. Nuts are a hex/square block with a matching threaded hole cut by a tap.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">ISO rod</button> <button class="spec-tag" type="button">ISO nut</button> <button class="spec-tag" type="button">trapezoidal rod</button> <button class="spec-tag" type="button">ACME rod</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">6,172</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">8,055.3</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">20×20×30</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; Threading.<span class="k">threaded_rod</span>(d=20, l=30, pitch=2.5, fa=6, fs=1)</div>
        </div>

        <div class="spec-tests">25 tests</div>
      </div>
    </div>

.. raw:: html

    <script type="module">
<script type="module">
import * as THREE from "https://esm.sh/three@0.160.0";
import { STLLoader } from "https://esm.sh/three@0.160.0/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js";
const V = [{"id": "iso-rod", "label": "ISO rod", "uri": "_stl/threading-iso-rod.stl", "code": "Threading.<span class=\"k\">threaded_rod</span>(d=20, l=30, pitch=2.5, fa=6, fs=1)", "part": "threaded_rod(d=20, l=30, pitch=2.5, fa=6, fs=1)", "tris": 6172, "vol": "8,055.3", "bbox": "20\u00d720\u00d730", "wt": true}, {"id": "iso-nut", "label": "ISO nut", "uri": "_stl/threading-iso-nut.stl", "code": "Threading.<span class=\"k\">threaded_nut</span>(nutwidth=13, id=8, h=6.8, pitch=1.25)", "part": "threaded_nut(nutwidth=13, id=8, h=6.8, pitch=1.25)", "tris": 796, "vol": "610.8", "bbox": "15\u00d713\u00d77", "wt": true}, {"id": "trapezoidal", "label": "trapezoidal rod", "uri": "_stl/threading-trapezoidal.stl", "code": "Threading.<span class=\"k\">trapezoidal_threaded_rod</span>(d=20, l=30, pitch=4, fa=6, fs=1)", "part": "trapezoidal_threaded_rod(d=20, l=30, pitch=4, fa=6, fs=1)", "tris": 3932, "vol": "7,699.5", "bbox": "20\u00d720\u00d730", "wt": true}, {"id": "acme", "label": "ACME rod", "uri": "_stl/threading-acme.stl", "code": "Threading.<span class=\"k\">acme_threaded_rod</span>(d=12.7, l=30, pitch=2.54, fa=6, fs=1)", "part": "acme_threaded_rod(d=12.7, l=30, pitch=2.54, fa=6, fs=1)", "tris": 3996, "vol": "3,098.2", "bbox": "13\u00d713\u00d730", "wt": true}];
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
