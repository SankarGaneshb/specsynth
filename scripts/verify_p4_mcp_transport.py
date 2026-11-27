#!/usr/bin/env python3
"""
scripts/verify_p4_mcp_transport.py
Acceptance verification harness for Milestone P4: Independent MCP Transport and Client End-to-End Acceptance.

Audits all 7 acceptance criteria across Python (specsynth.mcp.server) and Node.js (perandam-psi/mcp_server.mjs)
using out-of-process stdio client transport, and outputs benchmark_mcp_transport_acceptance.json.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.mcp_client_transport import (
    MCPStdioClient,
    create_python_mcp_client,
    create_node_mcp_client,
    MCPTransportError,
)


def verify_criterion_1_lifecycle() -> dict[str, Any]:
    """Criterion 1: Lifecycle (spawn, initialize, notifications/initialized, shutdown)."""
    start = time.perf_counter()
    details = {}

    for name, factory in [("python", create_python_mcp_client), ("node", create_node_mcp_client)]:
        with factory() as client:
            init_res = client.initialize()
            assert "serverInfo" in init_res, f"{name} serverInfo missing in initialize"
            assert client.proc is not None
            details[f"{name}_server_name"] = init_res["serverInfo"].get("name")
            details[f"{name}_server_version"] = init_res["serverInfo"].get("version")
        # Ensure clean exit
        assert client.proc is None, f"{name} process was not cleaned up"
        details[f"{name}_shutdown_clean"] = True

    elapsed = time.perf_counter() - start
    return {
        "id": "CRITERION_1_LIFECYCLE",
        "name": "Out-of-Process stdio Transport Lifecycle",
        "passed": True,
        "elapsed_sec": round(elapsed, 4),
        "details": details,
    }


def verify_criterion_2_tool_discovery() -> dict[str, Any]:
    """Criterion 2: Tool Discovery via tools/list."""
    start = time.perf_counter()
    canonical_tools = {
        "specsynth_list_filters",
        "specsynth_inspect_galaxy",
        "specsynth_calculate_cosmology",
        "specsynth_get_3d_galaxy",
        "specsynth_get_evolution_track",
    }
    details = {}

    for name, factory in [("python", create_python_mcp_client), ("node", create_node_mcp_client)]:
        with factory() as client:
            client.initialize()
            tools = client.list_tools()
            tool_names = {t["name"] for t in tools}
            missing = canonical_tools - tool_names
            assert not missing, f"{name} MCP server missing canonical tools: {missing}"
            details[f"{name}_tool_count"] = len(tools)
            details[f"{name}_canonical_tools_present"] = sorted(list(canonical_tools & tool_names))

    elapsed = time.perf_counter() - start
    return {
        "id": "CRITERION_2_TOOL_DISCOVERY",
        "name": "Tool Discovery via tools/list",
        "passed": True,
        "elapsed_sec": round(elapsed, 4),
        "details": details,
    }


def verify_criterion_3_workflow_execution() -> dict[str, Any]:
    """Criterion 3: Real-Data Scientific Workflow Execution Over Transport."""
    start = time.perf_counter()
    details = {}

    for name, factory in [("python", create_python_mcp_client), ("node", create_node_mcp_client)]:
        with factory() as client:
            client.initialize()

            # Step 1: List Filters
            flt_data = client.call_tool("specsynth_list_filters", {"instrument": "jwst_nircam"})
            assert "filters" in flt_data
            filter_names = [f["name"] if isinstance(f, dict) else f for f in flt_data["filters"]]
            assert "jwst_f150w" in filter_names

            # Step 2: Inspect Galaxy
            gal_data = client.call_tool("specsynth_inspect_galaxy", {"galaxy_id": "tng100_subhalo_009873"})
            assert gal_data.get("galaxy_id") == "tng100_subhalo_009873"

            # Step 3: Cosmology Calculation
            cosmo = client.call_tool("specsynth_calculate_cosmology", {"redshift": 1.5, "h0": 67.74, "om0": 0.3089})
            assert cosmo.get("luminosity_distance_mpc", 0) > cosmo.get("comoving_distance_mpc", 0)

            # Step 4: 3D Galaxy Particle Geometry
            g3d = client.call_tool("specsynth_get_3d_galaxy", {"galaxy_id": "tng100_subhalo_009873"})
            assert "galaxy_id" in g3d

            # Step 5: Cosmic Evolution Track
            evo = client.call_tool("specsynth_get_evolution_track", {"galaxy_id": "tng100_subhalo_424601"})
            assert evo.get("galaxy_id") == "tng100_subhalo_424601"
            assert evo.get("data_mode") == "simulation_derived"

            details[f"{name}_workflow_steps_executed"] = 5
            details[f"{name}_galaxy_inspected"] = "tng100_subhalo_009873"
            details[f"{name}_dl_z1_5_mpc"] = cosmo.get("luminosity_distance_mpc")

    elapsed = time.perf_counter() - start
    return {
        "id": "CRITERION_3_WORKFLOW_EXECUTION",
        "name": "End-to-End Scientific Workflow Execution",
        "passed": True,
        "elapsed_sec": round(elapsed, 4),
        "details": details,
    }


def verify_criterion_4_cross_language_parity() -> dict[str, Any]:
    """Criterion 4: Cross-Language Semantic, Schema, and Unit Parity."""
    start = time.perf_counter()
    details = {}

    with create_python_mcp_client() as py_client, create_node_mcp_client() as node_client:
        py_client.initialize()
        node_client.initialize()

        # Cosmology Parity across test redshifts
        test_z = [0.5, 1.5, 3.0]
        cosmo_diffs = []
        for z in test_z:
            py_c = py_client.call_tool("specsynth_calculate_cosmology", {"redshift": z, "h0": 67.74, "om0": 0.3089})
            node_c = node_client.call_tool("specsynth_calculate_cosmology", {"redshift": z, "h0": 67.74, "om0": 0.3089})

            dl_py = py_c["luminosity_distance_mpc"]
            dl_node = node_c["luminosity_distance_mpc"]
            rel_diff = abs(dl_py - dl_node) / dl_py
            assert rel_diff < 1e-3, f"Cosmology divergence at z={z}: py={dl_py}, node={dl_node}"
            cosmo_diffs.append({"z": z, "py_dl": dl_py, "node_dl": dl_node, "rel_diff_pct": round(rel_diff * 100, 5)})

        details["cosmology_parity"] = cosmo_diffs
        details["max_cosmology_divergence_pct"] = max(d["rel_diff_pct"] for d in cosmo_diffs)

        # Filter List Parity
        py_f = py_client.call_tool("specsynth_list_filters", {"instrument": "jwst_nircam"})
        node_f = node_client.call_tool("specsynth_list_filters", {"instrument": "jwst_nircam"})
        py_filters = {f["name"] if isinstance(f, dict) else f for f in py_f.get("filters", [])}
        node_filters = {f["name"] if isinstance(f, dict) else f for f in node_f.get("filters", [])}
        assert py_filters == node_filters, f"Filter parity failed: {py_filters} != {node_filters}"
        details["filter_set_parity_jwst_nircam"] = sorted(list(py_filters))

    elapsed = time.perf_counter() - start
    return {
        "id": "CRITERION_4_CROSS_LANGUAGE_PARITY",
        "name": "Cross-Language Schema & Unit Parity",
        "passed": True,
        "elapsed_sec": round(elapsed, 4),
        "details": details,
    }


def verify_criterion_5_robustness_negative() -> dict[str, Any]:
    """Criterion 5: Protocol Robustness, Malformed JSON, Unknown Tools & Methods."""
    start = time.perf_counter()
    details = {}

    for name, factory in [("python", create_python_mcp_client), ("node", create_node_mcp_client)]:
        with factory() as client:
            client.start()

            # Malformed JSON-RPC (-32700)
            raw_bad = client.send_raw("{ this is invalid json }")
            assert "error" in raw_bad
            assert raw_bad["error"]["code"] == -32700
            details[f"{name}_malformed_code"] = raw_bad["error"]["code"]

            # Unknown Method (-32601)
            raw_method = client.send_raw(json.dumps({"jsonrpc": "2.0", "id": 99, "method": "unknown/method", "params": {}}))
            assert "error" in raw_method
            assert raw_method["error"]["code"] == -32601
            details[f"{name}_unknown_method_code"] = raw_method["error"]["code"]

            # Unknown Tool Call
            client.initialize()
            raw_tool = client.send_raw(json.dumps({"jsonrpc": "2.0", "id": 100, "method": "tools/call", "params": {"name": "nonexistent_tool_xyz", "arguments": {}}}))
            has_error = "error" in raw_tool or (isinstance(raw_tool.get("result"), dict) and "isError" in raw_tool["result"])
            assert has_error
            details[f"{name}_unknown_tool_handled"] = True

    elapsed = time.perf_counter() - start
    return {
        "id": "CRITERION_5_ROBUSTNESS_NEGATIVE",
        "name": "Protocol Robustness & Error Handling",
        "passed": True,
        "elapsed_sec": round(elapsed, 4),
        "details": details,
    }


def verify_criterion_6_inspector_fixtures() -> dict[str, Any]:
    """Criterion 6: Inspector Sessions and Fixtures."""
    start = time.perf_counter()
    py_fixture = REPO_ROOT / "sample_models" / "mcp" / "inspector_session_python.json"
    node_fixture = REPO_ROOT / "sample_models" / "mcp" / "inspector_session_node.json"
    guide_doc = REPO_ROOT / "docs" / "guides" / "mcp_agent_integration.md"

    assert py_fixture.exists(), f"Missing {py_fixture}"
    assert node_fixture.exists(), f"Missing {node_fixture}"
    assert guide_doc.exists(), f"Missing {guide_doc}"

    with open(py_fixture, "r", encoding="utf-8") as f:
        py_data = json.load(f)
    with open(node_fixture, "r", encoding="utf-8") as f:
        node_data = json.load(f)

    assert py_data.get("inspector_tool") == "@modelcontextprotocol/inspector"
    assert node_data.get("inspector_tool") == "@modelcontextprotocol/inspector"
    assert len(py_data.get("interactions", [])) >= 5
    assert len(node_data.get("interactions", [])) >= 5

    # Check documentation contains inspector commands
    guide_text = guide_doc.read_text(encoding="utf-8")
    assert "@modelcontextprotocol/inspector" in guide_text
    assert "inspector_session_python.json" in guide_text
    assert "inspector_session_node.json" in guide_text

    elapsed = time.perf_counter() - start
    return {
        "id": "CRITERION_6_INSPECTOR_FIXTURES",
        "name": "MCP Inspector Documentation & Fixtures",
        "passed": True,
        "elapsed_sec": round(elapsed, 4),
        "details": {
            "python_fixture": str(py_fixture.relative_to(REPO_ROOT)),
            "python_interactions": len(py_data["interactions"]),
            "node_fixture": str(node_fixture.relative_to(REPO_ROOT)),
            "node_interactions": len(node_data["interactions"]),
            "guide_doc_referenced": True,
        },
    }


def verify_criterion_7_security_loopback() -> dict[str, Any]:
    """Criterion 7: Loopback Isolation & Security Invariants."""
    start = time.perf_counter()
    from specsynth.mcp.bridge import is_loopback, run_bridge_server

    assert is_loopback("127.0.0.1")
    assert is_loopback("localhost")
    assert is_loopback("::1")
    assert not is_loopback("0.0.0.0")
    assert not is_loopback("192.168.1.100")

    rejected = False
    try:
        run_bridge_server(host="0.0.0.0", allow_remote=False)
    except ValueError as exc:
        if "Refusing to bind HTTP bridge to non-loopback" in str(exc):
            rejected = True
    assert rejected, "Bridge did not reject binding to 0.0.0.0 without --allow-remote"

    elapsed = time.perf_counter() - start
    return {
        "id": "CRITERION_7_SECURITY_LOOPBACK",
        "name": "Loopback Interface Security & Isolation",
        "passed": True,
        "elapsed_sec": round(elapsed, 4),
        "details": {
            "loopback_checks_passed": True,
            "non_loopback_rejected": True,
            "required_binding": "127.0.0.1",
        },
    }


def run_all_verifications() -> dict[str, Any]:
    print("=" * 80)
    print("  Milestone P4 Acceptance: Independent MCP Transport & Client Verification")
    print("=" * 80)

    verifiers = [
        ("Criterion 1: Lifecycle", verify_criterion_1_lifecycle),
        ("Criterion 2: Tool Discovery", verify_criterion_2_tool_discovery),
        ("Criterion 3: Workflow Execution", verify_criterion_3_workflow_execution),
        ("Criterion 4: Cross-Language Parity", verify_criterion_4_cross_language_parity),
        ("Criterion 5: Protocol Robustness & Negative", verify_criterion_5_robustness_negative),
        ("Criterion 6: Inspector Fixtures & Docs", verify_criterion_6_inspector_fixtures),
        ("Criterion 7: Loopback Security", verify_criterion_7_security_loopback),
    ]

    results = []
    all_passed = True
    total_start = time.perf_counter()

    for label, verifier in verifiers:
        sys.stdout.write(f"  * {label} ... ")
        sys.stdout.flush()
        try:
            res = verifier()
            results.append(res)
            print(f"PASSED ({res['elapsed_sec']}s)")
        except Exception as exc:
            all_passed = False
            print(f"FAILED: {exc}")
            results.append({
                "name": label,
                "passed": False,
                "error": str(exc),
            })

    total_elapsed = round(time.perf_counter() - total_start, 4)
    print("=" * 80)
    passed_count = sum(1 for r in results if r["passed"])
    status_str = "ALL PASSED" if all_passed else f"{len(results) - passed_count} FAILED"
    print(f"  Summary: {passed_count}/{len(results)} Criteria Passed ({status_str}) in {total_elapsed}s")
    print("=" * 80)

    report = {
        "milestone": "P4",
        "title": "Independent MCP Transport and Client End-to-End Acceptance",
        "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_criteria": len(results),
        "passed_criteria": passed_count,
        "all_passed": all_passed,
        "total_elapsed_sec": total_elapsed,
        "criteria": results,
    }

    report_path = REPO_ROOT / "benchmark_mcp_transport_acceptance.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report exported to: {report_path.relative_to(REPO_ROOT)}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify P4 MCP Transport and Client End-to-End Acceptance.")
    parser.parse_args()
    report = run_all_verifications()
    if not report["all_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
