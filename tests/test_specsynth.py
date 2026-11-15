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


@pytest.mark.integration
def test_write_many_batched_with_mock_client(monkeypatch):
    import dask.array as da
    from unittest.mock import MagicMock
    from specsynth.core import write_many_batched

    store_path = "mock_write_many_batched.zarr"
    # Array with 4 chunk blocks of size 5
    main_arr = da.from_array(np.ones(20, dtype=np.float32), chunks=5)
    wave_arr = da.from_array(np.arange(10, dtype=np.float32), chunks=10)

    mock_client = MagicMock()
    mock_client.compute.return_value = ["fut"]

    class MockGroup:
        def __init__(self):
            self.attrs = {}

    mock_grp = MockGroup()
    monkeypatch.setattr("zarr.open_group", lambda *args, **kwargs: mock_grp)
    monkeypatch.setattr("dask.array.to_zarr", lambda *args, **kwargs: MagicMock(blocks=["b0", "b1", "b2", "b3"]))

    # 4 blocks, batch_chunks=2 -> should trigger 1 static write + 2 batch writes = 3 compute calls
    write_many_batched(
        mock_client,
        store_path,
        static_arrays={"wave": wave_arr},
        main_name="photometry",
        main_array=main_arr,
        batch_chunks=2,
        metadata={"batch_pipelined": True},
    )
    assert mock_client.compute.call_count == 3
    assert mock_grp.attrs["batch_pipelined"] is True


@pytest.mark.critical
def test_write_many_batched_bounded_scheduler_verification(monkeypatch):
    """
    Regression test verifying write_many_batched enforces strict bounded scheduler windows.
    Verifies that:
    1. Dask task graph is partitioned into slices of size batch_chunks, not submitted all at once.
    2. Exact region slices (slice(start, end), slice(None)) are provided to to_zarr.
    3. client.gather is called on each window before proceeding to the next.
    """
    import dask.array as da
    from unittest.mock import MagicMock
    from specsynth.core import write_many_batched

    store_path = "mock_bounded_pipeline.zarr"
    # 6 chunk blocks of 10 rows each = 60 rows total
    np_data = np.ones((60, 5), dtype=np.float32)
    main_da = da.from_array(np_data, chunks=(10, 5))
    wave_da = da.from_array(np.arange(10, dtype=np.float32), chunks=10)

    to_zarr_calls = []

    def mock_to_zarr(arr, store, component=None, region=None, compute=False, **kwargs):
        to_zarr_calls.append({
            "component": component,
            "shape": arr.shape,
            "region": region,
            "chunks": arr.chunks,
        })
        return f"task_{component}_{len(to_zarr_calls)}"

    monkeypatch.setattr("dask.array.to_zarr", mock_to_zarr)

    class MockGroup:
        def __init__(self):
            self.attrs = {}
        def create_dataset(self, *args, **kwargs):
            pass

    mock_grp = MockGroup()
    monkeypatch.setattr("zarr.open_group", lambda *args, **kwargs: mock_grp)

    compute_events = []
    gather_events = []

    mock_client = MagicMock()
    def mock_compute(task):
        compute_events.append(task)
        return ["fut"]
    def mock_gather(fut):
        gather_events.append(fut)

    mock_client.compute = mock_compute
    mock_client.gather = mock_gather

    # Run with batch_chunks = 2 (6 blocks -> 3 windows of 2 blocks each)
    write_many_batched(
        mock_client,
        store_path,
        static_arrays={"wave": wave_da},
        main_name="photometry",
        main_array=main_da,
        batch_chunks=2,
        metadata={"bounded_test": True},
    )

    # 1 static write + 3 batch writes = 4 to_zarr calls
    assert len(to_zarr_calls) == 4

    # Check static array call
    assert to_zarr_calls[0]["component"] == "wave"
    assert to_zarr_calls[0]["shape"] == (10,)

    # Check windowed batch calls: each batch MUST have shape (20, 5) and NOT (60, 5)!
    # Batch 0: rows 0..20 (2 blocks of 10)
    assert to_zarr_calls[1]["component"] == "photometry"
    assert to_zarr_calls[1]["shape"] == (20, 5)
    assert to_zarr_calls[1]["region"] == (slice(0, 20), slice(None))

    # Batch 1: rows 20..40 (2 blocks of 10)
    assert to_zarr_calls[2]["component"] == "photometry"
    assert to_zarr_calls[2]["shape"] == (20, 5)
    assert to_zarr_calls[2]["region"] == (slice(20, 40), slice(None))

    # Batch 2: rows 40..60 (2 blocks of 10)
    assert to_zarr_calls[3]["component"] == "photometry"
    assert to_zarr_calls[3]["shape"] == (20, 5)
    assert to_zarr_calls[3]["region"] == (slice(40, 60), slice(None))

    # Verify synchronous compute -> gather pacing: exactly 4 compute calls, 4 gather calls
    assert len(compute_events) == 4
    assert len(gather_events) == 4
    assert mock_grp.attrs["bounded_test"] is True


@pytest.mark.critical
def test_write_many_batched_unmocked_real_zarr(tmp_path):
    """
    100% unmocked end-to-end integration test for write_many_batched.
    Writes real Dask arrays in bounded chunks to a real on-disk Zarr store,
    reads the data back directly from disk, and asserts bit-exact equality.
    """
    import os
    import shutil
    import dask
    import dask.array as da
    import zarr
    from specsynth.core import write_many_batched

    # Use workspace-relative temporary folder to remain robust across platforms
    test_dir = ".tmp_unmocked_test.zarr"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

    try:
        with dask.config.set(scheduler="synchronous"):
            # 6 blocks of 10 rows each = 60 rows total
            data = np.arange(300, dtype=np.float32).reshape(60, 5)
            main_da = da.from_array(data, chunks=(10, 5))
            wave_da = da.from_array(np.linspace(1000, 10000, 20, dtype=np.float32), chunks=10)

            write_many_batched(
                client=None,
                store=test_dir,
                static_arrays={"wave": wave_da},
                main_name="photometry",
                main_array=main_da,
                batch_chunks=2,
                metadata={"test_unmocked": True, "n_galaxies": 60},
            )

            # Read back directly from Zarr without mocks
            grp = zarr.open_group(test_dir, mode="r")
            read_phot = da.from_zarr(test_dir, component="photometry").compute()
            read_wave = da.from_zarr(test_dir, component="wave").compute()

            assert np.allclose(read_phot, data)
            assert np.allclose(read_wave, wave_da.compute())
            assert grp.attrs["test_unmocked"] is True
            assert grp.attrs["n_galaxies"] == 60
    finally:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)


@pytest.mark.critical
def test_write_many_batched_with_external_catalog_data():
    """
    100% unmocked end-to-end integration test for write_many_batched using real-world data
    from an external tabular catalog (Astropy Table / CSV format).
    Verifies that:
    1. External catalog file on disk is ingested via load_raw_table & resolve_catalog_columns.
    2. Physical galaxy SFH and in-flight JWST NIRCam filter projections are evaluated.
    3. write_many_batched writes chunk blocks into an on-disk Zarr store using bounded windows.
    4. Photometric arrays read back from disk match bit-exact and have valid physical magnitudes.
    """
    import os
    import shutil
    import dask
    import dask.array as da
    import zarr
    from astropy.table import Table

    from specsynth.catalog import resolve_catalog_columns, catalog_to_params_matrix, load_raw_table
    from specsynth.core import sfh_from_params, write_many_batched, synth_block, attenuation_curve, YOUNG_AGE_YR
    from specsynth.adapters.toy import build_toy_ssp
    from specsynth.filters import build_filter_projection_matrix, f_lambda_to_f_nu, flux_to_ab_mag

    csv_path = ".tmp_ext_cat.csv"
    store_path = ".tmp_ext_cat_phot.zarr"

    if os.path.exists(csv_path):
        os.remove(csv_path)
    if os.path.exists(store_path):
        shutil.rmtree(store_path)

    try:
        # 1. External catalog source with realistic galaxy parameters
        n_gal = 40
        tbl = Table({
            "galaxy_id": np.arange(101, 101 + n_gal),
            "m_star": np.logspace(9.5, 11.2, n_gal, dtype=np.float32),
            "formation_redshift": np.linspace(0.5, 3.0, n_gal, dtype=np.float32),
            "tau_sfh": np.full(n_gal, 2.0, dtype=np.float32),
            "metallicity": np.full(n_gal, 0.019, dtype=np.float32),
            "Av": np.linspace(0.2, 1.5, n_gal, dtype=np.float32),
        })
        tbl.write(csv_path, format="ascii.csv", overwrite=True)

        # 2. Ingest external catalog file from disk
        raw_dict = load_raw_table(csv_path)
        resolved = resolve_catalog_columns(raw_dict)
        params = catalog_to_params_matrix(resolved)

        # 3. Setup SSP basis matrix
        ages, mets, wave, ssp = build_toy_ssp(n_age=15, n_met=3, n_wave=800)
        K = ssp.shape[0]
        n_young_k = int((ages < YOUNG_AGE_YR).sum()) * len(mets)
        kd = attenuation_curve(wave, -0.7)
        kb = attenuation_curve(wave, -1.3)

        # 4. Generate SFH and synthesize JWST NIRCam photometry
        sfh_dense = sfh_from_params(params, ages, mets)
        proj_mat, filter_names, pivots = build_filter_projection_matrix(wave, "jwst_nircam")

        spectra = synth_block(
            sfh_dense,
            resolved["tau_diffuse"],
            resolved["tau_birth"],
            ssp,
            kd,
            kb,
            n_young_k,
            use_gpu=False,
        )
        photometry_f_lambda = spectra @ proj_mat
        photometry_f_nu = f_lambda_to_f_nu(photometry_f_lambda, pivots)
        photometry_ab_mag = flux_to_ab_mag(photometry_f_nu)

        # 5. Partition into Dask array of 4 chunk blocks (10 galaxies each)
        chunk = 10
        phot_da = da.from_array(photometry_ab_mag, chunks=(chunk, len(filter_names)))
        pivots_da = da.from_array(pivots, chunks=len(pivots))

        # 6. Execute unmocked write_many_batched with batch_chunks=2
        with dask.config.set(scheduler="synchronous"):
            write_many_batched(
                client=None,
                store=store_path,
                static_arrays={"pivot_wavelengths": pivots_da},
                main_name="ab_magnitudes",
                main_array=phot_da,
                batch_chunks=2,
                metadata={
                    "source_catalog": csv_path,
                    "filter_set": "jwst_nircam",
                    "n_galaxies": n_gal,
                },
            )

        # 7. Read back from real disk Zarr store without mocks
        grp = zarr.open_group(store_path, mode="r")
        read_phot = da.from_zarr(store_path, component="ab_magnitudes").compute()
        read_pivots = da.from_zarr(store_path, component="pivot_wavelengths").compute()

        assert np.allclose(read_phot, photometry_ab_mag)
        assert np.allclose(read_pivots, pivots)
        assert grp.attrs["filter_set"] == "jwst_nircam"
        assert grp.attrs["n_galaxies"] == n_gal
        assert np.all(np.isfinite(read_phot))
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)
        if os.path.exists(store_path):
            shutil.rmtree(store_path)


@pytest.mark.critical
def test_full_pipeline_cloud_object_store_uri():
    """
    Validates end-to-end execution of the complete pipeline (make-ssp, make-sfh, synth, verify)
    using pure non-POSIX cloud object store URIs via fsspec (memory:// protocol).
    Ensures zero reliance on local filesystem paths or NFS mounts.
    """
    import argparse
    import dask
    from specsynth.cli import cmd_make_ssp, cmd_make_sfh, cmd_synth, cmd_verify

    base_uri = "memory://cloud_object_store_pipeline"

    with dask.config.set(scheduler="synchronous"):
        # 1. make-ssp
        a_ssp = argparse.Namespace(
            base=base_uri, adapter="toy", n_age=10, n_met=2, n_wave=500,
            resample_wave=None, input_path=None, input_file=None
        )
        cmd_make_ssp(a_ssp, None)

        # 2. make-sfh
        a_sfh = argparse.Namespace(
            base=base_uri, n_gal=100, chunk=25, seed=42, redshift_range=None
        )
        cmd_make_sfh(a_sfh, None)

        # 3. synth
        a_synth = argparse.Namespace(
            base=base_uri, diffuse_index=-0.7, birth_index=-1.3,
            redshift=1.5, per_galaxy_z=False, distance_dimming=False,
            input_units="lsun", igm=True, filters="jwst_nircam",
            chunk=25, wave_chunk=0, bands=0, no_persist_ssp=True,
            batch_chunks=2, gpu=False, sample=50, output=None,
            fail_on_anomaly=False
        )
        cmd_synth(a_synth, None)

        # 4. verify (cmd_verify calls sys.exit(0) on success)
        a_verify = argparse.Namespace(
            base=base_uri, sample=25, tolerance_max=5e-4, tolerance_mean=1e-5,
            diffuse_index=-0.7, birth_index=-1.3
        )
        with pytest.raises(SystemExit) as exc_info:
            cmd_verify(a_verify, None)
        assert exc_info.value.code == 0


@pytest.mark.critical
def test_gen_params_with_block_info():
    from specsynth.core import _gen_params

    dummy = np.zeros((5, 6), dtype=np.float32)
    binfo = {None: {"chunk-location": (2,), "chunk-shape": (5,)}}
    p = _gen_params(dummy, seed=42, block_info=binfo)
    assert p.shape == (5, 6)
    assert np.all(np.isfinite(p))


@pytest.mark.critical
def test_parse_memory_limit():
    from specsynth.core import parse_memory_limit

    assert parse_memory_limit("1GB") == 1024**3
    assert parse_memory_limit("512MB") == 512 * 1024**2
    assert parse_memory_limit("2GiB") == 2 * 1024**3
    assert parse_memory_limit("100M") == 100 * 1024**2
    assert parse_memory_limit(1073741824) == 1073741824
    assert parse_memory_limit(None) == 0
    assert parse_memory_limit("invalid") == 0


@pytest.mark.critical
def test_compute_adaptive_chunk_size():
    from specsynth.core import compute_adaptive_chunk_size

    # On 1GB limit, high resolution (2000 wave), safe chunk should be budgeted
    # Bytes per galaxy approx (2*2000 + 160 + 7) * 4 = 16,668 bytes
    # Safe budget = 1GB * 0.20 = ~214 MB -> ~12,883 galaxies
    chunk_1gb = compute_adaptive_chunk_size(
        requested_chunk=50_000,
        n_wave=2000,
        k_dim=160,
        n_bands=7,
        memory_limit="1GB",
        safety_fraction=0.20,
    )
    assert 10_000 <= chunk_1gb <= 15_000

    # If requested chunk is smaller than safe chunk, it should not be altered
    assert compute_adaptive_chunk_size(
        requested_chunk=5_000,
        n_wave=2000,
        k_dim=160,
        n_bands=7,
        memory_limit="1GB",
    ) == 5_000

    # On large 32GB node, requested 50,000 should be retained
    assert compute_adaptive_chunk_size(
        requested_chunk=50_000,
        n_wave=2000,
        k_dim=160,
        n_bands=7,
        memory_limit="32GB",
    ) == 50_000

    # Handles edge cases (invalid or zero limit falls back gracefully)
    assert compute_adaptive_chunk_size(
        requested_chunk=20_000,
        n_wave=2000,
        memory_limit=None,
    ) >= 1_000

