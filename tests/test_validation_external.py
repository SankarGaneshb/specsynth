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


# -----------------------------------------------------------------------------
# 4. External Astronomical Standards & Physical Conservation
# -----------------------------------------------------------------------------

def test_physical_constants_against_astropy():
    """
    Verify core cosmological physical constants match CODATA/Astropy definitions:
    1. Speed of light (c) in km/s.
    2. Solar luminosity (L_sun) in erg/s.
    3. Megaparsec to centimeter conversion (Mpc -> cm).
    """
    import astropy.constants as const
    import astropy.units as u

    c_astropy = const.c.to(u.km / u.s).value
    lsun_astropy = const.L_sun.to(u.erg / u.s).value
    mpc_astropy = (1.0 * u.Mpc).to(u.cm).value

    assert np.isclose(C_KM_S, c_astropy, rtol=1e-6)
    assert np.isclose(L_SUN_ERG_S, lsun_astropy, rtol=1e-4)
    assert np.isclose(MPC_TO_CM, mpc_astropy, rtol=1e-6)


def test_ab_magnitude_zero_point_against_astropy_flux_density():
    """
    Cross-validate AB magnitude zero point directly with Astropy Unit definition:
    3631 Jy converted to erg/s/cm^2/Hz must yield m_AB = 0.0000 mag (< 1e-4 mag precision).
    """
    import astropy.units as u

    f_nu_3631 = (3631.0 * u.Jy).to(u.erg / u.s / u.cm**2 / u.Hz).value
    mag = flux_to_ab_mag(f_nu_3631)
    assert abs(mag) < 1e-4, f"AB zero point mismatch: {mag:.6f} mag"


def test_dust_attenuation_non_amplification_invariant():
    """
    Physical law: Dust attenuation in the UV/optical/NIR can only absorb and scatter stellar photons,
    never amplify or create them (absorption non-amplification invariant).
    Integrated flux of dust-attenuated spectra must be strictly <= intrinsic unattenuated flux:
        integral(F_attenuated d_lambda) <= integral(F_intrinsic d_lambda)

    Scientific Note on Dust Energy Balance:
    Full dust energy balance requires equating absorbed stellar UV/optical luminosity with emitted
    thermal dust luminosity in the mid- and far-infrared (e.g. L_dust = integral(F_int - F_att) d_lambda).
    Because Specsynth models stellar population synthesis and forward-models UV-to-NIR photometry
    (without synthesizing far-IR dust thermal re-emission), full dust energy balance is explicitly
    NOT implemented. This test verifies the physical absorption non-amplification invariant.
    """
    from specsynth.core import attenuation_curve, synth_block

    wave = np.linspace(1000.0, 10000.0, 500, dtype=np.float32)
    kd = attenuation_curve(wave, -0.7)
    kb = attenuation_curve(wave, -1.3)

    sfh = np.random.uniform(1e7, 1e10, (10, 15)).astype(np.float32)
    ssp = np.random.uniform(1e-5, 1e-3, (15, 500)).astype(np.float32)
    tau_d = np.random.uniform(0.1, 2.5, 10).astype(np.float32)
    tau_b = 1.5 * tau_d

    spec_atten = synth_block(sfh, tau_d, tau_b, ssp, kd, kb, n_young_k=4, use_gpu=False)
    spec_intrinsic = synth_block(
        sfh, np.zeros_like(tau_d), np.zeros_like(tau_b), ssp, kd, kb, n_young_k=4, use_gpu=False
    )

    trapz_fn = getattr(np, "trapezoid", None)
    if trapz_fn is not None:
        int_atten = trapz_fn(spec_atten, wave, axis=1)
        int_intrinsic = trapz_fn(spec_intrinsic, wave, axis=1)
    else:
        # Standard trapezoidal numerical integration
        dw = np.diff(wave)
        int_atten = np.sum(0.5 * (spec_atten[:, 1:] + spec_atten[:, :-1]) * dw, axis=1)
        int_intrinsic = np.sum(0.5 * (spec_intrinsic[:, 1:] + spec_intrinsic[:, :-1]) * dw, axis=1)

    assert np.all(int_atten <= int_intrinsic + 1e-6)
    # With non-zero optical depth, attenuated flux must be strictly less than intrinsic
    assert np.all(int_atten < int_intrinsic)


def test_dust_power_law_scaling_limits():
    """
    Verify Charlot & Fall (2000) / Calzetti dust curve boundary conditions:
    1. At lambda = 5500 A (V-band), optical depth scale k(lambda) = 1.000.
    2. At UV wavelengths (1500 A), attenuation is strongly enhanced (k ~ 2.48).
    3. At near-IR wavelengths (22,000 A), attenuation is strongly diminished (k ~ 0.38).
    """
    from specsynth.core import attenuation_curve

    wave_test = np.array([1500.0, 5500.0, 22000.0], dtype=np.float32)
    kd = attenuation_curve(wave_test, -0.7)

    assert np.isclose(kd[1], 1.0, atol=1e-5), "V-band (5500 A) dust scale must be 1.000"
    assert np.isclose(kd[0], (1500.0 / 5500.0) ** -0.7, rtol=1e-4)
    assert np.isclose(kd[2], (22000.0 / 5500.0) ** -0.7, rtol=1e-4)
    assert kd[0] > kd[1] > kd[2], "Dust extinction must decrease monotonically with wavelength"


# -----------------------------------------------------------------------------
# 5. Direct Astropy FLRW and SFH Mass Conservation Parity (Milestone P1 / GitHub Milestone #2)
# -----------------------------------------------------------------------------

def test_astropy_flrw_cosmology_direct_parity():
    """
    Directly verify Specsynth FlatLambdaCDM against Astropy's native FlatLambdaCDM.
    Tests comoving, luminosity, and angular diameter distances, plus lookback time and cosmic age,
    across a documented fine redshift grid z in [0.0, 10.0] for Planck 2018 and WMAP9.
    Tolerance: relative error < 1e-5 (scientifically rigorous).
    Requires scipy for Astropy's hypergeometric elliptic integration.
    """
    pytest.importorskip("scipy.special")
    from astropy.cosmology import FlatLambdaCDM as AstropyFlatLambdaCDM
    from specsynth.cosmology import FlatLambdaCDM

    test_models = [
        ("Planck 2015/2018", 67.74, 0.3089),
        ("WMAP9", 69.3, 0.286),
    ]
    test_redshifts = [0.0, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 7.0, 10.0]

    for model_name, H0, Om0 in test_models:
        spec_cosmo = FlatLambdaCDM(H0=H0, Om0=Om0)
        astro_cosmo = AstropyFlatLambdaCDM(H0=H0, Om0=Om0)

        for z in test_redshifts:
            if z == 0.0:
                assert spec_cosmo.comoving_distance(0.0) == 0.0
                assert spec_cosmo.luminosity_distance(0.0) == 0.0
                assert spec_cosmo.angular_diameter_distance(0.0) == 0.0
                assert spec_cosmo.lookback_time_gyr(0.0) == 0.0
                # Age at z=0 matches Astropy
                age_spec = float(spec_cosmo.cosmic_time_gyr(0.0))
                age_astro = float(astro_cosmo.age(0.0).value)
                assert abs(age_spec - age_astro) / age_astro < 1e-5
                continue

            # Comoving distance
            d_c_spec = float(spec_cosmo.comoving_distance(z))
            d_c_astro = float(astro_cosmo.comoving_distance(z).value)
            rel_err_dc = abs(d_c_spec - d_c_astro) / d_c_astro
            assert rel_err_dc < 1e-5, f"[{model_name}] Comoving distance error at z={z}: {rel_err_dc:.2e}"

            # Luminosity distance
            d_l_spec = float(spec_cosmo.luminosity_distance(z))
            d_l_astro = float(astro_cosmo.luminosity_distance(z).value)
            rel_err_dl = abs(d_l_spec - d_l_astro) / d_l_astro
            assert rel_err_dl < 1e-5, f"[{model_name}] Luminosity distance error at z={z}: {rel_err_dl:.2e}"

            # Angular diameter distance
            d_a_spec = float(spec_cosmo.angular_diameter_distance(z))
            d_a_astro = float(astro_cosmo.angular_diameter_distance(z).value)
            rel_err_da = abs(d_a_spec - d_a_astro) / d_a_astro
            assert rel_err_da < 1e-5, f"[{model_name}] Angular diameter distance error at z={z}: {rel_err_da:.2e}"

            # Lookback time
            t_lb_spec = float(spec_cosmo.lookback_time_gyr(z))
            t_lb_astro = float(astro_cosmo.lookback_time(z).value)
            assert abs(t_lb_spec - t_lb_astro) / t_lb_astro < 1e-5, f"[{model_name}] Lookback time error at z={z}"

            # Cosmic age
            t_age_spec = float(spec_cosmo.cosmic_time_gyr(z))
            t_age_astro = float(astro_cosmo.age(z).value)
            assert abs(t_age_spec - t_age_astro) / t_age_astro < 1e-5, f"[{model_name}] Cosmic age error at z={z}"


def test_cosmology_quadrature_convergence():
    """
    Verify numerical convergence of Gauss-Legendre quadrature in comoving distance calculation.
    Compares quadrature orders n = [20, 50, 100, 200, 500] at z = 2.0.
    """
    from specsynth.cosmology import DEFAULT_COSMOLOGY

    cosmo = DEFAULT_COSMOLOGY
    z = 2.0
    orders = [20, 50, 100, 200, 500]
    distances = [float(cosmo.comoving_distance(z, n_steps=n)) for n in orders]

    ref_d = distances[-1]  # n=500 high-order reference
    for n, d in zip(orders[:-1], distances[:-1]):
        rel_diff = abs(d - ref_d) / ref_d
        if n >= 50:
            assert rel_diff < 1e-5, f"Quadrature order n={n} failed convergence tolerance: rel_diff={rel_diff:.2e}"
        if n >= 100:
            assert rel_diff < 1e-6, f"Production order n={n} failed precision tolerance: rel_diff={rel_diff:.2e}"


def test_cosmology_edge_cases_and_exceptions():
    """
    Test edge cases and fail-closed exception handling in FlatLambdaCDM:
    1. z=0 returns exact zero distance and lookback time.
    2. Negative z raises ValueError.
    3. Non-positive H0 raises ValueError.
    4. Om0 outside (0, 1] raises ValueError.
    5. High-redshift (z=20) evaluates without overflow or NaNs.
    """
    from specsynth.cosmology import FlatLambdaCDM

    cosmo = FlatLambdaCDM(H0=70.0, Om0=0.3)

    # z = 0 boundary
    assert cosmo.comoving_distance(0.0) == 0.0
    assert cosmo.luminosity_distance(0.0) == 0.0
    assert cosmo.angular_diameter_distance(0.0) == 0.0
    assert cosmo.lookback_time_gyr(0.0) == 0.0

    # Negative z must fail closed
    with pytest.raises(ValueError, match="non-negative"):
        cosmo.comoving_distance(-0.5)
    with pytest.raises(ValueError, match="non-negative"):
        cosmo.cosmic_time_gyr(-1.0)
    with pytest.raises(ValueError, match="non-negative"):
        cosmo.lookback_time_gyr(-0.01)

    # Invalid cosmology parameters must fail closed
    with pytest.raises(ValueError, match="positive"):
        FlatLambdaCDM(H0=0.0, Om0=0.3)
    with pytest.raises(ValueError, match="positive"):
        FlatLambdaCDM(H0=-70.0, Om0=0.3)
    with pytest.raises(ValueError, match=r"\(0, 1\]"):
        FlatLambdaCDM(H0=70.0, Om0=0.0)
    with pytest.raises(ValueError, match=r"\(0, 1\]"):
        FlatLambdaCDM(H0=70.0, Om0=1.5)

    # High-z stability
    dc_20 = cosmo.comoving_distance(20.0)
    t_20 = cosmo.cosmic_time_gyr(20.0)
    assert np.isfinite(dc_20) and dc_20 > cosmo.comoving_distance(10.0)
    assert np.isfinite(t_20) and 0.0 < t_20 < cosmo.cosmic_time_gyr(10.0)


def test_sfh_delayed_tau_exact_mass_conservation():
    """
    Verify that compute_delayed_tau_sfh exactly conserves formed stellar mass:
    sum_{age, met} SFH_matrix[gal, :] == M_formed[gal] within relative tolerance 1e-5.
    """
    from specsynth.sfh import compute_delayed_tau_sfh

    ages = np.logspace(6.0, np.log10(1.35e10), 50)
    mets = np.array([0.004, 0.008, 0.019, 0.03])
    masses = np.array([1e9, 5e10, 2.5e11], dtype=np.float64)
    t_onsets = np.array([10.0, 12.0, 8.5], dtype=np.float64)
    taus = np.array([1.5, 3.0, 0.8], dtype=np.float64)
    log_zs = np.array([-2.1, -1.8, -1.5], dtype=np.float64)

    sfh = compute_delayed_tau_sfh(
        mass_formed_msun=masses,
        t_onset_gyr=t_onsets,
        tau_gyr=taus,
        ages_yr=ages,
        mets_z=mets,
        log_z_centre=log_zs,
    )

    summed_masses = np.sum(sfh, axis=1)
    for expected, actual in zip(masses, summed_masses):
        rel_diff = abs(actual - expected) / expected
        assert rel_diff < 1e-5, f"Mass conservation failed: expected {expected:.2e}, got {actual:.2e}"


def test_fsps_multiz_export_and_import(tmp_path):
    """
    Verify exporting and header-driven importing of multi-metallicity FSPS grids.
    """
    from specsynth.adapters.fsps import FSPSAdapter, parse_fsps_spec_file

    ages = np.array([1e7, 1e8, 1e9])
    mets = np.array([0.004, 0.019])
    wave = np.linspace(2000, 8000, 40)
    fluxes = np.ones((len(ages) * len(mets), len(wave)), dtype=np.float32)

    export_path = tmp_path / "test_multiz.spec"
    FSPSAdapter.export_spec_file(
        filepath=export_path,
        ages_yr=ages,
        mets_z=mets,
        wave_angstrom=wave,
        fluxes_2d=fluxes,
        is_genuine_fsps=True,
        col_order="age_major",
    )

    assert export_path.exists()
    adapter = FSPSAdapter(filepath=export_path)
    ssp_data = adapter.load()

    assert ssp_data.metadata["is_genuine_fsps"] is True
    assert len(ssp_data.ages) == 3
    assert len(ssp_data.mets) == 2
    assert len(ssp_data.wave) == 40
    assert ssp_data.ssp.shape == (6, 40)

