/**
 * Automated Unit Test Suite for PerandamΨ In-Browser Physics Engine.
 * Executed via Node.js native test runner: node --experimental-strip-types --test
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  comovingDistanceMpc,
  luminosityDistanceMpc,
  luminosityDistanceCm,
  charlotFallAttenuation,
  madauIgmTransmission,
  fLambdaToFNu,
  fluxToAbMag,
  abMagToFNu,
  chi2SurvivalDf6,
  integrateBandpass,
  forwardModelGalaxy,
  computeEvolutionaryTrack,
} from '../src/utils/physics.ts';

test('Physics: Cosmological Distances (FlatLambdaCDM)', () => {
  // Test comoving distance and luminosity distance at z=1.0 with Planck 2015 parameters
  const dc = comovingDistanceMpc(1.0);
  const dl = luminosityDistanceMpc(1.0);

  // Exact physical relation: D_L = (1 + z) * D_C
  assert.ok(Math.abs(dl - (1.0 + 1.0) * dc) < 1e-4, 'D_L must equal (1 + z) * D_C');
  assert.ok(dl > 6700 && dl < 6900, `Expected dL ~ 6792 Mpc, got ${dl}`);

  // Low-z Hubble law limit: D_L ~ c*z / H0 for z << 1
  const dl_low = luminosityDistanceMpc(0.01);
  const hubble_pred = (299792.458 * 0.01) / 67.74;
  const rel_err = Math.abs(dl_low - hubble_pred) / hubble_pred;
  assert.ok(rel_err < 0.02, `Low-z Hubble law agreement violated: rel_err=${rel_err}`);
});

test('Physics: Charlot & Fall (2000) Dust Attenuation', () => {
  // At deltaAv = 0, transmission must be exactly 1.0
  assert.strictEqual(charlotFallAttenuation(5500, 0.0), 1.0);

  // At V-band (5500 A), deltaAv = 1.0 mag -> factor = 10^(-0.4 * 1.0) = 0.398107
  const t_v = charlotFallAttenuation(5500, 1.0);
  assert.ok(Math.abs(t_v - 0.3981) < 1e-3, `V-band transmission must be ~0.3981, got ${t_v}`);

  // UV extinction must be stronger than optical extinction
  const t_uv = charlotFallAttenuation(1500, 1.0);
  const t_nir = charlotFallAttenuation(22000, 1.0);
  assert.ok(t_uv < t_v, `UV transmission (${t_uv}) must be strictly less than V (${t_v})`);
  assert.ok(t_v < t_nir, `Optical transmission (${t_v}) must be strictly less than NIR (${t_nir})`);
});

test('Physics: Madau (1995) IGM Absorption', () => {
  const z = 3.0;

  // Redward of Ly-alpha (1215.67 * (1 + z) = 4862.68 A), transmission must be 1.0
  const t_redward = madauIgmTransmission(5500, z);
  assert.strictEqual(t_redward, 1.0, 'Redward of Ly-alpha must experience 0 absorption');

  // In Lyman-alpha valley (e.g. 4000 A), transmission must be attenuated
  const t_valley = madauIgmTransmission(4000, z);
  assert.ok(t_valley < 1.0 && t_valley > 0.0, `Lyman valley transmission must be attenuated: ${t_valley}`);

  // Shortward of Lyman limit (911.75 * (1 + z) = 3647 A), strong photoelectric cutoff
  const t_lyman_limit = madauIgmTransmission(3000, z);
  assert.ok(t_lyman_limit < t_valley, `Photoelectric cutoff must be stronger than valley: ${t_lyman_limit} < ${t_valley}`);
});

test('Physics: Photometric Units & AB Zero Point', () => {
  // A 3631 Jy flat source has m_AB = 0.000 by definition
  // 3631 Jy = 3.631e-20 erg/s/cm^2/Hz
  const f_nu_3631jy = 3631e-23; // 1 Jy = 1e-23 erg/s/cm^2/Hz
  const mag_zero = fluxToAbMag(f_nu_3631jy);
  assert.ok(Math.abs(mag_zero - 0.0) < 1e-3, `3631 Jy must yield m_AB = 0.000 mag, got ${mag_zero}`);

  // Round-trip conversion: AB mag -> f_nu -> AB mag
  const test_mag = 24.5;
  const f_nu_round = abMagToFNu(test_mag);
  const mag_round = fluxToAbMag(f_nu_round);
  assert.ok(Math.abs(mag_round - test_mag) < 1e-4, 'AB mag round-trip conversion failed');
});

test('Physics: Chi^2 Survival Probability (df = 6)', () => {
  // chi2 = 0 -> p = 1.0
  assert.strictEqual(chi2SurvivalDf6(0.0), 1.0);

  // chi2 = 6.0 (mean for df=6): s = 3.0, P = exp(-3) * (1 + 3 + 4.5) = 8.5 * exp(-3) ~ 0.42319
  const p6 = chi2SurvivalDf6(6.0);
  assert.ok(Math.abs(p6 - 0.4232) < 1e-3, `P(chi2 >= 6) must be ~0.4232, got ${p6}`);

  // Large chi2 -> small p-value
  const p20 = chi2SurvivalDf6(20.0);
  assert.ok(p20 < 0.005, `P(chi2 >= 20) must be < 0.005, got ${p20}`);
});

test('Physics: In-Browser Forward Modeling & Evolutionary Tracks', () => {
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);
  const catalogPath = path.resolve(__dirname, '../src/data/tng_100_calibration.json');
  const data = JSON.parse(fs.readFileSync(catalogPath, 'utf8'));

  const sampleGalaxy = data.galaxies[0];
  const filters = data.filters;

  // Forward model the galaxy: sedRest, baseZ, targetZ, baseAv, targetAv, filters
  const result = forwardModelGalaxy(sampleGalaxy.sed, sampleGalaxy.redshift, 1.5, sampleGalaxy.av, 0.5, filters);

  assert.ok(result.sedObs.length > 0, 'Must produce observed SED points');
  assert.ok(result.fluxes['jwst_f150w'] !== undefined, 'Must produce F150W flux');
  assert.ok(result.mags['jwst_f150w'] !== undefined, 'Must produce F150W magnitude');
  assert.ok(result.mags['jwst_f150w'] > 15 && result.mags['jwst_f150w'] < 25, `Expected mag ~ 18.69, got ${result.mags['jwst_f150w']}`);

  // Compute evolutionary track across z in [0.2, 8.5]
  const track = computeEvolutionaryTrack(sampleGalaxy.sed, sampleGalaxy.redshift, sampleGalaxy.av, filters);
  assert.ok(track.length > 5, 'Track must contain multiple redshift steps');
  assert.strictEqual(track[0].z, 0.2, 'Track start redshift must be 0.2');
});
