:icon: material/wrench-outline

.. _spec-bottlecaps:

bottlecaps
==========

.. raw:: html

    <p class="spec-lede">Standard soda-bottle necks and caps — PCO 1810 and 1881 thread finishes — a threaded neck to graft onto a bottle body and its matching cap.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">pco1810_neck(fa=6)</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Bottle neck and cap schematic" xmlns="http://www.w3.org/2000/svg"><rect width="460" height="240" fill="var(--ground)"/><path d="M120,50 L120,190 M140,50 L140,190 M160,50 L160,190 M100,80 L180,80 M100,160 L180,160 M115,80 Q115,30 140,20 Q165,30 165,80" fill="none" stroke="var(--ink-dim)" stroke-width="2" stroke-linecap="round"/></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>The neck profile (inner bore, support ring, tamper-ring channel and sealing lip) is a turtle path revolved with <b>rotate_extrude</b>. Threads are <b>thread_helix</b> ridges with the two thread breaks cut by prismoids.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">PCO 1810 neck</button> <button class="spec-tag" type="button">PCO 1810 cap</button> <button class="spec-tag" type="button">PCO 1881 neck</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">4,130</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">4,358.5</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">33×33×26</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; BottleCaps.<span class="k">pco1810_neck</span>(fa=6)</div>
        </div>

        <div class="spec-tests">7 tests</div>
      </div>
    </div>

.. raw:: html

    <script type="module">
<script type="module">
import * as THREE from "https://esm.sh/three@0.160.0";
import { STLLoader } from "https://esm.sh/three@0.160.0/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js";
const V = [{"id": "pco1810-neck", "label": "PCO 1810 neck", "uri": "_stl/bottlecaps-pco1810-neck.stl", "code": "BottleCaps.<span class=\"k\">pco1810_neck</span>(fa=6)", "part": "pco1810_neck(fa=6)", "tris": 4130, "vol": "4,358.5", "bbox": "33\u00d733\u00d726", "wt": true}, {"id": "pco1810-cap", "label": "PCO 1810 cap", "uri": "_stl/bottlecaps-pco1810-cap.stl", "code": "BottleCaps.<span class=\"k\">pco1810_cap</span>(fa=6)", "part": "pco1810_cap(fa=6)", "tris": 932, "vol": "3,952.8", "bbox": "33\u00d733\u00d716", "wt": true}, {"id": "pco1881-neck", "label": "PCO 1881 neck", "uri": "_stl/bottlecaps-pco1881-neck.stl", "code": "BottleCaps.<span class=\"k\">pco1881_neck</span>(fa=6)", "part": "pco1881_neck(fa=6)", "tris": 3806, "vol": "3,258.7", "bbox": "33\u00d733\u00d722", "wt": true}];
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
