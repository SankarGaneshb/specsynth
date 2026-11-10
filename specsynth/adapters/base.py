from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class SSPData:
    """
    Standard container for Simple Stellar Population (SSP) library grids.

    Attributes:
        ages: 1D array of stellar ages in years (strictly ascending).
        mets: 1D array of metallicities in mass fraction Z (strictly ascending).
        wave: 1D array of wavelengths in Angstroms (strictly ascending).
        ssp: 2D array of luminosity per unit formed stellar mass of shape
             (len(ages) * len(mets), len(wave)), stored in age-major layout:
             k = i_age * n_met + i_met.
        metadata: Arbitrary metadata dictionary for provenance, IMF, and isochrones.
    """
    ages: np.ndarray
    mets: np.ndarray
    wave: np.ndarray
    ssp: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.ages = np.asarray(self.ages, dtype=np.float64)
        self.mets = np.asarray(self.mets, dtype=np.float64)
        self.wave = np.asarray(self.wave, dtype=np.float64)
        self.ssp = np.asarray(self.ssp, dtype=np.float32)
        self.validate()

    def validate(self):
        """Validate dimensions, ordering, and numerical validity."""
        if self.ages.ndim != 1 or len(self.ages) == 0:
            raise ValueError(f"ages must be a non-empty 1D array, got shape {self.ages.shape}")
        if self.mets.ndim != 1 or len(self.mets) == 0:
            raise ValueError(f"mets must be a non-empty 1D array, got shape {self.mets.shape}")
        if self.wave.ndim != 1 or len(self.wave) == 0:
            raise ValueError(f"wave must be a non-empty 1D array, got shape {self.wave.shape}")

        if np.any(np.diff(self.ages) <= 0):
            raise ValueError("ages must be strictly monotonically increasing")
        if np.any(np.diff(self.wave) <= 0):
            raise ValueError("wave must be strictly monotonically increasing")

        expected_shape = (len(self.ages) * len(self.mets), len(self.wave))
        if self.ssp.shape != expected_shape:
            raise ValueError(
                f"ssp shape mismatch: expected {expected_shape} "
                f"(n_age * n_met, n_wave), got {self.ssp.shape}"
            )

        if not np.all(np.isfinite(self.ssp)):
            raise ValueError("ssp contains non-finite values (NaN or Inf)")

    @classmethod
    def from_3d_grid(
        cls,
        ages: np.ndarray,
        mets: np.ndarray,
        wave: np.ndarray,
        grid_3d: np.ndarray,
        metadata: dict[str, Any] | None = None,
    ) -> SSPData:
        """
        Construct SSPData from a 3D grid of shape (n_age, n_met, n_wave),
        automatically flattening to age-major layout k = i_age * n_met + i_met.
        """
        ages = np.asarray(ages, dtype=np.float64)
        mets = np.asarray(mets, dtype=np.float64)
        wave = np.asarray(wave, dtype=np.float64)
        grid_3d = np.asarray(grid_3d, dtype=np.float32)

        expected = (len(ages), len(mets), len(wave))
        if grid_3d.shape != expected:
            raise ValueError(f"grid_3d shape {grid_3d.shape} does not match expected {expected}")

        # Ensure sorted ages and metallicities
        age_order = np.argsort(ages)
        met_order = np.argsort(mets)
        wave_order = np.argsort(wave)

        ages = ages[age_order]
        mets = mets[met_order]
        wave = wave[wave_order]

        # Reindex grid along each dimension
        grid_3d = grid_3d[age_order][:, met_order][:, :, wave_order]
        ssp_2d = grid_3d.reshape(-1, len(wave))

        return cls(
            ages=ages,
            mets=mets,
            wave=wave,
            ssp=ssp_2d,
            metadata=metadata or {},
        )

    def resample_wavelength(self, target_wave: np.ndarray) -> SSPData:
        """
        Resample the SSP library onto a new wavelength grid using linear interpolation.
        """
        target_wave = np.asarray(target_wave, dtype=np.float64)
        if np.any(np.diff(target_wave) <= 0):
            raise ValueError("target_wave must be strictly monotonically increasing")

        # Vectorized interpolation for each row in ssp
        resampled = np.empty((self.ssp.shape[0], len(target_wave)), dtype=np.float32)
        for i in range(self.ssp.shape[0]):
            resampled[i] = np.interp(target_wave, self.wave, self.ssp[i], left=0.0, right=0.0)

        meta = dict(self.metadata)
        meta["resampled"] = True
        return SSPData(
            ages=self.ages.copy(),
            mets=self.mets.copy(),
            wave=target_wave,
            ssp=resampled,
            metadata=meta,
        )


class BaseAdapter(ABC):
    """Abstract base class for SSP model adapters."""

    @abstractmethod
    def load(self) -> SSPData:
        """Load and return validated SSP data."""
        pass
