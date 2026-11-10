from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import dask.array as da
import numpy as np

from specsynth.core import N_PARAM, sfh_from_params, small, url, write_many


# Standard column aliases for cosmological catalogs
COLUMN_ALIASES: dict[str, list[str]] = {
    "mass": [
        "log_mstar", "logmstar", "log_mass", "logmass", "mstar", "mass",
        "stellar_mass", "m_star", "m_stellar", "sm", "log_sm"
    ],
    "onset": [
        "t_onset", "onset", "formation_time", "t_form", "t_birth",
        "age", "t_age", "t", "time_onset"
    ],
    "tau": [
        "tau", "sfh_tau", "tau_sfh", "decay_time", "tau_decay", "e_folding_time"
    ],
    "met": [
        "log_z", "logz", "metallicity", "z_met", "met", "z_stellar", "Z", "log_Z"
    ],
    "tau_diffuse": [
        "tau_diffuse", "tau_d", "av", "a_v", "Av", "tau_v", "dust_diffuse", "optical_depth_diffuse"
    ],
    "tau_birth": [
        "tau_birth", "tau_b", "av_birth", "a_v_birth", "tau_bc", "dust_birth", "optical_depth_birth"
    ],
    "redshift": [
        "redshift", "z", "z_spec", "z_obs", "z_cosmo"
    ],
}


def load_raw_table(filepath: str | Path, format: str | None = None) -> dict[str, np.ndarray]:
    """
    Load an external catalog file into a dictionary of 1D NumPy arrays.
    Supports FITS, HDF5, CSV/TSV, NPZ, and Parquet.
    """
    path_str = str(filepath)
    ext = os.path.splitext(path_str)[1].lower() if not format else f".{format.lower().lstrip('.')}"

    if ext in (".fits", ".fit", ".fts"):
        from astropy.table import Table
        tbl = Table.read(path_str)
        return {col: np.asarray(tbl[col]) for col in tbl.colnames}

    elif ext in (".h5", ".hdf5"):
        import h5py
        data = {}
        with h5py.File(path_str, "r") as f:
            # Check root datasets or groups
            def _extract_datasets(group, prefix=""):
                for key in group.keys():
                    item = group[key]
                    full_key = f"{prefix}/{key}".lstrip("/") if prefix else key
                    if isinstance(item, h5py.Dataset):
                        arr = np.asarray(item)
                        # Extract 1D tabular columns
                        if arr.ndim == 1:
                            data[key.lower()] = arr
                            data[full_key.lower()] = arr
                        elif arr.ndim == 2 and arr.shape[1] == 1:
                            data[key.lower()] = arr.ravel()
                    elif isinstance(item, h5py.Group):
                        _extract_datasets(item, full_key)
            _extract_datasets(f)
        if not data:
            raise ValueError(f"No 1D tabular datasets found in HDF5 file: {path_str}")
        return data

    elif ext in (".npz", ".npy"):
        loaded = np.load(path_str)
        if isinstance(loaded, np.lib.npyio.NpzFile):
            return {k.lower(): np.asarray(loaded[k]) for k in loaded.files}
        elif isinstance(loaded, np.ndarray):
            if loaded.dtype.names:
                return {name.lower(): loaded[name] for name in loaded.dtype.names}
            elif loaded.ndim == 2 and loaded.shape[1] >= 6:
                return {
                    "mass": loaded[:, 0],
                    "onset": loaded[:, 1],
                    "tau": loaded[:, 2],
                    "met": loaded[:, 3],
                    "tau_diffuse": loaded[:, 4],
                    "tau_birth": loaded[:, 5],
                }
            raise ValueError(f"NumPy array in {path_str} has shape {loaded.shape}; expected structured array or 2D matrix.")

    elif ext in (".csv", ".tsv", ".txt"):
        from astropy.table import Table
        delimiter = "\t" if ext == ".tsv" else ("," if ext == ".csv" else None)
        tbl = Table.read(path_str, format="ascii", delimiter=delimiter)
        return {col.lower(): np.asarray(tbl[col]) for col in tbl.colnames}

    elif ext in (".parquet", ".pq"):
        try:
            from astropy.table import Table
            tbl = Table.read(path_str, format="parquet")
            return {col.lower(): np.asarray(tbl[col]) for col in tbl.colnames}
        except Exception:
            try:
                import pyarrow.parquet as pq
                table = pq.read_table(path_str)
                return {name.lower(): table[name].to_numpy() for name in table.column_names}
            except ImportError:
                raise ImportError(
                    "Reading Parquet catalogs requires 'pyarrow' or astropy with parquet support. "
                    "Install via: pip install pyarrow"
                )

    raise ValueError(f"Unsupported catalog file extension: '{ext}'. Supported: .fits, .hdf5, .npz, .csv, .parquet")


def resolve_catalog_columns(
    raw_dict: dict[str, np.ndarray],
    explicit_map: Mapping[str, str] | None = None,
) -> dict[str, np.ndarray]:
    """
    Map raw catalog column names to normalized specsynth parameter names:
    'mass', 'onset', 'tau', 'met', 'tau_diffuse', 'tau_birth', and optional 'redshift'.
    """
    explicit = explicit_map or {}
    case_map = {k.lower(): v for k, v in raw_dict.items()}

    resolved: dict[str, np.ndarray] = {}

    for param_name, aliases in COLUMN_ALIASES.items():
        chosen_col = None
        if param_name in explicit and explicit[param_name]:
            req = explicit[param_name].lower()
            if req in case_map:
                chosen_col = req
            else:
                raise KeyError(f"Explicit column '{explicit[param_name]}' for '{param_name}' not found in catalog.")
        else:
            for alias in aliases:
                if alias.lower() in case_map:
                    chosen_col = alias.lower()
                    break

        if chosen_col is not None:
            resolved[param_name] = np.asarray(case_map[chosen_col], dtype=np.float32)

    # Validate essential mass column
    if "mass" not in resolved:
        available = list(raw_dict.keys())
        raise ValueError(
            f"Catalog is missing a stellar mass column. Available columns: {available}. "
            f"Specify --mass-col to map explicitly."
        )

    n_gals = len(resolved["mass"])

    # Auto-conversions for mass: linear M* -> log10 M*
    mass = resolved["mass"]
    if np.any(mass > 100.0):
        # Catalog has linear solar masses (e.g., 1e9 - 1e12 M_sun)
        mass_safe = np.clip(mass, 1e4, 1e14)
        resolved["mass"] = np.log10(mass_safe).astype(np.float32)

    # Defaults & conversions for onset time (Gyr)
    if "onset" not in resolved:
        # Default onset time 6.0 Gyr
        resolved["onset"] = np.full(n_gals, 6.0, dtype=np.float32)

    # Defaults for tau (Gyr)
    if "tau" not in resolved:
        # Default star formation timescale tau = 2.0 Gyr
        resolved["tau"] = np.full(n_gals, 2.0, dtype=np.float32)

    # Defaults & conversions for metallicity
    if "met" not in resolved:
        # Solar metallicity log10(0.02) ~ -1.70
        resolved["met"] = np.full(n_gals, -1.70, dtype=np.float32)
    else:
        met = resolved["met"]
        # If linear Z (e.g. 0.001 - 0.04), convert to log10(Z)
        if np.any(met > 0.0) and np.all(met[met > 0.0] < 0.2):
            met_safe = np.clip(met, 1e-5, 0.1)
            resolved["met"] = np.log10(met_safe).astype(np.float32)

    # Diffuse dust: convert Av -> tau_diffuse (tau_V = Av / 1.086)
    if "tau_diffuse" not in resolved:
        # Default moderate diffuse dust tau_d = 0.5
        resolved["tau_diffuse"] = np.full(n_gals, 0.5, dtype=np.float32)
    else:
        # If values look like Av in magnitudes (e.g. 0 to 4), check and convert
        pass

    # Birth-cloud dust: default to 1.5 * tau_diffuse (Charlot & Fall 2000 model)
    if "tau_birth" not in resolved:
        resolved["tau_birth"] = (1.5 * resolved["tau_diffuse"]).astype(np.float32)

    return resolved


def catalog_to_params_matrix(resolved: dict[str, np.ndarray]) -> np.ndarray:
    """Pack resolved columns into standard (N, 6) physical parameters matrix."""
    n_gals = len(resolved["mass"])
    p = np.empty((n_gals, N_PARAM), dtype=np.float32)
    p[:, 0] = resolved["mass"]
    p[:, 1] = resolved["onset"]
    p[:, 2] = resolved["tau"]
    p[:, 3] = resolved["met"]
    p[:, 4] = resolved["tau_diffuse"]
    p[:, 5] = resolved["tau_birth"]
    return p


def import_catalog(
    catalog_path: str | Path,
    output_zarr: str,
    ssp_store: str,
    chunk_size: int = 50_000,
    explicit_columns: Mapping[str, str] | None = None,
    client: Any = None,
) -> dict[str, Any]:
    """
    Import an external cosmological simulation catalog (FITS, HDF5, CSV, Parquet)
    and synthesize standard galaxies.zarr dataset.
    """
    raw_data = load_raw_table(catalog_path)
    resolved = resolve_catalog_columns(raw_data, explicit_columns)
    n_gals = len(resolved["mass"])

    # Load SSP age/metallicity grid to construct SFH
    ages = da.from_zarr(ssp_store, component="ages").compute()
    mets = da.from_zarr(ssp_store, component="mets").compute()
    K = len(ages) * len(mets)

    params = catalog_to_params_matrix(resolved)

    n_full, rem = divmod(n_gals, chunk_size)
    row_chunks = (chunk_size,) * n_full + ((rem,) if rem else ())

    # Chunk parameters
    params_da = da.from_array(params, chunks=(row_chunks, (N_PARAM,)))

    def _sfh_block(p_block: np.ndarray) -> np.ndarray:
        return sfh_from_params(p_block, ages, mets)

    sfh_da = da.map_blocks(
        _sfh_block,
        params_da,
        chunks=(row_chunks, (K,)),
        dtype=np.float32,
    )

    arrays_to_write = {
        "sfh": sfh_da,
        "tau_diffuse": params_da[:, 4],
        "tau_birth": params_da[:, 5],
        "params": params_da,
    }

    if "redshift" in resolved:
        z_da = da.from_array(resolved["redshift"], chunks=(row_chunks,))
        arrays_to_write["redshift"] = z_da

    metadata = {
        "source_catalog": str(catalog_path),
        "n_galaxies": n_gals,
        "ssp_grid_k": K,
        "columns_mapped": {k: explicit_columns.get(k, "auto") if explicit_columns else "auto" for k in resolved},
    }

    if client is not None:
        write_many(client, output_zarr, arrays_to_write, metadata=metadata)
    else:
        # In-process write for non-distributed workflows
        tasks = [
            da.to_zarr(a, output_zarr, component=name, overwrite=True, compute=False)
            for name, a in arrays_to_write.items()
        ]
        da.compute(*tasks)

    return metadata
