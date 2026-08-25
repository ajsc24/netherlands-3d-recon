/**
 * 3D showcase viewer — Gaussian splat (first-person walk + orbit).
 * Renders assets/livingroom.splat with @mkkellogg/gaussian-splats-3d into the
 * existing hero canvas UI. Camera is built around the reconstruction's true
 * "up" vector (this scene's up is ~ -Y, not +Y) so the horizon stays level.
 */
import * as THREE from "three";
import * as GS from "@mkkellogg/gaussian-splats-3d";

const SPLAT_URL = "assets/livingroom.splat";
// Mean of the COLMAP camera up-vectors for this reconstruction (ply frame).
const UP = new THREE.Vector3(-0.0167, -0.9804, 0.1963).normalize();

const wrap = document.getElementById("viewer-wrap");
const oldCanvas = document.getElementById("viewer-canvas");
const overlay = document.getElementById("viewer-overlay");
const statusEl = document.getElementById("viewer-status");
const spinner = document.getElementById("viewer-spinner");
const hintEl = document.getElementById("viewer-hint");
const walkHud = document.getElementById("walk-hud");
const btnWalk = document.getElementById("btn-walk");
const btnOrbit = document.getElementById("btn-orbit");
const btnFs = document.getElementById("btn-fullscreen");

if (oldCanvas) oldCanvas.style.display = "none"; // library creates its own canvas

const setStatus = (m, hide = false) => { if (statusEl) statusEl.textContent = m; if (spinner && hide) spinner.style.display = "none"; };
const hideOverlay = () => overlay?.classList.add("hidden");

// horizontal basis perpendicular to UP
const RIGHT0 = new THREE.Vector3(), FWD0 = new THREE.Vector3();
(function basis() {
  const ref = Math.abs(UP.dot(new THREE.Vector3(0, 0, 1))) < 0.9 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(1, 0, 0);
  RIGHT0.crossVectors(UP, ref).normalize();
  FWD0.crossVectors(RIGHT0, UP).normalize();
})();

const viewer = new GS.Viewer({
  rootElement: wrap,
  useBuiltInControls: false,
  sharedMemoryForWorkers: false,
  dynamicScene: false,
  cameraUp: [UP.x, UP.y, UP.z],
  initialCameraPosition: [0, 0, 1],
  initialCameraLookAt: [0, 0, 0],
  sphericalHarmonicsDegree: 0,
});

// ---- scene bounds + camera state ----
const st = { center: new THREE.Vector3(), size: 6, pos: new THREE.Vector3(), yaw: 0, pitch: 0, speed: 1 };
const keys = { w: false, a: false, s: false, d: false, shift: false };
let mode = "walk";
let dragging = false, lx = 0, ly = 0;
// orbit state
const orb = { az: 0, el: 0.25, dist: 6 };

function robustBounds() {
  let mesh = null, count = 0;
  try { mesh = viewer.getSplatMesh ? viewer.getSplatMesh() : viewer.splatMesh; count = mesh.getSplatCount(); } catch (e) {}
  if (mesh && count > 0) {
    const t = new THREE.Vector3(), xs = [], ys = [], zs = [], N = Math.min(count, 8000);
    for (let i = 0; i < N; i++) { mesh.getSplatCenter((Math.random() * count) | 0, t, true); if (isFinite(t.x)) { xs.push(t.x); ys.push(t.y); zs.push(t.z); } }
    const pc = (a, p) => { const b = [...a].sort((u, v) => u - v); return b[Math.max(0, Math.min(b.length - 1, Math.round(p * (b.length - 1))))]; };
    st.center.set(pc(xs, .5), pc(ys, .5), pc(zs, .5));
    st.size = Math.max(pc(xs, .9) - pc(xs, .1), pc(ys, .9) - pc(ys, .1), pc(zs, .9) - pc(zs, .1), 1);
  }
  st.speed = st.size * 0.12;
  orb.dist = st.size * 0.9;
  st.pos.copy(st.center);
}

function setMode(next) {
  mode = next;
  if (next === "walk") {
    btnWalk?.classList.add("active"); btnOrbit?.classList.remove("active");
    walkHud?.classList.remove("hidden");
    if (hintEl) hintEl.textContent = "Click the view, then WASD to move · mouse/drag to look · Shift sprint";
  } else {
    btnOrbit?.classList.add("active"); btnWalk?.classList.remove("active");
    walkHud?.classList.add("hidden");
    document.exitPointerLock?.();
    if (hintEl) hintEl.textContent = "Drag to orbit · scroll to zoom";
    // seed orbit angles from current position
    orb.dist = Math.max(st.size * 0.4, st.pos.distanceTo(st.center));
  }
}

// ---- input ----
const el = () => wrap.querySelector("canvas") || wrap;
function onKey(e, d) {
  const k = e.code;
  if (k === "KeyW") keys.w = d; if (k === "KeyS") keys.s = d;
  if (k === "KeyA") keys.a = d; if (k === "KeyD") keys.d = d;
  if (k === "ShiftLeft" || k === "ShiftRight") keys.shift = d;
  if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(k)) e.preventDefault();
}
addEventListener("keydown", (e) => onKey(e, true));
addEventListener("keyup", (e) => onKey(e, false));

wrap.addEventListener("mousedown", (e) => { dragging = true; lx = e.clientX; ly = e.clientY; });
addEventListener("mouseup", () => { dragging = false; });
addEventListener("mousemove", (e) => {
  const locked = document.pointerLockElement;
  if (locked) { st.yaw -= e.movementX * 0.0025; st.pitch -= e.movementY * 0.0025; clampPitch(); return; }
  if (!dragging) return;
  const dx = e.clientX - lx, dy = e.clientY - ly; lx = e.clientX; ly = e.clientY;
  if (mode === "walk") { st.yaw -= dx * 0.005; st.pitch -= dy * 0.005; clampPitch(); }
  else { orb.az -= dx * 0.008; orb.el = Math.max(-1.4, Math.min(1.4, orb.el + dy * 0.008)); }
});
wrap.addEventListener("wheel", (e) => {
  e.preventDefault();
  if (mode === "orbit") orb.dist = Math.max(st.size * 0.05, orb.dist * (e.deltaY < 0 ? 0.9 : 1.11));
  else st.speed *= (e.deltaY < 0 ? 1.12 : 0.9);
}, { passive: false });

const clampPitch = () => st.pitch = Math.max(-Math.PI / 2 + 0.05, Math.min(Math.PI / 2 - 0.05, st.pitch));

btnWalk?.addEventListener("click", () => { setMode("walk"); el().requestPointerLock?.(); });
btnOrbit?.addEventListener("click", () => setMode("orbit"));
btnFs?.addEventListener("click", () => wrap.requestFullscreen?.());
wrap.addEventListener("click", () => { if (mode === "walk" && !document.pointerLockElement) el().requestPointerLock?.(); });

// ---- per-frame camera ----
let prev = performance.now();
function forwardDir() {
  const h = new THREE.Vector3().addScaledVector(FWD0, Math.cos(st.yaw)).addScaledVector(RIGHT0, Math.sin(st.yaw));
  return new THREE.Vector3().addScaledVector(h, Math.cos(st.pitch)).addScaledVector(UP, Math.sin(st.pitch)).normalize();
}
function updateCamera(dt) {
  const cam = viewer.camera;
  if (mode === "orbit") {
    const dir = new THREE.Vector3()
      .addScaledVector(FWD0, Math.cos(orb.el) * Math.cos(orb.az))
      .addScaledVector(RIGHT0, Math.cos(orb.el) * Math.sin(orb.az))
      .addScaledVector(UP, Math.sin(orb.el));
    cam.position.copy(st.center).addScaledVector(dir, orb.dist);
    cam.up.copy(UP); cam.lookAt(st.center); cam.updateMatrixWorld();
    return;
  }
  const fwd = forwardDir();
  const right = new THREE.Vector3().crossVectors(fwd, UP).normalize();
  const mv = new THREE.Vector3();
  if (keys.w) mv.add(fwd); if (keys.s) mv.addScaledVector(fwd, -1);
  if (keys.d) mv.add(right); if (keys.a) mv.addScaledVector(right, -1);
  if (mv.lengthSq() > 0) st.pos.addScaledVector(mv.normalize(), st.speed * dt * (keys.shift ? 2.4 : 1));
  cam.position.copy(st.pos);
  cam.up.copy(UP); cam.lookAt(st.pos.clone().add(fwd)); cam.updateMatrixWorld();
}
function loop() {
  requestAnimationFrame(loop);
  const now = performance.now(), dt = Math.min(0.05, (now - prev) / 1000); prev = now;
  updateCamera(dt);
}

setStatus("Loading 3D model…");
(async () => {
  try {
    // Fetch the whole splat ourselves, then hand the viewer a local blob URL.
    // GitHub Pages' streamed responses break the library's built-in URL loader;
    // a fully-buffered local blob is reliable across hosts.
    const resp = await fetch(SPLAT_URL);
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const total = +(resp.headers.get("content-length") || 0);
    const reader = resp.body.getReader();
    const chunks = []; let received = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value); received += value.length;
      if (total) setStatus("Loading splat… " + Math.round((received / total) * 100) + "%");
    }
    const bytes = new Uint8Array(received); let off = 0;
    for (const c of chunks) { bytes.set(c, off); off += c.length; }
    const blobUrl = URL.createObjectURL(new Blob([bytes], { type: "application/octet-stream" }));
    await viewer.addSplatScene(blobUrl, {
      format: GS.SceneFormat.Splat,
      showLoadingUI: false, progressiveLoad: false, splatAlphaRemovalThreshold: 5,
    });
    URL.revokeObjectURL(blobUrl);
    robustBounds();
    setMode("walk");
    setStatus("Loaded", true);
    hideOverlay();
    viewer.start();
    loop();
  } catch (e) {
    setStatus("Could not load model: " + (e && e.message || e), true);
    console.error(e);
  }
})();
