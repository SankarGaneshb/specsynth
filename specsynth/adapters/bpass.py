"""
BPASS adapter: Model loader for Binary Population and Spectral Synthesis (BPASS v2.2+).
Eldridge et al. (2017), Stanway & Eldridge (2018).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Sequence

import numpy as np

from specsynth.adapters.base import BaseAdapter, SSPData

BPASS_Z_REGEX = re.compile(r"z(?:em(?P<em_exp>\d+)|(?P<z_val>0\d+)|(?P<z_float>\d+\.\d+))", re.IGNORECASE)

BPASS_STANDARD_LOG_AGES = np.arange(6.0, 11.05, 0.1)  # 51 age bins from 10^6.0 to 10^11.0 yr
BPASS_STANDARD_AGES = 10.0**BPASS_STANDARD_LOG_AGES


def parse_bpass_z_from_filename(filename: str, default_z: float | None = None) -> float | None:
    """Extract metallicity mass fraction Z from BPASS filename (e.g. 'spectot-bin-imf135_300.z020.dat')."""
    m = BPASS_Z_REGEX.search(filename)
    if not m:
        return default_z
    if m.group("em_exp"):
        return 10.0 ** (-float(m.group("em_exp")))
    if m.group("z_val"):
        val_str = m.group("z_val")  # e.g. '020' -> 0.020, '001' -> 0.001
        return float(f"0.{val_str}")
    if m.group("z_float"):
        return float(m.group("z_float"))
    return default_z


def parse_bpass_ascii_file(filepath: Path | str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Parse a standard BPASS spectot ASCII data file.

    Format:
      - Column 0: Wavelength in Angstroms (1 to 100,000 A)
      - Columns 1-51: Luminosity density (L_sun / A per 1e6 M_sun formed) for 51 age steps (6.0 to 11.0 dex).

    Returns:
      (ages, wave, fluxes) where fluxes is of shape (n_age, n_wave) in L_sun / A per M_sun.
    """
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"BPASS file not found: {path}")

    # Load data table (ignoring any comment headers)
    data = np.loadtxt(path, comments="#")
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError(f"Invalid BPASS file format in '{path}': Expected at least 2 columns (wavelength + age bins), got shape {data.shape}")

    wave = data[:, 0].astype(np.float64)
    # Columns 1.. are the age steps
    flux_cols = data[:, 1:].astype(np.float32)
    n_cols = flux_cols.shape[1]

    if n_cols == len(BPASS_STANDARD_AGES):
        ages = BPASS_STANDARD_AGES
    else:
        # Custom or truncated age grid
        ages = 10.0 ** np.linspace(6.0, 6.0 + 0.1 * (n_cols - 1), n_cols)

    # Convert from per 1e6 M_sun to per 1 M_sun formed
    fluxes = (flux_cols.T / 1.0e6).astype(np.float32)  # (n_age, n_wave)

    return ages, wave, fluxes


class BPASSAdapter(BaseAdapter):
    """
    Adapter for Binary Population and Spectral Synthesis (BPASS v2.2+).
    Supports either:
      - Single BPASS ASCII spectrum file (e.g. spectot-*.dat)
      - Directory of BPASS metallicity tables
      - Pre-compiled FITS/HDF5 grids via generic reader
    """

    def __init__(
        self,
        filepath: str | Path | None = None,
        path: str | Path | None = None,
        input_file: str | Path | None = None,
        input_path: str | Path | None = None,
        metallicity: float | None = None,
    ):
        target = filepath or path or input_file or input_path
        if not target:
            raise ValueError("BPASSAdapter requires either 'filepath', 'path', 'input_file', or 'input_path' pointing to BPASS model file(s).")
        self.path = Path(target)
        self.metallicity = metallicity

    def load(self) -> SSPData:
        if self.path.is_file():
            ext = self.path.suffix.lower()
            if ext in (".fits", ".fit", ".h5", ".hdf5", ".npz"):
                from specsynth.adapters.fits_grid import FITSGridAdapter
                return FITSGridAdapter(self.path).load()

            # Single ASCII table
            z = self.metallicity if self.metallicity is not None else parse_bpass_z_from_filename(self.path.name)
            if z is None:
                raise ValueError(f"Explicit --metallicity must be provided for BPASS file '{self.path.name}' when metallicity cannot be parsed from filename.")
            ages, wave, fluxes = parse_bpass_ascii_file(self.path)
            return SSPData.from_3d_grid(
                ages=ages,
                mets=np.array([z], dtype=np.float64),
                wave=wave,
                grid_3d=fluxes[:, None, :],
                metadata={"model": "BPASS", "file": str(self.path), "Z": z},
            )

        if self.path.is_dir():
            # Parse directory containing multiple metallicity files
            dat_files = sorted(self.path.glob("*.dat")) + sorted(self.path.glob("*.txt"))
            if not dat_files:
                raise FileNotFoundError(f"No BPASS .dat or .txt files found in directory: {self.path}")

            parsed = []
            for f in dat_files:
                z = parse_bpass_z_from_filename(f.name)
                if z is not None:
                    parsed.append((z, f))

            if not parsed:
                raise ValueError(f"Could not parse metallicities from any BPASS files in directory: {self.path}")

            # Deduplicate by metallicity
            unique_mets = np.unique([item[0] for item in parsed])
            unique_mets.sort()

            ref_ages, ref_wave, ref_flux = parse_bpass_ascii_file(parsed[0][1])
            n_age = len(ref_ages)
            n_met = len(unique_mets)
            n_wave = len(ref_wave)

            grid_3d = np.zeros((n_age, n_met, n_wave), dtype=np.float32)
            met_idx_map = {z: j for j, z in enumerate(unique_mets)}

            for z, f in parsed:
                j = met_idx_map[z]
                _, _, fluxes = parse_bpass_ascii_file(f)
                grid_3d[:, j, :] = fluxes

            return SSPData.from_3d_grid(
                ages=ref_ages,
                mets=unique_mets,
                wave=ref_wave,
                grid_3d=grid_3d,
                metadata={"model": "BPASS", "directory": str(self.path), "n_metallicities": n_met},
            )

        raise FileNotFoundError(f"BPASS model path does not exist: {self.path}")
