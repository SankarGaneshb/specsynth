/**
 * Automated Schema & Integrity Test Suite for PerandamΨ Datasets.
 * Validates that frontend static JSONs load and parse cleanly into TypeScript types.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('Datasets: TNG-100 Calibration Manifest', () => {
  const p = path.resolve(__dirname, '../src/data/tng_100_calibration.json');
  assert.ok(fs.existsSync(p), 'tng_100_calibration.json must exist');

  const data = JSON.parse(fs.readFileSync(p, 'utf8'));
  assert.strictEqual(data.galaxies.length, 100, 'Must contain exactly 100 calibration galaxies');
  assert.ok(data.filters.length >= 6, 'Must contain at least 6 core NIRCam filters');

  for (const g of data.galaxies) {
    assert.ok(g.id.startsWith('TNG-'), `Invalid galaxy ID: ${g.id}`);
    assert.ok(g.redshift > 0 && g.redshift < 15, `Invalid redshift: ${g.redshift}`);
    assert.ok(g.log_mstar >= 6 && g.log_mstar <= 13, `Invalid stellar mass: ${g.log_mstar}`);
    assert.ok(g.sed.length >= 400, `SED resolution too low: ${g.sed.length}`);
    assert.ok(g.mags['jwst_f150w'] !== undefined, 'Missing F150W magnitude');
  }
});

test('Datasets: GOODS-S Deep Mock (508 Galaxies)', () => {
  const p = path.resolve(__dirname, '../src/data/tng_goods_s_mock_508.json');
  assert.ok(fs.existsSync(p), 'tng_goods_s_mock_508.json must exist');

  const data = JSON.parse(fs.readFileSync(p, 'utf8'));
  assert.strictEqual(data.galaxies.length, 508, 'Must contain exactly 508 mock galaxies');

  const discoveries = data.galaxies.filter((g: any) => Boolean(g.discovery_profile));
  assert.ok(discoveries.length >= 4, `Expected at least 4 discovery candidates, got ${discoveries.length}`);

  for (const d of discoveries) {
    assert.ok(d.discovery_profile.rarity_sigma > 2.0, 'Discovery must have rarity > 2 sigma');
    assert.ok(d.discovery_profile.hypotheses.citations.length >= 1, 'Must include citations');
  }
});
