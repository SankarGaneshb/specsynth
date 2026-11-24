/**
 * Model Context Protocol (MCP) Client for Perandam Space Intelligence (PerandamΨ).
 * Connects the web frontend to the SpecSynth MCP Bridge (localhost:8000).
 * Implements JSON-RPC 2.0 transport, tool invocation, and M8ven Trust Index validation.
 */

export interface MCPToolAnnotations {
  readOnlyHint: boolean;
  destructiveHint: boolean;
  idempotentHint: boolean;
  openWorldHint: boolean;
}

export interface MCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, any>;
  annotations: MCPToolAnnotations;
}

export interface MCPRequest<T = any> {
  jsonrpc: '2.0';
  id: number | string;
  method: string;
  params?: T;
}

export interface MCPResponse<T = any> {
  jsonrpc: '2.0';
  id: number | string | null;
  result?: T;
  error?: {
    code: number;
    message: string;
    data?: any;
  };
}

export interface BridgeHealthResponse {
  service: string;
  mark: string;
  status: string;
  version: string;
  frontend_url?: string;
  endpoints?: Record<string, string>;
}

export class MCPBridgeClient {
  private baseUrl: string;
  private reqId: number = 0;

  constructor(baseUrl: string = 'http://127.0.0.1:8000') {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  private nextId(): number {
    this.reqId += 1;
    return this.reqId;
  }

  /**
   * Health check probe against SpecSynth MCP HTTP Bridge.
   */
  async checkHealth(): Promise<BridgeHealthResponse> {
    const res = await fetch(`${this.baseUrl}/api/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) {
      throw new Error(`Health check failed with HTTP ${res.status}: ${res.statusText}`);
    }
    return res.json();
  }

  /**
   * Query all registered tools and their safety annotations from the MCP server.
   */
  async listTools(): Promise<MCPTool[]> {
    const payload: MCPRequest = {
      jsonrpc: '2.0',
      id: this.nextId(),
      method: 'tools/list',
      params: {},
    };

    const res = await fetch(`${this.baseUrl}/api/tools/call`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`Failed to list MCP tools: HTTP ${res.status}`);
    }

    const data: MCPResponse<{ tools: MCPTool[] }> = await res.json();
    if (data.error) {
      throw new Error(`MCP Error ${data.error.code}: ${data.error.message}`);
    }

    return data.result?.tools || [];
  }

  /**
   * Dispatch a generic tool call to the MCP server.
   */
  async callTool<T = any>(toolName: string, args: Record<string, any> = {}): Promise<T> {
    const payload = {
      name: toolName,
      arguments: args,
    };

    const res = await fetch(`${this.baseUrl}/api/tools/call`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`Tool execution '${toolName}' failed: HTTP ${res.status}`);
    }

    const json = await res.json();
    if (json.error) {
      throw new Error(`Tool '${toolName}' error ${json.error.code}: ${json.error.message}`);
    }

    // In MCP, result content is an array of text/binary blocks
    if (json.result?.content && Array.isArray(json.result.content)) {
      const textBlock = json.result.content.find((b: any) => b.type === 'text');
      if (textBlock?.text) {
        try {
          return JSON.parse(textBlock.text) as T;
        } catch {
          return textBlock.text as unknown as T;
        }
      }
    }

    return (json.result ?? json) as T;
  }

  /**
   * List available filter sets (e.g. JWST NIRCam, Roman WFI, HST, Euclid).
   */
  async listFilters(instrument?: string): Promise<any> {
    return this.callTool('sps_list_filters', instrument ? { instrument } : {});
  }

  /**
   * Inspect synthesized properties, flux, and SFH for a galaxy by index.
   */
  async inspectGalaxy(galaxyIdx: number, base: string = './run'): Promise<any> {
    return this.callTool('sps_inspect_galaxy', { galaxy_idx: galaxyIdx, base });
  }

  /**
   * Run 4-tier automated Scientific Sentry audit.
   */
  async runSentryAudit(sampleSize: number = 10000, base: string = './run'): Promise<any> {
    return this.callTool('sps_run_sentry_audit', { sample_size: sampleSize, base });
  }

  /**
   * Load validated IllustrisTNG -> JWST NIRCam demonstration sample.
   */
  async loadTngDemo(limit: number = 5): Promise<any> {
    return this.callTool('sps_load_tng_demo', { limit });
  }

  /**
   * Get host hardware capabilities (CPU, RAM, GPU/BLAS).
   */
  async getSystemInfo(): Promise<any> {
    return this.callTool('sps_get_system_info', {});
  }

  /**
   * Validates tool adherence to M8ven MCP Registry & Trust Index risk vocabulary.
   */
  static validateSafetyContract(tool: MCPTool): {
    isValid: boolean;
    isReadOnly: boolean;
    isDestructive: boolean;
    isIdempotent: boolean;
    isOpenWorld: boolean;
  } {
    const ann = tool.annotations;
    if (!ann) {
      return {
        isValid: false,
        isReadOnly: false,
        isDestructive: false,
        isIdempotent: false,
        isOpenWorld: false,
      };
    }

    const hasAllFlags =
      typeof ann.readOnlyHint === 'boolean' &&
      typeof ann.destructiveHint === 'boolean' &&
      typeof ann.idempotentHint === 'boolean' &&
      typeof ann.openWorldHint === 'boolean';

    return {
      isValid: hasAllFlags,
      isReadOnly: ann.readOnlyHint,
      isDestructive: ann.destructiveHint,
      isIdempotent: ann.idempotentHint,
      isOpenWorld: ann.openWorldHint,
    };
  }
}
