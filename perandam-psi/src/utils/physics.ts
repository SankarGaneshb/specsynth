/**
 * In-Browser Scientific Forward Model & Cosmological Calculator for PerandamΨ.
 * 
 * Provides:
 *  1. Flat Lambda-CDM cosmological luminosity distance via 16-node Gauss-Legendre quadrature.
 *  2. Charlot & Fall (2000) dust attenuation curve.
 *  3. Madau (1995) Intergalactic Medium (IGM) line blanketing and Lyman continuum absorption.
 *  4. In-flight numerical bandpass integration for JWST NIRCam filters.
 *  5. JWST Exposure Time Calculator (ETC) point-source noise model (10 ks medium-deep limits).
 *  6. Exact analytical chi^2 survival probability for 6 degrees of freedom.
 *  7. Complete in-browser galaxy forward-modeling engine.
 */

import type { SedPoint, FilterCurveData } from '../types/galaxy';

// Physical astronomical constants (IAU 2015 Resolution B3)
export const C_KM_S = 299792.458; // Speed of light in km/s
export const C_ANG_S = 2.99792458e18; // Speed of light in Angstrom / s
export const L_SUN_ERG_S = 3.828e33; // Solar luminosity in erg / s
export const MPC_TO_CM = 3.08567758128e24; // Megaparsec in cm

// Default cosmology: IllustrisTNG Planck 2015 parameters
export const DEFAULT_H0 = 67.74; // km/s/Mpc
export const DEFAULT_OM0 = 0.3089; // Matter density

// 16-point Gauss-Legendre quadrature nodes and weights on [-1, 1]
const GL16_NODES = [
  -0.98940093, -0.94457502, -0.8656312, -0.75540441,
  -0.61787624, -0.45801678, -0.28160355, -0.09501251,
  0.09501251, 0.28160355, 0.45801678, 0.61787624,
  0.75540441, 0.8656312, 0.94457502, 0.98940093,
];

const GL16_WEIGHTS = [
  0.02715246, 0.06225352, 0.09515851, 0.12462897,
  0.14959599, 0.16915652, 0.18260342, 0.18945061,
  0.18945061, 0.18260342, 0.16915652, 0.14959599,
  0.12462897, 0.09515851, 0.06225352, 0.02715246,
];

// Madau (1995) Lyman series rest wavelengths (Angstroms) and coefficients
const MADAU_LYMAN_SERIES = [
  { wave: 1215.67, a: 0.0036 }, // Ly-alpha
  { wave: 1025.72, a: 0.0017 }, // Ly-beta
  { wave: 972.54, a: 0.0012 },  // Ly-gamma
  { wave: 949.74, a: 0.00093 }, // Ly-delta
];
const LYMAN_LIMIT_AA = 911.75;

// JWST NIRCam 5-sigma point-source sensitivity limits for 10 ks medium-deep exposure (AB mag)
export const NIRCAM_5SIGMA_LIMITS: Record<string, number> = {
  jwst_f090w: 29.2,
  jwst_f150w: 29.5,
  jwst_f200w: 29.7,
  jwst_f277w: 29.4,
  jwst_f356w: 29.4,
  jwst_f444w: 29.0,
};

/**
 * Dimensionless Hubble parameter E(z) = H(z) / H0 in Flat Lambda-CDM.
 */
export function ez(z: number, Om0: number = DEFAULT_OM0): number {
  const Ode0 = 1.0 - Om0;
  return Math.sqrt(Om0 * Math.pow(1.0 + z, 3) + Ode0);
}

/**
 * Line-of-sight comoving distance in Mpc using 16-node Gauss-Legendre quadrature.
 */
export function comovingDistanceMpc(z: number, H0: number = DEFAULT_H0, Om0: number = DEFAULT_OM0): number {
  if (z <= 0) return 0;
  let integral = 0;
  for (let i = 0; i < 16; i++) {
    const zSample = 0.5 * z * (GL16_NODES[i] + 1.0);
    integral += GL16_WEIGHTS[i] / ez(zSample, Om0);
  }
  return (C_KM_S / H0) * 0.5 * z * integral;
}

/**
 * Luminosity distance D_L(z) in Mpc. D_L = (1 + z) * D_C(z).
 */
export function luminosityDistanceMpc(z: number, H0: number = DEFAULT_H0, Om0: number = DEFAULT_OM0): number {
  return (1.0 + z) * comovingDistanceMpc(z, H0, Om0);
}

/**
 * Luminosity distance D_L(z) in cm.
 */
export function luminosityDistanceCm(z: number, H0: number = DEFAULT_H0, Om0: number = DEFAULT_OM0): number {
  return luminosityDistanceMpc(z, H0, Om0) * MPC_TO_CM;
}

/**
 * Charlot & Fall (2000) dust attenuation factor T_dust(lambda) = exp(-delta_tau).
 * delta_tau = (deltaAv / 1.086) * (lambda / 5500)^(-0.7).
 */
export function charlotFallAttenuation(waveRestA: number, deltaAv: number): number {
  if (Math.abs(deltaAv) < 1e-4) return 1.0;
  const deltaTau = (deltaAv / 1.086) * Math.pow(waveRestA / 5500.0, -0.7);
  return Math.exp(-deltaTau);
}

/**
 * Madau (1995) Intergalactic Medium (IGM) transmission factor T_IGM in [0, 1].
 */
export function madauIgmTransmission(waveObsA: number, z: number): number {
  if (z <= 0.0) return 1.0;

  let tauEff = 0.0;

  // 1. Lyman series line blanketing
  for (const line of MADAU_LYMAN_SERIES) {
    if (waveObsA >= line.wave && waveObsA <= line.wave * (1.0 + z)) {
      tauEff += line.a * Math.pow(waveObsA / line.wave, 3.46);
    }
  }

  // 2. Lyman continuum photoelectric absorption (rest-frame < 911.75 A)
  const lymanLimitObs = LYMAN_LIMIT_AA * (1.0 + z);
  if (waveObsA < lymanLimitObs) {
    const xc = waveObsA / LYMAN_LIMIT_AA;
    const zP1 = 1.0 + z;
    const tauLc =
      0.25 * Math.pow(xc, 3) * (Math.pow(zP1, 0.46) - Math.pow(xc, 0.46)) +
      9.4 * Math.pow(xc, 1.5) * (Math.pow(zP1, 0.18) - Math.pow(xc, 0.18)) -
      0.7 * Math.pow(xc, 3) * (Math.pow(xc, -1.32) - Math.pow(zP1, -1.32)) -
      0.023 * (Math.pow(zP1, 1.68) - Math.pow(xc, 1.68));

    tauEff += Math.max(0.0, Math.min(50.0, tauLc));
  }

  return Math.exp(-Math.min(50.0, Math.max(0.0, tauEff)));
}

/**
 * Convert bandpass F_lambda [erg/s/cm2/A] to f_nu [erg/s/cm2/Hz].
 * f_nu = F_lambda * lambda_pivot^2 / c.
 */
export function fLambdaToFNu(fLambdaCgs: number, pivotWaveA: number): number {
  return (fLambdaCgs * (pivotWaveA * pivotWaveA)) / C_ANG_S;
}

/**
 * Convert f_nu [erg/s/cm2/Hz] to AB magnitude: m_AB = -2.5 * log10(f_nu) - 48.60.
 */
export function fluxToAbMag(fNuCgs: number): number {
  if (fNuCgs <= 0 || isNaN(fNuCgs)) return 99.0;
  return -2.5 * Math.log10(fNuCgs) - 48.60;
}

/**
 * Convert AB magnitude to f_nu [erg/s/cm2/Hz].
 */
export function abMagToFNu(mag: number): number {
  if (mag >= 90) return 0;
  return Math.pow(10, -(mag + 48.60) / 2.5);
}

/**
 * Linear interpolation helper for transmission curves.
 */
function interpolate(x: number, xs: number[], ys: number[]): number {
  const n = xs.length;
  if (n === 0 || x < xs[0] || x > xs[n - 1]) return 0.0;
  let low = 0;
  let high = n - 1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (xs[mid] < x) low = mid + 1;
    else high = mid - 1;
  }
  const i0 = Math.max(0, high);
  const i1 = Math.min(n - 1, low);
  if (i0 === i1) return ys[i0];
  const t = (x - xs[i0]) / (xs[i1] - xs[i0]);
  return ys[i0] + t * (ys[i1] - ys[i0]);
}

/**
 * In-flight numerical integration of observed spectrum against a broadband transmission curve.
 * Computes bandpass flux density:
 *  F_lambda,band = \int F_lambda(lambda) * T(lambda) * lambda dlambda / \int T(lambda) * lambda dlambda.
 */
export function integrateBandpass(
  waveObs: number[],
  fObs: number[],
  filterWave: number[],
  filterTransmission: number[]
): number {
  const n = waveObs.length;
  if (n < 2) return 0.0;

  // Compute filter normalization \int T(lambda) * lambda dlambda
  let filterNorm = 0.0;
  for (let j = 0; j < filterWave.length - 1; j++) {
    const w0 = filterWave[j];
    const w1 = filterWave[j + 1];
    const dw = w1 - w0;
    const integrand0 = filterTransmission[j] * w0;
    const integrand1 = filterTransmission[j + 1] * w1;
    filterNorm += 0.5 * (integrand0 + integrand1) * dw;
  }
  if (filterNorm <= 0) return 0.0;

  // Trapezoidal integration across observed wavelength nodes
  let numerator = 0.0;
  for (let i = 0; i < n - 1; i++) {
    const w0 = waveObs[i];
    const w1 = waveObs[i + 1];
    const dw = w1 - w0;

    const t0 = interpolate(w0, filterWave, filterTransmission);
    const t1 = interpolate(w1, filterWave, filterTransmission);

    const int0 = fObs[i] * t0 * w0;
    const int1 = fObs[i + 1] * t1 * w1;

    numerator += 0.5 * (int0 + int1) * dw;
  }

  return numerator / filterNorm;
}

/**
 * Photometric uncertainty and S/N based on 10 ks NIRCam medium-deep exposure limits.
 */
export function getPhotometricUncertainty(
  fNuCgs: number,
  bandName: string
): { magErr: number; snr: number; status: 'SECURE' | 'MARGINAL' | 'UPPER_LIMIT' } {
  const lim5sig = NIRCAM_5SIGMA_LIMITS[bandName] || 29.5;
  const fnu5sig = Math.pow(10, -(lim5sig + 48.60) / 2.5);
  const sigmaFnu = fnu5sig / 5.0;

  if (fNuCgs <= 0 || isNaN(fNuCgs)) {
    return { magErr: 99.0, snr: 0.0, status: 'UPPER_LIMIT' };
  }

  const snr = fNuCgs / sigmaFnu;
  const magErr = 1.085736 / Math.max(0.05, snr);

  let status: 'SECURE' | 'MARGINAL' | 'UPPER_LIMIT' = 'SECURE';
  if (snr < 3.0) status = 'UPPER_LIMIT';
  else if (snr < 5.0) status = 'MARGINAL';

  return {
    magErr: Math.min(99.0, Number(magErr.toFixed(3))),
    snr: Number(snr.toFixed(1)),
    status,
  };
}

/**
 * Analytical chi^2 survival probability P(X >= chi2) for df = 6.
 * Formula: P = exp(-s) * (1 + s + 0.5 * s^2) where s = chi2 / 2.
 */
export function chi2SurvivalDf6(chi2: number): number {
  if (chi2 <= 0) return 1.0;
  const s = chi2 / 2.0;
  return Math.exp(-s) * (1.0 + s + 0.5 * s * s);
}

export interface ForwardModelResult {
  sedObs: SedPoint[];
  sedRestModified: SedPoint[];
  fluxes: Record<string, number>;
  mags: Record<string, number>;
  magErrs: Record<string, number>;
  snr: Record<string, number>;
  apparentMag: number;
}

/**
 * In-browser scientific forward-modeling engine.
 * Takes a galaxy's rest-frame FSPS spectrum L_lambda [L_sun / A] and applies:
 *  1. Additional dust attenuation (deltaAv = targetAv - baseAv) via Charlot & Fall (2000).
 *  2. Redshift wavelength expansion lambda_obs = lambda_rest * (1 + targetZ).
 *  3. Cosmological physical distance dimming 1 / [4 * pi * D_L(targetZ)^2 * (1 + targetZ)].
 *  4. Intergalactic Medium (IGM) Madau (1995) absorption.
 *  5. Broadband NIRCam bandpass numerical integration with ETC noise.
 */
export function forwardModelGalaxy(
  sedRest: SedPoint[],
  baseZ: number,
  targetZ: number,
  baseAv: number,
  targetAv: number,
  filters: FilterCurveData[]
): ForwardModelResult {
  const deltaAv = targetAv - baseAv;
  const z = Math.max(0.01, targetZ);
  const zP1 = 1.0 + z;

  const dlCm = luminosityDistanceCm(z);
  const dimmingFactor = L_SUN_ERG_S / (4.0 * Math.PI * dlCm * dlCm * zP1);

  const sedRestModified: SedPoint[] = [];
  const sedObs: SedPoint[] = [];
  const waveObsArr: number[] = [];
  const fObsArr: number[] = [];

  for (let i = 0; i < sedRest.length; i++) {
    const wRest = sedRest[i].wave;
    const lRest = sedRest[i].flux;

    // 1. Dust modification
    const tDust = charlotFallAttenuation(wRest, deltaAv);
    const lRestMod = Math.max(1e-12, lRest * tDust);
    sedRestModified.push({ wave: wRest, flux: lRestMod });

    // 2. Redshift expansion
    const wObs = wRest * zP1;

    // 3. Cosmological dimming & IGM attenuation
    const tIgm = madauIgmTransmission(wObs, z);
    const fObs = lRestMod * dimmingFactor * tIgm;

    waveObsArr.push(wObs);
    fObsArr.push(fObs);
    sedObs.push({ wave: Number(wObs.toFixed(1)), flux: fObs });
  }

  // 4. Numerical bandpass integration
  const fluxes: Record<string, number> = {};
  const mags: Record<string, number> = {};
  const magErrs: Record<string, number> = {};
  const snr: Record<string, number> = {};

  for (const flt of filters) {
    const fLam = integrateBandpass(waveObsArr, fObsArr, flt.wave, flt.transmission);
    fluxes[flt.name] = fLam;

    const fNu = fLambdaToFNu(fLam, flt.pivot_wavelength);
    const mag = fluxToAbMag(fNu);
    mags[flt.name] = Number(mag.toFixed(2));

    const noise = getPhotometricUncertainty(fNu, flt.name);
    magErrs[flt.name] = noise.magErr;
    snr[flt.name] = noise.snr;
  }

  const apparentMag = mags['jwst_f200w'] || 24.5;

  return {
    sedObs,
    sedRestModified,
    fluxes,
    mags,
    magErrs,
    snr,
    apparentMag,
  };
}

/**
 * Computes color-redshift evolutionary track for a galaxy across z in [0.2, 8.5].
 */
export function computeEvolutionaryTrack(
  sedRest: SedPoint[],
  baseZ: number,
  baseAv: number,
  filters: FilterCurveData[],
  zSteps: number[] = [0.2, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 8.5]
): Array<{ z: number; color1: number; color2: number }> {
  const track: Array<{ z: number; color1: number; color2: number }> = [];

  for (const zVal of zSteps) {
    const res = forwardModelGalaxy(sedRest, baseZ, zVal, baseAv, baseAv, filters);
    const m150 = res.mags['jwst_f150w'] ?? 26.0;
    const m200 = res.mags['jwst_f200w'] ?? 26.0;
    const m277 = res.mags['jwst_f277w'] ?? 26.0;
    const m444 = res.mags['jwst_f444w'] ?? 26.0;

    const color1 = Number((m150 - m444).toFixed(2));
    const color2 = Number((m200 - m277).toFixed(2));
    track.push({ z: zVal, color1, color2 });
  }

  return track;
}
