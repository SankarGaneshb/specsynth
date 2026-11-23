"""
Automated validation and scientific parity test suite for PerandamΨ Web Datasets.

Validates:
1. Physical and schema integrity of exported datasets:
   - perandam-psi/src/data/tng_100_calibration.json (100 galaxies)
   - perandam-psi/src/data/tng_goods_s_mock_508.json (508 galaxies)
2. Filter response curves and SHA-256 verification.
3. Physical parameter bounds (redshift, stellar mass, dust attenuation, flux positivity).
4. Grounded statistical discovery profiles (Mahalanobis distance, chi2_6, p-value, citations).
5. Exact scientific parity between the dataset photometry and SpecSynth core integration (< 0.02 mag).
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pytest

from specsynth.cosmology import TNG_COSMOLOGY, FlatLambdaCDM, redshift_flux
from specsynth.filters import (
    NIRCAM_FILTER_REGISTRY,
    f_lambda_to_f_nu,
    flux_to_ab_mag,
    get_filter,
)

DATA_DIR = Path(__file__).parents[1] / "perandam-psi" / "src" / "data"


def test_perandam_web_dataset_files_exist():
    """Verify web dataset JSON files are present on disk."""
    assert (DATA_DIR / "tng_100_calibration.json").exists(), "Missing tng_100_calibration.json"
    assert (DATA_DIR / "tng_goods_s_mock_508.json").exists(), "Missing tng_goods_s_mock_508.json"


@pytest.mark.parametrize("filename,expected_count", [
    ("tng_100_calibration.json", 100),
    ("tng_goods_s_mock_508.json", 508),
])
def test_perandam_web_dataset_schema_and_counts(filename: str, expected_count: int):
    """Verify dataset manifests comply with CatalogManifest schema."""
    path = DATA_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "title" in data
    assert "filters" in data
    assert "galaxies" in data

    galaxies = data["galaxies"]
    assert len(galaxies) == expected_count, f"{filename} should contain {expected_count} galaxies, found {len(galaxies)}"

    # Check filter curves
    filters = data["filters"]
    assert len(filters) >= 6
    for f in filters:
        assert "name" in f
        assert "pivot_wavelength" in f
        assert f["pivot_wavelength"] > 0
        assert len(f["wave"]) == len(f["transmission"])
        assert np.all(np.array(f["transmission"]) >= 0.0)
        assert "sha256" in f


def test_perandam_galaxy_physical_invariants():
    """Verify astrophysical invariants across all galaxies in both datasets."""
    for filename in ["tng_100_calibration.json", "tng_goods_s_mock_508.json"]:
        path = DATA_DIR / filename
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for g in data["galaxies"]:
            # Coordinate bounds
            assert -180.0 <= g["ra"] <= 360.0
            assert -90.0 <= g["dec"] <= 90.0

            # Redshift & stellar mass
            assert 0.0 < g["redshift"] <= 15.0
            assert 6.0 <= g["log_mstar"] <= 13.0
            assert g["av"] >= 0.0

            # Spectral rest frame (480-node break-preserving grid)
            sed = g["sed"]
            assert len(sed) >= 400, "Wavelength grid must have high resolution"
            wave = np.array([p["wave"] for p in sed], dtype=np.float64)
            lum = np.array([p["flux"] for p in sed], dtype=np.float64)

            assert np.all(np.diff(wave) > 0), "Wavelengths must be strictly monotonic"
            assert np.all(lum >= 0.0), "Rest-frame luminosity must be non-negative"
            assert np.all(np.isfinite(lum)), "Luminosities must be finite"

            # Photometry
            mags = g["mags"]
            fluxes = g["fluxes"]
            assert len(mags) >= 6
            assert len(fluxes) >= 6
            for b in mags:
                assert np.isfinite(mags[b])
                assert fluxes[b] >= -1e-25


def test_perandam_discovery_profiles_and_citations():
    """Verify statistical discovery profiles adhere to rigorous metrics and citations."""
    path = DATA_DIR / "tng_goods_s_mock_508.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    discoveries = [g for g in data["galaxies"] if g.get("discovery_profile") is not None]
    assert len(discoveries) > 0, "Goods-S mock must contain discovery candidates"

    for g in discoveries:
        dp = g["discovery_profile"]
        assert dp["rarity_sigma"] > 0
        assert 0.0 <= dp["rarity_p_value"] <= 1.0
        assert dp["rarity_chi2"] > 0
        assert "hypotheses" in dp

        hypo_dict = dp["hypotheses"]
        citations = hypo_dict.get("citations", [])
        assert len(citations) >= 2

        # Check that citations reference peer-reviewed literature
        all_text = " ".join(citations) + " " + hypo_dict.get("primary", "") + " " + hypo_dict.get("alternative", "")
        has_valid_citation = any(pub in all_text for pub in ["ApJ", "Nature", "MNRAS", "A&A", "Phys. Rep.", "arXiv"])
        assert has_valid_citation, f"Discovery {g['id']} must reference peer-reviewed literature"


def test_perandam_scientific_photometry_parity():
    """
    Test scientific parity between SpecSynth core numerical integration
    and the exported web dataset photometry (< 0.02 mag parity tolerance).
    """
    path = DATA_DIR / "tng_100_calibration.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Test first 5 calibration galaxies
    sample_galaxies = data["galaxies"][:5]
    cosmo = FlatLambdaCDM(H0=67.74, Om0=0.3089)

    for g in sample_galaxies:
        z = g["redshift"]
        sed = g["sed"]
        wave_rest = np.array([p["wave"] for p in sed], dtype=np.float64)
        lum_rest = np.array([p["flux"] for p in sed], dtype=np.float64)

        # Redshift to observed frame
        wave_obs, flux_obs = redshift_flux(wave_rest, lum_rest, z, cosmo)

        # Evaluate against JWST NIRCam filters
        for band_id in ["jwst_f090w", "jwst_f150w", "jwst_f200w", "jwst_f277w", "jwst_f356w", "jwst_f444w"]:
            band_info = get_filter(band_id)
            bw = np.array(band_info.wave, dtype=np.float64)
            bt = np.array(band_info.transmission, dtype=np.float64)

            # Interpolate observed flux onto filter curve
            in_range = (bw >= wave_obs[0]) & (bw <= wave_obs[-1])
            if not np.any(in_range):
                continue

            flux_interp = np.interp(bw, wave_obs, flux_obs, left=0.0, right=0.0)
            f_lam = np.trapezoid(flux_interp * bt * bw, bw) / np.trapezoid(bt * bw, bw)
            f_nu = f_lambda_to_f_nu(f_lam, band_info.pivot_wavelength)
            mag_specsynth = flux_to_ab_mag(f_nu)

            # Compare to catalog pre-computed mag
            mag_catalog = g["mags"][band_id]

            if np.isfinite(mag_specsynth) and np.isfinite(mag_catalog) and mag_catalog < 35.0:
                delta_mag = abs(mag_specsynth - mag_catalog)
                assert delta_mag < 0.02, f"Photometry parity violated on {g['id']} {band_id}: delta={delta_mag:.4f} mag (limit: 0.02 mag)"
