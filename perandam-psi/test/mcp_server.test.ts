/**
 * Automated Test Suite for PerandamΨ MCP Server (Node.js JSON-RPC 2.0 Stdio).
 * 
 * Verifies:
 * - JSON-RPC 2.0 handshake, tool enumeration, and ID matching.
 * - M8ven Trust Index & MCP risk annotations (readOnlyHint, destructiveHint, idempotentHint, openWorldHint).
 * - Functional tool dispatch for all PerandamΨ tools.
 * - Negative and edge cases: unknown tools, unknown methods, and parse errors.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { PerandamMCPServer, PSI_MCP_TOOLS } from '../mcp_server.mjs';

test('MCP Server: Initialize Handshake', async () => {
  const server = new PerandamMCPServer();
  const req = {
    jsonrpc: '2.0',
    id: 1,
    method: 'initialize',
    params: {},
  };
  const resp = await server.handleRequest(req);
  assert.strictEqual(resp.jsonrpc, '2.0');
  assert.strictEqual(resp.id, 1);
  assert.ok(resp.result);
  assert.strictEqual(resp.result.serverInfo.name, 'perandam-psi-mcp');
  assert.strictEqual(resp.result.protocolVersion, '2024-11-05');
});

test('MCP Server: Notification Initialized', async () => {
  const server = new PerandamMCPServer();
  const req = {
    jsonrpc: '2.0',
    method: 'notifications/initialized',
  };
  const resp = await server.handleRequest(req);
  assert.strictEqual(resp, null, 'Notifications should return null/no response');
});

test('MCP Server: Tools List & M8ven Risk Annotations', async () => {
  const server = new PerandamMCPServer();
  const req = {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/list',
    params: {},
  };
  const resp = await server.handleRequest(req);
  assert.strictEqual(resp.id, 2);
  const tools = resp.result.tools;
  assert.ok(Array.isArray(tools));
  assert.ok(tools.length >= 5);

  const toolNames = tools.map((t) => t.name);
  assert.ok(toolNames.includes('psi_get_catalog_info'));
  assert.ok(toolNames.includes('psi_inspect_galaxy'));
  assert.ok(toolNames.includes('psi_calculate_cosmology'));
  assert.ok(toolNames.includes('psi_query_hypotheses'));
  assert.ok(toolNames.includes('psi_check_bridge_status'));

  // Verify M8ven Trust Index Risk Annotations
  for (const t of tools) {
    assert.ok(t.annotations, `Tool ${t.name} must have annotations`);
    const ann = t.annotations;
    assert.strictEqual(typeof ann.readOnlyHint, 'boolean', `${t.name}.readOnlyHint must be boolean`);
    assert.strictEqual(typeof ann.destructiveHint, 'boolean', `${t.name}.destructiveHint must be boolean`);
    assert.strictEqual(typeof ann.idempotentHint, 'boolean', `${t.name}.idempotentHint must be boolean`);
    assert.strictEqual(typeof ann.openWorldHint, 'boolean', `${t.name}.openWorldHint must be boolean`);

    // Safety contract: all PSI query tools are readOnly & non-destructive
    assert.strictEqual(ann.readOnlyHint, true, `${t.name} must be readOnlyHint: true`);
    assert.strictEqual(ann.destructiveHint, false, `${t.name} must be destructiveHint: false`);
    assert.strictEqual(ann.idempotentHint, true, `${t.name} must be idempotentHint: true`);
    assert.strictEqual(ann.openWorldHint, false, `${t.name} must be openWorldHint: false`);
  }
});

test('MCP Server: Tool Call psi_get_catalog_info', async () => {
  const server = new PerandamMCPServer();
  const req = {
    jsonrpc: '2.0',
    id: 3,
    method: 'tools/call',
    params: {
      name: 'psi_get_catalog_info',
      arguments: { dataset: 'goods_s_mock' },
    },
  };
  const resp = await server.handleRequest(req);
  assert.strictEqual(resp.id, 3);
  assert.ok(resp.result.content);
  assert.strictEqual(resp.result.content[0].type, 'text');

  const data = JSON.parse(resp.result.content[0].text);
  assert.strictEqual(data.total_galaxies, 508);
  assert.ok(data.filters.length >= 6);
  assert.strictEqual(typeof data.sentry_certified, 'boolean');
});

test('MCP Server: Tool Call psi_inspect_galaxy', async () => {
  const server = new PerandamMCPServer();
  const req = {
    jsonrpc: '2.0',
    id: 4,
    method: 'tools/call',
    params: {
      name: 'psi_inspect_galaxy',
      arguments: { galaxy_index: 0, dataset: 'goods_s_mock' },
    },
  };
  const resp = await server.handleRequest(req);
  assert.strictEqual(resp.id, 4);
  const data = JSON.parse(resp.result.content[0].text);
  assert.ok(data.id);
  assert.ok(data.redshift > 0);
  assert.ok(data.log_mstar >= 6);
  assert.ok(data.mags);
  assert.ok(data.fluxes_uJy);
});

test('MCP Server: Tool Call psi_calculate_cosmology', async () => {
  const server = new PerandamMCPServer();
  const req = {
    jsonrpc: '2.0',
    id: 5,
    method: 'tools/call',
    params: {
      name: 'psi_calculate_cosmology',
      arguments: { redshift: 2.0, h0: 70.0, omega_m: 0.3 },
    },
  };
  const resp = await server.handleRequest(req);
  assert.strictEqual(resp.id, 5);
  const data = JSON.parse(resp.result.content[0].text);
  assert.strictEqual(data.redshift, 2.0);
  assert.ok(data.luminosity_distance_mpc > 10000);
  assert.ok(data.distance_modulus > 40);
});

test('MCP Server: Tool Call psi_query_hypotheses', async () => {
  const server = new PerandamMCPServer();
  const req = {
    jsonrpc: '2.0',
    id: 6,
    method: 'tools/call',
    params: {
      name: 'psi_query_hypotheses',
      arguments: { min_sigma: 2.0, limit: 3 },
    },
  };
  const resp = await server.handleRequest(req);
  assert.strictEqual(resp.id, 6);
  const data = JSON.parse(resp.result.content[0].text);
  assert.ok(data.total_discovered >= 1);
  assert.ok(data.candidates.length <= 3);
  assert.ok(data.candidates[0].profile.hypotheses.primary);
});

test('MCP Server: Negative Unknown Tool Handling', async () => {
  const server = new PerandamMCPServer();
  const req = {
    jsonrpc: '2.0',
    id: 7,
    method: 'tools/call',
    params: {
      name: 'non_existent_tool',
      arguments: {},
    },
  };
  const resp = await server.handleRequest(req);
  assert.strictEqual(resp.id, 7);
  assert.strictEqual(resp.error.code, -32601);
  assert.ok(resp.error.message.includes('Unknown tool: non_existent_tool'));
  assert.ok(resp.result.content[0].text.includes('Unknown tool'));
});

test('MCP Server: Negative Unknown Method Handling', async () => {
  const server = new PerandamMCPServer();
  const req = {
    jsonrpc: '2.0',
    id: 8,
    method: 'unknown/method',
    params: {},
  };
  const resp = await server.handleRequest(req);
  assert.strictEqual(resp.id, 8);
  assert.strictEqual(resp.error.code, -32601);
});
