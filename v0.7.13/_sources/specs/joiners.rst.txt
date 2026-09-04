:icon: material/wrench-outline

.. _spec-joiners:

joiners
=======

.. raw:: html

    <p class="spec-lede">Shapes that connect two separately-printed parts: a tapered-or-straight dovetail joint — male tenon or female socket — and a press-and-click snap pin.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">Dovetail(Gender.MALE, width=15, height=8, slide=30).shape</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Section of a dovetail joint: a flared male tenon seated in a female socket." xmlns="http://www.w3.org/2000/svg"><path d="M 46,52 H 414 V 210 H 46 Z M 136,60 L 324,60 L 295,174 L 165,174 Z" fill="url(#h)" fill-rule="evenodd" stroke="var(--ink-dim)" stroke-width="1.5"/><defs><pattern id="h" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse"><line x1="0" y1="0" x2="0" y2="7" stroke="var(--line)" stroke-width="1.4"/></pattern></defs><path d="M 171,168 L 289,168 L 318,66 L 142,66 Z" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink)" stroke-width="1.6"/><line x1="289" y1="168" x2="318" y2="66" stroke="var(--accent)" stroke-width="1.4"/><text x="230" y="198" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">male tenon · female socket · slope 1:6</text></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>The dovetail flares to <span class="mono">w + 2·h/slope</span> at the top so it resists pulling apart; a taper lets a long joint slide home and wedge tight. The female is the same shape grown by <b>slop</b> for a press fit.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">male dovetail</button> <button class="spec-tag" type="button">female socket</button> <button class="spec-tag" type="button">tapered</button> <button class="spec-tag" type="button">snap pin</button> <button class="spec-tag" type="button">pin socket</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">12</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">3,920.0</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">18×30×8</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; Dovetail(Gender.MALE, width=15, height=8, slide=30).shape</div>
        </div>

        <div class="spec-tests">8 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "male", "label": "male dovetail", "uri": "_stl/joiners-male.stl", "code": "Dovetail(Gender.MALE, width=15, height=8, slide=30).shape", "part": "Dovetail(Gender.MALE, width=15, height=8, slide=30).shape", "tris": 12, "vol": "3,920.0", "bbox": "18\u00d730\u00d78", "wt": true}, {"id": "female", "label": "female socket", "uri": "_stl/joiners-female.stl", "code": "Dovetail(Gender.FEMALE, width=15, height=8, slide=30).shape", "part": "Dovetail(Gender.FEMALE, width=15, height=8, slide=30).shape", "tris": 12, "vol": "3,920.0", "bbox": "18\u00d730\u00d78", "wt": true}, {"id": "taper", "label": "tapered", "uri": "_stl/joiners-taper.stl", "code": "Dovetail(Gender.MALE, width=15, height=8, slide=30, taper=4).shape", "part": "Dovetail(Gender.MALE, width=15, height=8, slide=30, taper=4).shape", "tris": 20, "vol": "3,419.1", "bbox": "18\u00d730\u00d78", "wt": true}, {"id": "snap-pin", "label": "snap pin", "uri": "_stl/joiners-snap-pin.stl", "code": "SnapPin().shape", "part": "SnapPin().shape", "tris": 228, "vol": "173.5", "bbox": "6\u00d76\u00d714", "wt": true}, {"id": "socket", "label": "pin socket", "uri": "_stl/joiners-socket.stl", "code": "SnapPinSocket().shape", "part": "SnapPinSocket().shape", "tris": 112, "vol": "301.2", "bbox": "6\u00d77\u00d713", "wt": true}]</script>
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
          camera.position.set(r * 1.4, -r * 1.8, r * 1.15);
          // Depth range tied to the model: a fixed 0.01/1e6 span leaves so little depth precision
          // that big parts z-fight and shimmer while orbiting.
          camera.near = r / 100;
          camera.far = r * 100;
          camera.updateProjectionMatrix();
          controls.target.set(0, 0, 0);
          controls.update();
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
