from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from specsynth.adapters.base import BaseAdapter, SSPData


class FITSGridAdapter(BaseAdapter):
    """
    Adapter for reading SSP grids stored in standard astronomical FITS or HDF5 files
    (e.g., E-MILES, C3K, or custom pipeline outputs).
    """

    def __init__(
        self,
        filepath: str | Path,
        wave_key: str = "WAVE",
        age_key: str = "AGE",
        met_key: str = "MET",
        flux_key: str = "FLUX",
        metadata: dict[str, Any] | None = None,
    ):
        self.filepath = Path(filepath)
        self.wave_key = wave_key
        self.age_key = age_key
        self.met_key = met_key
        self.flux_key = flux_key
        self.user_metadata = metadata or {}

    def load(self) -> SSPData:
        if not self.filepath.is_file():
            raise FileNotFoundError(f"File not found: {self.filepath}")

        suffix = self.filepath.suffix.lower()
        if suffix in (".fits", ".fit", ".fts"):
            return self._load_fits()
        elif suffix in (".h5", ".hdf5"):
            return self._load_hdf5()
        elif suffix == ".npz":
            return self._load_npz()
        else:
            raise ValueError(
                f"Unsupported grid format: '{suffix}'. Expected .fits, .hdf5, or .npz"
            )

    def _load_fits(self) -> SSPData:
        try:
            from astropy.io import fits
        except ImportError as e:
            raise ImportError(
                "astropy is required to read FITS SSP grids. Install it with: "
                "pip install astropy or pip install specsynth[astro]"
            ) from e

        with fits.open(self.filepath) as hdul:
            # Search for datasets either in PrimaryHDU or named HDUs / tables
            data_dict = {}
            for hdu in hdul:
                name = hdu.name.upper()
                if hdu.data is not None:
                    if hasattr(hdu.data, "names") and hdu.data.names:
                        # Binary table HDU
                        for col in hdu.data.names:
                            data_dict[col.upper()] = hdu.data[col]
                    else:
                        # Image / Array HDU
                        data_dict[name] = hdu.data

            # Look up keys case-insensitively
            def find_arr(preferred: str, fallback_candidates: list[str]) -> np.ndarray:
                candidates = [preferred.upper()] + [c.upper() for c in fallback_candidates]
                for c in candidates:
                    if c in data_dict:
                        return np.asarray(data_dict[c])
                raise KeyError(
                    f"Could not find array matching {candidates} in FITS file {self.filepath}. "
                    f"Available keys: {list(data_dict.keys())}"
                )

            wave = find_arr(self.wave_key, ["WAVELENGTH", "WAVELENGTHS", "LAMBDA"])
            ages = find_arr(self.age_key, ["AGES", "LOG_AGE", "TIME"])
            mets = find_arr(self.met_key, ["METS", "METALLICITY", "METALLICITIES", "Z"])
            flux = find_arr(self.flux_key, ["FLUXES", "SED", "SSP", "PRIMARY"])

        return self._build_ssp_data(ages, mets, wave, flux, fmt="fits")

    def _load_hdf5(self) -> SSPData:
        try:
            import h5py
        except ImportError as e:
            raise ImportError(
                "h5py is required to read HDF5 SSP grids. Install it with: "
                "pip install h5py or pip install specsynth[astro]"
            ) from e

        with h5py.File(self.filepath, "r") as hf:
            def find_arr(preferred: str, fallback_candidates: list[str]) -> np.ndarray:
                candidates = [preferred] + fallback_candidates
                for c in candidates:
                    for key in hf.keys():
                        if key.lower() == c.lower():
                            return np.asarray(hf[key])
                raise KeyError(
                    f"Could not find dataset matching {candidates} in HDF5 file {self.filepath}. "
                    f"Available keys: {list(hf.keys())}"
                )

            wave = find_arr(self.wave_key, ["wavelength", "wavelengths", "wave", "lambda"])
            ages = find_arr(self.age_key, ["ages", "age", "log_age", "time"])
            mets = find_arr(self.met_key, ["mets", "metallicity", "metallicities", "z"])
            flux = find_arr(self.flux_key, ["flux", "fluxes", "sed", "ssp", "spectra"])

        return self._build_ssp_data(ages, mets, wave, flux, fmt="hdf5")

    def _load_npz(self) -> SSPData:
        with np.load(self.filepath) as data:
            def find_arr(preferred: str, fallback_candidates: list[str]) -> np.ndarray:
                candidates = [preferred] + fallback_candidates
                for c in candidates:
                    for key in data.files:
                        if key.lower() == c.lower():
                            return np.asarray(data[key])
                raise KeyError(
                    f"Could not find array matching {candidates} in NPZ file. "
                    f"Available: {data.files}"
                )

            wave = find_arr(self.wave_key, ["wave", "wavelength", "wavelengths"])
            ages = find_arr(self.age_key, ["ages", "age"])
            mets = find_arr(self.met_key, ["mets", "met", "metallicity", "z"])
            flux = find_arr(self.flux_key, ["ssp", "flux", "spectra"])

        return self._build_ssp_data(ages, mets, wave, flux, fmt="npz")

    def _build_ssp_data(
        self,
        ages: np.ndarray,
        mets: np.ndarray,
        wave: np.ndarray,
        flux: np.ndarray,
        fmt: str,
    ) -> SSPData:
        # Convert ages in Gyr or log10 yr to linear years if needed
        ages = np.atleast_1d(np.asarray(ages, dtype=np.float64).squeeze())
        if np.all(ages < 100.0):
            # Check if log10(yr) (e.g. 6 to 10.2) or Gyr (0.001 to 13.8)
            if np.all(ages > 5.0):
                # log10(yr)
                ages = 10.0**ages
            else:
                # Gyr
                ages = ages * 1e9

        mets = np.atleast_1d(np.asarray(mets, dtype=np.float64).squeeze())
        wave = np.atleast_1d(np.asarray(wave, dtype=np.float64).squeeze())
        flux = np.asarray(flux, dtype=np.float32)

        if flux.ndim == 3:
            # (n_age, n_met, n_wave)
            return SSPData.from_3d_grid(
                ages=ages,
                mets=mets,
                wave=wave,
                grid_3d=flux,
                metadata={"format": fmt, "file": str(self.filepath), **self.user_metadata},
            )
        elif flux.ndim == 2:
            # Already flattened (K, n_wave)
            return SSPData(
                ages=ages,
                mets=mets,
                wave=wave,
                ssp=flux,
                metadata={"format": fmt, "file": str(self.filepath), **self.user_metadata},
            )
        else:
            raise ValueError(f"Flux array must be 2D or 3D, got ndim={flux.ndim}")
