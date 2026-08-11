:icon: material/wrench-outline

.. _spec-wiring:

wiring
======

.. raw:: html

    <p class="spec-lede">A routed bundle of round wires: hex-packed in cross-section and swept along a path whose corners are rounded, each wire coloured from a 17-entry table.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">WireBundle(PATH, wires=13, rounding=10).shape()</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Cross-section of a 13-wire bundle, hex-packed and colour-coded." xmlns="https://www.w3.org/2000/svg"><circle cx="230.0" cy="116.0" r="14.1" fill="#333333" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="245.0" cy="142.0" r="14.1" fill="#ff3333" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="215.0" cy="142.0" r="14.1" fill="#00cc00" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="200.0" cy="116.0" r="14.1" fill="#ffff33" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="215.0" cy="90.0" r="14.1" fill="#4c4cff" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="245.0" cy="90.0" r="14.1" fill="#ffffff" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="260.0" cy="116.0" r="14.1" fill="#b27f00" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="275.0" cy="142.0" r="14.1" fill="#7f7f7f" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="260.0" cy="168.0" r="14.1" fill="#33e5e5" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="230.0" cy="168.0" r="14.1" fill="#cc00cc" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="200.0" cy="168.0" r="14.1" fill="#009999" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="185.0" cy="142.0" r="14.1" fill="#ffb2b2" stroke="var(--ink-dim)" stroke-width="1.1"/><circle cx="170.0" cy="116.0" r="14.1" fill="#ff7fff" stroke="var(--ink-dim)" stroke-width="1.1"/><text x="230" y="224" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">13 wires · hex-packed · 17-colour table</text></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill" style="display:none">watertight</span>
        </div>
        <p>The wires pack into the optimal hex arrangement (rings of 1, 6, 12, …) and each sweeps along the rounded route as its own tube — kept separate and coloured, exactly as BOSL2 draws them.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">13 wires</button> <button class="spec-tag" type="button">7 wires</button> <button class="spec-tag" type="button">1 wire</button> <button class="spec-tag" type="button">thick gauge</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">10,348</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">6,974.3</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">60×59×54</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; WireBundle(PATH, wires=13, rounding=10).shape()</div>
        </div>
        <div class="spec-proof"><div class="spec-proof-big">529.0 mm³ ×13</div><div class="spec-proof-txt"><b>One wire seals watertight at 796 triangles.</b> Thirteen of them, hex-packed and tangent, are 13 independent tubes — 13 × 529.0 = 6,877 mm&sup3; of copper, no overlap.</div></div>
        <div class="spec-tests">11 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "13", "label": "13 wires", "uri": "_stl/wiring-13.stl", "code": "WireBundle(PATH, wires=13, rounding=10).shape()", "part": "WireBundle(PATH, wires=13, rounding=10).shape()", "tris": 10348, "vol": "6,974.3", "bbox": "60\u00d759\u00d754", "wt": false}, {"id": "7", "label": "7 wires", "uri": "_stl/wiring-7.stl", "code": "WireBundle(PATH, wires=7, rounding=10).shape()", "part": "WireBundle(PATH, wires=7, rounding=10).shape()", "tris": 5572, "vol": "3,703.2", "bbox": "56\u00d756\u00d753", "wt": false}, {"id": "1", "label": "1 wire", "uri": "_stl/wiring-1.stl", "code": "WireBundle(PATH, wires=1, rounding=10).shape()", "part": "WireBundle(PATH, wires=1, rounding=10).shape()", "tris": 796, "vol": "529.0", "bbox": "52\u00d752\u00d751", "wt": true}, {"id": "thick", "label": "thick gauge", "uri": "_stl/wiring-thick.stl", "code": "WireBundle(PATH, wires=7, wirediam=3, rounding=15).shape()", "part": "WireBundle(PATH, wires=7, wirediam=3, rounding=15).shape()", "tris": 5572, "vol": "8,043.4", "bbox": "59\u00d759\u00d754", "wt": false}]</script>
    <script type="module">
    import * as THREE from "https://unpkg.com/three@0.160.0/build/three.module.js";
    import { STLLoader } from "https://unpkg.com/three@0.160.0/examples/jsm/loaders/STLLoader.js";
    import { OrbitControls } from "https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js";

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
        const w = box.clientWidth, h = Math.max(300, box.clientHeight);
        renderer.setSize(w, Math.max(1, h));
        camera.aspect = w / Math.max(1, h);
        camera.updateProjectionMatrix();
        controls.update();
      }

      function initThree() {
        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
        camera.up.set(0, 0, 1);
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
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
          // Depth range tied to the model: a fixed 0.01/1e6 span leaves so little depth precision
          // that big parts z-fight and shimmer while orbiting.
          camera.near = r / 100;
          camera.far = r * 100;
          camera.updateProjectionMatrix();
          controls.target.set(0, 0, 0);
          controls.update();
          camera.position.set(r * 1.4, -r * 1.8, r * 1.15);
          camera.lookAt(0, 0, 0);
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
            h.textContent = "Could not load STL — file may be missing";
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
        b.addEventListener("click", (e) => { e.preventDefault(); selectVariant(i); });
      });
      selectVariant(0);
    })();
    </script>
    <script>
    function copySpecCode(btn) {var code=btn.nextElementSibling.textContent.trim().replace(/^>>> /,'');
    navigator.clipboard.writeText(code).then(function(){btn.title='Copied!';btn.classList.add('copied');
    setTimeout(function(){btn.title='Copy to clipboard';btn.classList.remove('copied');},1500);});}
    </script>
