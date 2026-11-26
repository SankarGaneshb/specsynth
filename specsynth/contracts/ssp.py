"""
Versioned SSP Library Grid Contract (v1.0.0).
Defines standard dimensions, units, and physical validation for Simple Stellar Population grids.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import numpy as np


@dataclass
class SSPGridContract:
    """
    Standard container and schema validator for Simple Stellar Population (SSP) grids.

    Attributes:
        version: Schema version string.
        source_engine: Name of generating engine (e.g. FSPS, BC03, BPASS, EMILES).
        engine_version: Version identifier of the generating engine.
        imf: Initial Mass Function (e.g. 'chabrier_2003', 'salpeter_1955', 'kroupa_2001').
        isochrones: Stellar evolution tracks (e.g. 'mist_v1.2', 'padova_1994', 'basti').
        ages_yr: 1D strictly ascending array of stellar ages in years.
        mets_z: 1D strictly ascending array of metallicity mass fractions Z.
        wave_angstrom: 1D strictly ascending array of rest-frame wavelengths in Angstroms.
        ssp_flux_2d: 2D array of luminosity per formed stellar mass of shape
                     (len(ages_yr) * len(mets_z), len(wave_angstrom)) in age-major layout:
                     index k = i_age * n_met + i_met.
                     Units: L_sun / Angstrom per M_sun formed.
        metadata: Arbitrary metadata dictionary for provenance, checksums, and execution flags.
    """
    source_engine: str
    engine_version: str
    imf: str
    isochrones: str
    ages_yr: np.ndarray
    mets_z: np.ndarray
    wave_angstrom: np.ndarray
    ssp_flux_2d: np.ndarray
    version: str = "1.0.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.ages_yr = np.asarray(self.ages_yr, dtype=np.float64)
        self.mets_z = np.asarray(self.mets_z, dtype=np.float64)
        self.wave_angstrom = np.asarray(self.wave_angstrom, dtype=np.float64)
        self.ssp_flux_2d = np.asarray(self.ssp_flux_2d, dtype=np.float32)
        self.validate()

    def validate(self) -> None:
        """Validate dimensions, strictly monotonic axes, non-negativity, and numerical integrity."""
        if self.ages_yr.ndim != 1 or len(self.ages_yr) == 0:
            raise ValueError(f"ages_yr must be a non-empty 1D array, got shape {self.ages_yr.shape}")
        if self.mets_z.ndim != 1 or len(self.mets_z) == 0:
            raise ValueError(f"mets_z must be a non-empty 1D array, got shape {self.mets_z.shape}")
        if self.wave_angstrom.ndim != 1 or len(self.wave_angstrom) == 0:
            raise ValueError(f"wave_angstrom must be a non-empty 1D array, got shape {self.wave_angstrom.shape}")

        if np.any(np.diff(self.ages_yr) <= 0):
            raise ValueError("ages_yr must be strictly monotonically increasing")
        if np.any(np.diff(self.mets_z) <= 0):
            raise ValueError("mets_z must be strictly monotonically increasing")
        if np.any(np.diff(self.wave_angstrom) <= 0):
            raise ValueError("wave_angstrom must be strictly monotonically increasing")

        expected_shape = (len(self.ages_yr) * len(self.mets_z), len(self.wave_angstrom))
        if self.ssp_flux_2d.shape != expected_shape:
            raise ValueError(
                f"ssp_flux_2d shape mismatch: expected {expected_shape} "
                f"(n_age * n_met, n_wave), got {self.ssp_flux_2d.shape}"
            )

        if not np.all(np.isfinite(self.ssp_flux_2d)):
            raise ValueError("ssp_flux_2d contains non-finite values (NaN or Inf)")

        if np.any(self.ssp_flux_2d < 0.0):
            raise ValueError("ssp_flux_2d contains unphysical negative luminosity values")

    def to_dict(self) -> dict[str, Any]:
        """Convert contract metadata and dimension summaries to dictionary."""
        return {
            "version": self.version,
            "source_engine": self.source_engine,
            "engine_version": self.engine_version,
            "imf": self.imf,
            "isochrones": self.isochrones,
            "n_ages": len(self.ages_yr),
            "age_range_yr": [float(self.ages_yr[0]), float(self.ages_yr[-1])],
            "n_mets": len(self.mets_z),
            "met_range_z": [float(self.mets_z[0]), float(self.mets_z[-1])],
            "n_wave": len(self.wave_angstrom),
            "wave_range_angstrom": [float(self.wave_angstrom[0]), float(self.wave_angstrom[-1])],
            "metadata": self.metadata,
        }
