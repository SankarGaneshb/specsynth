from __future__ import annotations

import os
import re
import struct
from pathlib import Path
from typing import Sequence

import numpy as np

from specsynth.adapters.base import BaseAdapter, SSPData

# Standard BC03 metallicity mappings
BC03_METALLICITY_MAP = {
    "m22": 0.0001,
    "m32": 0.0004,
    "m42": 0.004,
    "m52": 0.008,
    "m62": 0.02,
    "m72": 0.05,
}


def read_fortran_record(f) -> bytes:
    """Read a single Fortran unformatted sequential record."""
    raw_len = f.read(4)
    if len(raw_len) < 4:
        return b""
    rec_len = struct.unpack("=i", raw_len)[0]
    data = f.read(rec_len)
    end_len = f.read(4)
    if len(end_len) < 4:
        raise ValueError(f"Corrupted Fortran record: unexpected EOF waiting for tail length {rec_len}")
    trailing_len = struct.unpack("=i", end_len)[0]
    if rec_len != trailing_len:
        raise ValueError(f"Corrupted Fortran record: start {rec_len} != end {trailing_len}")
    return data


def parse_ised_binary(filepath: str | Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Parse a BC03 binary .ised file.
    Returns:
        ages: (n_age,) array in years
        wave: (n_wave,) array in Angstroms
        fluxes: (n_age, n_wave) array in L_sun / A per M_sun
    """
    filepath = Path(filepath)
    with open(filepath, "rb") as f:
        # Record 1: ages
        rec1 = read_fortran_record(f)
        if not rec1:
            raise ValueError(f"Empty or invalid .ised file: {filepath}")
        n_age = struct.unpack("=i", rec1[:4])[0]
        # Ages are stored as float32 in yr (typically 221 age points)
        ages = np.frombuffer(rec1[4 : 4 + n_age * 4], dtype=np.float32).astype(np.float64)

        # Record 2: wavelength grid
        rec2 = read_fortran_record(f)
        n_wave = struct.unpack("=i", rec2[:4])[0]
        wave = np.frombuffer(rec2[4 : 4 + n_wave * 4], dtype=np.float32).astype(np.float64)

        # Remaining records contain spectra for each age step
        fluxes = []
        for _ in range(n_age):
            rec = read_fortran_record(f)
            if not rec:
                break
            # Skip any auxiliary parameters at start of record if present
            # BC03 stores n_wave float32 flux values
            flux_chunk = np.frombuffer(rec[: n_wave * 4], dtype=np.float32)
            if len(flux_chunk) == n_wave:
                fluxes.append(flux_chunk)

        if len(fluxes) != n_age:
            # Alternate layout: all fluxes packed in a single subsequent record
            if len(fluxes) == 0:
                rec_all = read_fortran_record(f)
                arr = np.frombuffer(rec_all, dtype=np.float32)
                if len(arr) >= n_age * n_wave:
                    fluxes = [arr[i * n_wave : (i + 1) * n_wave] for i in range(n_age)]

        if len(fluxes) != n_age:
            raise ValueError(
                f"Expected {n_age} age spectra from {filepath}, but parsed {len(fluxes)}"
            )

        flux_matrix = np.stack(fluxes, axis=0).astype(np.float32)

    return ages, wave, flux_matrix


def parse_bc03_ascii(filepath: str | Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Parse a BC03 text / ASCII export table.
    Expects whitespace-delimited table with wavelength as first column, followed by ages.
    """
    data = np.loadtxt(filepath)
    wave = data[:, 0].astype(np.float64)
    fluxes = data[:, 1:].T.astype(np.float32)  # (n_age, n_wave)
    # Default logarithmic age steps if not in file
    n_age = fluxes.shape[0]
    ages = np.logspace(6.0, np.log10(1.3e10), n_age)
    return ages, wave, fluxes


class BC03Adapter(BaseAdapter):
    """
    Adapter for Bruzual & Charlot (2003) stellar population synthesis models.
    Supports either:
      - A directory of .ised / ASCII files for multiple metallicities
      - A single file (with specified metallicity)
    """

    def __init__(
        self,
        path: str | Path,
        metallicity: float | None = None,
        imf: str = "chabrier",
    ):
        self.path = Path(path)
        self.metallicity = metallicity
        self.imf = imf

    def load(self) -> SSPData:
        if self.path.is_file():
            # Single file mode
            z = self.metallicity
            if z is None:
                # Infer from filename
                for code, val in BC03_METALLICITY_MAP.items():
                    if code in self.path.name.lower():
                        z = val
                        break
                if z is None:
                    z = 0.02  # Default to solar if unspecified

            if self.path.suffix.lower() == ".ised":
                ages, wave, fluxes = parse_ised_binary(self.path)
            else:
                ages, wave, fluxes = parse_bc03_ascii(self.path)

            return SSPData.from_3d_grid(
                ages=ages,
                mets=np.array([z]),
                wave=wave,
                grid_3d=fluxes[:, None, :],
                metadata={
                    "model": "BC03",
                    "file": str(self.path),
                    "imf": self.imf,
                },
            )

        elif self.path.is_dir():
            # Directory containing multiple metallicity files
            files = list(self.path.glob("*.ised")) or list(self.path.glob("*.spec")) or list(self.path.glob("*.txt"))
            if not files:
                raise FileNotFoundError(f"No BC03 model files (.ised, .spec, .txt) found in {self.path}")

            met_entries = []
            for f in files:
                z = None
                for code, val in BC03_METALLICITY_MAP.items():
                    if code in f.name.lower():
                        z = val
                        break
                if z is not None:
                    met_entries.append((z, f))

            if not met_entries:
                raise ValueError(
                    f"Could not infer metallicity codes (e.g. m22, m62) from filenames in {self.path}"
                )

            # Sort by metallicity
            met_entries.sort(key=lambda item: item[0])
            mets = np.array([m[0] for m in met_entries], dtype=np.float64)

            # Read first to get grid dimensions
            first_z, first_file = met_entries[0]
            if first_file.suffix.lower() == ".ised":
                ages, wave, first_flux = parse_ised_binary(first_file)
                parser = parse_ised_binary
            else:
                ages, wave, first_flux = parse_bc03_ascii(first_file)
                parser = parse_bc03_ascii

            grid_3d = np.empty((len(ages), len(mets), len(wave)), dtype=np.float32)
            grid_3d[:, 0, :] = first_flux

            for i, (z, f) in enumerate(met_entries[1:], start=1):
                _, _, flx = parser(f)
                grid_3d[:, i, :] = flx

            return SSPData.from_3d_grid(
                ages=ages,
                mets=mets,
                wave=wave,
                grid_3d=grid_3d,
                metadata={
                    "model": "BC03",
                    "directory": str(self.path),
                    "imf": self.imf,
                    "n_files": len(met_entries),
                },
            )
        else:
            raise FileNotFoundError(f"Path does not exist: {self.path}")
