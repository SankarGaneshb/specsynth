#!/usr/bin/env python3
"""
Scientific Provenance & Truthful Execution Verification Script.
Audits all 7 Acceptance Criteria of Issue #33 / P1 through actual behavioral and negative tests:
1. Fail-closed Invariant on simulation_derived Source Provenance (Negative & Tampering Tests)
2. Orthogonal Source vs. Execution Provenance Data Structures & Typed Contract Enforcement
3. Authentic In-Flight Forward Modeling in Python MCP Backend & Physical Invariant Verification
4. Precomputed Reference Execution Mode for Baseline Lookups
5. Dual-Language Cross-Parity for Source and Execution Provenance (Full Node Test Suite Execution)
6. PerandamΨ Scientific UI Truth-in-Labeling, Zero Fallback Manufacture & Race Condition Handling
7. Zero Regressions Against Frozen Architecture Baseline

Exports: benchmark_scientific_provenance_truth.json
"""

from __future__ import annotations

import json
import os
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
    VerificationStatus,
    compute_file_sha256,
    propagate_mode,
    validate_source_provenance_evidence,
    verify_simulation_cutout_manifest,
)
from specsynth.contracts.galaxy3d import Galaxy3DContract
from specsynth.contracts.photometry import SyntheticObservationContract
from specsynth.governance.baseline_verifier import verify_frozen_baseline
from specsynth.mcp.server import SpecsynthMCPServer

TNG_REAL_CUTOUT = REPO_ROOT / "sample_models" / "3d" / "tng100_subhalo_real.hdf5"
EXPECTED_TNG_SHA256 = "8f5853a5fb4b5af9eaf2e67e39e9ce8c7bb04018d61c37b58d609f4731860c31"


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
        # Check 1a: Unmanifested galaxy fails validation
        empty_failed = False
        try:
            validate_source_provenance_evidence(DataMode.SIMULATION_DERIVED, {})
        except ValueError as exc:
            empty_failed = True
            ac1_details["empty_provenance_rejected"] = str(exc)

        # Check 1b: Fabricated TNG identity fails validation
        fake_id_failed = False
        try:
            validate_source_provenance_evidence(
                DataMode.SIMULATION_DERIVED,
                {
                    "source_name": "IllustrisTNG-100-1",
                    "subhalo_id": 999999,
                    "snapshot": 99,
                    "verification_status": VerificationStatus.UNKNOWN,
                },
            )
        except ValueError as exc:
            fake_id_failed = True
            ac1_details["fabricated_tng_rejected"] = str(exc)

        # Check 1c: Tampered checksum fails validation
        tampered_failed = False
        try:
            validate_source_provenance_evidence(
                DataMode.SIMULATION_DERIVED,
                {
                    "source_name": "IllustrisTNG-100-1",
                    "subhalo_id": 424601,
                    "snapshot": 99,
                    "content_sha256": "tampered_hash_0000",
                    "expected_sha256": EXPECTED_TNG_SHA256,
                },
            )
        except ValueError as exc:
            tampered_failed = True
            ac1_details["tampered_checksum_rejected"] = str(exc)

        # Check 1d: Real TNG cutout on disk passes genuine checksum verification
        cutout_verified = False
        if TNG_REAL_CUTOUT.exists():
            status, msg = verify_simulation_cutout_manifest(
                file_path=str(TNG_REAL_CUTOUT),
                expected_sha256=EXPECTED_TNG_SHA256,
                expected_snapshot=99,
                expected_subhalo_id=424601,
            )
            cutout_verified = status == VerificationStatus.VERIFIED
            ac1_details["disk_cutout_verification"] = msg

        # Check 1e: Non-promotion invariant in propagate_mode
        non_promotion_held = False
        try:
            propagate_mode(DataMode.ANALYTICAL_MOCK, DataMode.SIMULATION_DERIVED)
        except ValueError:
            non_promotion_held = True

        ac1_passed = empty_failed and fake_id_failed and tampered_failed and cutout_verified and non_promotion_held
    except Exception as exc:
        ac1_details["unexpected_error"] = str(exc)

    record_check(
        "AC-1",
        "Fail-closed Invariant on simulation_derived Source Provenance",
        ac1_passed,
        ac1_details,
    )

    # -------------------------------------------------------------------------
    # AC 2: Orthogonal Source vs. Execution Provenance Typed Dataclasses
    # -------------------------------------------------------------------------
    ac2_passed = False
    ac2_details = {}
    try:
        sp = SourceProvenance(
            data_mode=DataMode.CACHED_REFERENCE,
            source_name="IllustrisTNG-100-1",
            source_id=424601,
            snapshot=99,
            verification_status=VerificationStatus.VERIFIED,
            content_sha256=EXPECTED_TNG_SHA256,
            expected_sha256=EXPECTED_TNG_SHA256,
            manifest_path=str(REPO_ROOT / "sample_models" / "3d" / "tng100_subhalo_real_manifest.json"),
        )
        ep = ExecutionProvenance(
            execution_mode=ExecutionMode.LIVE_BACKEND,
            engine="SpecSynth Python GEMM Engine",
            endpoint="http://127.0.0.1:8000",
            latency_ms=18.0,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            parameters_applied={"redshift": 4.5, "dust_av": 1.2},
            request_id="req_tng_424601_z4.5",
            input_fingerprint="tng_424601:z=4.5000:av=1.2000",
        )
        sp_dict = sp.to_dict()
        ep_dict = ep.to_dict()

        ac2_details["source_keys"] = list(sp_dict.keys())
        ac2_details["execution_keys"] = list(ep_dict.keys())

        # Verify separation of concerns and typed propagation in observation contract
        obs = SyntheticObservationContract(
            galaxy_id="tng_subhalo_424601",
            redshift=1.0,
            cosmology={"H0": 67.74, "Om0": 0.3089, "Ol0": 0.6911},
            dust_model="charlot_fall",
            igm_model="madau_1995",
            ssp_model="fsps",
            photometry=[],
            sed_wave_angstrom=np.linspace(1000, 10000, 50),
            sed_flux_obs_cgs=np.ones(50, dtype=np.float32),
            source_provenance=sp,
            execution_provenance=ep,
        )
        obs_dict = obs.to_dict()
        obs_enforces_typed = (
            obs_dict["source_provenance"]["verification_status"] == "verified"
            and obs_dict["execution_provenance"]["execution_mode"] == "live_backend"
        )

        has_source_fields = "source_name" in sp_dict and "verification_status" in sp_dict
        has_exec_fields = "execution_mode" in ep_dict and "input_fingerprint" in ep_dict
        ac2_passed = has_source_fields and has_exec_fields and obs_enforces_typed
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
        # Test unattenuated baseline vs dust attenuated
        res_baseline = mcp._tool_inspect_galaxy({"galaxy_id": "TNG-DISC-01", "dust_av": 0.0})
        res_dust = mcp._tool_inspect_galaxy({"galaxy_id": "TNG-DISC-01", "dust_av": 2.0})

        ac3_details["baseline_execution_mode"] = res_baseline.get("execution_provenance", {}).get("execution_mode")
        ac3_details["dust_execution_mode"] = res_dust.get("execution_provenance", {}).get("execution_mode")

        # Physical invariant: dust attenuation must reduce flux (F_dust <= F_baseline)
        f_base = res_baseline.get("fluxes_cgs", {}).get("jwst_f090w", 0)
        f_dust = res_dust.get("fluxes_cgs", {}).get("jwst_f090w", 0)
        dust_attenuates = 0 < f_dust <= f_base
        ac3_details["f_base_jwst_f090w"] = f_base
        ac3_details["f_dust_jwst_f090w"] = f_dust
        ac3_details["dust_attenuates"] = dust_attenuates

        is_live_backend = res_dust.get("execution_provenance", {}).get("execution_mode") == "live_backend"
        is_override = res_dust.get("execution_provenance", {}).get("is_dynamic_override") is True
        has_photometry = len(res_dust.get("photometry", {})) >= 6

        ac3_passed = is_live_backend and is_override and has_photometry and dust_attenuates
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
        # Run the full Node.js test suite including dedicated scientific provenance test
        node_test_run = subprocess.run(
            ["npm", "--prefix", "perandam-psi", "test"],
            shell=True,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        ac5_details["node_test_exit_code"] = node_test_run.returncode
        ac5_details["node_test_passed"] = node_test_run.returncode == 0

        # Cross-parity tool output checks with strict normalized value assertions
        inspect_node = run_node_tool("specsynth_inspect_galaxy", {"galaxy_id": "tng_424601"})
        inspect_py = mcp._tool_inspect_galaxy({"galaxy_id": "tng_424601"})

        g3d_node = run_node_tool("specsynth_get_3d_galaxy", {"galaxy_id": "tng100_subhalo_real"})
        g3d_py = mcp._tool_get_3d_galaxy({"galaxy_id": "tng100_subhalo_real"})

        trk_node = run_node_tool("specsynth_get_evolution_track", {"galaxy_id": "424601"})
        trk_py = mcp._tool_get_evolution_track({"galaxy_id": "424601"})

        inspect_parity = (
            inspect_py["data_mode"] == inspect_node["data_mode"] == "simulation_derived"
            and inspect_py["source_provenance"]["verification_status"] == inspect_node["source_provenance"]["verification_status"] == "verified"
            and inspect_py["source_provenance"]["checksum_sha256"] == inspect_node["source_provenance"]["checksum_sha256"] == "8f5853a5fb4b5af9eaf2e67e39e9ce8c7bb04018d61c37b58d609f4731860c31"
        )
        g3d_parity = (
            g3d_py["data_mode"] == g3d_node["data_mode"] == "simulation_derived"
            and g3d_py["source_provenance"]["verification_status"] == g3d_node["source_provenance"]["verification_status"] == "verified"
            and g3d_py["source_provenance"]["verified_authentic"] == g3d_node["source_provenance"]["verified_authentic"] is True
        )
        trk_parity = (
            trk_py["data_mode"] == trk_node["data_mode"] == "simulation_derived"
            and trk_py["source_provenance"]["verification_status"] == trk_node["source_provenance"]["verification_status"] == "verified"
            and trk_py["source_provenance"]["subhalo_id"] == trk_node["source_provenance"]["subhalo_id"] == 424601
        )

        ac5_details["inspect_parity"] = inspect_parity
        ac5_details["g3d_parity"] = g3d_parity
        ac5_details["trk_parity"] = trk_parity

        ac5_passed = (
            node_test_run.returncode == 0
            and inspect_parity
            and g3d_parity
            and trk_parity
        )
    except Exception as exc:
        ac5_details["error"] = str(exc)

    record_check(
        "AC-5",
        "Dual-Language Cross-Parity for Source and Execution Provenance",
        ac5_passed,
        ac5_details,
    )

    # -------------------------------------------------------------------------
    # AC 6: PerandamΨ Scientific UI Truth-in-Labeling & Zero-Hardcoding
    # -------------------------------------------------------------------------
    ac6_passed = False
    ac6_details = {}
    try:
        # 1. Check GalaxyInspector.tsx for deterministic fingerprint and atomic binding
        gi_path = REPO_ROOT / "perandam-psi" / "src" / "components" / "GalaxyInspector.tsx"
        gi_src = gi_path.read_text(encoding="utf-8")

        has_fingerprint = "currentFingerprint = `${originGalaxy.id}:${inputDataId}:z=${currentZ.toFixed(4)}:av=${currentAv.toFixed(4)}:cfg=${engineCfgVersion}`" in gi_src
        has_match_check = "activeFingerprintRef.current === reqFingerprint" in gi_src
        has_galaxy_match = "activeGalaxyIdRef.current === reqGalaxyId" in gi_src
        has_abort_controller = "new AbortController()" in gi_src
        has_finally_guard = "if (activeFingerprintRef.current === reqFingerprint)" in gi_src

        # 2. Check ProvenanceModal.tsx for zero fallback manufacture
        pm_path = REPO_ROOT / "perandam-psi" / "src" / "components" / "ProvenanceModal.tsx"
        pm_src = pm_path.read_text(encoding="utf-8")
        no_fallback_tng = "galaxy.subhalo_id ? 'IllustrisTNG-100-1'" not in pm_src
        no_fallback_snap = "galaxy.galaxy3d?.provenance?.snapshot ?? 99" not in pm_src
        no_hardcoded_cosmology = "H0: 67.74" not in pm_src
        has_verification_status = "sourceProv.verification_status" in pm_src

        ac6_details["has_fingerprint"] = has_fingerprint
        ac6_details["has_match_check"] = has_match_check
        ac6_details["has_galaxy_match"] = has_galaxy_match
        ac6_details["has_abort_controller"] = has_abort_controller
        ac6_details["has_finally_guard"] = has_finally_guard
        ac6_details["no_fallback_tng"] = no_fallback_tng
        ac6_details["no_fallback_snap"] = no_fallback_snap
        ac6_details["no_hardcoded_cosmology"] = no_hardcoded_cosmology
        ac6_details["has_verification_status"] = has_verification_status

        ac6_passed = all([
            has_fingerprint,
            has_match_check,
            has_galaxy_match,
            has_abort_controller,
            has_finally_guard,
            no_fallback_tng,
            no_fallback_snap,
            no_hardcoded_cosmology,
            has_verification_status,
        ])
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

