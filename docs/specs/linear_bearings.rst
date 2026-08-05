:icon: material/wrench-outline

.. _spec-linear_bearings:

linear bearings
===============

.. raw:: html

    <p class="spec-lede">LMxUU linear ball bearings that run along a rod, plus the pillow-block housings that clamp them to a plate with a teardrop bore and a screw.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">lmXuu_bearing(8)</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Longitudinal cutaway of a linear ball bearing running on a rod." xmlns="http://www.w3.org/2000/svg"><rect x="80.0" y="60.0" width="300" height="116" rx="8" fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.8"/><rect x="66.0" y="87.0" width="328" height="62" fill="var(--ground)" stroke="var(--ink-dim)" stroke-width="1.4"/><line x1="54.0" y1="118" x2="406.0" y2="118" stroke="var(--accent)" stroke-width="1.2" stroke-dasharray="10 4 2 4"/><circle cx="101.4" cy="73.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="101.4" cy="162.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="144.3" cy="73.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="144.3" cy="162.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="187.1" cy="73.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="187.1" cy="162.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="230.0" cy="73.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="230.0" cy="162.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="272.9" cy="73.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="272.9" cy="162.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="315.7" cy="73.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="315.7" cy="162.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="358.6" cy="73.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="358.6" cy="162.5" r="7.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/><text x="230" y="198.0" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">shell &amp; ball tracks · runs on a rod</text></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>The bearing is four nested shells modelling the outer race, liner and ball tracks; the housing prints without support thanks to its teardrop bore. 17 LMxUU sizes are tabulated.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">LM8UU</button> <button class="spec-tag" type="button">LM8UU housing</button> <button class="spec-tag" type="button">LM12UU</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">816</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">2,997.1</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">15×15×24</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; LinearBearings.lmXuu_bearing(8)</div>
        </div>

        <div class="spec-tests">10 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "lm8uu", "label": "LM8UU", "uri": "_stl/linear_bearings-lm8uu.stl", "code": "LinearBearings.lmXuu_bearing(8)", "part": "lmXuu_bearing(8)", "tris": 816, "vol": "2,997.1", "bbox": "15\u00d715\u00d724", "wt": true}, {"id": "housing", "label": "LM8UU housing", "uri": "_stl/linear_bearings-housing.stl", "code": "LinearBearings.lmXuu_housing(8)", "part": "lmXuu_housing(8)", "tris": 508, "vol": "6,499.2", "bbox": "27\u00d724\u00d724", "wt": true}, {"id": "lm12uu", "label": "LM12UU", "uri": "_stl/linear_bearings-lm12uu.stl", "code": "LinearBearings.lmXuu_bearing(12)", "part": "lmXuu_bearing(12)", "tris": 1088, "vol": "6,932.1", "bbox": "21\u00d721\u00d730", "wt": true}]</script>
    <script type="module">
    import * as THREE from "https://esm.sh/three@0.160.0";
    import { STLLoader } from "https://esm.sh/three@0.160.0/examples/jsm/loaders/STLLoader.js";
    import { OrbitControls } from "https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js";

    (function() {
      const dataEl = document.getElementById("spec-data");
      if (!dataEl) return;
      const V = JSON.parse(dataEl.textContent);
      const box = document.getElementById("viewer");
      const poster = document.getElementById("poster");
      if (!box) return;

      let renderer, scene, camera, controls, mesh, ready = false;
      const css = (n) => (getComputedStyle(document.documentElement).getPropertyValue(n) || "").trim() || null;
      const primaryColor = css("--md-accent-fg-color") || "#6f9ac9";

      function resize() {
        const w = box.clientWidth, h = box.clientHeight || 300;
        renderer.setSize(w, h, false);
        camera.aspect = w / Math.max(1, h);
        camera.updateProjectionMatrix();
      }

      function initThree() {
        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(38, 1, 0.01, 1e6);
        camera.up.set(0, 0, 1);
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(window.devicePixelRatio);
        box.appendChild(renderer.domElement);
        scene.add(new THREE.AmbientLight(0xffffff, 0.7));
        const k = new THREE.DirectionalLight(0xffffff, 0.85);
        k.position.set(1, 0.6, 1);
        scene.add(k);
        const f = new THREE.DirectionalLight(0xffffff, 0.4);
        f.position.set(-1, -0.8, 0.5);
        scene.add(f);
        controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        window.addEventListener("resize", resize);
        ready = true;
        (function loop() {
          requestAnimationFrame(loop);
          controls.update();
          renderer.render(scene, camera);
        })();
      }

      const loader = new STLLoader();
      function loadStl(uri) {
        if (!ready) initThree();
        loader.load(uri, function(geo) {
          if (mesh) { scene.remove(mesh); mesh.geometry.dispose(); }
          geo.computeVertexNormals();
          geo.computeBoundingBox();
          const c = new THREE.Vector3();
          geo.boundingBox.getCenter(c);
          const s = new THREE.Vector3();
          geo.boundingBox.getSize(s);
          geo.translate(-c.x, -c.y, -c.z);
          mesh = new THREE.Mesh(geo,
            new THREE.MeshPhongMaterial({ color: primaryColor, specular: 0x222222, shininess: 22 }));
          scene.add(mesh);
          const r = Math.max(s.x, s.y, s.z) || 1;
          camera.position.set(r * 1.4, -r * 1.8, r * 1.15);
          controls.target.set(0, 0, 0);
          if (poster) poster.style.display = "none";
          const hint = box.querySelector(".hint");
          if (hint) hint.remove();
          resize();
        }, undefined, function() {
          if (!box.querySelector(".hint")) {
            const h = document.createElement("div");
            h.className = "hint";
            h.style.cssText = (
              "position:absolute;inset:0;display:flex;align-items:center;"
              + "justify-content:center;padding:1em;color:#a00;"
              + "background:rgba(255,255,255,0.8);font-size:0.85em;"
            );
            h.textContent = "serve the docs over HTTP for the interactive 3-D view";
            box.appendChild(h);
          }
        });
      }

      function selectVariant(i) {
        const v = V[i];
        const buttons = document.querySelectorAll(".spec-tags button.spec-tag");
        buttons.forEach((b, j) => {
          b.setAttribute("aria-selected", j === i ? "true" : "false");
          b.classList.toggle("active", j === i);
        });
        document.getElementById("code").textContent = ">>> " + v.code;
        document.getElementById("s-tris").textContent = v.tris == null ? "—" : v.tris.toLocaleString();
        document.getElementById("s-vol").textContent = v.vol;
        document.getElementById("s-bbox").textContent = v.bbox;
        document.getElementById("vpart").textContent = v.part;
        document.getElementById("wtpill").style.display = v.wt ? "" : "none";
        loadStl(v.uri);
      }

      const buttons = document.querySelectorAll(".spec-tags button.spec-tag");
      buttons.forEach((b, i) => {
        b.addEventListener("click", () => { selectVariant(i); });
      });
      selectVariant(0);
    })();
    </script>
    <script>
    function copySpecCode(btn) {var code=btn.nextElementSibling.textContent.trim().replace(/^>>> /,'');
    navigator.clipboard.writeText(code).then(function(){btn.title='Copied!';btn.classList.add('copied');
    setTimeout(function(){btn.title='Copy to clipboard';btn.classList.remove('copied');},1500);});}
    </script>
