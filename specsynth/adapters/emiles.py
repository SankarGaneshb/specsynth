from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np

from specsynth.adapters.base import BaseAdapter, SSPData

# Regex for E-MILES and MILES FITS filename convention
# Examples:
#   Ebi1.30Zp0.06T01.0000_iTp0.00_baseFe.fits
#   Mku1.30Zm0.40T10.0000_iTp0.00_baseFe.fits
EMILES_REGEX = re.compile(
    r"[EM][a-zA-Z0-9.]+Z(?P<z_sign>[pm])(?P<z_val>\d+\.\d+)T(?P<age>\d+\.\d+)",
    re.IGNORECASE,
)


def read_fits_1d_spectrum(filepath: str | Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """
    Read a 1D astronomical FITS spectrum (wavelength and flux).
    Uses astropy if installed, otherwise falls back to a built-in pure-Python FITS reader.
    """
    filepath = Path(filepath)

    try:
        from astropy.io import fits
        with fits.open(filepath) as hdul:
            hdr = hdul[0].header
            flux = np.asarray(hdul[0].data, dtype=np.float32).squeeze()
            crval1 = float(hdr.get("CRVAL1", 1.0))
            cdelt1 = float(hdr.get("CDELT1", hdr.get("CD1_1", 1.0)))
            crpix1 = float(hdr.get("CRPIX1", 1.0))
            naxis1 = int(hdr.get("NAXIS1", len(flux)))
            wave = crval1 + (np.arange(naxis1, dtype=np.float64) - (crpix1 - 1.0)) * cdelt1
            return wave, flux, dict(hdr)
    except ImportError:
        pass

    # Built-in pure-Python reader for FITS 1D Primary Array
    with open(filepath, "rb") as f:
        header_text = ""
        while True:
            block = f.read(2880)
            if not block:
                raise ValueError(f"Corrupted or empty FITS file: {filepath}")
            text_block = block.decode("ascii", errors="replace")
            header_text += text_block
            if "END " in text_block:
                break

        hdr = {}
        for i in range(0, len(header_text), 80):
            card = header_text[i : i + 80]
            if card.startswith("END"):
                break
            if "=" in card:
                parts = card.split("=", 1)
                key = parts[0].strip()
                val_comment = parts[1].split("/", 1)
                val_str = val_comment[0].strip().strip("'")
                hdr[key] = val_str

        bitpix = int(hdr.get("BITPIX", -32))
        naxis1 = int(hdr.get("NAXIS1", 0))
        crval1 = float(hdr.get("CRVAL1", 1.0))
        cdelt1 = float(hdr.get("CDELT1", hdr.get("CD1_1", 1.0)))
        crpix1 = float(hdr.get("CRPIX1", 1.0))

        dtype_map = {-32: ">f4", -64: ">f8", 16: ">i2", 32: ">i4"}
        dtype = np.dtype(dtype_map.get(bitpix, ">f4"))
        raw_data = f.read(naxis1 * dtype.itemsize)
        if len(raw_data) < naxis1 * dtype.itemsize:
            raise ValueError(f"Incomplete data array in FITS file: {filepath}")
        flux = np.frombuffer(raw_data, dtype=dtype).astype(np.float32)
        wave = crval1 + (np.arange(naxis1, dtype=np.float64) - (crpix1 - 1.0)) * cdelt1
        return wave, flux, hdr


class EMILESAdapter(BaseAdapter):
    """
    Adapter for E-MILES and MILES (Vazdekis et al.) Single Stellar Population models.
    Parses a directory of individual FITS files or ASCII tables containing models
    across varying metallicities [M/H] and ages T (Gyr).
    """

    def __init__(
        self,
        path: str | Path,
        z_sun: float = 0.019,
        imf_filter: str | None = None,
    ):
        """
        Args:
            path: Path to directory containing E-MILES / MILES FITS files.
            z_sun: Solar metallicity mass fraction used to convert [M/H] to absolute Z.
            imf_filter: Optional substring filter for IMF code (e.g. 'bi1.30', 'ku1.30', 'ch').
        """
        self.path = Path(path)
        self.z_sun = z_sun
        self.imf_filter = imf_filter

    def load(self) -> SSPData:
        if not self.path.is_dir():
            if self.path.is_file():
                # Single FITS file
                return self._load_single_file(self.path)
            raise FileNotFoundError(f"E-MILES path does not exist: {self.path}")

        fits_files = list(self.path.glob("*.fits")) or list(self.path.glob("*.fit"))
        if not fits_files:
            raise FileNotFoundError(f"No FITS files found in {self.path}")

        if self.imf_filter:
            fits_files = [f for f in fits_files if self.imf_filter.lower() in f.name.lower()]
            if not fits_files:
                raise ValueError(
                    f"No files in {self.path} matched IMF filter '{self.imf_filter}'"
                )

        parsed_files = []
        for f in fits_files:
            match = EMILES_REGEX.search(f.name)
            if match:
                z_sign = 1.0 if match.group("z_sign").lower() == "p" else -1.0
                m_h = z_sign * float(match.group("z_val"))  # [M/H] in dex
                z_abs = self.z_sun * (10.0**m_h)            # Absolute Z
                age_gyr = float(match.group("age"))
                age_yr = age_gyr * 1e9                     # Convert Gyr to yr
                parsed_files.append((age_yr, z_abs, f))

        if not parsed_files:
            raise ValueError(
                f"Could not parse E-MILES filename conventions (Z[p/m]...T...) in {self.path}. "
                f"Found {len(fits_files)} files (e.g. {fits_files[0].name})."
            )

        # Extract unique sorted ages and metallicities
        unique_ages = np.unique([item[0] for item in parsed_files])
        unique_mets = np.unique([item[1] for item in parsed_files])
        unique_ages.sort()
        unique_mets.sort()

        age_idx_map = {age: i for i, age in enumerate(unique_ages)}
        met_idx_map = {met: j for j, met in enumerate(unique_mets)}

        # Load reference file to determine wavelength grid
        ref_wave, _, _ = read_fits_1d_spectrum(parsed_files[0][2])
        n_age = len(unique_ages)
        n_met = len(unique_mets)
        n_wave = len(ref_wave)

        grid_3d = np.zeros((n_age, n_met, n_wave), dtype=np.float32)
        filled = np.zeros((n_age, n_met), dtype=bool)

        for age_yr, z_abs, f in parsed_files:
            i = age_idx_map[age_yr]
            j = met_idx_map[z_abs]
            if filled[i, j]:
                continue
            w, flx, _ = read_fits_1d_spectrum(f)
            if len(flx) == n_wave:
                grid_3d[i, j, :] = flx
            else:
                # Interpolate if individual file wavelength grid differs slightly
                grid_3d[i, j, :] = np.interp(ref_wave, w, flx, left=0.0, right=0.0).astype(np.float32)
            filled[i, j] = True

        return SSPData.from_3d_grid(
            ages=unique_ages,
            mets=unique_mets,
            wave=ref_wave,
            grid_3d=grid_3d,
            metadata={
                "model": "E-MILES",
                "directory": str(self.path),
                "n_models": len(parsed_files),
                "z_sun": self.z_sun,
            },
        )

    def _load_single_file(self, filepath: Path) -> SSPData:
        match = EMILES_REGEX.search(filepath.name)
        if match:
            z_sign = 1.0 if match.group("z_sign").lower() == "p" else -1.0
            m_h = z_sign * float(match.group("z_val"))
            z_abs = self.z_sun * (10.0**m_h)
            age_yr = float(match.group("age")) * 1e9
        else:
            z_abs = 0.019
            age_yr = 1e9

        wave, flux, _ = read_fits_1d_spectrum(filepath)
        return SSPData(
            ages=np.array([age_yr]),
            mets=np.array([z_abs]),
            wave=wave,
            ssp=flux.reshape(1, -1),
            metadata={"model": "E-MILES", "file": str(filepath)},
        )
