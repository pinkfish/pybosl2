:icon: material/wrench-outline

.. _spec-polyhedra:

polyhedra
=========

.. raw:: html

    <p class="spec-lede">The five Platonic solids as watertight polyhedra — sized by circumradius, diameter, inradius or side. The dodecahedron is built as the dual of the icosahedron.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">tetrahedron(radius=15).shape()</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Isometric projection of a regular icosahedron, faces depth-shaded." xmlns="http://www.w3.org/2000/svg"><polygon points="189.7,92.3 271.5,48.8 272.2,142.6" fill="color-mix(in srgb,var(--accent) 17%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="272.2,142.6 189.7,182.0 189.7,92.3" fill="color-mix(in srgb,var(--accent) 18%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="188.5,30.1 271.5,48.8 189.7,92.3" fill="color-mix(in srgb,var(--accent) 21%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="322.0,111.6 272.2,142.6 271.5,48.8" fill="color-mix(in srgb,var(--accent) 22%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="138.0,112.4 189.7,92.3 189.7,182.0" fill="color-mix(in srgb,var(--accent) 22%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="271.5,193.9 189.7,182.0 272.2,142.6" fill="color-mix(in srgb,var(--accent) 22%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="188.5,30.1 189.7,92.3 138.0,112.4" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="271.5,193.9 272.2,142.6 322.0,111.6" fill="color-mix(in srgb,var(--accent) 25%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="188.5,30.1 270.3,42.0 271.5,48.8" fill="color-mix(in srgb,var(--accent) 28%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="271.5,48.8 270.3,42.0 322.0,111.6" fill="color-mix(in srgb,var(--accent) 28%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="189.7,182.0 188.5,175.2 138.0,112.4" fill="color-mix(in srgb,var(--accent) 29%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="271.5,193.9 188.5,175.2 189.7,182.0" fill="color-mix(in srgb,var(--accent) 29%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="188.5,30.1 138.0,112.4 187.8,81.4" fill="color-mix(in srgb,var(--accent) 32%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="271.5,193.9 322.0,111.6 270.3,131.7" fill="color-mix(in srgb,var(--accent) 33%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="188.5,30.1 187.8,81.4 270.3,42.0" fill="color-mix(in srgb,var(--accent) 35%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="270.3,131.7 322.0,111.6 270.3,42.0" fill="color-mix(in srgb,var(--accent) 35%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="187.8,81.4 138.0,112.4 188.5,175.2" fill="color-mix(in srgb,var(--accent) 35%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="271.5,193.9 270.3,131.7 188.5,175.2" fill="color-mix(in srgb,var(--accent) 36%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="270.3,42.0 187.8,81.4 270.3,131.7" fill="color-mix(in srgb,var(--accent) 39%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><polygon points="188.5,175.2 270.3,131.7 187.8,81.4" fill="color-mix(in srgb,var(--accent) 40%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/><text x="230" y="228" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">icosahedron · 12 v · 30 e · 20 f</text></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>Vertices come from exact &phi;-based coordinates, normalised to a unit circumradius and scaled to the requested size. Every one closes watertight, winding included.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">tetrahedron</button> <button class="spec-tag" type="button">cube</button> <button class="spec-tag" type="button">octahedron</button> <button class="spec-tag" type="button">dodecahedron</button> <button class="spec-tag" type="button">icosahedron</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">4</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">1,732.1</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">17×17×17</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; RegularPolyhedron.tetrahedron(radius=15).shape()</div>
        </div>
        <div class="spec-proof"><div class="spec-proof-big">V&minus;E+F=2</div><div class="spec-proof-txt"><b>Euler's formula holds for all five.</b> The icosahedron's 12 vertices, 30 edges and 20 faces satisfy it — the test suite checks each solid.</div></div>
        <div class="spec-tests">19 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "tetrahedron", "label": "tetrahedron", "uri": "_stl/polyhedra-tetrahedron.stl", "code": "RegularPolyhedron.tetrahedron(radius=15).shape()", "part": "tetrahedron(radius=15).shape()", "tris": 4, "vol": "1,732.1", "bbox": "17\u00d717\u00d717", "wt": true}, {"id": "cube", "label": "cube", "uri": "_stl/polyhedra-cube.stl", "code": "RegularPolyhedron.cube(radius=15).shape()", "part": "cube(radius=15).shape()", "tris": 12, "vol": "5,196.2", "bbox": "17\u00d717\u00d717", "wt": true}, {"id": "octahedron", "label": "octahedron", "uri": "_stl/polyhedra-octahedron.stl", "code": "RegularPolyhedron.octahedron(radius=15).shape()", "part": "octahedron(radius=15).shape()", "tris": 8, "vol": "4,500.0", "bbox": "30\u00d730\u00d730", "wt": true}, {"id": "dodecahedron", "label": "dodecahedron", "uri": "_stl/polyhedra-dodecahedron.stl", "code": "RegularPolyhedron.dodecahedron(side=12).shape()", "part": "dodecahedron(side=12).shape()", "tris": 36, "vol": "13,241.9", "bbox": "31\u00d731\u00d731", "wt": true}, {"id": "icosahedron", "label": "icosahedron", "uri": "_stl/polyhedra-icosahedron.stl", "code": "RegularPolyhedron.icosahedron(radius=15).shape()", "part": "icosahedron(radius=15).shape()", "tris": 20, "vol": "8,559.5", "bbox": "26\u00d726\u00d726", "wt": true}]</script>
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
