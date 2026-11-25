import { test } from 'node:test';
import assert from 'node:assert/strict';
import { lookbackTimeGyr, projectGalaxyTo3D, getGalaxy3DColorRgb, COSMIC_EPOCHS } from '../src/utils/cosmo3d.ts';
import type { Galaxy } from '../src/types/galaxy.ts';

test('Cosmo3D: Lookback Time (Flat Lambda-CDM)', () => {
  // z = 0 should have zero lookback time
  assert.equal(lookbackTimeGyr(0), 0);

  // z = 1.0 lookback time ~ 7.9 Gyr (+/- 0.3 Gyr)
  const tL1 = lookbackTimeGyr(1.0);
  assert.ok(tL1 > 7.5 && tL1 < 8.3, `Expected t_L(1.0) ~ 7.9 Gyr, got ${tL1}`);

  // z = 2.0 (Cosmic Noon) ~ 10.5 Gyr
  const tL2 = lookbackTimeGyr(2.0);
  assert.ok(tL2 > 10.0 && tL2 < 11.0, `Expected t_L(2.0) ~ 10.5 Gyr, got ${tL2}`);

  // z = 8.5 (Cosmic Dawn) ~ 13.1 Gyr
  const tL85 = lookbackTimeGyr(8.5);
  assert.ok(tL85 > 12.8 && tL85 < 13.4, `Expected t_L(8.5) ~ 13.1 Gyr, got ${tL85}`);
});

test('Cosmo3D: 3D Coordinate Projections', () => {
  const centerRa = 53.15;
  const centerDec = -27.78;

  const mockGalaxyLowZ: Galaxy = {
    id: 'MOCK-LOWZ',
    ra: 53.15,
    dec: -27.78,
    redshift: 0.5,
    stellar_mass: 1e10,
    log_mstar: 10.0,
    sfr: 5.0,
    av: 0.5,
    tau_diffuse: 0.3,
    tau_birth: 0.7,
    sentry_status: 'PRISTINE',
    apparent_mag: 24.0,
    fluxes: { jwst_f444w: 1.0, jwst_f200w: 1.0, jwst_f090w: 1.0 },
    mags: { jwst_f444w: 24.0 },
    sed: [],
  };

  const mockGalaxyHighZ: Galaxy = {
    ...mockGalaxyLowZ,
    id: 'MOCK-HIGHZ',
    redshift: 6.0,
  };

  const posLow = projectGalaxyTo3D(mockGalaxyLowZ, centerRa, centerDec, 0.08);
  const posHigh = projectGalaxyTo3D(mockGalaxyHighZ, centerRa, centerDec, 0.08);

  // Directly on field center -> X and Y should be ~0
  assert.ok(Math.abs(posLow[0]) < 1e-6);
  assert.ok(Math.abs(posLow[1]) < 1e-6);

  // High-z should be deeper (-Z coordinate has larger absolute magnitude)
  assert.ok(Math.abs(posHigh[2]) > Math.abs(posLow[2]));

  // Off-center galaxy should have distinct X/Y proportional to field radius
  const offCenterGalaxy: Galaxy = {
    ...mockGalaxyLowZ,
    ra: centerRa - 0.04, // halfway across the field
  };
  const posOff = projectGalaxyTo3D(offCenterGalaxy, centerRa, centerDec, 0.08);
  assert.ok(Math.abs(posOff[0]) > 20, 'Transverse X position should be widely separated across the field');
});

test('Cosmo3D: 3D Color Calculations', () => {
  const mockGalaxy: Galaxy = {
    id: 'MOCK-G1',
    ra: 53.15,
    dec: -27.78,
    redshift: 2.0,
    stellar_mass: 1e11,
    log_mstar: 11.0,
    sfr: 25.0,
    av: 0.8,
    tau_diffuse: 0.4,
    tau_birth: 0.9,
    sentry_status: 'PRISTINE',
    apparent_mag: 23.5,
    fluxes: { jwst_f444w: 2.5, jwst_f200w: 1.2, jwst_f090w: 0.4 },
    mags: { jwst_f444w: 23.5 },
    sed: [],
  };

  for (const mode of ['rgb', 'redshift', 'ssfr', 'mass'] as const) {
    const col = getGalaxy3DColorRgb(mockGalaxy, mode);
    assert.ok(col.r >= 0 && col.r <= 1, `r in range [0, 1] for mode ${mode}`);
    assert.ok(col.g >= 0 && col.g <= 1, `g in range [0, 1] for mode ${mode}`);
    assert.ok(col.b >= 0 && col.b <= 1, `b in range [0, 1] for mode ${mode}`);
  }

  // Cosmic epochs metadata verification
  assert.equal(COSMIC_EPOCHS.length, 6);
  assert.equal(COSMIC_EPOCHS[2].label, 'z = 2.0 (Cosmic Noon)');
});
