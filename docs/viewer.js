/**
 * 3D showcase viewer — first-person walk (WASD) + orbit mode.
 * Loads: model.glb → model.ply → sparse_preview.ply → preview image.
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { PointerLockControls } from "three/addons/controls/PointerLockControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { PLYLoader } from "three/addons/loaders/PLYLoader.js";

const canvas = document.getElementById("viewer-canvas");
const overlay = document.getElementById("viewer-overlay");
const statusEl = document.getElementById("viewer-status");
const spinner = document.getElementById("viewer-spinner");
const hintEl = document.getElementById("viewer-hint");
const walkHud = document.getElementById("walk-hud");
const btnWalk = document.getElementById("btn-walk");
const btnOrbit = document.getElementById("btn-orbit");
const btnFs = document.getElementById("btn-fullscreen");

const EYE_HEIGHT = 1.65;
const MOVE_SPEED = 4.0;
const SPRINT_MULT = 1.8;

function setStatus(msg, hideSpinner = false) {
  if (statusEl) statusEl.textContent = msg;
  if (spinner && hideSpinner) spinner.style.display = "none";
}

function hideOverlay() {
  overlay?.classList.add("hidden");
}

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0c0e12);
scene.fog = new THREE.Fog(0x0c0e12, 40, 120);

const camera = new THREE.PerspectiveCamera(70, 1, 0.05, 300);
camera.rotation.order = "YXZ";

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;

const orbit = new OrbitControls(camera, canvas);
orbit.enableDamping = true;
orbit.dampingFactor = 0.06;
orbit.enabled = false;

const pointer = new PointerLockControls(camera, document.body);
const keys = { w: false, a: false, s: false, d: false, shift: false };
const velocity = new THREE.Vector3();
const direction = new THREE.Vector3();
let mode = "walk";
let content = null;
let sceneBounds = new THREE.Box3();
let floorY = 0;
let hasRealMesh = false;

scene.add(new THREE.AmbientLight(0xffffff, 0.65));
const keyLight = new THREE.DirectionalLight(0xffffff, 0.9);
keyLight.position.set(6, 12, 4);
scene.add(keyLight);

function setMode(next) {
  mode = next;
  if (mode === "walk") {
    orbit.enabled = false;
    pointer.unlock();
    walkHud?.classList.remove("hidden");
    if (hintEl) {
      hintEl.textContent = "Click Enter walk mode, then WASD to move · mouse to look · Esc to exit";
    }
    btnWalk?.classList.add("active");
    btnOrbit?.classList.remove("active");
  } else {
    pointer.unlock();
    orbit.enabled = true;
    walkHud?.classList.add("hidden");
    if (hintEl) {
      hintEl.textContent = "Drag to orbit · scroll to zoom · right-drag to pan";
    }
    btnOrbit?.classList.add("active");
    btnWalk?.classList.remove("active");
  }
}

function meshFromGeometry(geo, { pointCloud = false } = {}) {
  if (pointCloud) {
    geo.computeBoundingBox();
    const hasColor = geo.hasAttribute("color");
    const mat = new THREE.PointsMaterial({
      size: hasRealMesh ? 0.015 : 0.04,
      vertexColors: hasColor,
      color: hasColor ? 0xffffff : 0x9eb8d4,
      sizeAttenuation: true,
    });
    return new THREE.Points(geo, mat);
  }
  geo.computeVertexNormals();
  return new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: 0xb8c4d0, roughness: 0.82, metalness: 0.04, side: THREE.DoubleSide })
  );
}

function updateBounds(object) {
  sceneBounds.setFromObject(object);
  floorY = sceneBounds.min.y;
}

function placeWalkSpawn() {
  const center = sceneBounds.getCenter(new THREE.Vector3());
  const size = sceneBounds.getSize(new THREE.Vector3());
  camera.position.set(center.x, floorY + EYE_HEIGHT, center.z + size.z * 0.15);
  camera.rotation.set(0, 0, 0);
  orbit.target.copy(center);
  orbit.update();
}

async function tryLoad(url, pointCloud = false) {
  const loader = new PLYLoader();
  return new Promise((resolve, reject) => {
    loader.load(
      url,
      (geo) => resolve(meshFromGeometry(geo, { pointCloud })),
      undefined,
      reject
    );
  });
}

async function loadGlb() {
  const loader = new GLTFLoader();
  return new Promise((resolve, reject) => {
    loader.load("assets/model.glb", (gltf) => resolve(gltf.scene), undefined, reject);
  });
}

async function loadPreviewFallback() {
  setStatus("Showing photo preview — export mesh for full walk", true);
  const texLoader = new THREE.TextureLoader();
  return new Promise((resolve, reject) => {
    texLoader.load(
      "assets/preview.jpg",
      (tex) => {
        tex.colorSpace = THREE.SRGBColorSpace;
        const aspect = tex.image.width / tex.image.height;
        const h = 2.4;
        const geo = new THREE.PlaneGeometry(h * aspect, h);
        const mat = new THREE.MeshBasicMaterial({ map: tex, side: THREE.DoubleSide });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.rotation.y = 0.08;
        resolve(mesh);
      },
      undefined,
      reject
    );
  });
}

async function initContent() {
  const sources = [
    { fn: loadGlb, label: "mesh (GLB)", mesh: true },
    { fn: () => tryLoad("assets/model.ply"), label: "mesh (PLY)", mesh: true },
    { fn: () => tryLoad("assets/sparse_preview.ply", true), label: "sparse point cloud", mesh: false },
  ];

  for (const src of sources) {
    try {
      setStatus(`Loading ${src.label}…`);
      content = await src.fn();
      hasRealMesh = src.mesh;
      setStatus(`Loaded ${src.label}`, true);
      break;
    } catch {
      /* try next */
    }
  }

  if (!content) {
    try {
      content = await loadPreviewFallback();
      hasRealMesh = false;
    } catch {
      content = new THREE.Mesh(
        new THREE.BoxGeometry(1, 0.6, 1.4),
        new THREE.MeshStandardMaterial({ color: 0x3d6f96 })
      );
    }
  }

  scene.add(content);
  updateBounds(content);
  placeWalkSpawn();
  setMode(hasRealMesh || content.isPoints ? "walk" : "orbit");
  if (content.isPoints && hintEl) {
    hintEl.textContent = "Walk through the point cloud · dense mesh loads when exported";
  }
  setTimeout(hideOverlay, 400);
}

function onKey(e, down) {
  const k = e.code;
  if (k === "KeyW") keys.w = down;
  if (k === "KeyA") keys.a = down;
  if (k === "KeyS") keys.s = down;
  if (k === "KeyD") keys.d = down;
  if (k === "ShiftLeft" || k === "ShiftRight") keys.shift = down;
}

document.addEventListener("keydown", (e) => onKey(e, true));
document.addEventListener("keyup", (e) => onKey(e, false));

btnWalk?.addEventListener("click", () => {
  setMode("walk");
  pointer.lock();
});
btnOrbit?.addEventListener("click", () => setMode("orbit"));
btnFs?.addEventListener("click", () => {
  canvas.parentElement?.requestFullscreen?.();
});

pointer.addEventListener("lock", () => walkHud?.querySelector(".walk-prompt")?.classList.add("hidden"));
pointer.addEventListener("unlock", () => walkHud?.querySelector(".walk-prompt")?.classList.remove("hidden"));

const clock = new THREE.Clock();

function tickWalk(delta) {
  if (!pointer.isLocked) return;

  velocity.x -= velocity.x * 8 * delta;
  velocity.z -= velocity.z * 8 * delta;

  direction.set(0, 0, 0);
  if (keys.w) direction.z -= 1;
  if (keys.s) direction.z += 1;
  if (keys.a) direction.x -= 1;
  if (keys.d) direction.x += 1;
  direction.normalize();

  const speed = MOVE_SPEED * (keys.shift ? SPRINT_MULT : 1);
  if (keys.w || keys.s) velocity.z -= direction.z * speed * delta;
  if (keys.a || keys.d) velocity.x -= direction.x * speed * delta;

  pointer.moveRight(-velocity.x * delta);
  pointer.moveForward(-velocity.z * delta);

  camera.position.y = floorY + EYE_HEIGHT;

  const pad = 0.5;
  camera.position.x = THREE.MathUtils.clamp(camera.position.x, sceneBounds.min.x + pad, sceneBounds.max.x - pad);
  camera.position.z = THREE.MathUtils.clamp(camera.position.z, sceneBounds.min.z + pad, sceneBounds.max.z - pad);
}

function resize() {
  const wrap = canvas.parentElement;
  const w = wrap.clientWidth;
  const h = wrap.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
}

function animate() {
  requestAnimationFrame(animate);
  const delta = Math.min(clock.getDelta(), 0.05);
  if (mode === "walk") tickWalk(delta);
  else orbit.update();
  renderer.render(scene, camera);
}

resize();
window.addEventListener("resize", resize);
initContent();
animate();
