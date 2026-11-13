import os
import numpy as np
import pytest
from astropy.table import Table

pytestmark = pytest.mark.integration

from specsynth.catalog import (
    COLUMN_ALIASES,
    catalog_to_params_matrix,
    load_raw_table,
    resolve_catalog_columns,
)


def test_column_aliases_structure():
    assert "mass" in COLUMN_ALIASES
    assert "onset" in COLUMN_ALIASES
    assert "tau" in COLUMN_ALIASES
    assert "met" in COLUMN_ALIASES
    assert "tau_diffuse" in COLUMN_ALIASES
    assert "tau_birth" in COLUMN_ALIASES


def test_resolve_catalog_columns_auto_detection():
    raw = {
        "m_star": np.array([1e10, 1e11, 5e9], dtype=np.float32),
        "formation_time": np.array([8.0, 10.0, 4.0], dtype=np.float32),
        "tau_sfh": np.array([1.5, 2.5, 0.8], dtype=np.float32),
        "metallicity": np.array([0.02, 0.005, 0.04], dtype=np.float32),
        "Av": np.array([0.5, 1.2, 0.1], dtype=np.float32),
        "redshift": np.array([0.1, 0.5, 1.2], dtype=np.float32),
    }

    resolved = resolve_catalog_columns(raw)
    assert "mass" in resolved
    # Linear mass > 100 should be auto-converted to log10
    assert np.allclose(resolved["mass"], np.log10([1e10, 1e11, 5e9]))
    assert np.allclose(resolved["onset"], [8.0, 10.0, 4.0])
    assert np.allclose(resolved["tau"], [1.5, 2.5, 0.8])
    # Linear metallicity < 0.2 should be auto-converted to log10
    assert np.allclose(resolved["met"], np.log10([0.02, 0.005, 0.04]))
    # Av in magnitudes should be converted to optical depth tau_V = Av / 1.086
    expected_tau_d = np.array([0.5, 1.2, 0.1], dtype=np.float32) / 1.086
    assert np.allclose(resolved["tau_diffuse"], expected_tau_d)
    # tau_birth should default to 1.5 * tau_diffuse
    assert np.allclose(resolved["tau_birth"], 1.5 * expected_tau_d)
    assert np.allclose(resolved["redshift"], [0.1, 0.5, 1.2])


def test_resolve_catalog_columns_explicit_mapping():
    raw = {
        "custom_m": np.array([10.5, 11.2], dtype=np.float32),
        "custom_z": np.array([-1.7, -2.1], dtype=np.float32),
    }

    resolved = resolve_catalog_columns(
        raw,
        explicit_map={"mass": "custom_m", "met": "custom_z"},
    )
    assert np.allclose(resolved["mass"], [10.5, 11.2])
    assert np.allclose(resolved["met"], [-1.7, -2.1])
    # Defaults filled for missing columns
    assert np.allclose(resolved["onset"], [6.0, 6.0])
    assert np.allclose(resolved["tau"], [2.0, 2.0])


def test_resolve_catalog_missing_mass_raises():
    raw = {
        "onset": np.array([5.0], dtype=np.float32),
        "tau": np.array([2.0], dtype=np.float32),
    }
    with pytest.raises(ValueError, match="missing a stellar mass"):
        resolve_catalog_columns(raw)


def test_catalog_to_params_matrix():
    resolved = {
        "mass": np.array([10.0, 11.0], dtype=np.float32),
        "onset": np.array([5.0, 6.0], dtype=np.float32),
        "tau": np.array([2.0, 3.0], dtype=np.float32),
        "met": np.array([-1.5, -1.8], dtype=np.float32),
        "tau_diffuse": np.array([0.4, 0.6], dtype=np.float32),
        "tau_birth": np.array([0.8, 1.2], dtype=np.float32),
    }
    p = catalog_to_params_matrix(resolved)
    assert p.shape == (2, 6)
    assert p.dtype == np.float32
    assert np.allclose(p[0], [10.0, 5.0, 2.0, -1.5, 0.4, 0.8])


def test_load_raw_table_csv(tmp_path):
    csv_file = tmp_path / "galaxies.csv"
    tbl = Table({"mstar": [1e10, 2e10], "age": [3.0, 4.0], "av": [0.3, 0.5]})
    tbl.write(str(csv_file), format="ascii.csv")

    loaded = load_raw_table(csv_file)
    assert "mstar" in loaded
    assert len(loaded["mstar"]) == 2
    assert np.allclose(loaded["mstar"], [1e10, 2e10])


def test_load_raw_table_fits(tmp_path):
    fits_file = tmp_path / "galaxies.fits"
    tbl = Table({"mass": [10.2, 10.8], "z": [0.5, 1.0]})
    tbl.write(str(fits_file), format="fits", overwrite=True)

    loaded = load_raw_table(fits_file)
    assert "mass" in loaded
    assert "z" in loaded
    assert np.allclose(loaded["mass"], [10.2, 10.8])


def test_load_raw_table_hdf5(tmp_path):
    import h5py
    h5_file = tmp_path / "galaxies.h5"
    with h5py.File(str(h5_file), "w") as f:
        f.create_dataset("mstar", data=np.array([1e9, 5e10], dtype=np.float32))
        f.create_dataset("tau", data=np.array([1.2, 2.4], dtype=np.float32))

    loaded = load_raw_table(h5_file)
    assert "mstar" in loaded
    assert "tau" in loaded
    assert len(loaded["mstar"]) == 2


def test_load_raw_table_npz(tmp_path):
    npz_file = tmp_path / "galaxies.npz"
    np.savez(str(npz_file), mass=np.array([10.1, 10.9]), met=np.array([-1.6, -1.9]))

    loaded = load_raw_table(npz_file)
    assert "mass" in loaded
    assert "met" in loaded
    assert np.allclose(loaded["mass"], [10.1, 10.9])


def test_load_raw_table_npy_2d_and_structured(tmp_path):
    # 2D matrix (N, 6)
    npy_2d = tmp_path / "gal_2d.npy"
    mat = np.array([
        [10.0, 5.0, 1.5, -1.8, 0.3, 0.7],
        [11.0, 6.0, 2.0, -1.5, 0.4, 0.9],
    ], dtype=np.float32)
    np.save(str(npy_2d), mat)

    loaded_2d = load_raw_table(npy_2d)
    assert "mass" in loaded_2d
    assert "onset" in loaded_2d
    assert len(loaded_2d["mass"]) == 2

    # Structured array
    npy_struct = tmp_path / "gal_struct.npy"
    dt = np.dtype([("MSTAR", np.float32), ("REDSHIFT", np.float32)])
    s_arr = np.array([(1e10, 0.5), (2e10, 1.2)], dtype=dt)
    np.save(str(npy_struct), s_arr)

    loaded_s = load_raw_table(npy_struct)
    assert "mstar" in loaded_s
    assert "redshift" in loaded_s


def test_load_raw_table_tsv_and_invalid(tmp_path):
    tsv_file = tmp_path / "galaxies.tsv"
    tsv_file.write_text("m_star\tz\n1e10\t0.5\n", encoding="utf-8")
    loaded_tsv = load_raw_table(tsv_file)
    assert "m_star" in loaded_tsv

    bad_ext = tmp_path / "galaxies.unknown"
    bad_ext.write_text("random", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported catalog file extension"):
        load_raw_table(bad_ext)


def test_clean_catalog_base_mode_and_formats(tmp_path, monkeypatch):
    from specsynth.catalog import clean_catalog

    class MockZGroup(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.attrs = {}

    params_arr = np.array([
        [10.0, 5.0, 1.5, -1.8, 0.3, 0.7],
        [11.0, 6.0, 2.0, -1.5, 0.4, 0.9],
        [9.5, 3.0, 0.8, -2.0, 0.1, 0.3],
    ], dtype=np.float32)

    mock_group = MockZGroup({
        "params": params_arr,
        "tau_diffuse": np.array([0.3, 0.4, 0.1], dtype=np.float32),
        "tau_birth": np.array([0.7, 0.9, 0.3], dtype=np.float32),
        "redshift": np.array([0.5, 1.0, 1.5], dtype=np.float32),
    })

    monkeypatch.setattr("zarr.open_group", lambda *args, **kwargs: mock_group)

    # Clean catalog from base with quarantined index 1
    # Test FITS export
    fits_out = str(tmp_path / "clean.fits")
    res_fits = clean_catalog(
        base=str(tmp_path),
        anomalous_indices=[1],
        output_path=fits_out,
    )
    assert res_fits["valid_galaxies"] == 2
    assert res_fits["quarantined_count"] == 1
    assert os.path.exists(fits_out)

    # Test HDF5 export
    h5_out = str(tmp_path / "clean.h5")
    res_h5 = clean_catalog(
        base=str(tmp_path),
        anomalous_indices=[1],
        output_path=h5_out,
    )
    assert res_h5["valid_galaxies"] == 2
    assert os.path.exists(h5_out)

    # Test TSV export
    tsv_out = str(tmp_path / "clean.tsv")
    res_tsv = clean_catalog(
        base=str(tmp_path),
        anomalous_indices=[1],
        output_path=tsv_out,
    )
    assert res_tsv["valid_galaxies"] == 2
    assert os.path.exists(tsv_out)

    # Test Parquet export
    pq_out = str(tmp_path / "clean.parquet")
    res_pq = clean_catalog(
        base=str(tmp_path),
        anomalous_indices=[1],
        output_path=pq_out,
    )
    assert res_pq["valid_galaxies"] == 2


def test_import_catalog_with_mock_client(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    import dask.array as da
    from specsynth.catalog import import_catalog

    # Raw file
    csv_file = tmp_path / "catalog_input.csv"
    tbl = Table({
        "m_star": [1e10, 2e10],
        "z": [0.5, 1.2],
        "tau": [1.0, 2.0],
    })
    tbl.write(str(csv_file), format="ascii.csv")

    monkeypatch.setattr("specsynth.catalog.da.from_zarr", lambda s, component: da.from_array(np.array([1e7, 1e8])))
    mock_write_many = MagicMock()
    monkeypatch.setattr("specsynth.catalog.write_many", mock_write_many)

    mock_client = MagicMock()
    meta = import_catalog(
        catalog_path=csv_file,
        output_zarr="mock_out.zarr",
        ssp_store="mock_ssp.zarr",
        chunk_size=10,
        client=mock_client,
    )

    assert meta["n_galaxies"] == 2
    mock_write_many.assert_called_once()


def test_import_catalog_streaming(tmp_path, monkeypatch):
    import h5py
    import dask.array as da
    from unittest.mock import MagicMock
    from specsynth.catalog import import_catalog

    h5_path = tmp_path / "test_stream.h5"
    with h5py.File(str(h5_path), "w") as f:
        f.create_dataset("m_star", data=np.array([1e10, 2e10, 3e10, 4e10], dtype=np.float32))
        f.create_dataset("redshift", data=np.array([0.1, 0.5, 1.0, 1.5], dtype=np.float32))
        f.create_dataset("tau", data=np.array([1.0, 2.0, 1.5, 0.8], dtype=np.float32))

    monkeypatch.setattr("specsynth.catalog.da.from_zarr", lambda s, component: da.from_array(np.array([1e7, 1e8])))
    mock_write = MagicMock()
    monkeypatch.setattr("specsynth.catalog.write_many", mock_write)

    zarr_out = str(tmp_path / "stream_h5_out.zarr")
    meta = import_catalog(
        catalog_path=h5_path,
        output_zarr=zarr_out,
        ssp_store="mock_ssp.zarr",
        chunk_size=2,
        client=MagicMock(),
    )
    assert meta["n_galaxies"] == 4
    mock_write.assert_called_once()


def test_stream_csv_chunks(tmp_path):
    from specsynth.catalog import stream_csv_chunks

    csv_path = tmp_path / "test_stream.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("m_star,redshift,tau\n")
        for i in range(10):
            f.write(f"1e10,{i * 0.1},1.0\n")

    chunks = list(stream_csv_chunks(csv_path, chunk_size=4))
    assert len(chunks) == 3  # 4 + 4 + 2
    assert len(chunks[0]["m_star"]) == 4
    assert len(chunks[2]["m_star"]) == 2
    assert np.isclose(chunks[0]["redshift"][1], 0.1)





