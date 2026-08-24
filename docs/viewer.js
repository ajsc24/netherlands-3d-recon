/**
 * Interactive 3D viewer for the showcase site.
 * Loads assets/model.glb when present; otherwise shows a preview image on a plane.
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { PLYLoader } from "three/addons/loaders/PLYLoader.js";

const canvas = document.getElementById("viewer-canvas");
const overlay = document.getElementById("viewer-overlay");
const statusEl = document.getElementById("viewer-status");
const spinner = document.getElementById("viewer-spinner");

function setStatus(msg, hideSpinner = false) {
  if (statusEl) statusEl.textContent = msg;
  if (spinner && hideSpinner) spinner.style.display = "none";
}

function hideOverlay() {
  overlay?.classList.add("hidden");
}

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0c0e12);

const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 500);
camera.position.set(2.5, 1.8, 2.5);

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.target.set(0, 0.5, 0);

scene.add(new THREE.AmbientLight(0xffffff, 0.55));
const key = new THREE.DirectionalLight(0xffffff, 1.1);
key.position.set(4, 8, 4);
scene.add(key);
const fill = new THREE.DirectionalLight(0x88aacc, 0.35);
fill.position.set(-3, 2, -2);
scene.add(fill);

const grid = new THREE.GridHelper(8, 16, 0x2a3142, 0x1c2230);
grid.position.y = -0.01;
scene.add(grid);

let content = null;

function frameObject(object) {
  const box = new THREE.Box3().setFromObject(object);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 0.001);
  const dist = maxDim * 1.8 / Math.tan((camera.fov * Math.PI) / 360);
  camera.position.copy(center).add(new THREE.Vector3(dist * 0.7, dist * 0.5, dist * 0.7));
  controls.target.copy(center);
  controls.update();
}

async function loadPreviewFallback() {
  setStatus("No web model yet — showing source preview", true);
  const texLoader = new THREE.TextureLoader();
  return new Promise((resolve, reject) => {
    texLoader.load(
      "assets/preview.jpg",
      (tex) => {
        tex.colorSpace = THREE.SRGBColorSpace;
        const aspect = tex.image.width / tex.image.height;
        const h = 2.2;
        const w = h * aspect;
        const geo = new THREE.PlaneGeometry(w, h);
        const mat = new THREE.MeshBasicMaterial({ map: tex, side: THREE.DoubleSide });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.rotation.y = Math.PI * 0.04;
        resolve(mesh);
      },
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

async function loadPly() {
  const loader = new PLYLoader();
  return new Promise((resolve, reject) => {
    loader.load(
      "assets/model.ply",
      (geo) => {
        geo.computeVertexNormals();
        const mat = new THREE.MeshStandardMaterial({ color: 0xaabbcc, roughness: 0.85, metalness: 0.05 });
        resolve(new THREE.Mesh(geo, mat));
      },
      undefined,
      reject
    );
  });
}

async function initContent() {
  try {
    setStatus("Loading 3D mesh…");
    content = await loadGlb();
    setStatus("Model loaded", true);
  } catch {
    try {
      content = await loadPly();
      setStatus("Model loaded (PLY)", true);
    } catch {
      try {
        content = await loadPreviewFallback();
      } catch {
        setStatus("Add assets/model.glb or run Export-WebModel.ps1", true);
        content = new THREE.Mesh(
          new THREE.BoxGeometry(1, 0.6, 1.4),
          new THREE.MeshStandardMaterial({ color: 0x3d6f96, roughness: 0.7 })
        );
      }
    }
  }
  scene.add(content);
  frameObject(content);
  setTimeout(hideOverlay, 400);
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
  controls.update();
  renderer.render(scene, camera);
}

resize();
window.addEventListener("resize", resize);
initContent();
animate();
