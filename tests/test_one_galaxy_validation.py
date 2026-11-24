"""
Automated Pytest Suite for SpecSynth One-Galaxy Scientific Validation Benchmark.

Verifies end-to-end forward modeling against independent astrophysical integration:
- Parameter extraction from TNG sample catalog (tng100_subhalo_009873).
- Delayed-tau star formation history and Charlot & Fall (2000) attenuation.
- Madau (1995) IGM attenuation and FlatLambdaCDM distance dimming.
- In-flight filter projection into JWST NIRCam bands with |Δm| < 0.02 mag.
"""

from __future__ import annotations

import pytest

from scripts.validate_one_galaxy_fsps import TARGET_FILTERS, validate_one_galaxy


def test_one_galaxy_scientific_parity() -> None:
    """Verifies that SpecSynth synthesis matches independent integration within 0.02 mag."""
    res = validate_one_galaxy("tng100_subhalo_009873")

    assert res["passed"] is True, f"Parity check failed with max_delta={res['max_delta_mag']} mag"
    assert res["max_delta_mag"] < 0.02, f"Max delta {res['max_delta_mag']} exceeds 0.02 mag threshold"

    # Verify every individual NIRCam band
    for fname in TARGET_FILTERS:
        delta = res["delta_mags"][fname]
        assert delta < 0.02, f"Band {fname} diverged by {delta} mag (expected < 0.02)"
        assert res["specsynth_mags"][fname] < 35.0, f"Band {fname} magnitude is unphysically faint"
        assert res["specsynth_fnu_ujy"][fname] > 0.0, f"Band {fname} microJansky flux is non-positive"


def test_one_galaxy_astrophysical_properties() -> None:
    """Verifies that target subhalo properties are within expected physical ranges."""
    res = validate_one_galaxy("tng100_subhalo_009873")

    assert 0.5 < res["redshift"] < 3.0, f"Unexpected redshift {res['redshift']}"
    assert 8.0 < res["log_mstar"] < 12.0, f"Unexpected stellar mass {res['log_mstar']}"
    assert 0.0 <= res["tau_diffuse"] <= 2.0, f"Unexpected diffuse dust {res['tau_diffuse']}"
    assert 0.0 <= res["tau_birth"] <= 4.0, f"Unexpected birth cloud dust {res['tau_birth']}"
