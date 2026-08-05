(function() {
  var dataEl = document.getElementById("spec-data");
  if (!dataEl) return;
  var V = JSON.parse(dataEl.textContent);
  var box = document.getElementById("viewer");
  var poster = document.getElementById("poster");
  if (!box) return;

  var renderer, scene, camera, controls, mesh, ready = false;
  var css = function(n) {
    return (getComputedStyle(document.documentElement).getPropertyValue(n) || "").trim() || null;
  };
  var primaryColor = css("--model") || "#6f9ac9";

  function resize() {
    var w = box.clientWidth, h = box.clientHeight || 300;
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
    var k = new THREE.DirectionalLight(0xffffff, 0.85);
    k.position.set(1, 0.6, 1);
    scene.add(k);
    var f = new THREE.DirectionalLight(0xffffff, 0.4);
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

  var loader = new STLLoader();
  function loadStl(uri) {
    if (!ready) initThree();
    loader.load(uri, function(geo) {
      if (mesh) { scene.remove(mesh); mesh.geometry.dispose(); }
      geo.computeVertexNormals();
      geo.computeBoundingBox();
      var c = new THREE.Vector3();
      geo.boundingBox.getCenter(c);
      var s = new THREE.Vector3();
      geo.boundingBox.getSize(s);
      geo.translate(-c.x, -c.y, -c.z);
      mesh = new THREE.Mesh(geo,
        new THREE.MeshPhongMaterial({ color: primaryColor, specular: 0x222222, shininess: 22 }));
      scene.add(mesh);
      var r = Math.max(s.x, s.y, s.z) || 1;
      camera.position.set(r * 1.4, -r * 1.8, r * 1.15);
      controls.target.set(0, 0, 0);
      if (poster) poster.style.display = "none";
      var hint = box.querySelector(".hint");
      if (hint) hint.remove();
      resize();
    }, undefined, function() {
      if (!box.querySelector(".hint")) {
        var h = document.createElement("div");
        h.className = "hint";
        h.textContent = "serve the docs over HTTP for the interactive 3-D view";
        box.appendChild(h);
      }
    });
  }

  function selectVariant(i) {
    var v = V[i];
    var buttons = document.querySelectorAll(".spec-tags button.spec-tag");
    buttons.forEach(function(b, j) {
      b.setAttribute("aria-selected", j === i ? "true" : "false");
    });
    document.getElementById("code").innerHTML = "&gt;&gt;&gt; " + v.code;
    document.getElementById("s-tris").textContent = v.tris == null ? "\u2014" : v.tris.toLocaleString();
    document.getElementById("s-vol").textContent = v.vol;
    document.getElementById("s-bbox").textContent = v.bbox;
    document.getElementById("vpart").textContent = v.part;
    document.getElementById("wtpill").style.display = v.wt ? "" : "none";
    loadStl(v.uri);
  }

  var buttons = document.querySelectorAll(".spec-tags button.spec-tag");
  buttons.forEach(function(b, i) {
    b.addEventListener("click", function() { selectVariant(i); });
  });
  selectVariant(0);
})();
