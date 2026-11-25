import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { Galaxy, SkyColorMode } from '../types/galaxy';
import {
  projectGalaxyTo3D,
  getGalaxy3DColorRgb,
  lookbackTimeGyr,
  COSMIC_EPOCHS,
  Cosmo3DOptions,
} from '../utils/cosmo3d';
import { comovingDistanceMpc } from '../utils/physics';
import {
  Orbit,
  Eye,
  Sliders,
  Sparkles,
  Maximize2,
  RotateCcw,
  Calendar,
  Layers,
  Compass,
  Box,
} from 'lucide-react';

interface LightconeCanvas3DProps {
  galaxies: Galaxy[];
  selectedGalaxy: Galaxy | null;
  onSelectGalaxy: (galaxy: Galaxy) => void;
  centerRa: number;
  centerDec: number;
  fieldRadius: number;
  resetTrigger: number;
  colorMode?: SkyColorMode;
  discoveryMode?: boolean;
}

function isWebGLAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return Boolean(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl2') || canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
    );
  } catch {
    return false;
  }
}

// Generate crisp astronomical point-source texture with stellar core & subtle diffraction spikes
function createGalaxyParticleTexture(): THREE.CanvasTexture {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;

  const center = size / 2;

  // Soft atmospheric outer falloff
  const grad = ctx.createRadialGradient(center, center, 0, center, center, center * 0.9);
  grad.addColorStop(0, 'rgba(255, 255, 255, 1.0)');
  grad.addColorStop(0.2, 'rgba(240, 248, 255, 0.85)');
  grad.addColorStop(0.5, 'rgba(180, 210, 255, 0.35)');
  grad.addColorStop(0.8, 'rgba(100, 150, 255, 0.08)');
  grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  // Subtle 4-point diffraction spike cross (pinpoint astronomical look)
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.45)';
  ctx.lineWidth = 1.0;
  const spikeLen = size * 0.42;

  ctx.beginPath();
  ctx.moveTo(center - spikeLen, center);
  ctx.lineTo(center + spikeLen, center);
  ctx.moveTo(center, center - spikeLen);
  ctx.lineTo(center, center + spikeLen);
  ctx.stroke();

  // Brilliant pinpoint core
  ctx.beginPath();
  ctx.arc(center, center, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = '#ffffff';
  ctx.fill();

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

export const LightconeCanvas3D: React.FC<LightconeCanvas3DProps> = ({
  galaxies,
  selectedGalaxy,
  onSelectGalaxy,
  centerRa,
  centerDec,
  fieldRadius,
  resetTrigger,
  colorMode = 'rgb',
  discoveryMode = false,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // 3D Visual & Viewport controls
  const [geometryMode, setGeometryMode] = useState<'sky_plane' | 'cone'>('sky_plane');
  const [fieldSpread, setFieldSpread] = useState<number>(90.0);
  const [minZ, setMinZ] = useState<number>(0.0);
  const [maxZ, setMaxZ] = useState<number>(9.0);
  const [showEpochShells, setShowEpochShells] = useState<boolean>(true);
  const [showGrid, setShowGrid] = useState<boolean>(true);
  const [showDropLines, setShowDropLines] = useState<boolean>(true);
  const [autoRotate, setAutoRotate] = useState<boolean>(false);
  const [isControlsOpen, setIsControlsOpen] = useState<boolean>(false);
  const [webGlSupported, setWebGlSupported] = useState<boolean>(true);

  // Hover & Tooltip state
  const [hoveredGalaxy, setHoveredGalaxy] = useState<Galaxy | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);

  // Three.js instances ref
  const threeRef = useRef<{
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    renderer: THREE.WebGLRenderer;
    controls: OrbitControls;
    pointsMesh: THREE.Points | null;
    selectionRing: THREE.Mesh | null;
    selectionDropLine: THREE.Line | null;
    discoveryRingsGroup: THREE.Group | null;
    gridGroup: THREE.Group | null;
    shellsGroup: THREE.Group | null;
    backgroundStars: THREE.Points | null;
    particleTexture: THREE.CanvasTexture;
    galaxyPositions: Map<string, THREE.Vector3>;
    animFrameId: number | null;
  } | null>(null);

  // Filtered galaxies based on active redshift slider
  const visibleGalaxies = useMemo(() => {
    return galaxies.filter((g) => {
      const z = g.redshift ?? 0;
      return z >= minZ && z <= maxZ;
    });
  }, [galaxies, minZ, maxZ]);

  // Initial Scene Setup
  useEffect(() => {
    if (!canvasRef.current || !containerRef.current) return;

    if (!isWebGLAvailable()) {
      setWebGlSupported(false);
      return;
    }

    const container = containerRef.current;
    const canvas = canvasRef.current;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: true,
        powerPreference: 'high-performance',
      });
    } catch {
      setWebGlSupported(false);
      return;
    }

    // 1. Scene with dark cosmic nebula gradient
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x03050c);

    // 2. Camera: Angled isometric perspective looking along the cone
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.5, 3000);
    camera.position.set(130, 95, 120);

    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;

    // 3. Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 20;
    controls.maxDistance = 1500;
    controls.target.set(0, 0, -130);
    controls.update();

    // 4. Ambient Light
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    scene.add(ambientLight);

    // 5. Background Starfield (Subtle distant stars)
    const starCount = 350;
    const starPositions = new Float32Array(starCount * 3);
    const starColors = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount; i++) {
      starPositions[i * 3] = (Math.random() - 0.5) * 800;
      starPositions[i * 3 + 1] = (Math.random() - 0.5) * 800;
      starPositions[i * 3 + 2] = -Math.random() * 600 - 100;
      const lum = 0.3 + Math.random() * 0.45;
      starColors[i * 3] = lum * 0.9;
      starColors[i * 3 + 1] = lum * 0.95;
      starColors[i * 3 + 2] = lum;
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    starGeo.setAttribute('color', new THREE.BufferAttribute(starColors, 3));
    const starMat = new THREE.PointsMaterial({
      size: 2.0,
      vertexColors: true,
      transparent: true,
      opacity: 0.6,
      depthWrite: false,
    });
    const backgroundStars = new THREE.Points(starGeo, starMat);
    scene.add(backgroundStars);

    // Texture for galaxy particles
    const particleTexture = createGalaxyParticleTexture();

    // Selection Reticle Mesh
    const ringGeo = new THREE.RingGeometry(4.0, 5.2, 32);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.9,
    });
    const selectionRing = new THREE.Mesh(ringGeo, ringMat);
    selectionRing.visible = false;
    scene.add(selectionRing);

    // Selection Drop-Line (Connecting galaxy to base z=0 plane)
    const dropLineGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(0, 0, 0),
    ]);
    const dropLineMat = new THREE.LineDashedMaterial({
      color: 0x38bdf8,
      dashSize: 3,
      gapSize: 2,
      transparent: true,
      opacity: 0.7,
    });
    const selectionDropLine = new THREE.Line(dropLineGeo, dropLineMat);
    selectionDropLine.visible = false;
    scene.add(selectionDropLine);

    // Groups for Discovery rings, Grid, and Epoch Shells
    const discoveryRingsGroup = new THREE.Group();
    scene.add(discoveryRingsGroup);

    const gridGroup = new THREE.Group();
    scene.add(gridGroup);

    const shellsGroup = new THREE.Group();
    scene.add(shellsGroup);

    threeRef.current = {
      scene,
      camera,
      renderer,
      controls,
      pointsMesh: null,
      selectionRing,
      selectionDropLine,
      discoveryRingsGroup,
      gridGroup,
      shellsGroup,
      backgroundStars,
      particleTexture,
      galaxyPositions: new Map(),
      animFrameId: null,
    };

    // Animation Loop
    let lastTime = performance.now();
    const animate = (currentTime: number) => {
      const delta = (currentTime - lastTime) / 1000;
      lastTime = currentTime;

      const state = threeRef.current;
      if (!state) return;

      if (autoRotate) {
        state.controls.autoRotate = true;
        state.controls.autoRotateSpeed = 0.8;
      } else {
        state.controls.autoRotate = false;
      }

      state.controls.update();

      // Billboard orientation for selection ring to face camera
      if (state.selectionRing && state.selectionRing.visible) {
        state.selectionRing.quaternion.copy(state.camera.quaternion);
        const pulse = 1.0 + 0.12 * Math.sin(currentTime * 0.005);
        state.selectionRing.scale.set(pulse, pulse, pulse);
      }

      // Billboard orientation for discovery rings
      if (state.discoveryRingsGroup) {
        state.discoveryRingsGroup.children.forEach((child, idx) => {
          child.quaternion.copy(state.camera.quaternion);
          const p = 1.0 + 0.15 * Math.sin(currentTime * 0.004 + idx);
          child.scale.set(p, p, p);
        });
      }

      state.renderer.render(state.scene, state.camera);
      state.animFrameId = requestAnimationFrame(animate);
    };

    threeRef.current.animFrameId = requestAnimationFrame(animate);

    // Resize Observer
    const handleResize = () => {
      if (!containerRef.current || !threeRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      threeRef.current.camera.aspect = w / h;
      threeRef.current.camera.updateProjectionMatrix();
      threeRef.current.renderer.setSize(w, h);
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      if (threeRef.current?.animFrameId) {
        cancelAnimationFrame(threeRef.current.animFrameId);
      }
      controls.dispose();
      renderer.dispose();
      particleTexture.dispose();
      threeRef.current = null;
    };
  }, []);

  // Update Galaxies 3D Points & Wireframe whenever galaxies, scale, or colors change
  useEffect(() => {
    const state = threeRef.current;
    if (!state) return;

    // 1. Clean previous points
    if (state.pointsMesh) {
      state.scene.remove(state.pointsMesh);
      state.pointsMesh.geometry.dispose();
      (state.pointsMesh.material as THREE.Material).dispose();
      state.pointsMesh = null;
    }

    // 2. Clear discovery rings
    if (state.discoveryRingsGroup) {
      while (state.discoveryRingsGroup.children.length > 0) {
        const obj = state.discoveryRingsGroup.children.pop()!;
        if (obj instanceof THREE.Mesh) {
          obj.geometry.dispose();
          (obj.material as THREE.Material).dispose();
        }
      }
    }

    state.galaxyPositions.clear();

    const n = visibleGalaxies.length;
    if (n === 0) return;

    const positions = new Float32Array(n * 3);
    const colors = new Float32Array(n * 3);
    const sizes = new Float32Array(n);

    visibleGalaxies.forEach((g, idx) => {
      const [x, y, z] = projectGalaxyTo3D(g, centerRa, centerDec, fieldRadius, {
        geometryMode,
        fieldSpread,
        sceneDepth: 260,
        maxRedshift: 9.0,
      });

      positions[idx * 3] = x;
      positions[idx * 3 + 1] = y;
      positions[idx * 3 + 2] = z;

      state.galaxyPositions.set(g.id, new THREE.Vector3(x, y, z));

      const col = getGalaxy3DColorRgb(g, colorMode);
      colors[idx * 3] = col.r;
      colors[idx * 3 + 1] = col.g;
      colors[idx * 3 + 2] = col.b;

      // Realistic galaxy sizing: crisp stellar cores with mass-dependent scaling
      const massFactor = Math.max(0.65, (g.log_mstar - 7.0) / 2.5);
      const isDisco = Boolean(g.discovery_profile);
      // Point size in world units
      sizes[idx] = (isDisco ? 10.0 : 6.5) * massFactor;

      // Special reticle beacon for discovery or anomaly objects
      if (state.discoveryRingsGroup && (isDisco || g.sentry_status === 'ANOMALY')) {
        const ringGeo = new THREE.RingGeometry(3.0, 3.8, 24);
        const ringColor = isDisco ? 0xc084fc : 0xf43f5e;
        const ringMat = new THREE.MeshBasicMaterial({
          color: ringColor,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: isDisco ? 0.8 : 0.65,
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.position.set(x, y, z);
        state.discoveryRingsGroup.add(ring);
      }
    });

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

    // PointsMaterial with NormalBlending for rich, vibrant astronomical colors without blowout
    const material = new THREE.PointsMaterial({
      size: 7.5,
      vertexColors: true,
      map: state.particleTexture,
      transparent: true,
      blending: THREE.NormalBlending,
      opacity: 0.95,
      depthWrite: false,
      sizeAttenuation: true,
    });

    const pointsMesh = new THREE.Points(geometry, material);
    state.scene.add(pointsMesh);
    state.pointsMesh = pointsMesh;
  }, [visibleGalaxies, centerRa, centerDec, fieldRadius, geometryMode, fieldSpread, colorMode, discoveryMode]);

  // Update Astrometric Grid & Cosmic Epoch Shells
  useEffect(() => {
    const state = threeRef.current;
    if (!state) return;

    // 1. Rebuild Grid
    if (state.gridGroup) {
      while (state.gridGroup.children.length > 0) {
        const obj = state.gridGroup.children.pop()!;
        if (obj instanceof THREE.Line || obj instanceof THREE.LineSegments || obj instanceof THREE.Mesh) {
          obj.geometry.dispose();
          (obj.material as THREE.Material).dispose();
        }
      }

      if (showGrid) {
        // Base coordinate plane at z=0 (Observer / Sky plane)
        const gridSize = fieldSpread * 1.05;
        const gridDivisions = 8;
        const gridHelper = new THREE.GridHelper(gridSize * 2, gridDivisions, 0x4f46e5, 0x1e293b);
        gridHelper.rotation.x = Math.PI / 2; // Orient on X-Y plane
        gridHelper.position.set(0, 0, 0);
        state.gridGroup.add(gridHelper);

        // 4 bounding lines running along Z depth to frame the survey volume
        const zFar = -260;
        const boxCorners = [
          new THREE.Vector3(-fieldSpread, -fieldSpread, 0),
          new THREE.Vector3(fieldSpread, -fieldSpread, 0),
          new THREE.Vector3(fieldSpread, fieldSpread, 0),
          new THREE.Vector3(-fieldSpread, fieldSpread, 0),
        ];

        const linePoints: THREE.Vector3[] = [];
        boxCorners.forEach((c) => {
          if (geometryMode === 'cone') {
            // Lines radiating from observer at (0, 0, 0)
            linePoints.push(new THREE.Vector3(0, 0, 0), new THREE.Vector3(c.x, c.y, zFar));
          } else {
            // Parallel depth lines forming an elegant survey bounding box
            linePoints.push(c, new THREE.Vector3(c.x, c.y, zFar));
          }
        });

        // Far bounding rectangle
        const farCorners = boxCorners.map((c) =>
          geometryMode === 'cone' ? new THREE.Vector3(c.x, c.y, zFar) : new THREE.Vector3(c.x, c.y, zFar)
        );
        linePoints.push(farCorners[0], farCorners[1]);
        linePoints.push(farCorners[1], farCorners[2]);
        linePoints.push(farCorners[2], farCorners[3]);
        linePoints.push(farCorners[3], farCorners[0]);

        const boxGeo = new THREE.BufferGeometry().setFromPoints(linePoints);
        const boxMat = new THREE.LineBasicMaterial({
          color: 0x334155,
          transparent: true,
          opacity: 0.35,
        });
        const boxLines = new THREE.LineSegments(boxGeo, boxMat);
        state.gridGroup.add(boxLines);
      }
    }

    // 2. Cosmic Epoch Shells (Discs marking z=1, 2, 4, 6, 8.5)
    if (state.shellsGroup) {
      while (state.shellsGroup.children.length > 0) {
        const obj = state.shellsGroup.children.pop()!;
        if (obj instanceof THREE.Line || obj instanceof THREE.Mesh) {
          obj.geometry.dispose();
          (obj.material as THREE.Material).dispose();
        }
      }

      if (showEpochShells) {
        const sceneDepth = 260;
        const maxZ = 9.0;
        const maxDistanceMpc = comovingDistanceMpc(maxZ);

        COSMIC_EPOCHS.forEach((epoch) => {
          if (epoch.z > maxZ) return;
          const dMpc = comovingDistanceMpc(epoch.z);
          const zNorm = (dMpc / maxDistanceMpc) * sceneDepth;
          const zCoord = -zNorm;

          // Scale radius of ring based on geometry
          let ringRadius = fieldSpread;
          if (geometryMode === 'cone') {
            ringRadius = fieldSpread * (0.25 + 0.75 * (zNorm / sceneDepth));
          }

          // Subtle translucent circular rim
          const segments = 64;
          const ringPoints: THREE.Vector3[] = [];
          for (let i = 0; i <= segments; i++) {
            const theta = (i / segments) * Math.PI * 2;
            ringPoints.push(new THREE.Vector3(Math.cos(theta) * ringRadius, Math.sin(theta) * ringRadius, zCoord));
          }

          const ringGeo = new THREE.BufferGeometry().setFromPoints(ringPoints);
          const ringMat = new THREE.LineBasicMaterial({
            color: new THREE.Color(epoch.colorHex),
            transparent: true,
            opacity: 0.45,
          });
          const ringLine = new THREE.Line(ringGeo, ringMat);
          state.shellsGroup!.add(ringLine);

          // Subtle inner planar disc tint for Cosmic Noon (z=2) and Reionization (z=6)
          if (epoch.z === 2.0 || epoch.z === 6.0) {
            const discGeo = new THREE.CircleGeometry(ringRadius, 48);
            const discMat = new THREE.MeshBasicMaterial({
              color: new THREE.Color(epoch.colorHex),
              transparent: true,
              opacity: 0.035,
              side: THREE.DoubleSide,
              depthWrite: false,
            });
            const discMesh = new THREE.Mesh(discGeo, discMat);
            discMesh.position.set(0, 0, zCoord);
            state.shellsGroup!.add(discMesh);
          }
        });
      }
    }
  }, [showGrid, showEpochShells, geometryMode, fieldSpread]);

  // Update Selection Reticle & Drop-Line Position
  useEffect(() => {
    const state = threeRef.current;
    if (!state || !state.selectionRing) return;

    if (!selectedGalaxy) {
      state.selectionRing.visible = false;
      if (state.selectionDropLine) state.selectionDropLine.visible = false;
      return;
    }

    let pos = state.galaxyPositions.get(selectedGalaxy.id);
    if (!pos) {
      const [x, y, z] = projectGalaxyTo3D(selectedGalaxy, centerRa, centerDec, fieldRadius, {
        geometryMode,
        fieldSpread,
        sceneDepth: 260,
        maxRedshift: 9.0,
      });
      pos = new THREE.Vector3(x, y, z);
    }

    state.selectionRing.position.copy(pos);
    state.selectionRing.visible = true;

    // Update Drop-Line from galaxy to base plane z=0
    if (state.selectionDropLine && showDropLines) {
      const positions = new Float32Array([pos.x, pos.y, 0, pos.x, pos.y, pos.z]);
      state.selectionDropLine.geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      state.selectionDropLine.geometry.computeBoundingSphere();
      state.selectionDropLine.computeLineDistances();
      state.selectionDropLine.visible = true;
    }
  }, [selectedGalaxy, centerRa, centerDec, fieldRadius, geometryMode, fieldSpread, showDropLines]);

  // Reset Camera on Trigger
  useEffect(() => {
    if (!threeRef.current) return;
    const { camera, controls } = threeRef.current;
    camera.position.set(130, 95, 120);
    controls.target.set(0, 0, -130);
    controls.update();
  }, [resetTrigger]);

  // View Presets
  const setPresetView = (type: 'front' | 'isometric' | 'profile') => {
    if (!threeRef.current) return;
    const { camera, controls } = threeRef.current;
    if (type === 'front') {
      // Front View: LOOKS EXACTLY LIKE 2D SKY PROJECTION!
      camera.position.set(0, 0, 160);
      controls.target.set(0, 0, -130);
    } else if (type === 'isometric') {
      // Angled 3D Lightcone Perspective
      camera.position.set(130, 95, 120);
      controls.target.set(0, 0, -130);
    } else if (type === 'profile') {
      // Side-on Redshift Depth Profile
      camera.position.set(280, 0, -130);
      controls.target.set(0, 0, -130);
    }
    controls.update();
  };

  // Focus Camera smoothly onto a galaxy
  const focusGalaxy = useCallback((g: Galaxy) => {
    if (!threeRef.current) return;
    const { camera, controls, galaxyPositions } = threeRef.current;
    const pos = galaxyPositions.get(g.id);
    if (pos) {
      controls.target.copy(pos);
      camera.position.set(pos.x + 22, pos.y + 16, pos.z + 38);
      controls.update();
    }
  }, []);

  // Raycasting for Mouse Hover & Selection
  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const state = threeRef.current;
    if (!state || !state.pointsMesh || !containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const mouseY = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    const raycaster = new THREE.Raycaster();
    raycaster.params.Points.threshold = 4.5;
    raycaster.setFromCamera(new THREE.Vector2(mouseX, mouseY), state.camera);

    const intersects = raycaster.intersectObject(state.pointsMesh);

    if (intersects.length > 0) {
      const index = intersects[0].index;
      if (typeof index === 'number' && index < visibleGalaxies.length) {
        const found = visibleGalaxies[index];
        setHoveredGalaxy(found);
        setTooltipPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
        canvasRef.current!.style.cursor = 'pointer';
        return;
      }
    }

    setHoveredGalaxy(null);
    setTooltipPos(null);
    if (canvasRef.current) {
      canvasRef.current.style.cursor = 'default';
    }
  };

  const handleClick = () => {
    if (hoveredGalaxy) {
      onSelectGalaxy(hoveredGalaxy);
      focusGalaxy(hoveredGalaxy);
    }
  };

  if (!webGlSupported) {
    return (
      <div ref={containerRef} className="w-full h-full flex flex-col items-center justify-center bg-cosmos-950 p-6 text-center select-none">
        <div className="max-w-md p-6 bg-cosmos-900/90 border border-cosmos-700/80 rounded-2xl shadow-2xl backdrop-blur">
          <Layers className="w-10 h-10 text-cyan-400 mx-auto mb-3 animate-pulse" />
          <h3 className="text-base font-bold text-slate-100 mb-2">3D WebGL Acceleration Unavailable</h3>
          <p className="text-xs text-slate-300 leading-relaxed mb-4">
            The 3D Cosmological Lightcone requires WebGL hardware acceleration, which appears to be disabled in this browser or container environment.
          </p>
          <div className="text-xs text-slate-400">
            You can continue using the high-precision <strong className="text-cyan-300">2D Sky projection</strong> with full photometric analysis, SED fitting, and proposal generation.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-full relative overflow-hidden bg-cosmos-950 select-none">
      {/* 3D WebGL Canvas */}
      <canvas
        ref={canvasRef}
        onPointerMove={handlePointerMove}
        onClick={handleClick}
        className="w-full h-full block touch-none"
      />

      {/* Floating 3D Navigation Bar (Top Left) */}
      <div className="absolute top-4 left-4 z-20 flex flex-wrap items-center gap-2">
        {/* Preset Camera View Buttons */}
        <div className="flex items-center bg-cosmos-900/90 border border-cosmos-700/80 rounded-lg p-1 shadow-lg backdrop-blur text-xs">
          <button
            onClick={() => setPresetView('front')}
            className="px-2.5 py-1 rounded hover:bg-cosmos-800 text-slate-200 hover:text-cyan-300 font-medium transition-colors"
            title="Front View: Exactly matches 2D Sky projection from the observer perspective"
          >
            2D Sky Plane
          </button>
          <button
            onClick={() => setPresetView('isometric')}
            className="px-2.5 py-1 rounded hover:bg-cosmos-800 text-slate-200 hover:text-cyan-300 font-medium transition-colors"
            title="Isometric 3D Lightcone Perspective"
          >
            Isometric 3D
          </button>
          <button
            onClick={() => setPresetView('profile')}
            className="px-2.5 py-1 rounded hover:bg-cosmos-800 text-slate-200 hover:text-cyan-300 font-medium transition-colors"
            title="Side-on Redshift Depth Profile"
          >
            Side Profile
          </button>
        </div>

        {/* 3D Geometry Mode Toggle (Sky Plane vs Cone) */}
        <div className="flex items-center bg-cosmos-900/90 border border-cosmos-700/80 rounded-lg p-1 shadow-lg backdrop-blur text-xs">
          <button
            onClick={() => setGeometryMode('sky_plane')}
            className={`px-2 py-1 rounded font-medium transition-colors ${
              geometryMode === 'sky_plane' ? 'bg-indigo-950 text-indigo-200 border border-indigo-700/60' : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Orthogonal 3D Sky Plane (Preserves exact 2D sky layout while showing 3D depth)"
          >
            Plane + Depth
          </button>
          <button
            onClick={() => setGeometryMode('cone')}
            className={`px-2 py-1 rounded font-medium transition-colors ${
              geometryMode === 'cone' ? 'bg-indigo-950 text-indigo-200 border border-indigo-700/60' : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Expanding Cosmic Lightcone Funnel"
          >
            Cosmic Funnel
          </button>
        </div>

        {/* Auto Rotate Toggle */}
        <button
          onClick={() => setAutoRotate((prev) => !prev)}
          className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium shadow-lg backdrop-blur transition-all ${
            autoRotate
              ? 'bg-indigo-900/80 border-indigo-500 text-indigo-200 ring-1 ring-indigo-400'
              : 'bg-cosmos-900/90 border-cosmos-700/80 text-slate-300 hover:bg-cosmos-800'
          }`}
          title="Toggle Cinematic Auto-Orbit"
        >
          <Orbit className={`w-3.5 h-3.5 ${autoRotate ? 'animate-spin' : ''}`} />
          <span>{autoRotate ? 'Orbiting' : 'Auto-Orbit'}</span>
        </button>

        {/* 3D Parameters & Filter Drawer Toggle */}
        <button
          onClick={() => setIsControlsOpen((prev) => !prev)}
          className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium shadow-lg backdrop-blur transition-all ${
            isControlsOpen
              ? 'bg-cyan-900/80 border-cyan-500 text-cyan-200'
              : 'bg-cosmos-900/90 border-cosmos-700/80 text-slate-300 hover:bg-cosmos-800'
          }`}
        >
          <Sliders className="w-3.5 h-3.5 text-cyan-400" />
          <span>3D Controls</span>
        </button>
      </div>

      {/* 3D Settings & Redshift Filter Panel (Dropdown / Drawer) */}
      {isControlsOpen && (
        <div className="absolute top-16 left-4 z-20 w-80 bg-cosmos-900/95 border border-cosmos-700/80 rounded-xl p-4 shadow-2xl backdrop-blur text-xs text-slate-200 space-y-3.5 animate-in fade-in duration-150">
          <div className="flex items-center justify-between pb-2 border-b border-cosmos-800">
            <span className="font-semibold text-sm text-cyan-300 flex items-center space-x-1.5">
              <Sliders className="w-4 h-4 text-cyan-400" />
              <span>Cosmological 3D Controls</span>
            </span>
            <button
              onClick={() => setIsControlsOpen(false)}
              className="text-slate-400 hover:text-slate-200 text-xs px-1.5 py-0.5 rounded"
            >
              ✕
            </button>
          </div>

          {/* Transverse Field Spread */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-slate-300 font-medium">Sky Field Spread:</span>
              <span className="font-mono text-cyan-400 font-bold">{fieldSpread.toFixed(0)} units</span>
            </div>
            <input
              type="range"
              min="40"
              max="160"
              step="5"
              value={fieldSpread}
              onChange={(e) => setFieldSpread(Number(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-500 mt-0.5">
              <span>Compact (40)</span>
              <span>Standard (90)</span>
              <span>Expansive (160)</span>
            </div>
          </div>

          {/* Redshift Slice Filter */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-slate-300 font-medium">Redshift (z) Filter:</span>
              <span className="font-mono text-amber-400 font-bold">
                z = {minZ.toFixed(1)} — {maxZ.toFixed(1)}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">Min z</label>
                <input
                  type="range"
                  min="0.0"
                  max="8.0"
                  step="0.2"
                  value={minZ}
                  onChange={(e) => setMinZ(Math.min(Number(e.target.value), maxZ - 0.2))}
                  className="w-full accent-amber-400 cursor-pointer"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">Max z</label>
                <input
                  type="range"
                  min="1.0"
                  max="9.0"
                  step="0.2"
                  value={maxZ}
                  onChange={(e) => setMaxZ(Math.max(Number(e.target.value), minZ + 0.2))}
                  className="w-full accent-amber-400 cursor-pointer"
                />
              </div>
            </div>
          </div>

          {/* Wireframe, Grid, & Epoch Shell Toggles */}
          <div className="pt-2 border-t border-cosmos-800 space-y-2">
            <label className="flex items-center space-x-2 cursor-pointer text-slate-300 hover:text-slate-100">
              <input
                type="checkbox"
                checked={showGrid}
                onChange={(e) => setShowGrid(e.target.checked)}
                className="rounded accent-indigo-400"
              />
              <span>Show Astrometric Base Grid & Bounds</span>
            </label>
            <label className="flex items-center space-x-2 cursor-pointer text-slate-300 hover:text-slate-100">
              <input
                type="checkbox"
                checked={showEpochShells}
                onChange={(e) => setShowEpochShells(e.target.checked)}
                className="rounded accent-amber-400"
              />
              <span>Show Cosmic Epoch Shells</span>
            </label>
            <label className="flex items-center space-x-2 cursor-pointer text-slate-300 hover:text-slate-100">
              <input
                type="checkbox"
                checked={showDropLines}
                onChange={(e) => setShowDropLines(e.target.checked)}
                className="rounded accent-cyan-400"
              />
              <span>Show Redshift Depth Drop-Lines</span>
            </label>
          </div>

          {/* Reset Viewport */}
          <button
            onClick={() => {
              setFieldSpread(90);
              setMinZ(0.0);
              setMaxZ(9.0);
              setPresetView('front');
            }}
            className="w-full py-1 text-center bg-cosmos-800 hover:bg-cosmos-700 text-slate-300 rounded font-medium transition-colors"
          >
            Reset to 2D Sky Align
          </button>
        </div>
      )}

      {/* Cosmic Epoch Legend / Milestones (Bottom Right) */}
      {showEpochShells && (
        <div className="absolute bottom-4 right-4 z-10 hidden md:flex flex-col space-y-1 bg-cosmos-900/85 border border-cosmos-800/80 rounded-lg p-2.5 backdrop-blur text-[11px] shadow-lg pointer-events-none">
          <div className="font-semibold text-slate-400 mb-1 flex items-center space-x-1">
            <Calendar className="w-3.5 h-3.5 text-indigo-400" />
            <span>Cosmic Lookback Epochs</span>
          </div>
          {COSMIC_EPOCHS.map((epoch) => (
            <div key={epoch.z} className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: epoch.colorHex }} />
              <span className="font-mono font-medium text-slate-200">{epoch.label}:</span>
              <span className="text-slate-400">~{epoch.lookbackGyr} Gyr ago</span>
            </div>
          ))}
        </div>
      )}

      {/* Floating Hover Tooltip */}
      {hoveredGalaxy && tooltipPos && (
        <div
          className="absolute z-30 pointer-events-none bg-cosmos-900/95 border border-cyan-500/70 rounded-xl p-3 shadow-2xl backdrop-blur text-xs w-64 transform -translate-x-1/2 -translate-y-full mb-3"
          style={{ left: `${tooltipPos.x}px`, top: `${tooltipPos.y}px` }}
        >
          <div className="flex items-center justify-between pb-1 mb-1.5 border-b border-cosmos-700">
            <span className="font-mono font-bold text-cyan-300">{hoveredGalaxy.id}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-950 border border-indigo-700 text-indigo-300 font-mono">
              z = {hoveredGalaxy.redshift.toFixed(2)}
            </span>
          </div>

          <div className="space-y-1 text-slate-300 text-[11px]">
            <div className="flex justify-between">
              <span className="text-slate-400">Lookback Time:</span>
              <span className="font-mono text-amber-300 font-medium">
                ~{lookbackTimeGyr(hoveredGalaxy.redshift).toFixed(2)} Gyr
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Comoving Distance:</span>
              <span className="font-mono text-slate-200">
                {comovingDistanceMpc(hoveredGalaxy.redshift).toFixed(0)} Mpc
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Stellar Mass:</span>
              <span className="font-mono text-slate-200">
                log M* = {hoveredGalaxy.log_mstar.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Star Formation:</span>
              <span className="font-mono text-slate-200">
                {hoveredGalaxy.sfr?.toFixed(2) ?? '—'} M☉/yr
              </span>
            </div>
          </div>

          {hoveredGalaxy.discovery_profile && (
            <div className="mt-2 pt-1.5 border-t border-purple-800/80 flex items-center space-x-1 text-purple-300 text-[10px] font-semibold">
              <Sparkles className="w-3 h-3 text-purple-400" />
              <span>{hoveredGalaxy.discovery_profile.class_title.split('(')[0].trim()}</span>
            </div>
          )}

          <div className="mt-2 text-[10px] text-cyan-400 text-center font-medium">
            Click to inspect galaxy in detail →
          </div>
        </div>
      )}
    </div>
  );
};
