import numpy as np
import pytest

from specsynth import (
    YOUNG_AGE_YR,
    _gen_params,
    attenuation_curve,
    band_matrix,
    build_toy_ssp,
    planck,
    sfh_from_params,
    synth_block,
    url,
)


@pytest.mark.integration
def test_url_formatting():
    assert url("/data/run1", "ssp.zarr") == "/data/run1/ssp.zarr"
    assert url("/data/run1/", "ssp.zarr") == "/data/run1/ssp.zarr"
    assert url("s3://bucket/run1/", "ssp.zarr") == "s3://bucket/run1/ssp.zarr"


@pytest.mark.critical
def test_planck():
    wave = np.linspace(1000, 10000, 50)
    flux = planck(wave, 6000.0)
    assert flux.shape == (50,)
    assert np.all(flux > 0)
    assert np.all(np.isfinite(flux))


@pytest.mark.critical
def test_build_toy_ssp():
    n_age, n_met, n_wave = 10, 3, 100
    ages, mets, wave, ssp = build_toy_ssp(n_age, n_met, n_wave)
    assert len(ages) == n_age
    assert len(mets) == n_met
    assert len(wave) == n_wave
    assert ssp.shape == (n_age * n_met, n_wave)
    assert np.all(np.isfinite(ssp))
    assert np.all(ssp >= 0)


@pytest.mark.astrophysics
def test_attenuation_curve():
    wave = np.array([2750.0, 5500.0, 11000.0], dtype=np.float32)
    k = attenuation_curve(wave, index=-1.0)
    assert np.isclose(k[1], 1.0)
    assert np.isclose(k[0], 2.0)
    assert np.isclose(k[2], 0.5)


@pytest.mark.astrophysics
def test_band_matrix():
    wave = np.logspace(np.log10(1000.0), np.log10(10000.0), 200)
    n_bands = 5
    bm = band_matrix(wave, n_bands)
    assert bm.shape == (200, n_bands)
    # Each filter band integrates to 1 across wavelength
    sums = bm.sum(axis=0)
    assert np.allclose(sums, 1.0, atol=1e-5)


@pytest.mark.critical
def test_gen_params_reproducibility():
    dummy = np.zeros((10, 6), dtype=np.float32)
    p1 = _gen_params(dummy, seed=42)
    p2 = _gen_params(dummy, seed=42)
    p3 = _gen_params(dummy, seed=99)
    assert np.allclose(p1, p2)
    assert not np.allclose(p1, p3)


@pytest.mark.critical
def test_sfh_and_synth_block():
    n_age, n_met, n_wave = 8, 3, 50
    ages, mets, wave, ssp = build_toy_ssp(n_age, n_met, n_wave)
    ny = int((ages < YOUNG_AGE_YR).sum()) * len(mets)

    n_gal = 5
    dummy = np.zeros((n_gal, 6), dtype=np.float32)
    params = _gen_params(dummy, seed=123)
    sfh = sfh_from_params(params, ages, mets)
    assert sfh.shape == (n_gal, n_age * n_met)

    kd = attenuation_curve(wave, -0.7)
    kb = attenuation_curve(wave, -1.3)
    spec = synth_block(
        sfh=sfh,
        tau_d=params[:, 4],
        tau_b=params[:, 5],
        ssp=ssp,
        k_d=kd,
        k_b=kb,
        n_young_k=ny,
    )
    assert spec.shape == (n_gal, n_wave)
    assert np.all(np.isfinite(spec))
    assert np.all(spec >= 0)


@pytest.mark.critical
def test_wave_chunking_contract():
    # Verify column-partitioned wavelength contractions
    n_gal, K, W = 10, 8, 40
    ny = 3
    sfh = np.ones((n_gal, K), dtype=np.float32)
    ssp = np.ones((K, W), dtype=np.float32)
    td = np.zeros(n_gal, dtype=np.float32)
    tb = np.zeros(n_gal, dtype=np.float32)
    kd = np.ones(W, dtype=np.float32)
    kb = np.ones(W, dtype=np.float32)

    # Full wavelength evaluation
    full_spec = synth_block(sfh, td, tb, ssp, kd, kb, ny)

    # Split into 2 wavelength chunks of 20 each
    chunk1_spec = synth_block(sfh, td, tb, ssp[:, :20], kd[:20], kb[:20], ny)
    chunk2_spec = synth_block(sfh, td, tb, ssp[:, 20:], kd[20:], kb[20:], ny)
    combined = np.hstack([chunk1_spec, chunk2_spec])

    assert np.allclose(full_spec, combined)


@pytest.mark.critical
def test_small_and_read_small(monkeypatch):
    import dask.array as da
    from specsynth.core import small, read_small

    arr = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    darr = small(arr)
    assert isinstance(darr, da.Array)
    assert darr.shape == (4,)

    mock_grp = {"test_comp": arr}
    monkeypatch.setattr("zarr.open_group", lambda *args, **kwargs: mock_grp)

    read_back = read_small("mock_store.zarr", "test_comp")
    assert np.allclose(arr, read_back)


@pytest.mark.integration
def test_write_many_with_mock_client(monkeypatch):
    import dask.array as da
    from unittest.mock import MagicMock
    from specsynth.core import write_many

    store_path = "mock_write_many.zarr"
    a1 = da.from_array(np.ones(10, dtype=np.float32), chunks=5)
    a2 = da.from_array(np.zeros(10, dtype=np.float32), chunks=5)

    mock_client = MagicMock()
    mock_client.compute.return_value = ["fut1", "fut2"]

    class MockGroup:
        def __init__(self):
            self.attrs = {}

    mock_grp = MockGroup()
    monkeypatch.setattr("zarr.open_group", lambda *args, **kwargs: mock_grp)
    monkeypatch.setattr("dask.array.to_zarr", lambda *args, **kwargs: "delayed_task")

    write_many(
        mock_client,
        store_path,
        {"a1": a1, "a2": a2},
        metadata={"created_by": "test", "version": "1.0"},
    )
    mock_client.compute.assert_called_once()
    mock_client.gather.assert_called_once_with(["fut1", "fut2"])
    assert mock_grp.attrs["created_by"] == "test"


@pytest.mark.critical
def test_gen_params_with_block_info():
    from specsynth.core import _gen_params

    dummy = np.zeros((5, 6), dtype=np.float32)
    binfo = {None: {"chunk-location": (2,), "chunk-shape": (5,)}}
    p = _gen_params(dummy, seed=42, block_info=binfo)
    assert p.shape == (5, 6)
    assert np.all(np.isfinite(p))
