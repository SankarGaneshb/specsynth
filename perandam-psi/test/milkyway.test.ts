import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  MILKY_WAY_BENCHMARK,
  MILKY_WAY_GALAXY,
  getMilkyWayProgenitorExpected,
  estimatePhysicalRadiusKpc,
  compareWithMilkyWay,
} from '../src/utils/milkyway.ts';
import type { Galaxy } from '../src/types/galaxy.ts';

test('MilkyWay: Benchmark Constants Validation', () => {
  assert.equal(MILKY_WAY_BENCHMARK.logMstar, 10.78);
  assert.equal(MILKY_WAY_BENCHMARK.sfr, 1.65);
  assert.equal(MILKY_WAY_BENCHMARK.scaleLengthKpc, 2.6);
  assert.equal(MILKY_WAY_BENCHMARK.opticalDiameterKpc, 26.8);
  assert.equal(MILKY_WAY_GALAXY.id, 'MILKY_WAY');
  assert.equal(MILKY_WAY_GALAXY.redshift, 0.0);
  assert.equal(MILKY_WAY_GALAXY.log_mstar, 10.78);
});

test('MilkyWay: Progenitor Evolutionary Track (van Dokkum et al. 2013)', () => {
  // At z = 0, progenitor expected should match modern Milky Way
  const progZ0 = getMilkyWayProgenitorExpected(0);
  assert.ok(Math.abs(progZ0.logMass - 10.78) < 1e-3);
  assert.ok(Math.abs(progZ0.sfr - 1.65) < 1e-3);

  // At z = 2.0 (Cosmic Noon, 10.5 Gyr ago):
  // Expected mass ~ 9.98 (~15% modern mass), SFR ~ 18.5 M_sun/yr (11x modern rate)
  const progZ2 = getMilkyWayProgenitorExpected(2.0);
  assert.ok(Math.abs(progZ2.logMass - 9.98) < 0.05, `Expected logM ~ 9.98 at z=2, got ${progZ2.logMass}`);
  assert.ok(progZ2.sfr > 15 && progZ2.sfr < 22, `Expected SFR ~ 18.5 at z=2, got ${progZ2.sfr}`);

  // At z = 3.0:
  const progZ3 = getMilkyWayProgenitorExpected(3.0);
  assert.ok(progZ3.logMass < progZ2.logMass, 'Progenitor mass must decrease into earlier cosmic epochs');
  assert.ok(progZ3.sfr > progZ2.sfr, 'Progenitor SFR must be elevated at higher redshift');
});

test('MilkyWay: Mass-Size Relation Scaling', () => {
  const rZ0 = estimatePhysicalRadiusKpc(10.78, 0.0);
  const rZ2 = estimatePhysicalRadiusKpc(10.78, 2.0);

  // High-z galaxies are physically more compact for the same mass
  assert.ok(rZ2 < rZ0, `Expected r(z=2) < r(z=0), got ${rZ2} vs ${rZ0}`);
});

test('MilkyWay: Comparison Model & Progenitor Detection', () => {
  // Create a genuine Cosmic Noon progenitor match at z = 2.0
  const progenitorGalaxy: Galaxy = {
    id: 'TNG-PROG-01',
    ra: 53.15,
    dec: -27.78,
    redshift: 2.0,
    stellar_mass: 1.0e10,
    log_mstar: 10.0,
    sfr: 20.0,
    av: 0.5,
    tau_diffuse: 0.3,
    tau_birth: 0.7,
    sentry_status: 'PRISTINE',
    apparent_mag: 24.0,
    fluxes: {},
    mags: {},
    sed: [],
  };

  const comp = compareWithMilkyWay(progenitorGalaxy);
  assert.ok(comp.isProgenitorCandidate, 'Should classify as Milky Way progenitor candidate');
  assert.ok(comp.progenitorScorePercent >= 60, `Progenitor score should be >= 60%, got ${comp.progenitorScorePercent}%`);
  assert.ok(comp.classificationTitle.includes('Milky Way Progenitor Candidate'));
  assert.ok(comp.sfrMultiplier > 10, 'SFR multiplier should be > 10x Milky Way');
});
