import numpy as np
import pytest

from specsynth.igm import LYMAN_LIMIT_AA, madau_transmission


def test_madau_transmission_z0():
    wave = np.linspace(800, 5000, 100)
    trans = madau_transmission(wave, z=0.0)
    assert np.all(trans == 1.0)


def test_madau_transmission_high_z():
    z = 3.5
    wave_rest = np.linspace(600, 2000, 200)
    wave_obs = wave_rest * (1.0 + z)
    trans = madau_transmission(wave_obs, z=z)

    # Transmission must be bounded in [0, 1]
    assert np.all((trans >= 0.0) & (trans <= 1.0))

    # Wavelengths shortward of Lyman limit (912 A rest-frame) are absorbed
    lyman_limit_obs = LYMAN_LIMIT_AA * (1.0 + z)
    below_lyman = wave_obs < lyman_limit_obs
    assert np.all(trans[below_lyman] < 0.5)

    # Deep in the Lyman continuum (rest-frame < 800 A), absorption is severe (< 5% transmission)
    deep_continuum = wave_rest < 800.0
    assert np.all(trans[deep_continuum] < 0.05)

    # Continuum transmission decreases towards shorter wavelengths
    assert trans[0] < trans[np.where(below_lyman)[0][-1]]

    # Wavelengths longward of Ly-alpha (1216 A rest-frame) should have high transmission
    above_ly_alpha = wave_obs > (1216.0 * (1.0 + z))
    assert np.all(trans[above_ly_alpha] == 1.0)
