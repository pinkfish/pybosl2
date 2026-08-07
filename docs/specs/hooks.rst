:icon: material/wrench-outline

.. _spec-hooks:

hooks
=====

.. raw:: html

    <p class="spec-lede">A ring hook: a rectangular mounting base that flares up and joins tangentially to a Y-axis cylinder — the ring — with a round, D-shaped or custom through-hole.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">RingHook([50, 10], 25, outer_radius=25, inner_radius=20).shape()</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Side elevation of a ring hook: a base flaring along the tangent into a holed ring." xmlns="http://www.w3.org/2000/svg"><circle cx="230.0" cy="134.0" r="60.0" fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.8"/><polygon points="194.0,206.0 266.0,206.0 285.8,156.1 174.2,156.1" fill="var(--panel-2)" stroke="none"/><polyline points="174.2,156.1 194.0,206.0 266.0,206.0 285.8,156.1" fill="none" stroke="var(--ink-dim)" stroke-width="1.8"/><circle cx="230.0" cy="134.0" r="40.8" fill="var(--ground)" stroke="var(--accent)" stroke-width="1.6"/><line x1="266.0" y1="206.0" x2="285.8" y2="156.1" stroke="var(--accent)" stroke-width="1" stroke-dasharray="4 4" opacity="0.8"/><line x1="194.0" y1="206.0" x2="174.2" y2="156.1" stroke="var(--accent)" stroke-width="1" stroke-dasharray="4 4" opacity="0.8"/><circle cx="285.8" cy="156.1" r="2.6" fill="var(--accent)"/><circle cx="174.2" cy="156.1" r="2.6" fill="var(--accent)"/><line x1="180.0" y1="206.0" x2="180.0" y2="134.0" stroke="var(--ink-dim)" stroke-width="1"/><text x="174.0" y="173.0" text-anchor="end" fill="var(--ink-dim)" font-family="var(--mono)" font-size="10">hole_z</text><circle cx="230.0" cy="134.0" r="2.2" fill="var(--accent)"/><text x="230.0" y="224.0" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">base flares along the ring tangent</text></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>Give exactly two of <b>or/od</b>, <b>ir/id</b> and <b>wall</b> to size the ring. The base flares to the tangent points computed by <b>circle_point_tangents()</b>, so the paddle meets the cylinder seamlessly. Circle, D and custom-path holes all close watertight.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">ring hole</button> <button class="spec-tag" type="button">solid paddle</button> <button class="spec-tag" type="button">D hole</button> <button class="spec-tag" type="button">rounded</button> <button class="spec-tag" type="button">custom hole</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">208</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">9,771.2</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">50×10×50</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; RingHook([50, 10], 25, outer_radius=25, inner_radius=20).shape()</div>
        </div>
        <div class="spec-proof"><div class="spec-proof-big">tangent join</div><div class="spec-proof-txt"><b>The base corners must lie outside the ring</b> so a tangent exists; the flare follows it exactly. Verified watertight for round, D and octagonal holes.</div></div>
        <div class="spec-tests">14 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "ring", "label": "ring hole", "uri": "_stl/hooks-ring.stl", "code": "RingHook([50, 10], 25, outer_radius=25, inner_radius=20).shape()", "part": "RingHook([50, 10], 25, outer_radius=25, inner_radius=20).shape()", "tris": 208, "vol": "9,771.2", "bbox": "50\u00d710\u00d750", "wt": true}, {"id": "solid", "label": "solid paddle", "uri": "_stl/hooks-solid.stl", "code": "RingHook([70, 10], 25, outer_radius=25, inner_radius=0).shape()", "part": "RingHook([70, 10], 25, outer_radius=25, inner_radius=0).shape()", "tris": 124, "vol": "25,197.0", "bbox": "70\u00d710\u00d750", "wt": true}, {"id": "d-hole", "label": "D hole", "uri": "_stl/hooks-d-hole.stl", "code": "RingHook([50, 10], 25, outer_radius=25, inner_radius=15, hole=HoleType.D).shape()", "part": "RingHook([50, 10], 25, outer_radius=25, inner_radius=15, hole=HoleType.D).shape()", "tris": 144, "vol": "18,737.4", "bbox": "50\u00d710\u00d750", "wt": true}, {"id": "rounded", "label": "rounded", "uri": "_stl/hooks-rounded.stl", "code": "RingHook([50, 10], 40, outer_radius=25, inner_radius=15, rounding=5).shape()", "part": "RingHook([50, 10], 40, outer_radius=25, inner_radius=15, rounding=5).shape()", "tris": 312, "vol": "21,937.7", "bbox": "50\u00d710\u00d765", "wt": true}, {"id": "custom", "label": "custom hole", "uri": "_stl/hooks-custom.stl", "code": "RingHook([50, 20], 30, outer_radius=25, hole=[[10*math.cos(math.radians(22.5+45*k)),10*math.sin(math.radians(22.5+45*k))] for k in range(8)]).shape()", "part": "RingHook([50, 20], 30, outer_radius=25, hole=[[10*math.cos(math.radians(22.5+45*k)),10*math.sin(math.radians(22.5+45*k))] for k in range(8)]).shape()", "tris": 120, "vol": "43,834.9", "bbox": "50\u00d720\u00d755", "wt": true}]</script>
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
        // updateStyle must stay on: setPixelRatio() scales the drawing buffer, and without the
        // matching CSS size the canvas lays out devicePixelRatio times too large and the .spec-viewer
        // box (overflow:hidden) shows only its top-left corner.
        renderer.setSize(w, Math.max(1, h));
        camera.aspect = w / Math.max(1, h);
        camera.updateProjectionMatrix();
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
