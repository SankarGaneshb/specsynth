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


def normalize_mcp_dict(d: dict) -> dict:
    """Normalize payload by stripping dynamic timestamps and latencies for strict cross-runtime parity."""
    out = {}
    for k, v in d.items():
        if k in ("timestamp_utc", "latency_ms", "timestamp", "executor", "engine"):
            continue
        if isinstance(v, dict):
            out[k] = normalize_mcp_dict(v)
        elif isinstance(v, list):
            out[k] = [normalize_mcp_dict(item) if isinstance(item, dict) else item for item in v]
        elif isinstance(v, float):
            out[k] = round(v, 3)
        else:
            out[k] = v
    return out


def test_evolution_track_cross_language_parity():
    """Verify progenitor evolutionary track parity across Python and Node.js MCP servers."""
    py_server = SpecsynthMCPServer()

    # 1. Bundled procedural track fails closed to analytical_mock on both runtimes
    galaxy_id = "TNG-DISC-01"
    py_resp = py_server.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "specsynth_get_evolution_track", "arguments": {"galaxy_id": galaxy_id}},
    })
    py_data = json.loads(py_resp["result"]["content"][0]["text"])
    node_data = run_node_mcp_call("specsynth_get_evolution_track", {"galaxy_id": galaxy_id})

    assert "main_branch" in py_data and "main_branch" in node_data
    assert len(py_data["main_branch"]) == len(node_data["main_branch"])
    assert py_data.get("data_mode") == node_data.get("data_mode") == "analytical_mock"
    assert py_data["source_provenance"]["verification_status"] == node_data["source_provenance"]["verification_status"] == "declared"

    # 2. Authentic SubLink merger tree is verified simulation_derived on both runtimes
    py_sub_resp = py_server.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "specsynth_get_evolution_track", "arguments": {"galaxy_id": "424601"}},
    })
    py_sub = json.loads(py_sub_resp["result"]["content"][0]["text"])
    node_sub = run_node_mcp_call("specsynth_get_evolution_track", {"galaxy_id": "424601"})

    assert py_sub.get("data_mode") == node_sub.get("data_mode") == "simulation_derived"
    assert py_sub["source_provenance"]["verification_status"] == node_sub["source_provenance"]["verification_status"] == "verified"
    assert py_sub["source_provenance"]["subhalo_id"] == node_sub["source_provenance"]["subhalo_id"] == 424601
    assert py_sub["source_provenance"]["simulation"] == node_sub["source_provenance"]["simulation"] == "IllustrisTNG-100-1"


def test_data_mode_and_provenance_cross_language_parity():
    """Verify data_mode and structured provenance parity for inspect and 3D galaxy tools across 4 regimes."""
    py_server = SpecsynthMCPServer()

    # Regime 1: Calibrated reference mock catalog galaxy
    py_resp = py_server.handle_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "specsynth_inspect_galaxy", "arguments": {"galaxy_id": "0"}},
    })
    py_inspect = json.loads(py_resp["result"]["content"][0]["text"])
    node_inspect = run_node_mcp_call("specsynth_inspect_galaxy", {"galaxy_id": "0"})

    assert py_inspect["data_mode"] == node_inspect["data_mode"] == "cached_reference"
    assert py_inspect["source_provenance"]["verification_status"] == node_inspect["source_provenance"]["verification_status"] == "declared"
    assert py_inspect["source_provenance"]["verified_authentic"] == node_inspect["source_provenance"]["verified_authentic"] is False

    # Regime 2: Authentic simulation cutout inspection (tng_424601)
    py_tng_resp = py_server.handle_request({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "specsynth_inspect_galaxy", "arguments": {"galaxy_id": "tng_424601"}},
    })
    py_tng = json.loads(py_tng_resp["result"]["content"][0]["text"])
    node_tng = run_node_mcp_call("specsynth_inspect_galaxy", {"galaxy_id": "tng_424601"})

    assert py_tng["data_mode"] == node_tng["data_mode"] == "simulation_derived"
    assert py_tng["source_provenance"]["verification_status"] == node_tng["source_provenance"]["verification_status"] == "verified"
    assert py_tng["source_provenance"]["verified_authentic"] == node_tng["source_provenance"]["verified_authentic"] is True
    assert py_tng["source_provenance"]["checksum_sha256"] == node_tng["source_provenance"]["checksum_sha256"] == "8f5853a5fb4b5af9eaf2e67e39e9ce8c7bb04018d61c37b58d609f4731860c31"

    # Regime 3: Authentic 3D galaxy cutout (tng100_subhalo_real)
    py_3d_resp = py_server.handle_request({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {"name": "specsynth_get_3d_galaxy", "arguments": {"galaxy_id": "tng100_subhalo_real"}},
    })
    py_3d = json.loads(py_3d_resp["result"]["content"][0]["text"])
    node_3d = run_node_mcp_call("specsynth_get_3d_galaxy", {"galaxy_id": "tng100_subhalo_real"})

    assert py_3d["data_mode"] == node_3d["data_mode"] == "simulation_derived"
    assert py_3d["source_provenance"]["verification_status"] == node_3d["source_provenance"]["verification_status"] == "verified"
    assert py_3d["source_provenance"]["verified_authentic"] == node_3d["source_provenance"]["verified_authentic"] is True

    # Regime 4: Procedural 3D model (goods_s_508_0)
    py_proc_resp = py_server.handle_request({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": "specsynth_get_3d_galaxy", "arguments": {"galaxy_id": "goods_s_508_0"}},
    })
    py_proc = json.loads(py_proc_resp["result"]["content"][0]["text"])
    node_proc = run_node_mcp_call("specsynth_get_3d_galaxy", {"galaxy_id": "goods_s_508_0"})

    assert py_proc["data_mode"] == node_proc["data_mode"] == "analytical_mock"
    assert py_proc["source_provenance"]["verification_status"] == node_proc["source_provenance"]["verification_status"] == "declared"
    assert py_proc["source_provenance"]["verified_authentic"] == node_proc["source_provenance"]["verified_authentic"] is False



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
