"""
Cross-language parity tests between Python and Node.js MCP servers.
Validates exact numerical, schema, and behavioral parity across both runtimes.
"""

from __future__ import annotations

import json
import subprocess
import pytest

from specsynth.mcp.server import SpecsynthMCPServer


def run_node_mcp_call(tool_name: str, arguments: dict) -> dict:
    """Invoke tool via Node.js MCP server using a standalone script."""
    node_script = f"""
    import('./perandam-psi/mcp_server.mjs').then(async (m) => {{
        const server = new m.PerandamMCPServer();
        const resp = await server.handleRequest({{
            jsonrpc: "2.0",
            id: 1,
            method: "tools/call",
            params: {{
                name: {json.dumps(tool_name)},
                arguments: {json.dumps(arguments)}
            }}
        }});
        if (resp.error) {{
            console.log(JSON.stringify({{ error: resp.error.message }}));
        }} else {{
            console.log(resp.result.content[0].text);
        }}
    }}).catch(err => {{
        console.error(err);
        process.exit(1);
    }});
    """
    res = subprocess.run(
        ["node", "--input-type=module", "-e", node_script],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(res.stdout.strip())


def test_cosmology_cross_language_parity():
    """Verify numerical parity for FLRW cosmology across Python and Node.js implementations."""
    py_server = SpecsynthMCPServer()

    test_redshifts = [0.1, 0.5, 1.0, 2.0, 4.0, 8.0]
    h0 = 67.74
    om0 = 0.3089

    for z in test_redshifts:
        # Python
        py_resp = py_server.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "specsynth_calculate_cosmology", "arguments": {"redshift": z, "h0": h0, "om0": om0}},
        })
        py_data = json.loads(py_resp["result"]["content"][0]["text"])

        # Node.js
        node_data = run_node_mcp_call("specsynth_calculate_cosmology", {"redshift": z, "h0": h0, "om0": om0})

        # Compare Comoving Distance (< 0.1% tolerance)
        rel_diff_dc = abs(py_data["comoving_distance_mpc"] - node_data["comoving_distance_mpc"]) / max(1.0, py_data["comoving_distance_mpc"])
        assert rel_diff_dc < 1e-3, f"Comoving distance mismatch at z={z}: py={py_data['comoving_distance_mpc']}, node={node_data['comoving_distance_mpc']}"

        # Compare Luminosity Distance (< 0.1% tolerance)
        rel_diff_dl = abs(py_data["luminosity_distance_mpc"] - node_data["luminosity_distance_mpc"]) / max(1.0, py_data["luminosity_distance_mpc"])
        assert rel_diff_dl < 1e-3, f"Luminosity distance mismatch at z={z}: py={py_data['luminosity_distance_mpc']}, node={node_data['luminosity_distance_mpc']}"

        # Compare Lookback Time (< 0.05 Gyr)
        diff_t_lb = abs(py_data["lookback_time_gyr"] - node_data["lookback_time_gyr"])
        assert diff_t_lb < 0.05, f"Lookback time mismatch at z={z}: py={py_data['lookback_time_gyr']}, node={node_data['lookback_time_gyr']}"


def test_evolution_track_cross_language_parity():
    """Verify progenitor evolutionary track parity across Python and Node.js MCP servers."""
    py_server = SpecsynthMCPServer()

    galaxy_id = "TNG-DISC-01"

    py_resp = py_server.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "specsynth_get_evolution_track", "arguments": {"galaxy_id": galaxy_id}},
    })
    py_data = json.loads(py_resp["result"]["content"][0]["text"])
    node_data = run_node_mcp_call("specsynth_get_evolution_track", {"galaxy_id": galaxy_id})

    assert "main_branch" in py_data
    assert "main_branch" in node_data
    assert len(py_data["main_branch"]) == len(node_data["main_branch"])
    assert len(py_data["main_branch"]) >= 5


def test_legacy_aliases_across_languages():
    """Verify legacy aliases (sps_* vs psi_*) are supported across both engines."""
    py_server = SpecsynthMCPServer()

    # Calling psi_* on Python server works
    py_resp = py_server.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "psi_calculate_cosmology", "arguments": {"redshift": 1.0}},
    })
    assert "result" in py_resp

    # Calling sps_* on Node server works
    node_data = run_node_mcp_call("sps_calculate_cosmology", {"redshift": 1.0})
    assert "luminosity_distance_mpc" in node_data
