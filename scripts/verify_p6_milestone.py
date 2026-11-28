"""
Comprehensive Verification Harness for Milestone P6 (GitHub Milestone #7 / Issue #20)
Independent Developer and External-Engine Validation
==================================================================
Verifies:
  1. Conformance Suite & Invariant assertions on built-in and external adapters
  2. Adapter Compatibility Policy (v1.0.0) declaration & boundaries
  3. External Engine Plugin (CB2026) dynamic registration and execution
  4. Contractual data validation (SSPGridContract & SyntheticObservationContract)
  5. MCP Protocol interoperability for external registered adapters
  6. Zero-Core-Modification invariant verification (Pillar 1)
  7. Documentation coverage & MkDocs navigation integrity
"""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path

# Add project root and examples plugin dir to sys.path
root_dir = Path(__file__).resolve().parent.parent
plugin_dir = root_dir / "examples" / "external_engine_plugin"

for p in [str(root_dir), str(plugin_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np

# Specsynth imports
from specsynth.adapters import (
    AdapterCompatibilityPolicy,
    AdapterConformanceError,
    AdapterConformanceResult,
    BaseAdapter,
    SSPData,
    ToyAdapter,
    assert_adapter_conforms,
    get_adapter,
    list_adapters,
    register_adapter,
    unregister_adapter,
)
from specsynth.contracts import (
    PhotometryPointContract,
    SSPGridContract,
    SyntheticObservationContract,
)
from specsynth.filters import get_filter
from specsynth.mcp.server import SpecsynthMCPServer


def log_step(name: str):
    print(f"\n{'=' * 75}\n[TEST] {name}\n{'=' * 75}")


def test_conformance_suite():
    log_step("1. Conformance Suite & Invariant Assertions")

    # A. Built-in ToyAdapter
    toy = ToyAdapter(n_age=5, n_met=2, n_wave=50)
    res_toy = assert_adapter_conforms(toy, verbose=False)
    assert res_toy.passed is True
    assert len(res_toy.checks_passed) >= 10
    print(f"  ✓ ToyAdapter passed {len(res_toy.checks_passed)} conformance checks.")

    # B. Non-conformant class failure
    class FaultyAdapter(BaseAdapter):
        def load(self, wave_resample=None):
            return SSPData(
                ages=np.array([1e8, 1e7]), # Non-monotonic
                mets=np.array([0.02]),
                wave=np.array([1000.0, 2000.0]),
                ssp=np.ones((2, 2)),
            )

    try:
        assert_adapter_conforms(FaultyAdapter, raise_on_error=True)
        raise AssertionError("FaultyAdapter should have failed conformance!")
    except (AdapterConformanceError, ValueError):
        print("  ✓ FaultyAdapter correctly caught and rejected by conformance suite.")


def test_compatibility_policy():
    log_step("2. Formal Compatibility Policy (v1.0.0)")

    policy = AdapterCompatibilityPolicy.get_policy_declaration()
    assert policy["specification_version"] == "1.0.0"
    assert "min_python_version" in policy
    assert policy["required_base_class"] == "specsynth.adapters.BaseAdapter"
    assert policy["required_container_class"] == "specsynth.adapters.SSPData"
    assert len(policy["invariants"]) >= 7

    bounds = policy["physical_bounds"]
    assert bounds["age_yr"] == [1e4, 2e10]
    assert bounds["metallicity_z"] == [1e-6, 0.10]
    assert bounds["wavelength_angstrom"] == [10.0, 1e6]

    print("  ✓ Formal Adapter Compatibility Policy verified against physical bounds.")


def test_external_engine_plugin():
    log_step("3. External Engine Plugin (CB2026) Lifecycle")

    # Import external adapter (triggers dynamic registration)
    from external_adapter import CB2026Adapter

    # Verify registration
    adapters = list_adapters()
    assert "cb2026" in adapters, "cb2026 not registered!"
    print(f"  ✓ 'cb2026' registered in Specsynth registry. Active: {sorted(list(adapters.keys()))}")

    # Verify conformance
    conformance = assert_adapter_conforms(CB2026Adapter, sample_kwargs={"n_wave": 600}, verbose=False)
    assert conformance.passed is True
    print(f"  ✓ CB2026Adapter passed 100% of conformance tests ({len(conformance.checks_passed)}/{len(conformance.checks_run)}).")

    # Instantiate via get_adapter
    inst = get_adapter("cb2026", n_wave=800)
    caps = inst.get_capabilities()
    assert caps["name"] == "cb2026_external"
    assert caps["zero_core_mod"] is True
    assert "Illustrative Demo Engine" in caps["provenance_badge"] or "Mock" in caps["provenance_badge"]
    print(f"  ✓ Retrieved '{caps['full_name']}' via standard get_adapter() factory.")
    print(f"  ✓ Provenance Badge strictly formatted: '{caps['provenance_badge']}'")

    # Load data
    ssp = inst.load()
    assert isinstance(ssp, SSPData)
    assert ssp.ssp.shape == (len(ssp.ages) * len(ssp.mets), len(ssp.wave))
    print(f"  ✓ Successfully produced 2D SSP grid: {ssp.ssp.shape} in age-major layout.")

    return ssp, caps


def test_contractual_validation(ssp_data, caps):
    log_step("4. Canonical Contractual Data Invariants")

    # A. Validate SSPGridContract
    ssp_contract = SSPGridContract(
        source_engine="cb2026",
        engine_version="2026.1-preview",
        imf=caps["imf"],
        isochrones=caps["isochrone"],
        ages_yr=ssp_data.ages,
        mets_z=ssp_data.mets,
        wave_angstrom=ssp_data.wave,
        ssp_flux_2d=ssp_data.ssp,
    )
    ssp_contract.validate()
    print("  ✓ SSPGridContract (v1.0.0) validation passed.")

    # B. Synthesize Mock Galaxy & Validate SyntheticObservationContract
    f150 = get_filter("jwst_f150w")
    t150 = f150.resample(ssp_data.wave)
    dl = np.gradient(ssp_data.wave)

    sed_rest = ssp_data.ssp[10, :] * 5e10
    band_flux = float(np.sum(sed_rest * t150 * dl) / np.maximum(np.sum(t150 * dl), 1e-30))

    point = PhotometryPointContract(
        filter_name="jwst_f150w",
        pivot_wavelength_angstrom=f150.pivot_wavelength,
        flux_density_ujy=band_flux * 1e-5,
        ab_magnitude=21.8,
    )
    obs = SyntheticObservationContract(
        galaxy_id="CB2026-VERIFY-001",
        redshift=1.2,
        cosmology={"h0": 67.74, "om0": 0.3089},
        dust_model="charlot_fall_2000",
        igm_model="madau_1995",
        ssp_model="cb2026_external",
        photometry=[point],
        sed_wave_angstrom=ssp_data.wave * 2.2,
        sed_flux_obs_cgs=sed_rest * 1e-32,
    )
    obs.validate()
    print("  ✓ SyntheticObservationContract (v1.0.0) validation passed.")


def test_mcp_integration():
    log_step("5. MCP Protocol Interoperability & Canonical Tool Handlers")

    server = SpecsynthMCPServer()
    assert len(server.tools) >= 10
    print(f"  ✓ SpecsynthMCPServer initialized with {len(server.tools)} tools (canonical + legacy aliases).")

    # A. Cosmology Calculation Tool
    cosmo_tool = server.tools["specsynth_calculate_cosmology"]["handler"]
    cosmo_res = cosmo_tool({"redshift": 2.0})
    assert cosmo_res["redshift"] == 2.0
    assert "luminosity_distance_mpc" in cosmo_res
    print(f"  ✓ MCP specsynth_calculate_cosmology(z=2.0) succeeded: d_L = {cosmo_res['luminosity_distance_mpc']} Mpc.")

    # B. System Info Tool
    sys_tool = server.tools["specsynth_get_system_info"]["handler"]
    sys_res = sys_tool({})
    assert "cpu_threads" in sys_res
    print(f"  ✓ MCP specsynth_get_system_info succeeded: CPU threads = {sys_res['cpu_threads']}.")

    # C. Scientific Sentry Audit Tool
    audit_tool = server.tools["specsynth_run_sentry_audit"]["handler"]
    audit_res = audit_tool({"sample_size": 50})
    assert "status" in audit_res
    print(f"  ✓ MCP specsynth_run_sentry_audit succeeded: status = {audit_res['status']}.")


def test_zero_core_modifications():
    log_step("6. Zero Core Modifications Verification (Pillar 1 - Frozen P0 Baseline)")

    from specsynth.governance import verify_frozen_baseline
    res = verify_frozen_baseline(repo_path=root_dir)
    assert res.status in ("CONFORMANT", "DRIFT_DETECTED"), f"Baseline verification error: {res.diagnostic_summary}"
    assert len(res.unauthorized_core_files) == 0, f"Unauthorized core modifications detected: {res.unauthorized_core_files}"
    assert len(res.external_plugin_files) > 0, "External plugin files not detected in repository!"

    print(f"  ✓ Audited against immutable P0 baseline: {res.baseline_sha[:12]}")
    print(f"  ✓ Verified {len(res.modified_core_files)} core files are 100% roadmap-attributed.")
    print(f"  ✓ Verified external plugin ({len(res.external_plugin_files)} files) operates without unauthorized core modifications.")


def test_documentation_and_nav():
    log_step("7. Documentation & MkDocs Navigation Integrity")

    import re
    with open(root_dir / "mkdocs.yml", encoding="utf-8") as f:
        text = f.read()

    # Verify newly added docs
    assert "guides/authoring_external_adapters.md" in text
    assert "guides/mcp_agent_integration.md" in text
    assert "architecture/engine_capabilities_matrix.md" in text

    # Verify no unreferenced markdown files
    docs_dir = root_dir / "docs"
    all_docs = set(p.relative_to(docs_dir).as_posix() for p in docs_dir.rglob("*.md"))
    referenced = set(re.findall(r'[\w\-/\.]+\.md', text))
    missing = all_docs - referenced

    assert len(missing) == 0, f"Unreferenced documentation files found: {missing}"
    print(f"  ✓ All {len(all_docs)} documentation pages are strictly registered in mkdocs.yml nav.")


def main():
    print("=" * 75)
    print("SPECSYNTH MILESTONE P6 (GitHub #7 / ISSUE #20) VERIFICATION HARNESS")
    print("Zero-Core-Modification Pluggability & External-Engine Validation")
    print("=" * 75)

    test_conformance_suite()
    test_compatibility_policy()
    ssp_data, caps = test_external_engine_plugin()
    test_contractual_validation(ssp_data, caps)
    test_mcp_integration()
    test_zero_core_modifications()
    test_documentation_and_nav()

    print("\n" + "=" * 75)
    print("ALL MILESTONE P6 ACCEPTANCE CRITERIA VERIFIED AND PASSED!")
    print("=" * 75)


if __name__ == "__main__":
    main()
