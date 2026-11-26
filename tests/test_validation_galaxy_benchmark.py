"""
Automated End-to-End Real Galaxy Validation Benchmark Test Suite.
Enforces P1.M2.10 (Issue #15) — Real-galaxy scientific validation with declared numerical tolerances.
"""

from pathlib import Path
import pytest

from scripts.validate_one_galaxy_fsps import TARGET_FILTERS, validate_one_galaxy
from specsynth.contracts.photometry import SyntheticObservationContract
from specsynth.provenance import validate_provenance_manifest


@pytest.mark.astrophysics
def test_one_galaxy_scientific_benchmark_tolerance():
    """
    Execute the real-galaxy forward modeling benchmark on subhalo tng100_subhalo_009873.
    Verifies:
      1. Maximum photometric divergence |Δm| < 0.005 mag across all 6 JWST NIRCam bands.
      2. Valid SyntheticObservationContract instance returned.
      3. Complete, valid cryptographic provenance manifest returned.
    """
    res = validate_one_galaxy("tng100_subhalo_009873")

    # 1. Assert declared numerical tolerance (< 0.005 mag)
    assert res["passed"] is True
    assert res["max_delta_mag"] < 0.005, f"Max delta mag exceeded tolerance: {res['max_delta_mag']} mag"

    # 2. Check bandpass specific tolerances
    for fname in TARGET_FILTERS:
        delta = res["delta_mags"][fname]
        assert delta < 0.005, f"Band {fname} diverged by {delta} mag (limit 0.005 mag)"

    # 3. Verify Observation Contract
    contract = res["observation_contract"]
    assert isinstance(contract, SyntheticObservationContract)
    assert contract.galaxy_id == "tng100_subhalo_009873"
    assert len(contract.photometry) == len(TARGET_FILTERS)
    assert len(contract.sed_wave_angstrom) > 0
    assert len(contract.sed_flux_obs_cgs) == len(contract.sed_wave_angstrom)

    # 4. Verify Provenance Manifest
    manifest = res["manifest"]
    assert validate_provenance_manifest(manifest) is True
    assert manifest["target"]["galaxy_id"] == "tng100_subhalo_009873"
    assert manifest["target"]["simulation_name"] == "IllustrisTNG-100"
    assert manifest["sps_engine"]["name"] in ("FSPS", "analytical_reference")
    assert "code_snippet" in manifest["reproducibility"]
