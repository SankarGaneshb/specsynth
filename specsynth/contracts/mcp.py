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
}


def get_canonical_tool_schema(tool_name: str) -> dict[str, Any]:
    """Retrieve the JSON Schema definition for a canonical MCP tool."""
    tool = CANONICAL_MCP_TOOLS.get(tool_name)
    if not tool:
        raise KeyError(f"Unknown canonical MCP tool: '{tool_name}'")
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.input_schema,
        "outputSchema": tool.output_schema,
        "annotations": tool.annotations,
        "version": tool.version,
    }
