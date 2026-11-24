/**
 * Automated Test Suite for PerandamΨ MCP Bridge Client (TypeScript).
 * Validates protocol request construction, tool invocation, M8ven risk contract validation,
 * and error handling.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { MCPBridgeClient } from '../src/utils/mcpClient.ts';
import type { MCPTool } from '../src/utils/mcpClient.ts';

test('MCP Client: Safety Contract Validator (M8ven Trust Index)', () => {
  const readOnlyTool: MCPTool = {
    name: 'sps_list_filters',
    description: 'List available telescope filters',
    inputSchema: { type: 'object' },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  };

  const validation = MCPBridgeClient.validateSafetyContract(readOnlyTool);
  assert.strictEqual(validation.isValid, true);
  assert.strictEqual(validation.isReadOnly, true);
  assert.strictEqual(validation.isDestructive, false);
  assert.strictEqual(validation.isIdempotent, true);
  assert.strictEqual(validation.isOpenWorld, false);

  const destructiveTool: MCPTool = {
    name: 'sps_remediate_catalog',
    description: 'Remediate corrupted galaxies',
    inputSchema: { type: 'object' },
    annotations: {
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: false,
      openWorldHint: false,
    },
  };

  const destValidation = MCPBridgeClient.validateSafetyContract(destructiveTool);
  assert.strictEqual(destValidation.isValid, true);
  assert.strictEqual(destValidation.isReadOnly, false);
  assert.strictEqual(destValidation.isDestructive, true);

  // Missing annotations
  const invalidTool: any = {
    name: 'bad_tool',
    description: 'Missing flags',
    inputSchema: {},
  };
  const badValidation = MCPBridgeClient.validateSafetyContract(invalidTool);
  assert.strictEqual(badValidation.isValid, false);
});

test('MCP Client: checkHealth Endpoint Request', async () => {
  const client = new MCPBridgeClient('http://127.0.0.1:8000');

  // Mock fetch
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (url: string | URL, init?: RequestInit) => {
    assert.strictEqual(url.toString(), 'http://127.0.0.1:8000/api/health');
    return {
      ok: true,
      status: 200,
      json: async () => ({
        service: 'specsynth-mcp-bridge',
        mark: 'PerandamΨ',
        status: 'online',
        version: '1.0.0',
      }),
    } as any;
  }) as typeof fetch;

  try {
    const health = await client.checkHealth();
    assert.strictEqual(health.service, 'specsynth-mcp-bridge');
    assert.strictEqual(health.mark, 'PerandamΨ');
    assert.strictEqual(health.status, 'online');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('MCP Client: listTools Request & Annotations Parsing', async () => {
  const client = new MCPBridgeClient('http://127.0.0.1:8000');

  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (url: string | URL, init?: RequestInit) => {
    assert.strictEqual(url.toString(), 'http://127.0.0.1:8000/api/tools/call');
    const body = JSON.parse(init?.body as string);
    assert.strictEqual(body.jsonrpc, '2.0');
    assert.strictEqual(body.method, 'tools/list');

    return {
      ok: true,
      status: 200,
      json: async () => ({
        jsonrpc: '2.0',
        id: body.id,
        result: {
          tools: [
            {
              name: 'sps_list_filters',
              description: 'List filters',
              inputSchema: {},
              annotations: {
                readOnlyHint: true,
                destructiveHint: false,
                idempotentHint: true,
                openWorldHint: false,
              },
            },
          ],
        },
      }),
    } as any;
  }) as typeof fetch;

  try {
    const tools = await client.listTools();
    assert.strictEqual(tools.length, 1);
    assert.strictEqual(tools[0].name, 'sps_list_filters');
    assert.strictEqual(tools[0].annotations.readOnlyHint, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('MCP Client: callTool Dispatches and Extracts Text Content', async () => {
  const client = new MCPBridgeClient('http://127.0.0.1:8000');

  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (url: string | URL, init?: RequestInit) => {
    const body = JSON.parse(init?.body as string);
    assert.strictEqual(body.name, 'sps_list_filters');
    assert.strictEqual(body.arguments.instrument, 'jwst_nircam');

    return {
      ok: true,
      status: 200,
      json: async () => ({
        result: {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                filter_set: 'jwst_nircam',
                filters: [{ name: 'f150w', center_wavelength: 1.5 }],
              }),
            },
          ],
        },
      }),
    } as any;
  }) as typeof fetch;

  try {
    const filters = await client.listFilters('jwst_nircam');
    assert.strictEqual(filters.filter_set, 'jwst_nircam');
    assert.strictEqual(filters.filters[0].name, 'f150w');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('MCP Client: Negative Error Handling', async () => {
  const client = new MCPBridgeClient('http://127.0.0.1:8000');

  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async () => {
    return {
      ok: true,
      status: 200,
      json: async () => ({
        error: {
          code: -32601,
          message: 'Unknown tool: invalid_tool',
        },
      }),
    } as any;
  }) as typeof fetch;

  try {
    await assert.rejects(
      async () => {
        await client.callTool('invalid_tool', {});
      },
      (err: Error) => {
        return err.message.includes('Unknown tool: invalid_tool');
      }
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
