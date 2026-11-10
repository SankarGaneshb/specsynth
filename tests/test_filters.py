import numpy as np
import pytest

from specsynth.filters import (
    FILTER_SETS,
    STANDARD_FILTER_SPECS,
    FilterCurve,
    build_filter_projection_matrix,
    f_lambda_to_f_nu,
    flux_to_ab_mag,
    get_filter,
    resolve_filter_names,
)


def test_filter_curve_properties():
    wave = np.linspace(4000, 6000, 200)
    # Top-hat filter between 4500 and 5500
    trans = ((wave >= 4500) & (wave <= 5500)).astype(float)
    flt = FilterCurve(name="test_band", wave=wave, transmission=trans)

    assert 4950 < flt.effective_wavelength < 5050
    assert 4950 < flt.pivot_wavelength < 5050

    # Resample
    new_wave = np.linspace(4000, 6000, 100)
    res = flt.resample(new_wave)
    assert res.shape == (100,)
    assert np.all(res >= 0)


def test_standard_filters_and_sets():
    # Test individual filter retrieval
    jwst_f200w = get_filter("jwst_f200w")
    assert "jwst_f200w" in jwst_f200w.name
    assert 19000 < jwst_f200w.pivot_wavelength < 21000

    sdss_r = get_filter("sdss_r")
    assert 6000 < sdss_r.pivot_wavelength < 6500

    # Test resolving filter set names
    resolved = resolve_filter_names("jwst_nircam")
    assert len(resolved) == len(FILTER_SETS["jwst_nircam"])
    assert "jwst_f200w" in resolved

    resolved_combo = resolve_filter_names("hst,sdss_r")
    assert "hst_f606w" in resolved_combo
    assert "sdss_r" in resolved_combo


def test_filter_projection_matrix():
    wave = np.linspace(3000, 10000, 500)
    filter_names = ["sdss_g", "sdss_r", "sdss_i"]

    matrix, names, pivots = build_filter_projection_matrix(wave, filter_names)
    assert matrix.shape == (500, 3)
    assert names == filter_names
    assert len(pivots) == 3

    # Flat spectrum test: S(lam) = 1.0 -> projected band flux should be ~ 1.0
    flat_spec = np.ones((1, 500), dtype=np.float32)
    phot = flat_spec @ matrix
    assert np.allclose(phot, 1.0, atol=1e-3)


def test_ab_magnitude_conversion():
    # 3631 Jansky = 3.631e-20 erg/s/cm^2/Hz corresponds to m_AB = 0.0
    f_nu_zero = 3.631e-20
    mag_zero = flux_to_ab_mag(np.array([f_nu_zero]))
    assert np.isclose(mag_zero[0], 0.0, atol=1e-2)

    # 10x fainter = +2.5 magnitudes
    mag_faint = flux_to_ab_mag(np.array([f_nu_zero / 10.0]))
    assert np.isclose(mag_faint[0], 2.5, atol=1e-2)
