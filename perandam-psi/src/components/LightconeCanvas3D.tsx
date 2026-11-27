import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { Galaxy, SkyColorMode, ProgenitorNode } from '../types/galaxy';
import {
  projectGalaxyTo3D,
  projectCoordsTo3D,
  getGalaxy3DColorRgb,
  lookbackTimeGyr,
  COSMIC_EPOCHS,
  Cosmo3DOptions,
} from '../utils/cosmo3d';
import { comovingDistanceMpc } from '../utils/physics';
import evolutionTracksData from '../data/evolution_tracks.json';
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
  GitBranch,
  Activity,
  ChevronDown,
  ChevronUp,
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
  scrubberZ?: number;
  onScrubberChange?: (z: number) => void;
  isActive?: boolean;
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

// Cosmic epoch snapshots from high-z (early universe) to low-z (present day)
const EPOCHS_TREE = [
  { z: 'z = 6.0', desc: 'Proto-halos', y: 7.5, color: 0x818cf8, hex: '#818cf8' },
  { z: 'z = 4.0', desc: 'First mergers', y: 4.5, color: 0x38bdf8, hex: '#38bdf8' },
  { z: 'z = 2.2', desc: 'Peak assembly', y: 1.5, color: 0x22d3ee, hex: '#22d3ee' },
  { z: 'z = 1.0', desc: 'Major accretion', y: -1.5, color: 0x34d399, hex: '#34d399' },
  { z: 'z = 0.4', desc: 'Late infall', y: -4.5, color: 0xfbbf24, hex: '#fbbf24' },
  { z: 'z = 0.0', desc: 'Descendant halo', y: -7.5, color: 0xf97316, hex: '#f97316' }
];

const MERGER_BRANCHES = [
  {
    id: 'main',
    name: 'Main Progenitor',
    tubeRadius: 0.16,
    colorStart: new THREE.Color(0x38bdf8),
    colorEnd: new THREE.Color(0xfbbf24),
    pulseColor: 0xffffff,
    pulseCount: 16,
    pulseSpeed: 0.24,
    nodes: [
      { epochIdx: 0, pos: new THREE.Vector3(-2.4, 7.5, -1.6), mass: 0.24 },
      { epochIdx: 1, pos: new THREE.Vector3(-1.3, 4.5, -0.5), mass: 0.34 },
      { epochIdx: 2, pos: new THREE.Vector3(-1.8, 1.5, 1.2), mass: 0.48 },
      { epochIdx: 3, pos: new THREE.Vector3(-0.3, -1.5, 0.4), mass: 0.64 },
      { epochIdx: 4, pos: new THREE.Vector3( 0.6, -4.5, -0.5), mass: 0.82 },
      { epochIdx: 5, pos: new THREE.Vector3( 0.0, -7.5, 0.0), mass: 1.05 }
    ]
  },
  {
    id: 'sub1',
    name: 'Sub-halo Alpha',
    tubeRadius: 0.10,
    colorStart: new THREE.Color(0xa78bfa),
    colorEnd: new THREE.Color(0x22d3ee),
    pulseColor: 0xe0f2fe,
    pulseCount: 9,
    pulseSpeed: 0.28,
    nodes: [
      { epochIdx: 0, pos: new THREE.Vector3( 3.2, 7.5, 1.4), mass: 0.20 },
      { epochIdx: 1, pos: new THREE.Vector3( 2.1, 4.5, 2.2), mass: 0.28 },
      { epochIdx: 2, pos: new THREE.Vector3( 0.5, 1.5, 1.7), mass: 0.36 },
      { epochIdx: 3, pos: new THREE.Vector3(-0.3, -1.5, 0.4), mass: 0.42 }
    ]
  },
  {
    id: 'sub2',
    name: 'Sub-halo Beta',
    tubeRadius: 0.09,
    colorStart: new THREE.Color(0x34d399),
    colorEnd: new THREE.Color(0xfbbf24),
    pulseColor: 0xfef3c7,
    pulseCount: 9,
    pulseSpeed: 0.26,
    nodes: [
      { epochIdx: 1, pos: new THREE.Vector3(-3.8, 4.5, 1.8), mass: 0.19 },
      { epochIdx: 2, pos: new THREE.Vector3(-3.4, 1.5, -0.8), mass: 0.26 },
      { epochIdx: 3, pos: new THREE.Vector3(-2.1, -1.5, -1.9), mass: 0.33 },
      { epochIdx: 4, pos: new THREE.Vector3( 0.6, -4.5, -0.5), mass: 0.38 }
    ]
  },
  {
    id: 'sub3',
    name: 'Satellite Gamma',
    tubeRadius: 0.075,
    colorStart: new THREE.Color(0xf472b6),
    colorEnd: new THREE.Color(0xf97316),
    pulseColor: 0xffedd5,
    pulseCount: 7,
    pulseSpeed: 0.31,
    nodes: [
      { epochIdx: 2, pos: new THREE.Vector3( 3.6, 1.5, -2.0), mass: 0.18 },
      { epochIdx: 3, pos: new THREE.Vector3( 2.6, -1.5, -1.4), mass: 0.24 },
      { epochIdx: 4, pos: new THREE.Vector3( 1.5, -4.5, -0.9), mass: 0.29 },
      { epochIdx: 5, pos: new THREE.Vector3( 0.0, -7.5, 0.0), mass: 0.34 }
    ]
  }
];

function createGlowTexture(): THREE.CanvasTexture {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0.0, 'rgba(255, 255, 255, 1.0)');
  gradient.addColorStop(0.25, 'rgba(220, 248, 255, 0.85)');
  gradient.addColorStop(0.55, 'rgba(56, 189, 248, 0.25)');
  gradient.addColorStop(1.0, 'rgba(0, 0, 0, 0.0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  return texture;
}

function createBadgeSprite(text: string, colorHex: string = '#818cf8'): THREE.Sprite {
  const canvas = document.createElement('canvas');
  canvas.width = 160;
  canvas.height = 48;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.fillStyle = 'rgba(12, 18, 34, 0.88)';
    ctx.strokeStyle = colorHex;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.roundRect(4, 4, 152, 40, 20);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = colorHex;
    ctx.beginPath();
    ctx.arc(24, 24, 6, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#f8fafc';
    ctx.font = 'bold 18px monospace';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, 38, 25);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(12, 3.6, 1);
  return sprite;
}

function addStrutBetween(
  parent: THREE.Group,
  p1: THREE.Vector3,
  p2: THREE.Vector3,
  radius: number,
  colorHex: number,
  opacity: number
) {
  const dir = new THREE.Vector3().subVectors(p2, p1);
  const len = dir.length();
  if (len < 0.0001) return;
  const geo = new THREE.CylinderGeometry(radius, radius, len, 12);
  const mat = new THREE.MeshStandardMaterial({
    color: colorHex,
    emissive: colorHex,
    emissiveIntensity: 0.35,
    roughness: 0.4,
    transparent: true,
    opacity,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.copy(p1).addScaledVector(dir, 0.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
  parent.add(mesh);
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
  scrubberZ,
  onScrubberChange,
  isActive = true,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // 3D Visual & Viewport controls
  const [geometryMode, setGeometryMode] = useState<'sky_plane' | 'cone'>('sky_plane');
  const [fieldSpread, setFieldSpread] = useState<number>(135.0);
  const [minZ, setMinZ] = useState<number>(0.0);
  const [maxZ, setMaxZ] = useState<number>(9.0);
  const [showEpochShells, setShowEpochShells] = useState<boolean>(true);
  const [showGrid, setShowGrid] = useState<boolean>(true);
  const [showDropLines, setShowDropLines] = useState<boolean>(true);
  const [autoRotate, setAutoRotate] = useState<boolean>(false);
  const [isControlsOpen, setIsControlsOpen] = useState<boolean>(false);
  const [isTreeCardCollapsed, setIsTreeCardCollapsed] = useState<boolean>(false);

  // Lineage / Evolutionary Trajectory State
  const [showLineage, setShowLineage] = useState<boolean>(true);
  const [lineageStyle, setLineageStyle] = useState<'smooth_spline' | 'discrete_steps'>('smooth_spline');
  const lineageStyleRef = useRef(lineageStyle);
  lineageStyleRef.current = lineageStyle;
  const [hoveredNode, setHoveredNode] = useState<ProgenitorNode | null>(null);
  const [hoveredNodePos, setHoveredNodePos] = useState<{ x: number; y: number } | null>(null);

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
    hoverRing: THREE.Mesh | null;
    scrubberRing: THREE.Mesh | null;
    selectionDropLine: THREE.Line | null;
    discoveryRingsGroup: THREE.Group | null;
    gridGroup: THREE.Group | null;
    shellsGroup: THREE.Group | null;
    lineageGroup: THREE.Group | null;
    pulseParticles: Array<{
      sprite: THREE.Sprite;
      curve: THREE.CatmullRomCurve3;
      t: number;
      speed: number;
      baseScale: number;
    }>;
    epochDiscRings: THREE.Mesh[];
    backgroundStars: THREE.Points | null;
    particleTexture: THREE.CanvasTexture;
    glowTexture: THREE.CanvasTexture;
    galaxyPositions: Map<string, THREE.Vector3>;
    progenitorPositions: Array<{ node: ProgenitorNode; pos: THREE.Vector3 }>;
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
    } catch (err) {
      console.warn('[PerandamΨ] WebGL context creation failed in LightconeCanvas3D:', err);
      return;
    }

    // 1. Scene with dark cosmic nebula gradient
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x03050c);

    // 2. Camera: Symmetrical, centered view dynamically framed to fill 75-85% of canvas
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.5, 3000);
    const aspect = width / height;
    const initialCamDist = aspect > 1.5 ? 135 : 160;
    camera.position.set(30, 45, -130 + initialCamDist);

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

    // Hover Reticle Mesh (Vibrant cyan targeting ring)
    const hoverRingGeo = new THREE.RingGeometry(3.5, 4.5, 32);
    const hoverRingMat = new THREE.MeshBasicMaterial({
      color: 0x06b6d4,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.85,
    });
    const hoverRing = new THREE.Mesh(hoverRingGeo, hoverRingMat);
    hoverRing.visible = false;
    scene.add(hoverRing);

    // Cosmic Time Scrubber Horizon Ring (Active Time Slice indicator)
    const scrubberRingGeo = new THREE.RingGeometry(18.0, 19.5, 64);
    const scrubberRingMat = new THREE.MeshBasicMaterial({
      color: 0xf59e0b,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.7,
    });
    const scrubberRing = new THREE.Mesh(scrubberRingGeo, scrubberRingMat);
    scrubberRing.visible = true;
    scene.add(scrubberRing);

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

    // Groups for Progenitor Lineage trajectory
    const lineageGroup = new THREE.Group();
    scene.add(lineageGroup);

    const glowTexture = createGlowTexture();

    threeRef.current = {
      scene,
      camera,
      renderer,
      controls,
      pointsMesh: null,
      selectionRing,
      hoverRing,
      scrubberRing,
      selectionDropLine,
      discoveryRingsGroup,
      gridGroup,
      shellsGroup,
      lineageGroup,
      pulseParticles: [],
      epochDiscRings: [],
      backgroundStars,
      particleTexture,
      glowTexture,
      galaxyPositions: new Map(),
      progenitorPositions: [],
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

      // Billboard orientation for hover ring to face camera
      if (state.hoverRing && state.hoverRing.visible) {
        state.hoverRing.quaternion.copy(state.camera.quaternion);
        const pulse = 1.0 + 0.1 * Math.sin(currentTime * 0.008);
        state.hoverRing.scale.set(pulse, pulse, pulse);
      }

      // Billboard orientation for discovery rings
      if (state.discoveryRingsGroup) {
        state.discoveryRingsGroup.children.forEach((child, idx) => {
          child.quaternion.copy(state.camera.quaternion);
          const p = 1.0 + 0.15 * Math.sin(currentTime * 0.004 + idx);
          child.scale.set(p, p, p);
        });
      }

      // Update Option A traveling pulse particles along curves
      if (lineageStyleRef.current === 'smooth_spline' && state.pulseParticles.length > 0) {
        const pt = new THREE.Vector3();
        for (let i = 0; i < state.pulseParticles.length; i++) {
          const p = state.pulseParticles[i];
          p.t = (p.t + p.speed * delta) % 1.0;
          p.curve.getPointAt(p.t, pt);
          p.sprite.position.copy(pt);

          // Smooth edge fade and mass growth from high-z to low-z
          const edgeFade = Math.sin(p.t * Math.PI);
          const massGrowth = 0.75 + 0.55 * p.t;
          const s = p.baseScale * massGrowth * (0.65 + 0.35 * edgeFade);
          p.sprite.scale.set(s, s, 1);
          p.sprite.material.opacity = 0.25 + 0.75 * edgeFade;
        }
      } else if (lineageStyleRef.current === 'discrete_steps' && state.epochDiscRings.length > 0) {
        // Subtle pulse on Option B's discrete epoch disc rings
        const pulse = 0.65 + 0.3 * Math.sin(currentTime * 0.004);
        for (let i = 0; i < state.epochDiscRings.length; i++) {
          (state.epochDiscRings[i].material as THREE.MeshBasicMaterial).opacity = pulse;
        }
      }

      if (containerRef.current && containerRef.current.clientWidth > 10 && containerRef.current.clientHeight > 10) {
        state.renderer.render(state.scene, state.camera);
      }
      state.animFrameId = requestAnimationFrame(animate);
    };

    threeRef.current.animFrameId = requestAnimationFrame(animate);

    // Robust Resize Handler with strictly non-zero dimension guarding
    const handleResize = () => {
      if (!containerRef.current || !threeRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      // Guard against 0 or negative dimensions during CSS layout transitions to prevent NaN matrices
      if (!w || !h || w <= 10 || h <= 10) return;
      threeRef.current.camera.aspect = w / h;
      threeRef.current.camera.updateProjectionMatrix();
      threeRef.current.renderer.setSize(w, h);
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);
    window.addEventListener('resize', handleResize);

    // Initial settle passes to ensure full viewport dimensions are captured
    const timer1 = setTimeout(handleResize, 50);
    const timer2 = setTimeout(handleResize, 180);

    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
      resizeObserver.disconnect();
      window.removeEventListener('resize', handleResize);
      if (threeRef.current?.animFrameId) {
        cancelAnimationFrame(threeRef.current.animFrameId);
      }
      controls.dispose();
      renderer.dispose();
      particleTexture.dispose();
      threeRef.current = null;
    };
  }, []);

  // When tab becomes active, sync dimensions and trigger immediate render
  useEffect(() => {
    if (isActive && threeRef.current && containerRef.current) {
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      if (w > 10 && h > 10) {
        threeRef.current.camera.aspect = w / h;
        threeRef.current.camera.updateProjectionMatrix();
        threeRef.current.renderer.setSize(w, h);
        threeRef.current.renderer.render(threeRef.current.scene, threeRef.current.camera);
      }
    }
  }, [isActive]);

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

  // Update Cosmic Merger Tree 3D Trajectory (Option A vs Option B)
  useEffect(() => {
    const state = threeRef.current;
    if (!state || !state.lineageGroup) return;

    const lineageGrp = state.lineageGroup;

    // 1. Clear previous lineage meshes
    while (lineageGrp.children.length > 0) {
      const obj = lineageGrp.children.pop()!;
      if (obj instanceof THREE.Mesh || obj instanceof THREE.Line || obj instanceof THREE.Sprite || obj instanceof THREE.Group) {
        if ('geometry' in obj && obj.geometry) {
          (obj.geometry as THREE.BufferGeometry).dispose();
        }
        if ('material' in obj && obj.material) {
          if (Array.isArray(obj.material)) {
            obj.material.forEach((m) => m.dispose());
          } else {
            (obj.material as THREE.Material).dispose();
          }
        }
      }
    }

    state.pulseParticles = [];
    state.epochDiscRings = [];

    if (!showLineage) return;

    const TREE_SCALE = 5.2;
    const TREE_CENTER = new THREE.Vector3(0, 0, -130);

    // 2. Build Shared Reference Guides (Vertical axis + arrow cone + horizontal epoch slice rings)
    const axisX = TREE_CENTER.x - 5.6 * TREE_SCALE;
    const axisZ = TREE_CENTER.z;

    // Vertical cosmic redshift guide line
    const axisPoints = [
      new THREE.Vector3(axisX, TREE_CENTER.y + EPOCHS_TREE[0].y * TREE_SCALE + 4.0, axisZ),
      new THREE.Vector3(axisX, TREE_CENTER.y + EPOCHS_TREE[EPOCHS_TREE.length - 1].y * TREE_SCALE - 4.0, axisZ)
    ];
    const axisGeo = new THREE.BufferGeometry().setFromPoints(axisPoints);
    const axisMat = new THREE.LineBasicMaterial({
      color: 0x475569,
      transparent: true,
      opacity: 0.65
    });
    lineageGrp.add(new THREE.Line(axisGeo, axisMat));

    // Downward arrow cone at z = 0.0 indicating flow direction
    const coneGeo = new THREE.ConeGeometry(0.16 * TREE_SCALE, 0.45 * TREE_SCALE, 16);
    coneGeo.rotateX(Math.PI);
    const coneMat = new THREE.MeshBasicMaterial({ color: 0xfbbf24 });
    const cone = new THREE.Mesh(coneGeo, coneMat);
    cone.position.set(axisX, TREE_CENTER.y + EPOCHS_TREE[EPOCHS_TREE.length - 1].y * TREE_SCALE - 4.5, axisZ);
    lineageGrp.add(cone);

    // Epoch slice rings and axis tick spheres
    EPOCHS_TREE.forEach((ep, idx) => {
      const ringGeo = new THREE.RingGeometry(4.75 * TREE_SCALE, 4.82 * TREE_SCALE, 64);
      ringGeo.rotateX(-Math.PI / 2);
      const ringMat = new THREE.MeshBasicMaterial({
        color: ep.color,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: idx === 0 || idx === EPOCHS_TREE.length - 1 ? 0.24 : 0.11
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.position.set(TREE_CENTER.x, TREE_CENTER.y + ep.y * TREE_SCALE, TREE_CENTER.z);
      lineageGrp.add(ring);

      const tickGeo = new THREE.SphereGeometry(0.12 * TREE_SCALE, 12, 12);
      const tickMat = new THREE.MeshBasicMaterial({ color: ep.color });
      const tick = new THREE.Mesh(tickGeo, tickMat);
      tick.position.set(axisX, TREE_CENTER.y + ep.y * TREE_SCALE, axisZ);
      lineageGrp.add(tick);
    });

    // 3. Render Option A or Option B
    if (lineageStyle === 'smooth_spline') {
      // OPTION A: Smooth Glowing Catmull-Rom Spline Tubes + Traveling Mass Flow Particles
      MERGER_BRANCHES.forEach((branch) => {
        const points = branch.nodes.map(
          (n) => new THREE.Vector3(
            TREE_CENTER.x + n.pos.x * TREE_SCALE,
            TREE_CENTER.y + n.pos.y * TREE_SCALE,
            TREE_CENTER.z + n.pos.z * TREE_SCALE
          )
        );

        const curve = new THREE.CatmullRomCurve3(points, false, 'centripetal', 0.5);

        // Core glowing tube with vertex color gradient
        const tubularSegments = 96;
        const radialSegments = 16;
        const tubeRadius = branch.tubeRadius * TREE_SCALE;
        const tubeGeo = new THREE.TubeGeometry(curve, tubularSegments, tubeRadius, radialSegments, false);

        const posAttr = tubeGeo.attributes.position;
        const colors = new Float32Array(posAttr.count * 3);
        const tempColor = new THREE.Color();
        for (let i = 0; i < posAttr.count; i++) {
          const ringIdx = Math.floor(i / (radialSegments + 1));
          const t = Math.min(1, ringIdx / tubularSegments);
          tempColor.copy(branch.colorStart).lerp(branch.colorEnd, t);
          colors[i * 3]     = tempColor.r;
          colors[i * 3 + 1] = tempColor.g;
          colors[i * 3 + 2] = tempColor.b;
        }
        tubeGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const tubeMat = new THREE.MeshStandardMaterial({
          vertexColors: true,
          emissive: branch.colorStart,
          emissiveIntensity: 0.55,
          roughness: 0.25,
          metalness: 0.1,
          transparent: true,
          opacity: 0.92
        });
        lineageGrp.add(new THREE.Mesh(tubeGeo, tubeMat));

        // Outer halo tube for additive glow
        const haloGeo = new THREE.TubeGeometry(curve, tubularSegments, tubeRadius * 2.25, radialSegments, false);
        const haloMat = new THREE.MeshBasicMaterial({
          color: branch.colorStart,
          transparent: true,
          opacity: 0.18,
          blending: THREE.AdditiveBlending,
          depthWrite: false
        });
        lineageGrp.add(new THREE.Mesh(haloGeo, haloMat));

        // Soft spherical progenitor nodes
        branch.nodes.forEach((node) => {
          const ep = EPOCHS_TREE[node.epochIdx];
          const nodeGeo = new THREE.SphereGeometry(node.mass * 0.42 * TREE_SCALE, 20, 20);
          const nodeMat = new THREE.MeshStandardMaterial({
            color: 0xffffff,
            emissive: ep.color,
            emissiveIntensity: 0.85,
            roughness: 0.2
          });
          const nodeMesh = new THREE.Mesh(nodeGeo, nodeMat);
          nodeMesh.position.set(
            TREE_CENTER.x + node.pos.x * TREE_SCALE,
            TREE_CENTER.y + node.pos.y * TREE_SCALE,
            TREE_CENTER.z + node.pos.z * TREE_SCALE
          );
          lineageGrp.add(nodeMesh);
        });

        // Animated traveling pulse sprites
        for (let p = 0; p < branch.pulseCount; p++) {
          const spriteMat = new THREE.SpriteMaterial({
            map: state.glowTexture,
            color: branch.pulseColor,
            transparent: true,
            blending: THREE.AdditiveBlending,
            depthWrite: false
          });
          const sprite = new THREE.Sprite(spriteMat);
          const baseScale = tubeRadius * 5.2;
          sprite.scale.set(baseScale, baseScale, 1);
          lineageGrp.add(sprite);

          state.pulseParticles.push({
            sprite,
            curve,
            t: p / branch.pulseCount,
            speed: branch.pulseSpeed,
            baseScale
          });
        }
      });

      // Option A 3D Billboarded Badges (as seen in screenshot 1)
      const badge1 = createBadgeSprite('z = 4.0', '#38bdf8');
      badge1.position.set(TREE_CENTER.x - 3.4 * TREE_SCALE, TREE_CENTER.y + 4.5 * TREE_SCALE, TREE_CENTER.z);
      lineageGrp.add(badge1);

      const badge2 = createBadgeSprite('z = 2.2', '#22d3ee');
      badge2.position.set(TREE_CENTER.x - 3.8 * TREE_SCALE, TREE_CENTER.y + 1.5 * TREE_SCALE, TREE_CENTER.z);
      lineageGrp.add(badge2);

    } else {
      // OPTION B: Stepped Polygonal Segments + Octahedron Joints + Discrete Epoch Discs
      MERGER_BRANCHES.forEach((branch) => {
        // 1. Stepped struts between discrete snapshots
        for (let i = 0; i < branch.nodes.length - 1; i++) {
          const start = branch.nodes[i].pos;
          const end = branch.nodes[i + 1].pos;

          const sPt = new THREE.Vector3(
            TREE_CENTER.x + start.x * TREE_SCALE,
            TREE_CENTER.y + start.y * TREE_SCALE,
            TREE_CENTER.z + start.z * TREE_SCALE
          );
          const ePt = new THREE.Vector3(
            TREE_CENTER.x + end.x * TREE_SCALE,
            TREE_CENTER.y + end.y * TREE_SCALE,
            TREE_CENTER.z + end.z * TREE_SCALE
          );
          const midStep = new THREE.Vector3(ePt.x, sPt.y, ePt.z);

          const segPoints = [sPt, midStep, ePt];
          const lineGeo = new THREE.BufferGeometry().setFromPoints(segPoints);
          const lineMat = new THREE.LineBasicMaterial({
            color: EPOCHS_TREE[branch.nodes[i].epochIdx].color,
            linewidth: 2
          });
          lineageGrp.add(new THREE.Line(lineGeo, lineMat));

          const strutRadius = branch.tubeRadius * TREE_SCALE * 0.55;
          addStrutBetween(lineageGrp, sPt, midStep, strutRadius, EPOCHS_TREE[branch.nodes[i].epochIdx].color, 0.85);
          addStrutBetween(lineageGrp, midStep, ePt, strutRadius, EPOCHS_TREE[branch.nodes[i + 1].epochIdx].color, 0.85);

          // Octahedron corner joint
          const jointGeo = new THREE.OctahedronGeometry(branch.tubeRadius * TREE_SCALE * 0.9, 0);
          const jointMat = new THREE.MeshBasicMaterial({
            color: 0x94a3b8,
            wireframe: true
          });
          const jointMesh = new THREE.Mesh(jointGeo, jointMat);
          jointMesh.position.copy(midStep);
          lineageGrp.add(jointMesh);
        }

        // 2. Discrete Epoch Discs at each snapshot position
        branch.nodes.forEach((node) => {
          const ep = EPOCHS_TREE[node.epochIdx];
          const discRadius = node.mass * 0.65 * TREE_SCALE;

          const discGroup = new THREE.Group();
          discGroup.position.set(
            TREE_CENTER.x + node.pos.x * TREE_SCALE,
            TREE_CENTER.y + node.pos.y * TREE_SCALE,
            TREE_CENTER.z + node.pos.z * TREE_SCALE
          );

          // Solid cylindrical epoch disc
          const cylGeo = new THREE.CylinderGeometry(discRadius, discRadius, 0.09 * TREE_SCALE, 32);
          const cylMat = new THREE.MeshStandardMaterial({
            color: ep.color,
            emissive: ep.color,
            emissiveIntensity: 0.45,
            roughness: 0.3,
            metalness: 0.4
          });
          discGroup.add(new THREE.Mesh(cylGeo, cylMat));

          // Torus bevel ring around disc
          const torusGeo = new THREE.TorusGeometry(discRadius * 1.12, 0.025 * TREE_SCALE, 12, 36);
          torusGeo.rotateX(Math.PI / 2);
          const torusMat = new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: 0.85
          });
          const torusMesh = new THREE.Mesh(torusGeo, torusMat);
          discGroup.add(torusMesh);

          lineageGrp.add(discGroup);
          state.epochDiscRings.push(torusMesh);
        });
      });

      // Option B 3D Billboarded Badges (right aligned, as seen in screenshot 2)
      const rightX = TREE_CENTER.x + 5.6 * TREE_SCALE;
      const bZ6 = createBadgeSprite('z = 6.0', '#818cf8');
      bZ6.position.set(rightX, TREE_CENTER.y + 7.5 * TREE_SCALE, TREE_CENTER.z);
      lineageGrp.add(bZ6);

      const bZ4 = createBadgeSprite('z = 4.0', '#38bdf8');
      bZ4.position.set(rightX, TREE_CENTER.y + 4.5 * TREE_SCALE, TREE_CENTER.z);
      lineageGrp.add(bZ4);

      const bZ2 = createBadgeSprite('z = 2.2', '#22d3ee');
      bZ2.position.set(rightX, TREE_CENTER.y + 1.5 * TREE_SCALE, TREE_CENTER.z);
      lineageGrp.add(bZ2);

      const bZ1 = createBadgeSprite('z = 1.0', '#34d399');
      bZ1.position.set(rightX, TREE_CENTER.y - 1.5 * TREE_SCALE, TREE_CENTER.z);
      lineageGrp.add(bZ1);
    }
  }, [showLineage, lineageStyle]);

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
    camera.position.set(0, 75, 45);
    controls.target.set(0, 0, -130);
    controls.update();
  }, [resetTrigger]);

  // View Presets
  const setPresetView = (type: 'front' | 'isometric' | 'profile') => {
    if (!threeRef.current) return;
    const { camera, controls } = threeRef.current;
    if (type === 'front') {
      // Front View: 2D Sky alignment
      camera.position.set(0, 0, 115);
      controls.target.set(0, 0, -130);
    } else if (type === 'isometric') {
      // Angled Cinematic 3D Lightcone Perspective
      camera.position.set(55, 45, 10);
      controls.target.set(0, 0, -130);
    } else if (type === 'profile') {
      // Side-on Redshift Depth Profile
      camera.position.set(190, 0, -130);
      controls.target.set(0, 0, -130);
    }
    controls.update();
  };

  // Update Cosmic Time Scrubber Horizon Ring position in 3D
  useEffect(() => {
    const state = threeRef.current;
    if (!state || !state.scrubberRing) return;
    const maxZ = 9.0;
    const maxDistanceMpc = comovingDistanceMpc(maxZ);
    const sceneDepth = 260;
    const currentZ = scrubberZ ?? 0.0;
    const dMpc = comovingDistanceMpc(currentZ);
    const zNorm = (dMpc / maxDistanceMpc) * sceneDepth;
    state.scrubberRing.position.set(0, 0, -zNorm);
  }, [scrubberZ]);

  // Reset Camera specifically for 3D Merger Tree viewing (Centered & Full Canvas)
  const resetTrajectoryCamera = useCallback(() => {
    if (!threeRef.current) return;
    const { camera, controls } = threeRef.current;
    const w = containerRef.current?.clientWidth || 1000;
    const h = containerRef.current?.clientHeight || 600;
    const aspect = w / h;
    const initialCamDist = aspect > 1.5 ? 135 : 160;
    camera.position.set(30, 45, -130 + initialCamDist);
    controls.target.set(0, 0, -130);
    controls.update();
  }, []);

  // Keyboard shortcut: Space toggles Option A / Option B
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeTag = (document.activeElement as HTMLElement)?.tagName?.toLowerCase();
      if (activeTag === 'input' || activeTag === 'textarea' || activeTag === 'select') return;
      if (e.code === 'Space') {
        e.preventDefault();
        setLineageStyle((prev) => (prev === 'smooth_spline' ? 'discrete_steps' : 'smooth_spline'));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Raycasting for Mouse Hover & Selection
  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const state = threeRef.current;
    if (!state || !state.pointsMesh || !containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const mouseY = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    const raycaster = new THREE.Raycaster();
    raycaster.params.Points.threshold = 12.0; // Generous hover threshold so mouse hover immediately catches galaxy
    raycaster.setFromCamera(new THREE.Vector2(mouseX, mouseY), state.camera);

    const intersects = raycaster.intersectObject(state.pointsMesh);

    if (intersects.length > 0) {
      const index = intersects[0].index;
      if (typeof index === 'number' && index < visibleGalaxies.length) {
        const found = visibleGalaxies[index];
        setHoveredGalaxy(found);
        setTooltipPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
        setHoveredNode(null);
        setHoveredNodePos(null);

        // Show mouse pointer that this is a clickable area
        if (canvasRef.current) {
          canvasRef.current.style.cursor = 'pointer';
        }
        if (containerRef.current) {
          containerRef.current.style.cursor = 'pointer';
        }

        // Position 3D hover ring at galaxy coordinates
        const pos = state.galaxyPositions?.get(found.id);
        if (pos && state.hoverRing) {
          state.hoverRing.position.copy(pos);
          state.hoverRing.visible = true;
        }
        return;
      }
    }

    // Check Progenitor Node Hover
    if (state.progenitorPositions && state.progenitorPositions.length > 0) {
      for (const item of state.progenitorPositions) {
        const screenPos = item.pos.clone().project(state.camera);
        const sx = ((screenPos.x + 1) / 2) * rect.width;
        const sy = ((-screenPos.y + 1) / 2) * rect.height;
        const dist = Math.hypot(e.clientX - rect.left - sx, e.clientY - rect.top - sy);
        if (dist < 18) {
          setHoveredNode(item.node);
          setHoveredNodePos({ x: sx, y: sy });
          setHoveredGalaxy(null);
          setTooltipPos(null);
          if (state.hoverRing) state.hoverRing.visible = false;
          if (canvasRef.current) canvasRef.current.style.cursor = 'pointer';
          if (containerRef.current) containerRef.current.style.cursor = 'pointer';
          return;
        }
      }
    }

    setHoveredNode(null);
    setHoveredNodePos(null);
    setHoveredGalaxy(null);
    setTooltipPos(null);
    if (state.hoverRing) {
      state.hoverRing.visible = false;
    }
    if (canvasRef.current) {
      canvasRef.current.style.cursor = 'default';
    }
    if (containerRef.current) {
      containerRef.current.style.cursor = 'default';
    }
  };

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const state = threeRef.current;
    if (!state || !state.pointsMesh || !containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const mouseY = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    const raycaster = new THREE.Raycaster();
    raycaster.params.Points.threshold = 14.0; // Generous click threshold
    raycaster.setFromCamera(new THREE.Vector2(mouseX, mouseY), state.camera);

    const intersects = raycaster.intersectObject(state.pointsMesh);
    if (intersects.length > 0) {
      const index = intersects[0].index;
      if (typeof index === 'number' && index < visibleGalaxies.length) {
        const target = visibleGalaxies[index];
        onSelectGalaxy(target);
        setHoveredGalaxy(null);
        setTooltipPos(null);
        if (state.hoverRing) state.hoverRing.visible = false;
        return;
      }
    }

    if (hoveredGalaxy) {
      onSelectGalaxy(hoveredGalaxy);
      setHoveredGalaxy(null);
      setTooltipPos(null);
      if (state.hoverRing) state.hoverRing.visible = false;
    }
  };

  return (
    <div ref={containerRef} className="w-full h-full relative overflow-hidden bg-cosmos-950 select-none">
      {/* 3D WebGL Canvas */}
      <canvas
        ref={canvasRef}
        onPointerMove={handlePointerMove}
        onClick={handleClick}
        className="w-full h-full block touch-none"
      />

      {/* Top-Left: Consolidated Cosmic Merger Tree 3D Card */}
      <div className="absolute top-4 left-4 z-20 pointer-events-none flex flex-col gap-2 max-w-sm sm:max-w-md select-none">
        <div className="bg-slate-900/90 backdrop-blur-md border border-slate-700/70 rounded-2xl p-4 shadow-2xl pointer-events-auto">
          {/* Header row: Title + Spacebar Hint + Collapse Toggle */}
          <div className="flex items-center justify-between gap-3 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-cyan-400">
              Cosmic Merger Tree 3D
            </span>
            <div className="flex items-center space-x-1.5">
              <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">
                Press <kbd className="px-1 py-0.5 bg-slate-800 rounded border border-slate-700 text-slate-200">Space</kbd>
              </span>
              <button
                type="button"
                onClick={() => setIsTreeCardCollapsed((prev) => !prev)}
                className="p-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition cursor-pointer"
                title={isTreeCardCollapsed ? "Expand card description" : "Collapse card description"}
              >
                {isTreeCardCollapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          {/* Segmented Switch Control: Option A vs Option B */}
          <div
            className="relative grid grid-cols-2 bg-slate-950/90 p-1 rounded-xl border border-slate-700/80 mb-2.5"
            role="group"
            aria-label="Visualization Mode Toggle"
          >
            {/* Animated Sliding Highlight */}
            <div
              className={`absolute top-1 bottom-1 w-[calc(50%-4px)] rounded-lg shadow-lg transition-all duration-300 ease-out ${
                lineageStyle === 'smooth_spline'
                  ? 'left-1 bg-gradient-to-r from-cyan-500 to-blue-600 shadow-cyan-500/25'
                  : 'left-[calc(50%+2px)] bg-gradient-to-r from-emerald-500 to-teal-600 shadow-emerald-500/25'
              }`}
            />

            <button
              type="button"
              onClick={() => setLineageStyle('smooth_spline')}
              className={`relative z-10 py-1.5 px-2 text-xs font-semibold rounded-lg transition-colors flex items-center justify-center gap-1.5 cursor-pointer ${
                lineageStyle === 'smooth_spline' ? 'text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              <span>Option A</span>
              <span className="text-[10px] font-normal opacity-85 hidden sm:inline">(Smooth Spline)</span>
            </button>

            <button
              type="button"
              onClick={() => setLineageStyle('discrete_steps')}
              className={`relative z-10 py-1.5 px-2 text-xs font-semibold rounded-lg transition-colors flex items-center justify-center gap-1.5 cursor-pointer ${
                lineageStyle === 'discrete_steps' ? 'text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              <span>Option B</span>
              <span className="text-[10px] font-normal opacity-85 hidden sm:inline">(Stepped + Discs)</span>
            </button>
          </div>

          {!isTreeCardCollapsed && (
            <>
              <h1 className="text-sm sm:text-base font-bold text-white leading-tight">
                {lineageStyle === 'smooth_spline'
                  ? 'Smooth Catmull-Rom Spline + Mass Flow'
                  : 'Stepped Segments + Discrete Epoch Discs'}
              </h1>
              <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                {lineageStyle === 'smooth_spline'
                  ? 'Continuous glowing 3D curves interpolate progenitor trajectories with animated particles showing accretion from high-z to low-z.'
                  : 'Polygonal stepped connectors highlight exact snapshot intervals while flat discs mark discrete redshift (z) epochs.'}
              </p>

              {/* Live Visual Indicators / Key Takeaways */}
              <div className="mt-2.5 pt-2.5 border-t border-slate-700/60 grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      lineageStyle === 'smooth_spline'
                        ? 'bg-cyan-400 shadow-[0_0_8px_#22d3ee]'
                        : 'bg-emerald-400 shadow-[0_0_8px_#34d399]'
                    }`}
                  />
                  <span className="text-slate-200 font-medium text-[11px]">
                    {lineageStyle === 'smooth_spline' ? 'Interpolated spline tube' : 'Stepped polygonal links'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      lineageStyle === 'smooth_spline'
                        ? 'bg-amber-400 shadow-[0_0_8px_#fbbf24]'
                        : 'bg-indigo-400 shadow-[0_0_8px_#818cf8]'
                    }`}
                  />
                  <span className="text-slate-200 font-medium text-[11px]">
                    {lineageStyle === 'smooth_spline' ? 'Traveling mass pulses' : 'Discrete epoch discs'}
                  </span>
                </div>
              </div>
            </>
          )}

          {/* Integrated Action Buttons: Auto-Orbit & Reset View */}
          <div className="mt-2.5 pt-2.5 border-t border-slate-700/60 flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => setAutoRotate((prev) => !prev)}
              className="flex-1 py-1.5 px-2.5 rounded-lg text-xs font-medium bg-slate-800/80 hover:bg-slate-700 text-slate-200 border border-slate-700/80 transition flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <span
                className={`w-2 h-2 rounded-full transition-colors ${
                  autoRotate ? 'bg-emerald-400 shadow-[0_0_6px_#34d399]' : 'bg-slate-500'
                }`}
              />
              <span>Auto-Orbit</span>
            </button>
            <button
              type="button"
              onClick={resetTrajectoryCamera}
              className="py-1.5 px-3 rounded-lg text-xs font-medium bg-slate-800/80 hover:bg-slate-700 text-slate-200 border border-slate-700/80 transition cursor-pointer"
              title="Reset camera view to center merger tree"
            >
              Reset View
            </button>
          </div>
        </div>

        {/* Secondary View Presets & 3D Controls Pill */}
        <div className="flex items-center gap-1.5 pointer-events-auto">
          <div className="flex items-center bg-slate-900/80 border border-slate-700/60 rounded-xl p-1 shadow-lg backdrop-blur text-xs">
            <button
              onClick={() => setPresetView('front')}
              className="px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-cyan-300 font-medium transition-colors cursor-pointer"
              title="Front View: 2D Sky projection alignment"
            >
              Sky
            </button>
            <button
              onClick={() => setPresetView('isometric')}
              className="px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-cyan-300 font-medium transition-colors cursor-pointer"
              title="Isometric 3D Lightcone Perspective"
            >
              Isometric
            </button>
            <button
              onClick={() => setPresetView('profile')}
              className="px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-cyan-300 font-medium transition-colors cursor-pointer"
              title="Side Depth Profile"
            >
              Profile
            </button>
            <button
              onClick={resetTrajectoryCamera}
              className="px-2 py-0.5 rounded hover:bg-slate-800 text-cyan-300 hover:text-white font-medium transition-colors cursor-pointer border-l border-slate-700/80 pl-2"
              title="Fit & Frame: Auto-scale Lightcone to fill the entire screen"
            >
              Fit
            </button>
            <button
              onClick={() => setIsControlsOpen((prev) => !prev)}
              className={`ml-1 pl-1.5 border-l border-slate-700 flex items-center space-x-1 px-2 py-0.5 rounded transition-colors cursor-pointer ${
                isControlsOpen ? 'bg-cyan-900/60 text-cyan-200' : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Open 3D cosmological parameter drawer"
            >
              <Sliders className="w-3 h-3 text-cyan-400" />
              <span>Params</span>
            </button>
          </div>
        </div>
      </div>

      {/* Bottom-Left: Cosmic Time / Redshift Axis Bar */}
      <div className="hidden sm:flex absolute bottom-24 left-4 z-20 bg-slate-900/85 backdrop-blur-md border border-slate-700/60 rounded-2xl px-4 py-2.5 items-center gap-3 pointer-events-none shadow-xl select-none">
        <div className="flex flex-col">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
            Cosmic Time / Redshift Axis
          </span>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs font-semibold text-indigo-300">z = 6.0 (Early)</span>
            <div className="w-28 h-2 rounded-full bg-gradient-to-r from-indigo-500 via-cyan-400 to-amber-400" />
            <span className="text-xs font-semibold text-amber-300">z = 0.0 (Today)</span>
          </div>
        </div>
      </div>

      {/* 3D Settings & Redshift Filter Panel (Dropdown / Drawer) */}
      {isControlsOpen && (
        <div className="absolute top-44 left-4 z-30 w-80 bg-cosmos-900/95 border border-cosmos-700/80 rounded-xl p-4 shadow-2xl backdrop-blur text-xs text-slate-200 space-y-3.5 animate-in fade-in duration-150">
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
              min="50"
              max="240"
              step="5"
              value={fieldSpread}
              onChange={(e) => setFieldSpread(Number(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-500 mt-0.5">
              <span>Compact (50)</span>
              <span>Standard (135)</span>
              <span>Expansive (240)</span>
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

      {/* Sleek, Non-Obtrusive Clickable Hover Pill with direct onClick */}
      {hoveredGalaxy && tooltipPos && (
        <div
          onClick={(e) => {
            e.stopPropagation();
            onSelectGalaxy(hoveredGalaxy);
            setHoveredGalaxy(null);
            setTooltipPos(null);
          }}
          className="absolute z-30 cursor-pointer pointer-events-auto bg-cosmos-950/95 border border-cyan-400 rounded-lg px-3 py-1.5 shadow-2xl backdrop-blur text-xs font-mono text-cyan-200 transform -translate-x-1/2 -translate-y-full -mt-3 flex items-center space-x-2 transition-transform hover:scale-105"
          style={{ left: `${tooltipPos.x}px`, top: `${tooltipPos.y}px` }}
          title="Click to inspect this galaxy in detail"
        >
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span className="font-bold text-slate-100">{hoveredGalaxy.id}</span>
          <span className="text-slate-500">•</span>
          <span className="text-amber-300 font-semibold">z = {hoveredGalaxy.redshift.toFixed(2)}</span>
          <span className="text-slate-500">•</span>
          <span className="text-[11px] text-cyan-300 font-sans font-bold flex items-center gap-1 hover:underline">
            Click to inspect →
          </span>
        </div>
      )}

      {/* Progenitor Lineage Node Hover Tooltip */}
      {hoveredNode && hoveredNodePos && (
        <div
          className="absolute z-30 pointer-events-none bg-cosmos-900/95 border border-amber-500/80 rounded-xl p-3 shadow-2xl backdrop-blur text-xs w-64 transform -translate-x-1/2 -translate-y-full mb-3"
          style={{ left: `${hoveredNodePos.x}px`, top: `${hoveredNodePos.y}px` }}
        >
          <div className="flex items-center justify-between pb-1 mb-1.5 border-b border-cosmos-700">
            <span className="font-mono font-bold text-amber-300 flex items-center space-x-1">
              <GitBranch className="w-3.5 h-3.5 text-amber-400" />
              <span>Progenitor Snapshot</span>
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-950 border border-amber-700 text-amber-200 font-mono">
              z = {hoveredNode.redshift.toFixed(2)}
            </span>
          </div>

          <div className="space-y-1 text-slate-300 text-[11px]">
            <div className="flex justify-between">
              <span className="text-slate-400">Lookback Time:</span>
              <span className="font-mono text-cyan-300 font-medium">
                ~{hoveredNode.lookback_time_gyr.toFixed(1)} Gyr
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Cosmic Age:</span>
              <span className="font-mono text-slate-200">
                t ≈ {hoveredNode.cosmic_time_gyr.toFixed(2)} Gyr
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Stellar Mass:</span>
              <span className="font-mono text-emerald-400 font-semibold">
                {hoveredNode.stellar_mass_msun.toExponential(2)} M☉
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Star Formation:</span>
              <span className="font-mono text-slate-200">
                {hoveredNode.sfr_msun_per_yr.toFixed(1)} M☉/yr
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Half-Mass Radius:</span>
              <span className="font-mono text-slate-200">
                r_1/2 ≈ {hoveredNode.half_mass_radius_kpc.toFixed(2)} kpc
              </span>
            </div>
          </div>
          <div className="mt-2 text-[10px] text-amber-400 text-center font-medium">
            Evolutionary Lineage Node (Main Branch)
          </div>
        </div>
      )}
    </div>
  );
};
