"""
Automated tests for Phase 2A cross-code astrophysical validation harness
(`scripts/cross_validate_sps.py`).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.astrophysics


def _load_cross_validate_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "cross_validate_sps.py"
    spec = importlib.util.spec_from_file_location("cross_validate_sps", script_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tng_catalog_mapping_physical_bounds():
    """Verify TNG-like catalog generation and physical parameter mapping."""
    mod = _load_cross_validate_module()
    cat = mod.generate_tng_like_subhalo_catalog(n_gal=120, seed=7)
    params, redshifts = mod.map_tng_catalog_to_specsynth_params(cat)

    assert params.shape == (120, 6)
    assert redshifts.shape == (120,)
    assert np.all(np.isfinite(params))
    assert np.all(params[:, 0] >= 8.0) and np.all(params[:, 0] <= 12.0)  # log10 M*
    assert np.all(params[:, 4] > 0.0) and np.all(params[:, 5] >= params[:, 4])  # tau_b >= tau_d


def test_cosmology_cross_validation_against_astropy():
    """Verify specsynth FlatLambdaCDM matches astropy.cosmology.FlatLambdaCDM (< 1e-4)."""
    mod = _load_cross_validate_module()
    res = mod.validate_cosmology_vs_astropy()
    assert res["status"] == "PASS"
    for cosmo_label in ("planck18", "concordance"):
        entry = res["cosmologies"][cosmo_label]
        assert entry["status"] == "PASS"
        assert entry["max_rel_err_comoving_distance"] < 1e-4
        assert entry["max_rel_err_luminosity_distance"] < 1e-4


def test_tng_population_photometry_accuracy_and_manifest():
    """Verify sub-millimag photometric agreement across JWST, HST, and SDSS bands."""
    mod = _load_cross_validate_module()
    manifest = mod.run_cross_validation(n_gal=100, z_snapshot=2.0, seed=42)

    assert manifest["overall_status"] == "PASS"
    phot = manifest["checks"]["tng_population_photometry_vs_float64"]
    assert phot["status"] == "PASS"
    assert phot["max_abs_delta_mag_all_bands"] < 1e-3
    for fset in ("jwst_nircam", "hst", "sdss"):
        assert phot["filter_sets"][fset]["status"] == "PASS"
        assert phot["filter_sets"][fset]["max_abs_delta_mag"] < 1e-3


def test_live_fsps_hook_if_installed():
    """Run live FSPS cross-validation when python-fsps is available; skip cleanly otherwise."""
    mod = _load_cross_validate_module()
    res = mod.validate_live_python_fsps()
    if res["status"] == "skipped_not_installed":
        pytest.skip(res["note"])
    assert res["status"] == "PASS"
    assert res["max_rel_spectral_error_vs_fsps"] < 1e-3
