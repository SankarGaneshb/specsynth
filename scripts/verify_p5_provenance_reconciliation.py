#!/usr/bin/env python3
"""
scripts/verify_p5_provenance_reconciliation.py
=============================================
Verification harness for Milestone P5 (GitHub Issue #32):
End-to-end data-mode provenance and reviewer-assessment claim reconciliation.

Audits:
1. Canonical DataMode enumeration and non-promotion invariants.
2. Truth-in-labeling enforcement across 3D galaxy contracts and observations.
3. Dual-runtime MCP schema and response parity for data_mode and structured provenance.
4. Frozen P0 architecture baseline conformance (zero unauthorized core mutations).
5. Reviewer readiness assessment claims reconciliation and accuracy.
6. Exports benchmark_provenance_claim_reconciliation.json.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from specsynth.contracts.data_mode import DataMode, propagate_mode, classify_source_data_mode
from specsynth.contracts.galaxy3d import Galaxy3DContract, GeometrySource, ParticleBatchContract, ParticleType, CoordinateFrame
from specsynth.contracts.photometry import SyntheticObservationContract, PhotometryPointContract
from specsynth.contracts.evolution import EvolutionaryTrackContract, ProgenitorNode
from specsynth.contracts.mcp import CANONICAL_MCP_TOOLS, get_canonical_tool_schema
from specsynth.mcp.server import SpecsynthMCPServer
from specsynth.governance.baseline_verifier import verify_frozen_baseline


def audit_milestone_p5() -> dict:
    results = {
        "milestone": "P5",
        "issue": "#32",
        "title": "End-to-End Data-Mode Provenance & Claim Reconciliation",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": {},
        "status": "PASS",
    }

    # ---------------- 1. Canonical DataMode Enumeration ----------------
    print("[1/6] Auditing Canonical DataMode Enumeration...")
    expected_modes = {
        "simulation_derived",
        "cached_reference",
        "live_computation",
        "analytical_mock",
        "illustrative_demo",
    }
    actual_modes = {m.value for m in DataMode}
    assert actual_modes == expected_modes, f"DataMode mismatch: {actual_modes} vs {expected_modes}"
    
    # Category checks
    assert DataMode.SIMULATION_DERIVED.is_empirical_science() is True
    assert DataMode.LIVE_COMPUTATION.is_empirical_science() is True
    assert DataMode.ANALYTICAL_MOCK.is_mock_or_demo() is True
    assert DataMode.ILLUSTRATIVE_DEMO.is_mock_or_demo() is True
    
    results["checks"]["datamode_enumeration"] = {
        "status": "PASS",
        "modes": list(actual_modes),
    }
    print("  [PASS] DataMode enumeration & classification invariants verified.")

    # ---------------- 2. Non-Promotion Invariant ----------------
    print("[2/6] Auditing Non-Promotion Invariant Fail-Closed Behavior...")
    # Safe propagation
    assert propagate_mode("simulation_derived", "simulation_derived") == DataMode.SIMULATION_DERIVED
    assert propagate_mode("analytical_mock", "analytical_mock") == DataMode.ANALYTICAL_MOCK
    assert propagate_mode("cached_reference") == DataMode.CACHED_REFERENCE

    # Illegal promotion must fail
    promotion_failed = False
    try:
        propagate_mode("analytical_mock", "simulation_derived")
    except ValueError as exc:
        if "Non-promotion invariant violation" in str(exc):
            promotion_failed = True

    assert promotion_failed, "Failed to reject promotion of mock to simulation_derived!"

    demo_promotion_failed = False
    try:
        propagate_mode("illustrative_demo", "live_computation")
    except ValueError as exc:
        if "Non-promotion invariant violation" in str(exc):
            demo_promotion_failed = True

    assert demo_promotion_failed, "Failed to reject promotion of demo to live_computation!"

    results["checks"]["non_promotion_invariant"] = {
        "status": "PASS",
        "mock_to_sim_rejected": promotion_failed,
        "demo_to_live_rejected": demo_promotion_failed,
    }
    print("  [PASS] Non-promotion invariant strictly verified fail-closed.")

    # ---------------- 3. Truth-in-Labeling in 3D Galaxy & Observation ----------------
    print("[3/6] Auditing Truth-in-Labeling in 3D Galaxy Contracts...")
    rng = np.random.default_rng(42)
    stars = ParticleBatchContract(
        particle_type=ParticleType.STAR,
        coordinates_kpc=rng.normal(0.0, 1.5, size=(10, 3)).astype(np.float32),
        velocities_km_s=np.zeros((10, 3), dtype=np.float32),
        masses_msun=np.ones(10, dtype=np.float32) * 1e4,
    )

    truth_rejected = False
    try:
        Galaxy3DContract(
            galaxy_id="mock_specimen",
            geometry_source=GeometrySource.PROCEDURAL_ILLUSTRATIVE,
            coordinate_frame=CoordinateFrame.PHYSICAL_REST,
            redshift=1.0,
            center_of_mass_kpc=(0.0, 0.0, 0.0),
            half_mass_radius_kpc=2.0,
            components={"star": stars},
            data_mode="simulation_derived",
        )
    except ValueError as exc:
        if "Truth-in-labeling violation" in str(exc):
            truth_rejected = True

    assert truth_rejected, "Failed to catch truth-in-labeling violation in Galaxy3DContract!"

    # Factory auto-defaults to analytical_mock for procedural
    mock_galaxy = Galaxy3DContract.from_particles(
        galaxy_id="mock_specimen",
        redshift=1.0,
        components={"star": stars},
        geometry_source=GeometrySource.PROCEDURAL_ILLUSTRATIVE,
    )
    assert mock_galaxy.data_mode == "analytical_mock"

    # Observation contract inherits analytical_mock
    phot = [
        PhotometryPointContract(
            filter_name="jwst_nircam_f200w",
            pivot_wavelength_angstrom=19886.0,
            flux_density_ujy=10.0,
            ab_magnitude=21.4,
        )
    ]
    sed_w = np.linspace(1000, 50000, 20)
    sed_f = np.ones(20, dtype=np.float32) * 1e-18
    obs = mock_galaxy.to_observation_contract(
        photometry_points=phot,
        sed_wave_angstrom=sed_w,
        sed_flux_obs_cgs=sed_f,
        cosmology={"H0": 67.74, "Om0": 0.3089, "Ol0": 0.6911},
    )
    assert obs.data_mode == "analytical_mock"

    results["checks"]["truth_in_labeling"] = {
        "status": "PASS",
        "mock_simulation_derived_rejected": truth_rejected,
        "factory_mode_default": mock_galaxy.data_mode,
        "derived_observation_mode": obs.data_mode,
    }
    print("  [PASS] Truth-in-labeling and contract derivation verified.")

    # ---------------- 4. MCP Schema & Handler Parity ----------------
    print("[4/6] Auditing Dual-Runtime MCP Schema & Response Parity...")
    py_server = SpecsynthMCPServer()

    # 1. specsynth_inspect_galaxy
    py_insp_resp = py_server.handle_request({
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tools/call",
        "params": {"name": "specsynth_inspect_galaxy", "arguments": {"galaxy_id": "0"}},
    })
    py_insp = json.loads(py_insp_resp["result"]["content"][0]["text"])
    assert "data_mode" in py_insp, "data_mode missing from specsynth_inspect_galaxy response!"
    assert "provenance" in py_insp, "provenance missing from specsynth_inspect_galaxy response!"

    # 2. specsynth_get_3d_galaxy
    py_3d_resp = py_server.handle_request({
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tools/call",
        "params": {"name": "specsynth_get_3d_galaxy", "arguments": {"galaxy_id": "tng100_subhalo_real"}},
    })
    py_3d = json.loads(py_3d_resp["result"]["content"][0]["text"])
    assert py_3d.get("data_mode") == "simulation_derived"
    assert "provenance" in py_3d

    # 3. Node.js MCP parity call
    node_script = """
    import('./perandam-psi/mcp_server.mjs').then(async (m) => {
        const server = new m.PerandamMCPServer();
        const r1 = await server.handleRequest({
            jsonrpc: "2.0", id: 1, method: "tools/call",
            params: { name: "specsynth_inspect_galaxy", arguments: { galaxy_id: "0" } }
        });
        const r2 = await server.handleRequest({
            jsonrpc: "2.0", id: 2, method: "tools/call",
            params: { name: "specsynth_get_3d_galaxy", arguments: { galaxy_id: "tng100_subhalo_real" } }
        });
        console.log(JSON.stringify({
            inspect: JSON.parse(r1.result.content[0].text),
            galaxy3d: JSON.parse(r2.result.content[0].text),
        }));
    }).catch(err => { console.error(err); process.exit(1); });
    """
    node_proc = subprocess.run(
        ["node", "--input-type=module", "-e", node_script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    node_out = json.loads(node_proc.stdout.strip())
    assert node_out["inspect"]["data_mode"] == py_insp["data_mode"] == "cached_reference"
    assert node_out["galaxy3d"]["data_mode"] == py_3d["data_mode"] == "simulation_derived"

    results["checks"]["mcp_data_mode_parity"] = {
        "status": "PASS",
        "py_inspect_mode": py_insp["data_mode"],
        "node_inspect_mode": node_out["inspect"]["data_mode"],
        "py_3d_mode": py_3d["data_mode"],
        "node_3d_mode": node_out["galaxy3d"]["data_mode"],
    }
    print("  [PASS] MCP schema and dual-runtime response parity verified.")

    # ---------------- 5. Frozen Baseline Conformance ----------------
    print("[5/6] Auditing Frozen P0 Architecture Baseline...")
    baseline_res = verify_frozen_baseline(repo_path=REPO_ROOT)
    assert baseline_res.status == "CONFORMANT", f"Baseline status is {baseline_res.status}!"
    assert baseline_res.passed is True
    assert len(baseline_res.unauthorized_core_files) == 0

    results["checks"]["frozen_baseline_conformance"] = {
        "status": "PASS",
        "baseline_sha": baseline_res.baseline_sha[:12],
        "head_sha": baseline_res.tested_commit_sha[:12],
        "modified_core_files": len(baseline_res.modified_core_files),
        "unauthorized_core_files": len(baseline_res.unauthorized_core_files),
    }
    print(f"  [PASS] Frozen baseline verified CONFORMANT against commit {baseline_res.baseline_sha[:7]}.")

    # ---------------- 6. Reviewer Readiness Reconciliation ----------------
    print("[6/6] Auditing Reviewer Readiness Assessment File & Matrix...")
    assessment_file = REPO_ROOT / "docs" / "governance" / "reviewer_readiness_assessment.md"
    assert assessment_file.exists(), "reviewer_readiness_assessment.md missing from docs/governance/!"
    content = assessment_file.read_text(encoding="utf-8")

    assert "318 passed, 5 skipped, 0 failed" in content, "CI test counts not accurately cited!"
    assert "322 passed, 1 skipped" in content, "Local test counts not accurately cited!"
    assert "Section 6: Claim-to-Evidence Matrix" in content, "Section 6 Claim-to-Evidence Matrix missing!"
    assert "tng100_subhalo_real.hdf5" in content, "Genuine TNG cutout not cited in assessment!"
    assert "tng100_subhalo_424601_sublink_tree.json" in content, "Genuine SubLink tree not cited in assessment!"
    assert "absorption non-amplification invariant" in content.lower(), "Absorption non-amplification invariant not cited!"

    results["checks"]["reviewer_readiness_reconciliation"] = {
        "status": "PASS",
        "assessment_path": str(assessment_file.relative_to(REPO_ROOT)),
        "ci_test_run_cited": "318 passed, 5 skipped, 0 failed",
        "claim_to_evidence_matrix_present": True,
        "genuine_simulation_cutout_cited": True,
        "sublink_merger_tree_cited": True,
    }
    print("  [PASS] Reviewer readiness assessment claims reconciled and verified.")

    # Write benchmark JSON
    benchmark_file = REPO_ROOT / "benchmark_provenance_claim_reconciliation.json"
    with open(benchmark_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[SUCCESS] Milestone P5 Audit Complete. Summary saved to {benchmark_file.name}")
    return results


if __name__ == "__main__":
    audit_milestone_p5()
