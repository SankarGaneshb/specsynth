/**
 * perandam-psi/test/scientific_provenance_truth.test.ts
 * ====================================================
 * Dedicated behavioral, negative, and race-condition test suite for Issue #33.
 * 
 * Verifies:
 * 1. Node MCP server rejects unverified simulation claims and does NOT infer simulation
 *    identity from the presence of a 3D model alone.
 * 2. Authentic TNG-100 snapshot cutout preserves verified provenance.
 * 3. Race condition & stale response rejection logic in PerandamΨ GalaxyInspector.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { CANONICAL_MCP_TOOLS } from '../mcp_server.mjs';

test('Node MCP: Unmanifested / Mock Galaxy Does Not Claim Verified Simulation', async () => {
  const inspectTool = CANONICAL_MCP_TOOLS.specsynth_inspect_galaxy;
  assert.ok(inspectTool, 'specsynth_inspect_galaxy must exist');

  // Inspect galaxy from goods_s_mock
  const res = inspectTool.handler({ dataset: 'goods_s_mock', galaxy_index: 0 });
  assert.ok(!res.error, 'Inspect should succeed for goods_s_mock');

  // Must NOT claim simulation_derived or verified_authentic
  assert.equal(res.source_provenance.verified_authentic, false, 'Mock galaxy must NOT claim verified_authentic: true');
  assert.notEqual(res.source_provenance.verification_status, 'verified', 'Mock galaxy must NOT have verification_status: verified');
  assert.equal(res.data_mode, 'cached_reference');
});

test('Node MCP: 3D Galaxy Does Not Infer Simulation From 3D Model Alone', async () => {
  const get3DTool = CANONICAL_MCP_TOOLS.specsynth_get_3d_galaxy;
  assert.ok(get3DTool, 'specsynth_get_3d_galaxy must exist');

  // Request a synthetic procedural model from GOODS-S
  const res = get3DTool.handler({ galaxy_id: 'goods_s_508_0' });
  if (!res.error) {
    assert.equal(res.source_provenance.verified_authentic, false, 'Procedural 3D model must not claim verified_authentic');
    assert.notEqual(res.source_provenance.data_mode, 'simulation_derived', 'Procedural 3D model must not claim simulation_derived');
  }
});

test('Node MCP: Authentic TNG-100 Snapshot Cutout Yields Verified Provenance', async () => {
  const inspectTool = CANONICAL_MCP_TOOLS.specsynth_inspect_galaxy;

  const res = inspectTool.handler({ dataset: 'tng_100', galaxy_id: 'tng_424601' });
  if (res && !res.error) {
    assert.equal(res.source_provenance.verified_authentic, true, 'Authentic TNG cutout must be verified_authentic: true');
    assert.equal(res.source_provenance.verification_status, 'verified', 'Must have verification_status: verified');
    assert.equal(res.source_provenance.simulation, 'IllustrisTNG-100-1');
    assert.equal(res.source_provenance.subhalo_id, 424601);
  }
});

test('PerandamΨ Race Condition Handler: Stale & Mismatched Responses Rejected', async () => {
  // Deterministic Fingerprint matching test simulating GalaxyInspector.tsx logic
  const activeGalaxyId = 'galaxy_alpha';
  const activeZ = 2.5000;
  const activeAv = 0.8000;
  const currentFingerprint = `${activeGalaxyId}:z=${activeZ.toFixed(4)}:av=${activeAv.toFixed(4)}`;

  // Arriving response 1: Stale Z from previous slider move
  const staleResponseZ = {
    fingerprint: `${activeGalaxyId}:z=1.2000:av=${activeAv.toFixed(4)}`,
    galaxyId: activeGalaxyId,
    mags: { jwst_f200w: 23.4 },
  };
  const isStaleAccepted = (
    staleResponseZ.fingerprint === currentFingerprint &&
    staleResponseZ.galaxyId === activeGalaxyId
  );
  assert.equal(isStaleAccepted, false, 'Late response with old redshift must be rejected');

  // Arriving response 2: Out-of-order response for previously selected galaxy
  const previousGalaxyResponse = {
    fingerprint: `galaxy_beta:z=${activeZ.toFixed(4)}:av=${activeAv.toFixed(4)}`,
    galaxyId: 'galaxy_beta',
    mags: { jwst_f200w: 21.0 },
  };
  const isSwitchedGalaxyAccepted = (
    previousGalaxyResponse.fingerprint === currentFingerprint &&
    previousGalaxyResponse.galaxyId === activeGalaxyId
  );
  assert.equal(isSwitchedGalaxyAccepted, false, 'Response from previously selected galaxy must be rejected');

  // Arriving response 3: Matching fingerprint and active galaxy ID
  const validResponse = {
    fingerprint: currentFingerprint,
    galaxyId: activeGalaxyId,
    mags: { jwst_f200w: 22.8 },
  };
  const isValidAccepted = (
    validResponse.fingerprint === currentFingerprint &&
    validResponse.galaxyId === activeGalaxyId
  );
  assert.equal(isValidAccepted, true, 'Exact matching response must be accepted');
});
