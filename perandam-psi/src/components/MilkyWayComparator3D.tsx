import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { Galaxy } from '../types/galaxy.ts';
import {
  MILKY_WAY_BENCHMARK,
  MILKY_WAY_GALAXY,
  compareWithMilkyWay,
  estimatePhysicalRadiusKpc,
} from '../utils/milkyway.ts';
import { lookbackTimeGyr } from '../utils/cosmo3d.ts';
import {
  Sparkles,
  Orbit,
  Scale,
  Copy,
  Check,
  Flame,
  Layers,
  Plus,
  X,
  ArrowLeftRight,
  Clock,
  RotateCcw,
  Sliders,
} from 'lucide-react';

export interface SlotTheme {
  name: string;
  hex: string;
  threeColor: number;
  badgeBorder: string;
  badgeText: string;
  accent: string;
  tailColor: string;
  bgRgba: string;
}

export const SLOT_THEMES: SlotTheme[] = [
  { name: 'Amber', hex: '#f59e0b', threeColor: 0xf59e0b, badgeBorder: '#f59e0b', badgeText: '#fef08a', accent: '#f59e0b', tailColor: 'text-amber-300', bgRgba: 'rgba(245, 158, 11, 0.12)' },
  { name: 'Cyan', hex: '#06b6d4', threeColor: 0x06b6d4, badgeBorder: '#06b6d4', badgeText: '#38bdf8', accent: '#06b6d4', tailColor: 'text-cyan-300', bgRgba: 'rgba(6, 182, 212, 0.12)' },
  { name: 'Emerald', hex: '#10b981', threeColor: 0x10b981, badgeBorder: '#10b981', badgeText: '#6ee7b7', accent: '#10b981', tailColor: 'text-emerald-300', bgRgba: 'rgba(16, 185, 129, 0.12)' },
  { name: 'Purple', hex: '#a855f7', threeColor: 0xa855f7, badgeBorder: '#a855f7', badgeText: '#d8b4fe', accent: '#a855f7', tailColor: 'text-purple-300', bgRgba: 'rgba(168, 85, 247, 0.12)' },
  { name: 'Rose', hex: '#f43f5e', threeColor: 0xf43f5e, badgeBorder: '#f43f5e', badgeText: '#fda4af', accent: '#f43f5e', tailColor: 'text-rose-300', bgRgba: 'rgba(244, 63, 94, 0.12)' },
  { name: 'Blue', hex: '#3b82f6', threeColor: 0x3b82f6, badgeBorder: '#3b82f6', badgeText: '#93c5fd', accent: '#3b82f6', tailColor: 'text-blue-300', bgRgba: 'rgba(59, 130, 246, 0.12)' },
  { name: 'Lime', hex: '#84cc16', threeColor: 0x84cc16, badgeBorder: '#84cc16', badgeText: '#bef264', accent: '#84cc16', tailColor: 'text-lime-300', bgRgba: 'rgba(132, 204, 22, 0.12)' },
  { name: 'Orange', hex: '#f97316', threeColor: 0xf97316, badgeBorder: '#f97316', badgeText: '#fdba74', accent: '#f97316', tailColor: 'text-orange-300', bgRgba: 'rgba(249, 115, 22, 0.12)' },
];

interface MilkyWayComparator3DProps {
  galaxy: Galaxy;
  allGalaxies: Galaxy[];
  onSelectGalaxy: (galaxy: Galaxy) => void;
  onClose?: () => void;
}

// Generate realistic star particle texture
function createStarParticleTexture(): THREE.CanvasTexture {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;

  const center = size / 2;
  const grad = ctx.createRadialGradient(center, center, 0, center, center, center * 0.9);
  grad.addColorStop(0, 'rgba(255, 255, 255, 1.0)');
  grad.addColorStop(0.2, 'rgba(235, 245, 255, 0.9)');
  grad.addColorStop(0.5, 'rgba(180, 215, 255, 0.4)');
  grad.addColorStop(0.85, 'rgba(100, 150, 255, 0.08)');
  grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  // Pinpoint stellar core
  ctx.beginPath();
  ctx.arc(center, center, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = '#ffffff';
  ctx.fill();

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

// Generate sleek sci-fi holographic floating text label (additive blending, 100% transparent background)
function createHologramLabelSprite(
  title: string,
  category: string,
  subtext: string,
  neonColor: string,
  secondaryColor: string
): THREE.Sprite {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 160;
  const ctx = canvas.getContext('2d')!;

  ctx.clearRect(0, 0, 512, 160);

  const w = 512;
  const h = 160;

  // Sci-fi holographic corner brackets [ ... ]
  ctx.strokeStyle = neonColor;
  ctx.lineWidth = 2.5;
  ctx.shadowColor = neonColor;
  ctx.shadowBlur = 10;

  const bracketSize = 22;
  const pad = 12;

  // Top-left
  ctx.beginPath();
  ctx.moveTo(pad, pad + bracketSize);
  ctx.lineTo(pad, pad);
  ctx.lineTo(pad + bracketSize, pad);
  ctx.stroke();

  // Top-right
  ctx.beginPath();
  ctx.moveTo(w - pad - bracketSize, pad);
  ctx.lineTo(w - pad, pad);
  ctx.lineTo(w - pad, pad + bracketSize);
  ctx.stroke();

  // Bottom-left
  ctx.beginPath();
  ctx.moveTo(pad, h - pad - bracketSize);
  ctx.lineTo(pad, h - pad);
  ctx.lineTo(pad + bracketSize, h - pad);
  ctx.stroke();

  // Bottom-right
  ctx.beginPath();
  ctx.moveTo(w - pad - bracketSize, h - pad);
  ctx.lineTo(w - pad, h - pad);
  ctx.lineTo(w - pad, h - pad - bracketSize);
  ctx.stroke();

  // Subtle tech crosshair notches
  ctx.beginPath();
  ctx.moveTo(pad - 4, h / 2);
  ctx.lineTo(pad + 6, h / 2);
  ctx.moveTo(w - pad - 6, h / 2);
  ctx.lineTo(w - pad + 4, h / 2);
  ctx.stroke();

  // Category Tag (small uppercase glowing header)
  ctx.shadowBlur = 8;
  ctx.fillStyle = neonColor;
  ctx.font = 'bold 18px monospace';
  ctx.fillText(`‹ ${category.toUpperCase()} ›`, 28, 42);

  // Main Galaxy Title (large, luminous)
  ctx.shadowBlur = 14;
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 36px sans-serif';
  ctx.fillText(title, 28, 88);

  // Subtitle / Primary Metric (crisp cyan/amber)
  ctx.shadowBlur = 6;
  ctx.fillStyle = secondaryColor;
  ctx.font = '18px monospace';
  ctx.fillText(subtext, 28, 126);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    blending: THREE.AdditiveBlending, // Key: glows like a true laser hologram!
    opacity: 0.95,
    depthTest: false,
    depthWrite: false,
  });

  const sprite = new THREE.Sprite(material);
  sprite.scale.set(16, 5, 1);
  return sprite;
}

// Build a complete 3D galaxy group (particles, pedestal, core beacon, laser guide, and holographic label)
function buildGalaxyModel(
  g: Galaxy,
  theme: SlotTheme,
  slotIndex: number,
  totalSlots: number,
  scaleMode: 'physical' | 'normalized',
  starTexture: THREE.CanvasTexture,
  showOrbits: boolean
): THREE.Group {
  const group = new THREE.Group();
  const isMilkyWay = g.id === 'MILKY_WAY';

  const mwBaseRadius = 26.0;
  let visualRadius = mwBaseRadius;

  if (isMilkyWay) {
    visualRadius = mwBaseRadius;
  } else if (scaleMode === 'physical') {
    const isQuenched = (g.discovery_profile?.classification === 'EARLY_QUENCHED_GIANT') || ((g.sfr / Math.pow(10, g.log_mstar)) < 1e-11);
    const rKpc = estimatePhysicalRadiusKpc(g.log_mstar, g.redshift, isQuenched);
    visualRadius = mwBaseRadius * Math.max(0.22, Math.min(2.4, rKpc / 4.2));
  } else {
    visualRadius = 24.0;
  }

  // Adjust particle count dynamically to preserve 60 FPS across 1-8 galaxies
  const nStars = totalSlots <= 2 ? 2600 : totalSlots <= 4 ? 2000 : 1500;
  const positions = new Float32Array(nStars * 3);
  const colors = new Float32Array(nStars * 3);
  const sizes = new Float32Array(nStars);

  const isLittleRedDot = g.discovery_profile?.classification === 'LITTLE_RED_DOT';
  const isStarburst = (g.sfr > 15) || (g.discovery_profile?.classification === 'COSMIC_NOON_SUPER_STARBURST');
  const isQuenched = (g.discovery_profile?.classification === 'EARLY_QUENCHED_GIANT') || ((g.sfr / Math.pow(10, g.log_mstar)) < 1e-11);
  const isDusty = (g.av > 1.2) || (g.discovery_profile?.classification === 'HST_DARK_MONSTER');

  // Check for empirical simulation-derived 3D particle data (M3.7 Truth in Labeling)
  const simStars = g.galaxy3d?.particles?.star || (g.galaxy3d?.particles as any)?.stars;
  const isSimDerived = g.galaxy3d?.geometry_source === 'simulation_derived' && simStars?.coordinates_kpc?.length > 0;

  if (isSimDerived && simStars) {
    // 0. Empirical Simulation-Derived Particle Geometry (P2 Milestone 3 Foundation)
    const count = Math.min(simStars.coordinates_kpc.length, nStars);
    const rHalfKpc = Math.max(0.5, g.galaxy3d?.half_mass_radius_kpc ?? 3.0);
    const coordScale = (visualRadius * 0.45) / rHalfKpc;

    for (let i = 0; i < count; i++) {
      const [x, y, z] = simStars.coordinates_kpc[i];
      // In Three.js, Y is vertical axis, X and Z are horizontal disk plane.
      // Simulation coords aligned J with +Z, so disk is in X-Y. Map (x, z, y) into Three.js:
      positions[i * 3] = x * coordScale;
      positions[i * 3 + 1] = z * coordScale;
      positions[i * 3 + 2] = y * coordScale;

      const ageGyr = (simStars.ages_yr?.[i] ?? 3.0e9) / 1.0e9;
      const metZ = simStars.metallicities_z?.[i] ?? 0.019;

      if (ageGyr < 0.6) {
        // Hot young OB stars: luminous blue-cyan
        colors[i * 3] = 0.45;
        colors[i * 3 + 1] = 0.78 + Math.random() * 0.15;
        colors[i * 3 + 2] = 1.0;
        sizes[i] = 5.2 + Math.random() * 2.5;
      } else if (ageGyr < 3.5) {
        // Intermediate main sequence: crisp ivory/white
        colors[i * 3] = 0.92;
        colors[i * 3 + 1] = 0.94;
        colors[i * 3 + 2] = 0.98;
        sizes[i] = 4.0 + Math.random() * 1.5;
      } else {
        // Old evolved giants: warm golden amber
        const redBoost = Math.min(0.2, (metZ / 0.02) * 0.1);
        colors[i * 3] = 1.0;
        colors[i * 3 + 1] = Math.max(0.4, 0.78 - redBoost);
        colors[i * 3 + 2] = Math.max(0.2, 0.42 - redBoost);
        sizes[i] = 3.6 + Math.random() * 1.8;
      }
    }
  } else if (isMilkyWay) {
    // 1. Milky Way: Barred Spiral with Bulge & Spiral Arms
    const nBulge = Math.floor(nStars * 0.35);
    for (let i = 0; i < nBulge; i++) {
      const isBar = i % 2 === 0;
      let x = 0, y = 0, z = 0;
      if (isBar) {
        x = (Math.random() - 0.5) * visualRadius * 0.45;
        y = (Math.random() - 0.5) * 1.8;
        z = (Math.random() - 0.5) * visualRadius * 0.16;
      } else {
        const r = Math.pow(Math.random(), 2.2) * (visualRadius * 0.28);
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        x = r * Math.sin(phi) * Math.cos(theta);
        y = r * Math.sin(phi) * Math.sin(theta) * 0.55;
        z = r * Math.cos(phi);
      }
      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;
      colors[i * 3] = 1.0;
      colors[i * 3 + 1] = 0.85 + Math.random() * 0.1;
      colors[i * 3 + 2] = 0.5 + Math.random() * 0.2;
      sizes[i] = 4.2 + Math.random() * 2.5;
    }

    const nDisk = nStars - nBulge;
    for (let i = 0; i < nDisk; i++) {
      const idx = nBulge + i;
      const armOffset = (i % 2) * Math.PI;
      const theta = Math.pow(Math.random(), 0.75) * (Math.PI * 2.8) + 0.5;
      const r = (visualRadius * 0.15) + (visualRadius * 0.85) * (theta / (Math.PI * 2.8));
      const spread = 1.2 * (r / visualRadius);
      const dx = (Math.random() - 0.5) * spread;
      const dz = (Math.random() - 0.5) * spread;
      const dy = (Math.random() - 0.5) * 0.8 * Math.exp(-r / visualRadius);

      const angle = theta + armOffset;
      positions[idx * 3] = r * Math.cos(angle) + dx;
      positions[idx * 3 + 1] = dy;
      positions[idx * 3 + 2] = r * Math.sin(angle) + dz;

      const isBlueClump = Math.random() < 0.45;
      const isDust = Math.random() < 0.12;
      if (isDust) {
        colors[idx * 3] = 0.65;
        colors[idx * 3 + 1] = 0.25;
        colors[idx * 3 + 2] = 0.15;
        sizes[idx] = 3.5;
      } else if (isBlueClump) {
        colors[idx * 3] = 0.55 + Math.random() * 0.2;
        colors[idx * 3 + 1] = 0.75 + Math.random() * 0.2;
        colors[idx * 3 + 2] = 1.0;
        sizes[idx] = 4.8 + Math.random() * 3.0;
      } else {
        colors[idx * 3] = 0.75;
        colors[idx * 3 + 1] = 0.9;
        colors[idx * 3 + 2] = 0.75;
        sizes[idx] = 3.2;
      }
    }
  } else if (isLittleRedDot) {
    // 2. Little Red Dot: Hyper-dense ruby-red core + infrared torus
    const nCore = Math.floor(nStars * 0.6);
    for (let i = 0; i < nCore; i++) {
      const r = Math.pow(Math.random(), 3.0) * (visualRadius * 0.28);
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
      colors[i * 3] = 1.0;
      colors[i * 3 + 1] = 0.25 + Math.random() * 0.2;
      colors[i * 3 + 2] = 0.35 + Math.random() * 0.3;
      sizes[i] = 5.5 + Math.random() * 3.5;
    }
    for (let i = nCore; i < nStars; i++) {
      const theta = Math.random() * Math.PI * 2;
      const r = visualRadius * 0.35 + (Math.random() - 0.5) * (visualRadius * 0.18);
      const y = (Math.random() - 0.5) * (visualRadius * 0.08);
      positions[i * 3] = r * Math.cos(theta);
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = r * Math.sin(theta);
      colors[i * 3] = 0.95;
      colors[i * 3 + 1] = 0.4;
      colors[i * 3 + 2] = 0.2;
      sizes[i] = 3.8;
    }
  } else if (isQuenched) {
    // 3. Early Quenched Giant: Spheroidal de Vaucouleurs ellipsoid
    for (let i = 0; i < nStars; i++) {
      const r = Math.pow(Math.random(), 2.0) * visualRadius;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.65;
      positions[i * 3 + 2] = r * Math.cos(phi);
      colors[i * 3] = 0.98;
      colors[i * 3 + 1] = 0.45 + Math.random() * 0.2;
      colors[i * 3 + 2] = 0.35;
      sizes[i] = 4.0;
    }
  } else if (isStarburst) {
    // 4. Super Starburst: Clumpy, turbulent disk with glowing UV knots
    for (let i = 0; i < nStars; i++) {
      const r = Math.pow(Math.random(), 0.8) * visualRadius;
      const theta = Math.random() * Math.PI * 2;
      const y = (Math.random() - 0.5) * 2.2;
      positions[i * 3] = r * Math.cos(theta);
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = r * Math.sin(theta);
      const isClump = Math.random() < 0.6;
      if (isClump) {
        colors[i * 3] = 0.35;
        colors[i * 3 + 1] = 0.85 + Math.random() * 0.15;
        colors[i * 3 + 2] = 1.0;
        sizes[i] = 6.0 + Math.random() * 4.0;
      } else {
        colors[i * 3] = 0.7;
        colors[i * 3 + 1] = 0.85;
        colors[i * 3 + 2] = 1.0;
        sizes[i] = 3.5;
      }
    }
  } else {
    // 5. Normal Disk / Progenitor Spiral
    const nCore = Math.floor(nStars * 0.25);
    for (let i = 0; i < nCore; i++) {
      const r = Math.pow(Math.random(), 2.0) * (visualRadius * 0.3);
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.5;
      positions[i * 3 + 2] = r * Math.cos(phi);
      colors[i * 3] = 1.0;
      colors[i * 3 + 1] = 0.85;
      colors[i * 3 + 2] = 0.45;
      sizes[i] = 4.5;
    }
    for (let i = nCore; i < nStars; i++) {
      const theta = Math.pow(Math.random(), 0.8) * (Math.PI * 2.5);
      const r = visualRadius * 0.2 + (visualRadius * 0.8) * (theta / (Math.PI * 2.5));
      const armAngle = theta + (i % 2) * Math.PI;
      positions[i * 3] = r * Math.cos(armAngle) + (Math.random() - 0.5) * 1.5;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 1.0;
      positions[i * 3 + 2] = r * Math.sin(armAngle) + (Math.random() - 0.5) * 1.5;
      if (isDusty) {
        colors[i * 3] = 0.75;
        colors[i * 3 + 1] = 0.35;
        colors[i * 3 + 2] = 0.2;
        sizes[i] = 3.5;
      } else {
        colors[i * 3] = 0.5;
        colors[i * 3 + 1] = 0.75;
        colors[i * 3 + 2] = 1.0;
        sizes[i] = 4.2;
      }
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

  const material = new THREE.PointsMaterial({
    size: 5.5,
    vertexColors: true,
    map: starTexture,
    transparent: true,
    blending: THREE.NormalBlending,
    opacity: 0.95,
    depthWrite: false,
    sizeAttenuation: true,
  });

  const starPoints = new THREE.Points(geometry, material);
  group.add(starPoints);

  // 2. Ground Pedestal Foundation
  if (showOrbits) {
    const ringSegments = 64;
    const ringPoints: THREE.Vector3[] = [];
    for (let i = 0; i <= ringSegments; i++) {
      const th = (i / ringSegments) * Math.PI * 2;
      ringPoints.push(new THREE.Vector3(Math.cos(th) * visualRadius, -3.5, Math.sin(th) * visualRadius));
    }
    const ringGeo = new THREE.BufferGeometry().setFromPoints(ringPoints);
    const ringMat = new THREE.LineBasicMaterial({
      color: theme.threeColor,
      transparent: true,
      opacity: 0.75,
    });
    group.add(new THREE.Line(ringGeo, ringMat));

    if (isMilkyWay) {
      // Solar Orbit Ring at R_sun ~ 8.2 kpc
      const sunR = (8.2 / 26.8) * visualRadius;
      const sunPoints: THREE.Vector3[] = [];
      for (let i = 0; i <= 48; i++) {
        const th = (i / 48) * Math.PI * 2;
        sunPoints.push(new THREE.Vector3(Math.cos(th) * sunR, -3.5, Math.sin(th) * sunR));
      }
      const sunRingGeo = new THREE.BufferGeometry().setFromPoints(sunPoints);
      const sunRingMat = new THREE.LineDashedMaterial({
        color: 0xfef08a,
        dashSize: 1.5,
        gapSize: 1.0,
        transparent: true,
        opacity: 0.6,
      });
      const sunRingLine = new THREE.Line(sunRingGeo, sunRingMat);
      sunRingLine.computeLineDistances();
      group.add(sunRingLine);

      // Glowing Sun marker
      const sunMarkerGeo = new THREE.SphereGeometry(0.8, 12, 12);
      const sunMarkerMat = new THREE.MeshBasicMaterial({ color: 0xfff066 });
      const sunMarker = new THREE.Mesh(sunMarkerGeo, sunMarkerMat);
      sunMarker.position.set(sunR, -3.5, 0);
      group.add(sunMarker);
    } else {
      // Targeting crosshair ticks
      const crossPoints: THREE.Vector3[] = [
        new THREE.Vector3(-visualRadius - 3.5, -3.5, 0),
        new THREE.Vector3(-visualRadius + 3.5, -3.5, 0),
        new THREE.Vector3(visualRadius - 3.5, -3.5, 0),
        new THREE.Vector3(visualRadius + 3.5, -3.5, 0),
        new THREE.Vector3(0, -3.5, -visualRadius - 3.5),
        new THREE.Vector3(0, -3.5, -visualRadius + 3.5),
        new THREE.Vector3(0, -3.5, visualRadius - 3.5),
        new THREE.Vector3(0, -3.5, visualRadius + 3.5),
      ];
      const crossGeo = new THREE.BufferGeometry().setFromPoints(crossPoints);
      const crossMat = new THREE.LineSegments(
        crossGeo,
        new THREE.LineBasicMaterial({ color: theme.threeColor, opacity: 0.85, transparent: true })
      );
      group.add(crossMat);
    }
  }

  // 3. 3D Core Beacon Orb & Wireframe Octahedron
  const beaconHeight = Math.max(15.0, visualRadius * 0.42 + 9.0);
  const coreBeaconGeo = new THREE.SphereGeometry(0.8, 16, 16);
  const coreBeaconMat = new THREE.MeshBasicMaterial({ color: theme.threeColor });
  const coreBeacon = new THREE.Mesh(coreBeaconGeo, coreBeaconMat);
  coreBeacon.position.set(0, 0, 0);
  group.add(coreBeacon);

  const octGeo = new THREE.OctahedronGeometry(Math.max(1.6, visualRadius * 0.10), 0);
  const octMat = new THREE.MeshBasicMaterial({
    color: theme.threeColor,
    wireframe: true,
    transparent: true,
    opacity: 0.8,
  });
  const octMesh = new THREE.Mesh(octGeo, octMat);
  group.add(octMesh);

  // 4. 3D Vertical Laser Pointer Thread
  const stemGeo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(0, beaconHeight, 0),
  ]);
  const stemMat = new THREE.LineDashedMaterial({
    color: theme.threeColor,
    dashSize: 0.8,
    gapSize: 0.6,
    transparent: true,
    opacity: 0.75,
  });
  const stemLine = new THREE.Line(stemGeo, stemMat);
  stemLine.computeLineDistances();
  group.add(stemLine);

  // 5. 3D Holographic Reticle Ring in XZ Plane (tilts with 3D scene)
  const haloPoints: THREE.Vector3[] = [];
  for (let i = 0; i <= 32; i++) {
    const th = (i / 32) * Math.PI * 2;
    haloPoints.push(new THREE.Vector3(Math.cos(th) * 3.4, beaconHeight, Math.sin(th) * 3.4));
  }
  const haloGeo = new THREE.BufferGeometry().setFromPoints(haloPoints);
  const haloMat = new THREE.LineBasicMaterial({
    color: theme.threeColor,
    transparent: true,
    opacity: 0.85,
  });
  group.add(new THREE.Line(haloGeo, haloMat));

  // 6. Sleek Hologram Nameplate directly above the 3D ring (with Truth in Labeling)
  const title = isMilkyWay ? 'Milky Way (z = 0)' : `${g.id} (z = ${g.redshift.toFixed(2)})`;
  const provenanceTag = isMilkyWay ? 'BENCHMARK' : isSimDerived ? 'SIM-DERIVED' : 'ILLUSTRATIVE';
  const category = `SLOT ${slotIndex + 1} • [${provenanceTag}] ${isMilkyWay ? 'BENCHMARK' : (g.discovery_profile?.class_title ?? 'TARGET')}`;
  const rKpc = estimatePhysicalRadiusKpc(g.log_mstar, g.redshift);
  const subtext = isMilkyWay
    ? '6.0 × 10¹⁰ M☉ • D₂₅ = 26.8 kpc'
    : `log M* = ${g.log_mstar.toFixed(2)} • R_e ≈ ${rKpc.toFixed(1)} kpc • SFR: ${g.sfr?.toFixed(1) ?? '—'}`;

  const badge = createHologramLabelSprite(title, category, subtext, theme.hex, theme.badgeText);
  badge.position.set(0, beaconHeight + 3.2, 0);
  group.add(badge);

  return group;
}

export const MilkyWayComparator3D: React.FC<MilkyWayComparator3DProps> = ({
  galaxy,
  allGalaxies,
  onSelectGalaxy,
  onClose,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Configurable Max Slots (Default 4, options: 2, 3, 4, 5, 6, 8)
  const [maxSlots, setMaxSlots] = useState<number>(4);

  // Multi-Galaxy Stage Slots: Slot 1 defaults to Milky Way benchmark, Slot 2 defaults to selected target
  const [slots, setSlots] = useState<Galaxy[]>([MILKY_WAY_GALAXY, galaxy]);

  // Controls state
  const [scaleMode, setScaleMode] = useState<'physical' | 'normalized'>('physical');
  const [autoRotate, setAutoRotate] = useState<boolean>(false);
  const [showOrbits, setShowOrbits] = useState<boolean>(true);
  const [isCopied, setIsCopied] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'matrix' | 'timeline' | 'proposal'>('matrix');

  // Three.js instances ref
  const threeRef = useRef<{
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    renderer: THREE.WebGLRenderer;
    controls: OrbitControls;
    stageGroup: THREE.Group;
    starTexture: THREE.CanvasTexture;
    animFrameId: number | null;
  } | null>(null);

  // Initial Scene Setup
  useEffect(() => {
    if (!canvasRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const canvas = canvasRef.current;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x02030a); // Deepest cosmic black

    const camera = new THREE.PerspectiveCamera(40, width / height, 1, 3000);
    camera.position.set(0, 65, 140);

    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI * 0.88;
    controls.minDistance = 30;
    controls.maxDistance = 800;
    controls.target.set(0, 0, 0);

    const starTexture = createStarParticleTexture();

    // Subtle Ambient Cosmic Grid on XZ plane
    const gridHelper = new THREE.GridHelper(360, 24, 0x1e293b, 0x0f172a);
    gridHelper.position.y = -3.8;
    scene.add(gridHelper);

    // Deep cosmic background field stars
    const bgStarsCount = 700;
    const bgPositions = new Float32Array(bgStarsCount * 3);
    const bgColors = new Float32Array(bgStarsCount * 3);
    for (let i = 0; i < bgStarsCount; i++) {
      const r = 250 + Math.random() * 450;
      const th = Math.random() * Math.PI * 2;
      const ph = Math.acos(2 * Math.random() - 1);
      bgPositions[i * 3] = r * Math.sin(ph) * Math.cos(th);
      bgPositions[i * 3 + 1] = r * Math.sin(ph) * Math.sin(th) * 0.6;
      bgPositions[i * 3 + 2] = r * Math.cos(ph);

      const b = 0.5 + Math.random() * 0.45;
      bgColors[i * 3] = b * 0.85;
      bgColors[i * 3 + 1] = b * 0.95;
      bgColors[i * 3 + 2] = b * 1.0;
    }
    const bgGeo = new THREE.BufferGeometry();
    bgGeo.setAttribute('position', new THREE.BufferAttribute(bgPositions, 3));
    bgGeo.setAttribute('color', new THREE.BufferAttribute(bgColors, 3));
    const bgMat = new THREE.PointsMaterial({
      size: 1.8,
      vertexColors: true,
      transparent: true,
      opacity: 0.5,
      depthWrite: false,
    });
    scene.add(new THREE.Points(bgGeo, bgMat));

    // Master Stage Group holding all active galaxy slots
    const stageGroup = new THREE.Group();
    scene.add(stageGroup);

    threeRef.current = {
      scene,
      camera,
      renderer,
      controls,
      stageGroup,
      starTexture,
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
        state.controls.autoRotateSpeed = 0.9;
      } else {
        state.controls.autoRotate = false;
      }

      state.controls.update();

      // Differential organic rotation of all galaxies on stage
      state.stageGroup.children.forEach((child, idx) => {
        child.rotation.y += delta * (0.10 + (idx % 3) * 0.04);
      });

      state.renderer.render(state.scene, state.camera);
      state.animFrameId = requestAnimationFrame(animate);
    };

    threeRef.current.animFrameId = requestAnimationFrame(animate);

    const handleResize = () => {
      if (!containerRef.current || !threeRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      threeRef.current.camera.aspect = w / h;
      threeRef.current.camera.updateProjectionMatrix();
      threeRef.current.renderer.setSize(w, h);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (threeRef.current?.animFrameId) {
        cancelAnimationFrame(threeRef.current.animFrameId);
      }
      renderer.dispose();
      starTexture.dispose();
      threeRef.current = null;
    };
  }, []);

  // Rebuild 3D Stage whenever slots, scaleMode, or showOrbits changes
  useEffect(() => {
    const state = threeRef.current;
    if (!state) return;

    // Dispose old children in stageGroup
    while (state.stageGroup.children.length > 0) {
      const child = state.stageGroup.children.pop()!;
      child.traverse((obj) => {
        if (obj instanceof THREE.Points || obj instanceof THREE.Mesh || obj instanceof THREE.Line || obj instanceof THREE.LineSegments) {
          obj.geometry.dispose();
          if (Array.isArray(obj.material)) {
            obj.material.forEach((m) => m.dispose());
          } else {
            obj.material.dispose();
          }
        }
      });
    }

    const N = slots.length;
    // Spacing between galaxy centers in 3D
    const spacing = Math.max(46, Math.min(62, 220 / Math.max(3, N)));

    slots.forEach((g, idx) => {
      const theme = SLOT_THEMES[idx % SLOT_THEMES.length];
      const modelGroup = buildGalaxyModel(
        g,
        theme,
        idx,
        N,
        scaleMode,
        state.starTexture,
        showOrbits
      );

      // Symmetrically position across X with a gentle panoramic curve
      const x = (idx - (N - 1) / 2) * spacing;
      const z = -Math.abs(x) * 0.06;
      modelGroup.position.set(x, 0, z);

      state.stageGroup.add(modelGroup);
    });

    // Dynamically scale camera distance to comfortably frame all active galaxies
    const idealZ = Math.max(135, N * 42);
    const idealY = Math.max(62, 45 + N * 5);
    state.camera.position.set(0, idealY, idealZ);
    state.controls.target.set(0, 0, 0);
    state.controls.update();
  }, [slots, scaleMode, showOrbits]);

  // Synchronized Camera Angle Presets
  const setCameraPreset = (preset: 'faceon' | 'edgeon' | 'isometric' | 'front') => {
    if (!threeRef.current) return;
    const { camera, controls } = threeRef.current;
    const N = slots.length;
    const idealZ = Math.max(135, N * 42);
    const idealY = Math.max(62, 45 + N * 5);

    if (preset === 'front') {
      camera.position.set(0, idealY * 0.8, idealZ);
      controls.target.set(0, 0, 0);
    } else if (preset === 'faceon') {
      camera.position.set(0, Math.max(160, N * 55), 5);
      controls.target.set(0, 0, 0);
    } else if (preset === 'edgeon') {
      camera.position.set(0, 0, idealZ);
      controls.target.set(0, 0, 0);
    } else if (preset === 'isometric') {
      camera.position.set(0, idealY * 1.3, idealZ * 0.95);
      controls.target.set(0, 0, 0);
    }
    controls.update();
  };

  // Slot Management Handlers
  const handleAddSlot = () => {
    if (slots.length >= maxSlots) return;
    // Find next catalog galaxy not yet on the stage
    const activeIds = new Set(slots.map((s) => s.id));
    const nextCandidate = allGalaxies.find((g) => !activeIds.has(g.id)) || allGalaxies[0];
    setSlots((prev) => [...prev, nextCandidate]);
  };

  const handleRemoveSlot = (indexToRemove: number) => {
    if (slots.length <= 1) return;
    setSlots((prev) => prev.filter((_, idx) => idx !== indexToRemove));
  };

  const handleSlotChange = (slotIndex: number, newGalaxyId: string) => {
    let chosen: Galaxy = MILKY_WAY_GALAXY;
    if (newGalaxyId !== 'MILKY_WAY') {
      const found = allGalaxies.find((g) => g.id === newGalaxyId);
      if (found) chosen = found;
    }
    setSlots((prev) => {
      const copy = [...prev];
      copy[slotIndex] = chosen;
      return copy;
    });
    if (chosen.id !== 'MILKY_WAY') {
      onSelectGalaxy(chosen);
    }
  };

  const handleSetBaseline = (slotIndex: number) => {
    if (slotIndex === 0) return;
    setSlots((prev) => {
      const copy = [...prev];
      const target = copy[slotIndex];
      copy.splice(slotIndex, 1);
      return [target, ...copy];
    });
  };

  const handleSortTimeline = () => {
    setSlots((prev) => {
      const copy = [...prev];
      return copy.sort((a, b) => a.redshift - b.redshift);
    });
  };

  const handleResetToDual = () => {
    setSlots([MILKY_WAY_GALAXY, galaxy]);
  };

  // Baseline galaxy is slot 0
  const baseline = slots[0];
  const isBaselineMW = baseline.id === 'MILKY_WAY';

  return (
    <div ref={containerRef} className="w-full h-full relative flex flex-col bg-cosmos-950 overflow-hidden font-sans select-none">
      {/* Top Header Navigation Bar */}
      <div className="h-14 bg-cosmos-900/95 border-b border-cosmos-800 px-4 flex items-center justify-between z-20 backdrop-blur">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <span className="text-lg font-black bg-gradient-to-r from-indigo-400 via-cyan-400 to-amber-300 bg-clip-text text-transparent">
              Perandam Ψ Galaxy Stage
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-950/90 border border-indigo-700/70 text-indigo-300 font-semibold uppercase tracking-wider">
              3D Stage ({slots.length} / {maxSlots})
            </span>
          </div>
          <div className="hidden xl:flex items-center text-xs text-slate-400 pl-3 border-l border-cosmos-800">
            <span className="italic text-slate-300 font-serif">"Where simulations meet the real universe."</span>
          </div>
        </div>

        {/* Center Controls & Camera Presets */}
        <div className="flex items-center space-x-2">
          {/* Synchronized View Presets */}
          <div className="flex items-center bg-cosmos-950/80 border border-cosmos-700/80 rounded-lg p-1 text-xs">
            <button
              onClick={() => setCameraPreset('front')}
              className="px-2.5 py-1 rounded bg-indigo-950/80 hover:bg-cosmos-800 text-indigo-200 hover:text-cyan-300 font-semibold transition-colors"
              title="Reset camera to direct front stage view"
            >
              Front
            </button>
            <button
              onClick={() => setCameraPreset('isometric')}
              className="px-2.5 py-1 rounded hover:bg-cosmos-800 text-slate-200 hover:text-cyan-300 font-medium transition-colors"
            >
              Isometric
            </button>
            <button
              onClick={() => setCameraPreset('faceon')}
              className="px-2.5 py-1 rounded hover:bg-cosmos-800 text-slate-200 hover:text-cyan-300 font-medium transition-colors"
            >
              Face-on
            </button>
            <button
              onClick={() => setCameraPreset('edgeon')}
              className="px-2.5 py-1 rounded hover:bg-cosmos-800 text-slate-200 hover:text-cyan-300 font-medium transition-colors"
            >
              Edge-on
            </button>
          </div>

          {/* Scale Mode Switcher */}
          <button
            onClick={() => setScaleMode((prev) => (prev === 'physical' ? 'normalized' : 'physical'))}
            className={`flex items-center space-x-1.5 px-2.5 py-1 text-xs border rounded-lg font-semibold transition-all cursor-pointer ${
              scaleMode === 'physical'
                ? 'bg-cyan-950/90 border-cyan-500 text-cyan-200 shadow-sm ring-1 ring-cyan-400/40'
                : 'bg-cosmos-900 border-cosmos-700 text-slate-300 hover:bg-cosmos-800'
            }`}
            title="Toggle between 1:1 true physical radius (kpc) and normalized visual fit"
          >
            <Scale className="w-3.5 h-3.5 text-cyan-400" />
            <span className="hidden sm:inline">{scaleMode === 'physical' ? '1:1 Physical' : 'Normalized'}</span>
          </button>

          {/* Auto Rotate Toggle */}
          <button
            onClick={() => setAutoRotate((prev) => !prev)}
            className={`flex items-center space-x-1.5 px-2 py-1 text-xs border rounded-lg transition-all ${
              autoRotate
                ? 'bg-indigo-900/80 border-indigo-500 text-indigo-200'
                : 'bg-cosmos-900 border-cosmos-700 text-slate-400 hover:bg-cosmos-800'
            }`}
          >
            <Orbit className={`w-3.5 h-3.5 ${autoRotate ? 'animate-spin' : ''}`} />
            <span className="hidden md:inline">Spin</span>
          </button>

          {/* Configurable Max Slots Selector */}
          <div className="flex items-center space-x-1 bg-cosmos-900/90 border border-cosmos-700 rounded-lg px-2 py-1 text-xs">
            <Sliders className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400 hidden lg:inline">Max:</span>
            <select
              value={maxSlots}
              onChange={(e) => {
                const val = Number(e.target.value);
                setMaxSlots(val);
                if (slots.length > val) {
                  setSlots(slots.slice(0, val));
                }
              }}
              className="bg-transparent text-cyan-300 font-bold focus:outline-none cursor-pointer"
              title="Configure max simultaneous 3D galaxy slots (supports 2 to 8 for wide displays)"
            >
              <option value={2} className="bg-cosmos-900 text-slate-200">2 (Dual)</option>
              <option value={3} className="bg-cosmos-900 text-slate-200">3 (Trio)</option>
              <option value={4} className="bg-cosmos-900 text-slate-200">4 (Default)</option>
              <option value={5} className="bg-cosmos-900 text-slate-200">5</option>
              <option value={6} className="bg-cosmos-900 text-slate-200">6 (Wide)</option>
              <option value={8} className="bg-cosmos-900 text-slate-200">8 (Ultra-Wide)</option>
            </select>
          </div>
        </div>

        {/* Right Close / Back Button */}
        <div className="flex items-center space-x-2">
          {onClose && (
            <button
              onClick={onClose}
              className="px-2.5 py-1 text-xs bg-cosmos-800 hover:bg-cosmos-700 border border-cosmos-700 text-slate-300 rounded-lg transition-colors cursor-pointer"
            >
              Back to 2D Sky
            </button>
          )}
        </div>
      </div>

      {/* Active Galaxy Slots Tray */}
      <div className="h-10 bg-cosmos-950/95 border-b border-cosmos-800/80 px-4 flex items-center justify-between text-xs overflow-x-auto gap-3 backdrop-blur z-20">
        <div className="flex items-center space-x-2 flex-nowrap">
          <span className="text-slate-400 font-semibold text-[11px] uppercase tracking-wider hidden sm:inline mr-1">
            Stage Slots:
          </span>

          {slots.map((s, idx) => {
            const theme = SLOT_THEMES[idx % SLOT_THEMES.length];
            const isMW = s.id === 'MILKY_WAY';
            return (
              <div
                key={`${s.id}-${idx}`}
                className="flex items-center space-x-1.5 bg-cosmos-900/90 border rounded-lg px-2 py-0.5 shadow-sm"
                style={{ borderColor: theme.hex + '70' }}
              >
                <span className="w-2.5 h-2.5 rounded-full ring-1" style={{ backgroundColor: theme.hex, borderColor: theme.hex }} />
                <span className="font-bold font-mono text-[11px]" style={{ color: theme.hex }}>
                  #{idx + 1}{idx === 0 ? ' (Ref)' : ''}:
                </span>
                <select
                  value={s.id}
                  onChange={(e) => handleSlotChange(idx, e.target.value)}
                  className="bg-transparent text-slate-200 text-xs focus:outline-none cursor-pointer max-w-[140px] truncate font-mono font-medium"
                >
                  <option value="MILKY_WAY" className="bg-cosmos-900 text-amber-300">
                    🌌 Milky Way (z = 0)
                  </option>
                  {allGalaxies.map((g) => (
                    <option key={g.id} value={g.id} className="bg-cosmos-900 text-slate-200 font-sans">
                      {g.discovery_profile ? '✨ ' : ''}{g.id} (z={g.redshift.toFixed(2)})
                    </option>
                  ))}
                </select>
                {s.galaxy3d?.geometry_source === 'simulation_derived' ? (
                  <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-950 border border-emerald-400 text-emerald-300 font-mono font-bold flex items-center space-x-1 flex-shrink-0 shadow-sm" title="Empirical 3D simulation particles">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    <span>SIM-DERIVED</span>
                  </span>
                ) : !isMW ? (
                  <span className="text-[9px] px-1 py-0.5 rounded bg-amber-950/70 border border-amber-600/50 text-amber-300/80 font-mono flex-shrink-0" title="Procedural illustrative model">
                    ILLUSTRATIVE
                  </span>
                ) : null}
                {slots.length > 1 && (
                  <button
                    onClick={() => handleRemoveSlot(idx)}
                    className="text-slate-500 hover:text-rose-400 p-0.5 rounded transition-colors"
                    title="Remove galaxy from 3D stage"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
            );
          })}

          {slots.length < maxSlots && (
            <button
              onClick={handleAddSlot}
              className="flex items-center space-x-1 px-2.5 py-1 bg-cyan-950/70 hover:bg-cyan-900/90 border border-cyan-500/70 text-cyan-200 rounded-lg text-xs font-semibold transition-all cursor-pointer shadow-sm"
              title={`Add another galaxy to 3D stage (up to ${maxSlots})`}
            >
              <Plus className="w-3.5 h-3.5 text-cyan-400" />
              <span>Add Galaxy ({slots.length}/{maxSlots})</span>
            </button>
          )}
        </div>

        {/* Quick Stage Utilities */}
        <div className="flex items-center space-x-2 flex-shrink-0">
          <button
            onClick={handleSortTimeline}
            className="flex items-center space-x-1 px-2 py-0.5 text-xs text-slate-300 hover:text-cyan-300 hover:bg-cosmos-800 rounded transition-colors"
            title="Sort galaxies chronologically by redshift (z = 0 to high-z)"
          >
            <Clock className="w-3 h-3 text-cyan-400" />
            <span className="hidden md:inline">Sort by z</span>
          </button>
          <button
            onClick={handleResetToDual}
            className="flex items-center space-x-1 px-2 py-0.5 text-xs text-slate-400 hover:text-amber-300 hover:bg-cosmos-800 rounded transition-colors"
            title="Reset to 2-galaxy benchmark (Milky Way vs Target)"
          >
            <RotateCcw className="w-3 h-3 text-amber-400" />
            <span className="hidden md:inline">Dual Reset</span>
          </button>
        </div>
      </div>

      {/* Main 3D Canvas Viewport */}
      <div className="flex-1 relative overflow-hidden">
        <canvas ref={canvasRef} className="w-full h-full block touch-none" />

        {/* Central Progenitor / Discovery Verdict Banner */}
        <div className="absolute top-3 left-1/2 transform -translate-x-1/2 pointer-events-none hidden md:flex items-center space-x-2 bg-cosmos-900/90 border border-amber-500/60 rounded-full px-4 py-1.5 shadow-xl backdrop-blur text-xs z-20">
          <Flame className="w-4 h-4 text-amber-400" />
          <span className="font-semibold text-amber-200">
            {isBaselineMW
              ? `Comparative Reference: Milky Way Benchmark (z = 0) vs ${slots.length - 1} Target${slots.length > 2 ? 's' : ''}`
              : `Multi-Target Peer Comparison (Baseline: ${baseline.id}, z = ${baseline.redshift.toFixed(2)})`}
          </span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-300 font-mono">{slots.length} Galaxies on Stage</span>
        </div>
      </div>

      {/* Bottom Comparative Analysis Sheet */}
      <div className="h-60 min-h-[240px] bg-cosmos-900/95 border-t border-cosmos-800 p-3 flex flex-col z-20 backdrop-blur overflow-hidden">
        {/* Tab Header */}
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-cosmos-800 text-xs">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setActiveTab('matrix')}
              className={`font-semibold transition-colors pb-0.5 ${
                activeTab === 'matrix' ? 'text-cyan-300 border-b-2 border-cyan-400' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Multi-Galaxy Matrix ({slots.length})
            </button>
            <button
              onClick={() => setActiveTab('timeline')}
              className={`font-semibold transition-colors pb-0.5 ${
                activeTab === 'timeline' ? 'text-cyan-300 border-b-2 border-cyan-400' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Cosmic Timeline (Lookback Time)
            </button>
            <button
              onClick={() => setActiveTab('proposal')}
              className={`font-semibold transition-colors pb-0.5 ${
                activeTab === 'proposal' ? 'text-cyan-300 border-b-2 border-cyan-400' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Export Proposal Table
            </button>
          </div>

          <div className="text-[11px] text-slate-500 font-mono hidden sm:inline">
            Baseline Reference: <strong className="text-slate-300">Slot #1 ({baseline.id})</strong>
          </div>
        </div>

        {/* Tab 1: Multi-Galaxy Matrix */}
        {activeTab === 'matrix' && (
          <div className="flex-1 overflow-x-auto">
            <div className="flex gap-2.5 min-w-full pb-1">
              {slots.map((s, idx) => {
                const theme = SLOT_THEMES[idx % SLOT_THEMES.length];
                const isMW = s.id === 'MILKY_WAY';
                const lookback = lookbackTimeGyr(s.redshift);
                const rKpc = estimatePhysicalRadiusKpc(s.log_mstar, s.redshift);

                // Delta vs Baseline (Slot 0)
                const baseMstar = baseline.stellar_mass || Math.pow(10, baseline.log_mstar);
                const currentMstar = s.stellar_mass || Math.pow(10, s.log_mstar);
                const massRatio = (currentMstar / Math.max(1, baseMstar)) * 100;
                const sfrRatio = s.sfr / Math.max(0.01, baseline.sfr);

                return (
                  <div
                    key={`${s.id}-${idx}`}
                    className="flex-1 min-w-[210px] bg-cosmos-950/80 border rounded-xl p-2.5 flex flex-col justify-between shadow-sm"
                    style={{ borderColor: theme.hex + '50' }}
                  >
                    {/* Header */}
                    <div className="flex items-center justify-between pb-1.5 border-b border-cosmos-800/60">
                      <div className="flex items-center space-x-1.5 truncate">
                        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: theme.hex }} />
                        <span className="font-bold text-xs truncate" style={{ color: theme.hex }}>
                          #{idx + 1} {isMW ? 'Milky Way' : s.id}
                        </span>
                        {isMW ? (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-950/80 border border-amber-600/70 text-amber-300 font-mono font-semibold flex-shrink-0">
                            Reference
                          </span>
                        ) : s.galaxy3d?.geometry_source === 'simulation_derived' ? (
                          <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-950 border border-emerald-400 text-emerald-300 font-mono font-bold flex items-center space-x-1 shadow-md shadow-emerald-950/60 flex-shrink-0" title="Empirical simulation particles">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                            <span>SIMULATION-DERIVED</span>
                          </span>
                        ) : (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-950/60 border border-amber-600/50 text-amber-300/90 font-mono flex-shrink-0" title="Procedural illustrative model">
                            ILLUSTRATIVE
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cosmos-900 text-slate-300 flex-shrink-0">
                        z = {s.redshift.toFixed(2)}
                      </span>
                    </div>

                    {/* Metrics Grid */}
                    <div className="grid grid-cols-2 gap-2 my-1.5 text-[11px] font-mono">
                      <div>
                        <div className="text-slate-500 text-[10px]">Stellar Mass</div>
                        <div className="font-bold text-slate-200">
                          {s.stellar_mass?.toExponential(2) ?? Math.pow(10, s.log_mstar).toExponential(2)} M☉
                        </div>
                        <div className="text-[10px] text-cyan-400">
                          {idx === 0 ? 'Baseline' : `${massRatio.toFixed(1)}% of #1`}
                        </div>
                      </div>

                      <div>
                        <div className="text-slate-500 text-[10px]">Star Formation</div>
                        <div className="font-bold text-slate-200">
                          {s.sfr?.toFixed(2) ?? '—'} M☉/yr
                        </div>
                        <div className="text-[10px] text-emerald-400">
                          {idx === 0 ? 'Baseline' : `${sfrRatio.toFixed(1)}x of #1`}
                        </div>
                      </div>

                      <div>
                        <div className="text-slate-500 text-[10px]">Physical Size</div>
                        <div className="font-bold text-slate-200">
                          {isMW ? 'D₂₅ = 26.8' : `R_e ≈ ${rKpc.toFixed(1)}`} kpc
                        </div>
                      </div>

                      <div>
                        <div className="text-slate-500 text-[10px]">Lookback Time</div>
                        <div className="font-bold text-slate-200">
                          ~{lookback.toFixed(1)} Gyr
                        </div>
                      </div>
                    </div>

                    {/* Footer: Set Reference or Classification & Truth in Labeling */}
                    <div className="pt-1 border-t border-cosmos-800/60 text-[10px] space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400 truncate max-w-[120px]">
                          {isMW ? 'Reference Benchmark' : (s.discovery_profile?.class_title ?? 'Field Target')}
                        </span>
                        {idx !== 0 && (
                          <button
                            onClick={() => handleSetBaseline(idx)}
                            className="text-cyan-400 hover:text-cyan-200 hover:underline cursor-pointer"
                            title="Set this galaxy as Slot #1 baseline"
                          >
                            Make Ref
                          </button>
                        )}
                      </div>
                      <div className="flex items-center">
                        {isMW ? (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-950/70 border border-amber-600/70 text-amber-300 font-mono font-semibold">
                            🌌 Benchmark Reference
                          </span>
                        ) : s.galaxy3d?.geometry_source === 'simulation_derived' ? (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-500/80 text-emerald-300 font-mono font-semibold flex items-center space-x-1" title="Empirical simulation particles">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                            <span>SIMULATION-DERIVED</span>
                          </span>
                        ) : (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-950/50 border border-amber-500/50 text-amber-300/90 font-mono" title="Procedural heuristic model for visual context; not direct simulation particle data">
                            PROVISIONALLY ILLUSTRATIVE
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Tab 2: Cosmic Timeline */}
        {activeTab === 'timeline' && (
          <div className="flex-1 overflow-x-auto flex items-center px-2">
            <div className="flex items-center space-x-3 min-w-full">
              {[...slots].sort((a, b) => a.redshift - b.redshift).map((s, idx) => {
                const lookback = lookbackTimeGyr(s.redshift);
                return (
                  <React.Fragment key={`timeline-${s.id}`}>
                    <div className="bg-cosmos-950/90 border border-cosmos-700/80 rounded-xl p-3 min-w-[200px] shadow-sm">
                      <div className="text-xs font-bold text-cyan-300">
                        {s.id === 'MILKY_WAY' ? '🌌 Milky Way' : s.id}
                      </div>
                      <div className="text-[11px] font-mono text-amber-300 mt-1">
                        Redshift z = {s.redshift.toFixed(2)}
                      </div>
                      <div className="text-[11px] font-mono text-slate-400">
                        ~{lookback.toFixed(2)} Gyr Lookback
                      </div>
                      <div className="text-[10px] text-slate-500 mt-1 truncate">
                        {s.discovery_profile?.class_title ?? 'Local Universe Spiral'}
                      </div>
                    </div>
                    {idx < slots.length - 1 && (
                      <ArrowLeftRight className="w-4 h-4 text-slate-600 flex-shrink-0" />
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>
        )}

        {/* Tab 3: Proposal Table Export */}
        {activeTab === 'proposal' && (
          <div className="flex-1 flex flex-col justify-between text-xs">
            <div className="bg-cosmos-950/90 border border-cosmos-800 rounded-lg p-2 font-mono text-[11px] text-slate-300 overflow-y-auto max-h-24">
              <pre>
{`| Slot | Galaxy ID | Redshift (z) | Lookback (Gyr) | Stellar Mass (M_sun) | SFR (M_sun/yr) | Size (kpc) |
|---|---|---|---|---|---|---|
` + slots.map((s, i) => `| #${i + 1} | ${s.id} | ${s.redshift.toFixed(2)} | ${lookbackTimeGyr(s.redshift).toFixed(1)} | ${s.stellar_mass?.toExponential(2) ?? Math.pow(10, s.log_mstar).toExponential(2)} | ${s.sfr?.toFixed(2) ?? '—'} | ${s.id === 'MILKY_WAY' ? '26.8' : estimatePhysicalRadiusKpc(s.log_mstar, s.redshift).toFixed(1)} |`).join('\n')}
              </pre>
            </div>
            <div className="flex justify-end pt-1">
              <button
                onClick={() => {
                  const tableText = `| Slot | Galaxy ID | Redshift (z) | Lookback (Gyr) | Stellar Mass (M_sun) | SFR (M_sun/yr) | Size (kpc) |\n|---|---|---|---|---|---|---|\n` + slots.map((s, i) => `| #${i + 1} | ${s.id} | ${s.redshift.toFixed(2)} | ${lookbackTimeGyr(s.redshift).toFixed(1)} | ${s.stellar_mass?.toExponential(2) ?? Math.pow(10, s.log_mstar).toExponential(2)} | ${s.sfr?.toFixed(2) ?? '—'} | ${s.id === 'MILKY_WAY' ? '26.8' : estimatePhysicalRadiusKpc(s.log_mstar, s.redshift).toFixed(1)} |`).join('\n');
                  navigator.clipboard.writeText(tableText);
                  setIsCopied(true);
                  setTimeout(() => setIsCopied(false), 2000);
                }}
                className="flex items-center space-x-1 px-3 py-1 bg-cyan-950 hover:bg-cyan-900 border border-cyan-600/70 text-cyan-200 rounded-lg text-xs font-semibold transition-all cursor-pointer"
              >
                {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{isCopied ? 'Copied Table!' : 'Copy Markdown Table'}</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
