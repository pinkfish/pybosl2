:icon: material/wrench-outline

.. _spec-screw_drive:

screw drive
===========

.. raw:: html

    <p class="spec-lede">Driver-recess masks for Phillips, hex, Torx, and Robertson — subtract from a screw head to make the drive recess, with exact dimensional tables from ISO/ANSI standards.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">phillips_mask(size="#2", l=10)</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Screw drive recess schematic" xmlns="http://www.w3.org/2000/svg"><rect width="460" height="240" fill="var(--ground)"/><path d="M100,100 L120,40 L140,40 L160,100 M130,40 L130,200 M80,160 L180,160 M60,140 L200,140 M70,120 L190,120" fill="none" stroke="var(--ink-dim)" stroke-width="2" stroke-linecap="round"/></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>Every ``*_mask`` is built bottom-on-the-XY-plane. The dimensional helpers — <b>torx_info</b>, <b>phillips_depth</b>, etc. — return the same numbers as BOSL2.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">Phillips #2</button> <button class="spec-tag" type="button">hex 3 mm</button> <button class="spec-tag" type="button">Torx T30</button> <button class="spec-tag" type="button">Robertson #2</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">176</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">29.3</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">6×6×4</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; ScrewDrive.<span class="k">phillips_mask</span>(size="#2", l=10)</div>
        </div>

        <div class="spec-tests">19 tests</div>
      </div>
    </div>

.. raw:: html

    <script type="module">
<script type="module">
import * as THREE from "https://esm.sh/three@0.160.0";
import { STLLoader } from "https://esm.sh/three@0.160.0/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js";
const V = [{"id": "phillips", "label": "Phillips #2", "uri": "_stl/screw_drive-phillips.stl", "code": "ScrewDrive.<span class=\"k\">phillips_mask</span>(size=\"#2\", l=10)", "part": "phillips_mask(size=\"#2\", l=10)", "tris": 176, "vol": "29.3", "bbox": "6\u00d76\u00d74", "wt": true}, {"id": "hex", "label": "hex 3 mm", "uri": "_stl/screw_drive-hex.stl", "code": "ScrewDrive.<span class=\"k\">hex_mask</span>(size=3, l=10)", "part": "hex_mask(size=3, l=10)", "tris": 20, "vol": "80.9", "bbox": "4\u00d73\u00d710", "wt": true}, {"id": "torx", "label": "Torx T30", "uri": "_stl/screw_drive-torx.stl", "code": "ScrewDrive.<span class=\"k\">torx_mask</span>(size=30, l=10)", "part": "torx_mask(size=30, l=10)", "tris": 188, "vol": "176.3", "bbox": "6\u00d75\u00d710", "wt": true}, {"id": "robertson", "label": "Robertson #2", "uri": "_stl/screw_drive-robertson.stl", "code": "ScrewDrive.<span class=\"k\">robertson_mask</span>(size=\"#2\", l=10)", "part": "robertson_mask(size=\"#2\", l=10)", "tris": 74, "vol": "93.4", "bbox": "4\u00d74\u00d710", "wt": true}];
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
