:icon: material/wrench-outline

.. _spec-cubetruss:

cubetruss
=========

.. raw:: html

    <p class="spec-lede">Modular cube-truss segments, the trusses tiled from them (with end clips), L/T corners, diagonal supports, and the printed clip family.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">Truss(extents=3).shape()</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Isometric schematic of a 3-segment cube truss." xmlns="http://www.w3.org/2000/svg"><polygon points="120,70 160,93 120,70" fill="none"/><polygon points="120,70 160,93 120,93 80,93" fill="color-mix(in srgb,var(--accent) 16%,var(--panel-2))" stroke="var(--ink-dim)" stroke-width="1.3"/><polygon points="80,93 120,93 120,139 80,139" fill="var(--panel)" stroke="var(--ink-dim)" stroke-width="1.3"/><polygon points="120,93 160,93 160,139 120,139" fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.3"/><polygon points="160,93 199,116 160,93" fill="none"/><polygon points="160,93 199,116 160,116 120,116" fill="color-mix(in srgb,var(--accent) 16%,var(--panel-2))" stroke="var(--ink-dim)" stroke-width="1.3"/><polygon points="120,116 160,116 160,162 120,162" fill="var(--panel)" stroke="var(--ink-dim)" stroke-width="1.3"/><polygon points="160,116 199,116 199,162 160,162" fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.3"/><polygon points="199,116 239,139 199,116" fill="none"/><polygon points="199,116 239,139 199,139 160,139" fill="color-mix(in srgb,var(--accent) 16%,var(--panel-2))" stroke="var(--ink-dim)" stroke-width="1.3"/><polygon points="160,139 199,139 199,185 160,185" fill="var(--panel)" stroke="var(--ink-dim)" stroke-width="1.3"/><polygon points="199,139 239,139 239,185 199,185" fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.3"/><text x="230" y="225" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">3 segments · bracing shown open</text></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>Each 30 mm cube is lightened with octagonal tunnels through all three axes and braced; the assembly is one watertight solid. Length = truss_dist(3,1) = 84 mm.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">3-truss</button> <button class="spec-tag" type="button">segment</button> <button class="spec-tag" type="button">corner</button> <button class="spec-tag" type="button">support</button> <button class="spec-tag" type="button">clip</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">1,456</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">15,456.6</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">30×84×30</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; Truss(extents=3).shape()</div>
        </div>

        <div class="spec-tests">26 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "truss", "label": "3-truss", "uri": "_stl/cubetruss-truss.stl", "code": "Truss(extents=3).shape()", "part": "Truss(extents=3).shape()", "tris": 1456, "vol": "15,456.6", "bbox": "30\u00d784\u00d730", "wt": true}, {"id": "segment", "label": "segment", "uri": "_stl/cubetruss-segment.stl", "code": "TrussSegment().shape()", "part": "TrussSegment().shape()", "tris": 468, "vol": "5,997.9", "bbox": "30\u00d730\u00d730", "wt": true}, {"id": "corner", "label": "corner", "uri": "_stl/cubetruss-corner.stl", "code": "TrussCorner().shape()", "part": "TrussCorner().shape()", "tris": 1992, "vol": "19,910.0", "bbox": "57\u00d757\u00d757", "wt": true}, {"id": "support", "label": "support", "uri": "_stl/cubetruss-support.stl", "code": "TrussSupport(extents=1).shape()", "part": "TrussSupport(extents=1).shape()", "tris": 156, "vol": "3,150.3", "bbox": "30\u00d730\u00d730", "wt": true}, {"id": "clip", "label": "clip", "uri": "_stl/cubetruss-clip.stl", "code": "TrussClip().shape()", "part": "TrussClip().shape()", "tris": 96, "vol": "354.0", "bbox": "33\u00d78\u00d720", "wt": true}]</script>
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
