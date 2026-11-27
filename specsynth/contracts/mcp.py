"""
Canonical Model Context Protocol (MCP) Tool Contracts (v1.0.0).
Defines unified tool schemas, parameter validation, and M8ven safety annotations.
Enforces P0.5 and P4 dual-language interoperability between Python and Node.js.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MCPToolContract:
    """Canonical specification for an MCP tool."""
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    annotations: dict[str, bool]
    version: str = "1.0.0"


# Canonical MCP Tool Definitions
CANONICAL_MCP_TOOLS: dict[str, MCPToolContract] = {
    "specsynth_list_filters": MCPToolContract(
        name="specsynth_list_filters",
        description="List all available cosmological telescope and instrument filter sets (JWST, Roman, Euclid, Rubin, HST).",
        input_schema={
            "type": "object",
            "properties": {
                "instrument": {
                    "type": "string",
                    "description": "Optional filter to a specific instrument (e.g. 'jwst_nircam', 'roman_wfi', 'hst_wfc3').",
                }
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "instruments": {"type": "array", "items": {"type": "string"}},
                "total_filters": {"type": "integer"},
                "filters": {"type": "array"},
            },
            "required": ["instruments", "total_filters", "filters"],
        },
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    ),
    "specsynth_inspect_galaxy": MCPToolContract(
        name="specsynth_inspect_galaxy",
        description="Extract full physical parameters, SFH mass fractions, synthetic photometry, and SED for a galaxy.",
        input_schema={
            "type": "object",
            "properties": {
                "base": {
                    "type": "string",
                    "description": "Path to simulation run directory or catalog root.",
                    "default": "./run",
                },
                "galaxy_id": {
                    "type": "string",
                    "description": "Unique string galaxy identifier or index.",
                },
            },
            "required": ["galaxy_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "galaxy_id": {"type": "string"},
                "physical_properties": {"type": "object"},
                "photometry": {"type": "object"},
                "sed": {"type": "array"},
                "provenance": {"type": "object"},
            },
            "required": ["galaxy_id", "physical_properties"],
        },
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    ),
    "specsynth_calculate_cosmology": MCPToolContract(
        name="specsynth_calculate_cosmology",
        description="Calculate exact cosmological distance measures (luminosity, comoving, angular diameter) under FlatLambdaCDM.",
        input_schema={
            "type": "object",
            "properties": {
                "redshift": {
                    "type": "number",
                    "description": "Cosmological redshift z (>= 0).",
                },
                "h0": {
                    "type": "number",
                    "description": "Hubble constant H0 in km/s/Mpc (default: 67.74, Planck 2015).",
                    "default": 67.74,
                },
                "om0": {
                    "type": "number",
                    "description": "Matter density parameter Omega_m0 (default: 0.3089).",
                    "default": 0.3089,
                },
            },
            "required": ["redshift"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "redshift": {"type": "number"},
                "luminosity_distance_mpc": {"type": "number"},
                "comoving_distance_mpc": {"type": "number"},
                "angular_diameter_distance_mpc": {"type": "number"},
                "distance_modulus": {"type": "number"},
            },
            "required": ["redshift", "luminosity_distance_mpc", "comoving_distance_mpc"],
        },
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    ),
    "specsynth_get_3d_galaxy": MCPToolContract(
        name="specsynth_get_3d_galaxy",
        description="Extract simulation-derived 3D particle distribution, kinematics, and structural parameters for a galaxy.",
        input_schema={
            "type": "object",
            "properties": {
                "galaxy_id": {
                    "type": "string",
                    "description": "Unique galaxy identifier (e.g. 'TNG100-1-Subhalo-424601').",
                },
                "coordinate_frame": {
                    "type": "string",
                    "enum": ["physical_rest", "comoving_box", "observer_sky"],
                    "default": "physical_rest",
                    "description": "Target coordinate frame.",
                },
                "max_particles": {
                    "type": "integer",
                    "default": 5000,
                    "description": "Maximum number of particles per component to sample.",
                },
            },
            "required": ["galaxy_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "galaxy_id": {"type": "string"},
                "geometry_source": {"type": "string"},
                "coordinate_frame": {"type": "string"},
                "center_of_mass_kpc": {"type": "array"},
                "half_mass_radius_kpc": {"type": "number"},
                "total_stellar_mass_msun": {"type": "number"},
                "components": {"type": "object"},
            },
            "required": ["galaxy_id", "geometry_source", "coordinate_frame"],
        },
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    ),
    "specsynth_run_sentry_audit": MCPToolContract(
        name="specsynth_run_sentry_audit",
        description="Execute 4-tier Scientific Sentry quality audit across synthesized catalogs to verify physical invariants.",
        input_schema={
            "type": "object",
            "properties": {
                "base": {
                    "type": "string",
                    "description": "Base directory containing catalogs or run data.",
                    "default": "./run",
                },
                "sample_size": {
                    "type": "integer",
                    "description": "Number of galaxies to audit.",
                    "default": 1000,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "tiers_passed": {"type": "integer"},
                "total_tiers": {"type": "integer"},
                "anomalies_detected": {"type": "integer"},
                "summary": {"type": "string"},
            },
            "required": ["status", "tiers_passed", "total_tiers"],
        },
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    ),
    "specsynth_get_evolution_track": MCPToolContract(
        name="specsynth_get_evolution_track",
        description="Retrieve full multi-epoch progenitor evolutionary track, merger milestones, and stellar mass assembly across cosmic time for a galaxy.",
        input_schema={
            "type": "object",
            "properties": {
                "galaxy_id": {
                    "type": "string",
                    "description": "Unique galaxy identifier (e.g. 'TNG-DISC-01', 'TNG-ANOM-01', or subhalo ID).",
                },
                "dataset": {
                    "type": "string",
                    "description": "Target simulation or mock dataset.",
                    "default": "tng_100",
                },
                "data_mode": {
                    "type": "string",
                    "description": "Target data mode: 'simulation_derived' (default for simulations) or 'illustrative_demo'.",
                    "enum": ["simulation_derived", "illustrative_demo"],
                },
            },
            "required": ["galaxy_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "galaxy_id": {"type": "string"},
                "version": {"type": "string"},
                "main_branch": {"type": "array"},
                "mergers": {"type": "array"},
                "mass_assembly": {"type": "object"},
                "status": {"type": "string"},
            },
            "required": ["galaxy_id", "main_branch"],
        },
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    ),
    "specsynth_remediate_catalog": MCPToolContract(
        name="specsynth_remediate_catalog",
        description="Trigger the autonomous SentryAgent to isolate anomaly root causes, purge corruptions, and produce a pristine clean catalog.",
        input_schema={
            "type": "object",
            "properties": {
                "base": {
                    "type": "string",
                    "description": "Base storage directory.",
                    "default": "./run",
                },
                "output_csv": {
                    "type": "string",
                    "description": "Output path for the clean catalog CSV.",
                    "default": "clean_catalog.csv",
                },
                "confirm_destructive": {
                    "type": "boolean",
                    "description": "Explicit confirmation flag required to execute destructive remediation.",
                    "default": False,
                },
            },
            "required": ["confirm_destructive"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "clean_catalog_path": {"type": "string"},
                "anomalies_purged": {"type": "integer"},
                "galaxies_retained": {"type": "integer"},
            },
            "required": ["status"],
        },
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    ),
    "specsynth_query_hypotheses": MCPToolContract(
        name="specsynth_query_hypotheses",
        description="Retrieve rare frontier discovery profiles, anomaly hypotheses, and academic literature citations from deep mock catalogs.",
        input_schema={
            "type": "object",
            "properties": {
                "min_sigma": {
                    "type": "number",
                    "description": "Minimum statistical rarity sigma.",
                    "default": 2.0,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum candidate profiles to return.",
                    "default": 5,
                },
                "dataset": {
                    "type": "string",
                    "description": "Target mock catalog dataset (e.g. 'goods_s_mock').",
                    "default": "goods_s_mock",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "total_discovered": {"type": "integer"},
                "candidates": {"type": "array"},
            },
            "required": ["total_discovered", "candidates"],
        },
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    ),
    "specsynth_check_bridge_status": MCPToolContract(
        name="specsynth_check_bridge_status",
        description="Verify connectivity to the local SpecSynth HTTP computation bridge (localhost:8000).",
        input_schema={
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "HTTP bridge host URL (restricted to local loopback).",
                    "default": "http://127.0.0.1:8000",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "details": {"type": "object"},
            },
            "required": ["status"],
        },
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    ),
    "specsynth_get_system_info": MCPToolContract(
        name="specsynth_get_system_info",
        description="Get current host hardware info, CPU threads, RAM, and GPU/BLAS acceleration capabilities.",
        input_schema={
            "type": "object",
            "properties": {},
        },
        output_schema={
            "type": "object",
            "properties": {
                "cpu_threads": {"type": "integer"},
                "ram_total_gb": {"type": "number"},
                "acceleration": {"type": "string"},
            },
        },
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    ),
}

# Legacy Namespace Aliasing (sps_* and psi_* -> specsynth_*)
LEGACY_TOOL_ALIASES: dict[str, str] = {
    # Python legacy aliases
    "sps_list_filters": "specsynth_list_filters",
    "sps_inspect_galaxy": "specsynth_inspect_galaxy",
    "sps_run_sentry_audit": "specsynth_run_sentry_audit",
    "sps_remediate_catalog": "specsynth_remediate_catalog",
    "sps_load_tng_demo": "specsynth_query_hypotheses",
    "sps_get_system_info": "specsynth_get_system_info",
    "sps_calculate_cosmology": "specsynth_calculate_cosmology",
    "sps_get_3d_galaxy": "specsynth_get_3d_galaxy",
    "sps_get_evolution_track": "specsynth_get_evolution_track",
    # Node.js legacy aliases
    "psi_get_catalog_info": "specsynth_list_filters",
    "psi_inspect_galaxy": "specsynth_inspect_galaxy",
    "psi_calculate_cosmology": "specsynth_calculate_cosmology",
    "psi_query_hypotheses": "specsynth_query_hypotheses",
    "psi_check_bridge_status": "specsynth_check_bridge_status",
    "psi_get_3d_galaxy": "specsynth_get_3d_galaxy",
    "psi_get_evolution_track": "specsynth_get_evolution_track",
}


def resolve_tool_name(tool_name: str) -> str:
    """Resolve a tool name to its canonical specsynth_* form."""
    return LEGACY_TOOL_ALIASES.get(tool_name, tool_name)


def get_all_canonical_tools() -> list[str]:
    """Return all canonical MCP tool names."""
    return list(CANONICAL_MCP_TOOLS.keys())


def get_canonical_tool_schema(tool_name: str) -> dict[str, Any]:
    """Retrieve the JSON Schema definition for a canonical MCP tool (or alias)."""
    canonical_name = resolve_tool_name(tool_name)
    tool = CANONICAL_MCP_TOOLS.get(canonical_name)
    if not tool:
        raise KeyError(f"Unknown canonical MCP tool: '{tool_name}' (canonical: '{canonical_name}')")
    return {
        "name": tool_name,  # Keep the requested name for compatibility
        "canonical_name": tool.name,
        "description": tool.description,
        "inputSchema": tool.input_schema,
        "outputSchema": tool.output_schema,
        "annotations": tool.annotations,
        "version": tool.version,
    }
