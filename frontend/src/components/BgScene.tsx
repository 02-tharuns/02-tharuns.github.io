import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import * as THREE from "three";

/**
 * Animated background — ported from the v1 static site's inline Three.js
 * scene (index.html: starfield, orbiting sensor nodes, IoT ping rings).
 *
 * Two things from v1 were left out on purpose, not missed: the "AI core"
 * icosahedron and the procedural robotic arm are built in v1's source too,
 * but both are set `.visible = false` there — the hero SVG replaced them
 * visually and the WebGL versions were kept only so the (now pointless)
 * animation loop had something to drive. Skipping them here is a pure
 * performance win with zero visual difference from what v1 actually shows.
 *
 * The other adaptation: v1 is a single scrolling page, so its camera moves
 * along a scroll-progress curve (0 = hero, 1 = contact, six waypoints in
 * between). v2 is a multi-page app, so scroll progress doesn't exist —
 * the same waypoints are keyed to the current route instead, and the
 * camera eases toward the new one on navigation the same way it eased
 * along scroll in v1 (same damp()-based easing, just a different input).
 */

const COLOR_FLAME = 0xff7a18;
const COLOR_MAGENTA = 0xec1e62;

// route -> point along the old scroll-progress curve (see v1's camKeys)
const ROUTE_PROGRESS: Record<string, number> = {
  "/about": 0.05,
  "/projects": 0.3,
  "/education": 0.48,
  "/skills": 0.63,
  "/achievements": 0.8,
  "/contact": 1.0,
};

const CAM_KEYS = [
  { t: 0.0, pos: [1.7, 0.35, 12.4], look: [-2.7, 0.1, 0] },
  { t: 0.14, pos: [3.4, 1.0, 16.5], look: [-3.2, 0.15, 0] },
  { t: 0.3, pos: [-3.6, 1.2, 16.5], look: [-4.2, 0.3, 0] },
  { t: 0.48, pos: [3.8, -0.3, 16.5], look: [4.0, -0.15, 0] },
  { t: 0.63, pos: [0, 2.6, 15.5], look: [-3.2, 0.8, 0] },
  { t: 0.8, pos: [-3.4, 0.6, 16.5], look: [-4.0, 0, 0] },
  { t: 1.0, pos: [0, 0.7, 18.5], look: [3.4, 0.2, 0] },
] as const;

function clamp(v: number, min: number, max: number) {
  return Math.min(Math.max(v, min), max);
}
function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}
function damp(current: number, target: number, lambda: number, dt: number) {
  return lerp(current, target, 1 - Math.exp(-lambda * dt));
}

function evalCamera(progress: number) {
  const p = clamp(progress, 0, 1);
  let a: (typeof CAM_KEYS)[number] = CAM_KEYS[0];
  let b: (typeof CAM_KEYS)[number] = CAM_KEYS[CAM_KEYS.length - 1];
  for (let i = 0; i < CAM_KEYS.length - 1; i++) {
    if (p >= CAM_KEYS[i].t && p <= CAM_KEYS[i + 1].t) {
      a = CAM_KEYS[i];
      b = CAM_KEYS[i + 1];
      break;
    }
  }
  const span = b.t - a.t || 1;
  let lt = (p - a.t) / span;
  lt = lt * lt * (3 - 2 * lt); // smoothstep
  return {
    pos: [lerp(a.pos[0], b.pos[0], lt), lerp(a.pos[1], b.pos[1], lt), lerp(a.pos[2], b.pos[2], lt)],
    look: [lerp(a.look[0], b.look[0], lt), lerp(a.look[1], b.look[1], lt), lerp(a.look[2], b.look[2], lt)],
  };
}

export default function BgScene() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const progressRef = useRef(0);
  const location = useLocation();

  // Update the camera's target waypoint whenever the route changes — the
  // animation loop below eases toward it every frame, same as v1 eased
  // toward whatever scroll progress said.
  useEffect(() => {
    progressRef.current = ROUTE_PROGRESS[location.pathname] ?? 0.5;
  }, [location.pathname]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const small = window.innerWidth < 760;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
    } catch {
      return; // no WebGL — the CSS gradient/grain/vignette layers still show
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 100);
    camera.position.set(0, 0.3, 13);

    scene.add(new THREE.AmbientLight(0x1a2035, 1.1));
    const lightFlame = new THREE.PointLight(COLOR_FLAME, 2.2, 30);
    lightFlame.position.set(7, 5, 6);
    scene.add(lightFlame);
    const lightMagenta = new THREE.PointLight(COLOR_MAGENTA, 2.0, 30);
    lightMagenta.position.set(-6, -3, 5);
    scene.add(lightMagenta);

    // ---------- glow sprite texture, shared by nodes + stars ----------
    function makeGlowTexture() {
      const size = 128;
      const c = document.createElement("canvas");
      c.width = c.height = size;
      const ctx = c.getContext("2d")!;
      const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
      g.addColorStop(0, "rgba(255,255,255,1)");
      g.addColorStop(0.35, "rgba(255,255,255,0.4)");
      g.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, size, size);
      return new THREE.CanvasTexture(c);
    }
    const glowTex = makeGlowTexture();

    // ---------- orbiting sensor / data nodes ----------
    const nodeCount = small ? 9 : 16;
    const nodeGeo = new THREE.SphereGeometry(0.075, 12, 12);
    const nodes: { pivot: THREE.Object3D; mesh: THREE.Mesh; speed: number; worldPos: THREE.Vector3 }[] = [];
    const orbitGroup = new THREE.Group();
    scene.add(orbitGroup);

    const radiusMin = small ? 2.3 : 3.1;
    const radiusSpan = small ? 3.6 : 3.3;
    for (let i = 0; i < nodeCount; i++) {
      const radius = radiusMin + Math.random() * radiusSpan;
      const color = i % 2 === 0 ? COLOR_FLAME : COLOR_MAGENTA;
      const pivot = new THREE.Object3D();
      pivot.rotation.x = (Math.random() - 0.5) * 1.3;
      pivot.rotation.z = (Math.random() - 0.5) * 1.3;
      pivot.rotation.y = Math.random() * Math.PI * 2;
      orbitGroup.add(pivot);

      const mesh = new THREE.Mesh(nodeGeo, new THREE.MeshBasicMaterial({ color }));
      mesh.position.set(radius, 0, 0);
      pivot.add(mesh);

      const speed = (0.09 + Math.random() * 0.16) * (Math.random() < 0.5 ? -1 : 1);
      nodes.push({ pivot, mesh, speed, worldPos: new THREE.Vector3() });
    }

    // ---------- connecting lines (neural-network look) ----------
    // core is fixed at the origin in v2 (v1's core sprite is hidden too —
    // this just gives the node ring something shared to link through).
    const linkPairs: [number, number][] = [];
    for (let n = 0; n < nodeCount; n++) {
      linkPairs.push([-1, n]);
      linkPairs.push([n, (n + 1) % nodeCount]);
    }
    const linkGeo = new THREE.BufferGeometry();
    const linkPositions = new Float32Array(linkPairs.length * 2 * 3);
    linkGeo.setAttribute("position", new THREE.BufferAttribute(linkPositions, 3));
    const linkMat = new THREE.LineBasicMaterial({ color: COLOR_FLAME, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false });
    const linkLines = new THREE.LineSegments(linkGeo, linkMat);
    scene.add(linkLines);

    const originPos = new THREE.Vector3(0, 0, 0);
    function updateLinks() {
      for (let i = 0; i < nodeCount; i++) nodes[i].mesh.getWorldPosition(nodes[i].worldPos);
      const arr = linkLines.geometry.attributes.position.array as Float32Array;
      for (let j = 0; j < linkPairs.length; j++) {
        const [a, b] = linkPairs[j];
        const pA = a === -1 ? originPos : nodes[a].worldPos;
        const pB = b === -1 ? originPos : nodes[b].worldPos;
        const o = j * 6;
        arr[o] = pA.x; arr[o + 1] = pA.y; arr[o + 2] = pA.z;
        arr[o + 3] = pB.x; arr[o + 4] = pB.y; arr[o + 5] = pB.z;
      }
      linkLines.geometry.attributes.position.needsUpdate = true;
    }

    // ---------- starfield ----------
    function buildStars(count: number, spread: number, size: number, opacity: number) {
      const geo = new THREE.BufferGeometry();
      const pos = new Float32Array(count * 3);
      for (let k = 0; k < count; k++) {
        const r = spread * (0.4 + Math.random() * 0.6);
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(Math.random() * 2 - 1);
        pos[k * 3] = r * Math.sin(phi) * Math.cos(theta);
        pos[k * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        pos[k * 3 + 2] = r * Math.cos(phi);
      }
      geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      const mat = new THREE.PointsMaterial({
        color: 0xffd9b0, size, map: glowTex, transparent: true, opacity, sizeAttenuation: true,
        blending: THREE.AdditiveBlending, depthWrite: false,
      });
      return new THREE.Points(geo, mat);
    }
    const starsFar = buildStars(small ? 900 : 1900, 42, 0.06, 0.55);
    const starsNear = buildStars(small ? 250 : 550, 22, 0.09, 0.75);
    scene.add(starsFar, starsNear);

    // ---------- ground grid ----------
    const grid = new THREE.GridHelper(46, 46, COLOR_FLAME, COLOR_MAGENTA);
    grid.position.y = -3.4;
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.1;
    (grid.material as THREE.Material).blending = THREE.AdditiveBlending;
    scene.add(grid);

    // ---------- IoT radar ping rings ----------
    const ringGeo = new THREE.RingGeometry(0.85, 1.0, 40);
    const pingDefs = [
      { pos: [-2.6, -3.35, 1.6], color: COLOR_FLAME, offset: 0.0 },
      { pos: [1.9, -3.35, -1.8], color: COLOR_MAGENTA, offset: 1.1 },
      { pos: [4.6, -3.35, 2.4], color: COLOR_FLAME, offset: 2.1 },
    ];
    const pingRings = pingDefs.map((def) => {
      const mat = new THREE.MeshBasicMaterial({ color: def.color, transparent: true, opacity: 0.5, side: THREE.DoubleSide, depthWrite: false });
      const mesh = new THREE.Mesh(ringGeo, mat);
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.set(def.pos[0], def.pos[1], def.pos[2]);
      mesh.scale.setScalar(0.001);
      scene.add(mesh);
      return { mesh, mat, offset: def.offset, duration: 3.4 };
    });

    // ---------- pointer parallax ----------
    let mouseNormX = 0;
    let mouseNormY = 0;
    function onMouseMove(e: MouseEvent) {
      mouseNormX = (e.clientX / window.innerWidth) * 2 - 1;
      mouseNormY = (e.clientY / window.innerHeight) * 2 - 1;
    }
    window.addEventListener("mousemove", onMouseMove, { passive: true });

    // ---------- resize ----------
    function onResize() {
      const w = window.innerWidth, h = window.innerHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    }
    window.addEventListener("resize", onResize);

    // ---------- visibility pause ----------
    let running = true;
    let rafId: number | null = null;
    function onVisibility() {
      running = !document.hidden;
      if (running && rafId === null) {
        clock.getDelta();
        rafId = requestAnimationFrame(animate);
      }
    }
    document.addEventListener("visibilitychange", onVisibility);

    // ---------- animate ----------
    const clock = new THREE.Clock();
    const currentLook = new THREE.Vector3(0, 0, 0);
    let parallaxX = 0, parallaxY = 0;

    function animate() {
      rafId = running ? requestAnimationFrame(animate) : null;
      if (!running) return;

      const dt = Math.min(clock.getDelta(), 0.05);
      const elapsed = clock.getElapsedTime();
      const motionScale = reducedMotion ? 0.12 : 1;

      for (let i = 0; i < nodeCount; i++) nodes[i].pivot.rotation.y += nodes[i].speed * dt * motionScale;
      updateLinks();

      starsFar.rotation.y += dt * 0.0025 * motionScale;
      starsNear.rotation.y -= dt * 0.004 * motionScale;

      const gridCell = 46 / 46;
      grid.position.z = (elapsed * 0.5 * motionScale) % gridCell;

      pingRings.forEach((r) => {
        const t = ((elapsed * motionScale + r.offset) % r.duration) / r.duration;
        const s = 0.25 + t * 2.1;
        r.mesh.scale.set(s, s, s);
        r.mat.opacity = Math.max(0, 1 - t) * 0.55;
      });

      const cam = evalCamera(reducedMotion ? 0 : progressRef.current);
      parallaxX = damp(parallaxX, reducedMotion ? 0 : mouseNormX * 0.5, 4, dt);
      parallaxY = damp(parallaxY, reducedMotion ? 0 : -mouseNormY * 0.28, 4, dt);
      const idleBobY = Math.sin(elapsed * 0.3) * 0.06;

      camera.position.x = damp(camera.position.x, cam.pos[0] + parallaxX, 3.2, dt);
      camera.position.y = damp(camera.position.y, cam.pos[1] + parallaxY + idleBobY, 3.2, dt);
      camera.position.z = damp(camera.position.z, cam.pos[2], 3.2, dt);

      currentLook.x = damp(currentLook.x, cam.look[0], 3.2, dt);
      currentLook.y = damp(currentLook.y, cam.look[1], 3.2, dt);
      currentLook.z = damp(currentLook.z, cam.look[2], 3.2, dt);
      camera.lookAt(currentLook);

      renderer.render(scene, camera);
    }
    rafId = requestAnimationFrame(animate);

    return () => {
      running = false;
      if (rafId !== null) cancelAnimationFrame(rafId);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
      linkGeo.dispose();
      linkMat.dispose();
      nodeGeo.dispose();
      ringGeo.dispose();
      glowTex.dispose();
      starsFar.geometry.dispose();
      starsNear.geometry.dispose();
      (starsFar.material as THREE.Material).dispose();
      (starsNear.material as THREE.Material).dispose();
      pingRings.forEach((r) => r.mat.dispose());
      renderer.dispose();
    };
  }, []);

  return <canvas ref={canvasRef} className="bg-canvas" aria-hidden="true" />;
}
