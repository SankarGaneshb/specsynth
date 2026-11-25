import type { Galaxy, SkyColorMode } from '../types/galaxy.ts';
import { comovingDistanceMpc, ez, DEFAULT_H0, DEFAULT_OM0 } from './physics.ts';

// Conversion factor for 1/H0 in Gyr: (1 Mpc in km) / (1 Gyr in s) / H0
// 1 Mpc = 3.08567758e19 km, 1 Gyr = 3.15576e16 s -> (3.08567758e19 / 3.15576e16) / H0 = 977.79 / H0 Gyr
const GYR_PER_H0 = 977.792;

/**
 * Computes cosmological lookback time t_L(z) in Gyr in Flat Lambda-CDM.
 * t_L(z) = (1 / H0) * integral_0^z dz' / ((1 + z') * E(z'))
 */
export function lookbackTimeGyr(z: number, H0: number = DEFAULT_H0, Om0: number = DEFAULT_OM0): number {
  if (z <= 0) return 0;
  const hubbleTimeGyr = GYR_PER_H0 / H0;

  // 16-node Gauss-Legendre quadrature on [0, z]
  const nodes = [
    -0.98940093, -0.94457502, -0.8656312, -0.75540441,
    -0.61787624, -0.45801678, -0.28160355, -0.09501251,
    0.09501251, 0.28160355, 0.45801678, 0.61787624,
    0.75540441, 0.8656312, 0.94457502, 0.98940093,
  ];
  const weights = [
    0.02715246, 0.06225352, 0.09515851, 0.12462897,
    0.14959599, 0.16915652, 0.18260342, 0.18945061,
    0.18945061, 0.18260342, 0.16915652, 0.14959599,
    0.12462897, 0.09515851, 0.06225352, 0.02715246,
  ];

  let integral = 0;
  for (let i = 0; i < 16; i++) {
    const zp = 0.5 * z * (nodes[i] + 1.0);
    integral += weights[i] / ((1.0 + zp) * ez(zp, Om0));
  }

  return hubbleTimeGyr * 0.5 * z * integral;
}

export interface CosmicEpoch {
  z: number;
  label: string;
  description: string;
  lookbackGyr: number;
  colorHex: string;
}

export const COSMIC_EPOCHS: CosmicEpoch[] = [
  {
    z: 0.5,
    label: 'z = 0.5',
    description: 'Recent Universe (Lookback ~5.1 Gyr)',
    lookbackGyr: 5.1,
    colorHex: '#38bdf8', // Sky blue
  },
  {
    z: 1.0,
    label: 'z = 1.0',
    description: 'Cosmic Expansion Milestone (Lookback ~7.9 Gyr)',
    lookbackGyr: 7.9,
    colorHex: '#34d399', // Emerald
  },
  {
    z: 2.0,
    label: 'z = 2.0 (Cosmic Noon)',
    description: 'Peak Star Formation & AGN Activity (Lookback ~10.5 Gyr)',
    lookbackGyr: 10.5,
    colorHex: '#fbbf24', // Amber
  },
  {
    z: 4.0,
    label: 'z = 4.0',
    description: 'Early Massive Galaxies & Quenchers (Lookback ~12.2 Gyr)',
    lookbackGyr: 12.2,
    colorHex: '#f97316', // Orange
  },
  {
    z: 6.0,
    label: 'z = 6.0',
    description: 'Epoch of Reionization End (Lookback ~12.8 Gyr)',
    lookbackGyr: 12.8,
    colorHex: '#ef4444', // Red
  },
  {
    z: 8.5,
    label: 'z = 8.5',
    description: 'Cosmic Dawn & JWST Deep Frontier (Lookback ~13.1 Gyr)',
    lookbackGyr: 13.1,
    colorHex: '#c084fc', // Purple
  },
];

export interface Cosmo3DOptions {
  fieldRadius?: number;         // Survey field radius in degrees (e.g. 0.08)
  geometryMode?: 'sky_plane' | 'cone'; // 'sky_plane' preserves 2D sky layout; 'cone' expands from observer
  fieldSpread?: number;         // Transverse visual span in 3D units (default 85)
  sceneDepth?: number;          // Total depth units in 3D scene (default 260)
  maxRedshift?: number;         // Reference maximum redshift (default 9.0)
}

/**
 * Projects astronomical coordinates (RA, Dec, z) into 3D Cartesian coordinates (X, Y, Z).
 * - X and Y are proportional to normalized angular field coordinates (RA, Dec),
 *   guaranteeing galaxies are visibly separated and match the 2D Sky distribution.
 * - Z axis represents line-of-sight comoving depth into deep space (observer at Z=0, deep cosmos at -Z).
 */
export function projectGalaxyTo3D(
  galaxy: Galaxy,
  centerRa: number,
  centerDec: number,
  fieldRadius: number = 0.08,
  options: Cosmo3DOptions = {}
): [number, number, number] {
  const geometryMode = options.geometryMode ?? 'sky_plane';
  const fieldSpread = options.fieldSpread ?? 85.0;
  const sceneDepth = options.sceneDepth ?? 260.0;
  const maxZ = options.maxRedshift ?? 9.0;
  const radiusDeg = Math.max(1e-4, options.fieldRadius ?? fieldRadius);

  // Maximum comoving distance for normalization
  const maxDistanceMpc = comovingDistanceMpc(maxZ);

  const z = typeof galaxy.redshift === 'number' && !isNaN(galaxy.redshift) ? Math.max(0.01, galaxy.redshift) : 1.0;
  const dMpc = comovingDistanceMpc(z);

  // Normalized distance along line of sight (0 to sceneDepth)
  const zNorm = (dMpc / maxDistanceMpc) * sceneDepth;

  // Normalized angular offsets on [-1, 1] relative to field center
  const cosDecCenter = Math.cos((centerDec * Math.PI) / 180);
  const u = ((centerRa - galaxy.ra) * cosDecCenter) / radiusDeg;
  const v = (galaxy.dec - centerDec) / radiusDeg;

  let x: number;
  let y: number;

  if (geometryMode === 'cone') {
    // Expanding cone from observer (0.25 at z=0 to 1.0 at maxZ)
    const coneFactor = 0.25 + 0.75 * (zNorm / sceneDepth);
    x = u * fieldSpread * coneFactor;
    y = v * fieldSpread * coneFactor;
  } else {
    // Orthogonal 3D Sky Plane: preserves 2D sky projection when viewed from front
    x = u * fieldSpread;
    y = v * fieldSpread;
  }

  const zCoord = -zNorm; // extending into deep space (-Z)

  return [x, y, zCoord];
}

/**
 * Computes color RGB components in [0, 1] for 3D Three.js materials.
 */
export function getGalaxy3DColorRgb(galaxy: Galaxy, mode: SkyColorMode): { r: number; g: number; b: number } {
  const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

  if (mode === 'redshift') {
    const zVal = typeof galaxy.redshift === 'number' && !isNaN(galaxy.redshift) ? galaxy.redshift : 1.0;
    const t = Math.max(0, Math.min(1, (zVal - 0.2) / 8.0));
    if (t < 0.3) {
      const f = t / 0.3;
      return {
        r: clamp01((56 + f * (52 - 56)) / 255),
        g: clamp01((189 + f * (211 - 189)) / 255),
        b: clamp01((248 + f * (153 - 248)) / 255),
      };
    } else if (t < 0.65) {
      const f = (t - 0.3) / 0.35;
      return {
        r: clamp01((52 + f * (251 - 52)) / 255),
        g: clamp01((211 + f * (191 - 211)) / 255),
        b: clamp01((153 + f * (36 - 153)) / 255),
      };
    } else {
      const f = (t - 0.65) / 0.35;
      return {
        r: clamp01((251 + f * (244 - 251)) / 255),
        g: clamp01((191 + f * (63 - 191)) / 255),
        b: clamp01((36 + f * (94 - 36)) / 255),
      };
    }
  }

  if (mode === 'ssfr') {
    const ssfrVal = (galaxy.sfr && galaxy.stellar_mass && galaxy.stellar_mass > 0)
      ? (galaxy.sfr / galaxy.stellar_mass)
      : 1e-12;
    const logSSFR = Math.log10(Math.max(1e-13, ssfrVal));
    if (logSSFR > -10.0) {
      return { r: 96 / 255, g: 165 / 255, b: 250 / 255 }; // Blue cloud
    } else if (logSSFR > -10.8) {
      return { r: 52 / 255, g: 211 / 255, b: 153 / 255 }; // Green valley
    } else {
      return { r: 244 / 255, g: 63 / 255, b: 94 / 255 }; // Red sequence
    }
  }

  if (mode === 'mass') {
    const mVal = typeof galaxy.log_mstar === 'number' && !isNaN(galaxy.log_mstar) ? galaxy.log_mstar : 9.5;
    const t = Math.max(0, Math.min(1, (mVal - 7.5) / 4.0));
    return {
      r: clamp01((129 + t * (254 - 129)) / 255),
      g: clamp01((140 + t * (240 - 140)) / 255),
      b: clamp01((248 - t * 110) / 255),
    };
  }

  // Default: JWST RGB Composite from F444W, F200W, F090W
  const rFlux = Math.max(0, galaxy.fluxes?.['jwst_f444w'] ?? 1e-32);
  const gFlux = Math.max(0, galaxy.fluxes?.['jwst_f200w'] ?? 1e-32);
  const bFlux = Math.max(0, galaxy.fluxes?.['jwst_f090w'] ?? 1e-32);

  const maxFlux = Math.max(rFlux, gFlux, bFlux);
  if (maxFlux <= 0) return { r: 0.78, g: 0.86, b: 1.0 };

  const rRaw = 255 * Math.pow(rFlux / maxFlux, 0.4);
  const gRaw = 255 * Math.pow(gFlux / maxFlux, 0.4);
  const bRaw = 255 * Math.pow(bFlux / maxFlux, 0.4);

  const boost = Math.max(rRaw, gRaw, bRaw);
  const minLum = 180;
  const factor = boost > 0 && boost < minLum ? minLum / boost : 1;

  return {
    r: clamp01((rRaw * factor) / 255),
    g: clamp01((gRaw * factor) / 255),
    b: clamp01((bRaw * factor) / 255),
  };
}
