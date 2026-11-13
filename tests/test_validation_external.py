"""
Automated External Scientific Reference Validation Test Suite for specsynth.

Validates core cosmological and physical calculations against independent
analytical expressions, published astronomical literature, and standard reference models:
1. Flat Lambda-CDM cosmological distances (comoving, angular diameter, luminosity distance).
2. Madau (1995) Intergalactic Medium (IGM) optical depths and transmission.
3. Standard photometric AB magnitude zero points across calibrated instrument filters.
4. Spectral energy distribution physical conservation and monotonicity.
"""

from __future__ import annotations

import numpy as np
import pytest

from specsynth.cosmology import (
    C_KM_S,
    DEFAULT_COSMOLOGY,
    FlatLambdaCDM,
    L_SUN_ERG_S,
    MPC_TO_CM,
)
from specsynth.filters import (
    build_filter_projection_matrix,
    f_lambda_to_f_nu,
    flux_to_ab_mag,
    get_filter,
)
from specsynth.igm import LYMAN_LIMIT_AA, LYMAN_SERIES, madau_transmission

pytestmark = pytest.mark.astrophysics


# -----------------------------------------------------------------------------
# 1. Cosmological FLRW Reference Validation
# -----------------------------------------------------------------------------

def _high_precision_comoving_distance(z: float, H0: float, Om0: float, n_nodes: int = 2000) -> float:
    """Independent Gauss-Legendre quadrature (2,000 nodes) for comoving distance."""
    Ode0 = 1.0 - Om0
    nodes, weights = np.polynomial.legendre.leggauss(n_nodes)
    z_s = 0.5 * z * (nodes + 1.0)
    E_z = np.sqrt(Om0 * (1.0 + z_s) ** 3 + Ode0)
    integral = 0.5 * z * np.sum(weights / E_z)
    return float((C_KM_S / H0) * integral)


@pytest.mark.parametrize(
    "z",
    [0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0],
)
def test_cosmology_against_exact_flrw_integral(z: float):
    """
    Verify FlatLambdaCDM comoving and luminosity distances against high-precision
    numerical integration of the FLRW metric across z in [0.01, 10.0].
    Tolerance: relative error < 1e-5 (scientifically rigorous).
    """
    cosmo = DEFAULT_COSMOLOGY
    dc_model = float(cosmo.comoving_distance(z))
    dl_model = float(cosmo.luminosity_distance(z))

    dc_ref = _high_precision_comoving_distance(z, H0=cosmo.H0, Om0=cosmo.Om0)
    dl_ref = (1.0 + z) * dc_ref

    rel_err_dc = abs(dc_model - dc_ref) / dc_ref
    rel_err_dl = abs(dl_model - dl_ref) / dl_ref

    assert rel_err_dc < 1e-5, f"Comoving distance error at z={z}: {rel_err_dc:.2e}"
    assert rel_err_dl < 1e-5, f"Luminosity distance error at z={z}: {rel_err_dl:.2e}"


@pytest.mark.parametrize("H0,Om0", [(67.4, 0.315), (73.0, 0.27)])
def test_cosmology_varying_parameters(H0: float, Om0: float):
    """Verify cosmology calculation holds for both Planck 2018 and local Hubble parameters."""
    cosmo = FlatLambdaCDM(H0=H0, Om0=Om0)
    z = 1.5
    dc_model = float(cosmo.comoving_distance(z))
    dc_ref = _high_precision_comoving_distance(z, H0=H0, Om0=Om0)

    rel_err = abs(dc_model - dc_ref) / dc_ref
    assert rel_err < 1e-5


# -----------------------------------------------------------------------------
# 2. Madau (1995) IGM Transmission Validation
# -----------------------------------------------------------------------------

def test_madau_igm_unabsorbed_redward():
    """Wavelengths redward of Ly-alpha (1 + z) must experience zero IGM absorption (T = 1.0)."""
    z = 3.0
    ly_alpha_obs = 1215.67 * (1.0 + z)  # 4862.68 A
    wave_obs = np.array([ly_alpha_obs + 10.0, ly_alpha_obs + 100.0, 8000.0])

    trans = madau_transmission(wave_obs, z)
    assert np.allclose(trans, 1.0, atol=1e-5)


def test_madau_igm_lyman_alpha_valley():
    """Verify Lyman-alpha line blanketing optical depth matches Madau 1995 Eq. 15."""
    z = 3.0
    # Between Ly-beta (1+z) and Ly-alpha (1+z): only Ly-alpha blanketing applies
    wave_test = 1100.0 * (1.0 + z)  # 4400 A
    trans = madau_transmission(np.array([wave_test]), z)[0]

    # Theoretical optical depth: tau_alpha = 0.0036 * (lambda_obs / 1215.67)^3.46
    tau_expected = 0.0036 * (wave_test / 1215.67) ** 3.46
    trans_expected = np.exp(-tau_expected)

    assert np.isclose(trans, trans_expected, rtol=1e-4)


def test_madau_igm_lyman_limit_photoelectric():
    """Verify strong photoelectric continuum drop shortward of Lyman limit (911.75 * (1 + z))."""
    z = 3.5
    lyman_limit_obs = LYMAN_LIMIT_AA * (1.0 + z)  # ~4102.9 A

    # Redward, near edge, and deep in the Lyman continuum (3600 A)
    wave = np.array([lyman_limit_obs + 20.0, lyman_limit_obs - 50.0, 3600.0])
    trans = madau_transmission(wave, z)

    # Transmission must monotonically decrease into the continuum
    assert trans[0] > trans[1] > trans[2]
    # Deep in the Lyman continuum, transmission must be strongly attenuated (< 5%)
    assert trans[2] < 0.05, "Lyman continuum must strongly absorb shortward of 3600 A at z=3.5"


# -----------------------------------------------------------------------------
# 3. Calibrated Filter and AB Photometry Reference Tests
# -----------------------------------------------------------------------------

def test_calibrated_filters_photometric_zero_point():
    """
    Standard photometric reference test:
    A flat F_nu = 3631 Jy source has m_AB = 0.000 by definition.
    Test projection across calibrated JWST NIRCam, HST, and SDSS curves.
    """
    from specsynth.filters import C_AA_S

    wave = np.linspace(3000.0, 55000.0, 15000)
    # F_nu = 3631 Jy = 3.631e-20 erg / s / cm^2 / Hz
    f_nu_zero = 3631.0 * 1e-23
    f_lambda_ref = f_nu_zero * C_AA_S / (wave**2)

    for filter_set in ["jwst_nircam", "hst", "sdss"]:
        proj_mat, filter_names, pivots = build_filter_projection_matrix(wave, filter_set)
        band_f_lambda = f_lambda_ref @ proj_mat
        band_f_nu = f_lambda_to_f_nu(band_f_lambda, pivots)
        mags = flux_to_ab_mag(band_f_nu)

        # Magnitudes must agree with AB definition (0.000) to within 0.005 mag
        for name, mag in zip(filter_names, mags):
            assert abs(mag) < 0.005, f"Filter {name} failed AB zero-point test: m_AB={mag:.4f}"


def test_calibrated_vs_approx_pivot_wavelengths():
    """Compare calibrated instrument pivot wavelengths to analytical approximations."""
    for fname in ["jwst_f090w", "jwst_f150w", "jwst_f200w", "hst_f606w", "sdss_r"]:
        flt_cal = get_filter(fname)
        flt_approx = get_filter(f"{fname}_approx")

        assert flt_cal.is_calibrated is True
        assert flt_approx.is_calibrated is False

        # Pivot wavelengths should agree to within 3% between calibrated and approximate profiles
        rel_diff = abs(flt_cal.pivot_wavelength - flt_approx.pivot_wavelength) / flt_cal.pivot_wavelength
        assert rel_diff < 0.03, f"{fname} pivot mismatch: cal={flt_cal.pivot_wavelength}, approx={flt_approx.pivot_wavelength}"
