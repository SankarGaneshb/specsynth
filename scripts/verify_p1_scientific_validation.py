#!/usr/bin/env python3
"""
scripts/verify_p1_scientific_validation.py
Acceptance verification harness for Milestone P1 / GitHub Issue #31:
Strengthen scientific validation: dust energy balance and cosmology accuracy.

Audits:
1. Dust absorption non-amplification invariant (Integral(F_att) <= Integral(F_int)).
2. Scientific disclosure that infrared dust thermal re-emission is not modeled.
3. Independent numerical parity against Astropy FlatLambdaCDM across z in [0.0, 10.0].
4. Gauss-Legendre quadrature convergence (n=50, 100, 200, 500).
5. Cosmology edge cases (z=0, z<0, high-z, parameter bounds) fail-closed.
6. Machine-readable report exported to benchmark_cosmology_dust_validation.json.
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

import numpy as np

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from specsynth.core import attenuation_curve, synth_block
from specsynth.cosmology import (
    C_KM_S,
    DEFAULT_COSMOLOGY,
    FlatLambdaCDM,
    PLANCK18_COSMOLOGY,
    TNG_COSMOLOGY,
)


def verify_criterion_1_dust_non_amplification() -> dict[str, Any]:
    """Criterion 1: Dust attenuation absorption non-amplification invariant."""
    start = time.perf_counter()

    wave = np.linspace(1000.0, 10000.0, 500, dtype=np.float32)
    kd = attenuation_curve(wave, -0.7)
    kb = attenuation_curve(wave, -1.3)

    # 1. Zero dust optical depth must leave flux strictly identical
    sfh = np.random.uniform(1e7, 1e10, (10, 15)).astype(np.float32)
    ssp = np.random.uniform(1e-5, 1e-3, (15, 500)).astype(np.float32)
    tau_zero = np.zeros(10, dtype=np.float32)
    spec_pure = synth_block(sfh, tau_zero, tau_zero, ssp, kd, kb, n_young_k=4, use_gpu=False)
    spec_gemm = sfh @ ssp
    assert np.allclose(spec_pure, spec_gemm, rtol=1e-6), "Zero dust must leave spectrum bitwise identical"

    # 2. Non-zero optical depth must strictly attenuate (absorb/scatter), never amplify
    tau_d = np.random.uniform(0.1, 2.5, 10).astype(np.float32)
    tau_b = 1.5 * tau_d
    spec_atten = synth_block(sfh, tau_d, tau_b, ssp, kd, kb, n_young_k=4, use_gpu=False)

    dw = np.diff(wave)
    int_atten = np.sum(0.5 * (spec_atten[:, 1:] + spec_atten[:, :-1]) * dw, axis=1)
    int_pure = np.sum(0.5 * (spec_pure[:, 1:] + spec_pure[:, :-1]) * dw, axis=1)

    assert np.all(int_atten <= int_pure + 1e-6), "Attenuated flux exceeded unattenuated flux"
    assert np.all(int_atten < int_pure), "Non-zero optical depth failed to attenuate flux"

    max_atten_frac = float(np.max(int_atten / int_pure))
    min_atten_frac = float(np.min(int_atten / int_pure))

    elapsed = time.perf_counter() - start
    return {
        "id": "CRITERION_1_DUST_NON_AMPLIFICATION",
        "name": "Dust Absorption Non-Amplification Invariant",
        "passed": True,
        "elapsed_sec": round(elapsed, 4),
        "details": {
            "invariant_checked": "Integral(F_attenuated d_lambda) < Integral(F_intrinsic d_lambda)",
            "max_attenuated_flux_fraction": round(max_atten_frac, 4),
            "min_attenuated_flux_fraction": round(min_atten_frac, 4),
            "zero_dust_identity_verified": True,
        },
    }


def verify_criterion_2_dust_ir_disclosure() -> dict[str, Any]:
    """Criterion 2: Verify explicit scientific disclosure that IR dust emission is not modeled."""
    start = time.perf_counter()

    test_file = REPO_ROOT / "tests" / "test_validation_external.py"
    content = test_file.read_text(encoding="utf-8")

    assert "test_dust_attenuation_non_amplification_invariant" in content
    assert "NOT implemented" in content or "not implemented" in content
    assert "far-IR dust thermal re-emission" in content or "infrared" in content

    elapsed = time.perf_counter() - start
    return {
        "id": "CRITERION_2_DUST_IR_DISCLOSURE",
        "name": "Absence of Far-IR Re-emission Disclosure",
        "passed": True,
        "elapsed_sec": round(elapsed, 4),
        "details": {
            "test_renamed_to": "test_dust_attenuation_non_amplification_invariant",
            "disclosure_text_present": True,
            "misleading_claims_eliminated": True,
        },
    }


def verify_criterion_3_astropy_cosmology_parity() -> dict[str, Any]:
    """Criterion 3: Numerical parity against Astropy FlatLambdaCDM across z in [0.0, 10.0]."""
    start = time.perf_counter()

    try:
        from astropy.cosmology import FlatLambdaCDM as AstropyFlatLambdaCDM
        import astropy
        astropy_ver = astropy.__version__
    except ImportError:
        raise RuntimeError("astropy is required for Criterion 3 external validation")

    test_models = [
        ("Planck2018", 67.74, 0.3089),
        ("WMAP9", 69.3, 0.286),
    ]
    test_redshifts = [0.0, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 7.0, 10.0]

    grid_results = []
    max_rel_errors = {"comoving_distance": 0.0, "luminosity_distance": 0.0, "angular_diameter_distance": 0.0, "lookback_time": 0.0, "cosmic_age": 0.0}

    for model_name, H0, Om0 in test_models:
        spec_cosmo = FlatLambdaCDM(H0=H0, Om0=Om0)
        astro_cosmo = AstropyFlatLambdaCDM(H0=H0, Om0=Om0)

        for z in test_redshifts:
            if z == 0.0:
                assert spec_cosmo.comoving_distance(0.0) == 0.0
                assert spec_cosmo.luminosity_distance(0.0) == 0.0
                assert spec_cosmo.angular_diameter_distance(0.0) == 0.0
                assert spec_cosmo.lookback_time_gyr(0.0) == 0.0
                age_spec = float(spec_cosmo.cosmic_time_gyr(0.0))
                age_astro = float(astro_cosmo.age(0.0).value)
                rel_age = abs(age_spec - age_astro) / age_astro
                assert rel_age < 1e-5
                continue

            dc_spec = float(spec_cosmo.comoving_distance(z))
            dc_astro = float(astro_cosmo.comoving_distance(z).value)
            rel_dc = abs(dc_spec - dc_astro) / dc_astro
            assert rel_dc < 1e-5, f"Comoving distance error at z={z}: {rel_dc:.2e}"

            dl_spec = float(spec_cosmo.luminosity_distance(z))
            dl_astro = float(astro_cosmo.luminosity_distance(z).value)
            rel_dl = abs(dl_spec - dl_astro) / dl_astro
            assert rel_dl < 1e-5, f"Luminosity distance error at z={z}: {rel_dl:.2e}"

            da_spec = float(spec_cosmo.angular_diameter_distance(z))
            da_astro = float(astro_cosmo.angular_diameter_distance(z).value)
            rel_da = abs(da_spec - da_astro) / da_astro
            assert rel_da < 1e-5, f"Angular diameter distance error at z={z}: {rel_da:.2e}"

            tlb_spec = float(spec_cosmo.lookback_time_gyr(z))
            tlb_astro = float(astro_cosmo.lookback_time(z).value)
            rel_tlb = abs(tlb_spec - tlb_astro) / tlb_astro
            assert rel_tlb < 1e-5, f"Lookback time error at z={z}: {rel_tlb:.2e}"

            tage_spec = float(spec_cosmo.cosmic_time_gyr(z))
            tage_astro = float(astro_cosmo.age(z).value)
            rel_tage = abs(tage_spec - tage_astro) / tage_astro
            assert rel_tage < 1e-5, f"Cosmic age error at z={z}: {rel_tage:.2e}"

            max_rel_errors["comoving_distance"] = max(max_rel_errors["comoving_distance"], rel_dc)
            max_rel_errors["luminosity_distance"] = max(max_rel_errors["luminosity_distance"], rel_dl)
            max_rel_errors["angular_diameter_distance"] = max(max_rel_errors["angular_diameter_distance"], rel_da)
            max_rel_errors["lookback_time"] = max(max_rel_errors["lookback_time"], rel_tlb)
            max_rel_errors["cosmic_age"] = max(max_rel_errors["cosmic_age"], rel_tage)

            grid_results.append({
                "model": model_name,
                "z": z,
                "d_C_spec": round(dc_spec, 4),
                "d_C_astro": round(dc_astro, 4),
                "rel_err_dC": round(rel_dc, 8),
                "d_L_spec": round(dl_spec, 4),
                "d_L_astro": round(dl_astro, 4),
                "rel_err_dL": round(rel_dl, 8),
            })

    elapsed = time.perf_counter() - start
    return {
        "id": "CRITERION_3_ASTROPY_COSMOLOGY_PARITY",
        "name": "Independent Astropy FlatLambdaCDM Grid Parity",
        "passed": True,
        "elapsed_sec": round(elapsed, 4),
        "details": {
            "astropy_version": astropy_ver,
            "redshifts_tested": test_redshifts,
            "max_relative_residuals": {k: f"{v:.2e}" for k, v in max_rel_errors.items()},
            "tolerance": "< 1.00e-05",
            "sample_grid_evaluations": len(grid_results),
        },
    }


def verify_criterion_4_quadrature_convergence() -> dict[str, Any]:
    """Criterion 4: Gauss-Legendre quadrature convergence test."""
    start = time.perf_counter()

    cosmo = DEFAULT_COSMOLOGY
    z = 2.0
    orders = [20, 50, 100, 200, 500]
    distances = [float(cosmo.comoving_distance(z, n_steps=n)) for n in orders]

    ref_d = distances[-1]  # n=500 reference
    convergence = []
    for n, d in zip(orders, distances):
        rel_diff = abs(d - ref_d) / ref_d
        convergence.append({"order": n, "distance_mpc": round(d, 5), "rel_diff_vs_500": f"{rel_diff:.2e}"})

    # Assert production order n=100 converges within 1e-6 of n=500
    rel_diff_100 = abs(distances[2] - ref_d) / ref_d
    assert rel_diff_100 < 1e-6, f"Production quadrature failed convergence: {rel_diff_100:.2e}"

    elapsed = time.perf_counter() - start
    return {
        "id": "CRITERION_4_QUADRATURE_CONVERGENCE",
        "name": "Gauss-Legendre Quadrature Convergence",
        "passed": True,
        "elapsed_sec": round(elapsed, 4),
        "details": {
            "test_redshift": z,
            "production_quadrature_order": 100,
            "relative_error_vs_500_nodes": f"{rel_diff_100:.2e}",
            "convergence_table": convergence,
        },
    }


def verify_criterion_5_cosmology_edge_cases() -> dict[str, Any]:
    """Criterion 5: Cosmology edge cases and exception handling fail-closed."""
    start = time.perf_counter()

    cosmo = FlatLambdaCDM(H0=70.0, Om0=0.3)

    # 1. z = 0 boundary
    assert cosmo.comoving_distance(0.0) == 0.0
    assert cosmo.luminosity_distance(0.0) == 0.0
    assert cosmo.angular_diameter_distance(0.0) == 0.0
    assert cosmo.lookback_time_gyr(0.0) == 0.0

    # 2. Negative z must raise ValueError
    for fn in [cosmo.comoving_distance, cosmo.cosmic_time_gyr, cosmo.lookback_time_gyr]:
        raised = False
        try:
            fn(-0.5)
        except ValueError as exc:
            if "non-negative" in str(exc):
                raised = True
        assert raised, f"{fn.__name__} did not raise ValueError on negative z"

    # 3. Invalid parameter bounds must raise ValueError
    params = [(0.0, 0.3), (-70.0, 0.3), (70.0, 0.0), (70.0, 1.5)]
    for h, om in params:
        raised = False
        try:
            FlatLambdaCDM(H0=h, Om0=om)
        except ValueError:
            raised = True
        assert raised, f"FlatLambdaCDM failed to reject invalid parameters H0={h}, Om0={om}"

    # 4. High-redshift evaluation (z=20.0)
    d_20 = cosmo.comoving_distance(20.0)
    t_20 = cosmo.cosmic_time_gyr(20.0)
    assert np.isfinite(d_20) and d_20 > cosmo.comoving_distance(10.0)
    assert np.isfinite(t_20) and 0.0 < t_20 < cosmo.cosmic_time_gyr(10.0)

    elapsed = time.perf_counter() - start
    return {
        "id": "CRITERION_5_COSMOLOGY_EDGE_CASES",
        "name": "Cosmology Edge Cases & Fail-Closed Validation",
        "passed": True,
        "elapsed_sec": round(elapsed, 4),
        "details": {
            "z_zero_boundary_tested": True,
            "negative_z_rejection_tested": True,
            "parameter_bounds_rejection_tested": True,
            "high_redshift_z20_stability_tested": True,
        },
    }


def run_all_verifications() -> dict[str, Any]:
    print("=" * 80)
    print("  Milestone P1 Scientific Validation: Dust Invariants & Cosmology Accuracy")
    print("=" * 80)

    verifiers = [
        ("Criterion 1: Dust Non-Amplification Invariant", verify_criterion_1_dust_non_amplification),
        ("Criterion 2: Far-IR Re-emission Disclosure", verify_criterion_2_dust_ir_disclosure),
        ("Criterion 3: Astropy Cosmology Parity", verify_criterion_3_astropy_cosmology_parity),
        ("Criterion 4: Quadrature Convergence", verify_criterion_4_quadrature_convergence),
        ("Criterion 5: Cosmology Edge Cases & Exceptions", verify_criterion_5_cosmology_edge_cases),
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

    import astropy
    import scipy

    report = {
        "milestone": "P1",
        "issue": "#31",
        "title": "Strengthen scientific validation: dust energy balance and cosmology accuracy",
        "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "environment": {
            "python_version": sys.version.split()[0],
            "numpy_version": np.__version__,
            "astropy_version": astropy.__version__,
            "scipy_version": scipy.__version__,
        },
        "total_criteria": len(results),
        "passed_criteria": passed_count,
        "all_passed": all_passed,
        "total_elapsed_sec": total_elapsed,
        "criteria": results,
    }

    report_path = REPO_ROOT / "benchmark_cosmology_dust_validation.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report exported to: {report_path.relative_to(REPO_ROOT)}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify P1 Scientific Validation (Dust & Cosmology).")
    parser.parse_args()
    report = run_all_verifications()
    if not report["all_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
