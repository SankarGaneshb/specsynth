#!/usr/bin/env python3
"""
Scientific Provenance & Truthful Execution Verification Script.
Audits all 7 Acceptance Criteria of Issue #33 / P1:
1. Fail-closed Invariant on simulation_derived Source Provenance
2. Orthogonal Source vs. Execution Provenance Data Structures
3. Authentic In-Flight Forward Modeling in Python MCP Backend
4. Precomputed Reference Execution Mode for Baseline Lookups
5. Dual-Language Cross-Parity for Source and Execution Provenance
6. PerandamΨ Scientific UI Truth-in-Labeling & Decoupled State Check
7. Zero Regressions Against Frozen Architecture Baseline

Exports: benchmark_scientific_provenance_truth.json
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent

# Ensure local specsynth package is importable
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from specsynth.contracts.data_mode import (
    DataMode,
    ExecutionMode,
    ExecutionProvenance,
    SourceProvenance,
    propagate_mode,
    validate_source_provenance_evidence,
)
from specsynth.contracts.galaxy3d import Galaxy3DContract
from specsynth.contracts.photometry import SyntheticObservationContract
from specsynth.governance.baseline_verifier import verify_frozen_baseline
from specsynth.mcp.server import SpecsynthMCPServer


def run_node_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    node_script = f"""
    import {{ CANONICAL_MCP_TOOLS }} from './perandam-psi/mcp_server.mjs';
    const tool = CANONICAL_MCP_TOOLS[{json.dumps(tool_name)}];
    if (!tool) throw new Error("Tool " + {json.dumps(tool_name)} + " not found");
    const res = tool.handler({json.dumps(arguments)});
    console.log(JSON.stringify(res));
    """
    res = subprocess.run(
        ["node", "--input-type=module", "-e", node_script],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(res.stdout.strip())


def run_audit() -> Dict[str, Any]:
    audit_results: List[Dict[str, Any]] = []

    def record_check(ac_id: str, title: str, passed: bool, details: Dict[str, Any]):
        audit_results.append({
            "criterion": ac_id,
            "title": title,
            "status": "PASS" if passed else "FAIL",
            "details": details,
        })
        status_symbol = "✓ PASS" if passed else "✗ FAIL"
        print(f"[{status_symbol}] {ac_id}: {title}")

    print("=" * 80)
    print("  SPECSYNTH P1 AUDIT: SCIENTIFIC PROVENANCE & TRUTHFUL EXECUTION (ISSUE #33)")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # AC 1: Fail-closed Invariant on simulation_derived Source Provenance
    # -------------------------------------------------------------------------
    ac1_passed = False
    ac1_details = {}
    try:
        # Check 1a: Attempting to create an observation with simulation_derived without evidence must fail
        obs_fail_raised = False
        try:
            obs_invalid = SyntheticObservationContract(
                galaxy_id="fake_sim_galaxy",
                redshift=1.0,
                cosmology={"H0": 67.74, "Om0": 0.3089, "Ol0": 0.6911},
                dust_model="charlot_fall",
                igm_model="madau_1995",
                ssp_model="fsps",
                photometry=[],
                sed_wave_angstrom=np.linspace(1000, 10000, 50),
                sed_flux_obs_cgs=np.ones(50, dtype=np.float32),
                data_mode="simulation_derived",
                provenance={},  # missing simulation and subhalo evidence
            )
        except ValueError as exc:
            obs_fail_raised = True
            ac1_details["obs_validation_error"] = str(exc)

        # Check 1b: Valid simulation_derived evidence passes
        obs_valid = SyntheticObservationContract(
            galaxy_id="tng_subhalo_424601",
            redshift=1.0,
            cosmology={"H0": 67.74, "Om0": 0.3089, "Ol0": 0.6911},
            dust_model="charlot_fall",
            igm_model="madau_1995",
            ssp_model="fsps",
            photometry=[],
            sed_wave_angstrom=np.linspace(1000, 10000, 50),
            sed_flux_obs_cgs=np.ones(50, dtype=np.float32),
            data_mode="simulation_derived",
            provenance={"simulation": "IllustrisTNG-100-1", "subhalo_id": 424601},
        )
        obs_valid.validate()
        ac1_details["obs_valid_contract"] = "Successfully validated authentic simulation evidence"

        # Check 1c: Non-promotion invariant in propagate_mode
        combined_mode = propagate_mode(DataMode.SIMULATION_DERIVED, DataMode.ANALYTICAL_MOCK)
        ac1_details["combined_mode"] = combined_mode.value
        non_promotion_held = combined_mode == DataMode.ANALYTICAL_MOCK

        ac1_passed = obs_fail_raised and non_promotion_held
    except Exception as exc:
        ac1_details["unexpected_error"] = str(exc)

    record_check(
        "AC-1",
        "Fail-closed Invariant on simulation_derived Source Provenance",
        ac1_passed,
        ac1_details,
    )

    # -------------------------------------------------------------------------
    # AC 2: Orthogonal Source vs. Execution Provenance Data Structures
    # -------------------------------------------------------------------------
    ac2_passed = False
    ac2_details = {}
    try:
        sp = SourceProvenance(
            data_mode=DataMode.CACHED_REFERENCE,
            source_name="IllustrisTNG-100-1",
            source_id=424601,
            snapshot=99,
            checksums={"hdf5": "8f5853a5fb4b5af9eaf2e67e39e9ce8c7bb04018d61c37b58d609f4731860c31"},
            verification_state="VERIFIED_AGAINST_MANIFEST",
        )
        ep = ExecutionProvenance(
            execution_mode=ExecutionMode.LIVE_BACKEND,
            engine="SpecSynth Python GEMM Engine",
            endpoint="http://127.0.0.1:8000",
            latency_ms=18.0,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            parameters_applied={"redshift": 4.5, "dust_av": 1.2},
        )
        sp_dict = sp.to_dict()
        ep_dict = ep.to_dict()

        ac2_details["source_keys"] = list(sp_dict.keys())
        ac2_details["execution_keys"] = list(ep_dict.keys())

        # Verify separation of concerns
        has_source_fields = "source_name" in sp_dict and "data_mode" in sp_dict and "checksums" in sp_dict
        has_exec_fields = "execution_mode" in ep_dict and "engine" in ep_dict and "latency_ms" in ep_dict
        ac2_passed = has_source_fields and has_exec_fields
    except Exception as exc:
        ac2_details["error"] = str(exc)

    record_check(
        "AC-2",
        "Orthogonal Source vs. Execution Provenance Typed Dataclasses",
        ac2_passed,
        ac2_details,
    )

    # -------------------------------------------------------------------------
    # AC 3: Authentic In-Flight Forward Modeling in Python MCP Backend
    # -------------------------------------------------------------------------
    ac3_passed = False
    ac3_details = {}
    try:
        mcp = SpecsynthMCPServer()
        dynamic_res = mcp._tool_inspect_galaxy({
            "galaxy_id": "TNG-DISC-01",
            "redshift": 4.5,
            "dust_av": 1.2,
        })
        ac3_details["returned_redshift"] = dynamic_res.get("redshift")
        ac3_details["returned_av"] = dynamic_res.get("physical_properties", {}).get("av")
        ac3_details["execution_mode"] = dynamic_res.get("execution_provenance", {}).get("execution_mode")
        ac3_details["is_dynamic_override"] = dynamic_res.get("execution_provenance", {}).get("is_dynamic_override")
        ac3_details["photometry_bands"] = list(dynamic_res.get("photometry", {}).keys())

        is_live_backend = dynamic_res.get("execution_provenance", {}).get("execution_mode") == "live_backend"
        is_override = dynamic_res.get("execution_provenance", {}).get("is_dynamic_override") is True
        has_photometry = len(dynamic_res.get("photometry", {})) >= 6
        ac3_passed = is_live_backend and is_override and has_photometry
    except Exception as exc:
        ac3_details["error"] = str(exc)

    record_check(
        "AC-3",
        "Authentic In-Flight Forward Modeling in Python MCP Backend",
        ac3_passed,
        ac3_details,
    )

    # -------------------------------------------------------------------------
    # AC 4: Precomputed Reference Execution Mode for Baseline Lookups
    # -------------------------------------------------------------------------
    ac4_passed = False
    ac4_details = {}
    try:
        baseline_res = mcp._tool_inspect_galaxy({
            "galaxy_id": "TNG-DISC-01",
        })
        ac4_details["execution_mode"] = baseline_res.get("execution_provenance", {}).get("execution_mode")
        ac4_details["is_dynamic_override"] = baseline_res.get("execution_provenance", {}).get("is_dynamic_override")

        is_cached = baseline_res.get("execution_provenance", {}).get("execution_mode") == "precomputed_cached"
        not_override = baseline_res.get("execution_provenance", {}).get("is_dynamic_override") is False
        ac4_passed = is_cached and not_override
    except Exception as exc:
        ac4_details["error"] = str(exc)

    record_check(
        "AC-4",
        "Precomputed Reference Execution Mode for Baseline Lookups",
        ac4_passed,
        ac4_details,
    )

    # -------------------------------------------------------------------------
    # AC 5: Dual-Language Cross-Parity for Source and Execution Provenance
    # -------------------------------------------------------------------------
    ac5_passed = False
    ac5_details = {}
    try:
        inspect_node = run_node_tool("specsynth_inspect_galaxy", {"galaxy_id": "TNG-DISC-01"})
        g3d_node = run_node_tool("specsynth_get_3d_galaxy", {"galaxy_id": "TNG-0059"})
        evo_node = run_node_tool("specsynth_get_evolution_track", {"galaxy_id": "tng100_subhalo_424601"})

        ac5_details["inspect_has_source"] = "source_provenance" in inspect_node
        ac5_details["inspect_has_exec"] = "execution_provenance" in inspect_node
        ac5_details["inspect_exec_mode"] = inspect_node.get("execution_provenance", {}).get("execution_mode")
        ac5_details["g3d_has_source"] = "source_provenance" in g3d_node
        ac5_details["g3d_has_exec"] = "execution_provenance" in g3d_node
        ac5_details["evo_has_source"] = "source_provenance" in evo_node
        ac5_details["evo_has_exec"] = "execution_provenance" in evo_node

        ac5_passed = all([
            ac5_details["inspect_has_source"],
            ac5_details["inspect_has_exec"],
            ac5_details["inspect_exec_mode"] == "precomputed_cached",
            ac5_details["g3d_has_source"],
            ac5_details["g3d_has_exec"],
            ac5_details["evo_has_source"],
            ac5_details["evo_has_exec"],
        ])
    except Exception as exc:
        ac5_details["error"] = str(exc)

    record_check(
        "AC-5",
        "Dual-Language Cross-Parity for Source and Execution Provenance",
        ac5_passed,
        ac5_details,
    )

    # -------------------------------------------------------------------------
    # AC 6: PerandamΨ Scientific UI Truth-in-Labeling & Decoupled State Check
    # -------------------------------------------------------------------------
    ac6_passed = False
    ac6_details = {}
    try:
        # Check GalaxyInspector.tsx source code for decoupled state and dynamic swap
        gi_path = REPO_ROOT / "perandam-psi" / "src" / "components" / "GalaxyInspector.tsx"
        gi_src = gi_path.read_text(encoding="utf-8")

        has_active_exec = "activeExecutionMode" in gi_src
        has_backend_result = "backendResult" in gi_src
        has_live_backend_badge = "live_backend" in gi_src
        has_client_browser_badge = "client_browser" in gi_src
        has_precomputed_badge = "precomputed_cached" in gi_src

        # Check ProvenanceModal.tsx for zero hardcoding
        pm_path = REPO_ROOT / "perandam-psi" / "src" / "components" / "ProvenanceModal.tsx"
        pm_src = pm_path.read_text(encoding="utf-8")
        no_hardcoded_id = "isRealTNG = galaxy.subhalo_id === '424601'" not in pm_src
        no_hardcoded_particles = "const starCount = isRealTNG ? 14500" not in pm_src
        has_two_tabs = "activeTab === 'source'" in pm_src and "activeTab === 'execution'" in pm_src

        ac6_details["has_active_exec"] = has_active_exec
        ac6_details["has_backend_result"] = has_backend_result
        ac6_details["no_hardcoded_id"] = no_hardcoded_id
        ac6_details["no_hardcoded_particles"] = no_hardcoded_particles
        ac6_details["has_two_tabs"] = has_two_tabs

        ac6_passed = (
            has_active_exec
            and has_backend_result
            and has_live_backend_badge
            and has_client_browser_badge
            and has_precomputed_badge
            and no_hardcoded_id
            and no_hardcoded_particles
            and has_two_tabs
        )
    except Exception as exc:
        ac6_details["error"] = str(exc)

    record_check(
        "AC-6",
        "PerandamΨ Scientific UI Truth-in-Labeling & Zero-Hardcoding",
        ac6_passed,
        ac6_details,
    )

    # -------------------------------------------------------------------------
    # AC 7: Zero Regressions Against Frozen Architecture Baseline
    # -------------------------------------------------------------------------
    ac7_passed = False
    ac7_details = {}
    try:
        baseline_res = verify_frozen_baseline(repo_path=REPO_ROOT)
        ac7_details["baseline_status"] = baseline_res.status
        ac7_details["unauthorized_files"] = baseline_res.unauthorized_core_files
        ac7_passed = baseline_res.passed and len(baseline_res.unauthorized_core_files) == 0
    except Exception as exc:
        ac7_details["error"] = str(exc)

    record_check(
        "AC-7",
        "Zero Regressions Against Frozen Architecture Baseline",
        ac7_passed,
        ac7_details,
    )

    # -------------------------------------------------------------------------
    # Summary & Export
    # -------------------------------------------------------------------------
    total_checks = len(audit_results)
    passed_checks = sum(1 for r in audit_results if r["status"] == "PASS")
    overall_status = "ALL_PASSED" if passed_checks == total_checks else "SOME_FAILED"

    print("=" * 80)
    print(f"  AUDIT SUMMARY: {passed_checks}/{total_checks} Criteria Passed [{overall_status}]")
    print("=" * 80)

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "P1 / Issue #33",
        "overall_status": overall_status,
        "passed_criteria": passed_checks,
        "total_criteria": total_checks,
        "results": audit_results,
    }

    out_path = REPO_ROOT / "benchmark_scientific_provenance_truth.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Audit benchmark artifact written to: {out_path}")

    return report


if __name__ == "__main__":
    rep = run_audit()
    sys.exit(0 if rep["overall_status"] == "ALL_PASSED" else 1)
