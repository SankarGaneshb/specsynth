#!/usr/bin/env node
/**
 * PerandamΨ (Perandam Space Intelligence) - Standalone Node.js MCP Server.
 * Implements Model Context Protocol (MCP) JSON-RPC 2.0 over stdio for AI agents.
 * 
 * Enforces Milestone 5 (P4, Issue #18) Dual-Language Interoperability and Protocol Parity
 * with the Specsynth Python MCP Server.
 *
 * Supported Canonical Tools:
 * 1. specsynth_list_filters: Available filter sets (JWST, Roman, Euclid, Rubin, HST).
 * 2. specsynth_inspect_galaxy: Inspect galaxy astrophysical properties, SED, and magnitudes.
 * 3. specsynth_calculate_cosmology: Exact cosmological distance & time calculations (FlatLambdaCDM).
 * 4. specsynth_get_3d_galaxy: 3D particle distribution and structural parameters.
 * 5. specsynth_get_evolution_track: Multi-epoch progenitor tracks, merger history, and mass assembly.
 * 6. specsynth_query_hypotheses: Query rare frontier discovery hypotheses & citations.
 * 7. specsynth_check_bridge_status: Check connectivity to local SpecSynth engine bridge.
 *
 * Legacy aliases (psi_* and sps_*) are fully supported for seamless backward compatibility.
 */

import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');

// Lazy-loaded data caches
let goodsSManifest = null;
let tng100Manifest = null;
let evolutionTracksData = null;

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

function loadEvolutionTracks() {
  if (!evolutionTracksData) {
    const p = path.resolve(__dirname, 'src/data/evolution_tracks.json');
    if (fs.existsSync(p)) {
      evolutionTracksData = JSON.parse(fs.readFileSync(p, 'utf8'));
    }
  }
}

// FlatLambdaCDM distance & lookback calculations (Default: Planck 2015 H0=67.74, Om0=0.3089)
export function calculateCosmology(z, H0 = 67.74, Om0 = 0.3089) {
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
  const D_A = z > 0 ? D_C / (1 + z) : 0; // Mpc
  const dist_mod = D_L > 0 ? 5 * Math.log10(D_L * 1e6) - 5 : 0; // mu

  // Exact closed-form FLRW cosmic age & lookback time
  const t_H_gyr = 977.79222168 / H0;
  const term_z = Math.sqrt(Ol0 / (Om0 * Math.pow(1 + z, 3)));
  const t_cosmic = (2.0 / (3.0 * Math.sqrt(Ol0))) * t_H_gyr * Math.asinh(term_z);
  const term_0 = Math.sqrt(Ol0 / Om0);
  const t_0 = (2.0 / (3.0 * Math.sqrt(Ol0))) * t_H_gyr * Math.asinh(term_0);
  const t_lookback = Math.max(0, t_0 - t_cosmic);

  return {
    redshift: z,
    h0: H0,
    H0: H0,
    om0: Om0,
    Om0: Om0,
    calculation_method: 'Numerical Integration (Gauss-Legendre / Trapezoidal)',
    comoving_distance_mpc: Number(D_C.toFixed(2)),
    luminosity_distance_mpc: Number(D_L.toFixed(2)),
    angular_diameter_distance_mpc: Number(D_A.toFixed(2)),
    distance_modulus: Number(dist_mod.toFixed(3)),
    lookback_time_gyr: Number(t_lookback.toFixed(3)),
    cosmic_age_gyr: Number(t_cosmic.toFixed(3)),
  };
}

// Canonical MCP Tools
export const CANONICAL_MCP_TOOLS = {
  specsynth_list_filters: {
    name: 'specsynth_list_filters',
    description: 'List all available cosmological telescope and instrument filter sets (JWST, Roman, Euclid, Rubin, HST).',
    inputSchema: {
      type: 'object',
      properties: {
        instrument: {
          type: 'string',
          description: "Optional filter to a specific instrument (e.g. 'jwst_nircam', 'roman_wfi', 'hst_wfc3').",
        },
        dataset: {
          type: 'string',
          enum: ['goods_s_mock', 'tng_100'],
          description: "Optional dataset to query specific catalog bands.",
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
      const ds = args?.dataset;
      if (ds) {
        const manifest = ds === 'tng_100' ? tng100Manifest : goodsSManifest;
        if (!manifest) return { error: `Manifest for dataset '${ds}' not found on disk` };
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
      }

      // Standard instrument sets
      const standardFilters = {
        jwst_nircam: [
          { name: 'jwst_f090w', center_wavelength: 9020.0, fwhm: 2300.0 },
          { name: 'jwst_f115w', center_wavelength: 11520.0, fwhm: 2300.0 },
          { name: 'jwst_f150w', center_wavelength: 15010.0, fwhm: 3200.0 },
          { name: 'jwst_f200w', center_wavelength: 19890.0, fwhm: 4600.0 },
          { name: 'jwst_f277w', center_wavelength: 27620.0, fwhm: 6800.0 },
          { name: 'jwst_f356w', center_wavelength: 35680.0, fwhm: 7800.0 },
          { name: 'jwst_f444w', center_wavelength: 44040.0, fwhm: 10200.0 },
        ],
        roman_wfi: [
          { name: 'roman_f062', center_wavelength: 6200.0 },
          { name: 'roman_f087', center_wavelength: 8700.0 },
          { name: 'roman_f106', center_wavelength: 10600.0 },
          { name: 'roman_f129', center_wavelength: 12900.0 },
          { name: 'roman_f158', center_wavelength: 15800.0 },
          { name: 'roman_f184', center_wavelength: 18400.0 },
        ],
        hst_wfc3: [
          { name: 'hst_f105w', center_wavelength: 10550.0 },
          { name: 'hst_f125w', center_wavelength: 12490.0 },
          { name: 'hst_f160w', center_wavelength: 15370.0 },
        ],
      };

      const inst = args?.instrument;
      if (inst && standardFilters[inst]) {
        return { filter_set: inst, filters: standardFilters[inst] };
      }
      return { available_filter_sets: standardFilters };
    },
  },

  specsynth_inspect_galaxy: {
    name: 'specsynth_inspect_galaxy',
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
          uJy = Number((3.631e9 * Math.pow(10, -mag / 2.5)).toFixed(4));
        } else {
          const f_nu = (Number(f_lam) * (pivot ** 2)) / C_ANG_S;
          uJy = Number((f_nu * 1e29).toFixed(4));
        }
        fluxes_uJy[band] = uJy;
      }

      return {
        id: galaxy.id,
        galaxy_id: galaxy.id,
        redshift: galaxy.redshift,
        log_mstar: galaxy.log_mstar,
        sfr: galaxy.sfr,
        av: galaxy.av,
        tau_diffuse: galaxy.tau_diffuse,
        tau_birth: galaxy.tau_birth,
        sentry_status: galaxy.sentry_status,
        apparent_mag: galaxy.apparent_mag,
        photometry: galaxy.mags || {},
        mags: galaxy.mags,
        fluxes_cgs: fluxes_cgs,
        fluxes_uJy: fluxes_uJy,
        physical_properties: {
          log_mstar: galaxy.log_mstar,
          sfr: galaxy.sfr,
          av: galaxy.av,
          tau_diffuse: galaxy.tau_diffuse,
          tau_birth: galaxy.tau_birth,
        },
        has_discovery_profile: Boolean(galaxy.discovery_profile),
        sed: galaxy.sed || [],
        sed_points_count: galaxy.sed ? galaxy.sed.length : 0,
      };
    },
  },

  specsynth_calculate_cosmology: {
    name: 'specsynth_calculate_cosmology',
    description: 'Calculate luminosity distance, comoving distance, angular diameter distance, lookback time, and cosmic age under FlatLambdaCDM.',
    inputSchema: {
      type: 'object',
      properties: {
        redshift: { type: 'number', description: 'Cosmological redshift z (e.g. 2.5)' },
        h0: { type: 'number', default: 67.74, description: 'Hubble parameter in km/s/Mpc (Planck 2015/2018)' },
        omega_m: { type: 'number', default: 0.3089, description: 'Matter density parameter (Planck 2015/2018)' },
        om0: { type: 'number', default: 0.3089, description: 'Matter density parameter alias' },
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
      if (isNaN(z) || z < 0) {
        return { error: 'Redshift z must be a non-negative number' };
      }
      const H0 = args?.h0 ? Number(args.h0) : 67.74;
      const Om0 = args?.om0 ?? (args?.omega_m ? Number(args.omega_m) : 0.3089);
      return calculateCosmology(z, H0, Om0);
    },
  },

  specsynth_get_3d_galaxy: {
    name: 'specsynth_get_3d_galaxy',
    description: 'Extract simulation-derived 3D particle distribution, kinematics, and structural parameters for a galaxy.',
    inputSchema: {
      type: 'object',
      properties: {
        galaxy_id: { type: 'string', description: 'Galaxy identifier (e.g. TNG-0059 or MyGalaxy)' },
        coordinate_frame: { type: 'string', enum: ['physical_rest', 'comoving_box', 'observer_sky'], default: 'physical_rest' },
        max_particles: { type: 'integer', default: 5000 },
      },
      required: ['galaxy_id'],
    },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    handler: (args) => {
      loadManifests();
      const galaxyId = args?.galaxy_id || 'TNG-0059';
      const coordFrame = args?.coordinate_frame || 'physical_rest';
      const maxParticles = args?.max_particles || 5000;

      // 1. Check sample_models/3d/ for explicit manifests
      const sampleDir = path.resolve(REPO_ROOT, 'sample_models/3d');
      const manifestPath = path.resolve(sampleDir, `${galaxyId}_manifest.json`);
      if (fs.existsSync(manifestPath)) {
        try {
          const data = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
          return {
            galaxy_id: galaxyId,
            geometry_source: data.geometry_source || 'simulation_derived',
            coordinate_frame: coordFrame,
            center_of_mass_kpc: data.center_of_mass_kpc || [0, 0, 0],
            half_mass_radius_kpc: data.half_mass_radius_kpc || 2.85,
            total_stellar_mass_msun: data.total_stellar_mass_msun || 1.78e10,
            simulation_metadata: data.simulation_metadata || {},
            total_particles: data.total_particles || 4000,
            status: 'LOADED_FROM_SNAPSHOT',
          };
        } catch {}
      }

      // 2. Check local catalog entries
      for (const manifest of [tng100Manifest, goodsSManifest]) {
        if (!manifest) continue;
        const g = manifest.galaxies.find((x) => x.id.toLowerCase() === galaxyId.toLowerCase());
        if (g) {
          return {
            galaxy_id: g.id,
            geometry_source: g.galaxy3d ? 'simulation_derived' : 'procedural_illustrative',
            coordinate_frame: coordFrame,
            center_of_mass_kpc: [0, 0, 0],
            half_mass_radius_kpc: g.galaxy3d?.half_mass_radius_kpc || 2.5,
            total_stellar_mass_msun: Math.pow(10, g.log_mstar || 10),
            components: g.galaxy3d?.components || { star: { count: Math.min(maxParticles, 2000), sampled: true } },
            status: 'LOADED_FROM_CATALOG',
          };
        }
      }

      // 3. Fallback
      return {
        galaxy_id: galaxyId,
        geometry_source: 'procedural_illustrative',
        coordinate_frame: coordFrame,
        center_of_mass_kpc: [0, 0, 0],
        half_mass_radius_kpc: 2.5,
        total_stellar_mass_msun: 1e10,
        components: { star: { count: Math.min(maxParticles, 2000), sampled: true } },
        status: 'PROCEDURAL_FALLBACK',
      };
    },
  },

  specsynth_get_evolution_track: {
    name: 'specsynth_get_evolution_track',
    description: 'Retrieve full multi-epoch progenitor evolutionary track, merger milestones, and stellar mass assembly across cosmic time for a galaxy.',
    inputSchema: {
      type: 'object',
      properties: {
        galaxy_id: { type: 'string', description: "Galaxy ID (e.g. 'TNG-DISC-01', 'TNG-ANOM-01', or 'TNG-0059')" },
        dataset: { type: 'string', default: 'tng_100' },
      },
      required: ['galaxy_id'],
    },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    handler: (args) => {
      loadEvolutionTracks();
      const galaxyId = args?.galaxy_id || 'TNG-DISC-01';
      if (evolutionTracksData && evolutionTracksData.tracks) {
        for (const [tid, trk] of Object.entries(evolutionTracksData.tracks)) {
          if (tid.toLowerCase() === galaxyId.toLowerCase() || trk.galaxy_id?.toLowerCase() === galaxyId.toLowerCase()) {
            return trk;
          }
        }
      }
      return {
        error: `Evolutionary track for galaxy '${galaxyId}' not found`,
        available_tracks: evolutionTracksData?.tracks ? Object.keys(evolutionTracksData.tracks) : [],
      };
    },
  },

  specsynth_query_hypotheses: {
    name: 'specsynth_query_hypotheses',
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

  specsynth_check_bridge_status: {
    name: 'specsynth_check_bridge_status',
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

// Legacy Tool Aliases Map
export const LEGACY_TOOL_ALIASES = {
  // Python aliases
  sps_list_filters: 'specsynth_list_filters',
  sps_inspect_galaxy: 'specsynth_inspect_galaxy',
  sps_calculate_cosmology: 'specsynth_calculate_cosmology',
  sps_get_3d_galaxy: 'specsynth_get_3d_galaxy',
  sps_get_evolution_track: 'specsynth_get_evolution_track',
  sps_load_tng_demo: 'specsynth_query_hypotheses',
  sps_check_bridge_status: 'specsynth_check_bridge_status',
  // Node.js legacy aliases
  psi_get_catalog_info: 'specsynth_list_filters',
  psi_inspect_galaxy: 'specsynth_inspect_galaxy',
  psi_calculate_cosmology: 'specsynth_calculate_cosmology',
  psi_query_hypotheses: 'specsynth_query_hypotheses',
  psi_check_bridge_status: 'specsynth_check_bridge_status',
  psi_get_3d_galaxy: 'specsynth_get_3d_galaxy',
  psi_get_evolution_track: 'specsynth_get_evolution_track',
};

// Assemble Unified Tools Registry
export const PSI_MCP_TOOLS = { ...CANONICAL_MCP_TOOLS };

// Auto-register legacy aliases
for (const [legacyName, canonicalName] of Object.entries(LEGACY_TOOL_ALIASES)) {
  if (CANONICAL_MCP_TOOLS[canonicalName] && !PSI_MCP_TOOLS[legacyName]) {
    const canon = CANONICAL_MCP_TOOLS[canonicalName];
    PSI_MCP_TOOLS[legacyName] = {
      name: legacyName,
      description: canon.description,
      inputSchema: canon.inputSchema,
      annotations: canon.annotations,
      handler: canon.handler,
    };
  }
}

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
      const rawName = params?.name;
      const canonicalName = LEGACY_TOOL_ALIASES[rawName] || rawName;
      const tool = this.tools[rawName] || this.tools[canonicalName];
      const args = params?.arguments || {};

      if (!tool) {
        return {
          jsonrpc: '2.0',
          id: msgId,
          error: { code: -32601, message: `Unknown tool: ${rawName}` },
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
