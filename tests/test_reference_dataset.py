from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.integration


def test_reference_benchmark_catalog_structure():
    """Verify that the generated 100k canonical reference benchmark dataset conforms to all specifications."""
    data_dir = Path("benchmark_data/specsynth_reference_100k")
    if not data_dir.is_dir():
        pytest.skip("Benchmark dataset not present locally (run scripts/export_reference_dataset.py to generate)")

    parquet_path = data_dir / "specsynth_benchmark_100k.parquet"
    zarr_path = data_dir / "specsynth_benchmark_100k.zarr"
    card_path = data_dir / "dataset_card.json"
    checksum_path = data_dir / "SHA256SUMS.txt"

    assert parquet_path.is_file(), "specsynth_benchmark_100k.parquet must exist"
    assert zarr_path.is_dir(), "specsynth_benchmark_100k.zarr must exist"
    assert card_path.is_file(), "dataset_card.json must exist"
    assert checksum_path.is_file(), "SHA256SUMS.txt must exist"


def test_reference_parquet_content():
    """Verify Parquet schema, row counts, and physical bounds."""
    parquet_path = Path("benchmark_data/specsynth_reference_100k/specsynth_benchmark_100k.parquet")
    if not parquet_path.is_file():
        pytest.skip("Parquet benchmark dataset not present locally")

    import pyarrow.parquet as pq
    table = pq.read_table(parquet_path)

    assert table.num_rows == 100_000
    expected_cols = [
        "galaxy_id", "redshift", "log_mstar", "sfr", "av", "tau_diffuse", "tau_birth",
        "flux_cgs_jwst_f200w", "flux_ujy_jwst_f200w", "mag_ab_jwst_f200w",
        "flux_cgs_hst_f814w", "mag_ab_hst_f814w", "flux_cgs_sdss_r", "mag_ab_sdss_r",
        "sfh_matrix_60"
    ]
    for col in expected_cols:
        assert col in table.column_names, f"Expected column '{col}' missing from Parquet table"

    # Verify physical sanity
    redshift = table["redshift"].to_numpy()
    assert np.all(redshift >= 0.05) and np.all(redshift <= 4.0)

    mag_f200w = table["mag_ab_jwst_f200w"].to_numpy()
    assert np.all(np.isfinite(mag_f200w))
    # Typical galaxy AB magnitudes at z ~ 0.5 - 3
    assert np.median(mag_f200w) > 15.0 and np.median(mag_f200w) < 32.0


def test_reference_zarr_metadata():
    """Verify Zarr dataset attributes and metadata integrity."""
    zarr_path = Path("benchmark_data/specsynth_reference_100k/specsynth_benchmark_100k.zarr")
    if not zarr_path.is_dir():
        pytest.skip("Zarr benchmark dataset not present locally")

    # Read root group metadata directly (ensures cross-version and Windows async safety)
    root_json = zarr_path / "zarr.json"
    zgroup_json = zarr_path / ".zgroup"
    zattrs_json = zarr_path / ".zattrs"

    if root_json.is_file():
        with open(root_json, "r", encoding="utf-8") as f:
            root_meta = json.load(f)
        attrs = root_meta.get("attributes", {})
    elif zattrs_json.is_file():
        with open(zattrs_json, "r", encoding="utf-8") as f:
            attrs = json.load(f)
    else:
        import zarr
        root = zarr.open_group(str(zarr_path), mode="r")
        attrs = root.attrs

    assert attrs["n_galaxies"] == 100_000
    assert len(attrs["filters"]) == 16
    assert attrs["cosmology"]["H0"] == 67.4
    assert attrs["cosmology"]["Omega_m"] == 0.315

    # Check array shapes
    for col, expected_shape in [
        ("galaxy_id", [100_000]),
        ("redshift", [100_000]),
        ("sfh", [100_000, 60]),
        ("flux_ujy", [100_000, 16]),
        ("mag_ab", [100_000, 16]),
    ]:
        col_json = zarr_path / col / "zarr.json"
        col_zarray = zarr_path / col / ".zarray"
        if col_json.is_file():
            with open(col_json, "r", encoding="utf-8") as f:
                col_meta = json.load(f)
            assert col_meta["shape"] == expected_shape
        elif col_zarray.is_file():
            with open(col_zarray, "r", encoding="utf-8") as f:
                col_meta = json.load(f)
            assert col_meta["shape"] == expected_shape
