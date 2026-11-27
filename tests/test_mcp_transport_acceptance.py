"""
Automated Test Suite for Out-of-Process MCP Transport & Acceptance (Issue #30 / P4).
====================================================================================
Validates Python and Node.js MCP servers strictly over out-of-process stdio pipes:
1. Initialize handshake, protocol negotiation, and initialized notifications.
2. Tool enumeration (tools/list) and schema verification.
3. End-to-end scientific workflow over stdio with real IllustrisTNG data.
4. Semantic, schema, unit, and numerical parity across runtimes.
5. Negative protocol tests: malformed JSON-RPC (-32700), unknown tools (-32601), bad methods.
6. Security checks for loopback binding and transport integrity.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

# Ensure scripts directory is on sys.path
scripts_dir = Path(__file__).parents[1] / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from mcp_client_transport import (
    MCPStdioClient,
    MCPTransportError,
    create_node_mcp_client,
    create_python_mcp_client,
)

pytestmark = pytest.mark.astrophysics


# -----------------------------------------------------------------------------
# 1. Transport Lifecycle & Handshake Tests
# -----------------------------------------------------------------------------

def test_python_mcp_server_transport_lifecycle():
    """Verify Python MCP server initializes and negotiates protocol over stdio."""
    with create_python_mcp_client() as client:
        init_res = client.initialize(client_name="pytest-python-client", client_version="1.0.0")

        assert "protocolVersion" in init_res
        assert "serverInfo" in init_res
        assert init_res["serverInfo"]["name"] == "specsynth-mcp"
        assert "tools" in init_res["capabilities"]

        # Tools enumeration
        tools = client.list_tools()
        assert len(tools) >= 10
        tool_names = [t["name"] for t in tools]
        assert "specsynth_calculate_cosmology" in tool_names
        assert "specsynth_list_filters" in tool_names


def test_node_mcp_server_transport_lifecycle():
    """Verify Node.js MCP server initializes and negotiates protocol over stdio."""
    with create_node_mcp_client() as client:
        init_res = client.initialize(client_name="pytest-node-client", client_version="1.0.0")

        assert "protocolVersion" in init_res
        assert "serverInfo" in init_res
        assert init_res["serverInfo"]["name"] == "perandam-psi-mcp"
        assert "tools" in init_res["capabilities"]

        # Tools enumeration
        tools = client.list_tools()
        assert len(tools) >= 10
        tool_names = [t["name"] for t in tools]
        assert "specsynth_calculate_cosmology" in tool_names
        assert "specsynth_list_filters" in tool_names


# -----------------------------------------------------------------------------
# 2. End-to-End Real Scientific Workflow over stdio Transport
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("client_factory", [create_python_mcp_client, create_node_mcp_client])
def test_end_to_end_scientific_workflow_over_transport(client_factory):
    """
    Execute complete end-to-end scientific investigation over the stdio transport:
    1. specsynth_list_filters -> discover NIRCam filters
    2. specsynth_inspect_galaxy -> inspect subhalo 009873
    3. specsynth_calculate_cosmology -> compute FLRW distances at z=1.5
    4. specsynth_get_3d_galaxy -> retrieve simulation particles
    5. specsynth_get_evolution_track -> inspect merger tree timeline
    """
    with client_factory() as client:
        client.initialize()

        # Step 1: List Filters
        flt_data = client.call_tool("specsynth_list_filters", {"instrument": "jwst_nircam"})
        assert "filters" in flt_data
        filters = flt_data["filters"]
        filter_names = [f["name"] if isinstance(f, dict) else f for f in filters]
        assert len(filter_names) >= 6
        assert "jwst_f150w" in filter_names

        # Step 2: Inspect Real Subhalo
        gal_data = client.call_tool("specsynth_inspect_galaxy", {"galaxy_id": "tng100_subhalo_009873"})
        assert "galaxy_id" in gal_data
        assert gal_data["galaxy_id"] == "tng100_subhalo_009873"
        assert "physical_properties" in gal_data or "log_mstar" in gal_data or "stellar_mass_msun" in gal_data
        assert "sed" in gal_data or "rest_frame_sed" in gal_data

        # Step 3: Cosmological Distances
        cosmo_data = client.call_tool("specsynth_calculate_cosmology", {"redshift": 1.5, "h0": 67.74, "om0": 0.3089})
        assert cosmo_data["redshift"] == 1.5
        assert "luminosity_distance_mpc" in cosmo_data
        assert "comoving_distance_mpc" in cosmo_data
        assert cosmo_data["luminosity_distance_mpc"] > cosmo_data["comoving_distance_mpc"]

        # Step 4: 3D Galaxy Particle Geometry
        g3d_data = client.call_tool("specsynth_get_3d_galaxy", {"galaxy_id": "tng100_subhalo_009873"})
        assert "galaxy_id" in g3d_data
        assert "total_particles" in g3d_data or "components" in g3d_data or "particle_count" in g3d_data
        assert g3d_data.get("geometry_source") in ("simulation_derived", "procedural_illustrative")

        # Step 5: Cosmic Evolution Track
        evo_data = client.call_tool("specsynth_get_evolution_track", {"galaxy_id": "tng100_subhalo_424601"})
        assert "galaxy_id" in evo_data
        assert evo_data["galaxy_id"] == "tng100_subhalo_424601"
        assert evo_data.get("data_mode") == "simulation_derived"
        assert "main_branch" in evo_data or "timeline" in evo_data or "epochs" in evo_data


# -----------------------------------------------------------------------------
# 3. Cross-Language Semantic, Schema, and Unit Parity Tests
# -----------------------------------------------------------------------------

def test_cross_language_cosmology_parity_over_transport():
    """Verify numerical and unit parity for FLRW cosmology between Python and Node servers."""
    test_redshifts = [0.2, 0.5, 1.0, 1.5, 2.0, 3.5, 6.0]
    h0 = 67.74
    om0 = 0.3089

    with create_python_mcp_client() as py_client, create_node_mcp_client() as node_client:
        py_client.initialize()
        node_client.initialize()

        for z in test_redshifts:
            py_res = py_client.call_tool("specsynth_calculate_cosmology", {"redshift": z, "h0": h0, "om0": om0})
            node_res = node_client.call_tool("specsynth_calculate_cosmology", {"redshift": z, "h0": h0, "om0": om0})

            # Check schema keys
            for key in ("redshift", "comoving_distance_mpc", "luminosity_distance_mpc", "lookback_time_gyr", "cosmic_age_gyr"):
                assert key in py_res, f"Missing key '{key}' in Python response"
                assert key in node_res, f"Missing key '{key}' in Node.js response"

            # Check Comoving Distance (< 0.1% relative tolerance)
            dc_py = py_res["comoving_distance_mpc"]
            dc_node = node_res["comoving_distance_mpc"]
            rel_diff_dc = abs(dc_py - dc_node) / max(1.0, dc_py)
            assert rel_diff_dc < 1e-3, f"Comoving distance divergence at z={z}: py={dc_py}, node={dc_node}"

            # Check Luminosity Distance (< 0.1% relative tolerance)
            dl_py = py_res["luminosity_distance_mpc"]
            dl_node = node_res["luminosity_distance_mpc"]
            rel_diff_dl = abs(dl_py - dl_node) / max(1.0, dl_py)
            assert rel_diff_dl < 1e-3, f"Luminosity distance divergence at z={z}: py={dl_py}, node={dl_node}"

            # Check Lookback Time (< 0.05 Gyr absolute tolerance)
            diff_t_lb = abs(py_res["lookback_time_gyr"] - node_res["lookback_time_gyr"])
            assert diff_t_lb < 0.05, f"Lookback time divergence at z={z}: py={py_res['lookback_time_gyr']}, node={node_res['lookback_time_gyr']}"


def test_cross_language_filter_list_parity_over_transport():
    """Verify identical filter catalog responses across Python and Node.js servers for JWST NIRCam."""
    with create_python_mcp_client() as py_client, create_node_mcp_client() as node_client:
        py_client.initialize()
        node_client.initialize()

        py_res = py_client.call_tool("specsynth_list_filters", {"instrument": "jwst_nircam"})
        node_res = node_client.call_tool("specsynth_list_filters", {"instrument": "jwst_nircam"})

        py_filters = {f["name"] if isinstance(f, dict) else f for f in py_res.get("filters", [])}
        node_filters = {f["name"] if isinstance(f, dict) else f for f in node_res.get("filters", [])}

        expected = {"jwst_f090w", "jwst_f115w", "jwst_f150w", "jwst_f200w", "jwst_f277w", "jwst_f356w", "jwst_f444w"}
        assert py_filters == expected
        assert node_filters == expected


# -----------------------------------------------------------------------------
# 4. Negative Protocol, Error Handling, and Robustness Tests
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("client_factory", [create_python_mcp_client, create_node_mcp_client])
def test_negative_malformed_json_rpc(client_factory):
    """
    Verify server responds with standard JSON-RPC -32700 Parse error
    when fed invalid JSON over stdio, and does not crash.
    """
    with client_factory() as client:
        client.start()

        # Send malformed JSON string
        err_resp = client.send_raw("{ this is definitely not valid json !!! }")

        assert "error" in err_resp
        assert err_resp["error"]["code"] == -32700
        assert "Parse error" in err_resp["error"]["message"]

        # Server must still be alive and accept valid requests after error
        valid_res = client.initialize()
        assert "serverInfo" in valid_res


@pytest.mark.parametrize("client_factory", [create_python_mcp_client, create_node_mcp_client])
def test_negative_unknown_tool_call(client_factory):
    """
    Verify calling an unknown tool returns standard error code -32601 (Method/Tool not found).
    """
    with client_factory() as client:
        client.initialize()

        with pytest.raises(MCPTransportError) as exc_info:
            client.call_tool("unknown_fictional_astronomy_tool", {})

        assert exc_info.value.code == -32601
        assert "Unknown tool" in exc_info.value.message or "not found" in exc_info.value.message


@pytest.mark.parametrize("client_factory", [create_python_mcp_client, create_node_mcp_client])
def test_negative_unknown_json_rpc_method(client_factory):
    """
    Verify calling an unknown JSON-RPC method returns code -32601 (Method not found).
    """
    with client_factory() as client:
        client.start()

        with pytest.raises(MCPTransportError) as exc_info:
            client.send_request("unsupported/arbitrary_method", {})

        assert exc_info.value.code == -32601
        assert "not found" in exc_info.value.message.lower()


# -----------------------------------------------------------------------------
# 5. Security & Isolation Tests
# -----------------------------------------------------------------------------

def test_mcp_bridge_security_loopback_only():
    """Verify HTTP bridge enforces loopback interface (127.0.0.1) and rejects non-loopback bindings."""
    from specsynth.mcp.bridge import is_loopback, run_bridge_server

    assert is_loopback("127.0.0.1")
    assert is_loopback("localhost")
    assert is_loopback("::1")
    assert not is_loopback("0.0.0.0")
    assert not is_loopback("192.168.1.100")

    # Attempting to run server on 0.0.0.0 without allow_remote must raise ValueError
    with pytest.raises(ValueError, match="Refusing to bind HTTP bridge to non-loopback"):
        run_bridge_server(host="0.0.0.0", allow_remote=False)
