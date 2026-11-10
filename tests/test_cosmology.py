import numpy as np
import pytest

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
