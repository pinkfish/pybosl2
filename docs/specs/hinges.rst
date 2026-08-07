:icon: material/wrench-outline

.. _spec-hinges:

hinges
======

.. raw:: html

    <p class="spec-lede">A print-in-place living-hinge mask, an interlocking knuckle hinge with a pin bore, and snap lock / socket connectors.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">KnuckleHingePair(length=40, segs=5).shape()</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Plan view of a five-knuckle butt hinge." xmlns="http://www.w3.org/2000/svg">
    <defs><pattern id="h" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
      <line x1="0" y1="0" x2="0" y2="7" stroke="var(--line)" stroke-width="1.4"/></pattern></defs>
    <rect x="30" y="20" width="400" height="78" rx="4" fill="url(#h)" stroke="var(--ink-dim)" stroke-width="1.5"/>
    <rect x="30" y="142" width="400" height="78" rx="4" fill="none" stroke="var(--ink-dim)" stroke-width="1.5"/>
    <line x1="14" y1="120" x2="446" y2="120" stroke="var(--accent)" stroke-width="1.2" stroke-dasharray="10 4 2 4"/>
    <g stroke="var(--ink)" stroke-width="1.5">
      <rect x="46" y="98" width="70" height="44" rx="10" fill="color-mix(in srgb,var(--accent) 26%,var(--panel))"/>
      <rect x="122" y="98" width="66" height="44" rx="10" fill="var(--panel-2)"/>
      <rect x="196" y="98" width="70" height="44" rx="10" fill="color-mix(in srgb,var(--accent) 26%,var(--panel))"/>
      <rect x="272" y="98" width="66" height="44" rx="10" fill="var(--panel-2)"/>
      <rect x="344" y="98" width="70" height="44" rx="10" fill="color-mix(in srgb,var(--accent) 26%,var(--panel))"/></g>
    <g fill="var(--ground)" stroke="var(--accent)" stroke-width="1.4">
      <circle cx="81" cy="120" r="7"/><circle cx="155" cy="120" r="7"/><circle cx="231" cy="120" r="7"/>
      <circle cx="305" cy="120" r="7"/><circle cx="379" cy="120" r="7"/></g>
    <text x="230" y="232" text-anchor="middle" fill="var(--ink-dim)"
      font-family="var(--mono)" font-size="11">length = 40 mm · segs=5</text>
    </svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill" style="display:none">watertight</span>
        </div>
        <p>Two leaves meshed around one pin, exported as a single mesh. Folding re-triangulates the surface but moves mass rigidly.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">knuckle pair</button> <button class="spec-tag" type="button">single leaf</button> <button class="spec-tag" type="button">snap lock</button> <button class="spec-tag" type="button">snap socket</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">370</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">5,886.5</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">40×46×6</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; KnuckleHingePair(length=40, segs=5).shape()</div>
        </div>
        <div class="spec-proof"><div class="spec-proof-big">0.02%</div><div class="spec-proof-txt"><b>&Delta;volume across the fold = 1.2 mm&sup3;.</b> A rigid rotation, not a distortion — the pin bore and knuckle mesh stay closed.</div></div>
        <div class="spec-tests">6 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "pair", "label": "knuckle pair", "uri": "_stl/hinges-pair.stl", "code": "KnuckleHingePair(length=40, segs=5).shape()", "part": "KnuckleHingePair(length=40, segs=5).shape()", "tris": 370, "vol": "5,886.5", "bbox": "40\u00d746\u00d76", "wt": false}, {"id": "knuckle", "label": "single leaf", "uri": "_stl/hinges-knuckle.stl", "code": "KnuckleHinge(length=40, segs=5).shape()", "part": "KnuckleHinge(length=40, segs=5).shape()", "tris": 212, "vol": "3,102.8", "bbox": "40\u00d726\u00d76", "wt": true}, {"id": "snap-lock", "label": "snap lock", "uri": "_stl/hinges-snap-lock.stl", "code": "SnapLock().shape()", "part": "SnapLock().shape()", "tris": 36, "vol": "181.7", "bbox": "5\u00d75\u00d78", "wt": true}, {"id": "snap-socket", "label": "snap socket", "uri": "_stl/hinges-snap-socket.stl", "code": "SnapSocket().shape()", "part": "SnapSocket().shape()", "tris": 76, "vol": "179.6", "bbox": "5\u00d75\u00d78", "wt": true}]</script>
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
