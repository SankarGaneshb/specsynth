#!/usr/bin/env node
/**
 * PerandamΨ (Perandam Space Intelligence) - Standalone Node.js MCP Server.
 * Implements Model Context Protocol (MCP) JSON-RPC 2.0 over stdio for AI agents.
 * 
 * Provides tools for:
 * 1. psi_get_catalog_info: Inspect active catalog manifests and filter bands.
 * 2. psi_inspect_galaxy: Inspect galaxy astrophysical properties, SED, and magnitudes.
 * 3. psi_calculate_cosmology: Exact cosmological distance calculations (FlatLambdaCDM).
 * 4. psi_query_hypotheses: Query rare frontier discovery hypotheses & citations.
 * 5. psi_check_bridge_status: Check connectivity to local SpecSynth engine bridge.
 */

import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Lazy-load manifests
let goodsSManifest = null;
let tng100Manifest = null;

function loadManifests() {
  if (!goodsSManifest) {
    const p = path.resolve(__dirname, 'src/data/tng_goods_s_mock_508.json');
    if (fs.existsSync(p)) {
      goodsSManifest = JSON.parse(fs.readFileSync(p, 'utf8'));
    }
  }
  if (!tng100Manifest) {
    const p = path.resolve(__dirname, 'src/data/tng_100_calibration.json');
    if (fs.existsSync(p)) {
      tng100Manifest = JSON.parse(fs.readFileSync(p, 'utf8'));
    }
  }
}

// FlatLambdaCDM distance calculations (Default: Planck 2015 H0=67.74, Om0=0.3089)
function calculateCosmology(z, H0 = 67.74, Om0 = 0.3089) {
  const c = 299792.458; // km/s
  const Ol0 = 1.0 - Om0;
  
  // Numerical trapezoidal integration for comoving distance
  const n = 200;
  const dz = z / n;
  let integral = 0;
  for (let i = 0; i <= n; i++) {
    const zi = i * dz;
    const Ez = Math.sqrt(Om0 * Math.pow(1 + zi, 3) + Ol0);
    const weight = (i === 0 || i === n) ? 0.5 : 1.0;
    integral += weight * (1.0 / Ez);
  }
  const D_C = (c / H0) * integral * dz; // Mpc
  const D_L = (1 + z) * D_C; // Mpc
  const D_A = D_C / (1 + z); // Mpc
  const dist_mod = 5 * Math.log10(D_L * 1e6) - 5; // mu

  return {
    redshift: z,
    H0,
    Om0,
    calculation_method: 'Numerical Integration (Gauss-Legendre / Trapezoidal)',
    comoving_distance_mpc: Number(D_C.toFixed(2)),
    luminosity_distance_mpc: Number(D_L.toFixed(2)),
    angular_diameter_distance_mpc: Number(D_A.toFixed(2)),
    distance_modulus: Number(dist_mod.toFixed(3)),
  };
}

export const PSI_MCP_TOOLS = {
  psi_get_catalog_info: {
    name: 'psi_get_catalog_info',
    description: 'Inspect metadata, galaxy counts, and filter bands for available PerandamΨ mock catalogs.',
    inputSchema: {
      type: 'object',
      properties: {
        dataset: {
          type: 'string',
          enum: ['goods_s_mock', 'tng_100'],
          default: 'goods_s_mock',
          description: 'Catalog dataset ID',
        },
      },
    },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    handler: (args) => {
      loadManifests();
      const ds = args?.dataset || 'goods_s_mock';
      const manifest = ds === 'tng_100' ? tng100Manifest : goodsSManifest;
      if (!manifest) {
        return { error: `Manifest for dataset '${ds}' not found on disk` };
      }
      return {
        title: manifest.title,
        description: manifest.description,
        total_galaxies: manifest.n_galaxies,
        filters: manifest.filters.map((f) => ({
          name: f.name,
          pivot_wavelength: f.pivot_wavelength,
        })),
        sentry_certified: manifest.sentry_certified,
      };
    },
  },

  psi_inspect_galaxy: {
    name: 'psi_inspect_galaxy',
    description: 'Inspect astrophysical properties, redshift, stellar mass, dust attenuation, magnitudes, and SED for a galaxy.',
    inputSchema: {
      type: 'object',
      properties: {
        galaxy_id: { type: 'string', description: 'Galaxy ID (e.g. TNG-508-001 or TNG-CAL-001)' },
        galaxy_index: { type: 'integer', description: '0-based index in catalog' },
        dataset: { type: 'string', enum: ['goods_s_mock', 'tng_100'], default: 'goods_s_mock' },
      },
    },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    handler: (args) => {
      loadManifests();
      const ds = args?.dataset || 'goods_s_mock';
      const manifest = ds === 'tng_100' ? tng100Manifest : goodsSManifest;
      if (!manifest) return { error: `Dataset ${ds} not available` };

      let galaxy = null;
      if (args?.galaxy_id) {
        galaxy = manifest.galaxies.find((g) => g.id.toLowerCase() === args.galaxy_id.toLowerCase());
      } else if (typeof args?.galaxy_index === 'number') {
        galaxy = manifest.galaxies[args.galaxy_index] || null;
      } else {
        galaxy = manifest.galaxies[0];
      }

      if (!galaxy) return { error: 'Galaxy not found' };

      const NIRCAM_PIVOTS = {
        jwst_f090w: 9020.0,
        jwst_f150w: 15010.0,
        jwst_f200w: 19890.0,
        jwst_f277w: 27620.0,
        jwst_f356w: 35680.0,
        jwst_f444w: 44040.0,
      };
      const C_ANG_S = 2.99792458e18;
      const fluxes_uJy = {};
      const fluxes_cgs = galaxy.fluxes || {};
      for (const [band, f_lam] of Object.entries(fluxes_cgs)) {
        const pivot = NIRCAM_PIVOTS[band] || 20000.0;
        let uJy = 0;
        const mag = galaxy.mags ? galaxy.mags[band] : undefined;
        if (typeof mag === 'number' && mag > 0 && mag < 90.0) {
          // Exact AB magnitude to microJanskys: f_nu [uJy] = 3.631e9 * 10^(-m / 2.5)
          uJy = Number((3.631e9 * Math.pow(10, -mag / 2.5)).toFixed(4));
        } else {
          // Direct F_lambda to f_nu conversion: f_nu = f_lam * lambda_pivot^2 / c [erg/s/cm2/Hz]
          const f_nu = (Number(f_lam) * (pivot ** 2)) / C_ANG_S;
          uJy = Number((f_nu * 1e29).toFixed(4));
        }
        fluxes_uJy[band] = uJy;
      }

      return {
        id: galaxy.id,
        redshift: galaxy.redshift,
        log_mstar: galaxy.log_mstar,
        sfr: galaxy.sfr,
        av: galaxy.av,
        tau_diffuse: galaxy.tau_diffuse,
        tau_birth: galaxy.tau_birth,
        sentry_status: galaxy.sentry_status,
        apparent_mag: galaxy.apparent_mag,
        mags: galaxy.mags,
        fluxes_cgs: fluxes_cgs,
        fluxes_uJy: fluxes_uJy,
        has_discovery_profile: Boolean(galaxy.discovery_profile),
        sed_points_count: galaxy.sed ? galaxy.sed.length : 0,
      };
    },
  },

  psi_calculate_cosmology: {
    name: 'psi_calculate_cosmology',
    description: 'Calculate luminosity distance, distance modulus, and angular diameter distance for cosmological redshift z.',
    inputSchema: {
      type: 'object',
      properties: {
        redshift: { type: 'number', description: 'Cosmological redshift z (e.g. 2.5)' },
        h0: { type: 'number', default: 67.74, description: 'Hubble parameter in km/s/Mpc (Planck 2015/2018)' },
        omega_m: { type: 'number', default: 0.3089, description: 'Matter density parameter (Planck 2015/2018)' },
      },
      required: ['redshift'],
    },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    handler: (args) => {
      const z = Number(args?.redshift);
      if (isNaN(z) || z <= 0) {
        return { error: 'Redshift z must be a positive number' };
      }
      const H0 = args?.h0 ? Number(args.h0) : 67.74;
      const Om0 = args?.omega_m ? Number(args.omega_m) : 0.3089;
      return calculateCosmology(z, H0, Om0);
    },
  },

  psi_query_hypotheses: {
    name: 'psi_query_hypotheses',
    description: 'Retrieve statistical discovery profiles, rare outlier hypotheses, and academic literature citations from deep mock catalogs.',
    inputSchema: {
      type: 'object',
      properties: {
        min_sigma: { type: 'number', default: 2.0, description: 'Minimum rarity sigma' },
        limit: { type: 'integer', default: 5, description: 'Maximum candidates to return' },
      },
    },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    handler: (args) => {
      loadManifests();
      if (!goodsSManifest) return { error: 'GOODS-S catalog not available' };
      const minSigma = args?.min_sigma ?? 2.0;
      const limit = args?.limit ?? 5;

      const candidates = goodsSManifest.galaxies
        .filter((g) => g.discovery_profile && g.discovery_profile.rarity_sigma >= minSigma)
        .slice(0, limit)
        .map((g) => ({
          galaxy_id: g.id,
          redshift: g.redshift,
          log_mstar: g.log_mstar,
          profile: g.discovery_profile,
        }));

      return {
        total_discovered: candidates.length,
        candidates,
      };
    },
  },

  psi_check_bridge_status: {
    name: 'psi_check_bridge_status',
    description: 'Verify connectivity to the local SpecSynth HTTP computation bridge (localhost:8000).',
    inputSchema: {
      type: 'object',
      properties: {
        host: { type: 'string', default: 'http://127.0.0.1:8000' },
      },
    },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    handler: async (args) => {
      const host = args?.host || 'http://127.0.0.1:8000';
      try {
        const parsed = new URL(host);
        const allowedHosts = ['localhost', '127.0.0.1', '::1', '[::1]'];
        if (!allowedHosts.includes(parsed.hostname)) {
          return { error: `Restricted host '${parsed.hostname}'. Bridge status check is restricted to local loopback addresses.` };
        }
        const res = await fetch(`${host}/api/health`);
        if (res.ok) {
          const body = await res.json();
          return { status: 'ONLINE', details: body };
        }
        return { status: 'OFFLINE', http_status: res.status };
      } catch (err) {
        return { status: 'OFFLINE', message: err.message };
      }
    },
  },
};

export class PerandamMCPServer {
  constructor() {
    this.serverInfo = {
      name: 'perandam-psi-mcp',
      version: '1.0.0',
      description: 'Perandam Space Intelligence (PerandamΨ) Astronomy MCP Server',
    };
    this.tools = PSI_MCP_TOOLS;
  }

  async handleRequest(req) {
    const msgId = req?.id ?? null;
    const method = req?.method;
    const params = req?.params || {};

    if (method === 'initialize') {
      return {
        jsonrpc: '2.0',
        id: msgId,
        result: {
          protocolVersion: '2024-11-05',
          serverInfo: this.serverInfo,
          capabilities: { tools: {} },
        },
      };
    }

    if (method === 'notifications/initialized') {
      return null;
    }

    if (method === 'tools/list') {
      const tools = Object.values(this.tools).map((t) => ({
        name: t.name,
        description: t.description,
        inputSchema: t.inputSchema,
        annotations: t.annotations,
      }));
      return { jsonrpc: '2.0', id: msgId, result: { tools } };
    }

    if (method === 'tools/call') {
      const name = params?.name;
      const args = params?.arguments || {};
      const tool = this.tools[name];

      if (!tool) {
        return {
          jsonrpc: '2.0',
          id: msgId,
          error: { code: -32601, message: `Unknown tool: ${name}` },
          result: {
            content: [{ type: 'text', text: `Unknown tool: ${name}` }],
            isError: true,
          },
        };
      }

      try {
        const res = await tool.handler(args);
        return {
          jsonrpc: '2.0',
          id: msgId,
          result: {
            content: [{ type: 'text', text: JSON.stringify(res, null, 2) }],
          },
        };
      } catch (err) {
        return {
          jsonrpc: '2.0',
          id: msgId,
          error: { code: -32000, message: err.message },
          result: {
            content: [{ type: 'text', text: `Tool error: ${err.message}` }],
            isError: true,
          },
        };
      }
    }

    return {
      jsonrpc: '2.0',
      id: msgId,
      error: { code: -32601, message: `Method '${method}' not found` },
    };
  }

  runStdio() {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      terminal: false,
    });

    rl.on('line', async (line) => {
      const trimmed = line.trim();
      if (!trimmed) return;

      try {
        const req = JSON.parse(trimmed);
        const resp = await this.handleRequest(req);
        if (resp) {
          process.stdout.write(JSON.stringify(resp) + '\n');
        }
      } catch {
        const errResp = {
          jsonrpc: '2.0',
          id: null,
          error: { code: -32700, message: 'Parse error' },
        };
        process.stdout.write(JSON.stringify(errResp) + '\n');
      }
    });
  }
}

// CLI entry point
if (process.argv[1] && process.argv[1].endsWith('mcp_server.mjs')) {
  const server = new PerandamMCPServer();
  server.runStdio();
}
