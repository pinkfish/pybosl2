:icon: material/wrench-outline

.. _spec-ball_bearings:

ball bearings
=============

.. raw:: html

    <p class="spec-lede">Standard cartridge models from a trade-size name — shielded (ZZ) or open, with the balls modelled rolling in the race.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">ball_bearing("608")</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Schematic of an open ball bearing with 9 balls in the race." xmlns="http://www.w3.org/2000/svg"><circle cx="230" cy="118" r="96" fill="none" stroke="var(--ink-dim)" stroke-width="1.8"/><circle cx="230" cy="118" r="88" fill="none" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="230" cy="118" r="40" fill="var(--ground)" stroke="var(--ink-dim)" stroke-width="1.8"/><circle cx="230" cy="118" r="48" fill="none" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="230" cy="118" r="66" fill="none" stroke="var(--accent)" stroke-width="1" stroke-dasharray="5 5"/><circle cx="296.0" cy="118.0" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="280.6" cy="160.4" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="241.5" cy="183.0" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="197.0" cy="175.2" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="168.0" cy="140.6" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="168.0" cy="95.4" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="197.0" cy="60.8" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="241.5" cy="53.0" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="280.6" cy="75.6" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><text x="230" y="234" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">9 balls · pitch &Oslash;</text></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>The open 608 skate bearing: inner and outer races, a toroidal ball groove, and 9 balls spaced around it — one watertight assembly. 136 trade sizes are tabulated.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">608</button> <button class="spec-tag" type="button">6902ZZ</button> <button class="spec-tag" type="button">R8</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">2,328</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">1,640.6</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">22×22×7</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; BallBearings.<span class="k">ball_bearing</span>("608")</div>
        </div>

        <div class="spec-tests">10 tests</div>
      </div>
    </div>

.. raw:: html

    <script type="module">
<script type="module">
import * as THREE from "https://esm.sh/three@0.160.0";
import { STLLoader } from "https://esm.sh/three@0.160.0/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js";
const V = [{"id": "608", "label": "608", "uri": "_stl/ball_bearings-608.stl", "code": "BallBearings.<span class=\"k\">ball_bearing</span>(\"608\")", "part": "ball_bearing(\"608\")", "tris": 2328, "vol": "1,640.6", "bbox": "22\u00d722\u00d77", "wt": true}, {"id": "6902zz", "label": "6902ZZ", "uri": "_stl/ball_bearings-6902zz.stl", "code": "BallBearings.<span class=\"k\">ball_bearing</span>(\"6902ZZ\")", "part": "ball_bearing(\"6902ZZ\")", "tris": 696, "vol": "2,862.2", "bbox": "28\u00d728\u00d77", "wt": true}, {"id": "r8", "label": "R8", "uri": "_stl/ball_bearings-r8.stl", "code": "BallBearings.<span class=\"k\">ball_bearing</span>(\"R8\")", "part": "ball_bearing(\"R8\")", "tris": 2978, "vol": "2,400.7", "bbox": "29\u00d728\u00d76", "wt": false}];
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
