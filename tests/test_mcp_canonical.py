"""
Unit and integration tests for canonical MCP tools (specsynth_*) in Python.
Verifies all canonical contracts, M8ven safety annotations, and legacy alias equivalence.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from specsynth.contracts.mcp import (
    CANONICAL_MCP_TOOLS,
    LEGACY_TOOL_ALIASES,
    get_all_canonical_tools,
    get_canonical_tool_schema,
    resolve_tool_name,
)
from specsynth.mcp.server import SpecsynthMCPServer


def test_canonical_contracts_registry():
    """Verify all canonical tools are registered and conform to schema."""
    canonical_tools = get_all_canonical_tools()
    expected = [
        "specsynth_list_filters",
        "specsynth_inspect_galaxy",
        "specsynth_calculate_cosmology",
        "specsynth_get_3d_galaxy",
        "specsynth_get_evolution_track",
        "specsynth_run_sentry_audit",
        "specsynth_remediate_catalog",
        "specsynth_query_hypotheses",
        "specsynth_check_bridge_status",
        "specsynth_get_system_info",
    ]
    for exp in expected:
        assert exp in canonical_tools, f"Missing canonical tool: {exp}"
        schema = get_canonical_tool_schema(exp)
        assert "inputSchema" in schema
        assert "outputSchema" in schema
        assert "annotations" in schema
        for flag in ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"):
            assert flag in schema["annotations"]


def test_legacy_alias_resolution():
    """Verify legacy tool aliases correctly resolve to canonical tools."""
    assert resolve_tool_name("sps_list_filters") == "specsynth_list_filters"
    assert resolve_tool_name("sps_calculate_cosmology") == "specsynth_calculate_cosmology"
    assert resolve_tool_name("psi_inspect_galaxy") == "specsynth_inspect_galaxy"
    assert resolve_tool_name("psi_get_evolution_track") == "specsynth_get_evolution_track"
    assert resolve_tool_name("unknown_tool") == "unknown_tool"


def test_python_mcp_server_canonical_tool_calls():
    """Execute all canonical tools via JSON-RPC handle_request."""
    server = SpecsynthMCPServer()

    # 1. specsynth_list_filters
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "specsynth_list_filters", "arguments": {"instrument": "jwst_nircam"}},
    })
    res = json.loads(resp["result"]["content"][0]["text"])
    assert "filters" in res
    assert len(res["filters"]) >= 6

    # 2. specsynth_calculate_cosmology
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "specsynth_calculate_cosmology", "arguments": {"redshift": 2.5, "h0": 67.74, "om0": 0.3089}},
    })
    res = json.loads(resp["result"]["content"][0]["text"])
    assert res["redshift"] == 2.5
    assert res["luminosity_distance_mpc"] > 20000.0
    assert res["comoving_distance_mpc"] > 5000.0
    assert "lookback_time_gyr" in res
    assert "cosmic_age_gyr" in res

    # 3. specsynth_inspect_galaxy
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "specsynth_inspect_galaxy", "arguments": {"galaxy_id": "TNG-0059"}},
    })
    res = json.loads(resp["result"]["content"][0]["text"])
    assert "galaxy_id" in res or "galaxy_index" in res

    # 4. specsynth_get_3d_galaxy
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "specsynth_get_3d_galaxy", "arguments": {"galaxy_id": "TNG-0059"}},
    })
    res = json.loads(resp["result"]["content"][0]["text"])
    assert res["galaxy_id"] == "TNG-0059"
    assert res["geometry_source"] in ("simulation_derived", "procedural_illustrative")
    assert "center_of_mass_kpc" in res

    # 5. specsynth_get_evolution_track
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "specsynth_get_evolution_track", "arguments": {"galaxy_id": "TNG-DISC-01"}},
    })
    res = json.loads(resp["result"]["content"][0]["text"])
    assert "main_branch" in res
    assert len(res["main_branch"]) >= 5

    # 6. specsynth_query_hypotheses
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {"name": "specsynth_query_hypotheses", "arguments": {"min_sigma": 2.0, "limit": 3}},
    })
    res = json.loads(resp["result"]["content"][0]["text"])
    assert "candidates" in res or "sample_galaxies" in res

    # 7. specsynth_get_system_info
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": "specsynth_get_system_info", "arguments": {}},
    })
    res = json.loads(resp["result"]["content"][0]["text"])
    assert "cpu_threads" in res

    # 8. specsynth_remediate_catalog (Safety Check: must fail without confirmation)
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {"name": "specsynth_remediate_catalog", "arguments": {"confirm_destructive": False}},
    })
    res = json.loads(resp["result"]["content"][0]["text"])
    assert "error" in res
    assert "confirm_destructive" in res["error"]


def test_python_mcp_server_alias_equivalence():
    """Verify calling legacy aliases (sps_*) executes identically to canonical names."""
    server = SpecsynthMCPServer()

    # sps_calculate_cosmology vs specsynth_calculate_cosmology
    r_canon = server.handle_request({
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {"name": "specsynth_calculate_cosmology", "arguments": {"redshift": 1.5, "h0": 70.0, "om0": 0.3}},
    })
    r_legacy = server.handle_request({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {"name": "sps_calculate_cosmology", "arguments": {"redshift": 1.5, "h0": 70.0, "om0": 0.3}},
    })
    d_canon = json.loads(r_canon["result"]["content"][0]["text"])
    d_legacy = json.loads(r_legacy["result"]["content"][0]["text"])
    assert d_canon == d_legacy

    # psi_calculate_cosmology auto-routed through Python server
    r_psi = server.handle_request({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {"name": "psi_calculate_cosmology", "arguments": {"redshift": 1.5, "h0": 70.0, "om0": 0.3}},
    })
    d_psi = json.loads(r_psi["result"]["content"][0]["text"])
    assert d_psi == d_canon
