import os
import numpy as np
import pytest
from astropy.table import Table

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
    assert np.allclose(resolved["tau_diffuse"], [0.5, 1.2, 0.1])
    # tau_birth should default to 1.5 * tau_diffuse
    assert np.allclose(resolved["tau_birth"], [0.75, 1.8, 0.15])
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
