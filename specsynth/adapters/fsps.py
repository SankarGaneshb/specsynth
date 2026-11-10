from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

from specsynth.adapters.base import BaseAdapter, SSPData


def parse_fsps_spec_file(filepath: str | Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Parse a standard Fortran FSPS ASCII spectrum output file (e.g. spstot_*.spec).
    Format:
      Line 1: # N_WAVE, N_AGE
      Line 2..N_WAVE: wavelengths
      Followed by blocks of (log_age, spectra)
    """
    filepath = Path(filepath)
    with open(filepath, "r") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    # If whitespace-separated grid
    data = np.loadtxt(filepath, comments="#")
    if data.ndim == 2:
        # Standard table: col 0 = wave, cols 1..N = flux per age
        wave = data[:, 0].astype(np.float64)
        fluxes = data[:, 1:].T.astype(np.float32)
        n_age = fluxes.shape[0]
        ages = np.logspace(6.0, np.log10(1.35e10), n_age)
        return ages, wave, fluxes
    else:
        raise ValueError(f"Unable to automatically parse FSPS table format in {filepath}")


class FSPSAdapter(BaseAdapter):
    """
    Adapter for Flexible Stellar Population Synthesis (FSPS).
    Supports either:
      - Programmatic generation using python-fsps
      - Ingestion of raw FSPS ASCII output files (spstot_*.spec)
    """

    def __init__(
        self,
        filepath: str | Path | None = None,
        imf_type: int | str = "chabrier",
        isochrone: str = "mist",
        ages: Sequence[float] | None = None,
        metallicities: Sequence[float] | None = None,
        metallicity: float = 0.019,
        add_nebular_emission: bool = False,
    ):
        self.filepath = Path(filepath) if filepath else None
        self.imf_type = imf_type
        self.isochrone = isochrone
        self.ages = (
            np.asarray(ages, dtype=np.float64)
            if ages is not None
            else np.logspace(6.0, np.log10(1.35e10), 100)
        )
        self.metallicities = (
            np.asarray(metallicities, dtype=np.float64)
            if metallicities is not None
            else None
        )
        self.metallicity = metallicity
        self.add_nebular_emission = add_nebular_emission

    def load(self) -> SSPData:
        # File mode
        if self.filepath:
            ages, wave, fluxes = parse_fsps_spec_file(self.filepath)
            return SSPData.from_3d_grid(
                ages=ages,
                mets=np.array([self.metallicity]),
                wave=wave,
                grid_3d=fluxes[:, None, :],
                metadata={"model": "FSPS", "file": str(self.filepath)},
            )

        # Dynamic python-fsps mode
        try:
            import fsps
        except ImportError as e:
            raise ImportError(
                "python-fsps is required to run the dynamic FSPS adapter. Install it with: "
                "conda install -c conda-forge fsps python-fsps or pip install fsps "
                "or pass an exported FSPS file using --input-file."
            ) from e

        imf_map = {"salpeter": 0, "chabrier": 1, "kroupa": 2}
        imf_code = (
            imf_map.get(str(self.imf_type).lower(), self.imf_type)
            if isinstance(self.imf_type, str)
            else self.imf_type
        )

        sp = fsps.StellarPopulation(
            compute_vega_mags=False,
            zcontinuous=1,
            imf_type=imf_code,
            add_nebular_emission=self.add_nebular_emission,
        )

        if self.metallicities is None:
            z_sun = 0.019
            log_z = sp.zlegend
            mets = (10.0**log_z) * z_sun
        else:
            mets = np.asarray(self.metallicities, dtype=np.float64)

        wave = sp.wavelengths.astype(np.float64)
        n_age = len(self.ages)
        n_met = len(mets)
        n_wave = len(wave)

        grid_3d = np.empty((n_age, n_met, n_wave), dtype=np.float32)

        z_sun = 0.019
        for j, z in enumerate(mets):
            log_z_ratio = np.log10(max(z, 1e-6) / z_sun)
            sp.params["logzsol"] = log_z_ratio
            for i, age_yr in enumerate(self.ages):
                _, flux = sp.get_spectrum(tage=age_yr / 1e9, peraa=True)
                grid_3d[i, j, :] = flux

        return SSPData.from_3d_grid(
            ages=self.ages,
            mets=mets,
            wave=wave,
            grid_3d=grid_3d,
            metadata={
                "model": "FSPS",
                "imf": str(self.imf_type),
                "isochrone": self.isochrone,
                "nebular": self.add_nebular_emission,
            },
        )
