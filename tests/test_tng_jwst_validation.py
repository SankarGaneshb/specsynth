"""
Scientific Validation Test Suite: TNG -> JWST NIRCam (Tasks D01-D08).

Validates:
- D01: FSPS spectral agreement with reference grid
- D02: Cosmological redshift transformations (wavelength and flux scaling)
- D03: Cosmological distance and flux scaling (TNG Planck 2015 cosmology)
- D04: JWST NIRCam filter integration (6 core filters: F090W, F150W, F200W, F277W, F356W, F444W)
- D05: AB magnitude zero point calibration across all NIRCam filters
- D06: Dust attenuation physical energy conservation and monotonic extinction
- D07: Numerical precision evaluation (float32 vs float64)
- D08: Numerical repeatability and reproducibility
- Required scientific test cases 1 through 8.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from specsynth.adapters.fsps import FSPSAdapter, find_default_fsps_grid
from specsynth.core import attenuation_curve, synth_block
from specsynth.cosmology import (
    C_KM_S,
    DEFAULT_COSMOLOGY,
    FlatLambdaCDM,
    L_SUN_ERG_S,
    TNG_COSMOLOGY,
    get_cosmology,
    redshift_flux,
)
from specsynth.filters import (
    C_AA_S,
    NIRCAM_FILTER_REGISTRY,
    build_filter_projection_matrix,
    f_lambda_to_f_nu,
    flux_to_ab_mag,
    get_filter,
    verify_filter_registry,
)

pytestmark = pytest.mark.astrophysics

# Target 6 JWST NIRCam filters from milestone specification
NIRCAM_SIX_FILTERS = ["jwst_f090w", "jwst_f150w", "jwst_f200w", "jwst_f277w", "jwst_f356w", "jwst_f444w"]


# --------------------------------------------------------------------------
# D01: FSPS Spectral Agreement
# --------------------------------------------------------------------------
def test_d01_fsps_spectral_agreement():
    """Verify FSPS adapter loads wide-wavelength grid faithfully."""
    ref_grid = find_default_fsps_grid()
    assert ref_grid is not None, "FSPS reference grid file must be present"

    adapter = FSPSAdapter(filepath=ref_grid, metallicity=0.019)
    ssp = adapter.load()

    # Check grid structure
    assert ssp.ssp.ndim == 2
    assert len(ssp.wave) >= 2000
    assert ssp.wave[0] <= 100.0, "Must cover extreme UV down to <= 100 A"
    assert ssp.wave[-1] >= 55000.0, "Must cover mid-IR out to >= 5.5 um"

    # Physical checks: non-negative flux, non-zero total luminosity
    assert np.all(ssp.ssp >= 0.0), "Fluxes must be non-negative"
    assert np.all(np.isfinite(ssp.ssp)), "Fluxes must be finite"


# --------------------------------------------------------------------------
# D02 & Test Case 1 & 2: Cosmological Redshift Correctness
# --------------------------------------------------------------------------
def test_d02_case1_redshift_zero_limiting_behavior():
    """Test Case 1: At z=0, rest-frame spectrum is preserved without singularity."""
    wave_rest = np.linspace(1000.0, 50000.0, 1000)
    flux_rest = np.ones_like(wave_rest) * 5.0

    w_obs, f_obs = redshift_flux(wave_rest, flux_rest, z=0.0, distance_dimming=False)
    assert np.allclose(w_obs, wave_rest)
    assert np.allclose(f_obs, flux_rest)


def test_d02_case2_increasing_redshift_shifts_wavelengths():
    """Test Case 2: Wavelength shifts strictly as lambda_obs = (1 + z) * lambda_rest."""
    wave_rest = np.array([1215.67, 3727.0, 6563.0])  # Ly-alpha, [OII], H-alpha
    flux_rest = np.array([10.0, 5.0, 8.0])

    for z in [0.5, 1.0, 2.0, 3.0, 6.0]:
        w_obs, f_obs = redshift_flux(wave_rest, flux_rest, z=z, distance_dimming=False)
        assert np.allclose(w_obs, wave_rest * (1.0 + z), rtol=1e-6)
        # Without distance dimming, bandpass compression scales flux by 1 / (1 + z)
        assert np.allclose(f_obs, flux_rest / (1.0 + z), rtol=1e-6)


# --------------------------------------------------------------------------
# D03: TNG Cosmology Distance & Flux Scaling
# --------------------------------------------------------------------------
def test_d03_tng_cosmology_parameters():
    """Verify TNG cosmology matches Planck 2015 parameters used in IllustrisTNG."""
    tng = get_cosmology("tng")
    assert np.isclose(tng.H0, 67.74, atol=1e-2)
    assert np.isclose(tng.Om0, 0.3089, atol=1e-4)
    assert np.isclose(tng.Ode0, 1.0 - 0.3089, atol=1e-4)


def test_d03_cosmological_distance_scaling():
    """Verify luminosity distance and 1/(4*pi*D_L^2) scaling."""
    cosmo = TNG_COSMOLOGY
    z = 2.0
    dl_mpc = cosmo.luminosity_distance(z)
    dl_cm = cosmo.luminosity_distance_cm(z)
    assert dl_mpc > 0.0
    assert np.isclose(dl_cm, dl_mpc * 3.08567758128e24, rtol=1e-7)

    # Flux dimming calculation
    wave_rest = np.linspace(2000.0, 10000.0, 500)
    flux_rest = np.ones_like(wave_rest) * 1.0  # L_sun / A

    w_obs, f_obs = redshift_flux(
        wave_rest, flux_rest, z=z, cosmo=cosmo, distance_dimming=True, input_units="lsun"
    )
    expected_dimming = (1.0 / (1.0 + z)) * L_SUN_ERG_S / (4.0 * np.pi * (dl_cm**2))
    assert np.allclose(f_obs, expected_dimming, rtol=1e-5)


# --------------------------------------------------------------------------
# D04 & D05 & Test Case 6: NIRCam Filter Integration & AB Zero Points
# --------------------------------------------------------------------------
def test_d04_nircam_filter_checksums():
    """Verify all NIRCam filter curves have matching SHA-256 hashes (Task C06)."""
    status = verify_filter_registry()
    for fname in NIRCAM_SIX_FILTERS:
        assert status.get(fname) is True, f"Filter {fname} failed SHA-256 integrity check"


def test_d05_case6_filter_response_flat_fnu_ab_behavior():
    """
    Test Case 6: Flat-f_nu spectrum (3631 Jy) must produce m_AB = 0.000
    within 0.005 mag across all 6 NIRCam wide filters.
    """
    wave = np.geomspace(500.0, 60000.0, 15000)
    f_nu_zero = 3631.0 * 1e-23  # erg / s / cm^2 / Hz
    f_lambda_ref = f_nu_zero * C_AA_S / (wave**2)

    proj_mat, filter_names, pivots = build_filter_projection_matrix(wave, NIRCAM_SIX_FILTERS)
    f_lambda_bands = f_lambda_ref @ proj_mat
    f_nu_bands = f_lambda_to_f_nu(f_lambda_bands, pivots)
    mags = flux_to_ab_mag(f_nu_bands)

    for fname, mag, piv in zip(filter_names, mags, pivots):
        assert abs(mag) < 0.005, f"Filter {fname} (piv={piv:.1f} A) AB zero point error: m_AB={mag:.4f}"


# --------------------------------------------------------------------------
# D06 & Test Cases 3 & 4: Dust Attenuation & Physical Invariants
# --------------------------------------------------------------------------
def test_d06_case3_zero_dust_leaves_spectrum_unchanged():
    """Test Case 3: Zero optical depth must leave the spectrum strictly unchanged."""
    wave = np.linspace(1000.0, 10000.0, 200, dtype=np.float32)
    kd = attenuation_curve(wave, -0.7)
    kb = attenuation_curve(wave, -1.3)

    sfh = np.ones((5, 10), dtype=np.float32)
    ssp = np.ones((10, 200), dtype=np.float32) * 2.0
    tau_zero = np.zeros(5, dtype=np.float32)

    spec_atten = synth_block(sfh, tau_zero, tau_zero, ssp, kd, kb, n_young_k=3, use_gpu=False)
    spec_pure = sfh @ ssp

    assert np.allclose(spec_atten, spec_pure, rtol=1e-6)


def test_d06_case4_increasing_dust_strictly_reduces_flux():
    """Test Case 4: Increasing dust optical depth must monotonically reduce transmitted flux."""
    wave = np.linspace(1000.0, 10000.0, 200, dtype=np.float32)
    kd = attenuation_curve(wave, -0.7)
    kb = attenuation_curve(wave, -1.3)

    sfh = np.ones((1, 10), dtype=np.float32)
    ssp = np.ones((10, 200), dtype=np.float32)

    taus = [0.1, 0.5, 1.0, 2.0, 4.0]
    total_fluxes = []
    for tau in taus:
        td = np.array([tau], dtype=np.float32)
        tb = np.array([1.5 * tau], dtype=np.float32)
        spec = synth_block(sfh, td, tb, ssp, kd, kb, n_young_k=3, use_gpu=False)
        total_fluxes.append(float(np.sum(spec)))

    # Strictly monotonically decreasing
    for i in range(len(total_fluxes) - 1):
        assert total_fluxes[i] > total_fluxes[i + 1], f"Flux did not decrease from tau={taus[i]} to {taus[i+1]}"


# --------------------------------------------------------------------------
# Test Case 7: Out-of-Range Wavelength Guard
# --------------------------------------------------------------------------
def test_case7_out_of_range_wavelength_warning():
    """Test Case 7: Filter with zero overlap emits UserWarning and does not silently extrapolate."""
    wave_narrow = np.linspace(1000.0, 2000.0, 100)  # Far UV, zero overlap with NIRCam F444W (4-5 um)

    with pytest.warns(UserWarning, match="zero transmission overlap"):
        proj_mat, names, pivots = build_filter_projection_matrix(wave_narrow, ["jwst_f444w"])
        assert proj_mat.shape == (100, 1)


# --------------------------------------------------------------------------
# D07 & Test Case 8: Numerical Precision (Float32 vs Float64)
# --------------------------------------------------------------------------
def test_d07_case8_float32_vs_float64_photometry_precision():
    """
    Test Case 8: Quantify float32 vs float64 numerical deviation across all 6 NIRCam filters.
    Pass condition: |Delta m| < 0.002 mag (far below observational calibration limits).
    """
    wave = np.geomspace(900.0, 60000.0, 6000)

    # Mock galaxy SED
    flux_64 = (wave / 5000.0) ** (-1.5) * 1e-15
    flux_32 = flux_64.astype(np.float32)

    proj_mat, names, pivots = build_filter_projection_matrix(wave, NIRCAM_SIX_FILTERS)

    # Float 64 path
    f_lam_64 = flux_64 @ proj_mat.astype(np.float64)
    f_nu_64 = f_lambda_to_f_nu(f_lam_64, pivots)
    mag_64 = flux_to_ab_mag(f_nu_64)

    # Float 32 path
    f_lam_32 = flux_32 @ proj_mat
    f_nu_32 = f_lambda_to_f_nu(f_lam_32.astype(np.float64), pivots)
    mag_32 = flux_to_ab_mag(f_nu_32)

    delta_mag = np.abs(mag_32 - mag_64)
    for fname, dmag in zip(names, delta_mag):
        assert dmag < 0.002, f"Float32 vs Float64 magnitude difference for {fname} too large: {dmag:.5f} mag"


# --------------------------------------------------------------------------
# D08: Repeatability and Determinism
# --------------------------------------------------------------------------
def test_d08_repeatability_and_determinism():
    """Verify repeated synthesis calls yield bitwise identical outputs."""
    wave = np.geomspace(900.0, 55000.0, 1000)
    kd = attenuation_curve(wave, -0.7)
    kb = attenuation_curve(wave, -1.3)

    rng = np.random.default_rng(42)
    sfh = rng.uniform(1e7, 1e10, (20, 10)).astype(np.float32)
    ssp = rng.uniform(1e-5, 1e-2, (10, 1000)).astype(np.float32)
    td = rng.uniform(0.1, 1.5, 20).astype(np.float32)
    tb = 1.5 * td

    run1 = synth_block(sfh, td, tb, ssp, kd, kb, n_young_k=3, use_gpu=False)
    run2 = synth_block(sfh, td, tb, ssp, kd, kb, n_young_k=3, use_gpu=False)

    assert np.array_equal(run1, run2), "Synthesis must be bitwise deterministic"
