// Copyright (c) 2026, pinkfish
//
// Licensed under the BSD 2-Clause License. See the LICENSE file in the project
// root for the full license text.
// SPDX-License-Identifier: BSD-2-Clause
//
// Runtime for the ``.. stl::`` / ``.. pythonscad-example::`` viewers (see docs/_ext/stl_viewer.py).
//
// A single API page carries dozens of examples (paths.html has 36). Giving each one its own
// WebGLRenderer blows past the browser's live-WebGL-context cap (~8-16), at which point the oldest
// contexts are force-lost and their canvases go blank -- the "flashing" this module exists to fix.
//
// So: ONE WebGL context for the whole page, rendered off-screen and blitted into a plain 2-D canvas
// per viewer (the three.js "multiple elements" pattern). On top of that, meshes load only when their
// viewer nears the viewport, and a viewer redraws only when something actually changed, instead of
// every viewer spinning its own 60 fps loop forever.

import * as THREE from "https://esm.sh/three@0.160.0";
import { STLLoader } from "https://esm.sh/three@0.160.0/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js";

const MAX_DPR = 2; // rendering a 3x retina buffer costs 2.25x the pixels for no visible gain
const VIEW_DIR = new THREE.Vector3(0.8, -1.1, 0.7).normalize();

const viewers = [];
const loader = new STLLoader();
let renderer = null;
let rendererFailed = false;
let looping = false;

// --------------------------------------------------------------------------
// the one shared WebGL context
// --------------------------------------------------------------------------

function getRenderer() {
  if (renderer || rendererFailed) return renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.domElement.style.cssText = "position:fixed;width:1px;height:1px;top:-9999px;pointer-events:none";
    document.body.appendChild(renderer.domElement);
    renderer.setPixelRatio(1); // viewers size themselves in device pixels already
    renderer.setScissorTest(true);
    renderer.domElement.addEventListener("webglcontextlost", (e) => {
      e.preventDefault(); // lets the browser restore this context instead of dropping it
    });
    renderer.domElement.addEventListener("webglcontextrestored", () => {
      for (const v of viewers) v.dirty = true;
    });
  } catch {
    rendererFailed = true;
    looping = false; // stop the render loop – WebGL is unavailable
    for (const v of viewers) v.fail("WebGL is unavailable — check chrome://settings/system");
  }
  return renderer;
}

function blit(v) {
  const r = getRenderer();
  if (!r) return;
  const w = v.canvas.width;
  const h = v.canvas.height;
  const rc = r.domElement;
  if (rc.width < w || rc.height < h) {
    r.setSize(Math.max(rc.width, w), Math.max(rc.height, h), false);
  }
  r.setViewport(0, 0, w, h);
  r.setScissor(0, 0, w, h);
  r.render(v.scene, v.camera);
  // WebGL renders with y=0 at the bottom, but 2-D canvas readImage uses y=0 at the top.
  // The renderer's viewport is at the bottom-left, so the rendered region is at y-offset
  // rc.height - h in the shared buffer regardless of whether rc.height equals h.
  const srcY = Math.max(0, rc.height - h);
  v.ctx.globalCompositeOperation = "copy";
  v.ctx.drawImage(rc, 0, srcY, w, h, 0, 0, w, h);
}

function tick() {
  requestAnimationFrame(tick);
  for (const v of viewers) {
    if (!v.visible || !v.mesh) continue;
    if (v.controls.update()) v.dirty = true; // damping is still easing the camera
    if (!v.dirty) continue;
    v.dirty = false;
    blit(v);
  }
}

// --------------------------------------------------------------------------
// per-element viewer
// --------------------------------------------------------------------------

class Viewer {
  constructor(el) {
    this.el = el;
    this.uri = el.dataset.stlUri;
    this.color = el.dataset.stlColor || "#6f9ac9";
    this.status = el.querySelector(".stl-viewer-status");
    this.mesh = null;
    this.corners = [];
    this.visible = false;
    this.requested = false;
    this.dirty = false;

    this.canvas = document.createElement("canvas");
    this.canvas.style.width = "100%";
    this.canvas.style.height = "100%";
    this.ctx = this.canvas.getContext("2d");
    el.appendChild(this.canvas);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
    this.camera.up.set(0, 0, 1); // Z-up, matching OpenSCAD/pybosl2 coordinates

    this.scene.add(new THREE.AmbientLight(0xffffff, 0.65));
    const key = new THREE.DirectionalLight(0xffffff, 0.85);
    key.position.set(1, 0.6, 1);
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.4);
    fill.position.set(-1, -0.8, 0.5);
    this.scene.add(fill);

    this.controls = new OrbitControls(this.camera, this.canvas);
    this.controls.enableDamping = true;
    this.controls.addEventListener("change", () => {
      this.dirty = true;
    });

    this.syncSize();
  }

  /** Match the drawing buffer to the element's device-pixel size. */
  syncSize() {
    const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    const w = Math.max(1, Math.round(this.el.clientWidth * dpr));
    const h = Math.max(1, Math.round(this.el.clientHeight * dpr));
    if (this.canvas.width === w && this.canvas.height === h) return;
    this.canvas.width = w;
    this.canvas.height = h;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.dirty = true;
  }

  /** Place the camera so the whole mesh fits, whatever the element's aspect ratio. */
  frame() {
    // Fit the bounding box's corners rather than its bounding sphere: most examples are flat or
    // elongated, and sphere-fitting them (radius = half the diagonal) leaves the part tiny.
    const forward = VIEW_DIR; // unit vector pointing from the target back towards the camera
    const right = new THREE.Vector3().crossVectors(this.camera.up, forward).normalize();
    const up = new THREE.Vector3().crossVectors(forward, right).normalize();
    const tanV = Math.tan(((this.camera.fov * Math.PI) / 180) / 2);
    const tanH = tanV * this.camera.aspect;

    let dist = 1e-3;
    for (const c of this.corners) {
      const depth = c.dot(forward); // how far the corner already sits towards the camera
      dist = Math.max(dist, depth + Math.abs(c.dot(right)) / tanH, depth + Math.abs(c.dot(up)) / tanV);
    }
    dist *= 1.08; // a little air around the part

    this.camera.position.copy(forward).multiplyScalar(dist);
    // Depth range scaled to the model: the old fixed 0.01/1e6 span left so little depth precision
    // that large meshes z-fought and shimmered while orbiting.
    this.camera.near = dist / 100;
    this.camera.far = dist * 10;
    this.camera.updateProjectionMatrix();
    this.controls.target.set(0, 0, 0);
    this.controls.update();
    this.dirty = true;
  }

  load() {
    if (this.requested || !this.uri) return;
    this.requested = true;
    loader.load(
      this.uri,
      (geo) => this.onGeometry(geo),
      undefined,
      () => this.fail("Could not load STL (serve the docs over HTTP to view)."),
    );
  }

  onGeometry(geo) {
    geo.computeVertexNormals();
    geo.computeBoundingBox();
    const center = new THREE.Vector3();
    geo.boundingBox.getCenter(center);
    geo.translate(-center.x, -center.y, -center.z);
    geo.computeBoundingBox();
    const b = geo.boundingBox;
    this.corners = [];
    for (const x of [b.min.x, b.max.x]) {
      for (const y of [b.min.y, b.max.y]) {
        for (const z of [b.min.z, b.max.z]) this.corners.push(new THREE.Vector3(x, y, z));
      }
    }

    this.mesh = new THREE.Mesh(
      geo,
      new THREE.MeshPhongMaterial({
        color: this.color,
        specular: 0x222222,
        shininess: 25,
        flatShading: false,
      }),
    );
    this.scene.add(this.mesh);
    if (this.status) this.status.remove();
    this.syncSize();
    this.frame();
  }

  fail(message) {
    if (this.status) {
      if (this.uri) {
        this.status.innerHTML =
          '<a href="' + this.uri + '" download>&#8681; Download STL mesh</a>'
          + '<br><small style="opacity:0.65">WebGL is unavailable &mdash; <a href="https://support.google.com/chrome/answer/6138473">enable hardware acceleration</a> in Chrome, or try <a href="chrome://flags/#enable-webgl-swiftshader">SwiftShader</a> for software rendering.</small>';
        this.status.classList.add("stl-viewer-fallback");
      } else {
        this.status.textContent = message;
        this.status.classList.add("stl-viewer-error");
      }
    }
  }
}

// --------------------------------------------------------------------------
// wiring
// --------------------------------------------------------------------------

function init() {
  const els = document.querySelectorAll(".stl-viewer");
  if (!els.length) return;

  const seen = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const v = entry.target._stlViewer;
        if (!v) continue;
        v.visible = entry.isIntersecting;
        if (entry.isIntersecting) {
          v.load();
          v.syncSize();
          v.dirty = true;
        }
      }
    },
    // Start fetching just before a viewer scrolls in, so it is usually ready on arrival.
    { rootMargin: "300px 0px" },
  );

  // The theme's sidebar/search can resize content without firing a window resize event.
  const resized = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const v = entry.target._stlViewer;
      if (v) v.syncSize();
    }
  });

  for (const el of els) {
    if (el._stlViewer) continue;
    const v = new Viewer(el);
    el._stlViewer = v;
    viewers.push(v);
    seen.observe(el);
    resized.observe(el);
    // Check if already in viewport – observer fires asynchronously
    const rect = el.getBoundingClientRect();
    if (rect.bottom >= -300 && rect.top <= window.innerHeight + 300) {
      v.visible = true;
      v.syncSize();
      v.load();
    }
  }

  if (!looping) {
    looping = true;
    requestAnimationFrame(tick);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
