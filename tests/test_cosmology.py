import numpy as np
import pytest

pytestmark = pytest.mark.astrophysics

from specsynth.cosmology import FlatLambdaCDM, redshift_flux


def test_cosmology_distances():
    cosmo = FlatLambdaCDM(H0=70.0, Om0=0.3)
    assert np.isclose(cosmo.E(0.0), 1.0)
    assert cosmo.comoving_distance(0.0) == 0.0
    assert cosmo.luminosity_distance(0.0) == 0.0

    # Test monotonic distance with redshift
    d_L_1 = cosmo.luminosity_distance(0.5)
    d_L_2 = cosmo.luminosity_distance(1.0)
    d_L_3 = cosmo.luminosity_distance(2.0)
    assert d_L_1 > 0
    assert d_L_2 > d_L_1
    assert d_L_3 > d_L_2

    # Standard benchmark check at z = 1.0 (approx ~ 6600-6800 Mpc for Planck)
    assert 6000.0 < d_L_2 < 7500.0


def test_redshift_flux():
    wave_rest = np.array([2000.0, 4000.0, 6000.0])
    flux_rest = np.array([10.0, 20.0, 15.0])
    z = 1.0

    wave_obs, flux_obs = redshift_flux(wave_rest, flux_rest, z=z, distance_dimming=False)
    # Observed wavelength must be shifted by (1 + z) = 2.0
    assert np.allclose(wave_obs, wave_rest * 2.0)
    # Bandpass compression dimming: 1 / (1 + z) = 0.5
    assert np.allclose(flux_obs, flux_rest * 0.5)

    # Test luminosity_distance_cm
    cosmo = FlatLambdaCDM(H0=70.0, Om0=0.3)
    d_cm = cosmo.luminosity_distance_cm(1.0)
    assert d_cm > 0
    assert d_cm == cosmo.luminosity_distance(1.0) * cosmo.Mpc_to_cm

    # Test redshift_flux with z=0 (identity)
    w0, f0 = redshift_flux(wave_rest, flux_rest, z=0.0)
    assert np.allclose(w0, wave_rest)
    assert np.allclose(f0, flux_rest)

    # Test redshift_flux with distance dimming True
    w_dim, f_dim = redshift_flux(wave_rest, flux_rest, z=1.0, distance_dimming=True)
    assert np.allclose(w_dim, wave_rest * 2.0)
    assert np.all(f_dim > 0)
    assert np.all(f_dim < flux_obs)


def test_cosmology_vectorized():
    cosmo = FlatLambdaCDM(H0=70.0, Om0=0.3)
    z_arr = np.array([0.0, 0.5, 1.0, 2.0])
    dc = cosmo.comoving_distance(z_arr)
    assert dc.shape == (4,)
    assert dc[0] == 0.0
    assert np.all(np.diff(dc) > 0)

    dl = cosmo.luminosity_distance(z_arr)
    assert dl.shape == (4,)
    assert dl[0] == 0.0
    assert np.all(dl[1:] > dc[1:])

    # Test vectorized redshift_flux with 2D batch of galaxies (N, W)
    batch_flux = np.ones((4, 50), dtype=np.float32)
    wave = np.linspace(2000, 8000, 50)
    w_res, f_batch = redshift_flux(wave, batch_flux, z=z_arr, distance_dimming=False)
    assert f_batch.shape == (4, 50)
    # Bandpass compression factor 1 / (1 + z)
    assert np.isclose(f_batch[0, 0], 1.0)
    assert np.isclose(f_batch[1, 0], 1.0 / 1.5)
    assert np.isclose(f_batch[2, 0], 0.5)


def test_three_galaxy_redshift_regression():
    """
    Critical regression test: 3 identical galaxies at z = 0.5, 1.0, 2.0.
    Verify relative flux ratios, wavelength dilation, and physical distance dimming.
    """
    from specsynth.cosmology import (
        DEFAULT_COSMOLOGY,
        L_SUN_ERG_S,
        apply_redshift_to_chunk,
        project_per_galaxy_photometry_chunk,
    )

    cosmo = DEFAULT_COSMOLOGY
    z_vals = np.array([0.5, 1.0, 2.0], dtype=np.float64)
    wave_rest = np.linspace(2000.0, 10000.0, 800)

    # 3 identical rest-frame spectra
    base_spec = np.sin(wave_rest / 1000.0) + 2.0  # strictly positive
    spec_block = np.tile(base_spec, (3, 1)).astype(np.float32)

    # 1. Bandpass compression only (distance_dimming = False)
    out_scaled = apply_redshift_to_chunk(
        spec_block, z_vals, wave_rest, apply_igm=False, distance_dimming=False
    )
    assert out_scaled.shape == (3, len(wave_rest))
    # Relative ratio between z=1.0 and z=0.5 must be exactly (1 + 0.5) / (1 + 1.0) = 1.5 / 2.0 = 0.75
    ratio_1_0 = out_scaled[1] / out_scaled[0]
    assert np.allclose(ratio_1_0, 0.75, rtol=1e-5)
    # Ratio between z=2.0 and z=0.5 must be exactly 1.5 / 3.0 = 0.5
    ratio_2_0 = out_scaled[2] / out_scaled[0]
    assert np.allclose(ratio_2_0, 0.5, rtol=1e-5)

    # 2. Physical cosmological distance dimming (1 / [4 * pi * D_L^2])
    out_dimmed = apply_redshift_to_chunk(
        spec_block, z_vals, wave_rest, apply_igm=False, distance_dimming=True, input_units="lsun"
    )
    assert out_dimmed.shape == (3, len(wave_rest))
    assert out_dimmed.dtype == np.float64

    # Theoretical dimming factors:
    # F(z) = L_rest * L_SUN / [ (1 + z) * 4 * pi * D_L(z)^2 ]
    dl_cm = cosmo.luminosity_distance_cm(z_vals)
    expected_dim = (1.0 / (1.0 + z_vals)) / (4.0 * np.pi * dl_cm**2) * L_SUN_ERG_S
    for i in range(3):
        assert np.allclose(out_dimmed[i], base_spec * expected_dim[i], rtol=1e-6)

    # Monotonic physical dimming: higher redshift must be strictly fainter
    assert np.all(out_dimmed[0] > out_dimmed[1])
    assert np.all(out_dimmed[1] > out_dimmed[2])

    # 3. Test project_per_galaxy_photometry_chunk
    flt_wave = np.linspace(3000.0, 9000.0, 500)
    flt_trans = np.exp(-(((flt_wave - 6000.0) / 1000.0) ** 4))
    norm = np.trapezoid(flt_trans * flt_wave, flt_wave)
    filter_data = [("test_band", flt_wave, flt_trans, norm)]

    phot = project_per_galaxy_photometry_chunk(
        spec_block, z_vals, wave_rest, filter_data, apply_igm=False, distance_dimming=True, input_units="lsun"
    )
    assert phot.shape == (3, 1)
    assert phot[0, 0] > phot[1, 0] > phot[2, 0] > 0.0


def test_cosmology_flux_units():
    """Verify input_units='lsun' vs 'cgs' consistency in redshift_flux."""
    from specsynth.cosmology import L_SUN_ERG_S, redshift_flux

    wave = np.linspace(3000, 7000, 100)
    flux = np.ones_like(wave)
    z = 1.0

    _, f_lsun = redshift_flux(wave, flux, z=z, distance_dimming=True, input_units="lsun")
    _, f_cgs = redshift_flux(wave, flux, z=z, distance_dimming=True, input_units="cgs")

    # Ratio between lsun and cgs must be exactly L_SUN_ERG_S
    ratio = f_lsun / f_cgs
    assert np.allclose(ratio, L_SUN_ERG_S, rtol=1e-6)


